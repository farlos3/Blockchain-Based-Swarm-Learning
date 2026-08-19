"""ชั้นงานของ ledger: บันทึกบัญชีรอบ swarm learning ลงบล็อกเชนแบบ Proof of Authority

หลักการเดียวกับ chaincode sl-ledger (Go) ที่ทำไว้ก่อนหน้า:
น้ำหนักโมเดลตัวจริงอยู่นอกเชนเพราะใหญ่เกินกว่าจะเก็บในบล็อก
บนเชนเก็บแค่ hash + บัญชีรอบ ให้ตรวจย้อนหลังได้ว่า "รอบไหน ใครส่งอะไร ใครรวม"

ข้อตกลงของ PoC นี้: 1 รอบ swarm = 1 บล็อก
บล็อกหนึ่งจึงมี model_update ของทุกโหนดในรอบนั้น + aggregation ของ leader รอบนั้น

ทุกธุรกรรมต้องมีลายเซ็นของผู้ส่ง และบล็อกต้องถูกปิดโดย leader ของรอบนั้นเท่านั้น
กฎที่บังคับในนี้คือส่วนที่ตรงกับ smart contract:
  - ผู้ส่งต้องอยู่ใน authority set และลายเซ็นต้องตรงกับ public key ที่ประกาศไว้
  - หนึ่งโหนดส่งได้รอบละครั้ง
  - ผู้ปิดบล็อกต้องเป็น leader ของรอบนั้นจริง (คล้ายเช็ค AggregatorMSP)
  - รอบที่ปิดแล้วเปิดใหม่ไม่ได้
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
    """ธุรกรรมขัดกฎของ ledger — เทียบได้กับ chaincode ที่ reject transaction"""


def hash_params(coef: np.ndarray, intercept: np.ndarray) -> str:
    """fingerprint ของพารามิเตอร์โมเดล — ค่าเท่ากันได้ hash เท่ากัน ต่างแม้แต่บิตเดียวก็เปลี่ยน

    ใส่ชื่อและ shape ลงไปด้วย เพื่อไม่ให้ coef/intercept ที่สลับกันมาได้ hash เดียวกัน
    """
    digest = hashlib.sha256()
    for name, array in (("coef", coef), ("intercept", intercept)):
        values = np.ascontiguousarray(array, dtype=np.float64)
        digest.update(name.encode("utf-8"))
        digest.update(canonical_json(list(values.shape)).encode("utf-8"))
        digest.update(values.tobytes())
    return digest.hexdigest()


def params_size_bytes(coef: np.ndarray, intercept: np.ndarray) -> int:
    """ขนาดพารามิเตอร์ที่ต้องส่งจริงต่อรอบ (ใช้ประเมิน bandwidth / ledger growth)"""
    return int(np.asarray(coef).nbytes + np.asarray(intercept).nbytes)


def unsigned_view(tx: dict[str, Any]) -> dict[str, Any]:
    """ส่วนของธุรกรรมที่ถูกเซ็น — ทุกฟิลด์ยกเว้นตัวลายเซ็นเอง"""
    return {k: v for k, v in tx.items() if k != "signature"}


class SwarmLedger:
    """API ที่โหนดเรียกใช้ — ชื่อเมธอดตรงกับ chaincode sl-ledger เดิม

    submit_update() เก็บเข้า pending ก่อน แล้ว record_aggregation() ค่อยปิดเป็นบล็อกของรอบนั้น
    (เทียบกับ Fabric: pending คือ transaction ที่ถูก endorse แล้วรอ orderer ตัดบล็อก)
    """

    def __init__(self, keys: Sequence[NodeKey], chain: Blockchain | None = None) -> None:
        if not keys:
            raise ValueError("ต้องมีผู้เข้าร่วมอย่างน้อย 1 โหนด")
        self.keys = {k.node_id: k for k in keys}
        self.authorities = AuthoritySet.from_keys(list(keys))
        self.chain = chain if chain is not None else Blockchain(
            consensus=ProofOfAuthority(self.authorities)
        )
        self._pending: list[dict[str, Any]] = []

    @classmethod
    def bootstrap(cls, participants: Sequence[str], seed: str | None = None) -> SwarmLedger:
        """สร้าง swarm พร้อมกุญแจของทุกโหนดในครั้งเดียว

        ทำได้เพราะ PoC นี้รันในโปรเซสเดียว ของจริงแต่ละโหนดต้องสร้างกุญแจเองในเครื่องตัวเอง
        แล้วส่งมาเฉพาะ public key เพื่อลงทะเบียนเข้า authority set
        """
        return cls([NodeKey.generate(name, seed=seed) for name in participants])

    @property
    def participants(self) -> list[str]:
        return self.authorities.members

    # ---------- เขียน ----------

    def submit_update(self, round_num: int, node_id: str, coef: np.ndarray,
                      intercept: np.ndarray, n_samples: int,
                      key: NodeKey | None = None) -> dict[str, Any]:
        """โหนดหนึ่งประกาศผลเทรนในเครื่องของรอบนั้น (ส่งแค่ hash ไม่ส่งน้ำหนัก) พร้อมเซ็นกำกับ"""
        signing_key = key or self.keys.get(node_id)
        if signing_key is None:
            raise LedgerError(f"ไม่มีกุญแจของ node {node_id} จึงเซ็นธุรกรรมแทนไม่ได้")

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
        """รับธุรกรรมที่เซ็นมาแล้ว (เส้นทางเดียวกับที่จะมาจากเครือข่ายจริง) — ตรวจก่อนรับเสมอ"""
        node_id = tx.get("node_id")
        round_num = tx.get("round")

        if node_id not in self.authorities:
            raise LedgerError(f"node {node_id} ไม่ได้อยู่ใน authority set ของ swarm นี้")
        if not verify_payload(self.authorities, node_id, unsigned_view(tx), tx.get("signature", "")):
            raise LedgerError(f"ลายเซ็นของ node {node_id} ไม่ถูกต้อง — ปฏิเสธธุรกรรม")
        if round_num in self.committed_rounds():
            raise LedgerError(f"รอบ {round_num} ปิดบล็อกไปแล้ว ส่ง update เพิ่มไม่ได้")
        for pending in self._pending:
            if pending["round"] == round_num and pending["node_id"] == node_id:
                raise LedgerError(f"node {node_id} ส่ง update ของรอบ {round_num} ไปแล้ว")

        self._pending.append(tx)
        return tx

    def record_aggregation(self, round_num: int, leader: str, coef: np.ndarray,
                           intercept: np.ndarray, accuracy: float | None = None,
                           key: NodeKey | None = None) -> Block:
        """leader ของรอบนั้นบันทึก hash ของโมเดลกลาง เซ็นปิดบล็อก แล้วบล็อกจึงเข้าสาย"""
        expected = elect_leader(round_num, self.participants)
        if leader != expected:
            raise LedgerError(
                f"รอบ {round_num} leader ต้องเป็น {expected} ไม่ใช่ {leader} — ปฏิเสธ aggregation"
            )
        if round_num in self.committed_rounds():
            raise LedgerError(f"รอบ {round_num} มี aggregation อยู่แล้ว")

        signing_key = key or self.keys.get(leader)
        if signing_key is None:
            raise LedgerError(f"ไม่มีกุญแจของ leader {leader} จึงปิดบล็อกแทนไม่ได้")

        updates = [tx for tx in self._pending if tx["round"] == round_num]
        if not updates:
            raise LedgerError(f"รอบ {round_num} ยังไม่มี update ให้รวม")

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

    # ---------- อ่าน / ตรวจ ----------

    def committed_rounds(self) -> list[int]:
        return [tx["round"] for tx in self.chain.transactions(TX_AGGREGATION)]

    def get_round_updates(self, round_num: int) -> list[dict[str, Any]]:
        return [tx for tx in self.chain.transactions(TX_MODEL_UPDATE) if tx["round"] == round_num]

    def get_aggregation(self, round_num: int) -> dict[str, Any]:
        for tx in self.chain.transactions(TX_AGGREGATION):
            if tx["round"] == round_num:
                return tx
        raise LedgerError(f"ไม่พบ aggregation ของรอบ {round_num}")

    def verify_round(self, round_num: int, coef: np.ndarray, intercept: np.ndarray) -> bool:
        """โหนดใช้ตรวจว่าโมเดลกลางที่ตัวเองถืออยู่ ตรงกับที่บันทึกไว้บนเชนของรอบนั้นจริง"""
        return hash_params(coef, intercept) == self.get_aggregation(round_num)["aggregated_hash"]

    def leader_counts(self) -> dict[str, int]:
        """หน้าที่ leader กระจายไปกี่รอบต่อโหนด — อ่านจากเชน ไม่ใช่จากตัวแปรในหน่วยความจำ"""
        counts = {name: 0 for name in self.participants}
        for tx in self.chain.transactions(TX_AGGREGATION):
            counts[tx["aggregator"]] = counts.get(tx["aggregator"], 0) + 1
        return counts

    def ledger_bytes(self) -> int:
        """ขนาดเชนถ้าเซฟเป็น JSON — ใช้ดูอัตราการโตของ ledger ต่อรอบ"""
        return len(canonical_json(self.chain.to_dict()).encode("utf-8"))

    def audit(self) -> dict[str, Any]:
        return audit_chain(self.chain)


def audit_chain(source: Blockchain | str | Path) -> dict[str, Any]:
    """ตรวจเชนทั้งสายโดยไม่ต้องเชื่อใคร — ใช้ได้จากไฟล์ chain.json ล้วน ๆ

    ตรวจ 3 ชั้น: โครงสร้างสาย + ลายเซ็นผู้ปิดบล็อกว่าเป็น leader ตามคิว + ลายเซ็นของทุกธุรกรรม
    (authority public key ถูกเก็บอยู่ในไฟล์เชน คนนอกจึงตรวจเองได้ครบ)
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
                raise LedgerError(f"ธุรกรรมไม่มีลายเซ็น: {tx.get('type')} รอบ {tx.get('round')}")
            if not verify_payload(authorities, signer, unsigned_view(tx), signature):
                raise LedgerError(
                    f"ลายเซ็นธุรกรรมไม่ถูกต้อง: {tx.get('type')} รอบ {tx.get('round')} โดย {signer}"
                )
            checked += 1

    return {
        "consensus": consensus.to_dict().get("name"),
        "blocks": chain.height,
        "transactions_verified": checked,
        "authorities": authorities.members if authorities else [],
    }
