# Swarm learning กับ cybersecurity: paper, ชุดข้อมูล และผลลัพธ์

สร้างจาก `paper_review.py` — แก้ข้อมูลในสคริปต์แล้วรันใหม่ อย่าแก้ไฟล์นี้ตรง ๆ

ที่มาของตัวเลขแต่ละแถวบอกไว้ในคอลัมน์ “ที่มา”: ข้อความใน PDF (ตรวจอัตโนมัติ) · ภาพตารางใน PDF (คัดลอกด้วยตา) · อ่านจากกราฟ (ค่าประมาณ ±0.02) · เว็บ/บทคัดย่อ (ยังไม่ได้อ่านฉบับเต็ม) — กลุ่ม A และ B อ่านจาก PDF ฉบับเต็มใน `paper/SL+Cyber/` และ `paper/Cyber+Other/` ทั้งหมด ยกเว้นงาน log (fedlog2024) ที่ไฟล์ที่อัปโหลดเป็นคนละ paper

## 0 · การจัดกลุ่ม

ข้อมูล cyber โดยตรง คือ network traffic, flow, packet capture, system/host log หรือ telemetry ที่มี label การโจมตี ภาพ ข้อความ และสัญญาณวิทยุไม่นับ แม้ paper จะศึกษาเรื่อง security ก็ตาม

- **A. swarm learning + ข้อมูล cyber โดยตรง** (2 ฉบับ) — กลุ่มหลัก: เป็น swarm learning จริง และเทรนบน traffic หรือ log
- **B. ข้อมูล cyber โดยตรง + สถาปัตยกรรมคล้าย SL** (10 ฉบับ) — กลุ่มรอง: IDS บนข้อมูล cyber ที่เทรนแบบ decentralized, ประสานด้วย blockchain หรือ federated แต่ไม่ใช่ SL ตรงตัว
- **X. ภาคผนวก: งาน SL ด้าน security ที่ไม่ได้ใช้ข้อมูล cyber** (9 ฉบับ) — ศึกษาการโจมตี/ป้องกันตัว SL หรือใช้ SL ในงานใกล้เคียง แต่ข้อมูลเป็นภาพ ข้อความ หรือสัญญาณวิทยุ — ไม่นับเป็นงานหลัก เก็บไว้เพราะยังให้แนวคิดด้านสถาปัตยกรรม
- **base. ภาคผนวก: พื้นฐานของ swarm learning** (3 ฉบับ) — paper ในโฟลเดอร์ `paper/` ที่นิยามและวัด SL แต่ใช้ข้อมูลการแพทย์/ทั่วไป

ข้อสังเกตหลัก: เท่าที่ค้นเจอ งาน swarm learning ที่เทรนบนข้อมูล cyber โดยตรงมีแค่ 2 งาน (ADONIS และ IoT-FKGDL-SL) ทั้งคู่ใช้ข้อมูลที่ไม่เปิดเผย และไม่มีงาน SL ใดใช้ชุดข้อมูล IDS มาตรฐาน (N-BaIoT, CIC-IDS, TON_IoT, Edge-IIoTset, CICIoT2023) หรือ system log เลย ชุดเหล่านี้ถูกใช้เฉพาะในงาน FL/DFL/blockchain-FL (กลุ่ม B) ช่องว่างนี้คือจุดที่ sl-fabric เติมได้โดยตรง

## 1 · ภาพรวม: paper × ชุดข้อมูล × ผล

| กลุ่ม | paper | ชุดข้อมูล | ประเภทข้อมูล | ผลเด่น |
|---|---|---|---|---|
| A | adonis2023 | home IoT traffic (เก็บเอง ไม่เปิดเผย) | network traffic ของอุปกรณ์ IoT ในบ้าน (เก็บเอง) | SL ยก accuracy จากเทรนเดี่ยว 67.6% เป็น 89.4% (centralized 92.2%) บน traffic บ้านจริง 49 อุปกรณ์ |
| A | iotfkgdlsl2024 | LW5G-KPI (China Mobile Research Institute) | KPI time series ของเครือข่าย 5G IoT | SL เทียบผู้ร่วมรายเดียว: F1 0.910 → 0.937 ที่ 20 ผู้ร่วม แต่ 10 ผู้ร่วมไม่ช่วย และเกิน 20 precision ตก |
| B | hbfl2022 | NF-BoT-IoT-v2 | network flow (NetFlow) | แต่ละองค์กรเห็นการโจมตีต่างชนิด: ไม่แชร์ DR ของชนิดที่ไม่เคยเห็น 27.9–44.1% · แชร์แล้ว 90.5–98.6% |
| B | dofid2023 | Kitsune (Mirai), BoT-IoT (DoS HTTP, DDoS HTTP) | network traffic (packet) | โหนดละการโจมตี: FedAvg ทุกโหนดได้ ≈0.36 แย่กว่าเทรนเดี่ยว ≈0.80 · แชร์แบบเลือกได้ ≈0.93 |
| B | crowdsensing2026 | IoT Crowdsensing DFL dataset | host log (system call, file, kernel, I/O) + network | IID: DFL ≥ CFL ทุกจำนวนโหนด (32 โหนด F1 0.913 vs 0.817) · non-IID α=0.1: F1 ตกเหลือ 0.807 |
| B | pentidef2026 | CIC-IDS2018, Edge-IIoTset | network flow | Fabric + 20 client: non-IID ทำให้ไม่มีการป้องกันตกเหลือ 0.36–0.51 · PenTiDef 0.90–0.95 |
| B | uavids2025 | UAV-IDS, UKM-IDS, TLM-IDS, Cyber-Physical | network traffic + network log + UAV telemetry | 4 client = 4 ชุดข้อมูลคนละ schema: 96.85–99.99% แต่ไม่มีผลเทรนเดี่ยวให้เทียบ |
| B | bflids2024 | Edge-IIoTset, TON_IoT | network traffic + IoT telemetry | IID 0.97 → non-IID 0.93–0.95 (Edge-IIoTset CNN) แต่ข้อความในเนื้อหาบอก 85.31% ขัดกับตาราง |
| B | flbcids2025 | CIC-IDS2018, CICIoT2023 | network flow | 98.89% แต่ไม่บอกวิธีแบ่งข้อมูล ไม่มี baseline เดี่ยว/centralized และ recall ของคลาส 0.006% ได้ 98% |
| B | bfl2026 | CICIoT2023 | network flow | ตาราง: centralized 98.2 / FL 97.5 / B-FL 98.9 แต่ข้อความบอก 93 / 95 / 98 · ไม่ระบุโมเดลและการแบ่งข้อมูล |
| B | swarmsense2026 | IoT-23, NSL-KDD, CICIDS2017, UNSW-NB15, Industrial IoT | network traffic (IDS benchmark) | เฉลี่ย 5 ชุด 95.44% vs FedAvg 85.46% vs centralized 88.46% (centralized ต่ำผิดปกติ ไม่บอกวิธีแบ่งข้อมูล) |
| B | fedlog2024 | HDFS, Thunderbird | system log (log-event sequence) | HDFS + Thunderbird: federated 1D-CNN บน system log (ยังมี server, ยังไม่ได้ตัวเลข) |

## 1b · การแชร์ความรู้เมื่อข้อมูลแต่ละโหนดต่างกัน

คำถาม: ตัวเลข 97–99% ของงาน FL มาจากการแชร์ความรู้ หรือเพราะทุกโหนดเห็นข้อมูลแบบเดียวกัน วัดได้ก็ต่อเมื่อ paper บอกวิธีแบ่งข้อมูล และมีผลเทรนเดี่ยวของโมเดลเดียวกันให้เทียบ ตารางนี้สรุปจาก PDF ฉบับเต็มของกลุ่ม A และ B เท่านั้น

| paper | แบ่งข้อมูลให้โหนด | โหนด | baseline เทรนเดี่ยว | baseline รวมศูนย์ | ตัวชี้วัด | ผลของการแชร์ |
|---|---|---|---|---|---|---|
| hbfl2022 | ตามชนิดการโจมตี: 2 องค์กรเห็นการโจมตีคนละชุด | 2 องค์กร × 2 endpoint | มี (ทดสอบข้ามองค์กร) | ไม่มี | accuracy, DR, F1, FAR | DR ของการโจมตีที่ไม่เคยเห็น 27.9% → 98.6% (Theft), 44.1% → 90.5% (Recon) |
| dofid2023 | สุดขั้ว: โหนดละการโจมตี จาก 2 ชุดข้อมูล | 3 | มี | ไม่มี | accuracy, TPR, TNR | FedAvg ทุกโหนด ≈0.36 แย่กว่าเทรนเดี่ยว ≈0.80 · แชร์แบบเลือกส่วน ≈0.93 |
| adonis2023 | ตาม gateway (ไม่บอกวิธี) · gateway ส่วนใหญ่ไม่เคยถูกโจมตี | 20 | มี | มี | accuracy | 67.6% → 89.4% (centralized 92.2%) · FedProx/SCAFFOLD ดีกว่า avg ≈3 จุด |
| iotfkgdlsl2024 | ไม่บอก | 1–100 | มี (S = 1) | ไม่มี | precision, recall, F1 | F1 0.910 → 0.937 ที่ 20 ผู้ร่วม · 10 ผู้ร่วมไม่ช่วย · 100 ผู้ร่วม precision ตก |
| crowdsensing2026 | IID และ Dirichlet α = 10, 1, 0.1 | 4–32 | ไม่มี | มี (ML 0.963) | accuracy, macro-F1, AUC | วัดไม่ได้ (ไม่มีเทรนเดี่ยว) · DFL ≥ CFL · α = 0.1 F1 0.930 → 0.807 |
| pentidef2026 | IID / non-IID ด้านสัดส่วน benign-attack (binary) | 20 | ไม่มี | ไม่มี | ไม่ระบุในตาราง | วัดไม่ได้ · ไม่มีการป้องกัน: IID ≈0.70 → non-IID ≈0.42 ภายใต้ adversary 10% |
| bflids2024 | สุ่ม (IID) และ non-IID ไม่อธิบายวิธี | 10–20 | ไม่มี | มี (กราฟ) | accuracy | วัดไม่ได้ · non-IID ต่ำกว่า IID 2–4 จุด · ตัวเลขในเนื้อหาขัดกับตาราง |
| uavids2025 | client ละชุดข้อมูล (ฟีเจอร์และคลาสต่างกันหมด) | 4 | ไม่มี | ไม่มี | accuracy, F1 | วัดไม่ได้ · แชร์ได้แค่ encoder |
| flbcids2025 | ไม่บอก | 10 | ไม่มี | ไม่มี | accuracy, F1 | วัดไม่ได้ |
| bfl2026 | "non-IID" ไม่บอกวิธี | ไม่บอก | ไม่มี | มี (ตัวเลขขัดกัน) | accuracy, F1 | วัดไม่ได้ · FL 97.5 vs centralized 98.2 ตามตาราง |
| swarmsense2026 | ไม่บอก | 100 | ไม่มี | มี (88.46% ต่ำผิดปกติ) | accuracy, F1, AUC | วัดไม่ได้ |

