# Swarm learning กับ cybersecurity: paper, ชุดข้อมูล และผลลัพธ์

สร้างจาก `paper_review.py` — แก้ข้อมูลในสคริปต์แล้วรันใหม่ อย่าแก้ไฟล์นี้ตรง ๆ

ที่มาของตัวเลขแต่ละแถวบอกไว้ในคอลัมน์ “ที่มา”: ข้อความใน PDF (ตรวจอัตโนมัติ) · ภาพตารางใน PDF (คัดลอกด้วยตา) · อ่านจากกราฟ (ค่าประมาณ ±0.02) · เว็บ/บทคัดย่อ (ยังไม่ได้อ่านฉบับเต็ม เพราะเว็บของสำนักพิมพ์ถูกบล็อกจากเครื่องที่รัน)

## 0 · การจัดกลุ่ม

- **A. swarm learning + ชุดข้อมูลสาย cyber** (3 ฉบับ) — กลุ่มหลัก: เป็น swarm learning จริง และทดลองกับข้อมูลด้าน security (traffic, RF fingerprint, ข่าวปลอม)
- **B. swarm learning ในงาน security (ข้อมูลไม่ใช่ cyber)** (7 ฉบับ) — โจมตีหรือป้องกันตัว SL เอง เช่น backdoor, eclipse, poisoning, gradient leakage แต่ทดลองบนภาพ benchmark
- **C. ชุดข้อมูล cyber + สถาปัตยกรรมคล้าย SL** (9 ฉบับ) — กลุ่มรอง: IDS บนชุดข้อมูล cyber มาตรฐาน ที่เทรนแบบ decentralized หรือใช้ blockchain ประสาน แต่ไม่ใช่ SL ตรงตัว
- **base. พื้นฐานของ swarm learning (ไม่ใช่ cyber)** (3 ฉบับ) — paper ในโฟลเดอร์ `paper/` ที่นิยามและวัด SL แต่ใช้ข้อมูลการแพทย์/ทั่วไป

ข้อสังเกตหลัก: เท่าที่ค้นเจอ งาน swarm learning ที่ทดลองบนชุดข้อมูล IDS มาตรฐาน (N-BaIoT, CIC-IDS, TON_IoT, Edge-IIoTset, CICIoT2023) ยังไม่มีเลย งานที่ใช้ชุดเหล่านี้ล้วนเป็น FL/DFL/blockchain-FL (กลุ่ม C) ช่องว่างนี้คือจุดที่ sl-fabric เติมได้โดยตรง

## 1 · ภาพรวม: paper × ชุดข้อมูล × ผล

| กลุ่ม | paper | แหล่ง | ชุดข้อมูล | ผลเด่น |
|---|---|---|---|---|
| A | adonis2023 | เว็บ | traffic dataset (ตาม Table 5 ของ survey; ยังไม่รู้ชื่อชุดจริง) | traffic ของ IoT: SL + knowledge distillation ตรวจพฤติกรรมคุกคาม (ยังไม่รู้ชื่อชุดข้อมูลและตัวเลข) |
| A | rff2023 | เว็บ | RFF dataset | RF fingerprint: SL + differential privacy ยืนยันตัวตนอุปกรณ์ ความเป็นส่วนตัวสูงขึ้น precision ลดลงเล็กน้อย |
| A | hbsl2022 | เว็บ | LIAR | LIAR: SL + feedback ของผู้ใช้ ดีกว่า SL เดิมอย่างมีนัยสำคัญทุกโหนด |
| B | madni2023 | เครื่อง | CIFAR-10, MNIST | SL ชนะ baseline FL+defense ทั้ง 4 ตัวทุกค่า α บน CIFAR-10 (ResNet18 α=10: 73.17 vs ดีสุด 68.96 ของ BLUR+LUS) |
| B | chen2023backdoor | เว็บ | MNIST, CIFAR-10, SVHN | เป็นงานแรก ๆ ที่วัด backdoor กับ SL โดยตรงและเสนอการป้องกันที่ไม่ต้องมี server |
| B | yang2022sse | เว็บ | (ต้องดูฉบับเต็ม) | ชั้นเครือข่ายของเชนเป็นพื้นผิวโจมตีของโมเดลได้ ไม่ใช่แค่ของ ledger |
| B | zta2023 | เว็บ | (ต้องดูฉบับเต็ม) | เป็นงานเดียวที่ค้นเจอซึ่งมองว่า leader เองคือผู้โจมตี |
| B | swarmfhe2023 | เว็บ | CIFAR-10, MNIST | ปิดช่องโหว่ที่ Madni 2023 ทิ้งไว้ (leader เห็น gradient ดิบ) |
| B | masl2023 | เว็บ | GTSRB (ตาม Table 3 ของ survey) | แนวคิด SL สองชั้นช่วยเรื่อง non-IID และการขยายขนาด |
| B | dsl2023 | เว็บ | GTSRB (ตาม Table 3 ของ survey) | ตรวจผู้ร่วมประสงค์ร้ายจากพฤติกรรมบนเชน (confirmation rate) ไม่ต้องดูข้อมูลดิบ |
| C | pentidef2026 | เว็บ | CIC-IDS2018, Edge-IIoTset | CIC-IDS2018 + Edge-IIoTset: DFL + DP + smart contract ชนะ FLARE/FedCC ทุกสถานการณ์โจมตี |
| C | dofid2023 | เว็บ | Kitsune, BoT-IoT | Kitsune + BoT-IoT: decentralized online FL แม่นกว่า baseline ≥15%, overhead 30 ms/โหนด |
| C | crowdsensing2026 | เว็บ | IoT Crowdsensing DFL dataset | ชุดข้อมูล malware 8 ตระกูลที่ทำมาเพื่อ DFL โดยตรง; DFL ดีกว่า CFL เกือบทุกการตั้งค่า |
| C | flbcids2025 | เว็บ | CIC-IDS2018, CICIoT2023 | CIC-IDS2018 + CICIoT2023: accuracy 98.89% ด้วย FL + Hyperledger (ยังมี aggregator) |
| C | hbfl2022 | เว็บ | (ต้องดูฉบับเต็ม) | เรื่องเล่า 'แชร์ threat intelligence ข้ามองค์กร' ตรงกับเหตุผลที่โปรเจกต์ต้องมี ledger |
| C | bflids2024 | เว็บ | Edge-IIoTset, TON_IoT | Edge-IIoTset 97.43%, TON_IoT 98.21% (CNN) — blockchain-FL ไม่ใช่ SL |
| C | bfl2026 | เว็บ | CICIoT2023 | CICIoT2023: B-FL ≈98% vs FL ≈95% vs centralized ≈93% (centralized แพ้ผิดปกติ) |
| C | uavids2025 | เว็บ | UKM-IDS, UAV-IDS, TLM-UAV, Cyber-Physical | 4 ชุด UAV IDS: 96.85–99.99% ด้วย federated continual learning (ไม่ใช่ SL) |
| C | swarmsense2026 | เว็บ | 5 benchmark datasets (ต้องดูฉบับเต็ม) | เฉลี่ย 5 ชุด: accuracy 95.44%, ลด communication 67% — decentralized แต่ไม่มี ledger |
| base | han2022 | เครื่อง | NIH ChestX-ray, CIFAR-10, IMDB | SL แม่นใกล้ CL ในเกือบทุกสถานการณ์ และบางกรณีสูงกว่า (Task A 0.9090 vs 0.8850) |
| base | warnat2021 | เครื่อง | GEO (GSE…), NIH ChestX-ray, COVID-19 blood transcriptomes (EGA) | SL ชนะทุกโหนดเดี่ยวอย่างมีนัยสำคัญในทุก use case และใกล้เคียงหรือเท่ากับ central model |
| base | shammar2025 | เครื่อง | (survey — รวบรวมจากงานอื่น) | ภัยต่อ SL แบ่งตามช่วง: data poisoning ตอนเทรนท้องถิ่น · eclipse/DDoS ตอนอัปโหลด metadata บน P2P · backdoor ตอน merge |

## 2 · กลุ่ม A: swarm learning + ชุดข้อมูลสาย cyber

กลุ่มหลัก: เป็น swarm learning จริง และทดลองกับข้อมูลด้าน security (traffic, RF fingerprint, ข่าวปลอม)

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

