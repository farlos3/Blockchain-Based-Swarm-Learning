# Swarm learning กับ cybersecurity: paper, ชุดข้อมูล และผลลัพธ์

สร้างจาก `paper_review.py` — แก้ข้อมูลในสคริปต์แล้วรันใหม่ อย่าแก้ไฟล์นี้ตรง ๆ

ที่มาของตัวเลขแต่ละแถวบอกไว้ในคอลัมน์ “ที่มา”: ข้อความใน PDF (ตรวจอัตโนมัติ) · ภาพตารางใน PDF (คัดลอกด้วยตา) · อ่านจากกราฟ (ค่าประมาณ ±0.02) · เว็บ/บทคัดย่อ (ยังไม่ได้อ่านฉบับเต็ม เพราะเว็บของสำนักพิมพ์ถูกบล็อกจากเครื่องที่รัน)

## 0 · การจัดกลุ่ม

ข้อมูล cyber โดยตรง คือ network traffic, flow, packet capture, system/host log หรือ telemetry ที่มี label การโจมตี ภาพ ข้อความ และสัญญาณวิทยุไม่นับ แม้ paper จะศึกษาเรื่อง security ก็ตาม

- **A. swarm learning + ข้อมูล cyber โดยตรง** (1 ฉบับ) — กลุ่มหลัก: เป็น swarm learning จริง และเทรนบน traffic หรือ log
- **B. ข้อมูล cyber โดยตรง + สถาปัตยกรรมคล้าย SL** (10 ฉบับ) — กลุ่มรอง: IDS บนข้อมูล cyber ที่เทรนแบบ decentralized, ประสานด้วย blockchain หรือ federated แต่ไม่ใช่ SL ตรงตัว
- **X. ภาคผนวก: งาน SL ด้าน security ที่ไม่ได้ใช้ข้อมูล cyber** (9 ฉบับ) — ศึกษาการโจมตี/ป้องกันตัว SL หรือใช้ SL ในงานใกล้เคียง แต่ข้อมูลเป็นภาพ ข้อความ หรือสัญญาณวิทยุ — ไม่นับเป็นงานหลัก เก็บไว้เพราะยังให้แนวคิดด้านสถาปัตยกรรม
- **base. ภาคผนวก: พื้นฐานของ swarm learning** (3 ฉบับ) — paper ในโฟลเดอร์ `paper/` ที่นิยามและวัด SL แต่ใช้ข้อมูลการแพทย์/ทั่วไป

ข้อสังเกตหลัก: เท่าที่ค้นเจอ งาน swarm learning ที่เทรนบนข้อมูล cyber โดยตรงมีแค่ ADONIS งานเดียว และไม่มีงาน SL ใดใช้ชุดข้อมูล IDS มาตรฐาน (N-BaIoT, CIC-IDS, TON_IoT, Edge-IIoTset, CICIoT2023) หรือ system log เลย ชุดเหล่านี้ถูกใช้เฉพาะในงาน FL/DFL/blockchain-FL (กลุ่ม B) ช่องว่างนี้คือจุดที่ sl-fabric เติมได้โดยตรง

## 1 · ภาพรวม: paper × ชุดข้อมูล × ผล

