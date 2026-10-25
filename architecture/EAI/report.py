"""results/REPORT.md and results/figures/ from the run records, set against the paper's tables.

    python report.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
FIGURES = RESULTS / "figures"
MODELS = ("packet", "flow", "multimodal")
MERGES = ("mean", "coordmedian", "geomedian")
COLORS = {"mean": "#1f77b4", "coordmedian": "#d62728", "geomedian": "#2ca02c"}

# Tables 13-15: accuracy, precision, recall, F1 (%); None where the paper has no such row
PAPER = {
    1: {("cl", "packet"): (100, 100, 100, 100), ("cl", "flow"): (96.85, 94.28, 99.88, 97.00),
        ("cl", "multimodal"): (100, 100, 100, 100),
        ("sl", "packet", "mean"): (100, 100, 100, 100), ("sl", "packet", "coordmedian"): (100, 99.99, 100, 99.99),
        ("sl", "packet", "geomedian"): (100, 100, 100, 100),
        ("sl", "flow", "mean"): (96.59, 93.96, 99.70, 96.75), ("sl", "flow", "coordmedian"): (96.27, 93.94, 99.06, 96.43),
        ("sl", "flow", "geomedian"): (96.27, 93.94, 99.06, 96.43),
        ("sl", "multimodal", "mean"): (99.96, 100, 99.92, 99.96),
        ("sl", "multimodal", "coordmedian"): (99.52, 99.32, 99.75, 99.53),
        ("sl", "multimodal", "geomedian"): (99.50, 99.26, 99.75, 99.50)},
    2: {("cl", "packet"): (100, 100, 100, 100), ("cl", "flow"): (95.46, 95.78, 96.10, 95.94),
        ("cl", "multimodal"): (100, 100, 100, 100),
        ("sl", "multimodal", "mean"): (98.62, 98.81, 98.71, 98.76),
        ("sl", "multimodal", "coordmedian"): (83.26, 84.83, 85.24, 85.03),
        ("sl", "multimodal", "geomedian"): (83.91, 84.87, 86.59, 85.72)},
    3: {("cl", "packet"): (100, 100, 100, 100), ("cl", "flow"): (95.46, 95.78, 96.10, 95.94),
        ("cl", "multimodal"): (100, 100, 100, 100),
        ("sl", "packet", "mean"): (97.17, 99.82, 95.09, 97.40), ("sl", "packet", "coordmedian"): (94.05, 99.03, 90.22, 94.42),
        ("sl", "packet", "geomedian"): (95.00, 99.02, 91.95, 95.35),
        ("sl", "flow", "mean"): (70.70, 87.93, 55.02, 67.69), ("sl", "flow", "coordmedian"): (73.65, 81.87, 67.76, 74.15),
        ("sl", "flow", "geomedian"): (75.01, 82.38, 70.22, 75.82),
        ("sl", "multimodal", "mean"): (92.62, 99.78, 86.95, 92.93),
        ("sl", "multimodal", "coordmedian"): (89.20, 96.58, 83.60, 89.62),
        ("sl", "multimodal", "geomedian"): (89.69, 96.88, 84.24, 90.12)},
}
# Table 16: average test loss of the multimodal swarm
PAPER_LOSS = {"mean": (0.0039, 0.0352, 0.1968), "coordmedian": (0.0181, 0.7622, 0.5151),
              "geomedian": (0.0177, 0.7655, 0.4760)}
PAPER_ROUNDS = {2: 27, 3: 18}


VARIANTS = ("", "weighted", "inactive", "weighted-inactive")
VARIANT_LABELS = {"": "เปเปอร์ (equal, snapshot)", "weighted": "ถ่วงด้วยจำนวนข้อมูล",
                  "inactive": "inactive", "weighted-inactive": "ถ่วง + inactive"}
TYPES = ("Benign", "DDoS_HTTP", "DDoS_ICMP", "DDoS_TCP", "DDoS_UDP",
         "MQTT-DDoS-Connect_Flood", "MQTT-DDoS-Publish_Flood")


def load() -> tuple[dict, dict]:
    """The runs with SwarmCallback's defaults (and CL), keyed (scenario, arch, model, merge),
    and the swarm runs that change them, keyed (scenario, model, merge, variant)."""
    runs, variants = {}, {}
    for path in sorted((RESULTS / "runs").glob("scenario*/*.json")):
        r = json.loads(path.read_text())
        if r.get("variant"):
            variants[(r["scenario"], r["model"], r["merge"], r["variant"])] = r
        else:
            runs[(r["scenario"], r["architecture"], r["model"], r["merge"])] = r
    return runs, variants


def pct(x: float) -> str:
    return f"{100 * x:.2f}"


def row_key(arch: str, model: str, merge: str | None) -> tuple:
    return (arch, model) if arch == "cl" else (arch, model, merge)


def results_table(runs: dict, n: int) -> list[str]:
    lines = ["| สถาปัตยกรรม | โมเดล | merge | Accuracy | Precision | Recall | F1 | test loss | เปเปอร์ (Acc / P / R / F1) |",
             "|---|---|---|---|---|---|---|---|---|"]
    for arch in ("cl", "sl"):
        for model in MODELS:
            for merge in ((None,) if arch == "cl" else MERGES):
                r = runs.get((n, arch, model, merge))
                paper = PAPER[n].get(row_key(arch, model, merge))
                if r is None and paper is None:
                    continue
                cells = ["—"] * 5 if r is None else [pct(r["test"][k]) for k in ("accuracy", "precision", "recall", "f1")] \
                    + [f"{r['test']['loss']:.4f}"]
                ref = " / ".join(f"{v:.2f}" for v in paper) if paper else "ไม่มีในเปเปอร์"
                lines.append(f"| {arch.upper()} | {model} | {merge or '—'} | " + " | ".join(cells) + f" | {ref} |")
    return lines


def curves(runs: dict, n: int) -> str | None:
    """Average validation accuracy and loss per round (Figs. 9, 11, 12, 14, 15)."""
    have = [m for m in MODELS if any((n, "sl", m, g) in runs for g in MERGES)]
    if not have:
        return None
    fig, axes = plt.subplots(2, len(have), figsize=(4.6 * len(have), 6.4), squeeze=False)
    for j, model in enumerate(have):
        for merge in MERGES:
            r = runs.get((n, "sl", model, merge))
            if r is None:
                continue
            rounds = [h["round"] for h in r["history"]]
            axes[0][j].plot(rounds, [h["val_accuracy"] for h in r["history"]], label=merge, color=COLORS[merge])
            axes[1][j].plot(rounds, [h["val_loss"] for h in r["history"]], label=merge, color=COLORS[merge])
        axes[0][j].set_title(f"Scenario {n} · {model}")
        axes[0][j].set_ylabel("average validation accuracy")
        axes[1][j].set_ylabel("average validation loss")
        axes[1][j].set_xlabel("aggregation round")
        for ax in (axes[0][j], axes[1][j]):
            ax.grid(alpha=0.3)
            ax.legend(fontsize=8)
    fig.tight_layout()
    name = f"scenario{n}-validation.png"
    fig.savefig(FIGURES / name, dpi=120)
    plt.close(fig)
    return name


def host_curves(runs: dict, n: int) -> str | None:
    """The multimodal swarm's merged model on each host's own validation rows, per round:
    the average of Figs. 11-15 hides which host the merge serves."""
    have = [m for m in MERGES if (n, "sl", "multimodal", m) in runs]
    if not have:
        return None
    fig, axes = plt.subplots(1, len(have), figsize=(4.6 * len(have), 3.4), squeeze=False)
    for ax, merge in zip(axes[0], have):
        r = runs[(n, "sl", "multimodal", merge)]
        rounds = [h["round"] for h in r["history"]]
        for k, host in enumerate(r["hosts"]):
            ax.plot(rounds, [h["val_by_host"][k]["accuracy"] for h in r["history"]], label=host["name"])
        ax.set_title(f"Scenario {n} · multimodal · {merge}")
        ax.set_xlabel("aggregation round")
        ax.set_ylim(0.3, 1.02)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7)
    axes[0][0].set_ylabel("validation accuracy of each host")
    fig.tight_layout()
    name = f"scenario{n}-hosts.png"
    fig.savefig(FIGURES / name, dpi=120)
    plt.close(fig)
    return name


def confusions(runs: dict, n: int) -> str | None:
    """Figs. 10, 13, 16: the multimodal swarm's confusion matrices per merge method."""
    have = [m for m in MERGES if (n, "sl", "multimodal", m) in runs]
    if not have:
        return None
    fig, axes = plt.subplots(1, len(have), figsize=(3.6 * len(have), 3.4), squeeze=False)
    for ax, merge in zip(axes[0], have):
        m = runs[(n, "sl", "multimodal", merge)]["test"]["confusion"]
        ax.imshow(m, cmap="Blues")
        for i in range(2):
            for k in range(2):
                ax.text(k, i, f"{m[i][k]:,}", ha="center", va="center",
                        color="white" if m[i][k] > max(map(max, m)) / 2 else "black")
        ax.set_xticks([0, 1], ["benign", "attack"])
        ax.set_yticks([0, 1], ["benign", "attack"])
        ax.set_xlabel("predicted")
        ax.set_title(merge)
    axes[0][0].set_ylabel("actual")
    fig.suptitle(f"Scenario {n} · SL multimodal")
    fig.tight_layout()
    name = f"scenario{n}-confusion.png"
    fig.savefig(FIGURES / name, dpi=120)
    plt.close(fig)
    return name


