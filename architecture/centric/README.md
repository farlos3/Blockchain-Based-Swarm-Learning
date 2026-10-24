# Dataset-centric federated IDS: FL เทียบ Swarm Learning บน Hyperledger Fabric

ทำซ้ำงานของ **Bilal et al., "Dataset-centric evaluation of federated intrusion detection models
in IoT networks", *Scientific Reports* 16, 2683 (2026)** ([doi:10.1038/s41598-025-32567-w](https://doi.org/10.1038/s41598-025-32567-w))
โดยคงทุกอย่างของเปเปอร์ไว้ — ชุดข้อมูล การแบ่ง client การเตรียมข้อมูล โมเดล algorithm hyperparameter
และตัวชี้วัด — แล้วเปลี่ยน **สถาปัตยกรรมอย่างเดียว** จาก Federated Learning (มี server กลาง)
เป็น Swarm Learning (ไม่มี server, leader หมุนเวียน, ทุกขั้นบันทึกและตรวจบน Hyperledger Fabric)
รันทั้งสองแบบด้วย seed และข้อมูลชุดเดียวกัน แล้วเทียบผล

ข้อมูลเป็น**ฉบับเต็มของทั้งสามชุดเท่านั้น** จากแหล่งที่เปเปอร์ให้ลิงก์ ไม่มีมิเรอร์ย่อหรือทางลัดอื่น
สุ่ม 500,000 แถวต่อ scenario ตามสัดส่วนจริงของแต่ละชุด (ดูเหตุผลในข้อ 4) ผลอยู่ที่ [`results/full-500k/REPORT.md`](results/full-500k/REPORT.md)

---

## 1. สิ่งที่นำมาจากเปเปอร์

| หัวข้อ | ในเปเปอร์ | ในโค้ด |
|---|---|---|
| ชุดข้อมูล | Edge-IIoTset (2022), CIC-IoT2023, TII-SSRC-23 (Table 1, Data availability) | `data.py` · `download()` |
| ป้ายระดับตระกูล | Edge 5 attack + benign · CIC 7 + benign · TII 4 + benign (Tables 5–7) | `EDGE_FAMILY`, `CIC_FAMILY`, `TII_FAMILY` |
| ป้ายร่วม 4 คลาส | Benign, DoS/DDoS, Recon/InfoGather, BruteForce (Section 4.1) | `COMMON_CLASSES`, `*_COMMON` |
| จำนวน client | Edge 6 · CIC 10 · TII 5 · Combined 3 (หนึ่ง client ต่อหนึ่งชุด) (Table 2) | `EDGE`, `CIC`, `TII` |
| ขนาด client · สัดส่วน benign · คลาสที่แต่ละ client มี | Fig. 3 ทุกช่อง (เช่น Edge C2 = Benign, DoS/DDoS, MITM · benign 54%) | `ClientSpec`, `allocate()` |
| seed | global 42 · Edge 1729 · CIC 2023 · TII 1103 (Fig. 3) | `GLOBAL_SEED`, `DatasetSpec.seed` |
| features | ตัวเลขล้วน ไม่ใช้ IP หรือ port (Section 4.3) | `EDGE_NUMERIC`, `_load_tii` |
| normalisation | z-score **ต่อ client** fit บน train split ของ client นั้น ใช้กับ val/test ของ client เดียวกัน | `_split()` |
| validation | stratified 90/10 ของข้อมูล client (Algorithm 3) | `VAL_SHARE` |
| ไม่ rebalance ไม่ augment | Section 4.3 | — |
| LSTM | 2 ชั้น (64 → 32) dropout 0.2 แล้ว dense 2 ชั้น, flow = sequence ยาว 1 | `models.LSTMNet` |
| Transformer | 2 encoder blocks, 4 heads, hidden 64, ตัด feature เป็น 4 ส่วนเป็น pseudo-position + positional encoding, pool แล้ว dense | `models.TransformerNet` |
| loss / optimizer | cross-entropy · Adam β1 0.9 β2 0.999 weight decay 1e-4 | `federation.local_train()` |
| local training | E = 5 epochs, batch 128 (Table 4, Algorithm 3) | `Hyper` |
| learning rate | 0.001 LSTM · 0.0005 Transformer (Table 4) | `models.LEARNING_RATES` |
| FedAvg | Eq. (1) ถ่วงน้ำหนักด้วยจำนวนตัวอย่าง | `federation.aggregate()` |
| FedProx | aggregation แบบ FedAvg + proximal term μ/2‖w − w_global‖² ที่ client, μ = 10⁻³ | `local_train(..., "fedprox")` |
| FedNova | normalise update ด้วย τ_k = E·⌈\|D_k\|/B⌉ (Eq. 3, Algorithm 2) | `aggregate(..., "fednova")` |
| rounds | 50 สำหรับชุดเดี่ยว · 100 สำหรับ combined, ทุก client เข้าทุกรอบ | `run.DEFAULT_ROUNDS` |
| ตัวชี้วัด | accuracy, macro precision/recall/F1, AUC, confusion matrix, FPR/FNR (Section 4.4) | `federation.evaluate()` |
| rounds-to-95% และ data exchanged | Table 9: rounds × clients × params × 4 bytes × 2 | `Hyper.target_accuracy`, `CentralServer.merge()` |
| สามแบบการทดลอง | in-domain · cross-dataset (source scaler ใช้กับ target) · combined | scenarios `edge cic tii` · `*-h` · `combined` |