| กลุ่ม | paper | ชุดข้อมูล | ประเภทข้อมูล | ผลเด่น |
|---|---|---|---|---|
| A | adonis2023 | traffic dataset (ตาม Table 5 ของ survey; ยังไม่รู้ชื่อชุดจริง) | network traffic ของ IoT | traffic ของ IoT: SL + knowledge distillation ตรวจพฤติกรรมคุกคาม (ยังไม่รู้ชื่อชุดข้อมูลและตัวเลข) |
| B | pentidef2026 | CIC-IDS2018, Edge-IIoTset | network flow | CIC-IDS2018 + Edge-IIoTset: DFL + DP + smart contract ชนะ FLARE/FedCC ทุกสถานการณ์โจมตี |
| B | dofid2023 | Kitsune, BoT-IoT | network traffic (packet features) | Kitsune + BoT-IoT: decentralized online FL แม่นกว่า baseline ≥15%, overhead 30 ms/โหนด |
| B | crowdsensing2026 | IoT Crowdsensing DFL dataset | host log (system call, file, kernel, I/O) + network | ชุดข้อมูล malware 8 ตระกูลที่ทำมาเพื่อ DFL โดยตรง; DFL ดีกว่า CFL เกือบทุกการตั้งค่า |
| B | flbcids2025 | CIC-IDS2018, CICIoT2023 | network flow | CIC-IDS2018 + CICIoT2023: accuracy 98.89% ด้วย FL + Hyperledger (ยังมี aggregator) |
| B | hbfl2022 | (ต้องดูฉบับเต็ม) | network traffic (ต้องยืนยันชื่อชุด) | เรื่องเล่า 'แชร์ threat intelligence ข้ามองค์กร' ตรงกับเหตุผลที่โปรเจกต์ต้องมี ledger |
| B | bflids2024 | Edge-IIoTset, TON_IoT | network traffic + IoT telemetry | Edge-IIoTset 97.43%, TON_IoT 98.21% (CNN) — blockchain-FL ไม่ใช่ SL |
| B | bfl2026 | CICIoT2023 | network flow | CICIoT2023: B-FL ≈98% vs FL ≈95% vs centralized ≈93% (centralized แพ้ผิดปกติ) |
| B | uavids2025 | UKM-IDS, UAV-IDS, TLM-UAV, Cyber-Physical | network traffic + UAV telemetry | 4 ชุด UAV IDS: 96.85–99.99% ด้วย federated continual learning (ไม่ใช่ SL) |
| B | fedlog2024 | HDFS, Thunderbird | system log (log-event sequence) | HDFS + Thunderbird: federated 1D-CNN บน system log (ยังมี server, ยังไม่ได้ตัวเลข) |
| B | swarmsense2026 | 5 benchmark datasets (ต้องดูฉบับเต็ม) | IoT traffic/telemetry (ต้องยืนยันชื่อชุด) | เฉลี่ย 5 ชุด: accuracy 95.44%, ลด communication 67% — decentralized แต่ไม่มี ledger |

## 2 · กลุ่ม A: swarm learning + ข้อมูล cyber โดยตรง

กลุ่มหลัก: เป็น swarm learning จริง และเทรนบน traffic หรือ log

### Swarm Learning and Knowledge Distillation Empowered Self-Driving Detection Against Threat Behavior for Intelligent IoT (ADONIS)

*-* · IEEE, 2023 · IEEE Xplore 10310124

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | web search |
| ความเกี่ยวกับ cybersecurity | หลัก — ตรวจพฤติกรรมคุกคามของอุปกรณ์ IoT จาก traffic |
| ลิงก์ | <https://ieeexplore.ieee.org/document/10310124/> |
| สรุปบทคัดย่อ | เสนอ ADONIS ระบบตรวจความผิดปกติเล็ก ๆ (minor anomaly) ของอุปกรณ์ IoT แบบโต้ตอบได้ ใช้ swarm learning รวมความรู้จากหลายโหนดโดยไม่รวมข้อมูล ใช้ knowledge distillation ย่อโมเดลให้อุปกรณ์เล็กรันได้ และให้คนช่วยแก้ label ผ่าน human–computer interaction |
| ชุดข้อมูล | traffic dataset (ตาม Table 5 ของ survey; ยังไม่รู้ชื่อชุดจริง) |
| รายละเอียดข้อมูล/การแบ่งโหนด | - |
| วิธี/โมเดล | SL + knowledge distillation + human-in-the-loop label refinement |
| การตั้งค่า SL | swarm learning (swarm defense) — ไม่มี server กลาง |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| ตามบทคัดย่อ/survey | - | ADONIS: ตรวจจับดีขึ้น ปกป้องความเป็นส่วนตัว ลด latency และลดความเสี่ยงจาก central node | เว็บ/บทคัดย่อ |

**ประเด็นสำคัญ**

- เป็นงาน SL ที่ใช้กับ network traffic ของ IoT โดยตรงงานหนึ่งในไม่กี่งานที่ค้นเจอ
- distillation ทำให้โมเดลเบาพอสำหรับอุปกรณ์ปลายทาง

**ช่องโหว่ / ข้อจำกัด**