### Improved Swarm Learning with Differential Privacy for Radio Frequency Fingerprinting

*-* · IEEE, 2023 · IEEE Xplore 10211163

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | web search |
| ความเกี่ยวกับ cybersecurity | หลัก — physical-layer authentication ของอุปกรณ์ IoT |
| ลิงก์ | <https://ieeexplore.ieee.org/document/10211163/> |
| สรุปบทคัดย่อ | RF fingerprint ใช้ยืนยันตัวตนอุปกรณ์ IoT ได้ แต่ข้อมูลสัญญาณรั่วได้ ผู้เขียนเติม differential privacy ให้ SL และออกแบบวิธีประเมินอุปกรณ์ประสงค์ร้าย เพื่อกันข้อมูล RFF รั่ว โดยยอมเสียความแม่นยำเล็กน้อย |
| ชุดข้อมูล | RFF dataset |
| รายละเอียดข้อมูล/การแบ่งโหนด | - |
| วิธี/โมเดล | SL + differential privacy + malicious device evaluation |
| การตั้งค่า SL | swarm learning |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| ตามบทคัดย่อ | - | SL+DP: ความเป็นส่วนตัวสูงขึ้น แลกกับ precision ที่ลดลงเล็กน้อย | เว็บ/บทคัดย่อ |

**ประเด็นสำคัญ**

- ใช้ DP ร่วมกับ SL ซึ่งสวนทางกับ Madni 2023 ที่อ้างว่า SL ไม่ต้องใช้ DP
- มีกลไกคัดอุปกรณ์ประสงค์ร้ายออกจาก swarm

**ช่องโหว่ / ข้อจำกัด**

- ไม่รู้ชื่อชุด RFF จำนวนอุปกรณ์ และค่า ε ของ DP
- ข้อมูลเป็น IQ sample ไม่ใช่ network traffic

**ความเข้ากันได้กับสถาปัตยกรรม SL** — สูง — SL + DP

**เทียบกับ `poc/sl-fabric`** — client ตอนนี้รับ tabular ต้องเพิ่ม CNN 1D ถ้าจะใช้ · ใช้อ้างเรื่องเติม DP ให้ swarm ได้

### Integrating Human-in-the-loop into Swarm Learning for Decentralized Fake News Detection (HBSL)

*X. Dong, S. Sarker, L. Qian* · IDSTA 2022 · arXiv:2201.02048 · IEEE Xplore 9923043

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | web search |
| ความเกี่ยวกับ cybersecurity | รอง — information security (ข่าวปลอม/misinformation) |
| ลิงก์ | <https://arxiv.org/abs/2201.02048> · <https://ieeexplore.ieee.org/document/9923043/> |
| สรุปบทคัดย่อ | ระบบตรวจข่าวปลอมแบบรวมศูนย์ต้องเก็บข้อมูลผู้ใช้ไว้ที่เดียว และใช้ feedback ของผู้ใช้ไม่ได้เต็มที่ HBSL ให้ผู้ใช้แต่ละโหนดให้ feedback กับผลทำนาย แล้วโหนดนำ feedback มาขยายชุดเทรนและ fine-tune โมเดลต่อใน swarm |
| ชุดข้อมูล | LIAR |
| รายละเอียดข้อมูล/การแบ่งโหนด | LIAR: ข้อความสั้นพร้อม label ความจริง 6 ระดับ (benchmark fake news) |
| วิธี/โมเดล | swarm learning + human-in-the-loop feedback |
| การตั้งค่า SL | swarm learning แบบกระจายหลายโหนด |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| LIAR | ตามบทคัดย่อ | HBSL vs SL: HBSL ดีขึ้นอย่างมีนัยสำคัญในทุกโหนด | เว็บ/บทคัดย่อ |

**ประเด็นสำคัญ**

- แสดงว่า SL รับข้อมูลใหม่จากผู้ใช้เข้ามาเทรนต่อได้เรื่อย ๆ (continual)

**ช่องโหว่ / ข้อจำกัด**

- ข้อมูลเป็นข้อความ ไม่ใช่ network/IoT
- ไม่รู้ตัวเลขผลและจำนวนโหนด

**ความเข้ากันได้กับสถาปัตยกรรม SL** — สูง — SL ตรงตัว

**เทียบกับ `poc/sl-fabric`** — ต่ำสำหรับ IDS · ไอเดียเรื่อง feedback loop ใช้กับการติด label ทราฟฟิกที่ SOC ยืนยันแล้วได้


## 3 · กลุ่ม B: swarm learning ในงาน security (ข้อมูลไม่ใช่ cyber)

โจมตีหรือป้องกันตัว SL เอง เช่น backdoor, eclipse, poisoning, gradient leakage แต่ทดลองบนภาพ benchmark

### Blockchain-Based Swarm Learning for the Mitigation of Gradient Leakage in Federated Learning

