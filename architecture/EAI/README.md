# Multimodal Swarm Learning ตรวจจับ DDoS บน IoT — ทำซ้ำบน Hyperledger Fabric

ทำซ้ำงานของ **Nguyen-Khanh, Pham-Nguyen-Hai, Van-Thien, Le-Trung, "A Multimodal Swarm Learning Approach
for DDoS Detection in Internet of Things Infrastructure", *EAI Endorsed Transactions on Industrial Networks
and Intelligent Systems* 13(1), 2026** ([doi:10.4108/eetinis.131.9961](https://doi.org/10.4108/eetinis.131.9961))
ทั้งชุดข้อมูล การแบ่ง host โมเดล hyperparameter และวิธีรวมโมเดล โดย Swarm Learning (SL) รันบนเครือข่าย
Hyperledger Fabric จริงของโปรเจกต์ (`poc/sl-fabric`) แทน HPE Swarm Learning ที่เปเปอร์ใช้

ผลอยู่ที่ [`results/REPORT.md`](results/REPORT.md)

---

## 1. สิ่งที่ดึงออกมาจากเปเปอร์

### 1.1 วัตถุประสงค์ของงานวิจัย

- ตรวจจับ DDoS บนโครงสร้าง IoT ด้วย deep learning แบบ **multimodal** ที่ดูทราฟฟิกสองมุมพร้อมกัน:
  ข้อมูลระดับ **packet** และข้อมูลระดับ **flow** (งานเดิมส่วนใหญ่ดูมุมเดียว ทำให้ generalize ได้ไม่ดี)
- ฝึกโมเดลแบบ **กระจายศูนย์ไม่มี server กลาง** ด้วย Swarm Learning ที่ใช้ blockchain ยืนยันตัวตนผู้เข้าร่วมและประสานงาน
  แก้ปัญหา privacy ของ CL (ต้องส่งข้อมูลดิบ) และ single point of failure ของ FL (มี server กลาง)
- Contributions (Section 1): (1) โครงสร้างพื้นฐาน edge computing รองรับ SL (2) โมเดล multimodal สำหรับจำแนก DDoS
  (3) ประเมินโมเดลแบบกระจายเทียบกับแบบรวมศูนย์ รวมถึงความทนต่อข้อมูล non-IID และวิธี merge ทั้งสามแบบ
- ข้อสรุปของเปเปอร์: multimodal บน SL ได้ผลใกล้ CL (ต่างไม่เกิน 0.5% ใน Scenario 1), merge แบบ **mean** เสถียรที่สุด,
  SL ใช้ bandwidth น้อยกว่า CL มาก (4 × 0.611 MB × 18 รอบ ≈ 44 MB ใน Scenario 3)

### 1.2 สถาปัตยกรรม (Section 3.1, Fig. 2, Algorithm 1)

```
edge node k  ┌──────────────────────────────┐
             │ ML (local data, local train) │──insight──┐
             │ SL node  ◀──▶ SN node         │──state────┤   SN = Swarm Network (blockchain layer)
             └──────────────────────────────┘           │   ยืนยันว่าผู้เข้าร่วมได้รับอนุญาต
                         ▲                              │   + smart contract ควบคุมการฝึก
       ทุกรอบ: เลือก leader ─▶ leader รวม weights (f) ─▶ ส่งโมเดลรวมกลับทุก node
```

- ข้อมูลดิบอยู่ที่ edge ตลอด ส่งออกเฉพาะ weights
- SwarmCallback (Keras/PyTorch) ซิงก์ทุก **syncFrequency = 1024 batch** (Table 12)
- **Algorithm 1**: on_train_begin → ทุก node สร้างโมเดลของตัวเอง, เลือก leader, leader รวมแล้วแจกคืน
  → วน: ฝึก local F batch → เลือก leader → รวมด้วย f → แจกคืน จนครบ epoch
- leader ล้มจะเลือกใหม่ (leader เดิมกลับมาเป็น node ปกติ)
- merge ได้ 3 แบบ (Table 2): **mean** (weighted FedAvg), **coordmedian** (median รายพิกัด),
  **geomedian** (geometric median ด้วย Weiszfeld)

### 1.3 ชุดข้อมูล (Section 4.1, Tables 5–11)

| ชุด | ที่ใช้ | จำนวน (Table 7) |
|---|---|---|
| Edge-IIoTset (Ferrag et al. 2022) | DDoS HTTP, TCP SYN, ICMP, UDP Flood + benign | 48,544 / 50,062 / 67,939 / 121,567 |
| CICIoMT2024 (Dadkhah et al. 2024) | MQTT DDoS Publish Flood, MQTT DDoS Connect Flood + benign | 65,835 / 147,166 |
| benign จากทั้งสองชุด | | 480,213 |
| รวม | train / val / test = 794,875 / 88,319 / 98,132 | 981,326 |

- **packet modality**: field จาก Tshark ตัด 15 คอลัมน์ (frame.time, ip.src_host, … icmp.transmit_timestamp),
  ลบแถวซ้ำ/ค่าหาย, dummy encoding, z-score
- **flow modality**: LUCID — flow = 5-tuple, window **t = 10 s**, ต่อ fragment ใช้ **n = 10 packet × 11 feature**
  (Time, Packet Length, Highest Layer, IP Flags, Protocols, TCP Length, TCP Ack, TCP Flags, TCP Window Size,
  UDP Length, ICMP Type), padding ศูนย์, เวลาเป็น offset จาก packet แรก
- **ป้าย**: binary (0 benign, 1 attack)
- **Scenarios** (non-IID: หนึ่ง host ต่อ attack type):

| Scenario | hosts | เนื้อหา (Tables 9–11) |
|---|---|---|
| 1 | 3 | HTTP+ICMP+benign · TCP SYN(+benign) · UDP(+benign) — Edge-IIoTset ล้วน |
| 2 | 3 | HTTP+ICMP+benign · TCP SYN+UDP+benign · MQTT Publish+Connect+benign |
| 3 | 5 | HTTP+ICMP+benign · TCP SYN+benign · UDP+benign · MQTT Publish+benign · MQTT Connect+benign |

### 1.4 โมเดล (Section 3.2, Fig. 3, Tables 3, 4, 12)

| branch | ชั้น (Keras output shape, params) |
|---|---|
| flow (Table 3, LUCID) | Conv2D (8,1,64) 2,176 → ReLU → GlobalMaxPooling2D (64) → Flatten → Dense(1) 65 |
| packet (Table 4) | Conv1D (48,74) 444 → Conv1D (44,50) 18,550 → GlobalAveragePooling1D (50) → Dense 60 (3,060) → Dropout → Dense 60 (3,660) → Dropout → Dense(1) 61 = **25,775** |
| multimodal (Fig. 3) | flow features ‖ packet features → **Concatenate** (late fusion) → Dense → sigmoid |

Hyperparameters (Table 12): lr 0.001, batch 128, 10 epochs, Adam, binary cross-entropy, syncFrequency 1024, 3–5 nodes

### 1.5 ผลในเปเปอร์ (ใช้เทียบใน REPORT.md)

- Scenario 1: CL packet/multimodal 100%, flow 96.85%; SL multimodal mean 99.96 · coord 99.52 · geo 99.50
- Scenario 2 (27 รอบ): SL multimodal mean 98.62 · coord 83.26 · geo 83.91
- Scenario 3 (18 รอบ): SL packet mean 97.17, flow mean 70.70, multimodal mean 92.62 · coord 89.20 · geo 89.69
- Table 16 test loss (mean/coord/geo): S1 0.0039/0.0181/0.0177 · S2 0.0352/0.7622/0.7655 · S3 0.1968/0.5151/0.4760

## 2. สิ่งที่จำลอง: เปเปอร์ → โค้ด

| หัวข้อ | ในเปเปอร์ | ในโค้ด |
|---|---|---|
| ข้อมูล Edge-IIoTset | DNN-EdgeIIoT ที่ตัด 15 คอลัมน์ + dropna + dedup (ได้ Table 7 ตรงทุกตัว) | `data.edge_rows()` |
| ข้อมูล CICIoMT2024 | Tshark บน capture MQTT DDoS + benign | `data.ciciomt_rows()` (Tshark field ชุดเดียวกับ Edge-IIoTset) |
| packet features | 46 คอลัมน์, dummy 7 คอลัมน์ข้อความ, z-score | `data.FEATURES`, `CATEGORICAL`, `data.load()` |
| flow features | LUCID t = 10 s, n = 10, 11 feature, min-max ด้วยช่วงคงที่ของ LUCID | `data.lucid_packets()`, `data.fragments()`, `LUCID_RANGE` |
| การจับคู่สอง modality | ทุก sample = packet หนึ่งตัว + fragment ของ flow ที่ packet นั้นอยู่ | `data.edge_keys()`, `match_edge()`, `prepare()` |
| hosts / scenarios | Tables 9–11 (benign ต่อ host = ยอดรวม host − attack) | `data.UNITS`, `SCENARIOS` |
| split | test 10% ของ host, val 10% ของที่เหลือ | `data._split()` |
| โมเดล | Tables 3, 4, Fig. 3 | `models.py` (ทดสอบจำนวน parameter ตรง Table 3/4) |
| SL loop | Algorithm 1 + SwarmCallback | `swarm.swarm()`, `swarm.Node` |
| merge | mean / coordmedian / geomedian | `swarm.merge()`, `swarm.weiszfeld()` |
| blockchain | Swarm Network + smart contract | `swarm.FabricSwarm` บน chaincode `sl-ledger` ของ `poc/sl-fabric` |
| CL baseline | ฝึกบนข้อมูลรวมทุก host | `swarm.central()` |
| ตัวชี้วัด | accuracy, precision, recall, F1 (attack = positive), confusion matrix, test loss | `swarm.evaluate()` |

**จำนวนรอบ SL** ไม่ได้ตั้งเอง ได้จาก syncFrequency กับขนาดข้อมูลของ node ที่ฝึกนานที่สุด:
`1 + ceil(max_k 10·ceil(n_k/128) / 1024)` → Scenario 2 = **27**, Scenario 3 = **18** ตรงกับที่เปเปอร์รายงาน
(ทดสอบไว้ใน `test_eai.py`) · Scenario 1 = 17

## 3. Swarm Learning บน Fabric

```
รอบ r   ทุก node:  ฝึก ≤1024 batch ต่อจากที่ค้าง (นับข้ามรอบ/epoch, Adam ของตัวเองคงอยู่ทั้ง run)
        ทุก node:  submit sha256(weights) เข้า ledger  (เซ็นด้วย cert ของ OrgK ตัวเอง, ทำพร้อมกัน)
        chaincode: leader = sha256("round-N:members") mod N   — ใครก็คำนวณซ้ำได้
        leader:    รับ weights แบบ peer-to-peer, รับเฉพาะที่ hash ตรงกับ ledger, merge (mean/coord/geo)
        leader:    RecordAggregation(hash ของโมเดลรวม)  — chaincode รับเฉพาะ leader ของรอบนั้นและต้องครบ quorum
        ทุก node:  ตรวจโมเดลที่ได้กับ hash บน ledger ก่อนใช้ฝึกต่อ
```

| channel | organizations | quorum | ใช้กับ |
|---|---|---|---|
| `swarm-eai1-{packet,flow,multimodal}` | Org1–Org3 | 2 | Scenario 1 |
| `swarm-eai2-{packet,flow,multimodal}` | Org1–Org3 | 2 | Scenario 2 |
| `swarm-eai3-{packet,flow,multimodal}` | Org1–Org5 | 3 | Scenario 3 |

host k ของ scenario = `Org{k+1}MSP` · merge ทั้งสามแบบของโมเดลเดียวกันใช้ channel เดียวกัน แต่ละ run เริ่มที่รอบว่างถัดไปบน chain

พฤติกรรม SwarmCallback ที่ทำตาม (ค่า default ของ HPE เพราะเปเปอร์ไม่ได้ตั้ง):

- **nodeWeightage = 1 ทุก node** → mean เป็นค่าเฉลี่ยเท่ากันทุก node ไม่ถ่วงด้วยจำนวนข้อมูล
- **checkinModelOnTrainEnd = "snapshot"** → node ที่ครบ 10 epoch ก่อน ส่ง weights ตอนที่หยุดเข้ารวมต่อทุกรอบ
  และไม่รับโมเดลรวมอีก swarm ทำงานจน node ที่มี batch มากที่สุดครบ
- **minPeers = ทุก node** (ไม่มี node หลุดในการทดลองของเปเปอร์)
- รอบ 0 (on_train_begin) รวมโมเดลเริ่มต้นที่แต่ละ node สุ่มเอง

## 4. วิธีรัน

ต้องมี Docker Desktop + เครือข่าย `poc/sl-fabric` ที่ deploy แล้ว ([`poc/sl-fabric/README.md`](../../poc/sl-fabric/README.md)),
Wireshark (tshark 4.x) และ Python ที่มี PyTorch (ใช้ venv เดียวกับ `architecture/centric` ได้)

```bash
cd architecture/EAI
PY=../centric/.venv/Scripts/python.exe          # หรือ venv ที่มี torch numpy pandas pyarrow matplotlib

# 1. ข้อมูล: Edge-IIoTset (1.7 GB) และ CICIoMT2024 (11.0 GB) จาก Kaggle ไม่ต้องล็อกอิน แล้วแตกเฉพาะ capture ที่ใช้
$PY data.py download
# 2. Tshark + LUCID + จับคู่ + แบ่ง host  (ครั้งแรก ~25 นาที, ผลอยู่ data/processed/)
$PY data.py prepare
# 3. channel บน Fabric: บรรทัด eai1/eai2/eai3 อยู่ใน poc/sl-fabric/network/swarms.conf แล้ว
(cd ../../poc/sl-fabric/network && ./network.sh deploy)     # ถ้าค้างกลางทาง รันซ้ำได้
# 4. ทดลองทั้งหมด (CL + SL 3 merge × 3 โมเดล × 3 scenario, ~1 ชม. บน RTX 3060 Laptop) แล้วสร้างรายงาน
$PY run.py
$PY report.py
# ทดสอบ (ไม่ต้องมี Fabric หรือข้อมูล)
$PY test_eai.py
```

ตัวเลือก: `run.py --scenarios 3 --models multimodal --merges mean`, `--no-cl`, `--no-sl`, `--force`
· เปลี่ยนค่า default ของ SwarmCallback: `--weighting samples` (nodeWeightage = จำนวนแถว train ที่ประกาศบน ledger),
`--on-train-end inactive` (node ที่จบแล้วเลิกส่ง weights) ผลไปที่ `sl-<model>-<merge>-<variant>.json`
run ที่มีผลแล้วจะข้าม จึงรันต่อหลังหยุดกลางคันได้ · log อยู่ `results/logs/`

**ความเร็ว** โมเดลเล็กมาก (2k–36k parameters) เวลาส่วนใหญ่ของ PyTorch แบบปกติหมดไปกับการสั่ง kernel ทีละตัว
บน GPU จึงจับ 1 training step (gather batch, forward, backward, Adam) เป็น CUDA graph แล้วเล่นซ้ำ (`swarm.Node._capture`)
เร็วขึ้น 3–16 เท่า (multimodal ~1.3 ms/step) ทดสอบแล้วว่า flow network (ไม่มี dropout) ได้ weights เท่าแบบปกติทุกบิต
**อย่ารันหลาย process พร้อมกันบน GPU เดียว**: ลองแล้ว ช้าลง ~10 เท่าและ GPU memory 6 GB ไม่พอ

## 5. ส่วนที่ทำเหมือนเปเปอร์ไม่ได้ และสิ่งที่ใช้แทน

1. **การจับคู่ packet กับ flow** เปเปอร์ไม่ได้บอกว่าแต่ละ sample ของสอง branch จับคู่กันอย่างไร ที่นี่ให้ sample หนึ่ง =
   packet หนึ่งตัว คู่กับ LUCID fragment (flow 5-tuple ใน window 10 วินาที) ที่ packet นั้นอยู่ ป้ายเป็นของ packet
2. **หาแถวของ DNN-EdgeIIoT ใน capture** CSV ทำ frame.time หายวันที่ (เหลือ `"2021 HH:MM:SS.fffffffff"` ตามเวลา UTC+1)
   จึงจับด้วยเวลาในวันถึงไมโครวินาที + IP ต้นทาง/ปลายทาง · แถว DDoS_UDP ทั้งหมดไม่มี frame.time และคอลัมน์เลื่อนสองแบบ:
   (ก) `frame.time` เก็บ IP ต้นทาง, `tcp.srcport` เก็บ UDP source port → จับด้วย IP + port + `udp.stream`
   (ข) `frame.time` เก็บ IP เหยื่อ, `ip.src_host` เก็บ IP ต้นทาง, `udp.stream` เก็บ source port → จับด้วย IP + port
   แถวที่หาไม่เจอถูกตัด (จำนวนอยู่ใน `data/processed/prepare.json` และ REPORT.md) ที่สำคัญคือ Normal 268,414 แถว
   ไม่มี IPv4 address (`ip.src_host` = 0, เป็น TCP ที่ไม่ใช่ IPv4 และ ARP) LUCID ไม่สร้าง flow ให้ packet ที่ไม่ใช่ IPv4
   จึงไม่มี flow modality — benign ของ Edge-IIoTset จึงสุ่มจาก Normal ที่เป็น IPv4 เท่านั้น
3. **CICIoMT2024 มาจากมิเรอร์บน Kaggle** (`cyberdeeplearning/ciciomt2024`, release เต็ม 11.0 GB) เพราะหน้า UNB ต้องกรอกฟอร์มข้อมูลส่วนตัว
   ใช้ capture `WiFI_and_MQTT/attacks/pcap/{train,test}/` ของ Benign, MQTT-DDoS-Publish_Flood, MQTT-DDoS-Connect_Flood
4. **จำนวนแถวของ CICIoMT2024** เปเปอร์ไม่ได้บอกว่าได้ 65,835 / 147,166 มาจากส่วนไหนของ capture จึงลบแถวซ้ำแล้ว
   **สุ่ม** ให้ได้จำนวนเท่าเปเปอร์ (benign 65,848 + 127,568 ตาม Tables 9–11)
5. **Tshark** ใช้ 4.6.6 · field ชนิด FT_NONE พิมพ์ค่าออกมาไม่ได้: `tcp.connection.{syn,synack,fin,rst}` อ่านจาก `tcp.flags`
   (ความหมายเดียวกัน), `http.tls_port`, `dns.retransmit_request`, `icmp.unused`, `mqtt.msg_decoded_as` เป็นศูนย์
   (เป็นศูนย์ทุกแถวใน Edge-IIoTset ที่ใช้อยู่แล้ว) · ค่าที่ไม่มีในคอลัมน์ข้อความเป็น `"0"` · `mqtt.conack.flags` เขียนแบบ `0x%08x` ตาม Edge-IIoTset
6. **capture ของ CICIoMT2024 ใหญ่เกินหน่วยความจำของ Tshark** (MQTT flood >10 ล้าน packet, TCP connection ละ packet)
   จึงอ่านแบบ reset session ทุก 1 ล้าน packet (`tshark -M`) ทำให้ `udp.stream` และ tcp.seq/ack แบบ relative เริ่มนับใหม่ที่จุด reset
   Edge-IIoTset อ่านเต็มไฟล์
7. **LUCID** ใช้ฟิลด์จาก Tshark แทน pyshark: highest layer = protocol สุดท้ายใน `frame.protocols` (ไม่นับ `ethertype`),
   IP flags เป็นค่า 16 บิตแบบ Wireshark รุ่นที่ LUCID ใช้ (`ip.flags << 13`)
8. **จำนวน packet feature** เปเปอร์ได้ 52 (คำนวณจาก Table 4) ที่นี่ขึ้นกับ category ที่เจอในข้อมูลของแต่ละ scenario
   (ดู REPORT.md) โมเดล packet มี parameter 25,775 เท่ากันไม่ว่ากี่ feature เพราะมี global pooling
9. **ค่าที่เปเปอร์ไม่ได้ระบุ** Dropout 0.2 · ชั้นหลัง concatenate = Dense 64 + ReLU · activation ของ conv/dense = ReLU ·
   Weiszfeld หยุดเมื่อขยับน้อยกว่า 1e-7 (relative) · split แบ่งตามสัดส่วนชนิดทราฟฟิกใน host · seed 42
10. **z-score** fit บน train ของทุก host ใน scenario (เปเปอร์ encode/scale ก่อนแบ่ง host) — ใน SL จริง node จะแลกกันแค่ (n, mean, var)
11. **PyTorch แทน Keras** init แบบ Keras (Glorot uniform, bias ศูนย์), Adam ε = 1e-7 แบบ Keras
12. **กราฟ Scenario 1 เป็นต่อรอบ** (เปเปอร์ Fig. 6–9 เป็นต่อ epoch) ค่า validation = โมเดลรวมของรอบนั้นวัดบน val ของแต่ละ host แล้วเฉลี่ย

## 6. ผลโดยสรุป

ตารางเต็ม กราฟ และบัญชีบน Fabric อยู่ใน [`results/REPORT.md`](results/REPORT.md) (Accuracy %, ในวงเล็บคือเปเปอร์)

| | CL multimodal | SL multimodal mean | coordmedian | geomedian | SL flow mean | SL packet mean |
|---|---|---|---|---|---|---|
| Scenario 1 | 100.00 (100) | 99.93 (99.96) | 99.83 (99.52) | 100.00 (99.50) | 94.30 (96.59) | 100.00 (100) |
| Scenario 2 | 99.85 (100) | 77.99 (98.62) | 78.32 (83.26) | 78.29 (83.91) | 75.40 (—) | 78.33 (—) |
| Scenario 3 | 99.85 (100) | 74.11 (92.62) | 74.59 (89.20) | 78.51 (89.69) | 73.17 (70.70) | 78.77 (97.17) |

**ที่ตรงกับเปเปอร์**

- Scenario 1 (Edge-IIoTset ล้วน): SL multimodal ห่าง CL ไม่ถึง 0.2% และ packet ได้ 100% ทุกแบบ เหมือน Table 13
- multimodal ดีกว่าหรือเท่ากับ branch เดี่ยวทั้งใน CL และ SL ของ Scenario 1 · SL flow ของ Scenario 3 ได้ 72–73% ใกล้ Table 15 (70.7–75.0%)
- จำนวนรอบ 27 และ 18 ตรงกับเปเปอร์ ทุกรอบ hash ตรงกับ ledger (17/17, 27/27, 18/18) ไม่มี update ถูกปฏิเสธ leader หมุนครบทุก org
- loss ของ mean ต่ำที่สุดใน Scenario 2 (1.01 เทียบกับ 2.32 และ 3.99) และ mean ผันผวนมากกว่าแต่ฟื้นตัวเร็ว เหมือน Figs. 11–12

**ที่ไม่ตรง: Scenario 2 และ 3 ต่ำกว่าเปเปอร์มาก** CL บนข้อมูลชุดเดียวกันได้ 99.85% ข้อมูลจึงแยกได้ ปัญหาอยู่ที่การรวมโมเดลข้าม host:
host ที่ถือ MQTT DDoS ของ CICIoMT2024 ฝึก local ได้ ~91% ทุกรอบ แต่โมเดลรวมทายทุก packet ของ host นั้นเป็น benign
(val ค้างที่ 0.48 = สัดส่วน benign ของ host นั้น ดู `figures/scenario2-hosts.png`) อัตราตรวจ MQTT DDoS ของ SL เหลือ 0–7%
ส่วนการโจมตีของ Edge-IIoTset ยังตรวจได้ ~100% เหตุที่น่าจะเป็น: benign ของ Edge-IIoTset ที่เป็น IPv4 เกือบทั้งหมดคือทราฟฟิก MQTT
ของเซนเซอร์อุณหภูมิ/ความชื้น host ฝั่ง Edge จึงเรียนว่า "packet MQTT = benign" อย่างมั่นใจ สวนกับ host ฝั่ง CICIoMT ที่ต้องแยก
MQTT flood ออกจาก MQTT ปกติ พอเฉลี่ย weights แบบเท่ากัน (nodeWeightage 1) และ node ที่จบก่อนส่ง snapshot ต่อ ฝั่ง benign จึงชนะ
เปเปอร์ไม่ได้รายงานการตรวจแยกต่อชนิดหรือต่อ host จึงบอกไม่ได้ว่าเขาหลบปัญหานี้ได้ด้วยอะไร (การจับคู่ modality, การดึง packet ของ CICIoMT2024,
หรือรายละเอียดของ HPE SL ที่ไม่ได้ระบุ)

**หาสาเหตุ: เปลี่ยนค่า default ของ SwarmCallback** (multimodal, Scenario 2/3, ทั้ง 3 merge, ตารางเต็มใน REPORT.md
หัวข้อ "หาสาเหตุ") ทดลอง nodeWeightage ตามจำนวนข้อมูล (`weighted`), node ที่จบก่อนเลิกส่ง weights (`inactive`) และทั้งสองอย่าง

| Accuracy % (mean / coordmedian / geomedian) | Scenario 2 | Scenario 3 |
|---|---|---|
| ค่า default (เท่ากัน, snapshot) | 77.99 / 78.32 / 78.29 | 74.11 / 74.59 / 78.51 |
| ถ่วงด้วยจำนวนข้อมูล | 78.73 / 78.32 / 78.32 | 79.11 / 78.55 / 78.47 |
| inactive | 45.38 / 45.50 / 54.60 | 46.07 / 45.51 / 65.40 |
| ถ่วง + inactive | 46.52 / 43.69 / 54.41 | 52.85 / 52.19 / 63.30 |

- **การถ่วงน้ำหนักไม่ใช่สาเหตุ** เพิ่มได้แค่ 0–5 จุด MQTT DDoS ยังตรวจได้ 0–18% · coordmedian ของ Scenario 2 ได้ค่าเดิมทุกบิต
  เพราะเมื่อมี 3 node และไม่มี node ไหนถือข้อมูลเกินครึ่ง weighted median ก็คือ median ธรรมดา
- **inactive กลับด้านปัญหา** รอบท้ายเหลือ node ที่ยังฝึกน้อยกว่า quorum (Scenario 2: 4 รอบ, Scenario 3: 2 รอบ) จึงไม่มีการรวม
  โมเดลสุดท้ายเป็นของ host MQTT เอง ตรวจ MQTT DDoS ได้ ~99% แต่ทาย benign ของ Edge-IIoTset ถูกแค่ ~40% และลืม ICMP/UDP flood
- **ไม่มีโมเดลรวมไหนรับใช้ทุก host พร้อมกัน** ใน 24 run × ทุกรอบที่ merge ค่า val ของ host ที่แย่ที่สุดสูงสุดแค่ 61.7%
  ฝั่งไหนมีน้ำหนักในการรวมมากกว่าฝั่งนั้นชนะ: weighted median ของสอง node (Scenario 2 รอบ 16–22 แบบถ่วง + inactive)
  เลือกโมเดลของ host MQTT ทั้งก้อน host MQTT ได้ 99.3% แต่ host Edge เหลือ 14–18%
- ข้อสรุป: ช่องว่างไม่ได้มาจาก nodeWeightage หรือ checkinModelOnTrainEnd แต่มาจากป้ายที่ขัดกันข้ามชุดข้อมูล — packet MQTT
  ของ Edge-IIoTset เป็น benign ส่วน MQTT flood ของ CICIoMT2024 เป็น attack โมเดลที่ฝึกแยกแต่ละฝั่งจึงใช้ feature ที่ขัดกัน
  การเฉลี่ย weights ไม่ได้หา feature ที่แยกสองชุดออกจากกัน ทั้งที่ CL เห็นข้อมูลรวมแล้วแยกได้ 99.85%

**bandwidth** multimodal มี 35,955 parameters = 0.144 MB (float32) Scenario 3: 4 × 0.144 × 18 = 10.4 MB
(เปเปอร์ 0.611 MB ต่อโมเดล = ขนาดไฟล์ Keras ที่รวม optimizer → 44 MB) · เวลา Fabric ~4.1 วินาทีต่อรอบ

## 7. ข้อจำกัดของฝั่ง SL

- ทุก node อยู่ในโปรเซส Python เดียว การส่ง weights แบบ peer-to-peer จึงเป็นการส่งในหน่วยความจำ
  ส่วน ledger, endorsement, ลายเซ็นของแต่ละ org และการตรวจ hash เป็นของจริง (นับ bytes ไว้)
- local training รันทีละ node เวลาเทรนจึงเป็นผลรวม ไม่ใช่เวลาที่ node ขนานกัน
- ทุก node ซื่อสัตย์ ไม่มีการทดสอบ node โกง (เหมือนเปเปอร์)
- gateway ตัวเดียวถือ identity ของทุก org (ขอบเขตเดโมเดียวกับ `poc/sl-fabric`)

## 8. ไฟล์

| ไฟล์ | หน้าที่ |
|---|---|
| `data.py` | ดาวน์โหลด, แตก capture, Tshark, LUCID fragment, preprocessing ของ Edge-IIoTset, จับคู่, CICIoMT2024, แบ่ง host/split, `load(scenario)` |
| `models.py` | flow / packet / multimodal network, weights เป็นเวกเตอร์ float32, hash |
| `swarm.py` | merge 3 แบบ, Node (SwarmCallback), `FabricSwarm` (ledger), `swarm()` Algorithm 1, `central()` CL |
| `run.py` | รันทุก (scenario, model, CL/SL merge) เขียน `results/runs/scenario<N>/*.json` |
| `report.py` | `results/REPORT.md` + `results/figures/` เทียบ Tables 13–16 |
| `test_eai.py` | จำนวน parameter, shape, ยอด host, จำนวนรอบ 27/18, merge, LUCID, snapshot ของ node ที่จบก่อน |
| `results/runs/scenario<N>/` | ไฟล์ผลของทุก run (อยู่ใน git, เป็นที่มาของ REPORT.md) · `results/logs/` ไม่อยู่ใน git |
| `data/` | ข้อมูลดิบ 18 GB, ตาราง Tshark 7.4 GB, sample ที่เตรียมแล้ว 0.4 GB (ไม่อยู่ใน git) |