- ไม่รู้ชื่อชุดข้อมูล จำนวนโหนด และตัวเลขผล — ต้องอ่านฉบับเต็ม
- ไม่ระบุว่าใช้ blockchain แบบไหน หรือใช้ HPE SL หรือเขียนเอง

**ความเข้ากันได้กับสถาปัตยกรรม SL** — สูง — เป็น SL ตรงตัว

**เทียบกับ `poc/sl-fabric`** — ยืนยันว่า SL กับ IDS จาก traffic ไปด้วยกันได้ · distillation ช่วยลดขนาด parameter ที่ต้อง hash และส่งทุกรอบ


## 3 · กลุ่ม B: ข้อมูล cyber โดยตรง + สถาปัตยกรรมคล้าย SL

กลุ่มรอง: IDS บนข้อมูล cyber ที่เทรนแบบ decentralized, ประสานด้วย blockchain หรือ federated แต่ไม่ใช่ SL ตรงตัว

### PenTiDef: Decentralized Federated Intrusion Detection System with Differential Privacy and Latent-Space Defense via Blockchain Coordination in IIoT

*-* · arXiv:2602.17973, 2026

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | web search |
| ความเกี่ยวกับ cybersecurity | หลัก — IDS สำหรับ IIoT ที่ทนต่อ poisoning |
| ลิงก์ | <https://arxiv.org/abs/2602.17973> |
| สรุปบทคัดย่อ | DFL-IDS ที่ไม่มี server กลางต้องทั้งรักษาความลับและทนต่อ poisoning PenTiDef ใช้ distributed differential privacy ใช้ latent space ของ neural network ตรวจ update ประสงค์ร้าย และใช้ blockchain + smart contract จัดการ aggregation เก็บประวัติ update และบังคับ trust |
| ชุดข้อมูล | CIC-IDS2018, Edge-IIoTset |
| รายละเอียดข้อมูล/การแบ่งโหนด | ทดลองหลายสถานการณ์การโจมตีและหลายแบบการกระจายข้อมูล |
| วิธี/โมเดล | DFL + distributed DP + latent-space representation defense |
| การตั้งค่า SL | decentralized FL ประสานด้วย blockchain smart contract — ใกล้ SL มากที่สุดในกลุ่มนี้ |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| CIC-IDS2018, Edge-IIoTset | ตามบทคัดย่อ | PenTiDef: ดีกว่า FLARE และ FedCC ในทุกสถานการณ์การโจมตีที่ทดสอบ | เว็บ/บทคัดย่อ |

**ประเด็นสำคัญ**

- รวม privacy (DP) กับ robustness (ตรวจ poisoning) ใน IDS แบบไม่มี server
- ใช้ smart contract ติดตามประวัติ update เหมือน ledger ของโปรเจกต์

**ช่องโหว่ / ข้อจำกัด**

- ยังไม่ได้ตัวเลข accuracy
- preprint ยังไม่ผ่าน peer review (ณ ที่ค้นเจอ)

**ความเข้ากันได้กับสถาปัตยกรรม SL** — สูง — แทบเป็น SL บน IDS: ไม่มี server, เชนประสาน, ตรวจ update

**เทียบกับ `poc/sl-fabric`** — ต้นแบบที่ใกล้ที่สุดสำหรับ sl-fabric บน Edge-IIoTset · เทียบ defense กับ FLARE/FedCC ได้ตรง

### Decentralized Online Federated G-Network Learning for Lightweight Intrusion Detection (DOF-ID)

