"""สาธิตการใช้ ledger: 5 โหนด 3 รอบ + ตรวจสอบความถูกต้อง + จำลองการแก้ข้อมูลย้อนหลัง

รัน:  python demo.py
พารามิเตอร์ในนี้เป็นตัวเลขสุ่ม ไม่ได้เทรนจริง เพราะจุดประสงค์คือดูกลไกของเชน
ส่วนการต่อกับโมเดลจริงดูใน README หัวข้อ "ต่อกับ notebook"
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from blockchain import Blockchain, ChainError
from swarm_ledger import SwarmLedger, elect_leader

NODES = ["A", "B", "C", "D", "E"]
N_SAMPLES = {"A": 240, "B": 160, "C": 110, "D": 60, "E": 110}
ROUNDS = 3
CHAIN_FILE = Path(__file__).with_name("chain.json")


def fake_params(rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """แทนที่พารามิเตอร์จากการเทรนจริง (coef 1x10 + intercept 1 ตัว เท่ากับ SGDClassifier)"""
    return rng.normal(0, 1, size=(1, 10)), rng.normal(0, 1, size=(1,))


def main() -> None:
    rng = np.random.default_rng(7)
    # difficulty=2 เปิด proof-of-work ไว้ให้เห็นว่าปิดบล็อกต้องออกแรงหา nonce
    ledger = SwarmLedger(NODES, difficulty=2)

    print("=" * 78)
    print(f"swarm ledger: {len(NODES)} โหนด, {ROUNDS} รอบ, difficulty={ledger.chain.difficulty}")
    print("=" * 78)

    global_params: dict[int, tuple[np.ndarray, np.ndarray]] = {}

    for round_num in range(1, ROUNDS + 1):
        leader = elect_leader(round_num, NODES)
        print(f"\n[รอบ {round_num}] leader = Node {leader}")

        # 1) ทุกโหนดเทรนในเครื่อง แล้วส่งแค่ hash ขึ้นเชน
        updates = []
        for node in NODES:
            coef, intercept = fake_params(rng)
            weight_hash = ledger.submit_update(round_num, node, coef, intercept, N_SAMPLES[node])
            updates.append((coef, intercept, N_SAMPLES[node]))
            print(f"  submit_update  node {node}  n={N_SAMPLES[node]:3d}  weight_hash={weight_hash[:16]}…")

        # 2) leader ทำ FedAvg ถ่วงน้ำหนักตามจำนวนข้อมูล (คำนวณนอกเชน)
        total = sum(n for _, _, n in updates)
        g_coef = np.sum([c * n for c, _, n in updates], axis=0) / total
        g_intercept = np.sum([b * n for _, b, n in updates], axis=0) / total
        global_params[round_num] = (g_coef, g_intercept)

        # 3) leader บันทึก hash ของโมเดลกลาง = ปิดบล็อกของรอบนี้
        accuracy = 0.80 + 0.02 * round_num  # สมมติผลวัดจากชุดทดสอบกลาง
        block = ledger.record_aggregation(round_num, leader, g_coef, g_intercept, accuracy)
        print(f"  record_aggregation → block #{block.index}  nonce={block.nonce}  "
              f"tx={len(block.transactions)}  hash={block.compute_hash()[:16]}…")

    # ---------- ตรวจสอบ ----------
    print("\n" + "=" * 78)
    print("ตรวจสอบเชน")
    print("=" * 78)
    ledger.chain.validate()
    print(f"validate()          : ผ่าน ({ledger.chain.height} บล็อก, ไม่นับ genesis)")
    print(f"leader ต่อโหนด       : {ledger.leader_counts()}")
    print(f"ขนาด ledger         : {ledger.ledger_bytes():,} bytes "
          f"(~{ledger.ledger_bytes() // ROUNDS:,} bytes/รอบ)")

    coef, intercept = global_params[2]
    print(f"verify_round(2) ของจริง   : {ledger.verify_round(2, coef, intercept)}")
    print(f"verify_round(2) ที่ถูกแก้  : {ledger.verify_round(2, coef + 1e-9, intercept)}")

    agg = ledger.get_aggregation(2)
    print(f"aggregation รอบ 2   : aggregator={agg['aggregator']} "
          f"participants={agg['participant_count']} accuracy={agg['accuracy']}")

    # ---------- กฎของ ledger ----------
    print("\n" + "=" * 78)
    print("กฎที่ ledger ปฏิเสธ (เทียบกับ chaincode ที่ reject transaction)")
    print("=" * 78)
    probe_round = 9  # รอบที่ยังไม่ถูกใช้ เอาไว้ยิงธุรกรรมที่ผิดกฎ
    wrong_leader = next(n for n in NODES if n != elect_leader(probe_round, NODES))
    checks = [
        ("โหนดนอก swarm ส่ง update",
         lambda: ledger.submit_update(probe_round, "Z", *fake_params(rng), 10)),
        ("ส่ง update ซ้ำในรอบเดิม",
         lambda: (ledger.submit_update(probe_round, "A", *fake_params(rng), 10),
                  ledger.submit_update(probe_round, "A", *fake_params(rng), 10))),
        ("คนที่ไม่ใช่ leader ขอรวมพารามิเตอร์",
         lambda: ledger.record_aggregation(probe_round, wrong_leader, *fake_params(rng))),
        ("ปิดรอบที่ปิดแล้วซ้ำ",
         lambda: ledger.record_aggregation(1, elect_leader(1, NODES), *fake_params(rng))),
    ]
    for label, action in checks:
        try:
            action()
            print(f"  [ผิดคาด] {label}: ไม่ถูกปฏิเสธ")
        except Exception as exc:
            print(f"  [ปฏิเสธ] {label}\n            → {exc}")

    # ---------- เซฟ/โหลด แล้วลองแก้ข้อมูลย้อนหลัง ----------
    print("\n" + "=" * 78)
    print("เซฟลงไฟล์ แล้วลองแก้ประวัติย้อนหลัง")
    print("=" * 78)
    ledger.chain.save(CHAIN_FILE)
    reloaded = Blockchain.load(CHAIN_FILE)
    reloaded.validate()
    print(f"โหลดกลับมา validate() : ผ่าน ({CHAIN_FILE.name}, {len(reloaded)} บล็อกรวม genesis)")

    # แก้จำนวนข้อมูลของ Node D ในรอบ 1 ให้ดูเหมือนมีข้อมูลมากกว่าความจริง
    # (แรงจูงใจจริง: n_samples เป็นตัวถ่วงน้ำหนักใน FedAvg ยิ่งมากยิ่งดึงโมเดลกลาง)
    victim = reloaded.blocks[1]
    for tx in victim.transactions:
        if tx.get("node_id") == "D":
            print(f"  แก้ block #{victim.index}: node D n_samples {tx['n_samples']} → 9999")
            tx["n_samples"] = 9999
            break
    try:
        reloaded.validate()
        print("  [ผิดคาด] แก้ประวัติแล้วยัง validate ผ่าน")
    except ChainError as exc:
        print(f"  [จับได้]  {exc}")

    print(f"\nไฟล์เชนอยู่ที่: {CHAIN_FILE}")


if __name__ == "__main__":
    main()