### ข้อมูลฉบับเต็มที่ใช้

| ชุด | แหล่ง | ไฟล์ | แถว (เปเปอร์) | features (เปเปอร์) |
|---|---|---|---|---|
| Edge-IIoTset | Kaggle `mohamedamineferrag/edgeiiotset-…` (ลิงก์เดียวกับเปเปอร์) | CSV 24 ไฟล์ใน `Attack traffic/` + `Normal traffic/` | 20,939,622 (~21M) | 39 (41) |
| CIC-IoT2023 | ฉบับแรกของ Neto et al. บน Hugging Face `lacg030175/CIC-IoT-2023-neto-full` | `random/train` + `random/test` parquet | 46,686,579 (46.7M) | 46 (46) |
| TII-SSRC-23 | Kaggle `daniaherzalla/tii-ssrc-23` (ลิงก์เดียวกับเปเปอร์) | `csv/data.csv` | 8,656,767 (~8.7M) | 77 (79) |

CIC-IoT2023: เปเปอร์ลิงก์ไปหน้า UNB แต่ `CSV/MERGED_CSV` ที่ UNB แจกตอนนี้เป็นฉบับภายหลัง มี 39 features และ 45,019,234 แถว
(บรรทัดสุดท้ายของ `Merged42`–`Merged52` ถูกตัดกลางบรรทัด 9 แถว) ส่วนตัวเลขในเปเปอร์ (46 features, 46.7M แถว) ตรงกับ
ฉบับแรกที่ Neto et al. ปล่อยเป็น CSV 169 ไฟล์ ซึ่ง UNB ไม่แจกแล้ว จึงใช้สำเนาของฉบับแรกบน Hugging Face ที่จำนวนแถวและ features
ตรงกับเปเปอร์ทุกตัว (เป็นมิเรอร์บุคคลที่สาม ตรวจขนาดไฟล์กับที่ hub ระบุ)

## 2. สิ่งที่เปลี่ยน: FL → SL

```
FL (เปเปอร์, Fig. 1)                         SL (Warnat-Herresthal et al. 2021) บน Fabric
client ─ weights ─▶ server ─ เฉลี่ย          node ─ sha256(weights) ─▶ ledger (เซ็นด้วย cert ของ org ตัวเอง)
client ◀─ global ─ server                    chaincode เลือก leader ของรอบ: sha256("round-N:members") mod N
                                             leader รับ weights แบบ peer-to-peer, รับเฉพาะที่ hash ตรงกับ ledger
                                             leader รวมด้วยสูตรเดียวกัน (n_samples อ่านจาก ledger) แล้วบันทึก hash
                                             ทุก node ตรวจ global model กับ hash บน ledger ก่อนใช้
```