*H. A. Madni, R. M. Umer, G. L. Foresti* · IEEE Access vol. 11, pp. 16549–16556, 2023 · doi:10.1109/ACCESS.2023.3246126

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | ไฟล์ใน `paper/` |
| ความเกี่ยวกับ cybersecurity | หลัก — privacy attack (gradient leakage / gradient inversion) |
| ลิงก์ | `paper/Blockchain-Based_Swarm_Learning_for_the_Mitigation_of_Gradient_Leakage_in_Federated_Learning.pdf` |
| สรุปบทคัดย่อ | FL ส่ง gradient ให้ server กลาง ซึ่งถูกกู้ข้อมูลดิบกลับได้ด้วย DLG, GGL, GradInversion การป้องกันแบบ DP/perturbation ทำให้ความแม่นยำตก ผู้เขียนเสนอว่า SL ส่ง gradient จริง ให้เฉพาะโหนดที่ยืนยันตัวตนผ่าน smart contract แล้ว จึงไม่ต้องเติม noise |
| ชุดข้อมูล | CIFAR-10, MNIST |
| รายละเอียดข้อมูล/การแบ่งโหนด | CIFAR-10: 60,000 ภาพสี 32×32, 10 คลาส (train 50k / test 10k) · MNIST: 70,000 ภาพเทา 28×28 (train 60k / test 10k) · แบ่ง train ให้ 4 โหนดเท่ากัน แบบ non-IID ด้วย Dirichlet(α) α ∈ {0.1, 1, 10, 50, 100} · ทดสอบด้วย test set กลางที่คลาสสมดุล |
| วิธี/โมเดล | ResNet18 (pre-trained) และ CNN-2 · PyTorch · รวมโมเดลด้วย FedAvg ที่ sentinel node ซึ่งสุ่มเลือกทุกรอบ · วัดด้วย accuracy · ทำซ้ำ 4 รอบต่อ α รายงาน mean ± std |
| การตั้งค่า SL | HPE Swarm Learning ของจริง: 1 SN, 1 SWOP, 4 ML node, 4 SL node, SWCI, HPE license server บนโหนด sentinel · Ubuntu 22.04, i7-8700, RAM 50 GB ต่อโหนด · เชื่อมกันด้วย SSH + certificate |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| CIFAR-10 · CNN-2 · Dir(α=0.1) | accuracy % | DDGauss: 53.55±1.12; DP-FedAvg: 53.84±1.04; BLUR+LUS: 58.95±0.95; AE-DPFL: 55.79±0.86; SL (ของผู้เขียน): 59.22±0.47 | ภาพตารางใน PDF |
| CIFAR-10 · CNN-2 · Dir(α=1) | accuracy % | DDGauss: 58.28±0.96; DP-FedAvg: 58.67±0.85; BLUR+LUS: 63.74±0.70; AE-DPFL: 60.00±0.57; SL (ของผู้เขียน): 66.85±0.61 | ภาพตารางใน PDF |
| CIFAR-10 · CNN-2 · Dir(α=10) | accuracy % | DDGauss: 62.43±0.77; DP-FedAvg: 62.25±0.71; BLUR+LUS: 65.34±0.52; AE-DPFL: 63.93±0.45; SL (ของผู้เขียน): 67.26±0.51 | ภาพตารางใน PDF |
| CIFAR-10 · CNN-2 · Dir(α=100) | accuracy % | DDGauss: 63.80±0.69; DP-FedAvg: 63.73±0.64; BLUR+LUS: 66.05±0.45; AE-DPFL: 64.51±0.40; SL (ของผู้เขียน): 68.93±0.28 | ภาพตารางใน PDF |
| CIFAR-10 · ResNet18 · Dir(α=0.1) | accuracy % | DDGauss: 59.37±1.04; DP-FedAvg: 59.73±0.96; BLUR+LUS: 64.50±0.88; AE-DPFL: 63.11±0.65; SL (ของผู้เขียน): 66.48±0.26 | ภาพตารางใน PDF |
| CIFAR-10 · ResNet18 · Dir(α=1) | accuracy % | DDGauss: 63.84±0.89; DP-FedAvg: 63.49±0.81; BLUR+LUS: 67.27±0.62; AE-DPFL: 65.80±0.51; SL (ของผู้เขียน): 71.70±0.19 | ภาพตารางใน PDF |
| CIFAR-10 · ResNet18 · Dir(α=10) | accuracy % | DDGauss: 65.85±0.72; DP-FedAvg: 65.64±0.69; BLUR+LUS: 68.96±0.54; AE-DPFL: 67.62±0.42; SL (ของผู้เขียน): 73.17±0.17 | ภาพตารางใน PDF |
| CIFAR-10 · ResNet18 · Dir(α=100) | accuracy % | DDGauss: 66.74±0.63; DP-FedAvg: 66.58±0.60; BLUR+LUS: 69.42±0.47; AE-DPFL: 68.39±0.35; SL (ของผู้เขียน): 73.08±0.07 | ภาพตารางใน PDF |
| CIFAR-10 · ResNet18 · Dir(α=0.1) | accuracy % | node 1/2/3/4 (แยกเทรน): 55.18 / 52.12 / 49.78 / 52.21; SWARM: 66.48±0.26 | ภาพตารางใน PDF |
| CIFAR-10 · ResNet18 · Dir(α=1) | accuracy % | node 1/2/3/4 (แยกเทรน): 61.25 / 59.87 / 58.97 / 59.92; SWARM: 71.70±0.19 | ภาพตารางใน PDF |
| CIFAR-10 · ResNet18 · Dir(α=10) | accuracy % | node 1/2/3/4 (แยกเทรน): 65.74 / 64.27 / 65.48 / 64.22; SWARM: 73.17±0.17 | ภาพตารางใน PDF |
| CIFAR-10 · ResNet18 · Dir(α=50) | accuracy % | node 1/2/3/4 (แยกเทรน): 64.85 / 65.08 / 65.33 / 64.84; SWARM: 73.15±0.21 | ภาพตารางใน PDF |
| CIFAR-10 · ResNet18 · Dir(α=100) | accuracy % | node 1/2/3/4 (แยกเทรน): 65.34 / 65.55 / 65.42 / 64.84; SWARM: 73.08±0.07 | ภาพตารางใน PDF |
| CIFAR-10 · CNN-2 · Dir(α=0.1) | accuracy % | node 1/2/3/4 (แยกเทรน): 46.76 / 46.10 / 48.04 / 48.30; SWARM: 59.22±0.47 | ภาพตารางใน PDF |
| CIFAR-10 · CNN-2 · Dir(α=1) | accuracy % | node 1/2/3/4 (แยกเทรน): 55.59 / 53.11 / 53.97 / 54.33; SWARM: 66.85±0.61 | ภาพตารางใน PDF |
| CIFAR-10 · CNN-2 · Dir(α=10) | accuracy % | node 1/2/3/4 (แยกเทรน): 58.28 / 56.29 / 59.93 / 60.27; SWARM: 67.26±0.51 | ภาพตารางใน PDF |
| CIFAR-10 · CNN-2 · Dir(α=50) | accuracy % | node 1/2/3/4 (แยกเทรน): 59.86 / 56.96 / 58.78 / 59.48; SWARM: 67.73±0.18 | ภาพตารางใน PDF |
| CIFAR-10 · CNN-2 · Dir(α=100) | accuracy % | node 1/2/3/4 (แยกเทรน): 59.92 / 56.03 / 62.07 / 60.54; SWARM: 68.93±0.28 | ภาพตารางใน PDF |
| MNIST · ResNet18 · Dir(α=0.1) | accuracy % | node 1/2/3/4 (แยกเทรน): 89.37 / 90.74 / 87.13 / 87.35; SWARM: 97.97±0.31 | ภาพตารางใน PDF |
| MNIST · ResNet18 · Dir(α=1) | accuracy % | node 1/2/3/4 (แยกเทรน): 93.55 / 91.83 / 94.13 / 94.53; SWARM: 98.65±0.11 | ภาพตารางใน PDF |
| MNIST · ResNet18 · Dir(α=10) | accuracy % | node 1/2/3/4 (แยกเทรน): 96.00 / 96.00 / 95.77 / 95.95; SWARM: 98.88±0.18 | ภาพตารางใน PDF |
| MNIST · ResNet18 · Dir(α=50) | accuracy % | node 1/2/3/4 (แยกเทรน): 95.14 / 95.97 / 95.05 / 95.18; SWARM: 99.25±0.07 | ภาพตารางใน PDF |
| MNIST · ResNet18 · Dir(α=100) | accuracy % | node 1/2/3/4 (แยกเทรน): 96.17 / 95.93 / 95.93 / 95.99; SWARM: 99.72±0.09 | ภาพตารางใน PDF |
| MNIST · CNN-2 · Dir(α=0.1) | accuracy % | node 1/2/3/4 (แยกเทรน): 95.18 / 95.95 / 94.51 / 96.92; SWARM: 97.83±0.25 | ภาพตารางใน PDF |
| MNIST · CNN-2 · Dir(α=1) | accuracy % | node 1/2/3/4 (แยกเทรน): 97.30 / 95.29 / 97.36 / 98.49; SWARM: 97.98±0.13 | ภาพตารางใน PDF |
| MNIST · CNN-2 · Dir(α=10) | accuracy % | node 1/2/3/4 (แยกเทรน): 98.60 / 96.58 / 98.72 / 98.98; SWARM: 98.13±0.10 | ภาพตารางใน PDF |
| MNIST · CNN-2 · Dir(α=50) | accuracy % | node 1/2/3/4 (แยกเทรน): 99.10 / 98.93 / 98.94 / 99.04; SWARM: 99.26±0.20 | ภาพตารางใน PDF |
| MNIST · CNN-2 · Dir(α=100) | accuracy % | node 1/2/3/4 (แยกเทรน): 99.00 / 98.91 / 99.08 / 98.88; SWARM: 99.33±0.11 | ภาพตารางใน PDF |

**ประเด็นสำคัญ**

- SL ชนะ baseline FL+defense ทั้ง 4 ตัวทุกค่า α บน CIFAR-10 (ResNet18 α=10: 73.17 vs ดีสุด 68.96 ของ BLUR+LUS)
- SL ชนะโหนดที่เทรนเดี่ยวเกือบทุกกรณี ห่างมากสุดตอน α ต่ำ (CIFAR-10 ResNet18 α=0.1: 66.48 vs โหนดดีสุด 55.18)
- ResNet18 ดีกว่า CNN-2 ทั้งแบบเดี่ยวและ SL · ยิ่ง α สูง (ข้อมูลใกล้ IID) ยิ่งแม่น

**ช่องโหว่ / ข้อจำกัด**

- ไม่มีการทดลองโจมตีจริง — ไม่ได้รัน DLG/GGL กับ SL เพื่อวัดว่ากู้ภาพได้น้อยลงหรือไม่ ข้ออ้างว่า 'mitigate gradient leakage' จึงเป็นเชิงสถาปัตยกรรมล้วน
- sentinel/leader ยังได้ gradient ดิบของทุกโหนด ถ้า leader เป็นโหนดที่ได้รับอนุญาตแต่ประสงค์ร้าย ก็ทำ gradient inversion ได้เหมือน server ของ FL — blockchain ยืนยันว่าใครเป็นสมาชิก ไม่ได้ซ่อน gradient
- baseline ใส่ DP noise แต่ SL ไม่ใส่ จึงเป็นการเทียบระหว่าง 'มี privacy guarantee' กับ 'ไม่มี' ไม่ได้บอกว่าได้ตัวเลข baseline จากการรันเองหรือยกมาจาก paper อื่น
- ไม่มี centralized baseline · SL ไม่ได้ชนะทุกเซลล์: MNIST CNN-2 α=1 และ α=10 โหนด 4 (98.49, 98.98) สูงกว่า SWARM (97.98, 98.13)
- ตาราง 1–2 ใน PDF เป็นภาพ ตัวเลขในรายงานนี้คัดลอกด้วยตา (source = table-image)