def ledger_table(swarm_runs: list[dict]) -> list[str]:
    lines = ["| scenario | โมเดล | merge | variant | rounds (ปิดบน ledger) | leader (จำนวนรอบ) | ตรวจ hash ผ่าน | "
             "update ถูกปฏิเสธ | เวลา Fabric (s) | เวลาทั้งหมด (s) | upload (MB) |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    order = lambda r: (r["scenario"], r["model"], r["merge"], VARIANTS.index(r.get("variant", "")))
    for r in sorted(swarm_runs, key=order):
        leaders = ", ".join(f"{k.removesuffix('MSP')} {v}" for k, v in sorted(r["ledger"]["leader_rounds"].items()))
        closed = [h for h in r["history"] if h["leader"] is not None]
        verified = sum(h["verified"] is True for h in closed)
        lines.append(f"| {r['scenario']} | {r['model']} | {r['merge']} | {r.get('variant') or '—'} | "
                     f"{r['rounds']} ({len(closed)}) | {leaders} | {verified}/{len(closed)} | "
                     f"{r['ledger']['rejected_updates']} | {r['seconds']['ledger']:.0f} | {r['seconds']['wall']:.0f} | "
                     f"{r['upload_bytes'] / 1e6:.2f} |")
    return lines


def sensitivity_table(runs: dict, variants: dict, n: int, model: str) -> list[str]:
    """The paper's swarm against the same swarm with nodeWeightage proportional to data and/or
    finished nodes inactive: overall scores and the detection rate of every traffic type."""
    rows = []
    for merge in MERGES:
        for variant in VARIANTS:
            r = runs.get((n, "sl", model, merge)) if not variant else variants.get((n, model, merge, variant))
            if r is not None:
                rows.append((merge, variant, r))
    if not any(v for _, v, _ in rows):
        return []
    lines = ["| merge | variant | Accuracy | F1 | test loss | รอบที่ merge | " + " | ".join(
                 t.replace("MQTT-DDoS-", "MQTT ").replace("_Flood", "") for t in TYPES) + " |",
             "|---|---|---|---|---|---|" + "---|" * len(TYPES)]
    for merge, variant, r in rows:
        t = r["test"]
        merged = r.get("merged_rounds", r["rounds"])
        lines.append(f"| {merge} | {VARIANT_LABELS[variant]} | {pct(t['accuracy'])} | {pct(t['f1'])} | {t['loss']:.4f} | "
                     f"{merged}/{r['rounds']} | " + " | ".join(pct(t["by_type"][k]) if k in t["by_type"] else "—"
                                                            for k in TYPES) + " |")
    return lines


def sensitivity_hosts(runs: dict, variants: dict, n: int, model: str, merge: str = "mean") -> str | None:
    """Each host's validation accuracy per round, for every variant of one merge method."""
    have = [(v, runs.get((n, "sl", model, merge)) if not v else variants.get((n, model, merge, v))) for v in VARIANTS]
    have = [(v, r) for v, r in have if r is not None]
    if len(have) < 2:
        return None
    fig, axes = plt.subplots(1, len(have), figsize=(4.4 * len(have), 3.4), squeeze=False)
    for ax, (variant, r) in zip(axes[0], have):
        rounds = [h["round"] for h in r["history"]]
        for k, host in enumerate(r["hosts"]):
            ax.plot(rounds, [h["val_by_host"][k]["accuracy"] for h in r["history"]], label=host["name"])
        skipped = [h["round"] for h in r["history"] if h["leader"] is None]
        if skipped:
            ax.axvspan(min(skipped) - 0.5, max(skipped) + 0.5, color="grey", alpha=0.15, label="no quorum")
        ax.set_title(f"{merge} · {variant or 'paper defaults'}", fontsize=10)
        ax.set_xlabel("aggregation round")
        ax.set_ylim(0.3, 1.02)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=6)
    axes[0][0].set_ylabel("validation accuracy of each host")
    fig.suptitle(f"Scenario {n} · SL {model}")
    fig.tight_layout()
    name = f"scenario{n}-{model}-{merge}-variants.png"
    fig.savefig(FIGURES / name, dpi=120)
    plt.close(fig)
    return name