| | FL (`CentralServer`) | SL (`FabricSwarm`) |
|---|---|---|
| ใครรวมโมเดล | server กลาง | node ที่ chaincode เลือกในรอบนั้น หมุนตามสูตรที่ใครก็คำนวณซ้ำได้ |
| ใครตรวจได้ | ไม่มีใคร ต้องเชื่อ server | ทุก org: update และ global model ทุกตัวมี hash บน ledger |
| ใครปิดรอบได้ | server | เฉพาะ leader ของรอบนั้น และต้องมี update ครบ quorum (majority) |
| endorsement | — | majority ของ org ใน swarm นั้น (`SwarmN` profile) |
| traffic ต่อรอบ | 2 · K · P (star) | 2 · (K−1) · P (leader ไม่ต้องส่งของตัวเอง) + transaction เล็กๆ บน ledger |
| สูตร aggregation | `federation.aggregate` | ฟังก์ชันเดียวกัน — รวมตามลำดับ client ใน float64 จึงได้ผลเหมือนกันทุกบิต |

วงรอบอยู่ใน `federation.train()` ครั้งเดียว และรับ coordinator จากข้างนอก (`architectures.py`)
ทั้งสองแบบจึงต่างกันได้เฉพาะที่ coordinator เท่านั้น

**เทรนครั้งเดียว รวมสองทาง** local training ไม่ขึ้นกับว่าใครเป็นคนรวมโมเดล แต่ละรอบจึงเทรน client ครั้งเดียว
แล้วส่ง update ชุดเดียวกันให้ทั้ง server ของ FL และ swarm ของ SL ไปรวมแยกกัน (SL ผ่าน Fabric ครบทุกขั้นเหมือนเดิม)
ทุกรอบตรวจว่าทั้งสองได้ global model เดียวกันทุกบิต ถ้าไม่ตรง run จะหยุดทันที (ผลจริง: ตรงกันทุกบิตทุกคู่ ดู REPORT.md หัวข้อ 1)
วิธีนี้ประหยัดเวลาเทรนลงครึ่งหนึ่งเทียบกับรันแยกกัน ไฟล์ผลยังแยก `fl-*.json` กับ `sl-*.json` และเวลาเทรนในสองไฟล์เป็นตัวเลขเดียวกัน

### เครือข่าย Fabric

ใช้ `poc/sl-fabric` เดิม (chaincode `sl-ledger`, gateway, client `ledger.py` ไม่แก้) แต่ขยายเครือข่ายจาก 5 เป็น **10 organizations**
เพราะ CIC-IoT2023 มี 10 client และโปรเจกต์ยึดหลัก "หนึ่ง swarm node = หนึ่ง organization"

| channel | organizations | quorum | ใช้กับ |
|---|---|---|---|
| `swarm-edge-{lstm,transformer}` | Org1–Org6 | 4 | `edge`, `edge-h` |
| `swarm-cic-{lstm,transformer}` | Org1–Org10 | 6 | `cic`, `cic-h` |
| `swarm-tii-{lstm,transformer}` | Org1–Org5 | 3 | `tii`, `tii-h` |
| `swarm-combined-{lstm,transformer}` | Org1–Org3 | 2 | `combined` |

แต่ละ channel มีเฉพาะ org ของ swarm นั้น majority endorsement จึงหมายถึง majority ของ swarm นั้นเสมอ
client k ของ scenario คือ `Org{k+1}MSP` · algorithm ทั้งสามของ scenario เดียวกันใช้ channel เดียวกัน
แต่ละ run เริ่มที่ round ว่างถัดไปบน chain (`first_ledger_round` ในไฟล์ผล) จึงไม่มี round ซ้ำ

## 3. วิธีรัน

ต้องมี Docker Desktop, Go 1.23+, Fabric 2.5.13 binaries ใน `poc/sl-fabric/bin` (ดู [`poc/sl-fabric/README.md`](../../poc/sl-fabric/README.md))
และ Python 3.13 ใน venv ที่มี PyTorch แบบ CUDA (GPU NVIDIA ใช้เทรน Transformer ถ้าไม่มี GPU ทุกอย่างรันบน CPU ได้แต่ช้ากว่ามาก)