**ความเข้ากันได้กับสถาปัตยกรรม SL** — ตรงกับนิยาม SL ของ Warnat-Herresthal ครบ: ไม่มี server, onboarding ผ่าน smart contract, leader หมุนเวียน, merge ด้วย FedAvg · แต่ชั้นความปลอดภัยที่ได้คือ access control ไม่ใช่ confidentiality ของ gradient

**เทียบกับ `poc/sl-fabric`** — ตั้งการทดลองเหมือนโปรเจกต์: Dirichlet(α) แบ่ง non-IID (โปรเจกต์ใช้ α=0.5 บน BloodMNIST), FedAvg, โหนดเดี่ยว vs swarm · ต่างกันตรงที่ ledger ของโปรเจกต์เก็บ hash ของ weight (commit) แต่ weight ยังส่งกันนอกเชน จึงติดข้อจำกัดเดียวกันว่า leader เห็น weight ดิบ · ถ้าจะอ้างเรื่อง gradient leakage ต้องทดลองโจมตีจริง หรือเพิ่ม secure aggregation / HE (ดู Swarm-FHE) — เป็นช่องว่างที่ paper นี้ทิ้งไว้และโปรเจกต์เติมได้

**ชื่อชุดข้อมูลที่สคริปต์เจอใน PDF** (หน้า): CIFAR-10 (1, 4, 6, 7), MNIST (1, 4, 6), Edge-IIoTset (7)

**หลักฐานที่ตรวจกับ PDF**

- ✓ หน้า 4: “we divide all training data equally into four training nodes using different dirichlet distribution”
- ✓ หน้า 4: “we use a well-known resnet18 pre-trained model”
- ✓ หน้า 5: “1 swarm network (sn) node, 1 swarm operator (swop) node, 4 machine learning (ml)”
- ✓ หน้า 5: “4 swarm learning (sl) nodes, and a swarm learning command line interface (swci)”
- ✓ หน้า 6: “experiments are repeated four times for each”
- ✓ หน้า 6: “the gradients are shared only with the authenticated nodes”

### Backdoor attacks against distributed swarm learning

*K. Chen, H. Zhang, X. Feng, X. Zhang, B. Mi, Z. Jin* · ISA Transactions 141:59–72, 2023 · PMID 37012167

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | web search |
| ความเกี่ยวกับ cybersecurity | หลัก — backdoor attack ต่อ SL |
| ลิงก์ | <https://pubmed.ncbi.nlm.nih.gov/37012167/> · <https://www.sciencedirect.com/science/article/abs/pii/S0019057823001441> |
| สรุปบทคัดย่อ | SL ไม่มี server กลางคอยกรอง update ผู้โจมตีจึงฝัง backdoor pattern ให้ global model จำผิดได้ ผู้เขียนวัดผลของ backdoor ใน SL หลายสถานการณ์และเสนอวิธีป้องกัน |
| ชุดข้อมูล | MNIST, CIFAR-10, SVHN |
| รายละเอียดข้อมูล/การแบ่งโหนด | ทดลองทั้ง IID และ non-IID และขนาดเครือข่ายหลายระดับ |
| วิธี/โมเดล | pixel-pattern backdoor · single vs multi-target · single-shot vs multiple-shot |
| การตั้งค่า SL | distributed SL |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| ตามบทคัดย่อ | - | การป้องกัน: L2 regularization และ noise injection ลดผลของ backdoor ได้ | เว็บ/บทคัดย่อ |

**ประเด็นสำคัญ**

- เป็นงานแรก ๆ ที่วัด backdoor กับ SL โดยตรงและเสนอการป้องกันที่ไม่ต้องมี server

**ช่องโหว่ / ข้อจำกัด**

- ยังไม่ได้ตัวเลข attack success rate
- ใช้ภาพ benchmark ไม่ใช่ข้อมูล cyber — ยังไม่รู้ว่า backdoor บน traffic ทำงานเหมือนกันไหม

**ความเข้ากันได้กับสถาปัตยกรรม SL** — สูง — โจมตีขั้น merge ของ SL ตรง ๆ

**เทียบกับ `poc/sl-fabric`** — ทำซ้ำบน N-BaIoT ใน sl-fabric ได้: ให้ Org หนึ่งเทรนบนทราฟฟิกที่ฝัง trigger แล้วดูว่า global model ติด backdoor ไหม · ledger บันทึก hash ของ update ที่มี backdoor ไว้ถาวร ใช้ไล่ต้นตอย้อนหลังได้แต่ไม่ได้กันไว้ก่อน

### Propagable Backdoors over Blockchain-based Federated Learning via Sample-Specific Eclipse

*Z. Yang, G. Li, J. Wu, W. Yang* · IEEE GLOBECOM 2022, pp. 2579–2584

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | web search |
| ความเกี่ยวกับ cybersecurity | หลัก — eclipse attack บนชั้น P2P ของเชน + backdoor |
| ลิงก์ | <https://ieeexplore.ieee.org/document/10001370/> |
| สรุปบทคัดย่อ | ช่องโหว่ของ blockchain และของ FL ที่ดูไม่เกี่ยวกัน เมื่อรวมกันกลายเป็นภัยใหม่ต่อ swarm learning ผู้เขียนเสนอ sample-specific eclipse (SSE) ที่ตัดการเชื่อมต่อโหนดที่ data contribution สูงแล้วป้อนโมเดลที่ฝัง backdoor |
| ชุดข้อมูล | (ต้องดูฉบับเต็ม) |
| รายละเอียดข้อมูล/การแบ่งโหนด | - |
| วิธี/โมเดล | eclipse attack เลือกเป้าตาม data contribution + backdoor poisoning |
| การตั้งค่า SL | blockchain-based FL (ผู้เขียนเรียกว่า swarm learning) |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| ตามบทคัดย่อ | - | SSE: backdoor แพร่เร็วขึ้นและต้นทุนการโจมตีต่ำลง | เว็บ/บทคัดย่อ |

**ประเด็นสำคัญ**

- ชั้นเครือข่ายของเชนเป็นพื้นผิวโจมตีของโมเดลได้ ไม่ใช่แค่ของ ledger

**ช่องโหว่ / ข้อจำกัด**

- ยังไม่ได้ชุดข้อมูลและตัวเลข

**ความเข้ากันได้กับสถาปัตยกรรม SL** — สูง — โจมตีจุดที่ SL ต่างจาก FL (P2P)

**เทียบกับ `poc/sl-fabric`** — PoC ปัจจุบันไม่มี P2P จริง (process เดียว) · ถ้าแยกเครื่องควรให้ peer ของ Fabric ต่อกันหลายเส้นทาง

### Zero-Trust Empowered Decentralized Security Defense against Poisoning Attacks in SL-IoT: Joint Distance-Accuracy Detection Approach

*R. Song, J. Wu, Q. Pan, M. Imran, N. Naser, R. Jones, C. Verikoukis* · IEEE GLOBECOM 2023 · doi:10.1109/GLOBECOM54140.2023.10437789 · ฉบับเต็มบน Zenodo 13874888

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | web search |
| ความเกี่ยวกับ cybersecurity | หลัก — poisoning defense สำหรับ SL-IoT |
| ลิงก์ | <https://ieeexplore.ieee.org/document/10437789/> · <https://zenodo.org/records/13874888> |
| สรุปบทคัดย่อ | ใน SL โหนด header (leader) เป็นผู้อัปเดต global parameter ถ้า header ประสงค์ร้ายจะทำลายโมเดลได้ง่ายกว่า edge node ผู้เขียนใช้ zero-trust คำนวณความเสี่ยงต่อเนื่อง วิเคราะห์พฤติกรรมการเรียน และตรวจ parameter ผิดปกติ |
| ชุดข้อมูล | (ต้องดูฉบับเต็ม) |
| รายละเอียดข้อมูล/การแบ่งโหนด | ทดลองกับ edge node ประสงค์ร้ายแบบสุ่มและแบบปรับแต่ง |
| วิธี/โมเดล | zero-trust architecture · Manhattan distance ระหว่าง parameter + ความต่างของ accuracy |
| การตั้งค่า SL | SL-IoT (มี header หมุนเวียน) |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| ตามบทคัดย่อ | - | ZTA defense: accuracy สูงกว่าวิธีเดิมเมื่อมีโหนดประสงค์ร้าย | เว็บ/บทคัดย่อ |

