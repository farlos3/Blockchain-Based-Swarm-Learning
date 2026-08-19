"""สาธิต ledger แบบ Proof of Authority: 5 โหนด 3 รอบ

  python demo.py

พารามิเตอร์ในนี้เป็นตัวเลขสุ่ม ไม่ได้เทรนจริง เพราะจุดประสงค์คือดูกลไกของเชน
การต่อกับโมเดลจริงดูใน README หัวข้อ "ต่อกับ notebook"
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from blockchain import Block, Blockchain, ChainError
from consensus import NodeKey, elect_leader, sign_payload
from swarm_ledger import SwarmLedger, audit_chain, unsigned_view

NODES = ["A", "B", "C", "D", "E"]
N_SAMPLES = {"A": 240, "B": 160, "C": 110, "D": 60, "E": 110}
ROUNDS = 3
CHAIN_FILE = Path(__file__).with_name("chain.json")


def rule(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def fake_params(rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """แทนพารามิเตอร์จากการเทรนจริง (coef 1x10 + intercept 1 ตัว เท่ากับ SGDClassifier)"""
    return rng.normal(0, 1, size=(1, 10)), rng.normal(0, 1, size=(1,))


def main() -> None:
    rng = np.random.default_rng(7)
    ledger = SwarmLedger.bootstrap(NODES, seed="demo")

    rule(f"authority set — {len(NODES)} โหนด, consensus = {ledger.chain.consensus.name}")
    for node, public_key in ledger.authorities.to_dict().items():
        print(f"  Node {node}  public key = {public_key[:32]}…")
    print("\n  private key อยู่กับโหนดเจ้าของเท่านั้น เชนเก็บแค่ public key ไว้ให้คนอื่นตรวจ")

    global_params: dict[int, tuple[np.ndarray, np.ndarray]] = {}

    for round_num in range(1, ROUNDS + 1):
        leader = elect_leader(round_num, NODES)
        rule(f"รอบ {round_num} — leader = Node {leader}")

        updates = []
        for node in NODES:
            coef, intercept = fake_params(rng)
            tx = ledger.submit_update(round_num, node, coef, intercept, N_SAMPLES[node])
            updates.append((coef, intercept, N_SAMPLES[node]))
            print(f"  submit_update  node {node}  n={N_SAMPLES[node]:3d}  "
                  f"weight_hash={tx['weight_hash'][:12]}…  sig={tx['signature'][:12]}…")

        # leader ทำ FedAvg ถ่วงน้ำหนักตามจำนวนข้อมูล (คำนวณนอกเชน)
        total = sum(n for _, _, n in updates)
        g_coef = np.sum([c * n for c, _, n in updates], axis=0) / total
        g_intercept = np.sum([b * n for _, b, n in updates], axis=0) / total
        global_params[round_num] = (g_coef, g_intercept)

        accuracy = 0.80 + 0.02 * round_num  # สมมติผลวัดจากชุดทดสอบกลาง
        block = ledger.record_aggregation(round_num, leader, g_coef, g_intercept, accuracy)
        print(f"  record_aggregation → block #{block.index}  tx={len(block.transactions)}  "
              f"sealed by {block.sealer}  seal={block.seal[:12]}…")

    # ---------- ตรวจสอบ ----------
    rule("ตรวจสอบเชน")
    report = ledger.audit()
    print(f"audit()             : ผ่าน {report}")
    print(f"leader ต่อโหนด       : {ledger.leader_counts()}")
    print(f"ขนาด ledger         : {ledger.ledger_bytes():,} bytes "
          f"(~{ledger.ledger_bytes() // ROUNDS:,} bytes/รอบ)")

    coef, intercept = global_params[2]
    print(f"verify_round(2) ของจริง  : {ledger.verify_round(2, coef, intercept)}")
    print(f"verify_round(2) ที่ถูกแก้ : {ledger.verify_round(2, coef + 1e-9, intercept)}")

    # ---------- กฎที่ ledger ปฏิเสธ ----------
    rule("กฎที่ ledger ปฏิเสธ (เทียบกับ chaincode ที่ reject transaction)")
    probe = 9  # รอบที่ยังไม่ถูกใช้ เอาไว้ยิงธุรกรรมที่ผิดกฎ
    outsider = NodeKey.generate("Z", seed="attacker")
    probe_leader = elect_leader(probe, NODES)
    not_leader = next(n for n in NODES if n != probe_leader)

    # ผู้บุกรุกปลอมธุรกรรมโดยอ้างว่าเป็น Node A แล้วเซ็นด้วยกุญแจตัวเอง
    forged = {
        "type": "model_update", "round": probe, "node_id": "A",
        "weight_hash": "0" * 64, "size_bytes": 88, "n_samples": 99999, "timestamp": 0.0,
    }
    forged["signature"] = sign_payload(outsider, unsigned_view(forged))

    # สมาชิกที่ถูกต้องแต่ไม่ใช่คิวของตัวเอง พยายามปิดบล็อกเอง
    def seal_out_of_turn() -> None:
        agg = {"type": "aggregation", "round": probe, "aggregator": not_leader,
               "aggregated_hash": "0" * 64, "participant_count": 1, "total_samples": 1,
               "accuracy": None, "timestamp": 0.0}
        agg["signature"] = sign_payload(ledger.keys[not_leader], unsigned_view(agg))
        ledger.chain.add_block([agg], sealer=ledger.keys[not_leader])

    checks = [
        ("โหนดนอก authority set ส่ง update",
         lambda: ledger.submit_update(probe, "Z", *fake_params(rng), 10, key=outsider)),
        ("ปลอมลายเซ็นโดยอ้างชื่อ Node A",
         lambda: ledger.submit_signed_update(forged)),
        ("ส่ง update ซ้ำในรอบเดิม",
         lambda: (ledger.submit_update(probe, "A", *fake_params(rng), 10),
                  ledger.submit_update(probe, "A", *fake_params(rng), 10))),
        ("คนที่ไม่ใช่ leader ขอรวมพารามิเตอร์",
         lambda: ledger.record_aggregation(probe, not_leader, *fake_params(rng))),
        ("สมาชิกแท้ปิดบล็อกนอกคิวตัวเอง", seal_out_of_turn),
        ("ปิดรอบที่ปิดแล้วซ้ำ",
         lambda: ledger.record_aggregation(1, elect_leader(1, NODES), *fake_params(rng))),
    ]
    for label, action in checks:
        try:
            action()
            print(f"  [ผิดคาด] {label}: ไม่ถูกปฏิเสธ")
        except Exception as exc:
            print(f"  [ปฏิเสธ] {label}\n            → {exc}")

    # ---------- เซฟ แล้วให้คนนอกตรวจเอง ----------
    rule("เซฟลงไฟล์ แล้วให้คนที่ถือแค่ไฟล์ตรวจเอง")
    ledger.chain.save(CHAIN_FILE)
    print(f"audit_chain('{CHAIN_FILE.name}') : {audit_chain(CHAIN_FILE)}")
    print("  คนนอกไม่ต้องเชื่อใคร ตรวจได้เองจากไฟล์ เพราะ public key ของทุกโหนดอยู่ในนั้น")

    # ---------- แก้ประวัติย้อนหลัง 2 แบบ ----------
    rule("ลองแก้ประวัติย้อนหลัง")
    raw = json.loads(CHAIN_FILE.read_text(encoding="utf-8"))

    # แบบที่ 1: แก้บล็อกกลางสาย (n_samples คือตัวถ่วงน้ำหนักใน FedAvg ยิ่งมากยิ่งดึงโมเดลกลาง)
    middle = json.loads(json.dumps(raw))
    for tx in middle["blocks"][1]["transactions"]:
        if tx.get("node_id") == "D":
            print(f"  แบบที่ 1: แก้ block #1 node D n_samples {tx['n_samples']} → 9999")
            tx["n_samples"] = 9999
            break
    try:
        Blockchain.from_dict(middle).validate()
        print("  [ผิดคาด] แก้แล้วยัง validate ผ่าน")
    except ChainError as exc:
        print(f"  [จับได้]  {exc}")

    # แบบที่ 2: ผู้โจมตีที่ฉลาดกว่า — แก้บล็อกท้ายสุดแล้วคำนวณ hash ใหม่ให้เนียน
    last = json.loads(json.dumps(raw))
    victim = last["blocks"][-1]
    for tx in victim["transactions"]:
        if tx.get("node_id") == "D":
            tx["n_samples"] = 9999
            break
    victim["hash"] = Block.from_dict({**victim, "hash": None}).compute_hash()
    print(f"  แบบที่ 2: แก้ block #{victim['index']} (ท้ายสุด ไม่มีบล็อกถัดไปให้ขัด) "
          f"แล้วคำนวณ hash ใหม่ให้ตรง")
    try:
        Blockchain.from_dict(last).validate()
        print("  [ผิดคาด] แก้แล้วยัง validate ผ่าน")
    except ChainError as exc:
        print(f"  [จับได้]  {exc}")
    print("  ← จุดนี้คือสิ่งที่ PoA ให้: ต่อให้คำนวณ hash ใหม่ได้ ก็ปลอมลายเซ็นของ leader ไม่ได้")

    print(f"\nไฟล์เชนอยู่ที่: {CHAIN_FILE}")


if __name__ == "__main__":
    main()