```bash
cd architecture/centric
python -m venv .venv
.venv/Scripts/python.exe -m pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cu128
.venv/Scripts/python.exe -m pip install numpy pandas pyarrow scikit-learn matplotlib psutil

# 1. ข้อมูล: Edge-IIoTset และ TII-SSRC-23 จาก Kaggle, CIC-IoT2023 จาก Hugging Face
#    ไม่ต้องล็อกอิน ตรวจขนาดทุกไฟล์ (~3.4 GB ที่ต้องโหลด)
.venv/Scripts/python.exe data.py download

# 2. เครือข่าย Fabric 10 orgs (Git Bash)
cd ../../poc/sl-fabric/network
./network.sh up          # ~2 นาที
./network.sh deploy      # ถ้าค้างกลางทาง รัน deploy ซ้ำได้ จะทำต่อจากที่ค้าง

# 3. ทดลอง แล้วสร้างรายงาน
cd ../../../architecture/centric
.venv/Scripts/python.exe run.py --flush-denormal --workers 4   # ~10-11 ชม. บน RTX 3060 Laptop + i5-12500H
.venv/Scripts/python.exe report.py results/full-500k
```

### เลือกโมเดล

โมเดลที่ใช้ได้กำหนดสองที่ ตอนนี้ตั้งไว้เฉพาะ LSTM กับ Transformer ตามเปเปอร์:

| ที่ | กำหนดอะไร |
|---|---|
| `models.py` · `ARCHITECTURES`, `LEARNING_RATES` | โมเดลที่โค้ดเทรนได้ (`run.py --models` เลือกจากรายการนี้) |
| `poc/sl-fabric/network/swarms.conf` | dataset ไหนมีช่องบน Fabric สำหรับโมเดลไหน (ฝั่ง SL ต้องมีช่อง) |

- **เลือกบางโมเดลจากที่มี:** `run.py --models lstm` หรือ `--models transformer` (ค่าเริ่มต้น: ทุกโมเดลใน `models.py`)
- **เพิ่มโมเดลใหม่:** เขียน class ใน `models.py` แล้วใส่ใน `ARCHITECTURES` กับ `LEARNING_RATES`, เติมชื่อโมเดลต่อท้ายบรรทัดของ
  dataset ใน `swarms.conf`, รัน `./network.sh deploy` (สร้างช่องใหม่บนเครือข่ายที่รันอยู่ แต่จะ restart gateway จึงห้ามรันระหว่างเทรน)
- `run.py` ตรวจก่อนเริ่มว่าทุก (dataset, model) ที่จะรันฝั่ง SL มีช่องบน Fabric ถ้าขาดจะหยุดพร้อมบอกว่าต้องเพิ่มบรรทัดไหน

ครั้งแรกที่อ่านแต่ละชุด โค้ดจะอ่านไฟล์เต็มหนึ่งรอบแล้วเก็บ pool ไว้ที่ `data/raw/pools/` (Edge ~8 นาที, CIC ~4 นาที, TII ~3 นาที)

`run.py` แบ่งงานเป็น lane ตาม (dataset, model) — run ใน lane เดียวกันรันต่อกันเพราะใช้ channel เดียวกัน lane ต่างกันรันขนาน
lane ของ Transformer ไป GPU (`--gpu-models`, `--gpu-workers`) lane ของ LSTM ใช้ CPU (`--workers`)
ความคืบหน้าอยู่ใน `results/<ชุด>/logs/` run ที่มีผลแล้วจะข้าม จึงรันต่อหลังหยุดกลางคันได้ (`--force` เพื่อรันใหม่)
· ตัวเลือกอื่น: `--scenarios`, `--models`, `--algorithms`, `--arch`, `--rows`, `--rounds`

ทดลองสั้นๆ: `.venv/Scripts/python.exe run.py --scenarios edge --models lstm --algorithms fedavg --rows 20000 --rounds 3`
(ผลไปอยู่ `results/full-20k/`)

### ความเร็ว