*M. Nakıp, B. C. Gül, E. Gelenbe* · IEEE, 2023 · arXiv:2306.13029 · IEEE Xplore 10387644

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | web search |
| ความเกี่ยวกับ cybersecurity | หลัก — IDS แบบ online |
| ลิงก์ | <https://arxiv.org/abs/2306.13029> · <https://ieeexplore.ieee.org/document/10387644/> |
| สรุปบทคัดย่อ | ให้ IDS หลายตัวในระบบเรียนจากประสบการณ์ของกันและกันโดยไม่แชร์ข้อมูล ใช้โมเดล G-Network เทรนแบบ decentralized และ online (เรียนต่อเนื่องระหว่างใช้งาน) |
| ชุดข้อมูล | Kitsune, BoT-IoT |
| รายละเอียดข้อมูล/การแบ่งโหนด | Kitsune และ BoT-IoT ชุดสาธารณะ |
| วิธี/โมเดล | G-Network (random neural network) + decentralized online federated learning |
| การตั้งค่า SL | decentralized FL — ไม่มี server กลาง ไม่มี blockchain |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| Kitsune, BoT-IoT | ตามบทคัดย่อ | DOF-ID: accuracy สูงกว่าวิธีเทียบอย่างน้อย 15%; overhead: เวลาคำนวณเพิ่มเฉลี่ย 30 ms ต่อโหนดต่อรอบ federated update | เว็บ/บทคัดย่อ |

**ประเด็นสำคัญ**

- decentralized learning ช่วย IDS ได้มากเมื่อแต่ละโหนดเห็นการโจมตีต่างกัน
- overhead ต่ำพอสำหรับอุปกรณ์เล็ก

**ช่องโหว่ / ข้อจำกัด**

- ไม่มี ledger ตรวจสอบย้อนหลัง
- ตัวเลข +15% เทียบกับ baseline แบบไหนต้องดูฉบับเต็ม

**ความเข้ากันได้กับสถาปัตยกรรม SL** — กลาง — decentralized จริงแต่ไม่มีเชนและไม่มี leader

**เทียบกับ `poc/sl-fabric`** — Kitsune ใช้ฟีเจอร์ 115 ตัวแบบเดียวกับ N-BaIoT · ตัวเลข overhead 30 ms เทียบกับเวลาที่ ledger ของเราใช้ต่อรอบได้

### A Crowdsensing Intrusion Detection Dataset For Decentralized Federated Learning Models

*-* · Scientific Data, 2026 · arXiv:2507.13313

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | web search |
| ความเกี่ยวกับ cybersecurity | หลัก — malware detection ใน IoT crowdsensing |
| ลิงก์ | <https://arxiv.org/abs/2507.13313> · <https://www.nature.com/articles/s41597-026-07155-w> |
| สรุปบทคัดย่อ | เสนอชุดข้อมูลที่ออกแบบมาเพื่อ decentralized FL โดยตรง พร้อมผลเทียบ ML ทั่วไป, centralized FL และ DFL ในจำนวนโหนด topology และการกระจายข้อมูลต่าง ๆ |
| ชุดข้อมูล | IoT Crowdsensing DFL dataset |
| รายละเอียดข้อมูล/การแบ่งโหนด | benign + malware 8 ตระกูล · 21,582,484 record ดิบจาก system call, file system, resource usage, kernel event, I/O และ network · รวมเป็นหน้าต่าง 30 วินาทีได้ 342,106 ชุดข้อมูลสำหรับเทรน |
| วิธี/โมเดล | เทียบ ML / CFL / DFL บนแพลตฟอร์ม DFL |
| การตั้งค่า SL | DFL หลาย topology |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| ตามบทคัดย่อ | - | DFL vs CFL: DFL ได้ผลใกล้เคียงและดีกว่า CFL ในเกือบทุกการตั้งค่า | เว็บ/บทคัดย่อ |

**ประเด็นสำคัญ**

- เป็นชุดข้อมูล cyber ชุดเดียวที่เจอซึ่งออกแบบมาสำหรับ DFL และมีผลเทียบ CFL/DFL ในตัว

**ช่องโหว่ / ข้อจำกัด**

- เป็น host-based (system call ฯลฯ) ผสม network ไม่ใช่ network flow ล้วน
- ต้องตรวจว่าแบ่งโหนดตามอุปกรณ์จริงหรือไม่

**ความเข้ากันได้กับสถาปัตยกรรม SL** — สูงด้านข้อมูล — ออกแบบมาให้หลายโหนดเทรนร่วมกัน

**เทียบกับ `poc/sl-fabric`** — ผู้สมัครชุดข้อมูลใหม่ที่น่าสนใจ: มี baseline DFL ให้เทียบตรงกับ swarm ของเรา

### FLBC-IDS: a federated learning and blockchain-based intrusion detection system for secure IoT environments

