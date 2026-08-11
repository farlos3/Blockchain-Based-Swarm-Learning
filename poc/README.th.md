# Blockchain-Based Swarm Learning — PoC

เป้าหมายของ PoC นี้: วัดว่า Swarm Learning (SL) หนึ่งรอบที่ประสานงานผ่าน
blockchain กินทรัพยากรจริงเท่าไร และสรุปให้ได้ว่า permissioned blockchain
แบบไหนเหมาะกับ trust model ของ SL โดยใช้เครือข่าย Hyperledger Fabric จริง
(ไม่ใช่การจำลอง)

## สถาปัตยกรรม

- **Blockchain**: Hyperledger Fabric 2.5, channel แบบ **consortium** 3 องค์กร
  (`slchannel`), identity ออกให้แต่ละองค์กรโดย Fabric CA (ไม่ใช่แค่ cert
  แบบ static จาก `cryptogen` — ใกล้เคียงกับการ provision identity ใน
  deployment หลายสถาบันจริงมากกว่า)
- **Chaincode** (`chaincode/sl-ledger`, Go): บันทึกเฉพาะ metadata สำหรับ
  ประสานงาน SL เท่านั้น — `SubmitUpdate(round, nodeId, weightHash, sizeBytes, ts)`
  และ `RecordAggregation(round, aggregatedHash, participantCount, ts)`
  ตัว model weights เก็บไว้ off-chain (channel 3 องค์กรจริงไม่มีเหตุผลจะ
  เก็บ tensor ขนาดหลาย MB ไว้ใน block store ของทุก peer) มีเพียง SHA-256
  integrity hash ที่ถูก commit ลง chain
- **SL nodes** (`sl-client/`): 3 party จำลอง (องค์กรละหนึ่ง) แต่ละตัวเทรน
  โมเดล multinomial logistic-regression ขนาดเล็ก (`sklearn`, digits dataset,
  แบ่ง shard ไม่ทับกัน) เป็น local epoch ไม่กี่รอบ แล้วส่ง hash ของ update
  เข้า chaincode โหนด "aggregator" แบบ round-robin จะอ่าน update ทั้งสามกลับมา
  ทำ FedAvg กับ weights แล้วบันทึก hash ที่รวมแล้วลง on-chain
- **Resource monitor** (`scripts/monitor.py`): เก็บค่า `docker stats` ของทุก
  Fabric container ทุก 2 วินาที ตลอดช่วงที่รัน

## ประเภท permission: consortium ไม่ใช่ public / ไม่ใช่ single-org

ทำเป็น **permissioned consortium blockchain**: Fabric org อิสระ 3 องค์กร
(`Org1MSP`, `Org2MSP`, `Org3MSP`) แต่ละองค์กรแทน SL party/สถาบันหนึ่งราย
แต่ละรายมี CA และ MSP ของตัวเอง channel ใช้ **default majority-endorsement
policy** ของ Fabric ซึ่งประเมินจากสมาชิก channel ณ *ปัจจุบัน* — ดังนั้นเมื่อ
Org3 เข้าร่วมแล้ว ทุกการเขียน (`SubmitUpdate`, `RecordAggregation`) ต้องมี
endorsement signature จากอย่างน้อย **2 ใน 3 องค์กร** ก่อน orderer จะ commit
คำสั่ง `querycommitted` หลัง Org3 approve ยืนยันผลว่า
`[Org1MSP: true, Org2MSP: true, Org3MSP: true]`

รูปแบบนี้เหมาะกับ SL โดยเฉพาะ เพราะแก่นของ SL คือ party ที่ไม่ไว้ใจกัน
(โรงพยาบาล ธนาคาร ฯลฯ) ที่ต้องการ log ประสานงานร่วมกันแบบ tamper-evident
*โดยไม่มี* server กลางที่ต้องเชื่อใจ — chain แบบ public/permissionless ไม่ให้
identity accountability ว่าใครส่งอะไร ส่วน private chain แบบองค์กรเดียวก็ไม่ให้
หลักประกันความเชื่อใจแบบหลายฝ่ายจริง (ฝ่ายเดียวปลอมเรคอร์ด aggregation ที่อ้างว่า
เป็น "consensus" ได้เอง) consortium chain ที่ใช้ endorsement แบบ N-of-M คือ
คำตอบมาตรฐานของปัญหานี้ และเป็นสิ่งที่ PoC นี้บังคับใช้จริง ไม่ใช่แค่กล่าวอ้าง

## ผลการวัดทรัพยากร