โมเดลทั้งสองเล็กมาก (LSTM 41k, Transformer ~68k parameters) batch 128 ใช้เวลา GPU ระดับไมโครวินาที
แต่การสั่ง kernel หลายร้อยตัวทีละตัวจาก Python ใช้หลายมิลลิวินาที บน GPU จึงจับ 1 optimizer step เป็น CUDA graph
แล้วเล่นซ้ำ (`federation.CudaStep`) เร็วขึ้น ~30 เท่า (LSTM ~1,900, Transformer ~600 steps/s บน RTX 3060 Laptop)
ต่อ step ได้ผลเท่าแบบปกติในระดับ rounding ของ float และรันซ้ำได้ค่าเดิมทุกบิต (`torch.use_deterministic_algorithms`)
GPU เต็มตั้งแต่โปรเซสเดียว lane ของ LSTM จึงใช้ CPU คู่ขนานไป

## 4. ส่วนที่ทำเหมือนเปเปอร์ไม่ได้ และสิ่งที่ใช้แทน

ข้อเหล่านี้เปลี่ยนตัวเลขเทียบกับเปเปอร์ได้ แต่ **ใช้เหมือนกันทั้ง FL และ SL** การเทียบ FL กับ SL จึงไม่ได้รับผลกระทบ

1. **ขนาดข้อมูล** เปเปอร์ใช้ 21M / 46M / 8.7M flows · เทรนทุกแถวบนเครื่องนี้ใช้หลายสัปดาห์ จึงสุ่มต่อ scenario 500,000 แถว
   (`--rows`) จากฉบับเต็ม โดยคงสัดส่วนจริงของแต่ละชุด และสัดส่วนของ Fig. 3 ไว้ครบ: ขนาด client ตาม Total Flows,
   benign share ต่อ client, และแต่ละ client มีเฉพาะคลาสตาม Fig. 3
2. **pool ของข้อมูลเต็ม** ไฟล์เต็มใหญ่เกินจะโหลดทั้งก้อน จึงอ่านหนึ่งรอบแล้วเก็บไม่เกิน 1,000,000 แถวต่อตระกูล
   (สุ่มเท่ากันภายในตระกูล ตระกูลที่เล็กกว่านั้นได้ครบทุกแถว) และนับจำนวนแถวจริงของทุกตระกูลไว้
   สัดส่วนที่ใช้แบ่งมาจากการนับนี้ ไม่ใช่จาก pool (`Pool.release_share`) เพราะ class หายาก
   (เช่น MITM ของ Edge 1,229 แถวจาก 20.9M) จะหายไปถ้าสุ่มเท่ากันทั้งไฟล์
3. **TII-SSRC-23 มี benign แค่ 1,301 flow (0.015%)** แต่ Fig. 3 ให้ client ละ 0.85% (ต้องมี ~74,000 flow) ส่วนตัวเลขการโจมตี
   ตรงกับ Fig. 2c ทุกตัว (DoS 7.49M, Info Gathering 1.04M, Mirai 91k, BruteForce 35k) เปเปอร์เองเรียกการแบ่งนี้ว่า
   stratified random จึงใช้สัดส่วนจริงของไฟล์ → benign ราว 15 แถวต่อ client ที่ 500k
4. **class ที่หายากมากจะหายไปเองตามสัดส่วนจริง** client ที่ได้ class ไหนต่ำกว่า 10 แถวจะไม่ได้ class นั้น
   (`MIN_CLASS_ROWS`) ที่ 500k แถว MITM ของ Edge (0.006%) จึงไม่อยู่ใน client ไหนเลย macro-F1 คิดเฉพาะ class
   ที่ปรากฏใน label หรือ prediction (ค่าเริ่มต้นของ sklearn) class ที่ไม่มีเลยจึงไม่ถูกนับเป็นศูนย์
5. **CIC-IoT2023 มาจากมิเรอร์ ไม่ใช่หน้า UNB โดยตรง** (ดูหัวข้อ "ข้อมูลฉบับเต็มที่ใช้") เพราะฉบับที่ UNB แจกตอนนี้มี 39 features
   ไม่ตรงกับ 46 ที่เปเปอร์ใช้