*Govindaram, Jegatheesan* · Multimedia Tools and Applications, 2025

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | web search |
| ความเกี่ยวกับ cybersecurity | หลัก — IoT IDS |
| ลิงก์ | <https://link.springer.com/article/10.1007/s11042-024-19777-6> |
| สรุปบทคัดย่อ | รวม horizontal FL, Hyperledger blockchain และ EfficientNet ตรวจการบุกรุกใน IoT Hyperledger บันทึก model update และข้อตกลงระหว่างโหนดแบบแก้ไขไม่ได้ |
| ชุดข้อมูล | CIC-IDS2018, CICIoT2023 |
| รายละเอียดข้อมูล/การแบ่งโหนด | สองชุดข้อมูล network traffic |
| วิธี/โมเดล | horizontal FL + EfficientNet + Hyperledger |
| การตั้งค่า SL | FL + Hyperledger (มี aggregator) — ใช้ Hyperledger เหมือนโปรเจกต์ |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| CIC-IDS2018 + CICIoT2023 | ตามบทคัดย่อ | accuracy: 98.89%; recall: 98.044%; F1: 98.29%; precision: 98.44% | เว็บ/บทคัดย่อ |

**ประเด็นสำคัญ**

- ใช้ Hyperledger บันทึก update เหมือน sl-fabric

**ช่องโหว่ / ข้อจำกัด**

- ยังมี aggregator กลาง ไม่ใช่ SL
- รายงานตัวเลขรวมสองชุดข้อมูล ต้องดูแยก

**ความเข้ากันได้กับสถาปัตยกรรม SL** — กลาง

**เทียบกับ `poc/sl-fabric`** — baseline ตัวเลขบน CICIoT2023 จากระบบที่ใช้ Hyperledger เหมือนกัน

### HBFL: A Hierarchical Blockchain-based Federated Learning Framework for a Collaborative IoT Intrusion Detection

*M. Sarhan, W. W. Lo, S. Layeghy, M. Portmann* · Computers & Electrical Engineering, 2022 · arXiv:2204.04254

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | web search |
| ความเกี่ยวกับ cybersecurity | หลัก — แชร์ threat intelligence ข้ามองค์กร |
| ลิงก์ | <https://arxiv.org/abs/2204.04254> |
| สรุปบทคัดย่อ | หลายองค์กรอยากแชร์ความรู้เรื่องภัย IoT โดยไม่เปิดข้อมูล HBFL ใช้ FL แบบลำดับชั้น cloud–fog–edge model update และขั้นตอนทั้งหมดอยู่บน ledger และ smart contract ตรวจว่าแต่ละขั้นทำถูก |
| ชุดข้อมูล | (ต้องดูฉบับเต็ม) |
| รายละเอียดข้อมูล/การแบ่งโหนด | - |
| วิธี/โมเดล | hierarchical FL + blockchain + smart contract |
| การตั้งค่า SL | ลำดับชั้น (endpoint → combiner → reducer) ยังมีจุดรวมในแต่ละชั้น |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| ตามบทคัดย่อ | - | HBFL: IDS ตรวจการโจมตีได้หลากหลายโดยรักษาความเป็นส่วนตัวของข้อมูล | เว็บ/บทคัดย่อ |

**ประเด็นสำคัญ**

- เรื่องเล่า 'แชร์ threat intelligence ข้ามองค์กร' ตรงกับเหตุผลที่โปรเจกต์ต้องมี ledger

**ช่องโหว่ / ข้อจำกัด**

- ยังไม่รู้ชุดข้อมูลและตัวเลข

**ความเข้ากันได้กับสถาปัตยกรรม SL** — กลาง — มีเชนและ smart contract แต่ยังเป็นลำดับชั้น

**เทียบกับ `poc/sl-fabric`** — ใช้อ้างเหตุผลเชิงองค์กรของ ledger ในบทนำวิทยานิพนธ์ได้

### BFLIDS: Blockchain-Driven Federated Learning for Intrusion Detection in IoMT Networks