**ประเด็นสำคัญ**

- เป็นงานเดียวที่ค้นเจอซึ่งมองว่า leader เองคือผู้โจมตี

**ช่องโหว่ / ข้อจำกัด**

- ยังไม่ได้ชุดข้อมูลและตัวเลข — ฉบับเต็มอยู่บน Zenodo ซึ่งถูกบล็อกจากเครื่องที่รัน

**ความเข้ากันได้กับสถาปัตยกรรม SL** — สูง — ออกแบบมาเพื่อ SL โดยเฉพาะ

**เทียบกับ `poc/sl-fabric`** — chaincode รู้ว่าใครคือ leader และมี hash ของทุก update อยู่แล้ว · ขยายได้โดยให้โหนดรายงาน accuracy บน validation ของตัวเองกับ global model แล้วให้ chaincode ปฏิเสธรอบที่ accuracy ตกผิดปกติ

### Swarm-FHE: Fully Homomorphic Encryption-based Swarm Learning for Malicious Clients

*H. A. Madni, R. M. Umer, G. L. Foresti (กลุ่มเดียวกับ Madni 2023 ในเครื่อง)* · International Journal of Neural Systems 33(8):2350033, 2023 · PMID 37246573

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | web search |
| ความเกี่ยวกับ cybersecurity | หลัก — gradient leakage เมื่อมี participant ประสงค์ร้าย |
| ลิงก์ | <https://pubmed.ncbi.nlm.nih.gov/37246573/> |
| สรุปบทคัดย่อ | ต่อจาก Madni 2023: GAN กู้ข้อมูลดิบจาก parameter ได้ และ participant บางรายอาจถูกยึด จึงเข้ารหัส parameter ด้วย FHE ก่อนแชร์ให้สมาชิกที่ลงทะเบียนผ่าน blockchain |
| ชุดข้อมูล | CIFAR-10, MNIST |
| รายละเอียดข้อมูล/การแบ่งโหนด | เทรน CNN บน CIFAR-10 และ MNIST |
| วิธี/โมเดล | fully homomorphic encryption ของ model parameter · แชร์ ciphertext ระหว่างผู้ร่วม |
| การตั้งค่า SL | SL + blockchain registration + FHE |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| ตามบทคัดย่อ | - | Swarm-FHE: เทรนร่วมกันได้โดยไม่เปิด parameter ดิบ แม้มี participant ถูกยึด | เว็บ/บทคัดย่อ |

**ประเด็นสำคัญ**

- ปิดช่องโหว่ที่ Madni 2023 ทิ้งไว้ (leader เห็น gradient ดิบ)

**ช่องโหว่ / ข้อจำกัด**

- FHE หนักมาก ต้องดู overhead ในฉบับเต็ม
- ข้อมูลเป็นภาพ benchmark

**ความเข้ากันได้กับสถาปัตยกรรม SL** — สูง — เพิ่มชั้น confidentiality ให้ SL โดยไม่เปลี่ยน workflow

**เทียบกับ `poc/sl-fabric`** — FedAvg บน vector ทศนิยมทำใน CKKS ได้ · ledger เก็บ hash ของ ciphertext ได้เหมือนเดิม

### Multi-Region Asynchronous Swarm Learning for Data Sharing in Large-Scale Internet of Vehicles (MASL)

*Yin et al.* · 2023

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | web search |
| ความเกี่ยวกับ cybersecurity | รอง — identity verification + anomaly detection ใน IoV |
| ลิงก์ | <https://www.researchgate.net/publication/373856168_Multi-Region_Asynchronous_Swarm_Learning_for_Data_Sharing_in_Large-Scale_Internet_of_Vehicles> |
| สรุปบทคัดย่อ | IoV ขนาดใหญ่มีข้อมูล non-IID และต้องแชร์อย่างปลอดภัย MASL ใช้ hierarchical blockchain รันหลายภูมิภาคขนานกัน รวม identity verification กับการเทรนแบบ asynchronous |
| ชุดข้อมูล | GTSRB (ตาม Table 3 ของ survey) |
| รายละเอียดข้อมูล/การแบ่งโหนด | GTSRB เป็นภาพป้ายจราจร — ไม่ใช่ข้อมูล cyber |
| วิธี/โมเดล | asynchronous SL แบบหลายภูมิภาค + hierarchical blockchain |
| การตั้งค่า SL | SL หลายชั้น: ภายในภูมิภาค และข้ามภูมิภาค |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| ตามบทคัดย่อ | - | MASL: ทั้ง simulation และ hardware testbed ดีกว่าวิธีเดิมด้าน efficiency และ security | เว็บ/บทคัดย่อ |

**ประเด็นสำคัญ**

- แนวคิด SL สองชั้นช่วยเรื่อง non-IID และการขยายขนาด

**ช่องโหว่ / ข้อจำกัด**

- ข้อมูลเป็นภาพ ไม่ใช่ cyber
- ยังไม่ได้ตัวเลข

**ความเข้ากันได้กับสถาปัตยกรรม SL** — สูง — SL + blockchain

**เทียบกับ `poc/sl-fabric`** — ถ้าขยายเกิน 5 org อาจแบ่ง channel ของ Fabric ตามภูมิภาคแล้วรวมอีกชั้น

### DAG-based swarm learning: A secure asynchronous learning framework for Internet of Vehicles (DSL)

*Huang et al.* · Digital Communications and Networks (Elsevier), 2023

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | web search |
| ความเกี่ยวกับ cybersecurity | รอง — ตรวจรถประสงค์ร้ายระหว่างเทรน |
| ลิงก์ | <https://www.sciencedirect.com/science/article/pii/S2352864823001578> |
| สรุปบทคัดย่อ | ใช้ blockchain แบบ DAG กับ edge computing ให้รถเทรนแบบ asynchronous ได้ปลอดภัย มีวิธีตรวจรถประสงค์ร้ายจาก site confirmation rate และให้รางวัลตาม accuracy เพื่อจูงใจให้เทรนอย่างซื่อสัตย์ |
| ชุดข้อมูล | GTSRB (ตาม Table 3 ของ survey) |
| รายละเอียดข้อมูล/การแบ่งโหนด | GTSRB เป็นภาพป้ายจราจร — ไม่ใช่ข้อมูล cyber |
| วิธี/โมเดล | DAG blockchain + dynamic vehicle association + malicious attack detection + incentive |
| การตั้งค่า SL | DAG-based SL (asynchronous) |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| ตามบทคัดย่อ | - | DSL: accuracy, convergence และ security ดีกว่าวิธีเดิม | เว็บ/บทคัดย่อ |

**ประเด็นสำคัญ**

- ตรวจผู้ร่วมประสงค์ร้ายจากพฤติกรรมบนเชน (confirmation rate) ไม่ต้องดูข้อมูลดิบ

**ช่องโหว่ / ข้อจำกัด**

- ข้อมูลเป็นภาพ ไม่ใช่ cyber
- ยังไม่ได้ตัวเลข

**ความเข้ากันได้กับสถาปัตยกรรม SL** — สูง — SL + DAG blockchain

**เทียบกับ `poc/sl-fabric`** — แนวคิด incentive ตาม accuracy ใช้ต่อยอดใน chaincode ได้ (บันทึก accuracy ต่อรอบอยู่แล้ว)


## 4 · กลุ่ม C: ชุดข้อมูล cyber + สถาปัตยกรรมคล้าย SL

กลุ่มรอง: IDS บนชุดข้อมูล cyber มาตรฐาน ที่เทรนแบบ decentralized หรือใช้ blockchain ประสาน แต่ไม่ใช่ SL ตรงตัว

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


## 5 · กลุ่ม base: พื้นฐานของ swarm learning (ไม่ใช่ cyber)