- มีแค่ 4 จาก 11 งานที่มีผลเทรนเดี่ยวให้เทียบ (HBFL, DOF-ID, ADONIS, IoT-FKGDL-SL) และใน 4 งานนี้ไม่มีงานไหนรายงาน 97–99% จากการแชร์บนข้อมูลที่ต่างกันจริง ยกเว้น HBFL ที่ข้อมูลเป็น attack 99.64%
- เมื่อแต่ละโหนดเห็นการโจมตีคนละแบบ การแชร์ช่วยมากต่อโหนดที่ไม่เคยเห็น (HBFL: DR 28–44% → 90–99%, ADONIS: +22 จุด) แต่ FedAvg ธรรมดาอาจแย่กว่าไม่แชร์เลยเมื่อความต่างสุดขั้ว (DOF-ID: 0.36 vs 0.80)
- งานที่รายงาน 97–99% (BFLIDS, FLBC-IDS, B-FL, UAV IDS) แบ่งข้อมูลแบบสุ่มหรือไม่บอกวิธี และไม่มีผลเทรนเดี่ยว ตัวเลขจึงบอกได้แค่ว่าโมเดลทำงานได้บนชุดข้อมูลนั้น ไม่ได้บอกว่าการแชร์ช่วย · BFLIDS และ B-FL มีตัวเลขในเนื้อหาขัดกับตาราง
- non-IID ในงานส่วนใหญ่เป็นแค่สัดส่วนคลาสต่างกัน (PenTiDef, BFLIDS) ซึ่งลดผลแค่ 2–4 จุด · ความต่างระดับ α = 0.1 ลด F1 12 จุด (Crowdsensing)
- ด้านสถาปัตยกรรม: DFL ที่ไม่มี server (ตระกูลเดียวกับ SL) ได้ F1 เท่าหรือสูงกว่า CFL ใน Crowdsensing · ADONIS ได้ SL ห่าง centralized 2.8 จุด · ยังไม่มีงานไหนเทียบ SL กับ FL บนข้อมูลชุดเดียวกันและการแบ่งเดียวกันโดยตรง
- สิ่งที่ sl-fabric ควรรายงานเพื่อตอบคำถามนี้: เทรนเดี่ยวต่อ org / swarm / centralized บนโมเดลเดียวกัน · แบ่งข้อมูลตามอุปกรณ์หรือชนิดการโจมตี (ไม่สุ่ม) · macro-F1 และ DR ของการโจมตีที่ org นั้นไม่เคยเห็น

## 2 · กลุ่ม A: swarm learning + ข้อมูล cyber โดยตรง

กลุ่มหลัก: เป็น swarm learning จริง และเทรนบน traffic หรือ log

### Swarm Learning and Knowledge Distillation Empowered Self-Driving Detection Against Threat Behavior for Intelligent IoT (ADONIS)

*Y. Liu, X. Zhang, L. Huo, J. Wu, M. Guizani* · IEEE Transactions on Mobile Computing 23(6):7117–7134, มิ.ย. 2024 · doi:10.1109/TMC.2023.3330514

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | ไฟล์ใน `paper/` |
| ความเกี่ยวกับ cybersecurity | หลัก — ตรวจพฤติกรรมผิดปกติของอุปกรณ์ IoT จาก traffic |
| ลิงก์ | <https://ieeexplore.ieee.org/document/10310124/> |
| สรุปบทคัดย่อ | ตรวจความผิดปกติของอุปกรณ์ IoT ที่ gateway บ้าน โดยไม่ส่ง traffic ออกจากบ้าน ใช้ SL รวมความรู้จากหลาย gateway เทรนโมเดลใหญ่ (teacher) แล้วกลั่นเป็นโมเดลเล็ก (student) ให้ตรวจจับได้เร็วบนอุปกรณ์ และให้ผู้ใช้ยืนยัน label เพื่อเทรนต่อเนื่อง |
| ชุดข้อมูล | home IoT traffic (เก็บเอง ไม่เปิดเผย) |
| รายละเอียดข้อมูล/การแบ่งโหนด | traffic จริงของอุปกรณ์บ้านอัจฉริยะ 49 เครื่อง 17 ชนิด เก็บ 1 สัปดาห์ผ่าน gateway (tcpdump บน OpenWrt) · หลังทำความสะอาดได้ 316,564 ตัวอย่าง: injection 63,911 · ransomware 53,745 · scanning 50,520 · ddos 49,999 · dos 6,641 · normal 52,991 · password 38,757 (ลดสัดส่วน normal และ password ให้สมดุล) · จำลอง 20 home gateway โดย "each client has only the local traffic generated by itself" แต่ไม่บอกว่าแบ่ง 49 อุปกรณ์เข้า 20 gateway อย่างไร · train/dev/test = 7:2:1 |
| วิธี/โมเดล | TM (teacher, 1,434,368 parameter) เทรนใน SL แล้วกลั่นด้วย KL divergence (T=20) เป็น DM (student, 68,832 parameter) สำหรับตรวจจับ · วัดด้วย accuracy |
| การตั้งค่า SL | จำลอง SL 20 client บนเครื่องเดียว (i7-12700F, RTX 3070, TensorFlow 2.3) · client ถูกเลือกต่อรอบด้วยความน่าจะเป็น 0.2 · 5 local epoch · 55 รอบ · รวมพารามิเตอร์แบบ average ตาม HPE SL · เทียบ 3 แบบ: เทรนเดี่ยว / SL / centralized |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| Table III · 20 client | accuracy | TM เทรนเดี่ยว: 67.6%; TM ใน SL: 89.4%; TM centralized: 92.2%; DM เทรนเดี่ยว: 44.4%; DM ใน SL: 66.3%; DM centralized: 66.8%; ADONIS (train / detect): 89.6% / 82.2% | ภาพตารางใน PDF |
| Table V · ขนาดชุดข้อมูล 1k → 1000k | accuracy | DM เดี่ยว: 47.3% → 41.5%; SL-DM: 68.0% → 64.5%; centralized DM: 69.5% → 65.9%; ADONIS: 83.1% → 78.4% | ภาพตารางใน PDF |
| Fig. 14 · วิธีรวมพารามิเตอร์ใน SL รอบที่ 50 | accuracy | Avg: ≈0.90; FedProx / FedDyn / SCAFFOLD: ≈0.93 | อ่านจากกราฟ ≈ |

**ประเด็นสำคัญ**

- การแชร์ความรู้ผ่าน SL เพิ่ม accuracy ราว 22 จุดจากการเทรนเดี่ยว (TM 67.6 → 89.4, DM 44.4 → 66.3) และห่าง centralized แค่ 2.8 และ 0.5 จุด
- Fig. 9: เมื่อเทรนเดี่ยว บาง client (ID 2, 3, 10, 19) ติดอยู่ที่ accuracy ต่ำ เพราะ gateway ส่วนใหญ่ไม่เคยถูกโจมตี SL ดึงทุก client ขึ้นมาได้
- วิธีรวมที่ออกแบบเพื่อ non-IID (FedProx, FedDyn, SCAFFOLD) ดีกว่า average ราว 3 จุด
- ยิ่งเพิ่ม gateway จาก 10 เป็น 90 ยิ่ง converge ช้า เพราะแต่ละโหนดมีตัวอย่างการโจมตีน้อยลง

**ช่องโหว่ / ข้อจำกัด**

- SL จำลองบนเครื่องเดียว ไม่มีการทดลองบน blockchain หรือ HPE SL จริง
- ไม่บอกวิธีแบ่ง traffic ให้ 20 gateway และไม่วัดระดับ non-IID
- วัดด้วย accuracy อย่างเดียว ไม่มี F1 หรือ recall รายคลาส ทั้งที่ dos มีแค่ 6,641 ตัวอย่าง
- ชุดข้อมูลไม่เปิดเผย ทำซ้ำไม่ได้
- ผู้เขียนยอมรับเองว่าการเฉลี่ยแบบ Avg "has good applicability for IID data scenarios" ส่วน non-IID ต้องปรับวิธีรวม
- อ้างว่า SL ทน model poisoning ดีกว่า FL แต่ไม่ได้ทดลอง (อ้างงานอื่น)

**ความเข้ากันได้กับสถาปัตยกรรม SL** — สูง — SL ตรงตัว (จำลอง)

**เทียบกับ `poc/sl-fabric`** — ให้แม่แบบการทดลองที่ sl-fabric ควรทำตาม: เทรนเดี่ยว / swarm / centralized บนโมเดลเดียวกัน · ตัวเลขช่องว่าง SL กับ centralized (2.8 จุด) ใช้เป็นเป้าเทียบได้ · ควรเพิ่ม F1 และผลต่อ client ที่ ADONIS ไม่มี

**ชื่อชุดข้อมูลที่สคริปต์เจอใน PDF** (หน้า): N-BaIoT (17), MIMIC (17)

**หลักฐานที่ตรวจกับ PDF**

- ✓ หน้า 10: “collected network traffic data of 49 household iot devices of 17”
- ✓ หน้า 11: “each client has only the local traffic generated by itself”
- ✓ หน้า 12: “the accuracy of sl-tm is only 2.6% lower than that of centralized-tm”
- ✓ หน้า 12: “there are stubborn clients”
- ✓ หน้า 16: “this has good applicability for iid data scenarios”

### IoT-FKGDL-SL: Anomaly Detection Framework Integrating Knowledge Distillation and a Swarm Learning for 5G IoT

*L. Tang, E. Kou, W. Zhang, Q. Wu, Q. Chen* · IEEE Internet of Things Journal 11(23):38601–38614, ธ.ค. 2024

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | ไฟล์ใน `paper/` |
| ความเกี่ยวกับ cybersecurity | หลัก — ตรวจ traffic ผิดปกติและอุปกรณ์ล้มเหลวใน 5G IoT |
| ลิงก์ | <https://ieeexplore.ieee.org/document/10654372/> |
| สรุปบทคัดย่อ | โมเดลตรวจความผิดปกติจาก multivariate time series ทำงานไม่ดีกับลำดับเวลายาว และการเรียนแบบรวมศูนย์เสี่ยงข้อมูลรั่ว จึงเสนอโมเดล IoT-FKGDL แล้วนำไปเทรนใน SL ร่วมกับ knowledge distillation |
| ชุดข้อมูล | LW5G-KPI (China Mobile Research Institute) |
| รายละเอียดข้อมูล/การแบ่งโหนด | KPI ของเครือข่าย 5G IoT เลือก 8 ตัวชี้วัด · train 70% / validation 30% · หน้าต่างตรวจ 8 · ไม่บอกวิธีแบ่งข้อมูลให้ผู้ร่วม SL · ไม่บอกชนิดและจำนวนความผิดปกติ |
| วิธี/โมเดล | FastDTW + K-means จัดกลุ่มตัวแปร → GCN → multiscale dilated convolution → LSH attention → reconstruction · anomaly score จาก reconstruction error · teacher (GCN 2048) กลั่นเป็น student (GCN 512) |
| การตั้งค่า SL | edge server เป็นผู้ร่วม · สุ่ม edge server หนึ่งเป็น "virtual central server" รวม teacher ด้วย weighted average ตามจำนวนข้อมูลหรือผลของโมเดล · ใช้ smart contract ขยายชุดข้อมูลต่อเนื่อง · ทดลอง 1, 10, 20, 50, 100 ผู้ร่วม |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| Fig. 7–9 · จำนวนผู้ร่วม SL = 1 / 10 / 20 / 50 / 100 | student model | F1: 0.9102 / 0.9098 / 0.9366 / 0.9260 / 0.9250; precision: 0.9689 / 0.9748 / 0.9714 / 0.9595 / 0.9438; recall: 0.8822 / 0.8805 / 0.9168 / 0.9053 / 0.9079 | อ่านจากกราฟ ≈ |
| Table II · ลำดับเวลายาว 576 · โมเดลเดี่ยว (ไม่ใช่ SL) | P / R / F1 | IoT-FKGDL: 0.982 / 0.918 / 0.939; BeatGAN (baseline ดีสุด): 0.858 / 0.842 / 0.861 | ภาพตารางใน PDF |