*Begum, Mozumder, et al.* · Sensors (MDPI) 24(14):4591, 2024

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | web search |
| ความเกี่ยวกับ cybersecurity | หลัก — IDS สำหรับ Internet of Medical Things |
| ลิงก์ | <https://www.mdpi.com/1424-8220/24/14/4591> |
| สรุปบทคัดย่อ | IDS แบบรวมศูนย์ขัดกับความเป็นส่วนตัวของอุปกรณ์การแพทย์ จึงใช้ FL + blockchain + IPFS |
| ชุดข้อมูล | Edge-IIoTset, TON_IoT |
| รายละเอียดข้อมูล/การแบ่งโหนด | สองชุดข้อมูล IIoT/IoT ที่มี label การโจมตี |
| วิธี/โมเดล | adaptive max-pooling CNN และ BiLSTM + attention · FedAvg ดัดแปลงด้วย KL divergence + adaptive weight |
| การตั้งค่า SL | blockchain เก็บบันทึก + IPFS เก็บโมเดล — ยังมีจุดรวม |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| FL scenario | accuracy | CNN · Edge-IIoTset: 97.43%; BiLSTM · Edge-IIoTset: 96.02%; CNN · TON_IoT: 98.21%; BiLSTM · TON_IoT: 97.42% | เว็บ/บทคัดย่อ |

**ประเด็นสำคัญ**

- ผลใกล้ centralized ตามที่ผู้เขียนรายงาน

**ช่องโหว่ / ข้อจำกัด**

- ไม่ใช่ SL — ใช้เป็น baseline ฝั่ง blockchain-FL

**ความเข้ากันได้กับสถาปัตยกรรม SL** — กลาง

**เทียบกับ `poc/sl-fabric`** — แยก ledger (หลักฐาน) ออกจาก storage (IPFS) เหมือนที่โปรเจกต์แยก hash ออกจาก weight

### A blockchain-assisted secure federated learning architecture for intrusion detection in internet of things networks (B-FL)

*-* · Scientific Reports, 2026 · doi:10.1038/s41598-026-53053-x

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | web search |
| ความเกี่ยวกับ cybersecurity | หลัก — IoT IDS |
| ลิงก์ | <https://www.nature.com/articles/s41598-026-53053-x> |
| สรุปบทคัดย่อ | IDS แบบ federated ที่ต้องไว้ใจ aggregator และขาด audit จึงเพิ่ม blockchain |
| ชุดข้อมูล | CICIoT2023 |
| รายละเอียดข้อมูล/การแบ่งโหนด | CICIoT2023 เป็น benchmark หลัก |
| วิธี/โมเดล | blockchain-enabled secure FL |
| การตั้งค่า SL | blockchain-assisted FL |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| CICIoT2023 | accuracy (ตามผลค้น) | B-FL: ≈98%; FL: ≈95%; centralized: ≈93%; ML ทั่วไป: ≈90% | เว็บ/บทคัดย่อ |

**ประเด็นสำคัญ**

- รายงานว่า B-FL ดีกว่าทั้ง FL และ centralized

**ช่องโหว่ / ข้อจำกัด**

- centralized แพ้ FL เป็นเรื่องผิดปกติ ต้องดู setup ในฉบับเต็มก่อนอ้าง

**ความเข้ากันได้กับสถาปัตยกรรม SL** — กลาง

**เทียบกับ `poc/sl-fabric`** — baseline บน CICIoT2023

### An Efficient Privacy-preserving Intrusion Detection Scheme for UAV Swarm Networks

*Gharami, Moni* · AIAA/IEEE DASC 2025 · arXiv:2511.22791 · โค้ด github.com/SPIRE-Lab-2025/UAV-IDS-FL

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | web search |
| ความเกี่ยวกับ cybersecurity | หลัก — IDS สำหรับฝูงโดรน |
| ลิงก์ | <https://arxiv.org/abs/2511.22791> |
| สรุปบทคัดย่อ | ฝูง UAV ถูกโจมตีได้หลายแบบ จึงเสนอ IDS แบบ federated continuous learning ที่เบา เทรนกระจายข้ามฝูงโดยไม่แชร์ข้อมูล |
| ชุดข้อมูล | UKM-IDS, UAV-IDS, TLM-UAV, Cyber-Physical |
| รายละเอียดข้อมูล/การแบ่งโหนด | 4 ชุดข้อมูลการบุกรุกของ UAV/เครือข่าย |
| วิธี/โมเดล | federated continuous learning + สถาปัตยกรรมสามส่วนรองรับข้อมูลต่างชนิด |
| การตั้งค่า SL | FL (มีการรวมโมเดล) — คำว่า swarm หมายถึงฝูงโดรน ไม่ใช่ swarm learning |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| accuracy | ตามบทคัดย่อ | UKM-IDS: 99.45%; UAV-IDS: 99.99%; TLM-UAV: 96.85%; Cyber-Physical: 98.05% | เว็บ/บทคัดย่อ |

