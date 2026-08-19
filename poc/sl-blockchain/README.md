# sl-blockchain

บล็อกเชนขนาดเล็กสำหรับ PoC **Blockchain-Based Swarm Learning** เขียนด้วย Python
ใช้ **Proof of Authority (PoA)** เป็นกลไกฉันทามติ ไม่ต้องมี Docker ไม่ต้องตั้งเน็ตเวิร์ก
รันจบในเครื่องเดียว

ออกแบบให้เป็นขั้นแรกก่อนย้ายขึ้น Hyperledger Fabric: ชื่อเมธอดและฟิลด์ทำให้ตรงกับ
chaincode `sl-ledger` ที่เขียนไว้ (`SubmitUpdate` / `RecordAggregation` /
`GetRoundUpdates` / `GetAggregation`) เพื่อให้ตอนเปลี่ยน backend โค้ดฝั่งโหนดแก้น้อยที่สุด

## ไฟล์

| ไฟล์ | หน้าที่ |
|---|---|
| `blockchain.py` | `Block` + `Blockchain` — hash chain, `validate()`, save/load JSON |
| `consensus.py` | `ProofOfAuthority` (ค่าเริ่มต้น) + `ProofOfWork` (ไว้เทียบ), กุญแจ ed25519, กฎเลือก leader |
| `swarm_ledger.py` | `SwarmLedger` — ชั้นงาน swarm learning, ธุรกรรมมีลายเซ็น, `audit_chain()` |
| `demo.py` | สาธิต 5 โหนด 3 รอบ + กฎที่ถูกปฏิเสธ + ลองแก้ประวัติย้อนหลัง 2 แบบ |
| `test_swarm_ledger.py` | เทสต์ 28 เคส (รันได้ทั้งกับ pytest และไม่มี pytest) |

## รัน

```bash
cd poc
.venv/bin/python sl-blockchain/demo.py              # สาธิต
.venv/bin/python sl-blockchain/test_swarm_ledger.py # เทสต์
```

ต้องมี `cryptography` (อยู่ใน `poc/requirements.txt` แล้ว) สำหรับลายเซ็น ed25519

## ทำไมเลือก Proof of Authority

swarm ของเราเป็น consortium ที่สมาชิกรู้ตัวตนกันอยู่แล้ว (แต่ละองค์กรเข้าร่วมด้วยข้อตกลง)
โจทย์จึงไม่ใช่ "ใครก็เข้ามาขุดได้" แต่เป็น "ยืนยันให้ได้ว่าบล็อกนี้ผู้มีสิทธิ์เป็นคนปิดจริง"

- **PoW** แก้ปัญหา Sybil ในเครือข่ายเปิด ต้องแลกด้วย CPU และเวลา — ที่นี่ไม่มี Sybil
  ให้แก้ตั้งแต่แรก การเผา CPU จึงเพิ่มแค่ค่าไฟกับ latency (ยังเปิดใช้ได้เพื่อเทียบให้เห็นในเล่ม)
- **PoA** ผูกสิทธิ์ปิดบล็อกกับตัวตนที่ประกาศไว้ ต้นทุนต่อบล็อกเกือบเป็นศูนย์
  และตรงกับโมเดลของ Fabric (ทำอะไรได้ ขึ้นกับว่าเป็นใคร ไม่ใช่มีพลังประมวลผลเท่าไร)

PoA ในไฟล์นี้ประกอบด้วย 3 ส่วนตามนิยาม:

| ส่วน | ที่นี่ทำอย่างไร |
|---|---|
| **authority set** | `node_id → ed25519 public key` ประกาศไว้บนเชน (private key อยู่กับโหนดเท่านั้น) |
| **leader rule** | `sha256(เลขรอบ + รายชื่อสมาชิก) mod จำนวนสมาชิก` ทุกโหนดคำนวณเองได้ ผลตรงกัน |
| **block seal** | leader เซ็น hash ของบล็อกด้วย private key ตัวเอง ใครถือไฟล์เชนก็ตรวจได้ |

`elect_leader()` เป็น **สูตรเดียวกับใน `ini_swarm.ipynb`** — ถ้าแก้ที่ไฟล์ใดไฟล์หนึ่ง
เชนจะปฏิเสธ aggregation จาก notebook ทันที

## สิ่งที่บันทึกลงเชน

น้ำหนักโมเดลตัวจริง **ไม่ขึ้นเชน** เพราะใหญ่เกินกว่าจะเก็บในบล็อก และการเอาขึ้นก็ขัดกับ
เหตุผลที่ใช้ swarm learning ตั้งแต่ต้น บนเชนเก็บแค่ hash กับบัญชีรอบ

**ข้อตกลง: 1 รอบ swarm = 1 บล็อก** — บล็อกหนึ่งบรรจุ `model_update` ของทุกโหนดในรอบนั้น
แล้วปิดท้ายด้วย `aggregation` ของ leader ทุกธุรกรรมมีลายเซ็นของผู้ส่งกำกับ

```jsonc
// model_update — โหนดหนึ่งประกาศผลเทรนในเครื่อง
{"type": "model_update", "round": 1, "node_id": "A", "weight_hash": "aae85fb3…",
 "size_bytes": 88, "n_samples": 240, "timestamp": 1755…, "signature": "8f61ea7b…"}

// aggregation — leader ประกาศโมเดลกลางของรอบ
{"type": "aggregation", "round": 1, "aggregator": "D", "aggregated_hash": "4c1f…",
 "participant_count": 5, "total_samples": 680, "accuracy": 0.82,
 "timestamp": 1755…, "signature": "00aa333b…"}
```