**ประเด็นสำคัญ**

- เทียบกับผู้ร่วมรายเดียว (S=1) SL ช่วย F1 ได้สูงสุด +0.026 ที่ 20 ผู้ร่วม แต่ที่ 10 ผู้ร่วมไม่ช่วยเลย (0.9098 เทียบ 0.9102)
- เกิน 20 ผู้ร่วม precision ลดลงจาก 0.9714 เหลือ 0.9438
- ตัวเลขเด่นของ paper (F1 0.939) เป็นผลของโมเดลเดี่ยว ไม่ใช่ผลของการแชร์ความรู้

**ช่องโหว่ / ข้อจำกัด**

- ไม่บอกวิธีแบ่งข้อมูลให้ผู้ร่วม และไม่มี centralized หรือ FL baseline ในส่วนของ SL
- ข้อความบอกว่า precision ลดจาก "0.984–0.943" แต่กราฟมีค่าสูงสุด 0.9748
- ชุดข้อมูลไม่สาธารณะ
- "SL" ในงานนี้คือการสุ่ม edge server เป็นผู้รวม ไม่ได้บรรยายชั้น blockchain นอกจาก smart contract ขยายข้อมูล

**ความเข้ากันได้กับสถาปัตยกรรม SL** — กลาง–สูง

**เทียบกับ `poc/sl-fabric`** — ข้อมูลเป็น time series ต้องใช้โมเดลลำดับ · การทดลองไล่จำนวนผู้ร่วมเป็นแบบที่ sl-fabric ทำซ้ำได้

**หลักฐานที่ตรวจกับ PDF**

- ✓ หน้า 8: “provided by the china mobile research institute”
- ✓ หน้า 7: “one edge server is chosen at random as the virtual central server”
- ✓ หน้า 11: “as the number of participants increases to 100, the performance of anomaly detection gradually decreases”


## 3 · กลุ่ม B: ข้อมูล cyber โดยตรง + สถาปัตยกรรมคล้าย SL

กลุ่มรอง: IDS บนข้อมูล cyber ที่เทรนแบบ decentralized, ประสานด้วย blockchain หรือ federated แต่ไม่ใช่ SL ตรงตัว

### HBFL: A Hierarchical Blockchain-based Federated Learning Framework for a Collaborative IoT Intrusion Detection

*M. Sarhan, W. W. Lo, S. Layeghy, M. Portmann* · Computers & Electrical Engineering 103, 2022 · arXiv:2204.04254

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | ไฟล์ใน `paper/` |
| ความเกี่ยวกับ cybersecurity | หลัก — แชร์ threat intelligence ข้ามองค์กร |
| ลิงก์ | <https://arxiv.org/abs/2204.04254> |
| สรุปบทคัดย่อ | แต่ละองค์กรเจอการโจมตีไม่เหมือนกัน IDS ที่เทรนจากข้อมูลตัวเองจึงไม่รู้จักการโจมตีที่ไม่เคยเจอ HBFL ให้หลายองค์กรเทรนร่วมกันแบบลำดับชั้นบน permissioned blockchain + smart contract โดยไม่ต้องเชื่อใจกัน |
| ชุดข้อมูล | NF-BoT-IoT-v2 |
| รายละเอียดข้อมูล/การแบ่งโหนด | NetFlow v9 ของ BoT-IoT · 37,763,497 flow (attack 99.64%, benign 0.36%) · ตัด IP/port ออก · 2 องค์กร × 2 endpoint · องค์กร k1 เห็น DDoS + Recon, องค์กร k2 เห็น DoS + Theft (ทั้งคู่มี benign) · train/test 70/30 |
| วิธี/โมเดล | Deep Feed Forward 4 ชั้น (32-16-8-4) · binary · 10 epoch · 10 รอบ |
| การตั้งค่า SL | ลำดับชั้น endpoint → combiner (องค์กร) → reducer · การทำงานบน permissioned blockchain ตรวจด้วย smart contract |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| Table 4 · ไม่แชร์ข้ามองค์กร: เทรนที่ k1 ทดสอบการโจมตีของ k2 | accuracy / DR | DoS: 95.77% / 93.15%; Theft: 63.88% / 27.90% | ภาพตารางใน PDF |
| Table 4 · ไม่แชร์ข้ามองค์กร: เทรนที่ k2 ทดสอบการโจมตีของ k1 | accuracy / DR | DDoS: 98.95% / 98.10%; Recon: 69.17% / 44.09% | ภาพตารางใน PDF |
| Table 4 · HBFL แชร์ข้ามองค์กร | accuracy / DR | DoS: 99.93% / 99.96%; Theft: 99.84% / 98.63%; DDoS: 99.18% / 98.37%; Recon: 98.89% / 90.46% | ภาพตารางใน PDF |

**ประเด็นสำคัญ**

- เป็นการทดลองเดียวในชุดที่วัดตรง ๆ ว่าความรู้ที่องค์กรหนึ่งไม่เคยเห็นถูกส่งต่อได้หรือไม่
- การโจมตีที่คล้ายของที่เคยเห็นตรวจได้อยู่แล้ว (DoS ↔ DDoS) แต่ชนิดที่ต่างจริงตรวจไม่ได้ (Theft DR 27.9%, Recon DR 44.1%)
- เมื่อแชร์ DR ของ Theft ขึ้นเป็น 98.6% และ Recon เป็น 90.5% · detection rate เฉลี่ย 60.53% และ 71.1% → accuracy เฉลี่ย 99.71%

**ช่องโหว่ / ข้อจำกัด**

- เพียง 2 องค์กร 4 endpoint และแบ่งตามชนิดการโจมตีแบบสะอาด (แต่ละชนิดอยู่องค์กรเดียว)
- ข้อมูลเป็น attack 99.64% accuracy ต่อชนิดจึงเกือบเท่า DR · ไม่มี centralized baseline
- ใช้ FedAvg ล้วน ไม่มีการทดลองการโจมตีหรือ non-IID แบบอื่น

**ความเข้ากันได้กับสถาปัตยกรรม SL** — กลาง–สูง — มีเชนและ smart contract แต่ยังเป็นลำดับชั้น

**เทียบกับ `poc/sl-fabric`** — แบบทดลองนี้คือสิ่งที่ sl-fabric ควรทำบน N-BaIoT: อุปกรณ์ 2 ตัวไม่เคยเจอ Mirai = องค์กรที่ไม่เคยเห็นการโจมตีชนิดนั้น วัด DR ของ Mirai บนอุปกรณ์นั้นก่อนและหลังเข้า swarm

**ชื่อชุดข้อมูลที่สคริปต์เจอใน PDF** (หน้า): CIFAR-10 (6), MNIST (6), UNSW-NB15 (6), BoT-IoT (6, 13, 18), CIC-IDS2017 (6), NSL-KDD (6, 13)

**หลักฐานที่ตรวจกับ PDF**

- ✓ หน้า 13: “the data sets n1 and n2 collected from each organisation contain a different set of attack classes”
- ✓ หน้า 13: “the attack samples are 37,628,460 (99.64%)”
- ✓ หน้า 14: “the mean detection rate is 60.53% and 71.1% in scenarios 1 and 2”

### Decentralized Online Federated G-Network Learning for Lightweight Intrusion Detection (DOF-ID)

*M. Nakıp, B. C. Gül, E. Gelenbe* · IEEE MASCOTS 2023 · doi:10.1109/MASCOTS59514.2023.10387644

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | ไฟล์ใน `paper/` |
| ความเกี่ยวกับ cybersecurity | หลัก — IDS แบบ online สำหรับ supply chain |
| ลิงก์ | <https://arxiv.org/abs/2306.13029> · <https://ieeexplore.ieee.org/document/10387644/> |
| สรุปบทคัดย่อ | หลายส่วนของ supply chain ถูกโจมตีแต่ต้องเก็บข้อมูลเป็นความลับ จึงให้ IDS แต่ละส่วนเรียนจากประสบการณ์ของส่วนอื่น แบบ decentralized และ online โดยเรียนจาก traffic ปกติอย่างเดียว |
| ชุดข้อมูล | Kitsune (Mirai), BoT-IoT (DoS HTTP, DDoS HTTP) |
| รายละเอียดข้อมูล/การแบ่งโหนด | 3 โหนด = 3 การโจมตีจาก 2 ชุดข้อมูล: Mirai จาก Kitsune 764,137 packet (107 IP, ~2 ชม.) · DoS HTTP 29,762 packet · DDoS HTTP 19,826 packet จาก BoT-IoT · กลับแกนเวลาให้เริ่มด้วย traffic ปกติ · label ของหน้าต่างเวลา = เสียงข้างมากของ packet |
| วิธี/โมเดล | Deep Random Neural Network (G-Network) + SWBC decision · anomaly-based (เรียนจาก benign) · online |
| การตั้งค่า SL | ไม่มี server และไม่มี blockchain · แต่ละโหนดดึงพารามิเตอร์จากโหนดที่ใกล้ที่สุดทีละส่วน (c = 0.75) · เทียบกับ เทรนเดี่ยว, เฉลี่ยทุกโหนด (แบบ FedAvg), เฉลี่ยกับโหนดใกล้สุด (ACN, ACN-L) |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| Fig. 3 · DOF-ID ต่อโหนด | accuracy / TPR / TNR | Mirai: 0.98 / 1.00 / 0.97; DoS HTTP: 0.93 / 0.99 / 0.91; DDoS HTTP: 0.88 / 0.92 / 0.86 | อ่านจากกราฟ ≈ |
| Fig. 4 · ค่ามัธยฐานของ 3 โหนด | accuracy / TPR / TNR | DOF-ID: ≈0.93 / ≈0.99 / ≈0.92; เทรนเดี่ยว (No Federated): ≈0.80 / ≈0.38 / ≈0.97; เฉลี่ยทุกโหนด (Average): ≈0.36 / 1.00 / ≈0.05; ACN / ACN-L: ≈0.39–0.40 / 1.00 / ≈0.10 | อ่านจากกราฟ ≈ |
| Table I และข้อความ | เวลา | รวมต่อหน้าต่าง: 48.91 ms (เรียน 19.2 + federated 29.6 + ตรวจ 0.11) | ข้อความใน PDF |

**ประเด็นสำคัญ**

- เมื่อแต่ละโหนดเห็นการโจมตีคนละแบบ การเฉลี่ยพารามิเตอร์ทุกโหนดแบบ FedAvg แย่กว่าไม่แชร์เลย: accuracy ≈0.36 เทียบเทรนเดี่ยว ≈0.80 และ TNR ≈0.05 คือแจ้งเตือนเกือบทุกอย่าง
- ผู้เขียนอธิบายว่า "network traffic across nodes varies considerably"
- การแชร์แบบเลือกส่วน (ดึงจากโหนดที่คล้ายที่สุด) ได้ accuracy ≈0.93 และยก TPR จาก ≈0.38 เป็น ≈0.99 แลกกับ false alarm เพิ่มเล็กน้อย

**ช่องโหว่ / ข้อจำกัด**

- 3 โหนดเท่านั้น และแต่ละโหนดมาจากชุดข้อมูลต่างกัน ความต่างจึงปนทั้งชนิดการโจมตีและสภาพแวดล้อมการเก็บ
- ตัวเลขใน Fig. 4 อ่านจาก box plot
- ไม่มี centralized baseline

