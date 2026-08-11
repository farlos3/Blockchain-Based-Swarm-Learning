# PoC Architecture

`poc/` ประกอบขึ้นอย่างไร และทำไมถึงออกแบบแบบนี้

## สองชั้น

PoC แบ่งเป็น **blockchain layer** (Hyperledger Fabric — ทำหน้าที่ประสานงาน
อย่างเดียว) กับ **ML layer** (Python — เทรนโมเดลจริง) เชื่อมกันด้วย shell
script ไม่มีอะไรของฝั่ง ML อยู่ on-chain นอกจาก hash

```
poc/
├── chaincode/sl-ledger/   Go chaincode — the ledger's data model
├── scripts/               network lifecycle + chaincode invoke/query + resource sampler
├── sl-client/             Python: local training, aggregation, orchestration
└── results/               measured CSVs from the last run
```

## Blockchain layer: consortium 3 องค์กร

`scripts/01-network-up.sh` และ `02-join-org3-cc.sh` ยกเครือข่าย Hyperledger
Fabric ขึ้นมาผ่าน `fabric-samples/test-network`: 3 องค์กร (`Org1MSP`/
`Org2MSP`/`Org3MSP` แต่ละองค์กรมี Fabric CA ของตัวเอง), Raft orderer 1 ตัว,
peer + CouchDB องค์กรละชุด, channel เดียว (`slchannel`) chaincode `sl-ledger`
ถูก install และ approve โดยทั้งสามองค์กร ดังนั้น default
majority-endorsement policy ของ channel จึงต้องการลายเซ็น 2-of-3 องค์กร
ในทุกการเขียน — นั่นคือ trust model แบบ "consortium" ที่ถูกบังคับใช้จริง
ไม่ใช่แค่ตั้งค่าไว้เฉยๆ

ตัว chaincode เอง (`chaincode/sl-ledger/contract.go`) ตั้งใจให้บางที่สุด —
มันคือ ledger สำหรับประสานงาน ไม่ใช่ที่เก็บโมเดล:

- `SubmitUpdate(round, nodeId, weightHash, sizeBytes, timestamp)` — หนึ่ง
  entry ต่อโหนดต่อรอบ ใช้ composite key `("update", round, nodeId)` เพื่อไม่ให้
  โหนดหนึ่งเขียนทับ submission ของอีกโหนด หรือส่งซ้ำในรอบเดิมได้
- `GetRoundUpdates(round)` — range query บน composite key นั้น เพื่อ list
  submission ของทุกโหนดในรอบหนึ่ง
- `RecordAggregation(round, aggregatedHash, participantCount, timestamp)` —
  hash ของ global model ที่รวมแล้วในรอบนั้น ใช้ key `("agg", round)`

Model weights ไม่เคยแตะ chain — มีแค่ SHA-256 hash กับจำนวนไบต์ นี่คือ
decision หลักของดีไซน์: channel 3 องค์กรจริงไม่มีเหตุผลจะ replicate tensor
ขนาดหลายเมกะไบต์เข้า block store ของทุก peer ทุกรอบ หน้าที่ของ chain จึงจำกัด
อยู่ที่ *integrity + audit trail* (ใครส่งอะไร เมื่อไร และผลรวมที่ตกลงกันคืออะไร)
ส่วนไบต์ของ weights จริงเคลื่อนย้ายกัน off-chain

`scripts/cc-invoke.sh` / `cc-query.sh` คือสะพานเชื่อม: รับหมายเลของค์กรกับชื่อ
ฟังก์ชัน chaincode แล้วตั้ง MSP identity ขององค์กรนั้น (ผ่าน `setGlobals` ใน
`envVar.sh`) จากนั้นจะ invoke (เก็บ endorsement จากทั้ง 3 peer ก่อนส่งให้
orderer) หรือ query (peer เดียว ไม่ต้อง round-trip ผ่าน ordering) ทุกอย่าง
เหนือชั้น shell ขึ้นไปคุยกับ chain ผ่านสองสคริปต์นี้เท่านั้น

## ML layer: SL node แบบ off-chain

`sl-client/sl_node.py` คือ logic ของ "local party" ไม่รับรู้เรื่อง chain เลย:

- `load_shard(node_index, num_nodes)` แบ่ง dataset `digits` ของ sklearn เป็น
  shard ที่ไม่ทับกัน โหนดจำลองละหนึ่ง shard