6. **Edge-IIoTset ฉบับดิบ** เก็บบาง field เป็นเลขฐานสิบหก (`tcp.flags`, `tcp.checksum`, `icmp.checksum`, `mqtt.conflags`,
   `mqtt.hdrflags`) ฉบับ ML ที่ Ferrag et al. เตรียมให้แปลงไว้แล้ว ส่วนฉบับดิบต้องแปลงเอง (`_edge_number`)
   features = field ตัวเลข 39 ตัว ไม่รวม port 3 ตัว และ field ข้อความ (host, URI, payload, MQTT topic, `dns.qry.name`)
   เปเปอร์บอก 41
7. **แบ่ง client ตามกลุ่มอุปกรณ์ไม่ได้** CSV สาธารณะไม่มีคอลัมน์อุปกรณ์ (ตรวจไว้แล้วใน `poc/Finding Dataset/cut-off.ipynb`)
   จึงใช้สิ่งที่ Fig. 3 ระบุ (คลาสต่อ client, ขนาด, benign share) เป็นตัวกำหนดการแบ่ง
8. **Table 3 (40 features ร่วม) สร้างจากข้อมูลสาธารณะไม่ได้** ชื่อใน Table 3 เป็น feature ของ CICFlowMeter ซึ่งมีเฉพาะใน TII-SSRC-23
   schema ร่วมที่ใช้คือส่วนที่ทั้งสามชุดวัดเรื่องเดียวกันได้จริง 10 ตัว: สัดส่วน packet ที่มี flag FIN SYN RST PSH ACK ECE CWR
   และสัดส่วนที่เป็น TCP UDP ICMP (`HARMONIZED`) — packet เดี่ยวได้ 0/1, window หรือ flow ได้สัดส่วน
9. **FedNova** Eq. (3) ในเปเปอร์ไม่มี τ_eff = Σ(n_k/n)τ_k ที่ FedNova ต้นฉบับ (Wang et al. 2020) คูณกลับ
   ถ้าทำตาม Eq. (3) ตรงตัว แต่ละรอบจะขยับโมเดลแค่ราวหนึ่ง local step และจะไม่ "เท่ากับ FedAvg เมื่อทุก client ทำงานเท่ากัน"
   อย่างที่เปเปอร์เขียน เปเปอร์บอกว่าใช้โค้ดของผู้แต่ง FedNova จึงทำตามโค้ดนั้น (มี τ_eff)
10. **ค่าที่เปเปอร์ไม่ได้ระบุ** test split 20% ต่อ client (stratified) · feed-forward ของ Transformer 128 (2 × hidden)
    · optimizer ใหม่ทุกรอบ · source scaler ของ cross-dataset = รวมสถิติ (n, mean, var) ของทุก client ใน source
    (ไม่ต้องเห็นข้อมูลดิบ) · ขนาด client ของ combined ตามสัดส่วน Table 1 (21 : 46 : 8.7)
11. **ไม่ลบแถวซ้ำ** เปเปอร์ไม่ได้ระบุ · NaN/inf ใน feature แทนด้วย 0 ก่อน z-score
12. **"test split ที่ปรับ benign กับ attack ให้ใกล้กัน"** ในส่วนผลขัดกับ methodology ที่บอกว่าไม่ rebalance — ทำตาม methodology
13. **`--flush-denormal` บน CPU** หลังไม่กี่รอบ unit ของ LSTM จำนวนมากตาย weights ราวหนึ่งในสามลดลงต่ำกว่า 1e-30
    เพราะ weight decay ของ Adam ดึงพารามิเตอร์ที่ไม่ได้ gradient เข้าหาศูนย์ CPU คำนวณค่า denormal ช้ากว่าปกติหลายเท่า
    จึงปัดค่าที่เล็กกว่า 1e-38 เป็นศูนย์ ต่างจากไม่ปัดแค่บิตท้ายๆ ไม่มีผลกับ lane บน GPU