**ความเข้ากันได้กับสถาปัตยกรรม SL** — กลาง — decentralized จริงแต่ไม่มีเชนและไม่มี leader

**เทียบกับ `poc/sl-fabric`** — คำเตือนสำคัญที่สุดสำหรับ sl-fabric: เราใช้ FedAvg ล้วน ถ้าแบ่ง N-BaIoT ตามอุปกรณ์ซึ่งต่างกันจริง อาจเจอผลแบบเดียวกัน ควรเทียบกับการเทรนเดี่ยวทุกครั้ง และเตรียมวิธีรวมแบบเลือกส่วนหรือ personalization

**ชื่อชุดข้อมูลที่สคริปต์เจอใน PDF** (หน้า): Kitsune (1, 2, 5, 7, 8), BoT-IoT (1, 2, 5, 7, 8)

**หลักฐานที่ตรวจกับ PDF**

- ✓ หน้า 5: “we use three attack data each of which corresponds to a single node”
- ✓ หน้า 6: “another important observation of this figure is the poor performance of the averaging over all collaborating nodes”
- ✓ หน้า 6: “this is an expected result as network traffic across nodes varies considerably”

### A crowdsensing intrusion detection dataset for decentralized federated learning models

*C. Feng, A. Huertas Celdrán, J. Han, H. Ren, X. Cheng, Z. Zeng, L. Krauter, G. Bovet, B. Stiller* · Scientific Data 13:796, 2026 · doi:10.1038/s41597-026-07155-w

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | ไฟล์ใน `paper/` |
| ความเกี่ยวกับ cybersecurity | หลัก — malware detection ใน IoT crowdsensing |
| ลิงก์ | <https://www.nature.com/articles/s41597-026-07155-w> · <https://arxiv.org/abs/2507.13313> |
| สรุปบทคัดย่อ | เสนอชุดข้อมูล malware สำหรับ decentralized FL โดยตรง พร้อมผลเทียบ ML รวมศูนย์ / CFL / DFL หลายจำนวนโหนด topology และระดับ non-IID |
| ชุดข้อมูล | IoT Crowdsensing DFL dataset |
| รายละเอียดข้อมูล/การแบ่งโหนด | อุปกรณ์ Raspberry Pi · benign + malware 8 ตระกูล · 21,582,484 record ดิบ → หน้าต่าง 30 วินาที 342,106 record · เลือก 32 ฟีเจอร์ · ปรับคลาสให้สมดุล · "data were partitioned by device" · IID และ Dirichlet α = 10, 1, 0.1 |
| วิธี/โมเดล | MLP 32×128×9 · FedAvg · 10 รอบ × 3 local epoch · วัด accuracy, macro-F1, precision, recall, AUC, bytes |
| การตั้งค่า SL | DFL บนแพลตฟอร์ม Nebula: fully connected, random, ring, star · 4 / 8 / 16 / 32 โหนด · เทียบ CFL (มี server) |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| Table 6 · IID | macro-F1 | ML รวมศูนย์: 0.963; CFL 4 / 8 / 16 / 32 โหนด: 0.942 / 0.897 / 0.847 / 0.817; DFL fully connected: 0.950 / 0.932 / 0.887 / 0.913; DFL ring: 0.951 / 0.927 / 0.820 / 0.871; DFL star: 0.938 / 0.904 / 0.867 / 0.910 | ข้อความใน PDF |
| Table 7 · DFL fully connected 8 โหนด · non-IID | accuracy / macro-F1 | α = 10: 0.931 / 0.930; α = 1: 0.930 / 0.930; α = 0.1: 0.813 / 0.807 (AUC 0.986) | ข้อความใน PDF |
| Table 8 · label flipping 8 โหนด | accuracy / F1 | 25% โหนด: 0.853 / 0.843; 50%: 0.360 / 0.305; 75%: 0.108 / 0.100 | ข้อความใน PDF |

**ประเด็นสำคัญ**

- DFL (ตระกูลเดียวกับ SL) ได้ F1 สูงกว่า CFL ทุกจำนวนโหนดในแบบ fully connected (เช่น 32 โหนด 0.913 เทียบ 0.817)
- ยิ่งแบ่งโหนดมาก ยิ่งต่ำกว่า centralized (0.963): ข้อมูลต่อโหนดน้อยลง
- ระดับ non-IID ปานกลาง (α = 1) ไม่กระทบ แต่ α = 0.1 ทำให้ F1 ตก 12 จุดเหลือ 0.807
- FedAvg ไม่มีการป้องกัน: โหนดวางยา 50% ทำให้ F1 เหลือ 0.305

**ช่องโหว่ / ข้อจำกัด**

- ไม่มีผลเทรนเดี่ยวต่อโหนด จึงวัดประโยชน์ของการแชร์เทียบการไม่แชร์ไม่ได้
- ข้อความบอก partition ตามอุปกรณ์ แต่การทดลองใช้ IID/Dirichlet ไม่ชัดว่าใช้แบบไหนในตารางใด
- Raspberry Pi อย่างเดียว

**ความเข้ากันได้กับสถาปัตยกรรม SL** — สูงด้านข้อมูล — ออกแบบมาให้หลายโหนดเทรนร่วมกัน และรายงาน macro-F1

**เทียบกับ `poc/sl-fabric`** — ผู้สมัครชุดข้อมูลที่ดีที่สุดสำหรับเทียบ SL กับ DFL/CFL: มี baseline ครบ, macro-F1, ไล่ α และไล่จำนวนโหนด

**ชื่อชุดข้อมูลที่สคริปต์เจอใน PDF** (หน้า): BoT-IoT (2, 14), TON_IoT (2, 14), CIC-IDS2017 (2), NSL-KDD (2), N-BaIoT (15)

**หลักฐานที่ตรวจกับ PDF**

- ✓ หน้า 10: “data were partitioned by device to simulate dfl scenarios”
- ✓ หน้า 11: “dfl achieves comparable or superior performance to cfl under most evaluated configurations”
- ✓ หน้า 12: “with accuracy decreasing to 0.813 and the macro f1 score to 0.807”

### PenTiDef: Decentralized Federated Intrusion Detection System with Differential Privacy and Latent-Space Defense via Blockchain Coordination in IIoT

*P. T. Duy, N. H. Khoa, N. T. A. Quan, L. H. Tien, N. D. H. Son, V.-H. Pham* · arXiv:2602.17973v2, พ.ค. 2026

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | ไฟล์ใน `paper/` |
| ความเกี่ยวกับ cybersecurity | หลัก — IDS สำหรับ IIoT ที่ทนต่อ poisoning |
| ลิงก์ | <https://arxiv.org/abs/2602.17973> |
| สรุปบทคัดย่อ | DFL-IDS ที่ไม่มี server ต้องทั้งรักษาความลับและทน poisoning โดยเฉพาะเมื่อข้อมูล non-IID ทำให้แยกยากว่า update ไหน แค่ต่างกับ update ไหนประสงค์ร้าย |
| ชุดข้อมูล | CIC-IDS2018, Edge-IIoTset |
| รายละเอียดข้อมูล/การแบ่งโหนด | binary: Edge-IIoTset benign 71.4% / attack 28.6% (95 ฟีเจอร์) · CIC-IDS2018 benign 42.6% / attack 57.4% (71 ฟีเจอร์) · test 30% · train 70% แบ่งเท่ากันให้ 20 client · IID = สัดส่วนเท่ากันทุก client · non-IID = จำนวนเท่ากันแต่สัดส่วน benign/attack ต่างกันมาก |
| วิธี/โมเดล | CNN (11 hidden) · distributed differential privacy · AutoEncoder บีบ representation ชั้นก่อนสุดท้าย แล้วใช้ CKA + KMeans คัด update ที่ถูกวางยา · เทียบกับ FLARE และ FedCC ภายใต้ adversary 10/20/40% |
| การตั้งค่า SL | Hyperledger Fabric 3 org × 2 peer + IPFS เก็บโมเดล (hash บนเชน) · smart contract จัดการ aggregation และประวัติ update |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| Table 3 · IID · untargeted · adversary 10% | ผลรวม (ค่าเดียวต่อเซลล์) | ไม่มีการป้องกัน: 0.64–0.77; FLARE / FedCC: 0.94–0.99; PenTiDef: 0.95–0.98 | ภาพตารางใน PDF |
| Table 5 · non-IID · untargeted · adversary 10% | ผลรวม | ไม่มีการป้องกัน: 0.36–0.51; FLARE / FedCC: 0.89–0.93; PenTiDef: 0.90–0.95 | ภาพตารางใน PDF |
| Fig. 5 · ไม่มีผู้โจมตี | accuracy | ไม่มี DP: ≈0.99; มี DP: ต่ำกว่าราว 0.01 | อ่านจากกราฟ ≈ |

**ประเด็นสำคัญ**

- non-IID ทำให้ FedAvg ที่ไม่มีการป้องกันพังหนักกว่า IID มาก (≈0.70 → ≈0.42 ที่ adversary 10%)
- เมื่อข้อมูล non-IID คะแนน CKA ของ client ดีลดลงราว 0.1 การแยก "ต่าง" ออกจาก "ประสงค์ร้าย" ยากขึ้น
- สถาปัตยกรรมเกือบตรงกับ sl-fabric: Fabric + เก็บ hash บนเชน + โมเดลนอกเชน

**ช่องโหว่ / ข้อจำกัด**

- non-IID เป็นแค่สัดส่วน benign/attack ต่างกัน (binary) ไม่ใช่ชนิดการโจมตีต่างกัน
- ไม่มีผลเทรนเดี่ยวหรือ centralized · ทุกตารางวัดภายใต้การโจมตี
- ตารางไม่ระบุชัดว่าค่าในเซลล์คือ accuracy หรือ F1
- preprint ยังไม่ผ่าน peer review

**ความเข้ากันได้กับสถาปัตยกรรม SL** — สูง — แทบเป็น SL บน IDS: ไม่มี server, Fabric ประสาน, ตรวจ update

**เทียบกับ `poc/sl-fabric`** — ต้นแบบที่ใกล้ที่สุดของ sl-fabric บนข้อมูล cyber · กลไก CKA + clustering เพิ่มเป็นขั้นก่อน FedAvg ได้

**ชื่อชุดข้อมูลที่สคริปต์เจอใน PDF** (หน้า): Edge-IIoTset (1, 3, 5, 17, 18, 19…), CIFAR-10 (5), MNIST (5), N-BaIoT (5), TON_IoT (5)

**หลักฐานที่ตรวจกับ PDF**

- ✓ หน้า 12: “we implement it using a permissioned hyperledger fabric network with 3 organizations and 6 peer nodes”
- ✓ หน้า 16: “with the fl simulation incorporating 20 clients”
- ✓ หน้า 17: “the remaining 70% was evenly distributed among the collaborating machines”

### An Efficient Privacy-preserving Intrusion Detection Scheme for UAV Swarm Networks