ตัวเลขทั้งหมดวัดบนเครื่องนี้ (Windows, Docker Desktop, ไม่มี GPU) ผ่าน
`docker stats`, sampling ทุก 2 วินาที ตลอดการรัน 5 รอบ ข้อมูลดิบ:
`results/docker_stats.csv`, `results/round_metrics.csv`

### Idle footprint (เครือข่ายเปิดอยู่ ไม่มี traffic SL)

| Layer | Containers | RAM เฉลี่ย | CPU เฉลี่ย |
|---|---|---|---|
| Fabric CA (ออก identity) | 3 | ~9.1 MiB ต่อตัว (~27 MiB รวม) | ~0% |
| Ordering service | 1 | ~16–19 MiB | ~0.3% |
| Peers (องค์กรละ 1) | 3 | ~85–104 MiB ต่อตัว (~275 MiB รวม) | ~3% ต่อตัว |
| CouchDB (world state ต่อองค์กร) | 3 | ~94–106 MiB ต่อตัว (~300 MiB รวม) | ~1.3% ต่อตัว |
| Chaincode containers (องค์กรละ 1 สร้างตอน invoke ครั้งแรก) | 3 | ~7 MiB ต่อตัว (~21 MiB รวม) | <1% |
| **รวม** | **13** | **≈ 649 MiB RSS** | ต่ำ เป็นช่วงพุ่ง |

Disk (Docker images, ใช้ layer ร่วมกัน ดึงครั้งเดียว — ไม่ใช่ต่อ container):
`fabric-peer` 232 MB, `fabric-orderer` 182 MB, `fabric-ca` 381 MB,
`couchdb` 419 MB, `fabric-baseos` 257 MB (runtime base ของ chaincode),
`fabric-ccenv` 1.01 GB (image สำหรับ **build** chaincode ใช้ชั่วคราวตอน
package/install เท่านั้น ไม่ได้รันตอน steady state) — **≈ 2.48 GB
รวมขนาด image ที่ไม่ซ้ำกัน** สำหรับ stack 3 องค์กรเต็มรูปแบบ ปริมาตร
ledger/state หลัง commit ไป 6 block: ~128 MB (orderer ส่วนใหญ่เป็น overhead
คงที่ของ Raft/WAL indexing) + ~14 MB ต่อ peer ส่วน crypto material (cert/key
ของทั้ง 3 องค์กร + orderer): 780 KB

### ต้นทุนต่อรอบ (การประสานผ่าน blockchain เทียบกับ ML จริง)

| Operation | Latency เฉลี่ย | ครอบคลุมอะไรบ้าง |
|---|---|---|
| เทรน local (โมเดลเล่นๆ 3 epochs) | **28–70 ms** | คำนวณ `sklearn` ล้วน ไม่เกี่ยวกับ chain |
| `SubmitUpdate` invoke | **2.41 s** (ต่ำสุด 2.36, สูงสุด 2.54) | proposal, endorsement 3-of-3 peer, ordering, commit, รอ event |
| `GetRoundUpdates` query | **0.32 s** | อ่านจาก peer เดียว ไม่ผ่าน ordering |
| `RecordAggregation` invoke | **2.39 s** | เส้นทางเขียนเดียวกับ SubmitUpdate |
| Ledger โตขึ้น | **≈ 30.4 KB/รอบ** | chaincode เขียน 4 ครั้ง/รอบ (submit 3 + aggregation 1) ตกราว ~7.6 KB/tx |

ต่อรอบ (3 โหนด): ≈ 3×2.41 s (submits) + 3×0.32 s (queries) + 1×2.39 s
(aggregation) ≈ **10.6 วินาที ของ latency ที่เกิดจากการโต้ตอบกับ blockchain**
เทียบกับ **< 0.2 วินาที** ของการเทรนโมเดลจริง สำหรับโมเดลเล่นๆ ขนาดนี้
overhead ของ consensus ครองเวลา wall-clock ราว 50–70 เท่า

**ทำไมอัตราส่วนนี้สำคัญกว่าที่เห็น**: latency เขียน ~2.4 วินาที ถูกจำกัดด้วย
รอบ round-trip ของ consensus/endorsement (simulate proposal บน 3 peer +
Raft ordering + commit + แจ้ง event) ไม่ได้ถูกจำกัดด้วยขนาด payload — เพราะสิ่งที่
ขึ้น chain มีแค่ hash 64 ไบต์ ไม่ใช่ตัว weights ดังนั้นพื้นค่านี้แทบคงที่ไม่ว่า
โมเดลจะใหญ่แค่ไหน SL รอบจริงที่เทรนโมเดลใหญ่เป็นนาที จะทำให้ overhead ของ
blockchain เล็กจนแทบไม่มีนัยสำคัญ ขณะที่โมเดลเล่นๆ/เร็ว (แบบตัวนี้ หรือ
federated learning บนข้อมูล tabular เล็กๆ) ทำให้ภาษี consensus ~10 วินาที/รอบ
กลายเป็นต้นทุนหลัก

