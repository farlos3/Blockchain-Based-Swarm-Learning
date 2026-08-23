"""Consensus: who may seal a block, and how everyone else re-checks that later

Two mechanisms are provided so the thesis can compare them
  ProofOfAuthority (default) — fits a consortium whose members already know each other
  ProofOfWork                 — kept only to show why that route was not chosen

PoA here has the three parts the definition calls for
  1. authority set  the list of authorized nodes + their public keys, published on the chain
  2. leader rule    whose turn it is in a given round, derived from the round number alone
                    (nobody has to appoint anyone)
  3. block seal     the leader signs the block hash with its own private key
                    anyone holding the chain file + public keys can check it, trusting no one
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from blockchain import Block, ChainError, canonical_json

TX_AGGREGATION = "aggregation"  # this PoC seals one round per block; the round number lives in this tx type


# ---------- node keys ----------


class NodeKey:
    """One node's key pair — in production this must never leave that node's machine"""

    def __init__(self, node_id: str, private_key: Ed25519PrivateKey) -> None:
        self.node_id = node_id
        self._private_key = private_key

    @classmethod
    def generate(cls, node_id: str, seed: str | None = None) -> NodeKey:
        """seed exists so demos/tests get the same keys every run — production must be fully random"""
        if seed is None:
            return cls(node_id, Ed25519PrivateKey.generate())
        material = hashlib.sha256(f"{node_id}:{seed}".encode("utf-8")).digest()
        return cls(node_id, Ed25519PrivateKey.from_private_bytes(material))

    def public_hex(self) -> str:
        raw = self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return raw.hex()

    def sign(self, message: str) -> str:
        return self._private_key.sign(message.encode("utf-8")).hex()


class AuthoritySet:
    """Authorized nodes + their public keys — member order affects leader election, so it must be preserved"""

    def __init__(self, public_keys: dict[str, str]) -> None:
        if not public_keys:
            raise ValueError("the authority set cannot be empty")
        self._keys = dict(public_keys)

    @classmethod
    def from_keys(cls, keys: Sequence[NodeKey]) -> AuthoritySet:
        return cls({k.node_id: k.public_hex() for k in keys})

    @property
    def members(self) -> list[str]:
        return list(self._keys)

    def __contains__(self, node_id: object) -> bool:
        return node_id in self._keys

    def verify(self, node_id: str, message: str, signature_hex: str) -> bool:
        if node_id not in self._keys:
            return False
        public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(self._keys[node_id]))
        try:
            public_key.verify(bytes.fromhex(signature_hex), message.encode("utf-8"))
        except (InvalidSignature, ValueError):
            return False
        return True

    def to_dict(self) -> dict[str, str]:
        return dict(self._keys)


# ---------- leader rule ----------


def elect_leader(round_num: int, participants: Sequence[str]) -> str:
    """The round's leader = sha256(round number + participant list) mod participant count

    Same formula ini_swarm.ipynb uses. Every node computes it independently and agrees,
    and anyone can go back and check whose turn a past round was without trusting a record.
    """
    digest = hashlib.sha256(f"round-{round_num}:{','.join(participants)}".encode("utf-8")).hexdigest()
    return participants[int(digest, 16) % len(participants)]


def block_round(block: Block) -> int | None:
    """Find a block's round from its aggregation transaction (None = this block does not close a swarm round)"""
    for tx in block.transactions:
        if tx.get("type") == TX_AGGREGATION:
            return tx.get("round")
    return None


# ---------- mechanisms ----------


class Consensus(Protocol):
    name: str

    def seal(self, block: Block, sealer: NodeKey | None = None) -> Block: ...
    def verify(self, block: Block) -> None: ...
    def to_dict(self) -> dict[str, Any]: ...


@dataclass
class ProofOfWork:
    """Search for a nonce until the hash starts with `difficulty` zeros

    Not the mechanism we picked. It is here to show that in a consortium of known
    members, burning CPU against each other adds no security — only latency and a power bill.
    """

    difficulty: int = 0
    name: str = "pow"

    def seal(self, block: Block, sealer: NodeKey | None = None) -> Block:
        from dataclasses import replace

        target = "0" * self.difficulty
        while not block.compute_hash().startswith(target):
            block = replace(block, nonce=block.nonce + 1)
        return block

    def verify(self, block: Block) -> None:
        if self.difficulty and not block.compute_hash().startswith("0" * self.difficulty):
            raise ChainError(f"block {block.index}: hash does not meet difficulty {self.difficulty}")

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "difficulty": self.difficulty}


class ProofOfAuthority:
    """A block is accepted only if the leader of that round sealed it personally

    verify() checks three layers
      1. is the sealer in the authority set?
      2. is the sealer the leader of that round by the rule? (membership alone does not
         let a node seal out of turn)
      3. is the signature over the block hash valid against the published public key?
    """

    name = "poa"

    def __init__(self, authorities: AuthoritySet, enforce_leader: bool = True) -> None:
        self.authorities = authorities
        self.enforce_leader = enforce_leader

    def seal(self, block: Block, sealer: NodeKey | None = None) -> Block:
        from dataclasses import replace

        if sealer is None:
            raise ChainError("PoA requires a named sealer (nobody seals a block anonymously)")
        if sealer.node_id not in self.authorities:
            raise ChainError(f"{sealer.node_id} is not in the authority set")

        block = replace(block, sealer=sealer.node_id)
        return replace(block, seal=sealer.sign(block.compute_hash()))

    def verify(self, block: Block) -> None:
        if not block.sealer or not block.seal:
            raise ChainError(f"block {block.index}: no sealer signature")
        if block.sealer not in self.authorities:
            raise ChainError(f"block {block.index}: sealer {block.sealer} is not in the authority set")

        if self.enforce_leader:
            round_num = block_round(block)
            if round_num is not None:
                expected = elect_leader(round_num, self.authorities.members)
                if block.sealer != expected:
                    raise ChainError(
                        f"block {block.index}: round {round_num} belongs to {expected} "
                        f"but {block.sealer} sealed the block"
                    )

        if not self.authorities.verify(block.sealer, block.compute_hash(), block.seal):
            raise ChainError(f"block {block.index}: signature from {block.sealer} is invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "authorities": self.authorities.to_dict(),
            "leader_rule": "sha256(round + members)",
            "enforce_leader": self.enforce_leader,
        }


def consensus_from_dict(data: dict[str, Any] | None) -> Consensus:
    """Rebuild the mechanism from a chain file, so whoever holds only chain.json can verify it in full"""
    if not data or data.get("name") == "pow":
        return ProofOfWork(difficulty=(data or {}).get("difficulty", 0))
    if data["name"] == "poa":
        return ProofOfAuthority(
            AuthoritySet(data["authorities"]),
            enforce_leader=data.get("enforce_leader", True),
        )
    raise ValueError(f"unknown mechanism {data['name']!r}")


def sign_payload(key: NodeKey, payload: dict[str, Any]) -> str:
    """Sign a transaction — over its canonical form, so a verifier can reproduce the exact message"""
    return key.sign(canonical_json(payload))


def verify_payload(authorities: AuthoritySet, node_id: str, payload: dict[str, Any],
                   signature_hex: str) -> bool:
    return authorities.verify(node_id, canonical_json(payload), signature_hex)