ตัวบล็อกเองมี `sealer` (ใครปิด) + `seal` (ลายเซ็นบน hash ของบล็อก) เพิ่มจากธุรกรรมข้างใน

## กฎที่ถูกบังคับ

ส่วนนี้คือสิ่งที่ทำให้เป็น blockchain-based ไม่ใช่แค่ log ไฟล์ — ธุรกรรมที่ผิดกฎถูกปฏิเสธ
เหมือน chaincode ปฏิเสธ transaction (`demo.py` สาธิตครบทุกข้อ):

| กฎ | เทียบกับ Fabric |
|---|---|
| ผู้ส่งต้องอยู่ใน authority set | MSP membership |
| ลายเซ็นต้องตรงกับ public key ที่ประกาศไว้ | ตรวจ certificate ของผู้ส่ง |
| หนึ่งโหนดส่งได้รอบละครั้ง | เช็ค composite key ซ้ำใน `SubmitUpdate` |
| ผู้ปิดบล็อกต้องเป็น leader ของรอบนั้น | เช็ค `AggregatorMSP` |
| รอบที่ปิดแล้วแก้ไม่ได้ | ledger เป็น append-only |

การแก้ประวัติย้อนหลังถูกจับได้ 3 ชั้น:

1. แก้บล็อกกลางสาย → `prev_hash` ของบล็อกถัดไปไม่ตรง
2. แก้บล็อกท้ายสุด → ไม่ตรงกับ hash ที่บันทึกไว้ในไฟล์
3. แก้แล้วคำนวณ hash ใหม่ให้เนียน → **ยังตกที่ลายเซ็นของ leader** เพราะไม่มี private key
   ← ข้อนี้คือสิ่งที่ PoA ให้ ซึ่ง hash chain เปล่า ๆ ให้ไม่ได้

## ตรวจสอบโดยไม่ต้องเชื่อใคร

```python
from swarm_ledger import audit_chain
audit_chain("chain.json")
# {'consensus': 'poa', 'blocks': 3, 'transactions_verified': 18,
#  'authorities': ['A', 'B', 'C', 'D', 'E']}
```

คนที่ถือแค่ไฟล์เชนตรวจได้เองครบทั้ง 3 ชั้น (โครงสร้างสาย + ลายเซ็นผู้ปิดบล็อกว่าตรงคิว +
ลายเซ็นทุกธุรกรรม) เพราะ public key ของทุกโหนดถูกเก็บอยู่ในไฟล์

## ต่อกับ notebook

`ini_swarm.ipynb` มีลูป swarm อยู่แล้ว เพิ่ม ledger เข้าไปได้โดยไม่แตะตรรกะการเทรน:

```python
import sys; sys.path.append("sl-blockchain")
from swarm_ledger import SwarmLedger

ledger = SwarmLedger.bootstrap(NODE_NAMES, seed="poc")   # ของจริงแต่ละโหนดสร้างกุญแจเอง

# ในลูป หลัง local_train ของแต่ละโหนด
ledger.submit_update(round_num, name, coef, intercept, len(y_nodes[name]))

# หลัง aggregate()
ledger.record_aggregation(round_num, leader, global_coef, global_intercept, swarm_acc)

# จบทุกรอบ
print(ledger.audit(), ledger.leader_counts(), ledger.ledger_bytes(), "bytes")
ledger.chain.save("swarm_chain.json")
```

โหนดที่รับโมเดลกลางมาตรวจได้ว่าได้ของจริงหรือไม่ด้วย
`ledger.verify_round(round_num, coef, intercept)`

## ยังไม่มีในเวอร์ชันนี้

เรียงตามลำดับที่ควรทำต่อ:

1. **หลายเครื่องจริง** — ตอนนี้เป็น in-process ทุกโหนดใช้ออบเจ็กต์ ledger เดียวกัน
   ยังไม่มี networking และยังไม่มีการตกลงกันว่าใครถือสายที่ถูกต้อง (fork resolution)
2. **การจัดการ authority set** — สมาชิกคงที่ตั้งแต่สร้าง ยังเพิ่ม/ถอดสมาชิกกลางทางไม่ได้
   ของจริงต้องมีธุรกรรมประเภท governance ที่ต้องมีเสียงรับรองจากสมาชิกเดิม
3. **leader ที่หายไป** — ถ้า leader ของรอบนั้นออฟไลน์ ระบบจะค้าง ยังไม่มี timeout
   ที่จะข้ามไปคนถัดไป (Clique/Aura แก้ด้วยการให้คนอื่นปิดแทนได้หลังเลยเวลา)
4. **Merkle tree** — `tx_root` ตอนนี้คือ hash รวมทีเดียวของธุรกรรมทั้งบล็อก
   ยังพิสูจน์แบบ "ธุรกรรมนี้อยู่ในบล็อกนี้" โดยไม่ต้องส่งทั้งบล็อกไม่ได้
5. **ย้ายขึ้น Fabric** — เปลี่ยนเฉพาะ backend ของ `SwarmLedger` ไปเรียก chaincode
   `sl-ledger` โดยที่โหนดยังเรียกเมธอดชื่อเดิม