### สรุป

- เครือข่าย consortium 3 องค์กรตอน idle: **~650 MB RAM**, **~2.5 GB disk** (images), CPU ตอน idle แทบไม่มีนัยสำคัญ
- SL แต่ละรอบเพิ่ม latency การประสานผ่าน blockchain **~10.6 วินาที** และ ledger โต **~30 KB** โดยไม่ขึ้นกับขนาดโมเดล (เพราะ weights อยู่ off-chain)
- policy endorsement 3-of-3 + majority commit ถูกบังคับใช้และตรวจสอบแล้ว (`querycommitted` แสดงว่าทั้งสามองค์กร approve) ยืนยันว่าดีไซน์แบบ consortium/permissioned ให้หลักประกันความเชื่อใจแบบ N-of-M ตามที่ตั้งใจไว้จริง ไม่ใช่แค่บนกระดาษ

## วิธีทำซ้ำ

ต้องเปิด Docker Desktop ไว้ **รันทุกอย่างจาก path ที่ไม่มีช่องว่าง** —
เครื่องมือของ `fabric-samples` เองพังเมื่อ path มีช่องว่าง (ดูข้อควรระวัง
ด้านล่าง) โฟลเดอร์ `poc/` ของ repo นี้อยู่ใต้ path ที่มีช่องว่าง ตอนรันจริงจึง
ใช้สำเนา mirror ที่ `D:\swarm-poc` (fabric-samples + copy ของ `chaincode/`,
`scripts/`, `sl-client/`)

```bash
# one-time: fetch Fabric binaries/images/samples into <space-free-dir>
curl -sSL https://raw.githubusercontent.com/hyperledger/fabric/main/scripts/install-fabric.sh | bash -s -- docker samples binary

# bring up the 3-org consortium + deploy sl-ledger chaincode
bash scripts/01-network-up.sh

# run N rounds (rounds, local_epochs, start_round)
sl-client/.venv/Scripts/python sl-client/orchestrate.py 5 3 1

# resource sampling (run in background during the above)
sl-client/.venv/Scripts/python scripts/monitor.py 2 results/docker_stats.csv
```

ปิดเครือข่าย: `cd fabric-samples/test-network && ./network.sh down`

## ข้อควรระวังบน Windows/Git Bash ที่แก้ไปแล้ว

- **path ที่มีช่องว่างทำให้เครื่องมือ bash ของ `fabric-samples` พัง** (มีการใช้
  `$VAR` เป็น path โดยไม่ครอบ quote อยู่หลายจุดใน
  `network.sh`/`envVar.sh`/ฯลฯ) — ให้รันจาก path ที่ไม่มีช่องว่าง
- **Git Bash/MSYS แปลง path ของ bind mount ระหว่าง peer กับ Docker socket ผิด**
  (`${DOCKER_SOCK}:/host/var/run/docker.sock`) ทำให้เกิด `mkdir "C:\Program
  Files\Git\var": Access is denied` แก้โดยครอบเฉพาะ `docker` และ
  `docker-compose` ด้วย `MSYS_NO_PATHCONV=1` (ถ้าตั้ง env var แบบเหมารวมจะไป
  ทำให้ `fabric-ca-client`/`configtxgen` พังแทน เพราะสองตัวนั้นต้องการการแปลง
  path ตามปกติ) — ดู `scripts/01-network-up.sh`
- Docker Desktop บน Windows resolve `docker compose` ไปที่ shim
  `docker-compose.exe` แบบ standalone ไม่ใช่ plugin `docker compose` — ต้องครอบ
  ทั้งสองตัว ไม่ใช่แค่ตัวเดียว
- `setGlobals`/`parsePeerConnectionParameters` ใน `envVar.sh` อ้างถึง
  `$OVERRIDE_ORG`/`$VERBOSE` โดยไม่ตั้งค่า default ไว้ ภายใต้ `set -u` จะกลายเป็น
  unbound-variable error — ให้ export ทั้งสองตัว (ค่าว่าง/`false`) ก่อน source
- `installChaincode`/`approveForMyOrg` ใน `ccutils.sh` พึ่งพา `grep` ที่ตั้งใจให้
  คืนค่าไม่เป็นศูนย์ (เพื่อตรวจว่า "ยังไม่ได้ install") — อย่ารันใต้ `set -e`
  ไม่งั้น script จะหยุดตอนเจอเคส not-found ที่คาดไว้อยู่แล้ว