14. **GPU กับ CPU ให้ตัวเลขต่างกันที่บิตท้าย** Transformer เทรนบน GPU, LSTM บน CPU (`device` ในไฟล์ผล) FL กับ SL
    ของ run เดียวกันใช้ update ชุดเดียวกันเสมอ การเทียบ FL กับ SL จึงไม่ได้รับผลกระทบ

## 5. ข้อจำกัดของฝั่ง SL

- **ทุก node อยู่ในโปรเซส Python เดียว** การส่ง weights แบบ peer-to-peer จึงเป็นการส่งในหน่วยความจำ
  ledger, endorsement, ลายเซ็นของแต่ละ org และการตรวจ hash เป็นของจริง แต่การขนส่งโมเดลไม่ใช่ (นับ bytes ไว้ให้เห็นต้นทุน)
- **local training รันทีละ client** เวลาเทรนจึงเป็นผลรวม ไม่ใช่เวลาที่ client ขนานกัน
  ที่ต่างกันจริงระหว่างสองแบบคือ `coordination_seconds` ซึ่งเป็นเวลารอ Fabric ล้วนๆ
- **ทุก node ซื่อสัตย์** การทดลองตามเปเปอร์ไม่มี node ที่โกง SL จึงให้โมเดลเดียวกับ FL ทุกบิต
  สิ่งที่ SL ป้องกันได้แต่ FL ไม่ได้ (server แก้โมเดลเงียบๆ, ส่ง weights ไม่ตรงกับที่ประกาศ, ปิดรอบแทนคนอื่น) อยู่ในกฎของ chaincode
  และการตรวจ hash ซึ่งทดสอบไว้ใน `poc/sl-fabric/README.md` ยังไม่ได้วัดผลต่อความแม่นยำเมื่อมี node โกง
- **gateway ตัวเดียวถือ identity ของทั้ง 10 org** (ขอบเขตเดโมเดียวกับ `poc/sl-fabric`)
- **อ่านทันทีหลัง commit อาจยังไม่เห็น** Fabric ตอบ submit เมื่อ peer ของ org ที่ส่งบันทึก block แล้ว
  แต่ peer ที่ใช้อ่าน (Org1) อาจได้ block นั้นช้ากว่าเล็กน้อย (`round N has no aggregation`) — leader ที่อ่าน update ของรอบ
  และ node ที่ตรวจ aggregation จึงรอจนกว่า block จะมาถึง peer ที่อ่าน (`FabricSwarm._once_visible`)
  แบบเดียวกับที่ node จริงรอ peer ของตัวเอง ไม่มีการส่ง transaction ซ้ำ

## 6. ไฟล์

| ไฟล์ | หน้าที่ |
|---|---|
| `data.py` | ดาวน์โหลด, อ่านไฟล์เต็มเป็น pool, ตระกูลป้าย, schema ร่วม, การแบ่ง client ตาม Fig. 3, split และ scaler ต่อ client |
| `models.py` | LSTM และ Transformer, แปลง weights เป็นเวกเตอร์ float32, hash |
| `federation.py` | LocalTrain (CPU หรือ CUDA graph), FedAvg/FedProx/FedNova, ตัวชี้วัด, วงรอบ Algorithm 1 ที่รับ coordinator |
| `architectures.py` | `CentralServer` (FL) และ `FabricSwarm` (SL บน Fabric ผ่าน `poc/sl-fabric/client/ledger.py`) |
| `run.py` | รัน grid ขนานตาม lane, cross-dataset test, เขียน `results/<ชุด>/runs/<scenario>/<arch>-<model>-<algorithm>.json` |
| `report.py` | `REPORT.md` และรูปใน `figures/` ของชุดการทดลอง |
| `test_centric.py` | ทดสอบสูตร aggregation, การแบ่งตาม Fig. 3, การถ่วงสัดส่วนของ pool และว่าการแบ่งเหมือนเดิมทุกโปรเซส |
| `results/<ชุด>/runs/` | ไฟล์ผลของทุก run (อยู่ใน git, เป็นที่มาของ REPORT.md) |
| `data/` | ไฟล์ดิบและ pool (ไม่อยู่ใน git) |