**ประเด็นสำคัญ**

- เปิดโค้ดบน GitHub ทำซ้ำได้

**ช่องโหว่ / ข้อจำกัด**

- ไม่ใช่ SL และไม่มี blockchain
- 99.99% บน UAV-IDS บอกว่าชุดนั้นง่ายเกินจะแยกวิธี

**ความเข้ากันได้กับสถาปัตยกรรม SL** — ต่ำ–กลาง

**เทียบกับ `poc/sl-fabric`** — ใช้เป็นตัวอย่าง continual learning บน IDS ได้

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
- ยังไม่ได้ตัวเลข

**ความเข้ากันได้กับสถาปัตยกรรม SL** — ต่ำ–กลาง — ข้อมูลตรงโจทย์ แต่สถาปัตยกรรมยังรวมศูนย์

**เทียบกับ `poc/sl-fabric`** — ถ้าจะทำ SL บน log ต้องเปลี่ยน client เป็นโมเดลลำดับ (1D-CNN/LSTM) · ใช้เป็น baseline FL บน log ได้

### SwarmSense-DNN: A Trustworthy and Decentralized Neural Framework for Proactive Anomaly Defense in Consumer IoT

*-* · arXiv:2606.11803 / IEEE, มิ.ย. 2026

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | web search |
| ความเกี่ยวกับ cybersecurity | หลัก — consumer IoT anomaly detection |
| ลิงก์ | <https://arxiv.org/abs/2606.11803> |
| สรุปบทคัดย่อ | ตรวจความผิดปกติใน IoT ผู้บริโภคแบบ real-time โดยไม่มีจุดศูนย์กลาง ประสานงานแบบ pheromone (swarm intelligence) |
| ชุดข้อมูล | 5 benchmark datasets (ต้องดูฉบับเต็ม) |
| รายละเอียดข้อมูล/การแบ่งโหนด | - |
| วิธี/โมเดล | hierarchical FL + GNN + attention · pheromone-inspired coordination · differential privacy |
| การตั้งค่า SL | decentralized แต่ไม่ได้ใช้ blockchain ตามบทคัดย่อ |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| เฉลี่ย 5 ชุดข้อมูล | จากบทคัดย่อ | accuracy: 95.44%; precision: 94.87%; recall: 96.12%; AUC: 0.967; communication overhead: ลดลง 67% | เว็บ/บทคัดย่อ |

**ประเด็นสำคัญ**

- ทน node failure และ AI-enabled attack ตามการทดลองของผู้เขียน

**ช่องโหว่ / ข้อจำกัด**

- เป็น swarm intelligence + FL ไม่ใช่ SL แบบ HPE
- ยังไม่รู้ว่า 5 ชุดข้อมูลคืออะไร

**ความเข้ากันได้กับสถาปัตยกรรม SL** — กลาง — decentralized จริงแต่ไม่มี ledger

**เทียบกับ `poc/sl-fabric`** — ตัวเลข 95.44% ใช้เป็นเป้าเทียบคร่าว ๆ ได้หากชุดข้อมูลตรงกัน


## 4 · ภาคผนวก: งาน SL ด้าน security ที่ไม่ได้ใช้ข้อมูล cyber

ศึกษาการโจมตี/ป้องกันตัว SL หรือใช้ SL ในงานใกล้เคียง แต่ข้อมูลเป็นภาพ ข้อความ หรือสัญญาณวิทยุ — ไม่นับเป็นงานหลัก เก็บไว้เพราะยังให้แนวคิดด้านสถาปัตยกรรม

