"""A small append-only blockchain for the swarm learning PoC

Meant to be read end to end in one file. The single idea that makes it a blockchain
is that every block stores the sha256 of the block before it. Rewrite an old block and
its hash no longer matches what the next block points at; validate() reports exactly
which block broke.

"Who is allowed to seal a block" lives in consensus.py (this project defaults to PoA).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator

if TYPE_CHECKING:  # imported this way to avoid a circular import (consensus.py uses this file)
    from consensus import Consensus, NodeKey

GENESIS_PREV_HASH = "0" * 64


def canonical_json(value: Any) -> str:
    """Serialize to the same bytes every time (sorted keys, no stray whitespace)

    If key order could drift, the hash would change even though the content did not,
    and cross-machine verification would break immediately. The format is pinned here,
    in one place.
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(data: str) -> str:
    return sha256(data.encode("utf-8")).hexdigest()


class ChainError(Exception):
    """The chain is inconsistent — the message says which block broke and why"""


@dataclass(frozen=True)
class Block:
    """One block = one swarm round's transactions + the link to the previous block + the sealer's signature"""

    index: int
    timestamp: float
    prev_hash: str
    transactions: tuple[dict[str, Any], ...]
    nonce: int = 0
    sealer: str | None = None        # the node that sealed this block (PoA)
    seal: str | None = None          # the sealer's signature over the block hash
    stored_hash: str | None = None   # hash as read from file, used to detect edits

    def tx_root(self) -> str:
        """Reduce every transaction in the block to one value (a simple Merkle root: one hash over all of them)"""
        return sha256_hex(canonical_json(list(self.transactions)))

    def header(self) -> dict[str, Any]:
        """The part that gets hashed — excludes the block's own hash and the signature over that hash"""
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "prev_hash": self.prev_hash,
            "tx_root": self.tx_root(),
            "nonce": self.nonce,
            "sealer": self.sealer,
        }

    def compute_hash(self) -> str:
        return sha256_hex(canonical_json(self.header()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "prev_hash": self.prev_hash,
            "transactions": list(self.transactions),
            "nonce": self.nonce,
            "sealer": self.sealer,
            "seal": self.seal,
            "hash": self.compute_hash(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Block:
        return cls(
            index=data["index"],
            timestamp=data["timestamp"],
            prev_hash=data["prev_hash"],
            transactions=tuple(data["transactions"]),
            nonce=data.get("nonce", 0),
            sealer=data.get("sealer"),
            seal=data.get("seal"),
            stored_hash=data.get("hash"),
        )


class Blockchain:
    """An in-memory chain that can be saved to and loaded from JSON

    consensus decides who may seal a block and how anyone re-checks that later.
    Left unset it is ProofOfWork(difficulty), where difficulty=0 means no condition at all.
    """

    def __init__(self, consensus: Consensus | None = None, difficulty: int = 0) -> None:
        if consensus is None:
            from consensus import ProofOfWork

            consensus = ProofOfWork(difficulty=difficulty)
        self.consensus = consensus
        self.blocks: list[Block] = [self._genesis()]

    @staticmethod
    def _genesis() -> Block:
        # fixed timestamp so rebuilding the chain always yields the same genesis hash (reproducible tests)
        return Block(index=0, timestamp=0.0, prev_hash=GENESIS_PREV_HASH, transactions=())

    @property
    def last_block(self) -> Block:
        return self.blocks[-1]

    @property
    def height(self) -> int:
        """Number of blocks carrying data (genesis excluded)"""
        return len(self.blocks) - 1

    def add_block(self, transactions: list[dict[str, Any]], sealer: NodeKey | None = None) -> Block:
        if not transactions:
            raise ValueError("an empty block is pointless: at least one transaction is required")

        block = Block(
            index=self.last_block.index + 1,
            timestamp=time.time(),
            prev_hash=self.last_block.compute_hash(),
            transactions=tuple(transactions),
        )
        block = self.consensus.seal(block, sealer)
        self.consensus.verify(block)  # a sealed block must pass its own rules before joining the chain
        self.blocks.append(block)
        return block

    def validate(self) -> None:
        """Check the whole chain still links up and every block was sealed by an authorized node; raise ChainError otherwise"""
        genesis = self.blocks[0]
        if genesis.index != 0 or genesis.prev_hash != GENESIS_PREV_HASH:
            raise ChainError("block 0: invalid genesis")

        for i, block in enumerate(self.blocks):
            if block.stored_hash is not None and block.stored_hash != block.compute_hash():
                raise ChainError(f"block {i}: content was modified (computed hash does not match the stored one)")

            # genesis is hard-coded and never went through sealing, so consensus rules do not apply
            if i == 0:
                continue

            prev = self.blocks[i - 1]
            if block.index != prev.index + 1:
                raise ChainError(f"block {i}: index is not consecutive")
            if block.prev_hash != prev.compute_hash():
                raise ChainError(f"block {i}: prev_hash does not match block {i - 1} (the chain breaks here)")
            if block.timestamp < prev.timestamp:
                raise ChainError(f"block {i}: timestamp goes backwards")
            self.consensus.verify(block)

    def is_valid(self) -> bool:
        try:
            self.validate()
        except ChainError:
            return False
        return True

    def transactions(self, tx_type: str | None = None) -> Iterator[dict[str, Any]]:
        """Walk every transaction in the chain in recorded order (optionally filtered by type)"""
        for block in self.blocks:
            for tx in block.transactions:
                if tx_type is None or tx.get("type") == tx_type:
                    yield tx

    def to_dict(self) -> dict[str, Any]:
        return {
            "consensus": self.consensus.to_dict(),
            "blocks": [b.to_dict() for b in self.blocks],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Blockchain:
        from consensus import consensus_from_dict

        chain = cls(consensus=consensus_from_dict(data.get("consensus")))
        chain.blocks = [Block.from_dict(b) for b in data["blocks"]]
        return chain

    def save(self, path: str | Path) -> None:
        Path(path).write_text(canonical_json(self.to_dict()) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> Blockchain:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def __len__(self) -> int:
        return len(self.blocks)

    def __iter__(self) -> Iterator[Block]:
        return iter(self.blocks)