*K. Gharami, S. S. Moni* · AIAA/IEEE DASC 2025 · arXiv:2511.22791

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | ไฟล์ใน `paper/` |
| ความเกี่ยวกับ cybersecurity | หลัก — IDS สำหรับฝูงโดรน |
| ลิงก์ | <https://arxiv.org/abs/2511.22791> |
| สรุปบทคัดย่อ | ฝูงโดรนต่างฝูงมีข้อมูลคนละรูปแบบ จึงให้แต่ละฝูงมีชั้น input และตัวจำแนกของตัวเอง แล้วแชร์เฉพาะ encoder ร่วม |
| ชุดข้อมูล | UAV-IDS, UKM-IDS, TLM-IDS, Cyber-Physical |
| รายละเอียดข้อมูล/การแบ่งโหนด | 4 client = 4 ชุดข้อมูลคนละแบบ: UAV-IDS 98,736 ตัวอย่าง 54 ฟีเจอร์ 2 คลาส · UKM-IDS 12,887 · 46 · 9 · TLM-IDS 12,254 · 18 · 5 (ความล้มเหลวของโดรนจากการจำลอง) · Cyber-Physical 33,102 · 36 · 3 · train/test 80/20 |
| วิธี/โมเดล | ชั้น input เฉพาะฝูง + encoder CNN-LSTM ร่วม + classifier เฉพาะฝูง · EWC กันลืม |
| การตั้งค่า SL | Flower · cloud server กลางรวมเฉพาะ encoder ด้วย FedAvg · 4 client · 50 รอบ |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| Table V | accuracy / F1 | UAV-IDS: 99.99% / 99.99%; UKM-IDS: 99.46% / 99.03%; TLM-IDS: 96.85% / 94.83%; Cyber-Physical: 98.05% / 98.08% | ข้อความใน PDF |
| Table VI · เทียบโมเดลอื่น | accuracy | UKM-IDS: MLP-AE: 100% (สูงกว่าของผู้เขียน 99.46%); TLM-IDS: L-MADE: 97.86% (สูงกว่า 96.85%) | ข้อความใน PDF |

**ประเด็นสำคัญ**

- เป็นกรณีความหลากหลายสุดขั้วด้านฟีเจอร์: client ไม่มีฟีเจอร์หรือคลาสร่วมกันเลย แชร์ได้แค่ encoder
- TLM-IDS ไม่ใช่การโจมตีแต่เป็นความล้มเหลวของอุปกรณ์จากการจำลอง

**ช่องโหว่ / ข้อจำกัด**

- ไม่มีผลเทรนเดี่ยวของโมเดลเดียวกัน จึงบอกไม่ได้ว่า encoder ร่วมช่วยหรือถ่วงแต่ละฝูง
- baseline ใน Table VI เป็นโมเดลอื่น ไม่ใช่โมเดลเดียวกันที่ไม่แชร์ และบางชุด baseline ชนะ
- มี server กลาง ไม่มี blockchain

**ความเข้ากันได้กับสถาปัตยกรรม SL** — ต่ำ–กลาง

**เทียบกับ `poc/sl-fabric`** — แนวคิด encoder ร่วม + หัวเฉพาะโหนด ใช้ได้ถ้า org ใน sl-fabric มีฟีเจอร์ไม่เหมือนกัน (เช่น TON_IoT ต่างเซนเซอร์)

**ชื่อชุดข้อมูลที่สคริปต์เจอใน PDF** (หน้า): CIC-IDS2017 (2, 9), NSL-KDD (2, 9)

**หลักฐานที่ตรวจกับ PDF**

- ✓ หน้า 5: “integrates four separate uav swarm networks, each corresponding to one of our heterogeneous datasets”
- ✓ หน้า 5: “a central cloud server coordinates the aggregation of model updates”

### BFLIDS: Blockchain-Driven Federated Learning for Intrusion Detection in IoMT Networks

*K. Begum, M. A. I. Mozumder, M.-I. Joo, H.-C. Kim* · Sensors 24(14):4591, 2024

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | ไฟล์ใน `paper/` |
| ความเกี่ยวกับ cybersecurity | หลัก — IDS สำหรับ Internet of Medical Things |
| ลิงก์ | <https://www.mdpi.com/1424-8220/24/14/4591> |
| สรุปบทคัดย่อ | IDS แบบรวมศูนย์ขัดกับความเป็นส่วนตัวของอุปกรณ์การแพทย์ จึงใช้ FL + Ethereum smart contract + IPFS |
| ชุดข้อมูล | Edge-IIoTset, TON_IoT |
| รายละเอียดข้อมูล/การแบ่งโหนด | Edge-IIoTset 1,909,671 ตัวอย่าง 15 คลาส · TON_IoT 22,339,021 flow (attack 96.44%) · ใช้ SMOTE oversample คลาสน้อย · "training data were distributed to each client, from which a random selection was made" · มีคอลัมน์ IID และ non-IID ใน Table 3 แต่ไม่อธิบายวิธีแบ่ง non-IID |
| วิธี/โมเดล | CNN และ BiLSTM · FedAvg ปรับด้วย KL divergence + adaptive weight · 20 local epoch · 50 รอบ |
| การตั้งค่า SL | aggregation server บน blockchain (Ethereum, Solidity) + IPFS + MongoDB · K = 10, 15, 20 |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| Table 3 · รอบที่ 50 · global | accuracy IID / non-IID | Edge-IIoTset CNN: 0.97 / 0.93–0.95; Edge-IIoTset BiLSTM: 0.94–0.96 / 0.90–0.91; TON_IoT CNN: 0.97–0.98 / 0.95–0.96; TON_IoT BiLSTM: 0.93 / 0.92–0.95 | ภาพตารางใน PDF |
| ข้อความหัวข้อ 4.4.2 | global accuracy รอบที่ 50 | Edge-IIoTset CNN: 85.31%; TON_IoT CNN: 87.95%; BiLSTM: ≈82–83% | ข้อความใน PDF |

**ประเด็นสำคัญ**

- non-IID ลด accuracy ราว 2–4 จุดจาก IID
- ตัวเลข 97.43% ในบทคัดย่อตรงกับคอลัมน์ IID

**ช่องโหว่ / ข้อจำกัด**

- ข้อความในเนื้อหาบอก global accuracy 85.31% และ 87.95% แต่ Table 3 บอก 0.97 ในเงื่อนไขเดียวกัน ขัดกันเอง
- ไม่อธิบายวิธีแบ่ง non-IID · ไม่มีผลเทรนเดี่ยว · centralized มีแค่ในกราฟ
- SMOTE ก่อนแบ่งข้อมูลอาจทำให้ตัวอย่างสังเคราะห์รั่วไปชุดทดสอบ (ไม่ระบุลำดับ)
- การถ่วงน้ำหนักแบบผกผันกับ KL divergence ลดน้ำหนัก client ที่ข้อมูลต่าง ซึ่งอาจกดความรู้ที่หายากลง (ไม่ได้ทดลอง)

**ความเข้ากันได้กับสถาปัตยกรรม SL** — กลาง

**เทียบกับ `poc/sl-fabric`** — ใช้ได้เป็น baseline IID/non-IID บน Edge-IIoTset และ TON_IoT แต่ต้องระวังตัวเลขที่ขัดกันเอง

**ชื่อชุดข้อมูลที่สคริปต์เจอใน PDF** (หน้า): TON_IoT (1, 17, 18, 19, 20, 21…), Edge-IIoTset (1, 17, 18, 19, 20, 21…), BoT-IoT (25)

**หลักฐานที่ตรวจกับ PDF**

- ✓ หน้า 16: “we oversampled minority classes using smote”
- ✓ หน้า 17: “training data were distributed to each client, from which a random selection was made”
- ✓ หน้า 19: “the global accuracy after the 50th fl round improved to 85.31%”

### FLBC-IDS: a federated learning and blockchain-based intrusion detection system for secure IoT environments

*A. Govindaram, Jegatheesan A* · Multimedia Tools and Applications 84:17229–17251, 2025 · doi:10.1007/s11042-024-19777-6

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | ไฟล์ใน `paper/` |
| ความเกี่ยวกับ cybersecurity | หลัก — IoT IDS |
| ลิงก์ | <https://link.springer.com/article/10.1007/s11042-024-19777-6> |
| สรุปบทคัดย่อ | รวม horizontal FL, Hyperledger และ EfficientNet ตรวจการบุกรุก IoT โดยบันทึก update บนเชน |
| ชุดข้อมูล | CIC-IDS2018, CICIoT2023 |
| รายละเอียดข้อมูล/การแบ่งโหนด | CIC-IDS2018: benign 83.07%, web attack 0.006%, infiltration 0.997% · CICIoT2023 บางคลาส (Recon, Mirai) · 10 client "representing a variety of IoT devices deployed in a smart city" แต่ไม่บอกว่าแบ่งข้อมูลให้ client อย่างไร |
| วิธี/โมเดล | EfficientNet · Federated Averaging with Secure Aggregation · เลือก client 30% ต่อรอบ |
| การตั้งค่า SL | HFL มี server กลาง + Hyperledger บันทึก update |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| Table 2 · CIC-IDS2018 รายคลาส | accuracy / recall | Benign: 99.20% / 98.00%; Web Attack (0.006% ของข้อมูล): 98.81% / 98.25%; Infiltration: 98.85% / 98.22% | ข้อความใน PDF |
| Table 4 · เทียบงานอื่น | accuracy / F1 | FLBC-IDS: 98.89% / 98.29%; FedACNN: 98.73% / 88.97% | ข้อความใน PDF |

**ประเด็นสำคัญ**

- ใช้ Hyperledger บันทึก update เหมือน sl-fabric

**ช่องโหว่ / ข้อจำกัด**

- ไม่มีวิธีแบ่งข้อมูล ไม่มีผลเทรนเดี่ยว ไม่มี centralized และไม่มี non-IID
- recall 98.25% ของ Web Attack ซึ่งมี 0.006% ของข้อมูลน่าสงสัย และ accuracy รายคลาสแบบ one-vs-rest ไม่มีความหมายกับคลาสเล็กขนาดนี้
- Table 4 เทียบกับตัวเลขของงานอื่นที่ใช้ข้อมูลต่างกัน

**ความเข้ากันได้กับสถาปัตยกรรม SL** — กลาง

**เทียบกับ `poc/sl-fabric`** — ใช้อ้างได้แค่ว่ามีงานใช้ Hyperledger กับ IDS ตัวเลขไม่ควรใช้เป็น baseline

**ชื่อชุดข้อมูลที่สคริปต์เจอใน PDF** (หน้า): CICIoT2023 (5, 15, 23), TON_IoT (6), N-BaIoT (7)

**หลักฐานที่ตรวจกับ PDF**

- ✓ หน้า 16: “ten clients representing a variety of iot devices deployed in a smart city participate”
- ✓ หน้า 16: “roughly 30% of available clients are selected at random”

### A blockchain-assisted secure federated learning architecture for intrusion detection in internet of things networks (B-FL)

*M. Kamran, S. M. Akhtar, A. Gilani, A. A. Alhashmi, S. Kanwal, A. A. Darem, A. A. Alofairi* · Scientific Reports 16:26072, 2026 · doi:10.1038/s41598-026-53053-x

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | ไฟล์ใน `paper/` |
| ความเกี่ยวกับ cybersecurity | หลัก — IoT IDS |
| ลิงก์ | <https://www.nature.com/articles/s41598-026-53053-x> |
| สรุปบทคัดย่อ | FL ต้องเชื่อใจ client และ aggregator จึงเพิ่ม blockchain ประเมินความน่าเชื่อถือของ client แล้วถ่วงน้ำหนักตาม trust |
| ชุดข้อมูล | CICIoT2023 |
| รายละเอียดข้อมูล/การแบ่งโหนด | CICIoT2023 · "split into client-wise distributed subsets, which simulates the non-IID data distribution" ไม่บอกวิธีแบ่งหรือจำนวน client |
| วิธี/โมเดล | ไม่ระบุสถาปัตยกรรมโมเดล (ในเอกสารเขียนว่า "[E.g., CNN/LSTM/DNN]") · trust-weighted aggregation · PBFT |
| การตั้งค่า SL | blockchain-assisted FL · 50 รอบ · 5 local epoch · client participation 80% |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| Table 12 | accuracy / F1 | Centralized IDS: 98.2% / 98.1%; Standard FL: 97.5% / 97.3%; B-FL: 98.9% / 98.8% | ข้อความใน PDF |
| ข้อความใต้ Fig. 7 | accuracy | B-FL: ≈98%; FL: 95%; centralized: 93% | ข้อความใน PDF |

