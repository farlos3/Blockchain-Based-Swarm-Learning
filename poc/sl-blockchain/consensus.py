"""กลไกฉันทามติ: ใครมีสิทธิ์ปิดบล็อก และคนอื่นตรวจสิทธิ์นั้นย้อนหลังได้อย่างไร

มีให้ 2 แบบเพื่อเทียบกันในเล่ม
  ProofOfAuthority (ค่าเริ่มต้น) — เหมาะกับ consortium ที่สมาชิกรู้ตัวตนกันอยู่แล้ว
  ProofOfWork                    — ไว้สาธิตข้อเปรียบเทียบว่าทำไมไม่เลือกทางนี้

PoA ที่นี่ประกอบด้วย 3 ส่วนตามนิยาม
  1. authority set  รายชื่อผู้มีสิทธิ์ + public key ประกาศไว้บนเชน
  2. leader rule    รอบไหนใครมีคิวปิดบล็อก คำนวณได้เองจากเลขรอบ (ไม่ต้องมีใครแต่งตั้ง)
  3. block seal     leader เซ็น hash ของบล็อกด้วย private key ของตัวเอง
                    ใครถือไฟล์เชน + public key ก็ตรวจได้ ไม่ต้องเชื่อใคร
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

TX_AGGREGATION = "aggregation"  # PoC นี้ปิดบล็อกละหนึ่งรอบ เลขรอบอยู่ในธุรกรรมชนิดนี้


# ---------- กุญแจของโหนด ----------


class NodeKey:
    """คู่กุญแจของโหนดหนึ่ง — ของจริงต้องอยู่ในเครื่องโหนดนั้นเท่านั้น ห้ามออกจากเครื่อง"""

    def __init__(self, node_id: str, private_key: Ed25519PrivateKey) -> None:
        self.node_id = node_id
        self._private_key = private_key

    @classmethod
    def generate(cls, node_id: str, seed: str | None = None) -> NodeKey:
        """seed ใส่ไว้เพื่อให้ demo/เทสต์ได้กุญแจเดิมทุกครั้ง — ของจริงต้องสุ่มล้วน"""
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
    """รายชื่อผู้มีสิทธิ์ + public key — ลำดับสมาชิกมีผลต่อการเลือก leader จึงต้องคงลำดับไว้"""

    def __init__(self, public_keys: dict[str, str]) -> None:
        if not public_keys:
            raise ValueError("authority set ว่างไม่ได้")
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


# ---------- กฎการเลือก leader ----------


def elect_leader(round_num: int, participants: Sequence[str]) -> str:
    """leader ของรอบ = sha256(เลขรอบ + รายชื่อผู้เข้าร่วม) mod จำนวนผู้เข้าร่วม

    เป็นสูตรเดียวกับที่ ini_swarm.ipynb ใช้ ทุกโหนดคำนวณเองได้ ผลตรงกัน
    และย้อนกลับไปตรวจได้ว่ารอบนั้นใครมีคิว โดยไม่ต้องเชื่อบันทึกของใคร
    """
    digest = hashlib.sha256(f"round-{round_num}:{','.join(participants)}".encode("utf-8")).hexdigest()
    return participants[int(digest, 16) % len(participants)]


def block_round(block: Block) -> int | None:
    """หาเลขรอบของบล็อกจากธุรกรรม aggregation (None = บล็อกนี้ไม่ได้ปิดรอบ swarm)"""
    for tx in block.transactions:
        if tx.get("type") == TX_AGGREGATION:
            return tx.get("round")
    return None


# ---------- กลไก ----------


class Consensus(Protocol):
    name: str

    def seal(self, block: Block, sealer: NodeKey | None = None) -> Block: ...
    def verify(self, block: Block) -> None: ...
    def to_dict(self) -> dict[str, Any]: ...


@dataclass
class ProofOfWork:
    """ต้องไล่หา nonce ให้ hash ขึ้นต้นด้วย 0 ตามจำนวน difficulty

    ไม่ใช่ทางที่เลือกใช้ มีไว้เทียบให้เห็นว่าใน consortium ที่รู้ตัวตนกันแล้ว
    การเผา CPU แข่งกันไม่ได้เพิ่มความปลอดภัย แค่เพิ่มเวลาและค่าไฟ
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
            raise ChainError(f"block {block.index}: hash ไม่ผ่าน difficulty {self.difficulty}")

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "difficulty": self.difficulty}


