"""ชั้นงานของ ledger: บันทึกบัญชีรอบ swarm learning ลงบล็อกเชน

หลักการเดียวกับ chaincode sl-ledger (Go) ที่ทำไว้ก่อนหน้า:
น้ำหนักโมเดลตัวจริงอยู่นอกเชนเพราะใหญ่เกินกว่าจะเก็บในบล็อก
บนเชนเก็บแค่ hash + บัญชีรอบ ให้ตรวจย้อนหลังได้ว่า "รอบไหน ใครส่งอะไร ใครรวม"

ข้อตกลงของ PoC นี้: 1 รอบ swarm = 1 บล็อก
บล็อกหนึ่งจึงมี model_update ของทุกโหนดในรอบนั้น + aggregation ของ leader รอบนั้น

กฎที่บังคับในนี้คือส่วนที่ตรงกับ smart contract:
  - ผู้ส่งต้องเป็นสมาชิกที่ประกาศไว้         (คล้าย MSP membership)
  - หนึ่งโหนดส่งได้รอบละครั้ง                 (กันส่งซ้ำถ่วงน้ำหนักตัวเอง)
  - ผู้รวมพารามิเตอร์ต้องเป็น leader ของรอบนั้นจริง (คล้ายเช็ค AggregatorMSP)
  - รอบที่ปิดแล้วเปิดใหม่ไม่ได้
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Iterable, Sequence

import numpy as np

from blockchain import Block, Blockchain, canonical_json

TX_MODEL_UPDATE = "model_update"
TX_AGGREGATION = "aggregation"


class LedgerError(Exception):
    """ธุรกรรมขัดกฎของ ledger — เทียบได้กับ chaincode ที่ปฏิเสธ transaction"""


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


def elect_leader(round_num: int, participants: Sequence[str]) -> str:
    """เลือก leader ของรอบจาก sha256(เลขรอบ + รายชื่อผู้เข้าร่วม)

    ทุกโหนดคำนวณเองได้ ผลตรงกัน และตรวจย้อนหลังได้ว่ารอบนั้นใครมีสิทธิ์รวมพารามิเตอร์
    (ต้องเป็นสูตรเดียวกับที่ notebook ใช้ ไม่งั้นเชนจะปฏิเสธ aggregation ของ notebook)
    """
    digest = hashlib.sha256(f"round-{round_num}:{','.join(participants)}".encode("utf-8")).hexdigest()
    return participants[int(digest, 16) % len(participants)]


class SwarmLedger:
    """API ที่โหนดเรียกใช้ — ชื่อฟังก์ชันตรงกับ chaincode sl-ledger เดิม

    submit_update() เก็บเข้า pending ก่อน แล้ว record_aggregation() ค่อยปิดเป็นบล็อกของรอบนั้น
    (เทียบกับ Fabric: pending คือ transaction ที่ถูก endorse แล้วรอ orderer ตัดบล็อก)
    """

    def __init__(self, participants: Iterable[str], difficulty: int = 0,
                 chain: Blockchain | None = None) -> None:
        self.participants = list(participants)
        if not self.participants:
            raise ValueError("ต้องมีผู้เข้าร่วมอย่างน้อย 1 โหนด")
        self.chain = chain if chain is not None else Blockchain(difficulty=difficulty)
        self._pending: list[dict[str, Any]] = []

    # ---------- เขียน ----------

    def submit_update(self, round_num: int, node_id: str, coef: np.ndarray,
                      intercept: np.ndarray, n_samples: int) -> str:
        """โหนดหนึ่งประกาศผลเทรนในเครื่องของรอบนั้น (ส่งแค่ hash ไม่ส่งน้ำหนัก)"""
        if node_id not in self.participants:
            raise LedgerError(f"node {node_id} ไม่ได้เป็นสมาชิกของ swarm นี้")
        if round_num in self.committed_rounds():
            raise LedgerError(f"รอบ {round_num} ปิดบล็อกไปแล้ว ส่ง update เพิ่มไม่ได้")
        for tx in self._pending:
            if tx["round"] == round_num and tx["node_id"] == node_id:
                raise LedgerError(f"node {node_id} ส่ง update ของรอบ {round_num} ไปแล้ว")

        weight_hash = hash_params(coef, intercept)
        self._pending.append({
            "type": TX_MODEL_UPDATE,
            "round": round_num,
            "node_id": node_id,
            "weight_hash": weight_hash,
            "size_bytes": params_size_bytes(coef, intercept),
            "n_samples": int(n_samples),
            "timestamp": time.time(),
        })
        return weight_hash

    def record_aggregation(self, round_num: int, leader: str, coef: np.ndarray,
                           intercept: np.ndarray, accuracy: float | None = None) -> Block:
        """leader ของรอบนั้นบันทึก hash ของโมเดลกลาง แล้วปิดบล็อกของรอบ"""
        expected = elect_leader(round_num, self.participants)
        if leader != expected:
            raise LedgerError(
                f"รอบ {round_num} leader ต้องเป็น {expected} ไม่ใช่ {leader} — ปฏิเสธ aggregation"
            )
        if round_num in self.committed_rounds():
            raise LedgerError(f"รอบ {round_num} มี aggregation อยู่แล้ว")

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
        block = self.chain.add_block(updates + [aggregation])
        self._pending = [tx for tx in self._pending if tx["round"] != round_num]
        return block

    # ---------- อ่าน ----------

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
        """หน้าที่ leader กระจายไปกี่รอบต่อโหนด — ดูจากที่บันทึกบนเชน ไม่ใช่จากตัวแปรในหน่วยความจำ"""
        counts = {name: 0 for name in self.participants}
        for tx in self.chain.transactions(TX_AGGREGATION):
            counts[tx["aggregator"]] = counts.get(tx["aggregator"], 0) + 1
        return counts

    def ledger_bytes(self) -> int:
        """ขนาดเชนถ้าเซฟเป็น JSON — ใช้ดูอัตราการโตของ ledger ต่อรอบ"""
        return len(canonical_json(self.chain.to_dict()).encode("utf-8"))