**ประเด็นสำคัญ**

- FL ปกติด้อยกว่า centralized 0.7 จุด ตาม Table 12

**ช่องโหว่ / ข้อจำกัด**

- ตัวเลขในตารางกับข้อความขัดกัน (centralized 98.2% ในตาราง แต่ 93% ในข้อความ)
- ไม่ระบุโมเดล (ทิ้งข้อความแม่แบบ "[E.g., CNN/LSTM/DNN]"), ไม่บอกจำนวน client และวิธีแบ่ง non-IID
- บรรยายผลว่าเป็นสภาพแวดล้อม V2V ทั้งที่ใช้ CICIoT2023 · confusion matrix มี 4 คลาสแต่ ROC มีคลาสอื่น
- ablation รายงาน full model 97.8% ไม่ตรงกับ 98.9%

**ความเข้ากันได้กับสถาปัตยกรรม SL** — กลาง

**เทียบกับ `poc/sl-fabric`** — ความน่าเชื่อถือต่ำ ไม่ควรใช้ตัวเลขเป็น baseline

**ชื่อชุดข้อมูลที่สคริปต์เจอใน PDF** (หน้า): CICIoT2023 (1, 7, 9, 10, 15, 17…), UNSW-NB15 (7, 9), BoT-IoT (7, 9, 10), CIC-IDS2017 (7), NSL-KDD (7, 9, 10)

**หลักฐานที่ตรวจกับ PDF**

- ✓ หน้า 17: “model architecture: [e.g., cnn/lstm/dnn]”
- ✓ หน้า 17: “the highest accuracy of the proposed method is about 98 percent, which is better than fl (95 percent)”
- ✓ หน้า 12: “the processed data is then split into client-wise distributed subsets”

### SwarmSense-DNN: A Trustworthy and Decentralized Neural Framework for Proactive Anomaly Defense in Consumer IoT

*J. Yang, V. Govindarajan, S. Arif, X. Xu, M. Kallel, Z. A. Shaikh, Z. Liu, C. Yuan, L. Y. Por* · arXiv:2606.11803v1, มิ.ย. 2026

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | ไฟล์ใน `paper/` |
| ความเกี่ยวกับ cybersecurity | หลัก — consumer IoT anomaly detection |
| ลิงก์ | <https://arxiv.org/abs/2606.11803> |
| สรุปบทคัดย่อ | ตรวจความผิดปกติใน IoT ผู้บริโภคแบบไม่มีจุดศูนย์กลาง ประสานโหนดด้วยกลไก pheromone (swarm intelligence) + GNN + attention |
| ชุดข้อมูล | IoT-23, NSL-KDD, CICIDS2017, UNSW-NB15, Industrial IoT |
| รายละเอียดข้อมูล/การแบ่งโหนด | 100 โหนด Raspberry Pi 4 · train/val/test 70/15/15 · anomaly rate 5.2–23.1% · ไม่บอกว่าแบ่งข้อมูลให้ 100 โหนดอย่างไร |
| วิธี/โมเดล | hierarchical FL + GNN + multi-head attention · pheromone coordination · DP (ε ∈ {10, 5, 1, 0.1}) · 5 รอบอิสระ |
| การตั้งค่า SL | decentralized แบบ cluster 10–15 โหนด · ไม่มี blockchain |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| Table II · เฉลี่ย 5 ชุด | accuracy / F1 | Centralized DL: 88.46% / 88.16%; FedAvg-AD: 85.46% / 85.60%; Distributed GNN: 90.18% / 90.32%; SwarmSense-DNN: 95.44% / 95.49% | ข้อความใน PDF |
| Table III · ต่อชุดข้อมูล | accuracy SwarmSense / FedAvg | IoT-23: 94.7% / 84.6%; NSL-KDD: 96.2% / 86.8%; CICIDS2017: 97.1% / 88.3%; UNSW-NB15: 93.8% / 82.4% | ข้อความใน PDF |

**ประเด็นสำคัญ**

- รายงานว่า decentralized ชนะทั้ง FedAvg (+10 จุด) และ centralized (+7 จุด)

**ช่องโหว่ / ข้อจำกัด**

- centralized ที่เห็นข้อมูลครบได้แค่ 88.46% ต่ำกว่าวิธีกระจาย ซึ่งผิดปกติ และต่ำกว่าที่งานทั่วไปได้บน NSL-KDD/CICIDS2017
- ไม่บอกวิธีแบ่งข้อมูลให้โหนด · baseline "re-implemented" โดยผู้เขียน
- เป็น swarm intelligence + FL ไม่ใช่ SL และไม่มี ledger

**ความเข้ากันได้กับสถาปัตยกรรม SL** — กลาง

**เทียบกับ `poc/sl-fabric`** — ตัวเลขใช้เทียบไม่ได้จนกว่าจะรู้ว่าแบ่งข้อมูลอย่างไร

**ชื่อชุดข้อมูลที่สคริปต์เจอใน PDF** (หน้า): UNSW-NB15 (6, 7), CIC-IDS2017 (6, 7), NSL-KDD (6, 7)

**หลักฐานที่ตรวจกับ PDF**

- ✓ หน้า 6: “100 nodes distributed across testbed”
- ✓ หน้า 6: “iot-23, nsl-kdd, cicids2017, unsw-nb15, industrial iot”

### Anomaly detection in log-event sequences: A federated deep learning approach and open challenges

*-* · Machine Learning with Applications (Elsevier), 2024

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | web search |
| ความเกี่ยวกับ cybersecurity | หลัก — ตรวจความผิดปกติจาก system log |
| ลิงก์ | <https://www.sciencedirect.com/science/article/pii/S2666827024000306> |
| สรุปบทคัดย่อ | log ของระบบกระจายอยู่ตามองค์กรและมีข้อมูลอ่อนไหว จึงเทรนโมเดลตรวจความผิดปกติของลำดับ log-event แบบ federated โดยไม่ย้าย log ออกจากเจ้าของ และสรุปความท้าทายที่ยังเปิดอยู่ |
| ชุดข้อมูล | HDFS, Thunderbird |
| รายละเอียดข้อมูล/การแบ่งโหนด | HDFS: log ของ Hadoop บน Amazon EC2 · Thunderbird: log ของ supercomputer (ทั้งสองชุดอยู่ใน Loghub) |
| วิธี/โมเดล | 1D convolution บนลำดับ log-event + federated learning |
| การตั้งค่า SL | FL (มี server รวมโมเดล) — ไม่ใช่ decentralized |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| HDFS, Thunderbird | ตามผลค้น | federated 1D-CNN: ตัวเลขต้องดูฉบับเต็ม | เว็บ/บทคัดย่อ |

**ประเด็นสำคัญ**

- เป็นงานเดียวที่เจอซึ่งเทรนร่วมกันบน log ของระบบโดยตรง แทนที่จะเป็น network traffic

**ช่องโหว่ / ข้อจำกัด**

- ยังมี server กลาง
- HDFS/Thunderbird ส่วนใหญ่เป็นความผิดปกติจากความล้มเหลวของระบบ ไม่ใช่การโจมตีโดยเจตนา
- ยังไม่ได้ตัวเลข: ไฟล์ที่อัปโหลดใน paper/Cyber+Other/1-s2.0-S0730725X20300710-main.pdf เป็นคนละ paper (งาน MRI glioma ใน Magnetic Resonance Imaging) ไม่ใช่ S2666827024000306

**ความเข้ากันได้กับสถาปัตยกรรม SL** — ต่ำ–กลาง — ข้อมูลตรงโจทย์ แต่สถาปัตยกรรมยังรวมศูนย์

**เทียบกับ `poc/sl-fabric`** — ถ้าจะทำ SL บน log ต้องเปลี่ยน client เป็นโมเดลลำดับ (1D-CNN/LSTM) · ใช้เป็น baseline FL บน log ได้


## 4 · ภาคผนวก: งาน SL ด้าน security ที่ไม่ได้ใช้ข้อมูล cyber

ศึกษาการโจมตี/ป้องกันตัว SL หรือใช้ SL ในงานใกล้เคียง แต่ข้อมูลเป็นภาพ ข้อความ หรือสัญญาณวิทยุ — ไม่นับเป็นงานหลัก เก็บไว้เพราะยังให้แนวคิดด้านสถาปัตยกรรม