class ProofOfAuthority:
    """บล็อกจะถูกยอมรับก็ต่อเมื่อ leader ของรอบนั้นเป็นคนเซ็นปิดเอง

    ตรวจ 3 ชั้นตอน verify
      1. ผู้ปิดบล็อกอยู่ใน authority set ไหม
      2. ผู้ปิดบล็อกเป็น leader ของรอบนั้นตามกฎไหม (ถึงจะเป็นสมาชิกก็ปิดนอกคิวไม่ได้)
      3. ลายเซ็นบน hash ของบล็อกถูกต้องตาม public key ที่ประกาศไว้ไหม
    """

    name = "poa"

    def __init__(self, authorities: AuthoritySet, enforce_leader: bool = True) -> None:
        self.authorities = authorities
        self.enforce_leader = enforce_leader

    def seal(self, block: Block, sealer: NodeKey | None = None) -> Block:
        from dataclasses import replace

        if sealer is None:
            raise ChainError("PoA ต้องระบุผู้ปิดบล็อก (ไม่มีใครปิดบล็อกแบบไม่ระบุตัวตนได้)")
        if sealer.node_id not in self.authorities:
            raise ChainError(f"{sealer.node_id} ไม่ได้อยู่ใน authority set")

        block = replace(block, sealer=sealer.node_id)
        return replace(block, seal=sealer.sign(block.compute_hash()))

    def verify(self, block: Block) -> None:
        if not block.sealer or not block.seal:
            raise ChainError(f"block {block.index}: ไม่มีลายเซ็นผู้ปิดบล็อก")
        if block.sealer not in self.authorities:
            raise ChainError(f"block {block.index}: ผู้ปิดบล็อก {block.sealer} ไม่ได้อยู่ใน authority set")

        if self.enforce_leader:
            round_num = block_round(block)
            if round_num is not None:
                expected = elect_leader(round_num, self.authorities.members)
                if block.sealer != expected:
                    raise ChainError(
                        f"block {block.index}: รอบ {round_num} เป็นคิวของ {expected} "
                        f"แต่ {block.sealer} เป็นคนปิดบล็อก"
                    )

        if not self.authorities.verify(block.sealer, block.compute_hash(), block.seal):
            raise ChainError(f"block {block.index}: ลายเซ็นของ {block.sealer} ไม่ถูกต้อง")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "authorities": self.authorities.to_dict(),
            "leader_rule": "sha256(round + members)",
            "enforce_leader": self.enforce_leader,
        }


def consensus_from_dict(data: dict[str, Any] | None) -> Consensus:
    """สร้างกลไกกลับจากไฟล์เชน เพื่อให้คนที่ถือแค่ chain.json ตรวจสอบเองได้ครบ"""
    if not data or data.get("name") == "pow":
        return ProofOfWork(difficulty=(data or {}).get("difficulty", 0))
    if data["name"] == "poa":
        return ProofOfAuthority(
            AuthoritySet(data["authorities"]),
            enforce_leader=data.get("enforce_leader", True),
        )
    raise ValueError(f"ไม่รู้จักกลไก {data['name']!r}")


def sign_payload(key: NodeKey, payload: dict[str, Any]) -> str:
    """เซ็นธุรกรรม — เซ็นบน canonical form เพื่อให้ผู้ตรวจสร้างข้อความเดิมได้แน่นอน"""
    return key.sign(canonical_json(payload))


def verify_payload(authorities: AuthoritySet, node_id: str, payload: dict[str, Any],
                   signature_hex: str) -> bool:
    return authorities.verify(node_id, canonical_json(payload), signature_hex)
