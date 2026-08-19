"""บล็อกเชนขนาดเล็กแบบ append-only สำหรับ PoC swarm learning

ตั้งใจให้อ่านจบได้ในไฟล์เดียว แนวคิดเดียวที่ทำให้มันเป็นบล็อกเชนคือ
แต่ละบล็อกเก็บ sha256 ของบล็อกก่อนหน้า ถ้าใครแก้ของเก่าย้อนหลัง
hash จะไม่ตรงกับที่บล็อกถัดไปอ้างไว้ validate() จะบอกได้ว่าพังที่บล็อกไหน

ส่วน "ใครมีสิทธิ์ปิดบล็อก" แยกไปอยู่ใน consensus.py (ค่าเริ่มต้นของโปรเจกต์นี้คือ PoA)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator

if TYPE_CHECKING:  # นำเข้าแบบนี้เพื่อเลี่ยง import วน (consensus.py ใช้ของจากไฟล์นี้)
    from consensus import Consensus, NodeKey

GENESIS_PREV_HASH = "0" * 64


def canonical_json(value: Any) -> str:
    """serialize ให้ได้ผลเดิมทุกครั้ง (เรียงคีย์ ไม่มีช่องว่างเกิน)

    ถ้าลำดับคีย์เปลี่ยนได้ hash ก็เปลี่ยนตามทั้งที่เนื้อหาเท่าเดิม
    การตรวจสอบข้ามเครื่องจะพังทันที จึงล็อกรูปแบบไว้ที่เดียวตรงนี้
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(data: str) -> str:
    return sha256(data.encode("utf-8")).hexdigest()


class ChainError(Exception):
    """สายบล็อกไม่สอดคล้องกัน — ข้อความจะระบุว่าพังที่บล็อกไหนและเพราะอะไร"""


@dataclass(frozen=True)
class Block:
    """หนึ่งบล็อก = ธุรกรรมของหนึ่งรอบ swarm + ตัวผูกไปยังบล็อกก่อนหน้า + ลายเซ็นผู้ปิดบล็อก"""

    index: int
    timestamp: float
    prev_hash: str
    transactions: tuple[dict[str, Any], ...]
    nonce: int = 0
    sealer: str | None = None        # โหนดที่ปิดบล็อกนี้ (PoA)
    seal: str | None = None          # ลายเซ็นของ sealer บน hash ของบล็อก
    stored_hash: str | None = None   # hash ที่อ่านมาจากไฟล์ ใช้เทียบจับการแก้ไข

    def tx_root(self) -> str:
        """สรุปธุรกรรมทั้งบล็อกเป็นค่าเดียว (Merkle root แบบง่าย คือ hash รวมทีเดียว)"""
        return sha256_hex(canonical_json(list(self.transactions)))

    def header(self) -> dict[str, Any]:
        """ส่วนที่ถูก hash — ไม่รวม hash ของบล็อกเอง และไม่รวมลายเซ็นที่เซ็นทับ hash นั้น"""
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
    """สายบล็อกในหน่วยความจำ + เซฟ/โหลดเป็น JSON ได้

    consensus กำหนดว่าใครปิดบล็อกได้และตรวจย้อนหลังอย่างไร
    ไม่ระบุ = ProofOfWork(difficulty) ซึ่ง difficulty=0 หมายถึงไม่มีเงื่อนไขอะไรเลย
    """

    def __init__(self, consensus: Consensus | None = None, difficulty: int = 0) -> None:
        if consensus is None:
            from consensus import ProofOfWork

            consensus = ProofOfWork(difficulty=difficulty)
        self.consensus = consensus
        self.blocks: list[Block] = [self._genesis()]

    @staticmethod
    def _genesis() -> Block:
        # timestamp คงที่ เพื่อให้สร้างเชนใหม่กี่ครั้งก็ได้ genesis hash เดิม (ทดสอบซ้ำได้)
        return Block(index=0, timestamp=0.0, prev_hash=GENESIS_PREV_HASH, transactions=())

    @property
    def last_block(self) -> Block:
        return self.blocks[-1]

    @property
    def height(self) -> int:
        """จำนวนบล็อกที่มีข้อมูล (ไม่นับ genesis)"""
        return len(self.blocks) - 1

    def add_block(self, transactions: list[dict[str, Any]], sealer: NodeKey | None = None) -> Block:
        if not transactions:
            raise ValueError("บล็อกว่างไม่มีประโยชน์ ต้องมีธุรกรรมอย่างน้อย 1 รายการ")

        block = Block(
            index=self.last_block.index + 1,
            timestamp=time.time(),
            prev_hash=self.last_block.compute_hash(),
            transactions=tuple(transactions),
        )
        block = self.consensus.seal(block, sealer)
        self.consensus.verify(block)  # ปิดบล็อกแล้วต้องผ่านกฎของตัวเองก่อนถึงต่อเข้าสาย
        self.blocks.append(block)
        return block

    def validate(self) -> None:
        """ตรวจทั้งสายว่ายังต่อกันถูกต้องและทุกบล็อกถูกปิดโดยผู้มีสิทธิ์ ถ้าไม่ผ่านให้ ChainError"""
        genesis = self.blocks[0]
        if genesis.index != 0 or genesis.prev_hash != GENESIS_PREV_HASH:
            raise ChainError("block 0: genesis ไม่ถูกต้อง")

        for i, block in enumerate(self.blocks):
            if block.stored_hash is not None and block.stored_hash != block.compute_hash():
                raise ChainError(f"block {i}: เนื้อหาถูกแก้ (hash ที่คำนวณได้ไม่ตรงกับที่บันทึกไว้)")

            # genesis ถูกกำหนดค่าไว้ตายตัว ไม่ได้ผ่านการปิดบล็อก จึงไม่ต้องเข้ากฎ consensus
            if i == 0:
                continue

            prev = self.blocks[i - 1]
            if block.index != prev.index + 1:
                raise ChainError(f"block {i}: ลำดับ index ไม่ต่อเนื่อง")
            if block.prev_hash != prev.compute_hash():
                raise ChainError(f"block {i}: prev_hash ไม่ตรงกับบล็อก {i - 1} (สายขาดตรงนี้)")
            if block.timestamp < prev.timestamp:
                raise ChainError(f"block {i}: timestamp ย้อนเวลา")
            self.consensus.verify(block)

    def is_valid(self) -> bool:
        try:
            self.validate()
        except ChainError:
            return False
        return True

    def transactions(self, tx_type: str | None = None) -> Iterator[dict[str, Any]]:
        """ไล่ธุรกรรมทั้งเชนตามลำดับที่ถูกบันทึก (กรองตามชนิดได้)"""
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