def by_type(runs: dict, n: int) -> list[str]:
    """Which traffic the multimodal swarm gets wrong: the detection rate of each type."""
    rows = [(merge, runs[(n, "sl", "multimodal", merge)]) for merge in MERGES if (n, "sl", "multimodal", merge) in runs]
    if (n, "cl", "multimodal", None) in runs:
        rows.insert(0, ("CL", runs[(n, "cl", "multimodal", None)]))
    if not rows:
        return []
    types = sorted({t for _, r in rows for t in r["test"]["by_type"]})
    lines = ["| ชนิดทราฟฟิก | " + " | ".join(m for m, _ in rows) + " |", "|---|" + "---|" * len(rows)]
    for t in types:
        lines.append(f"| {t} | " + " | ".join(pct(r["test"]["by_type"].get(t, float("nan"))) for _, r in rows) + " |")
    return lines


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    runs, variants = load()
    prep = HERE / "data" / "processed" / "prepare.json"
    out = ["# ผลการทำซ้ำ: Multimodal Swarm Learning สำหรับตรวจจับ DDoS บน IoT (Fabric)", "",
           "สร้างโดย `report.py` จากไฟล์ใน `results/runs/` ตัวเลขเปเปอร์มาจาก Tables 13–16 ของ "
           "Nguyen-Khanh et al., *EAI Endorsed Trans. Ind. Netw. Intell. Syst.* 13(1), 2026 "
           "(doi:10.4108/eetinis.131.9961)", ""]
    for n in sorted({k[0] for k in runs}):
        any_run = next(r for k, r in runs.items() if k[0] == n)
        hosts = ", ".join(f"{h['name']} ({h['train']:,}/{h['val']:,}/{h['test']:,})" for h in any_run["hosts"])
        out += [f"## Scenario {n}", "", f"hosts (train/val/test): {hosts} · packet features {any_run['n_features']}", ""]
        sl = [r for k, r in runs.items() if k[0] == n and k[1] == "sl"]
        if sl:
            rounds = sl[0]["rounds"]
            paper = PAPER_ROUNDS.get(n)
            out += [f"SL รอบ aggregation: {rounds}" + (f" (เปเปอร์ {paper})" if paper else ""), ""]
        out += results_table(runs, n) + [""]
        losses = [(m, runs[(n, "sl", "multimodal", m)]["test"]["loss"]) for m in MERGES if (n, "sl", "multimodal", m) in runs]
        if losses:
            out += ["test loss ของ SL multimodal เทียบ Table 16: " + " · ".join(
                f"{m} {loss:.4f} (เปเปอร์ {PAPER_LOSS[m][n - 1]})" for m, loss in losses), ""]
        for name in (curves(runs, n), host_curves(runs, n), confusions(runs, n)):
            if name:
                out += [f"![{name}](figures/{name})", ""]
        table = by_type(runs, n)
        if table:
            out += ["อัตราตรวจถูกต่อชนิดทราฟฟิก (multimodal, %):", ""] + table + [""]
    studied = sorted({(k[0], k[1]) for k in variants})
    if studied:
        out += ["## หาสาเหตุ: น้ำหนักของ node และ node ที่จบก่อน", "",
                "SL ชุดเดิมเทียบกับการเปลี่ยนค่า default ของ SwarmCallback สองตัว: **ถ่วงด้วยจำนวนข้อมูล** "
                "(nodeWeightage = จำนวนแถว train ที่ node ประกาศบน ledger) และ **inactive** "
                "(checkinModelOnTrainEnd: node ที่ครบ 10 epoch แล้วเลิกส่ง weights) เมื่อเหลือ node ที่ยังส่ง weights "
                "น้อยกว่า quorum (majority) chaincode ปิดรอบไม่ได้ จึงไม่มีการ merge ในรอบนั้น "
                "และโมเดลสุดท้ายคือโมเดลของ node ที่ฝึกนานที่สุด (คอลัมน์ 'รอบที่ merge')", ""]
        for n, model in studied:
            out += [f"### Scenario {n} · {model}", "", "อัตราตรวจถูกต่อชนิดทราฟฟิก (%):", ""]
            out += sensitivity_table(runs, variants, n, model) + [""]
            for merge in MERGES:
                name = sensitivity_hosts(runs, variants, n, model, merge)
                if name:
                    out += [f"![{name}](figures/{name})", ""]
    swarm_runs = [r for k, r in runs.items() if k[1] == "sl"] + list(variants.values())
    out += ["## บัญชีบน Fabric", "",
            "ทุกรอบของ SL: ทุก node ส่ง sha256 ของ weights เข้า ledger (เซ็นด้วย cert ของ org ตัวเอง), "
            "chaincode เลือก leader, leader รวมเฉพาะ weights ที่ hash ตรง แล้วบันทึก hash ของโมเดลรวม, "
            "ทุก node ตรวจโมเดลที่ได้กับ hash บน ledger", ""] + ledger_table(swarm_runs) + [""]
    if prep.exists():
        out += ["## ข้อมูลที่เตรียม (`data/processed/prepare.json`)", "", "```json", prep.read_text(), "```", ""]
    (RESULTS / "REPORT.md").write_text("\n".join(out), encoding="utf-8")
    print(f"wrote {RESULTS / 'REPORT.md'}")


if __name__ == "__main__":
    main()