| paper | ชุดข้อมูล | ประเภทข้อมูล | ใช้ประโยชน์อะไรได้ | ลิงก์ |
|---|---|---|---|---|
| Blockchain-Based Swarm Learning for the Mitigation of Gradient Leakage in Federated Learning | CIFAR-10, MNIST | ภาพ | ตั้งการทดลองเหมือนโปรเจกต์: Dirichlet(α) แบ่ง non-IID (โปรเจกต์ใช้ α=0.5 บน BloodMNIST), FedAvg, โหนดเดี่ยว vs swarm · ต่างกันตรงที่ ledger ของโปรเจกต์เก็บ hash ของ weight (commit) แต่ weight ยังส่งกันนอกเชน จึงติดข้อจำกัดเดียวกันว่า leader เห็น weight ดิบ · ถ้าจะอ้างเรื่อง gradient leakage ต้องทดลองโจมตีจริง หรือเพิ่ม secure aggregation / HE (ดู Swarm-FHE) — เป็นช่องว่างที่ paper นี้ทิ้งไว้และโปรเจกต์เติมได้ | `paper/explore SL/Blockchain-Based_Swarm_Learning_for_the_Mitigation_of_Gradient_Leakage_in_Federated_Learning.pdf` |
| Improved Swarm Learning with Differential Privacy for Radio Frequency Fingerprinting | RFF dataset | สัญญาณวิทยุ (RF / IQ sample) | client ตอนนี้รับ tabular ต้องเพิ่ม CNN 1D ถ้าจะใช้ · ใช้อ้างเรื่องเติม DP ให้ swarm ได้ | <https://ieeexplore.ieee.org/document/10211163/> |
| Integrating Human-in-the-loop into Swarm Learning for Decentralized Fake News Detection (HBSL) | LIAR | ข้อความข่าว | ต่ำสำหรับ IDS · ไอเดียเรื่อง feedback loop ใช้กับการติด label ทราฟฟิกที่ SOC ยืนยันแล้วได้ | <https://arxiv.org/abs/2201.02048> · <https://ieeexplore.ieee.org/document/9923043/> |
| Backdoor attacks against distributed swarm learning | MNIST, CIFAR-10, SVHN | ภาพ | ทำซ้ำบน N-BaIoT ใน sl-fabric ได้: ให้ Org หนึ่งเทรนบนทราฟฟิกที่ฝัง trigger แล้วดูว่า global model ติด backdoor ไหม · ledger บันทึก hash ของ update ที่มี backdoor ไว้ถาวร ใช้ไล่ต้นตอย้อนหลังได้แต่ไม่ได้กันไว้ก่อน | <https://pubmed.ncbi.nlm.nih.gov/37012167/> · <https://www.sciencedirect.com/science/article/abs/pii/S0019057823001441> |
| Propagable Backdoors over Blockchain-based Federated Learning via Sample-Specific Eclipse | (ต้องดูฉบับเต็ม) | ไม่ระบุ | PoC ปัจจุบันไม่มี P2P จริง (process เดียว) · ถ้าแยกเครื่องควรให้ peer ของ Fabric ต่อกันหลายเส้นทาง | <https://ieeexplore.ieee.org/document/10001370/> |
| Zero-Trust Empowered Decentralized Security Defense against Poisoning Attacks in SL-IoT: Joint Distance-Accuracy Detection Approach | (ต้องดูฉบับเต็ม) | ไม่ระบุ | chaincode รู้ว่าใครคือ leader และมี hash ของทุก update อยู่แล้ว · ขยายได้โดยให้โหนดรายงาน accuracy บน validation ของตัวเองกับ global model แล้วให้ chaincode ปฏิเสธรอบที่ accuracy ตกผิดปกติ | <https://ieeexplore.ieee.org/document/10437789/> · <https://zenodo.org/records/13874888> |
| Swarm-FHE: Fully Homomorphic Encryption-based Swarm Learning for Malicious Clients | CIFAR-10, MNIST | ภาพ | FedAvg บน vector ทศนิยมทำใน CKKS ได้ · ledger เก็บ hash ของ ciphertext ได้เหมือนเดิม | <https://pubmed.ncbi.nlm.nih.gov/37246573/> |
| Multi-Region Asynchronous Swarm Learning for Data Sharing in Large-Scale Internet of Vehicles (MASL) | GTSRB (ตาม Table 3 ของ survey) | ภาพป้ายจราจร | ถ้าขยายเกิน 5 org อาจแบ่ง channel ของ Fabric ตามภูมิภาคแล้วรวมอีกชั้น | <https://www.researchgate.net/publication/373856168_Multi-Region_Asynchronous_Swarm_Learning_for_Data_Sharing_in_Large-Scale_Internet_of_Vehicles> |
| DAG-based swarm learning: A secure asynchronous learning framework for Internet of Vehicles (DSL) | GTSRB (ตาม Table 3 ของ survey) | ภาพป้ายจราจร | แนวคิด incentive ตาม accuracy ใช้ต่อยอดใน chaincode ได้ (บันทึก accuracy ต่อรอบอยู่แล้ว) | <https://www.sciencedirect.com/science/article/pii/S2352864823001578> |

## 5 · ภาคผนวก: พื้นฐานของ swarm learning

paper ในโฟลเดอร์ `paper/` ที่นิยามและวัด SL แต่ใช้ข้อมูลการแพทย์/ทั่วไป

| paper | ชุดข้อมูล | ประเภทข้อมูล | ใช้ประโยชน์อะไรได้ | ลิงก์ |
|---|---|---|---|---|
| Demystifying Swarm Learning: A New Paradigm of Blockchain-based Decentralized Federated Learning | NIH ChestX-ray, CIFAR-10, IMDB | ภาพ X-ray, ภาพ, ข้อความรีวิว | โปรเจกต์ใช้ leader rule แบบ deterministic `sha256(round + members) mod n` ซึ่งตรวจสอบย้อนหลังได้และกระจายสม่ำเสมอ ตอบข้อติของ paper นี้ตรง ๆ — วัดได้ทันทีด้วย `leader_counts()` และ `hostmetrics.py` ของ sl-fabric · `min_peers` ของ HPE = `quorum` ของ chaincode · RQ4 ชี้ว่าต้องมี robust aggregation (โปรเจกต์ยังไม่มี) · ข้อเสียของ rule แบบ deterministic คือรู้ล่วงหน้าว่าใครเป็น leader รอบถัดไป ผู้โจมตีเล็งเป้าได้ | `paper/explore SL/2201.05286v2.pdf` |
| Swarm Learning for decentralized and confidential clinical machine learning | GEO (GSE…), NIH ChestX-ray, COVID-19 blood transcriptomes (EGA) | transcriptome + ภาพ X-ray | ข้อมูลเป็น tabular มิติสูง + dense NN ซึ่งเข้ากับ interface 'flat parameter vector' ของ client ในโปรเจกต์พอดี · สิ่งที่โปรเจกต์ทำตรงกับ SL ต้นฉบับ: permissioned chain, leader หมุนเวียน, สิทธิ์ merge เท่ากัน, weight ไม่ขึ้นเชน · สิ่งที่ต่าง: โปรเจกต์ใช้ Fabric + MAJORITY endorsement แทน Ethereum ของ HPE และเปิดซอร์ส leader rule ได้ · ข้อมูลเป็นสายการแพทย์ ไม่ใช่ cyber — ใช้เป็นแม่แบบการออกแบบ scenario (prevalence ต่ำ, แยกตามแหล่ง) กับชุด cyber ได้ | `paper/explore SL/s41586-021-03583-3.pdf` |
| Swarm Learning: A Survey of Concepts, Applications, and Trends | (survey — รวบรวมจากงานอื่น) | survey (ไม่มีข้อมูลของตัวเอง) | ภัยที่โปรเจกต์กันได้แล้ว: ปลอมตัวเป็นโหนดอื่น (MSP identity), ส่งซ้ำ, non-leader ปิดรอบ, แก้รอบที่ปิดแล้ว (append-only) · ภัยที่ยังเปิด: backdoor/poisoning (ไม่มี robust aggregation), inference/model inversion (leader เห็น weight ดิบ), eclipse (ใน PoC ทุกโหนดอยู่ process เดียว) · ใช้บทที่ 5 เป็นโครง threat model ของวิทยานิพนธ์ได้ตรง ๆ | `paper/explore SL/2405.00556v2.pdf` |

รายละเอียดเต็มของงานในภาคผนวก (บทคัดย่อ ผลลัพธ์ หลักฐานจาก PDF) อยู่ใน `paper_review.json`

## 6 · งานที่ค้นเจอแต่คัดออก (ไม่ใช่ swarm learning)

| งาน | เหตุผล | ลิงก์ |
|---|---|---|
| SIML · Orchestrating ML models in a swarm architecture for IoT inline malware detection (Sci Rep 2025) | คำว่า swarm คือการจัด orchestration ของโมเดลหลายตัว ไม่มีการเทรนร่วมแบบไม่แชร์ข้อมูล · ตัวเลข UNSW-NB15 accuracy 93.7% ใช้เป็น baseline ได้อย่างเดียว | <https://www.nature.com/articles/s41598-025-28859-w> |
| งาน PSO / ACO / Salp swarm / Cat swarm สำหรับ IDS และ fraud detection | เป็น swarm intelligence ใช้เลือกฟีเจอร์หรือจูน hyperparameter ไม่ใช่ swarm learning | - |
| HLF-FSL · Decentralized Federated Split Learning on Hyperledger Fabric (arXiv 2507.07637) | สถาปัตยกรรมใกล้ sl-fabric มาก (chaincode ทำ aggregation แบบ P2P) แต่ทดลองบน CIFAR-10/MNIST ไม่ใช่ข้อมูล cyber — เก็บไว้อ้างเรื่องสถาปัตยกรรม | <https://arxiv.org/abs/2507.07637> |

## 7 · งาน SL สายการแพทย์ที่เจอระหว่างค้น (ไว้เทียบ)

| งาน | ข้อมูล | ผล | ลิงก์ |
|---|---|---|---|
| Saldanha et al. 2022 · Nature Medicine · SL in cancer histopathology | Epi700 (594), DACHS (2,039), TCGA (426) เทรน · QUASAR (MSI 1,774 / BRAF 1,477) และ YCR-BCIP ทดสอบภายนอก · ภาพ H&E กว่า 5,000 ผู้ป่วย | BRAF: local 0.7358 / 0.7339 / 0.7071, merged 0.7567, SL (w-chkpt) 0.7736 · MSI บน QUASAR: SL 0.8326 vs merged 0.8308 (AUROC) | <https://www.nature.com/articles/s41591-022-01768-5> |
| Saldanha et al. 2022 · Gastric Cancer · genetic aberrations with SL | 4 cohort จากสวิตเซอร์แลนด์ เยอรมนี สหราชอาณาจักร สหรัฐฯ แต่ละชุดอยู่บนคอมพิวเตอร์แยกกัน | external: MSI AUROC 0.8092 ± 0.0132, EBV 0.8372 ± 0.0179 · centralized ใกล้เคียงกัน | <https://link.springer.com/article/10.1007/s10120-022-01347-0> |
| Saldanha et al. 2025 · Communications Medicine · SL + weak supervision breast MRI | เทรน 1,372 exam (US, CH, UK) · ทดสอบภายนอก 649 exam (DE, GR) | 3D ResNet-101 AUROC 0.792 ± 0.045 · SL ดีกว่าเทรนเฉพาะที่ | <https://www.nature.com/articles/s43856-024-00722-5> |
| Fan et al. 2021 · On the Fairness of SL in Skin Lesion Classification | ชุดภาพรอยโรคผิวหนังสาธารณะ (ISIC) แบ่งตาม subgroup | SL ไม่ทำให้ fairness แย่กว่า centralized และดีกว่าเทรนเดี่ยว แต่ยังมี bias | <https://arxiv.org/abs/2109.12176> |
| SL-GAN 2022 · Generative Data Augmentation for Non-IID Problem in Decentralized Clinical ML | Tuberculosis, Leukemia, COVID-19 (ชุดเดียวกับ Nature 2021) | SL-GAN ดีกว่า state-of-the-art เมื่อ non-IID เพิ่มขึ้น (ตามบทคัดย่อ) | <https://arxiv.org/abs/2212.01109> |

## 8 · ชุดข้อมูล cyber โดยตรง เทียบกับสถาปัตยกรรมของโปรเจกต์

เกณฑ์ (0–2 ต่อข้อ, เต็ม 10) — ชุดเดียวกับ `../Explore.ipynb` บวกความเข้ากับ client ของ sl-fabric:

- **partition** — มี partition ตามเจ้าของจริง (ไม่ต้องสุ่ม Dirichlet)
- **baseline** — มีตัวเลขจาก paper SL/FL/blockchain-FL ให้เทียบ
- **size** — รันบนเครื่องเดียวได้ (client มี RAM ราว 6 GB)
- **audit** — มีเหตุผลว่าทำไมต้องมี ledger ตรวจสอบย้อนหลัง
- **model** — เข้ากับ client ของ sl-fabric (tabular → logistic/MLP)

