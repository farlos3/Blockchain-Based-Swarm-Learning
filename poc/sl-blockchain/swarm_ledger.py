"""Ledger layer: recording swarm learning rounds on a Proof of Authority blockchain

Same idea as the earlier sl-ledger chaincode (Go): real model weights stay off-chain
because they are far too large for a block. The chain holds only hashes plus the round
ledger, enough to check afterwards "which round, who submitted what, who aggregated".

This PoC's convention: 1 swarm round = 1 block.
A block therefore carries every node's model_update for that round plus the leader's aggregation.

Every transaction must carry its sender's signature, and only the round's leader may seal
the block. The rules enforced here are the ones that correspond to the smart contract:
  - the sender must be in the authority set and the signature must match the published public key
  - one node may submit once per round
  - the sealer must really be that round's leader (like the AggregatorMSP check)
  - a closed round cannot be reopened
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from blockchain import Block, Blockchain, canonical_json
from consensus import (
    AuthoritySet,
    NodeKey,
    ProofOfAuthority,
    elect_leader,
    sign_payload,
    verify_payload,
)

TX_MODEL_UPDATE = "model_update"
TX_AGGREGATION = "aggregation"

__all__ = [
    "LedgerError", "SwarmLedger", "NodeKey", "elect_leader",
    "hash_params", "params_size_bytes", "audit_chain",
]


class LedgerError(Exception):
    """A transaction broke a ledger rule — the equivalent of chaincode rejecting a transaction"""


def hash_params(coef: np.ndarray, intercept: np.ndarray) -> str:
    """Fingerprint of the model parameters — equal values hash equal, one differing bit changes everything

    The name and shape go into the digest too, so swapped coef/intercept cannot collide.
    """
    digest = hashlib.sha256()
    for name, array in (("coef", coef), ("intercept", intercept)):
        values = np.ascontiguousarray(array, dtype=np.float64)
        digest.update(name.encode("utf-8"))
        digest.update(canonical_json(list(values.shape)).encode("utf-8"))
        digest.update(values.tobytes())
    return digest.hexdigest()


def params_size_bytes(coef: np.ndarray, intercept: np.ndarray) -> int:
    """Bytes of parameters actually shipped per round (used to estimate bandwidth / ledger growth)"""
    return int(np.asarray(coef).nbytes + np.asarray(intercept).nbytes)


def unsigned_view(tx: dict[str, Any]) -> dict[str, Any]:
    """The signed portion of a transaction — every field except the signature itself"""
    return {k: v for k, v in tx.items() if k != "signature"}


class SwarmLedger:
    """The API nodes call — method names mirror the original sl-ledger chaincode

    submit_update() buffers into pending; record_aggregation() then closes that round into a block.
    (Fabric analogy: pending is an endorsed transaction waiting for the orderer to cut a block.)
    """

    def __init__(self, keys: Sequence[NodeKey], chain: Blockchain | None = None) -> None:
        if not keys:
            raise ValueError("at least one participant is required")
        self.keys = {k.node_id: k for k in keys}
        self.authorities = AuthoritySet.from_keys(list(keys))
        self.chain = chain if chain is not None else Blockchain(
            consensus=ProofOfAuthority(self.authorities)
        )
        self._pending: list[dict[str, Any]] = []

    @classmethod
    def bootstrap(cls, participants: Sequence[str], seed: str | None = None) -> SwarmLedger:
        """Create the swarm and every node's key in one call

        Possible only because this PoC runs in a single process. In production each node
        generates its key locally and sends nothing but the public key for registration
        into the authority set.
        """
        return cls([NodeKey.generate(name, seed=seed) for name in participants])

    @property
    def participants(self) -> list[str]:
        return self.authorities.members

    # ---------- write ----------

    def submit_update(self, round_num: int, node_id: str, coef: np.ndarray,
                      intercept: np.ndarray, n_samples: int,
                      key: NodeKey | None = None) -> dict[str, Any]:
        """A node announces its local training result for the round (hash only, never the weights) and signs it"""
        signing_key = key or self.keys.get(node_id)
        if signing_key is None:
            raise LedgerError(f"no key for node {node_id}, cannot sign the transaction on its behalf")

        tx = {
            "type": TX_MODEL_UPDATE,
            "round": round_num,
            "node_id": node_id,
            "weight_hash": hash_params(coef, intercept),
            "size_bytes": params_size_bytes(coef, intercept),
            "n_samples": int(n_samples),
            "timestamp": time.time(),
        }
        tx["signature"] = sign_payload(signing_key, tx)
        return self.submit_signed_update(tx)

    def submit_signed_update(self, tx: dict[str, Any]) -> dict[str, Any]:
        """Accept an already-signed transaction (the same path a real network would use) — always check first"""
        node_id = tx.get("node_id")
        round_num = tx.get("round")

        if node_id not in self.authorities:
            raise LedgerError(f"node {node_id} is not in this swarm's authority set")
        if not verify_payload(self.authorities, node_id, unsigned_view(tx), tx.get("signature", "")):
            raise LedgerError(f"signature from node {node_id} is invalid, transaction rejected")
        if round_num in self.committed_rounds():
            raise LedgerError(f"round {round_num} is already sealed, no further updates accepted")
        for pending in self._pending:
            if pending["round"] == round_num and pending["node_id"] == node_id:
                raise LedgerError(f"node {node_id} already submitted an update for round {round_num}")

        self._pending.append(tx)
        return tx

    def record_aggregation(self, round_num: int, leader: str, coef: np.ndarray,
                           intercept: np.ndarray, accuracy: float | None = None,
                           key: NodeKey | None = None) -> Block:
        """The round's leader records the global model hash, signs the block, and only then it joins the chain"""
        expected = elect_leader(round_num, self.participants)
        if leader != expected:
            raise LedgerError(
                f"round {round_num} leader must be {expected}, not {leader}, aggregation rejected"
            )
        if round_num in self.committed_rounds():
            raise LedgerError(f"round {round_num} already has an aggregation")

        signing_key = key or self.keys.get(leader)
        if signing_key is None:
            raise LedgerError(f"no key for leader {leader}, cannot seal the block on its behalf")

        updates = [tx for tx in self._pending if tx["round"] == round_num]
        if not updates:
            raise LedgerError(f"round {round_num} has no updates to aggregate")

        aggregation = {
            "type": TX_AGGREGATION,
            "round": round_num,
            "aggregator": leader,
            "aggregated_hash": hash_params(coef, intercept),
            "participant_count": len(updates),
            "total_samples": sum(tx["n_samples"] for tx in updates),
            "accuracy": None if accuracy is None else round(float(accuracy), 6),
            "timestamp": time.time(),
        }
        aggregation["signature"] = sign_payload(signing_key, aggregation)

        block = self.chain.add_block(updates + [aggregation], sealer=signing_key)
        self._pending = [tx for tx in self._pending if tx["round"] != round_num]
        return block

    # ---------- read / verify ----------

    def committed_rounds(self) -> list[int]:
        return [tx["round"] for tx in self.chain.transactions(TX_AGGREGATION)]

    def get_round_updates(self, round_num: int) -> list[dict[str, Any]]:
        return [tx for tx in self.chain.transactions(TX_MODEL_UPDATE) if tx["round"] == round_num]

    def get_aggregation(self, round_num: int) -> dict[str, Any]:
        for tx in self.chain.transactions(TX_AGGREGATION):
            if tx["round"] == round_num:
                return tx
        raise LedgerError(f"no aggregation found for round {round_num}")

    def verify_round(self, round_num: int, coef: np.ndarray, intercept: np.ndarray) -> bool:
        """A node checks that the global model it holds really matches what the chain recorded for that round"""
        return hash_params(coef, intercept) == self.get_aggregation(round_num)["aggregated_hash"]

    def leader_counts(self) -> dict[str, int]:
        """How many rounds each node led — read from the chain, not from an in-memory counter"""
        counts = {name: 0 for name in self.participants}
        for tx in self.chain.transactions(TX_AGGREGATION):
            counts[tx["aggregator"]] = counts.get(tx["aggregator"], 0) + 1
        return counts

    def ledger_bytes(self) -> int:
        """Chain size if saved as JSON — used to watch ledger growth per round"""
        return len(canonical_json(self.chain.to_dict()).encode("utf-8"))

    def audit(self) -> dict[str, Any]:
        return audit_chain(self.chain)


def audit_chain(source: Blockchain | str | Path) -> dict[str, Any]:
    """Verify a whole chain while trusting no one — works from chain.json alone

    Three layers: chain structure, the sealer's signature and whether it was that round's
    leader, and the signature on every transaction. (Authority public keys live in the
    chain file, so an outsider has everything needed.)
    """
    chain = source if isinstance(source, Blockchain) else Blockchain.load(source)
    chain.validate()

    consensus = chain.consensus
    authorities = getattr(consensus, "authorities", None)
    checked = 0
    if authorities is not None:
        for tx in chain.transactions():
            signer = tx.get("node_id") or tx.get("aggregator")
            signature = tx.get("signature")
            if not signer or not signature:
                raise LedgerError(f"unsigned transaction: {tx.get('type')} round {tx.get('round')}")
            if not verify_payload(authorities, signer, unsigned_view(tx), signature):
                raise LedgerError(
                    f"invalid transaction signature: {tx.get('type')} round {tx.get('round')} by {signer}"
                )
            checked += 1

    return {
        "consensus": consensus.to_dict().get("name"),
        "blocks": chain.height,
        "transactions_verified": checked,
        "authorities": authorities.members if authorities else [],
    }