| paper | ชุดข้อมูล | ประเภทข้อมูล | ใช้ประโยชน์อะไรได้ | ลิงก์ |
|---|---|---|---|---|
| Blockchain-Based Swarm Learning for the Mitigation of Gradient Leakage in Federated Learning | CIFAR-10, MNIST | ภาพ | ตั้งการทดลองเหมือนโปรเจกต์: Dirichlet(α) แบ่ง non-IID (โปรเจกต์ใช้ α=0.5 บน BloodMNIST), FedAvg, โหนดเดี่ยว vs swarm · ต่างกันตรงที่ ledger ของโปรเจกต์เก็บ hash ของ weight (commit) แต่ weight ยังส่งกันนอกเชน จึงติดข้อจำกัดเดียวกันว่า leader เห็น weight ดิบ · ถ้าจะอ้างเรื่อง gradient leakage ต้องทดลองโจมตีจริง หรือเพิ่ม secure aggregation / HE (ดู Swarm-FHE) — เป็นช่องว่างที่ paper นี้ทิ้งไว้และโปรเจกต์เติมได้ | `paper/Blockchain-Based_Swarm_Learning_for_the_Mitigation_of_Gradient_Leakage_in_Federated_Learning.pdf` |
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
| Demystifying Swarm Learning: A New Paradigm of Blockchain-based Decentralized Federated Learning | NIH ChestX-ray, CIFAR-10, IMDB | ภาพ X-ray, ภาพ, ข้อความรีวิว | โปรเจกต์ใช้ leader rule แบบ deterministic `sha256(round + members) mod n` ซึ่งตรวจสอบย้อนหลังได้และกระจายสม่ำเสมอ ตอบข้อติของ paper นี้ตรง ๆ — วัดได้ทันทีด้วย `leader_counts()` และ `hostmetrics.py` ของ sl-fabric · `min_peers` ของ HPE = `quorum` ของ chaincode · RQ4 ชี้ว่าต้องมี robust aggregation (โปรเจกต์ยังไม่มี) · ข้อเสียของ rule แบบ deterministic คือรู้ล่วงหน้าว่าใครเป็น leader รอบถัดไป ผู้โจมตีเล็งเป้าได้ | `paper/2201.05286v2.pdf` |
| Swarm Learning for decentralized and confidential clinical machine learning | GEO (GSE…), NIH ChestX-ray, COVID-19 blood transcriptomes (EGA) | transcriptome + ภาพ X-ray | ข้อมูลเป็น tabular มิติสูง + dense NN ซึ่งเข้ากับ interface 'flat parameter vector' ของ client ในโปรเจกต์พอดี · สิ่งที่โปรเจกต์ทำตรงกับ SL ต้นฉบับ: permissioned chain, leader หมุนเวียน, สิทธิ์ merge เท่ากัน, weight ไม่ขึ้นเชน · สิ่งที่ต่าง: โปรเจกต์ใช้ Fabric + MAJORITY endorsement แทน Ethereum ของ HPE และเปิดซอร์ส leader rule ได้ · ข้อมูลเป็นสายการแพทย์ ไม่ใช่ cyber — ใช้เป็นแม่แบบการออกแบบ scenario (prevalence ต่ำ, แยกตามแหล่ง) กับชุด cyber ได้ | `paper/s41586-021-03583-3.pdf` |
| Swarm Learning: A Survey of Concepts, Applications, and Trends | (survey — รวบรวมจากงานอื่น) | survey (ไม่มีข้อมูลของตัวเอง) | ภัยที่โปรเจกต์กันได้แล้ว: ปลอมตัวเป็นโหนดอื่น (MSP identity), ส่งซ้ำ, non-leader ปิดรอบ, แก้รอบที่ปิดแล้ว (append-only) · ภัยที่ยังเปิด: backdoor/poisoning (ไม่มี robust aggregation), inference/model inversion (leader เห็น weight ดิบ), eclipse (ใน PoC ทุกโหนดอยู่ process เดียว) · ใช้บทที่ 5 เป็นโครง threat model ของวิทยานิพนธ์ได้ตรง ๆ | `paper/2405.00556v2.pdf` |

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