| ชุดข้อมูล | partition | baseline | size | audit | model | รวม | ใช้ใน |
|---|---|---|---|---|---|---|---|
| Edge-IIoTset | 1 | 2 | 2 | 2 | 2 | **9** | PenTiDef (DFL + blockchain); BFLIDS (CNN 97.43%); Madni 2023 อ้างถึงใน related work [12] |
| TON_IoT | 1 | 2 | 2 | 2 | 2 | **9** | BFLIDS (CNN 98.21%) |
| IoT Crowdsensing DFL | 1 | 2 | 2 | 2 | 2 | **9** | Crowdsensing DFL dataset paper (ผลเทียบ ML/CFL/DFL ในตัว) |
| N-BaIoT | 2 | 1 | 1 | 2 | 2 | **8** | Explore.ipynb ของโปรเจกต์; งาน FL-autoencoder บน N-BaIoT |
| CICIoT2023 | 0 | 2 | 1 | 2 | 2 | **7** | FLBC-IDS (Hyperledger, 98.89%); B-FL Sci Rep 2026 (≈98%) |
| UNSW-NB15 | 0 | 2 | 2 | 1 | 2 | **7** | SIML (acc 93.7%, ไม่ใช่ SL); งาน IDS ทั่วไปจำนวนมาก |
| Kitsune | 1 | 2 | 1 | 1 | 2 | **7** | DOF-ID (decentralized online FL, ≥15% ดีกว่า baseline); N-BaIoT_Kitsune.ipynb ของโปรเจกต์ |
| CIC-IDS2018 | 0 | 2 | 1 | 1 | 2 | **6** | PenTiDef (DFL + blockchain); FLBC-IDS (Hyperledger) |
| BoT-IoT | 0 | 2 | 1 | 1 | 2 | **6** | DOF-ID (decentralized online FL); งาน FL IDS หลายงาน |
| CIC-IDS2017 | 0 | 2 | 1 | 1 | 2 | **6** | งาน IDS/FL จำนวนมาก |

### Edge-IIoTset — 9/10

IoT/IIoT testbed หลายชั้น (Ferrag et al. 2022, IEEE Access) · รุ่น ML ≈157k แถว · รุ่น DNN ≈2.2 ล้านแถว · 61 ฟีเจอร์ · label: normal + 14 การโจมตีใน 5 กลุ่ม

- partition: 1 — เก็บจากอุปกรณ์กว่า 10 ชนิด แต่ต้องตรวจไฟล์ว่ามีคอลัมน์ระบุอุปกรณ์ให้แบ่งได้หรือไม่
- baseline: 2 — ออกแบบมาเพื่อ 'centralized and federated learning' ตั้งแต่ชื่อ paper · มีงาน DFL + blockchain (PenTiDef) และ blockchain-FL (BFLIDS)
- size: 2 — รุ่น ML เล็กพอรันสบาย
- audit: 2 — IIoT ข้ามโรงงาน/ผู้ให้บริการ
- model: 2 — tabular

> ผู้สมัครอันดับสอง — ขนาดพอดีและมี baseline blockchain-FL ให้เทียบตรง

### TON_IoT — 9/10

telemetry ของเซนเซอร์ IoT/IIoT 7 ชนิด + network + OS log (UNSW Canberra) · ชุด train_test_network ≈460k แถว · label: normal + 9 การโจมตี (scanning, DoS, DDoS, ransomware, backdoor, injection, XSS, password, MITM)

- partition: 1 — แยกตามชนิดเซนเซอร์ได้ แต่แต่ละชนิดมี schema ต่างกัน = feature skew ใช้โมเดลเดียวยาก
- baseline: 2 — มีตัวเลข blockchain-FL
- size: 2 — ชุด network ขนาดพอดี
- audit: 2 — IIoT/สมาร์ทซิตี้
- model: 2 — tabular (ต้อง encode คอลัมน์ข้อความ)

> ดีถ้าใช้เฉพาะชุด network · ชุด telemetry เหมาะกับงาน vertical/heterogeneous FL มากกว่า

### IoT Crowdsensing DFL — 9/10

behavior ของอุปกรณ์ crowdsensing: system call, file, resource, kernel, I/O, network (Sci Data 2026) · 21.6 ล้าน record ดิบ → 342,106 หน้าต่าง 30 วินาที · label: benign + malware 8 ตระกูล

- partition: 1 — เก็บจากหลายอุปกรณ์และทดลองหลาย topology แต่ต้องตรวจไฟล์ว่ามีคอลัมน์ระบุอุปกรณ์หรือไม่
- baseline: 2 — มีผล DFL vs CFL ให้เทียบตรงกับ swarm
- size: 2 — 342k หน้าต่าง รันบนเครื่องเดียวได้
- audit: 2 — malware ข้ามผู้ให้บริการ crowdsensing
- model: 2 — tabular

> ชุดข้อมูลใหม่ที่ออกแบบมาเพื่อ decentralized FL โดยตรง — ผู้สมัครที่ควรโหลดมาสำรวจใน Explore.ipynb

### N-BaIoT — 8/10

network traffic ของอุปกรณ์ IoT จริง 9 ตัว · ≈7 ล้านแถว · 115 ฟีเจอร์ · แตกไฟล์แล้ว 6–7 GB · label: benign + BASHLITE (5 ชนิด) + Mirai (5 ชนิด)

- partition: 2 — อุปกรณ์ 1 ตัว = 1 โหนด โดยธรรมชาติ · 2 อุปกรณ์ไม่เคยเจอ Mirai = label skew จริง
- baseline: 1 — มีตัวเลข FL หลายงาน แต่ยังไม่เจองาน SL/blockchain โดยตรง
- size: 1 — ต้อง subsample ต่อโหนด
- audit: 2 — เหตุการณ์ botnet ข้ามองค์กร ต้องไล่ย้อนว่าใครส่งโมเดลอะไร
- model: 2 — ตัวเลข 115 คอลัมน์ ใช้ logistic/MLP ได้ทันที

> ผู้สมัครอันดับแรกสำหรับ sl-fabric — 9 โหนดแต่ Fabric มี 5 org ต้องจับคู่อุปกรณ์หรือเพิ่ม org

### CICIoT2023 — 7/10

อุปกรณ์ IoT 105 ตัว (CIC, UNB) · หลายสิบล้าน flow · 46 ฟีเจอร์ · label: benign + 33 การโจมตีใน 7 กลุ่ม

- partition: 0 — ไฟล์ CSV เรียงตามการโจมตี ไม่มีเจ้าของให้แบ่ง ต้องสุ่ม
- baseline: 2 — มีสองงาน blockchain-FL (หนึ่งใช้ Hyperledger) แต่ตัวเลข B-FL น่าสงสัย (centralized แพ้ FL)
- size: 1 — ใหญ่ ต้องใช้ subset
- audit: 2 — IoT หลายเจ้าของ
- model: 2 — tabular

> ใหม่และใหญ่ เหมาะเป็นชุดยืนยันผลรอบสอง

### UNSW-NB15 — 7/10

network traffic สังเคราะห์ใน cyber range (UNSW Canberra 2015) · 2.54 ล้าน record · 49 ฟีเจอร์ (ชุด train/test ทางการ ≈257k) · label: normal + 9 กลุ่มการโจมตี

- partition: 0 — ไม่มีเจ้าของข้อมูล
- baseline: 2 — baseline IDS มากที่สุดชุดหนึ่ง
- size: 2 — ชุด train/test ทางการเล็ก
- audit: 1 — เป็นเครือข่ายเดียว เรื่องเล่าข้ามองค์กรอ่อน
- model: 2 — tabular

> ดีสำหรับเทียบตัวเลขกับงาน IDS แต่ partition ต้องสังเคราะห์ (ปัญหาเดียวกับ CIC-IDS2017)

### Kitsune — 7/10

network capture จริง 9 สถานการณ์โจมตี (Mirsky et al. 2018) · 9 capture แยกไฟล์ · 115 ฟีเจอร์ AfterImage (ชุดเดียวกับ N-BaIoT) · label: 1 การโจมตีต่อ capture (ARP MitM, SSDP flood, Mirai, SYN DoS, …)

- partition: 1 — capture = โหนด ได้ แต่แต่ละโหนดเห็นการโจมตีชนิดเดียว — skew สุดขั้ว
- baseline: 2 — มีงาน decentralized FL โดยตรง (DOF-ID)
- size: 1 — บาง capture ใหญ่
- audit: 1 — -
- model: 2 — 115 ฟีเจอร์ตัวเลข ใช้ร่วมกับ N-BaIoT ได้

> ใช้เป็นชุดทดสอบข้ามโดเมนของโมเดลที่เทรนบน N-BaIoT

### CIC-IDS2018 — 6/10

network flow จาก AWS testbed ขององค์กรจำลอง (CIC, UNB) · ≈16 ล้าน flow · ราว 80 ฟีเจอร์ · label: benign + 7 กลุ่มการโจมตี (brute force, DoS, DDoS, web, infiltration, botnet)

- partition: 0 — ไม่มีเจ้าของข้อมูล แบ่งได้แค่ตามวัน/เครื่องใน testbed
- baseline: 2 — มีทั้ง DFL+blockchain และ FL+Hyperledger
- size: 1 — ใหญ่ ต้อง subsample
- audit: 1 — องค์กรเดียวใน testbed
- model: 2 — tabular

> baseline แข็งแรงแต่ partition ต้องสังเคราะห์ เหมือน CIC-IDS2017

### BoT-IoT — 6/10

botnet traffic ใน testbed (UNSW Canberra) · >72 ล้าน record · subset 5% ≈3.6 ล้าน · label: DDoS, DoS, reconnaissance, theft

- partition: 0 — ไม่มีเจ้าของ
- baseline: 2 — มีมาก
- size: 1 — ต้องใช้ subset 5%
- audit: 1 — เครือข่ายเดียว
- model: 2 — tabular

> class imbalance สุดขั้ว (benign น้อยมาก) ต้องระวังเวลาอ่าน accuracy

### CIC-IDS2017 — 6/10

network flow 5 วันทำงาน (CIC, UNB) · ≈2.8 ล้าน flow · ราว 80 ฟีเจอร์ · label: benign + การโจมตีต่างกันตามวัน

- partition: 0 — แบ่งตามวันได้ แต่แต่ละวันมีการโจมตีคนละชนิด ไม่ใช่เจ้าของ
- baseline: 2 — มีมาก
- size: 1 — ต้อง subsample
- audit: 1 — -
- model: 2 — tabular

> ปัญหาที่ Explore.ipynb ระบุไว้แล้ว: partition ต้องสังเคราะห์ เทียบข้าม paper ยาก

## 9 · ความเข้ากันได้กับสถาปัตยกรรม swarm learning — สรุป

| ชั้นของ SL | HPE SL (Nature 2021, Han 2022) | poc/sl-fabric | สิ่งที่ paper สาย cyber ชี้ว่ายังขาด |
|---|---|---|---|
| identity / onboarding | SPIFFE/SPIRE + X.509 + smart contract | X.509 ต่อ org ตรวจโดย MSP ของ peer | — |
| leader election | ไม่เปิดซอร์ส สงสัยว่าเป็น PoS, ภาระไม่เท่ากัน | sha256(round+members) mod n เปิดเผย ตรวจย้อนได้ | รู้ leader ล่วงหน้า → เป้าของ eclipse/DoS (Yang 2022) และ leader ประสงค์ร้าย (ZTA 2023) |
| merge | avg / weighted / min / max / median | FedAvg ถ่วงด้วยจำนวนตัวอย่าง | robust aggregation ต้าน backdoor/poisoning (Chen 2023, ZTA 2023, PenTiDef) |
| สิ่งที่อยู่บนเชน | metadata: สถานะโมเดล, ความคืบหน้า | hash ของ weight, ผู้ส่ง, leader, accuracy ต่อรอบ | ประวัติ update + trust score (PenTiDef, DSL) |
| ความลับของ parameter | ส่งดิบระหว่างโหนด | ส่งดิบ (นอกเชน) | HE/FHE (Swarm-FHE) หรือ distributed DP (PenTiDef, RFF-SL) |
| ผู้ร่วมขั้นต่ำ | min_peers | quorum ใน chaincode | timeout เมื่อ leader หาย |