paper ในโฟลเดอร์ `paper/` ที่นิยามและวัด SL แต่ใช้ข้อมูลการแพทย์/ทั่วไป

### Demystifying Swarm Learning: A New Paradigm of Blockchain-based Decentralized Federated Learning

*J. Han, Y. Ma, Y. Han (Peking University)* · arXiv:2201.05286v2, ม.ค. 2022

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | ไฟล์ใน `paper/` |
| ความเกี่ยวกับ cybersecurity | รอง — fault tolerance ต่อโหนดข้อมูลเสีย (label poisoning) และความเสี่ยงจาก leader election ที่ไม่ยุติธรรม |
| ลิงก์ | `paper/2201.05286v2.pdf` |
| สรุปบทคัดย่อ | ยังไม่มีงานวัด HPE SL เชิงประจักษ์ว่าใช้จริงแล้วแม่น/ทน/กินทรัพยากรแค่ไหน จึงตั้ง 5 research question แบบ black-box |
| ชุดข้อมูล | NIH ChestX-ray, CIFAR-10, IMDB |
| รายละเอียดข้อมูล/การแบ่งโหนด | Task A: NIH chest X-ray 112,120 ภาพ, 30,805 ผู้ป่วย, multi-label, ตัดอายุ >100 ปี, ย่อเป็น 256×256 · Task B: CIFAR-10 60,000 ภาพ 32×32 · Task C: IMDB 50,000 รีวิว (sentiment) · แบ่งเป็น 3–4 โหนด ทั้งเท่ากัน, 1:2:3(:4), label ไม่สมดุล (power-law 500–5000 ต่อคลาส / 12k neg : 4k pos), แบ่งตามอายุหรือเพศ (fairness), และให้โหนดหนึ่ง label ผิดครึ่งหนึ่ง (LQN) |
| วิธี/โมเดล | A: DenseNet-49 (block 4,4,8,6) · B: DenseNet-BC depth 100 growth 12 (RQ5 ใช้ EfficientNetB2) · C: attention Bi-LSTM (embedding 128, 64 units) · baseline คือ centralized learning (CL) และ localized learning (LL) สำหรับ fairness |
| การตั้งค่า SL | HPE SL (SLL แบบ binary): SL node, SN node บน Ethereum, SWCI, SPIRE server, license server · merge ทุก Synchronization Interval โดย leader ที่ blockchain เลือก · ขยาย SN 1→4, SL 2→8 · ไลเซนส์ non-commercial จำกัด 4 SN / 16 SL |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| RQ1 แบ่งเท่ากัน | accuracy | CL: A 0.8850 · B 0.9350 · C 0.8940; SL: A 0.9090 · B 0.9304 · C 0.8875; โหนดเดี่ยว: A 0.876–0.878 · B 0.886–0.892 · C 0.845–0.854 | ข้อความใน PDF |
| RQ2.1 ขนาดโหนด 1:2:3(:4) | accuracy | CL: A 0.8850 · B 0.9350 · C 0.8940; SL: A 0.8830 · B 0.9226 · C 0.8943 | ข้อความใน PDF |
| RQ2.2 label ไม่สมดุล | accuracy | CL: B 0.8699 · C 0.8591; SL: B 0.8559 · C 0.8629; โหนดเดี่ยว: B 0.761–0.775 · C 0.806–0.828 | ข้อความใน PDF |
| RQ3 NIH-age (แบ่งตามอายุ) | ROC-AUC บน global test | LL: 0.680–0.704; SL: 0.7395–0.7402 | ข้อความใน PDF |
| RQ3 NIH-gender (หญิง:ชาย 9:1, 5:5, 1:9) | ROC-AUC บน global test | LL: 0.699–0.704; SL: 0.736–0.739 | ข้อความใน PDF |
| RQ4 มีโหนด label ผิด 50% (LQN) | accuracy | CL: A 0.8841 · B 0.8673 · C 0.8646; SL: A 0.8840 · B 0.8897 · C 0.7955; LQN เอง: A 0.8796 · B 0.4480 · C 0.5002 | ข้อความใน PDF |
| RQ5.2 SN=2, SL=8 (CIFAR-10) | network in ต่อโหนด (MB) | SL-0-2: 51,100; SL-0-1: 14,900; โหนดอื่น: 8,760–10,500 | ข้อความใน PDF |

**ประเด็นสำคัญ**

- SL แม่นใกล้ CL ในเกือบทุกสถานการณ์ และบางกรณีสูงกว่า (Task A 0.9090 vs 0.8850)
- fairness: โมเดลทุกโหนดใน SL ให้ผลใกล้กันบน test ของทุกโหนด ต่างจาก LL ที่เก่งแค่ข้อมูลตัวเอง
- ทนโหนดข้อมูลเสียได้เมื่อข้อมูลพอ (A, B) แต่ IMDB ซึ่งเล็กกว่า SL ตกเหลือ 0.7955 ไม่ converge
- ภาระเครือข่ายกระจุกที่โหนดที่เป็น leader บ่อย — SL-0-2 รับข้อมูล ~5 เท่าของโหนดอื่น ผู้เขียนสงสัยว่า leader election เป็นแบบ PoS ที่ไม่ยุติธรรม และจำลองว่า PoW กระจายภาระได้เท่ากว่า
- เพิ่ม SN node แทบไม่เพิ่มภาระ แต่เพิ่ม SL node ทำให้ network overhead โตเชิงเส้น

**ช่องโหว่ / ข้อจำกัด**

- ทดสอบแบบ black-box — ไม่รู้ว่า HPE ใช้ leader election / aggregation แบบไหนจริง ข้อสรุปเรื่อง PoS เป็นการเดา
- ทดลองการเข้า-ออกของโหนด (connectivity) ไม่สำเร็จเพราะติดเพดานไลเซนส์และ token หมดอายุช้า 30 นาที
- RQ1–RQ4 ใช้แค่ 3–4 โหนด · ไม่มีการโจมตีเจตนาร้ายที่ปรับตัว (แค่ label ผิดแบบสุ่ม)

**ความเข้ากันได้กับสถาปัตยกรรม SL** — เป็นงานเดียวในชุดที่วัดชิ้นส่วนของ SL ทีละชิ้น (SN/SL/SPIRE/LS) และชี้ว่า leader election คือจุดอ่อนทั้งด้าน ความเป็นธรรมและ security (โหนดที่ทราฟฟิกสูงผิดปกติบอกผู้โจมตีว่าใครคือ leader)

**เทียบกับ `poc/sl-fabric`** — โปรเจกต์ใช้ leader rule แบบ deterministic `sha256(round + members) mod n` ซึ่งตรวจสอบย้อนหลังได้และกระจายสม่ำเสมอ ตอบข้อติของ paper นี้ตรง ๆ — วัดได้ทันทีด้วย `leader_counts()` และ `hostmetrics.py` ของ sl-fabric · `min_peers` ของ HPE = `quorum` ของ chaincode · RQ4 ชี้ว่าต้องมี robust aggregation (โปรเจกต์ยังไม่มี) · ข้อเสียของ rule แบบ deterministic คือรู้ล่วงหน้าว่าใครเป็น leader รอบถัดไป ผู้โจมตีเล็งเป้าได้

**ชื่อชุดข้อมูลที่สคริปต์เจอใน PDF** (หน้า): NIH ChestX-ray (4, 19), CIFAR-10 (5, 7), IMDB (5, 7, 8), ISIC / skin lesion (16, 18)

**หลักฐานที่ตรวจกับ PDF**

- ✓ หน้า 4: “we use nih chest x-ray dataset”
- ✓ หน้า 5: “we use imdb review dataset”
- ✓ หน้า 8: “we modify the labels of half of the samples on one node”
- ✓ หน้า 14: “the leader election algorithm (lea) is not open-sourced”
- ✓ หน้า 15: “hpe limits the capacity of licenses assigned for non-commercial use to have at most 4 sn nodes and 16 sl nodes”

### Swarm Learning for decentralized and confidential clinical machine learning