- `local_train(...)` โหลด global weights ของรอบ *ก่อนหน้า* จากไฟล์ local
  (`results/weights/round_{N-1}/global.npz`) แล้ว warm-start `SGDClassifier`
  เทรนไม่กี่ epoch บน shard ของโหนดตัวเอง เขียน weights ใหม่ลง
  `results/weights/round_N/{node_id}.npz` แล้วคืนค่า SHA-256 hash + ขนาดไฟล์
- `aggregate(round, node_ids)` — FedAvg ธรรมดา: โหลดไฟล์ weights ของทั้งสาม
  โหนดแล้วเฉลี่ยเป็น `global.npz`

เพราะทุกอย่างรันบนเครื่องเดียว "การแลกเปลี่ยน weights แบบ off-chain" ตรงนี้จึง
จำลองเป็น directory local ที่ใช้ร่วมกัน แทนการส่งแบบ peer-to-peer จริง — เป็น
การลดทอนที่ตั้งใจ จุดประสงค์ของ PoC คือวัด overhead ของ *blockchain*
ไม่ใช่สร้าง P2P transport จริง

## Orchestration: หนึ่งรอบ ทีละขั้น

`sl-client/orchestrate.py` คือ loop ที่ร้อยทุกอย่างเข้าด้วยกัน แต่ละรอบ:

1. สำหรับแต่ละโหนดใน 3 โหนด: `local_train` (คำนวณล้วน) แล้ว
   `cc-invoke.sh <org> SubmitUpdate ...` (เขียน จับเวลา) แล้ว
   `cc-query.sh <org> GetRoundUpdates ...` (อ่านกลับ จับเวลา)
2. `aggregate()` แบบ local (FedAvg บนไฟล์ weights 3 ไฟล์ที่เพิ่งส่ง)
3. องค์กรที่เป็น "aggregator" แบบ round-robin (`NODES[round_num % 3]`) เรียก
   `RecordAggregation` — สะท้อนแนวคิด leader-rotation ของ Swarm Learning จริง
   จึงไม่มีองค์กรใดเป็น coordinator ถาวร
4. เก็บขนาด ledger ก่อน/หลัง ผ่าน `docker exec ... du -sb` บน ledger data ของ
   peer0.org1 เพื่อติดตามการโตของ storage บน chain ในแต่ละรอบ

ทุกค่าเวลา (`train_seconds`, `submit_latency_s`, `query_latency_s`,
`agg_latency_s`) และส่วนต่างขนาด ledger ถูกเขียนลง
`results/round_metrics.csv` — CSV นั้นคือหลักฐานตรงที่อยู่เบื้องหลังตัวเลข
ทรัพยากรใน `poc/README.md`

`scripts/monitor.py` รันแยกอิสระควบคู่ไปกับแต่ละรอบ โดย poll `docker stats`
ทุก 2 วินาที สำหรับทุก Fabric container แล้วเขียน `results/docker_stats.csv`
— ตัวเลข idle CPU/RAM footprint มาจากไฟล์นี้

## ทำไมถึงออกแบบรูปนี้

- **weights อยู่ off-chain, hash อยู่ on-chain** — ทำให้ต้นทุน storage/
  bandwidth ของ chain ไม่ขึ้นกับขนาดโมเดล ซึ่งเป็นเหตุผลที่ README อ้างได้ว่า
  consensus latency ~2.4 วินาที/tx เป็นพื้นค่าคงที่ ไม่ใช่ค่าที่แย่ลงเมื่อโมเดล
  ใหญ่ขึ้น
- **ใช้ Fabric org จริง 3 องค์กร ไม่ใช่ chain จำลอง** — คำตอบว่า "consortium"
  ต่อคำถามเรื่องทรัพยากร/permission ตั้งต้น จึงเป็นสิ่งที่ PoC วัดได้จริง
  (endorsement ถูกบังคับใช้ ตรวจยืนยันผ่าน `querycommitted`) ไม่ใช่แค่กล่าวอ้าง
- **shell script เป็น interface เดียวที่ติดต่อ chain** — Python ไม่แตะ Fabric
  SDK เลย แต่เรียก `peer` CLI ตัวเดียวกับที่ operator มนุษย์ใช้ ง่ายกว่า และ
  เลี่ยงปัญหา Python SDK ของ Fabric ที่รองรับไม่ทั่วถึง แลกกับ subprocess
  `bash` หนึ่งตัวต่อการเรียก chain หนึ่งครั้ง (ต้นทุนนั้นปรากฏในค่าเวลาที่วัดด้วย)
