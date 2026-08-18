# sl-blockchain

บล็อกเชนขนาดเล็กสำหรับ PoC **Blockchain-Based Swarm Learning** เขียนด้วย Python ล้วน
ไม่ต้องมี Docker ไม่ต้องตั้งเน็ตเวิร์ก รันจบในเครื่องเดียว

จุดประสงค์คือใช้เป็นขั้นแรกก่อนย้ายขึ้น Hyperledger Fabric: API และชื่อฟิลด์
ทำให้ตรงกับ chaincode `sl-ledger` ที่เขียนไว้ (`SubmitUpdate` / `RecordAggregation` /
`GetRoundUpdates` / `GetAggregation`) เพื่อให้ตอนเปลี่ยน backend โค้ดฝั่งโหนดแก้น้อยที่สุด

## ไฟล์

| ไฟล์ | หน้าที่ |
|---|---|
| `blockchain.py` | `Block` + `Blockchain` — hash chain, proof-of-work (ตัวเลือก), `validate()`, save/load JSON |
| `swarm_ledger.py` | `SwarmLedger` — ชั้นงานของ swarm learning + กฎแบบ smart contract |
| `demo.py` | สาธิต 5 โหนด 3 รอบ + ตรวจสอบ + ลองแก้ประวัติย้อนหลัง |
| `test_swarm_ledger.py` | เทสต์ 17 เคส (รันได้ทั้งกับ pytest และไม่มี pytest) |

## รัน

```bash
cd poc
.venv/bin/python sl-blockchain/demo.py              # สาธิต
.venv/bin/python sl-blockchain/test_swarm_ledger.py # เทสต์
```

## สิ่งที่บันทึกลงเชน

น้ำหนักโมเดลตัวจริง **ไม่ขึ้นเชน** เพราะใหญ่เกินกว่าจะเก็บในบล็อก และการเอาขึ้น
ก็ขัดกับเหตุผลที่ใช้ swarm learning ตั้งแต่ต้น บนเชนเก็บแค่ hash กับบัญชีรอบ
ให้ตรวจย้อนหลังได้ว่า "รอบไหน ใครส่งอะไร ใครเป็นคนรวม"

**ข้อตกลง: 1 รอบ swarm = 1 บล็อก** — บล็อกหนึ่งบรรจุ `model_update` ของทุกโหนดในรอบนั้น
แล้วปิดท้ายด้วย `aggregation` ของ leader

```jsonc
// model_update — โหนดหนึ่งประกาศผลเทรนในเครื่อง
{"type": "model_update", "round": 1, "node_id": "A",
 "weight_hash": "aae85fb3…", "size_bytes": 88, "n_samples": 240, "timestamp": 1755…}

// aggregation — leader ประกาศโมเดลกลางของรอบ
{"type": "aggregation", "round": 1, "aggregator": "D", "aggregated_hash": "4c1f…",
 "participant_count": 5, "total_samples": 680, "accuracy": 0.82, "timestamp": 1755…}
```

## กฎที่ ledger บังคับ

ส่วนนี้คือสิ่งที่ทำให้เป็น "blockchain-based" ไม่ใช่แค่ log ไฟล์ — ธุรกรรมที่ผิดกฎถูกปฏิเสธ
เหมือน chaincode ปฏิเสธ transaction:

| กฎ | เทียบกับ Fabric |
|---|---|
| ผู้ส่งต้องเป็นสมาชิกที่ประกาศไว้ | MSP membership |
| หนึ่งโหนดส่งได้รอบละครั้ง | เช็ค composite key ซ้ำใน `SubmitUpdate` |
| ผู้รวมพารามิเตอร์ต้องเป็น leader ของรอบนั้น | เช็ค `AggregatorMSP` |
| รอบที่ปิดแล้วแก้ไม่ได้ | ledger เป็น append-only |

leader ของแต่ละรอบมาจาก `sha256(เลขรอบ + รายชื่อผู้เข้าร่วม)` — **สูตรเดียวกับใน
`ini_swarm.ipynb`** ทุกโหนดคำนวณเองได้ ผลตรงกัน ไม่ต้องมีศูนย์กลางคอยแต่งตั้ง
และตรวจย้อนหลังได้ว่ารอบนั้นใครมีสิทธิ์ (ถ้าแก้สูตรที่ไฟล์ใดไฟล์หนึ่ง
เชนจะปฏิเสธ aggregation จาก notebook ทันที)

## proof-of-work

`Blockchain(difficulty=n)` บังคับให้ hash ของบล็อกขึ้นต้นด้วย `0` จำนวน n ตัว
ค่าเริ่มต้นคือ `0` (ปิด) เพราะ swarm ของเราเป็นระบบที่สมาชิกรู้ตัวตนกันอยู่แล้ว
การแข่งขันขุดไม่ได้เพิ่มความปลอดภัยอะไร มีไว้เพื่อสาธิตกลไกเวลาต้องอธิบายเท่านั้น
(`demo.py` เปิดไว้ที่ 2 ให้เห็นว่า nonce ต้องไล่หา)

## ต่อกับ notebook

`ini_swarm.ipynb` มีลูป swarm อยู่แล้ว เพิ่ม ledger เข้าไปได้โดยไม่แตะตรรกะการเทรน:

```python
import sys; sys.path.append("sl-blockchain")
from swarm_ledger import SwarmLedger

ledger = SwarmLedger(NODE_NAMES)

# ในลูป หลัง local_train ของแต่ละโหนด
ledger.submit_update(round_num, name, coef, intercept, len(y_nodes[name]))

# หลัง aggregate()
ledger.record_aggregation(round_num, leader, global_coef, global_intercept, swarm_acc)

# จบทุกรอบ
ledger.chain.validate()
ledger.chain.save("swarm_chain.json")
print(ledger.leader_counts(), ledger.ledger_bytes(), "bytes")
```

โหนดที่รับโมเดลกลางมาตรวจได้ว่าได้ของจริงหรือไม่ด้วย
`ledger.verify_round(round_num, coef, intercept)`

## ยังไม่มีในเวอร์ชันนี้

เรียงตามลำดับที่ควรทำต่อ:

1. **ลายเซ็นดิจิทัล** — ตอนนี้ `node_id` เป็นแค่ข้อความ ใครก็อ้างเป็นโหนด A ได้
   ถ้าเข้าถึงตัวแปร ledger ได้ ขั้นถัดไปคือให้แต่ละโหนดถือคู่กุญแจแล้วเซ็น
   transaction (ed25519 ผ่าน `cryptography`) แล้ว ledger ตรวจลายเซ็นก่อนรับ
2. **หลายเครื่องจริง** — เวอร์ชันนี้เป็น in-process ทุกโหนดใช้ออบเจ็กต์ ledger เดียวกัน
   ยังไม่มี networking / consensus ระหว่างเครื่อง
3. **Merkle tree** — `tx_root` ตอนนี้คือ hash รวมทีเดียวของธุรกรรมทั้งบล็อก
   ยังพิสูจน์แบบ "ธุรกรรมนี้อยู่ในบล็อกนี้" โดยไม่ต้องส่งทั้งบล็อกไม่ได้
4. **ย้ายขึ้น Fabric** — เปลี่ยนเฉพาะ backend ของ `SwarmLedger` ไปเรียก chaincode
   `sl-ledger` โดยที่โหนดยังเรียกเมธอดชื่อเดิม