*S. Warnat-Herresthal, H. Schultze, … , J. L. Schultze (DZNE + HPE)* · Nature 594, 265–270, 2021 · doi:10.1038/s41586-021-03583-3

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | ไฟล์ใน `paper/` |
| ความเกี่ยวกับ cybersecurity | รอง — data confidentiality/sovereignty ตามกฎหมาย (GDPR) ไม่ได้ทดลองการโจมตี |
| ลิงก์ | `paper/s41586-021-03583-3.pdf` |
| สรุปบทคัดย่อ | ข้อมูลการแพทย์กระจายตามโรงพยาบาลและย้ายรวมศูนย์ไม่ได้ตามกฎหมาย จึงเสนอ SL ที่ไม่มี server กลาง |
| ชุดข้อมูล | GEO (GSE…), NIH ChestX-ray, COVID-19 blood transcriptomes (EGA) |
| รายละเอียดข้อมูล/การแบ่งโหนด | A1 PBMC microarray n=2,500 · A2 PBMC microarray n=8,348 · A3 PBMC RNA-seq n=1,181 (AML/ALL; 12,708 ยีน) · B whole blood RNA-seq n=1,999 (TB; 18,135 transcript) · C NIH chest X-ray 95,831 ภาพ (ย่อเป็น 128×128) · D whole blood n=2,143 (COVID-19; 19,358) · E n=2,400 จาก 8 ศูนย์ E1–E8 (COVID-19; 19,399) · รวม >16,400 transcriptome จาก 127 การศึกษา · แบ่งโหนดแบบจำลองสถานการณ์จริง: สัดส่วน case/control ต่างกัน, แยกตามการศึกษา, แยกตามเทคโนโลยี (microarray vs RNA-seq), outbreak ที่ prevalence ต่ำ |
| วิธี/โมเดล | Keras sequential DNN: input 256 → 8 hidden layer (1,024 → 64, ReLU, dropout 30%, L2 0.005) → sigmoid · Adam + BCE · 100 epoch · ทดลอง LASSO แทนด้วย · 16,694 การวิเคราะห์, 5–100 permutation ต่อ scenario, 8,347 ชั่วโมงคำนวณ · วัด accuracy, sensitivity, specificity, F1, AUC · ทดสอบนัยสำคัญด้วย one-sided Wilcoxon |
| การตั้งค่า SL | HPE SLL + permissioned blockchain (Ethereum) · 3 ถึง 32 training node (docker container ต่อโหนด) + test node แยก · HPE Apollo 6500 สองเครื่อง Tesla P100 × 8 · merge ได้ทั้ง average/weighted/min/max/median — ใช้ simple average เป็นหลัก และ node_weightage ในบาง scenario ของ TB · adaptive_rv ปรับความถี่ merge ตาม convergence |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| AML, dataset A2, case/control เอียงต่างกันต่อโหนด (Fig 2b) | accuracy | โหนด 1/2/3: ≈0.98 / 0.55 / 0.95; SL: ≈0.99 | อ่านจากกราฟ ≈ |
| AML, A1/A2/A3 คนละเทคโนโลยีต่อโหนด (Fig 2e) | accuracy | โหนด 1/2/3: ≈0.96 / 0.97 / 0.84; SL: ≈0.99 | อ่านจากกราฟ ≈ |
| TB, dataset B, 3 โหนด (Fig 3a) | accuracy | โหนด: ≈0.83–0.86; SL: ≈0.88 | อ่านจากกราฟ ≈ |
| X-ray, dataset C n=47,300, 3 โหนด (Fig 3d) | AUC (SL) | atelectasis: ≈0.75; effusion: ≈0.85; infiltration: ≈0.67; no finding: ≈0.80 | อ่านจากกราฟ ≈ |
| COVID-19, dataset E, 6 ศูนย์ (Fig 4d) | AUC | โหนด: ≈0.6–0.93; SL: ≈0.96 | อ่านจากกราฟ ≈ |

**ประเด็นสำคัญ**

- SL ชนะทุกโหนดเดี่ยวอย่างมีนัยสำคัญในทุก use case และใกล้เคียงหรือเท่ากับ central model
- ทนต่อ bias ของการศึกษา/เทคโนโลยี/เพศ/อายุ และแบ่งโหนดให้เล็กลง (3 → 6) แล้ว SL ไม่แย่ลงแต่โหนดเดี่ยวแย่ลง
- ศูนย์ COVID แต่ละแห่งทายตัวอย่างของศูนย์อื่นไม่ได้ แต่ SL ทายได้

**ช่องโหว่ / ข้อจำกัด**

- ตัวเลขจริงอยู่ใน Supplementary Table 3–5 ซึ่งไม่อยู่ใน PDF นี้ ค่าในรายงานอ่านจาก box plot (±0.02)
- ผู้เขียนหลายคนเป็นพนักงาน HPE ซึ่งเป็นเจ้าของ SLL และยื่นสิทธิบัตร (ระบุใน competing interests)
- ทุกโหนดรันบนเซิร์ฟเวอร์สองเครื่องเดียวกัน ไม่ใช่ข้ามองค์กรจริง · ไม่มีการทดลองโจมตี
- ข้ออ้างว่า blockchain 'gives robust measures against dishonest participants' ไม่มีการทดลองรองรับใน paper

**ความเข้ากันได้กับสถาปัตยกรรม SL** — เป็นต้นฉบับที่นิยาม SL — ทุกงานอื่นในรายงานนี้อ้างนิยามจากที่นี่

**เทียบกับ `poc/sl-fabric`** — ข้อมูลเป็น tabular มิติสูง + dense NN ซึ่งเข้ากับ interface 'flat parameter vector' ของ client ในโปรเจกต์พอดี · สิ่งที่โปรเจกต์ทำตรงกับ SL ต้นฉบับ: permissioned chain, leader หมุนเวียน, สิทธิ์ merge เท่ากัน, weight ไม่ขึ้นเชน · สิ่งที่ต่าง: โปรเจกต์ใช้ Fabric + MAJORITY endorsement แทน Ethereum ของ HPE และเปิดซอร์ส leader rule ได้ · ข้อมูลเป็นสายการแพทย์ ไม่ใช่ cyber — ใช้เป็นแม่แบบการออกแบบ scenario (prevalence ต่ำ, แยกตามแหล่ง) กับชุด cyber ได้

**ชื่อชุดข้อมูลที่สคริปต์เจอใน PDF** (หน้า): NIH ChestX-ray (1, 4, 6, 8, 9), GEO (GSE…) (9)

**หลักฐานที่ตรวจกับ PDF**

- ✓ หน้า 2: “dataset c: 95,831 x-ray images”
- ✓ หน้า 8: “the neural network consists of one input layer, eight hidden layers and one output layer”
- ✓ หน้า 9: “unless stated otherwise, we used a simple average without weights”
- ✓ หน้า 8: “we performed 16,694 analyses”
- ✓ หน้า 8: “the swarm network is created with a minimum of 3 up to a maximum of 32 training nodes”

### Swarm Learning: A Survey of Concepts, Applications, and Trends

*E. Shammar, X. Cui (Wuhan Univ.), M. A. A. Al-qaness* · arXiv:2405.00556v2, ก.พ. 2025 (ตีพิมพ์ใน ACM Transactions on Privacy and Security)

| หัวข้อ | รายละเอียด |
|---|---|
| แหล่ง | ไฟล์ใน `paper/` |
| ความเกี่ยวกับ cybersecurity | หลัก (บทที่ 5) — backdoor, poisoning, eclipse, DoS, sponge, inference, model inversion |
| ลิงก์ | `paper/2405.00556v2.pdf` |
| สรุปบทคัดย่อ | สำรวจงาน SL ทั้งหมดถึง ก.พ. 2025: แนวคิด, สถาปัตยกรรม, การประยุกต์, ความท้าทาย |
| ชุดข้อมูล | (survey — รวบรวมจากงานอื่น) |
| รายละเอียดข้อมูล/การแบ่งโหนด | ค้น 6 ฐานข้อมูล (IEEE 30, PubMed 12, ScienceDirect 129, Scopus 87, Springer 28, WoS 56) คัดเหลือ 84 paper · จำนวนต่อปี 2020: 4, 2021: 5, 2022: 14, 2023: 29, 2024: 28, 2025 (ถึง ก.พ.): 4 · ชุดข้อมูลที่ปรากฏในตาราง 2–5 ของงานที่เกี่ยวกับ security: MNIST, CIFAR-10, SVHN (backdoor), GTSRB (MASL, DAG-SL), RFF dataset (ยืนยันตัวตนอุปกรณ์), traffic dataset (ADONIS), LIAR (fake news), Universal Bank (credit scoring) |
| วิธี/โมเดล | systematic literature review + taxonomy ตามสาขา (healthcare, transportation, industry, robotics, energy, smart home, finance, multimedia IoT, fake news, metaverse) |
| การตั้งค่า SL | สรุปองค์ประกอบ HPE SL: SL node, SN node (Ethereum), SWOP, SWCI, SLM-UI, SPIRE server, license server · identity ด้วย X.509 |

