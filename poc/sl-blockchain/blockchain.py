"""บล็อกเชนขนาดเล็กแบบ append-only สำหรับ PoC swarm learning

ตั้งใจให้อ่านจบได้ในไฟล์เดียว ไม่มี dependency นอกจาก standard library
แนวคิดเดียวที่ทำให้มันเป็นบล็อกเชน: แต่ละบล็อกเก็บ sha256 ของบล็อกก่อนหน้า
ดังนั้นถ้าใครแก้ของเก่าย้อนหลัง hash จะไม่ตรงกับที่บล็อกถัดไปอ้างอิงไว้
และ validate() จะจับได้ว่าพังที่บล็อกไหน
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterator

GENESIS_PREV_HASH = "0" * 64


def canonical_json(value: Any) -> str:
    """serialize ให้ได้ผลเดิมทุกครั้ง (เรียงคีย์ ไม่มีช่องว่างเกิน)

    ถ้าลำดับคีย์เปลี่ยนได้ hash ก็เปลี่ยนตาม ทั้งที่เนื้อหาเท่าเดิม
    การตรวจสอบข้ามเครื่องจะพังทันที จึงต้องล็อกรูปแบบไว้ตรงนี้ที่เดียว
    """
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Block:
    """หนึ่งบล็อก = ธุรกรรมของหนึ่งรอบ swarm + ตัวผูกไปยังบล็อกก่อนหน้า"""

    index: int
    timestamp: float
    prev_hash: str
    transactions: tuple[dict[str, Any], ...]
    nonce: int = 0
    stored_hash: str | None = None  # hash ที่อ่านมาจากไฟล์ ใช้เทียบจับการแก้ไข

    def tx_root(self) -> str:
        """สรุปธุรกรรมทั้งบล็อกเป็นค่าเดียว (Merkle root แบบง่าย คือ hash รวมทีเดียว)"""
        return sha256_hex(canonical_json(list(self.transactions)))

    def header(self) -> dict[str, Any]:
        """ส่วนที่ถูก hash — ไม่รวมตัว hash ของบล็อกเอง"""
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "prev_hash": self.prev_hash,
            "tx_root": self.tx_root(),
            "nonce": self.nonce,
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
            stored_hash=data.get("hash"),
        )


class ChainError(Exception):
    """สายบล็อกไม่สอดคล้องกัน — ระบุไว้ว่าพังที่บล็อกไหนและเพราะอะไร"""


class Blockchain:
    """สายบล็อกในหน่วยความจำ + เซฟ/โหลดเป็น JSON ได้

    difficulty > 0 จะเปิด proof-of-work (ต้องหา nonce ให้ hash ขึ้นต้นด้วย 0 ตามจำนวนนั้น)
    ค่าเริ่มต้นคือ 0 เพราะ swarm ของเราเป็นระบบแบบมีสมาชิกที่รู้ตัวตน (permissioned)
    การแข่งขันขุดไม่ได้ให้อะไรเพิ่ม — เปิดไว้เป็นตัวเลือกเพื่อสาธิตกลไกเท่านั้น
    """

    def __init__(self, difficulty: int = 0) -> None:
        if difficulty < 0:
            raise ValueError("difficulty ต้องไม่ติดลบ")
        self.difficulty = difficulty
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

    def add_block(self, transactions: list[dict[str, Any]]) -> Block:
        if not transactions:
            raise ValueError("บล็อกว่างไม่มีประโยชน์ ต้องมีธุรกรรมอย่างน้อย 1 รายการ")

        block = Block(
            index=self.last_block.index + 1,
            timestamp=time.time(),
            prev_hash=self.last_block.compute_hash(),
            transactions=tuple(transactions),
        )
        block = self._mine(block)
        self.blocks.append(block)
        return block

    def _mine(self, block: Block) -> Block:
        """หา nonce ให้ hash ผ่านเงื่อนไข difficulty (difficulty=0 คือคืนค่าเดิมทันที)"""
        target = "0" * self.difficulty
        while not block.compute_hash().startswith(target):
            block = replace(block, nonce=block.nonce + 1)
        return block

    def validate(self) -> None:
        """ตรวจทั้งสายว่ายังต่อกันถูกต้อง ถ้าไม่ผ่านให้ ChainError พร้อมเหตุผล"""
        genesis = self.blocks[0]
        if genesis.index != 0 or genesis.prev_hash != GENESIS_PREV_HASH:
            raise ChainError("block 0: genesis ไม่ถูกต้อง")

        target = "0" * self.difficulty
        for i, block in enumerate(self.blocks):
            if block.stored_hash is not None and block.stored_hash != block.compute_hash():
                raise ChainError(f"block {i}: เนื้อหาถูกแก้ (hash ที่คำนวณได้ไม่ตรงกับที่บันทึกไว้)")
            # genesis ถูกกำหนดค่าไว้ตายตัว ไม่ได้ผ่านการขุด จึงไม่ต้องเข้าเงื่อนไข difficulty
            if i == 0:
                continue
            if self.difficulty and not block.compute_hash().startswith(target):
                raise ChainError(f"block {i}: hash ไม่ผ่าน difficulty {self.difficulty}")

            prev = self.blocks[i - 1]
            if block.index != prev.index + 1:
                raise ChainError(f"block {i}: ลำดับ index ไม่ต่อเนื่อง")
            if block.prev_hash != prev.compute_hash():
                raise ChainError(f"block {i}: prev_hash ไม่ตรงกับบล็อก {i - 1} (สายขาดตรงนี้)")
            if block.timestamp < prev.timestamp:
                raise ChainError(f"block {i}: timestamp ย้อนเวลา")

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
        return {"difficulty": self.difficulty, "blocks": [b.to_dict() for b in self.blocks]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Blockchain:
        chain = cls(difficulty=data.get("difficulty", 0))
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