**ผลลัพธ์**

| เงื่อนไข | ตัวชี้วัด | ค่า | ที่มา |
|---|---|---|---|
| งาน SL ด้าน security ที่ survey สรุปไว้ | ผล | Chen et al. [6]: backdoor แบบ pixel pattern บน MNIST/CIFAR-10/SVHN; ป้องกันด้วย L2 reg + noise injection; Yang et al. [39]: sample-specific eclipse (SSE) + backdoor — เล็งโหนดที่ data contribution สูง; Rongxuan et al. [86]: ZTA ต้าน poisoning จาก header node ด้วย Manhattan distance + accuracy difference; Swarm-FHE [92]: FHE เข้ารหัส parameter ก่อนแชร์ รับมือ participant ประสงค์ร้าย; ADONIS [82]: SL + knowledge distillation ตรวจพฤติกรรมผิดปกติของ IoT บน traffic dataset; RFF [83]: SL + differential privacy ยืนยันตัวตนอุปกรณ์ด้วย radio frequency fingerprint | ข้อความใน PDF |

**ประเด็นสำคัญ**

- ภัยต่อ SL แบ่งตามช่วง: data poisoning ตอนเทรนท้องถิ่น · eclipse/DDoS ตอนอัปโหลด metadata บน P2P · backdoor ตอน merge
- ปัญหาเปิด: non-IID, fairness/bias, leader election ที่ไม่ยุติธรรม, overhead ของเชนเทียบกับเวลาที่ประหยัดได้
- SL เหมาะกับอุตสาหกรรมที่ต้องมี provenance/audit (การเงิน, สุขภาพ) มากกว่า DFL ทั่วไป

**ช่องโหว่ / ข้อจำกัด**

- เป็น survey — ไม่มีการทดลองของตัวเอง ตัวเลขที่อ้างต้องกลับไปดูต้นฉบับ
- ปนงาน swarm intelligence (PSO/ACO) กับ swarm learning ในบางส่วน (เช่น CB-DSL, D-SLP) ต้องแยกเองเวลาอ้าง
- บางข้ออ้างคลาดเคลื่อน เช่น บรรยายงาน Warnat-Herresthal ว่าเป็น histopathology >5,000 ผู้ป่วย ซึ่งจริง ๆ เป็นของ Saldanha et al. 2022

**ความเข้ากันได้กับสถาปัตยกรรม SL** — ใช้เป็นแผนที่ของภัยคุกคามต่อ SL ได้ดีที่สุดในชุด — ตรงกับหัวข้อ cyber ของโปรเจกต์

**เทียบกับ `poc/sl-fabric`** — ภัยที่โปรเจกต์กันได้แล้ว: ปลอมตัวเป็นโหนดอื่น (MSP identity), ส่งซ้ำ, non-leader ปิดรอบ, แก้รอบที่ปิดแล้ว (append-only) · ภัยที่ยังเปิด: backdoor/poisoning (ไม่มี robust aggregation), inference/model inversion (leader เห็น weight ดิบ), eclipse (ใน PoC ทุกโหนดอยู่ process เดียว) · ใช้บทที่ 5 เป็นโครง threat model ของวิทยานิพนธ์ได้ตรง ๆ

**ชื่อชุดข้อมูลที่สคริปต์เจอใน PDF** (หน้า): MIMIC (5), NIH ChestX-ray (14, 17), ISIC / skin lesion (15, 17, 27), NGSIM (16, 18), MNIST (17, 18, 19, 22), TCGA (17), CIFAR-10 (18, 22), GTSRB (18), LIAR (21), RFF dataset (21), SVHN (22)

**หลักฐานที่ตรวจกับ PDF**

- ✓ หน้า 3: “we identified 84 papers that met our inclusion criteria”
- ✓ หน้า 22: “chen et al. [6] examined backdoor threats in sl using a pixel pattern backdoor attack method”
- ✓ หน้า 22: “sample-specific eclipse (sse) strategy”
- ✓ หน้า 23: “zero trust architecture (zta)-based defense mechanism”

## 6 · งานที่ค้นเจอแต่คัดออก

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

## 8 · ชุดข้อมูลสาย cybersecurity เทียบกับสถาปัตยกรรมของโปรเจกต์

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
| Elliptic | 0 | 1 | 2 | 2 | 1 | **6** | Explore.ipynb ของโปรเจกต์ |
| MNIST / CIFAR-10 / SVHN | 0 | 2 | 2 | 0 | 1 | **5** | Madni 2023; Chen et al. 2023 (backdoor); CB-DSL |

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

### Elliptic — 6/10

ธุรกรรมบิตคอยน์ 203,769 โหนด 234,355 เส้น · 166 ฟีเจอร์ · 49 time step · label: licit / illicit / unknown

- partition: 0 — กราฟก้อนเดียว ต้องแบ่งตาม time step หรือสุ่ม
- baseline: 1 — มี baseline centralized (Weber 2019)
- size: 2 — ≈700 MB
- audit: 2 — ผู้กำกับดูแลการเงินต้องการ audit trail
- model: 1 — ฟีเจอร์ 72 ตัวเป็นค่ารวมจากเพื่อนบ้าน แบ่งกราฟแล้วคำนวณไม่ครบ

> เรื่องเล่า audit ดีที่สุด แต่ partition อ่อน

### MNIST / CIFAR-10 / SVHN — 5/10

benchmark ภาพ ใช้วัด 'การโจมตีต่อ SL' ไม่ใช่ข้อมูล cyber · 60k–70k ภาพต่อชุด · label: 10 คลาส

- partition: 0 — ต้องใช้ Dirichlet
- baseline: 2 — ตัวเลข SL ภายใต้การโจมตีมีเฉพาะชุดพวกนี้
- size: 2 — เล็ก
- audit: 0 — ไม่มีเรื่องเล่าเจ้าของข้อมูล
- model: 1 — CNN จำเป็นสำหรับ CIFAR/SVHN (client มี cnn อยู่แล้ว)

> ใช้เมื่ออยากทำซ้ำ backdoor/gradient leakage ให้ตรงกับ paper ไม่ใช่เป็นชุดหลัก

## 9 · ความเข้ากันได้กับสถาปัตยกรรม swarm learning — สรุป

| ชั้นของ SL | HPE SL (Nature 2021, Han 2022) | poc/sl-fabric | สิ่งที่ paper สาย cyber ชี้ว่ายังขาด |
|---|---|---|---|
| identity / onboarding | SPIFFE/SPIRE + X.509 + smart contract | X.509 ต่อ org ตรวจโดย MSP ของ peer | — |
| leader election | ไม่เปิดซอร์ส สงสัยว่าเป็น PoS, ภาระไม่เท่ากัน | sha256(round+members) mod n เปิดเผย ตรวจย้อนได้ | รู้ leader ล่วงหน้า → เป้าของ eclipse/DoS (Yang 2022) และ leader ประสงค์ร้าย (ZTA 2023) |
| merge | avg / weighted / min / max / median | FedAvg ถ่วงด้วยจำนวนตัวอย่าง | robust aggregation ต้าน backdoor/poisoning (Chen 2023, ZTA 2023, PenTiDef) |
| สิ่งที่อยู่บนเชน | metadata: สถานะโมเดล, ความคืบหน้า | hash ของ weight, ผู้ส่ง, leader, accuracy ต่อรอบ | ประวัติ update + trust score (PenTiDef, DSL) |
| ความลับของ parameter | ส่งดิบระหว่างโหนด | ส่งดิบ (นอกเชน) | HE/FHE (Swarm-FHE) หรือ distributed DP (PenTiDef, RFF-SL) |
| ผู้ร่วมขั้นต่ำ | min_peers | quorum ใน chaincode | timeout เมื่อ leader หาย |
