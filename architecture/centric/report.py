"""Turn results/runs/*.json into results/REPORT.md and its figures.

    python report.py

Every number in the report is read from the run files; the paper's numbers are the
constants below, copied from Tables 5-9 of Bilal et al. (2026).
"""

from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import data

HERE = Path(__file__).resolve().parent
RUNS = HERE / "results" / "runs"
OUT = HERE / "results"
FIGS = OUT / "figures"

MODELS = ("lstm", "transformer")
ALGORITHMS = ("fedavg", "fedprox", "fednova")
NAMES = {"lstm": "LSTM", "transformer": "Transformer", "fedavg": "FedAvg", "fedprox": "FedProx",
         "fednova": "FedNova", "fl": "FL", "sl": "SL", "edge": "Edge-IIoTset", "cic": "CIC-IoT2023",
         "tii": "TII-SSRC-23", "combined": "Combined"}

# Tables 5-8: accuracy, precision, recall, F1, AUC (percent)
PAPER = {
    "edge": {("fedavg", "lstm"): (96.0, 94.0, 92.0, 93.0, 97.5), ("fedavg", "transformer"): (97.0, 96.0, 94.0, 95.0, 98.0),
             ("fedprox", "lstm"): (96.5, 95.0, 93.0, 94.0, 97.8), ("fedprox", "transformer"): (97.5, 96.5, 95.0, 95.7, 98.5),
             ("fednova", "lstm"): (97.0, 95.5, 94.0, 94.7, 98.0), ("fednova", "transformer"): (98.0, 97.0, 96.0, 96.5, 99.0)},
    "cic": {("fedavg", "lstm"): (95.0, 93.0, 91.0, 92.0, 96.0), ("fedavg", "transformer"): (96.0, 94.0, 92.5, 93.2, 97.0),
            ("fedprox", "lstm"): (95.5, 93.5, 92.0, 92.7, 96.5), ("fedprox", "transformer"): (96.5, 95.0, 93.5, 94.2, 97.5),
            ("fednova", "lstm"): (96.0, 94.0, 93.0, 93.5, 97.0), ("fednova", "transformer"): (97.0, 96.0, 94.5, 95.2, 98.0)},
    "tii": {("fedavg", "lstm"): (92.0, 90.0, 87.0, 88.5, 94.0), ("fedavg", "transformer"): (93.0, 91.0, 89.0, 90.0, 95.0),
            ("fedprox", "lstm"): (93.0, 91.0, 90.0, 90.5, 95.0), ("fedprox", "transformer"): (94.0, 92.5, 91.0, 91.7, 96.0),
            ("fednova", "lstm"): (93.5, 92.0, 90.5, 91.2, 95.5), ("fednova", "transformer"): (95.0, 94.0, 92.0, 93.0, 97.0)},
    "combined": {("fedavg", "lstm"): (91.5, 89.0, 88.2, 88.6, 96.2), ("fedavg", "transformer"): (92.7, 90.3, 89.6, 89.9, 97.1),
                 ("fedprox", "lstm"): (92.1, 89.8, 89.1, 89.4, 96.6), ("fedprox", "transformer"): (93.4, 91.3, 90.5, 90.9, 97.5),
                 ("fednova", "lstm"): (93.0, 90.6, 90.0, 90.3, 97.0), ("fednova", "transformer"): (94.2, 92.1, 91.4, 91.7, 98.0)},
}
# Table 9: combined federation, Transformer. Rounds to 95%, MB exchanged, minutes
PAPER_COST = {"fedavg": (50, 1500, 100), "fedprox": (55, 1650, 110), "fednova": (40, 1200, 80)}

# reference palette (dataviz skill), slots 1-3: validated all-pairs, light surface
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"


def load() -> dict[tuple[str, str, str, str], dict]:
    runs = {}
    for path in RUNS.glob("*/*.json"):
        r = json.loads(path.read_text(encoding="utf-8"))
        runs[(r["scenario"], r["architecture"], r["model"], r["algorithm"])] = r
    return runs


def pct(x: float) -> str:
    return "-" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{100 * x:.1f}"


# ---------- tables ----------

def equivalence(runs: dict) -> tuple[str, int, int]:
    pairs = [(fl, runs.get((s, "sl", m, a))) for (s, arch, m, a), fl in runs.items() if arch == "fl"]
    pairs = [(fl, sl) for fl, sl in pairs if sl is not None]
    final = sum(fl["final_hash"] == sl["final_hash"] for fl, sl in pairs)
    rounds = sum(len(fl["history"]) for fl, _ in pairs)
    same_rounds = sum(a["global_hash"] == b["global_hash"]
                      for fl, sl in pairs for a, b in zip(fl["history"], sl["history"]))
    verified = sum(bool(h.get("verified")) for _, sl in pairs for h in sl["history"])
    rejected = sum(sl["coordinator"].get("rejected_updates", 0) for _, sl in pairs)
    text = (f"| คู่ FL/SL ที่เทียบ | โมเดลสุดท้ายเหมือนกันทุกบิต | รอบที่ global model เหมือนกันทุกบิต | "
            f"รอบ SL ที่ทุกโหนดตรวจ hash กับ ledger ผ่าน | update ที่ leader ปฏิเสธ |\n|---|---|---|---|---|\n"
            f"| {len(pairs)} | {final} / {len(pairs)} | {same_rounds} / {rounds} | {verified} / {rounds} | {rejected} |")
    return text, final, len(pairs)


def metrics_table(runs: dict, scenario: str) -> str:
    paper = PAPER.get(scenario)
    head = ("| Model | Algorithm | " + ("Paper Acc | Paper F1 | Paper AUC | " if paper else "")
            + "FL Acc | FL Prec | FL Rec | FL F1 | FL AUC | SL Acc | SL F1 | SL AUC | FL = SL |")
    lines = [head, "|" + "---|" * (head.count("|") - 1)]
    for m in MODELS:
        for a in ALGORITHMS:
            fl, sl = runs.get((scenario, "fl", m, a)), runs.get((scenario, "sl", m, a))
            if fl is None and sl is None:
                continue
            row = [NAMES[m], NAMES[a]]
            if paper:
                p = paper[(a, m)]
                row += [f"{p[0]:.1f}", f"{p[3]:.1f}", f"{p[4]:.1f}"]
            t = fl["test"] if fl else {}
            row += [pct(t.get("accuracy")), pct(t.get("precision")), pct(t.get("recall")),
                    f"**{pct(t.get('f1'))}**" if fl else "-", pct(t.get("auc"))]
            u = sl["test"] if sl else {}
            row += [pct(u.get("accuracy")), f"**{pct(u.get('f1'))}**" if sl else "-", pct(u.get("auc"))]
            row.append(("ใช่" if fl["final_hash"] == sl["final_hash"] else "**ไม่**") if fl and sl else "-")
            lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def ceilings(scenarios: list[str], rows: int, source: str) -> str:
    """Not part of the paper: centralized gradient boosting on exactly the same features,
    splits and per-client scaling. It shows how much signal the features carry, which is
    what separates "the federation learned poorly" from "there was little to learn"."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import accuracy_score, f1_score

    have = data.available(source)
    if any(s != "combined" and data.dataset_of(s) not in have for s in scenarios):
        return f"_ข้อมูล {source} ที่ใช้รันไม่อยู่ในเครื่องแล้ว จึงคำนวณตารางนี้ไม่ได้_"
    pools: dict = {}
    lines = ["| Scenario | boosting Acc | boosting macro-F1 | majority-class Acc |", "|---|---|---|---|"]
    for s in scenarios:
        # data.build is deterministic: the same budget gives the rows the runs trained on
        fed = data.build(s, rows, pools, source=source)
        X, y = fed.stacked("train")
        Xt, yt = fed.stacked("test")
        pred = HistGradientBoostingClassifier(max_iter=100, random_state=0).fit(X, y).predict(Xt)
        lines.append(f"| {s} | {pct(accuracy_score(yt, pred))} | {pct(f1_score(yt, pred, average='macro'))} | "
                     f"{pct(np.bincount(yt).max() / len(yt))} |")
    return "\n".join(lines)


def per_round(run: dict, key: str) -> float:
    return statistics.fmean(h[key] for h in run["history"])


def cost_table(runs: dict) -> str:
    head = ("| Scenario | Model | clients | FL train s/round | SL train s/round | SL ledger s/round | "
            "SL ledger ÷ round | FL MB/round | SL MB/round | ledger tx/round |")
    lines = [head, "|" + "---|" * (head.count("|") - 1)]
    for scenario in data.SCENARIOS:
        for m in MODELS:
            fls = [runs[(scenario, "fl", m, a)] for a in ALGORITHMS if (scenario, "fl", m, a) in runs]
            sls = [runs[(scenario, "sl", m, a)] for a in ALGORITHMS if (scenario, "sl", m, a) in runs]
            if not fls or not sls:
                continue
            fl_train = statistics.fmean(per_round(r, "train_seconds") for r in fls)
            sl_train = statistics.fmean(per_round(r, "train_seconds") for r in sls)
            ledger = statistics.fmean(per_round(r, "coordination_seconds") for r in sls)
            share = ledger / (sl_train + ledger)
            fl_mb = statistics.fmean(r["bytes_exchanged"] / len(r["history"]) for r in fls) / 1e6
            sl_mb = statistics.fmean(r["bytes_exchanged"] / len(r["history"]) for r in sls) / 1e6
            # one SubmitUpdate per node, one RecordAggregation per round
            tx = len(sls[0]["clients"]) + 1
            lines.append(f"| {scenario} | {NAMES[m]} | {len(fls[0]['clients'])} | {fl_train:.1f} | "
                         f"{sl_train:.1f} | {ledger:.2f} | {100 * share:.0f}% | {fl_mb:.2f} | {sl_mb:.2f} | {tx} |")
    return "\n".join(lines)


def table9(runs: dict) -> str:
    head = ("| Model | Algorithm | Paper rounds→95% | Paper MB | Paper min | rounds→95% (FL = SL) | "
            "FL MB | SL MB | FL min | SL min | SL ledger min |")
    lines = [head, "|" + "---|" * (head.count("|") - 1)]
    for m in MODELS:
        for a in ALGORITHMS:
            fl, sl = runs.get(("combined", "fl", m, a)), runs.get(("combined", "sl", m, a))
            if not fl or not sl:
                continue
            p = PAPER_COST[a] if m == "transformer" else ("-", "-", "-")
            reached = fl["rounds_to_target"]
            lines.append(
                f"| {NAMES[m]} | {NAMES[a]} | {p[0]} | {p[1]} | {p[2]} | {reached or 'ไม่ถึง'} | "
                f"{fl['bytes_exchanged'] / 1e6:.0f} | {sl['bytes_exchanged'] / 1e6:.0f} | "
                f"{fl['seconds']['total'] / 60:.1f} | {sl['seconds']['total'] / 60:.1f} | "
                f"{sl['seconds']['coordination'] / 60:.1f} |")
    return "\n".join(lines)


def cross_table(runs: dict) -> str:
    """Rows: the source a model was trained on. Columns: the dataset it is tested on.
    Diagonal: the -h run's own test split. Averaged over the three algorithms, FL runs
    (the SL runs are the same models; equivalence() checks that)."""
    have = [d for d in ("edge", "cic", "tii") if any(k[0] == f"{d}-h" for k in runs)]
    if not have:
        return "_ยังไม่มีผล_"
    lines = []
    for m in MODELS:
        head = f"| {NAMES[m]}: train ↓ / test → | " + " | ".join(NAMES[d] for d in have) + " |"
        lines += [head, "|" + "---|" * (len(have) + 1)]
        for src in have:
            cells = []
            for tgt in have:
                vals = []
                for a in ALGORITHMS:
                    r = runs.get((f"{src}-h", "fl", m, a))
                    if r is None:
                        continue
                    vals.append(r["test"]["f1"] if tgt == src else r["cross"].get(tgt, {}).get("f1"))
                vals = [v for v in vals if v is not None]
                cells.append(pct(statistics.fmean(vals)) if vals else "-")
            lines.append(f"| {NAMES[src]} | " + " | ".join(cells) + " |")
        combined = [runs.get(("combined", "fl", m, a)) for a in ALGORITHMS]
        combined = [r for r in combined if r]
        if combined:
            cells = []
            for tgt in have:
                vals = [r["cross"][tgt]["f1"] for r in combined if tgt in r["cross"]]
                cells.append(pct(statistics.fmean(vals)) if vals else "-")
            lines.append("| **Combined** | " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines)


# ---------- figures ----------

def style(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=8)
    ax.yaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def fig_f1(runs: dict) -> Path | None:
    """Fig. 8 counterpart: macro-F1 per algorithm and backbone, the paper beside ours."""
    scenarios = [s for s in ("edge", "cic", "tii", "combined") if any(k[0] == s for k in runs)]
    if not scenarios:
        return None
    fig, axes = plt.subplots(1, len(scenarios), figsize=(3.6 * len(scenarios), 3.4), sharey=True,
                             facecolor=SURFACE)
    axes = np.atleast_1d(axes)
    for ax, s in zip(axes, scenarios):
        style(ax)
        labels, paper, ours = [], [], []
        for m in MODELS:
            for a in ALGORITHMS:
                r = runs.get((s, "fl", m, a))
                labels.append(f"{NAMES[a]}\n{'LSTM' if m == 'lstm' else 'Trf'}")
                paper.append(PAPER[s][(a, m)][3])
                ours.append(100 * r["test"]["f1"] if r else np.nan)
        x = np.arange(len(labels))
        w = 0.38
        ax.bar(x - w / 2 - 0.01, paper, w, color=BLUE, label="Paper (FL)")
        bars = ax.bar(x + w / 2 + 0.01, ours, w, color=ORANGE, label="Ours: FL = SL")
        for b, v in zip(bars, ours):
            if not np.isnan(v):
                ax.text(b.get_x() + b.get_width() / 2, v + 1, f"{v:.0f}", ha="center", va="bottom",
                        fontsize=7, color=INK_2)
        ax.set_xticks(x, labels, fontsize=7)
        ax.set_title(NAMES[s], fontsize=10, color=INK, loc="left")
        ax.set_ylim(0, 105)
    axes[0].set_ylabel("macro-F1 (%)", color=INK_2, fontsize=9)
    handles, names = axes[0].get_legend_handles_labels()
    fig.legend(handles, names, frameon=False, fontsize=8, loc="upper right", ncol=2, labelcolor=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    return save(fig, "f1_vs_paper.png")


def fig_round_time(runs: dict) -> Path | None:
    """Where a round's time goes: local training versus agreeing on the ledger."""
    rows = []
    for s in data.SCENARIOS:
        for m in MODELS:
            for arch in ("fl", "sl"):
                rs = [runs[(s, arch, m, a)] for a in ALGORITHMS if (s, arch, m, a) in runs]
                if rs:
                    rows.append((f"{s} · {NAMES[m]} · {NAMES[arch]}",
                                 statistics.fmean(per_round(r, "train_seconds") for r in rs),
                                 statistics.fmean(per_round(r, "aggregate_seconds") + per_round(r, "coordination_seconds")
                                                  for r in rs)))
    if not rows:
        return None
    fig, ax = plt.subplots(figsize=(7.5, 0.32 * len(rows) + 1.2), facecolor=SURFACE)
    style(ax)
    ax.yaxis.grid(False)
    ax.xaxis.grid(True, color=GRID, linewidth=0.6)
    y = np.arange(len(rows))[::-1]
    train = np.array([r[1] for r in rows])
    coord = np.array([r[2] for r in rows])
    ax.barh(y, train, 0.62, color=BLUE, label="local training (all clients)")
    ax.barh(y, coord, 0.62, left=train + 0.05, color=ORANGE, label="merge + ledger")
    for yi, t, c in zip(y, train, coord):
        if c >= 0.05:                     # FL's merge is milliseconds: nothing to label
            ax.text(t + c + 0.3, yi, f"+{c:.1f}s", va="center", fontsize=7, color=INK_2)
    ax.set_yticks(y, [r[0] for r in rows], fontsize=7)
    ax.set_xlabel("seconds per round (mean of the three algorithms)", color=INK_2, fontsize=8)
    fig.legend(*ax.get_legend_handles_labels(), frameon=False, fontsize=8, loc="upper right",
               ncol=2, labelcolor=INK)
    fig.tight_layout(rect=(0, 0, 1, 1 - 0.5 / fig.get_figheight()))
    return save(fig, "round_time.png")


def fig_convergence(runs: dict) -> Path | None:
    """Fig. 9 counterpart, against rounds (where FL and SL coincide) and wall time (where
    they do not)."""
    model = "transformer"
    have = [a for a in ALGORITHMS if ("combined", "fl", model, a) in runs and ("combined", "sl", model, a) in runs]
    if not have:
        return None
    fig, (left, right) = plt.subplots(1, 2, figsize=(10, 3.6), facecolor=SURFACE)
    colors = dict(zip(ALGORITHMS, (BLUE, ORANGE, AQUA)))
    for a in have:
        fl, sl = runs[("combined", "fl", model, a)], runs[("combined", "sl", model, a)]
        acc = [100 * h["val_accuracy"] for h in fl["history"]]
        left.plot(range(1, len(acc) + 1), acc, color=colors[a], linewidth=2, label=NAMES[a])
        left.annotate(NAMES[a], (len(acc), acc[-1]), xytext=(4, 0), textcoords="offset points",
                      fontsize=7, color=INK_2, va="center")
    style(left)
    left.set_title("validation accuracy by round — FL and SL lines coincide", fontsize=9, color=INK, loc="left")
    left.set_xlabel("communication round", color=INK_2, fontsize=8)
    left.set_ylabel("accuracy (%)", color=INK_2, fontsize=8)
    left.legend(frameon=False, fontsize=8, labelcolor=INK)

    a = "fednova" if "fednova" in have else have[0]
    for arch, color in (("fl", BLUE), ("sl", ORANGE)):
        r = runs[("combined", arch, model, a)]
        per = [h["train_seconds"] + h["aggregate_seconds"] + h["coordination_seconds"] for h in r["history"]]
        t = np.cumsum(per) / 60
        acc = [100 * h["val_accuracy"] for h in r["history"]]
        right.plot(t, acc, color=color, linewidth=2, label=f"{NAMES[arch]} ({t[-1]:.0f} min)")
    style(right)
    right.set_title(f"the same curve against wall time ({NAMES[a]}, Transformer)", fontsize=9, color=INK, loc="left")
    right.set_xlabel("minutes (training + merge + ledger)", color=INK_2, fontsize=8)
    right.legend(frameon=False, fontsize=8, labelcolor=INK)
    fig.tight_layout()
    return save(fig, "convergence.png")


def fig_confusion(runs: dict) -> Path | None:
    """Figs. 4-7 counterpart: the Transformer + FedNova test confusion, row-normalised."""
    picks = [s for s in ("edge", "cic", "tii", "combined") if (s, "fl", "transformer", "fednova") in runs]
    if not picks:
        return None
    fig, axes = plt.subplots(1, len(picks), figsize=(3.4 * len(picks), 3.4), facecolor=SURFACE)
    axes = np.atleast_1d(axes)
    for ax, s in zip(axes, picks):
        r = runs[(s, "fl", "transformer", "fednova")]
        m = np.array(r["test"]["confusion"], dtype=float)
        m = m / np.maximum(m.sum(axis=1, keepdims=True), 1)
        ax.imshow(m, cmap=matplotlib.colors.LinearSegmentedColormap.from_list(
            "blue", ["#ffffff", "#cde2fb", "#6da7ec", "#256abf", "#0d366b"]), vmin=0, vmax=1)
        names = [c[:6] for c in r["classes"]]
        ax.set_xticks(range(len(names)), names, rotation=60, fontsize=6, color=INK_2)
        ax.set_yticks(range(len(names)), names, fontsize=6, color=INK_2)
        for i in range(len(names)):
            for j in range(len(names)):
                if m[i, j] >= 0.05:
                    ax.text(j, i, f"{100 * m[i, j]:.0f}", ha="center", va="center", fontsize=6,
                            color="#ffffff" if m[i, j] > 0.5 else INK)
        ax.set_title(NAMES[s], fontsize=9, color=INK, loc="left")
        ax.set_xlabel("predicted", fontsize=7, color=INK_2)
    axes[0].set_ylabel("true", fontsize=7, color=INK_2)
    fig.tight_layout()
    return save(fig, "confusion.png")


def save(fig, name: str) -> Path:
    FIGS.mkdir(parents=True, exist_ok=True)
    path = FIGS / name
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    return path


# ---------- the report ----------

def main() -> None:
    import argparse

    global RUNS, OUT, FIGS
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("experiment", nargs="?", default=str(HERE / "results" / "full-500k"),
                        help="an experiment folder made by run.py (default results/full-500k)")
    args = parser.parse_args()
    OUT = Path(args.experiment).resolve()
    RUNS, FIGS = OUT / "runs", OUT / "figures"
    runs = load()
    if not runs:
        raise SystemExit(f"no results in {RUNS}; run python run.py first")
    eq_text, same, pairs = equivalence(runs)
    any_run = next(iter(runs.values()))
    # the first experiment (subset-50k) predates these two fields
    source = any_run.get("source", "subset")
    budget = any_run.get("rows_budget", 50_000)
    scenarios = [s for s in data.SCENARIOS if any(k[0] == s for k in runs)]
    figs = {name: fn(runs) for name, fn in (("f1", fig_f1), ("time", fig_round_time),
                                             ("conv", fig_convergence), ("conf", fig_confusion))}
    rel = lambda p: p.relative_to(OUT).as_posix() if p else None

    rows = {s: next(r for k, r in runs.items() if k[0] == s) for s in scenarios}
    setup = "\n".join(
        f"| {s} | {len(r['clients'])} | {r['rows_drawn']:,} | {sum(c['train'] for c in r['clients']):,} | "
        f"{r['n_features']} | {len(r['classes'])} ({', '.join(r['classes'])}) | {r['rounds']} |"
        for s, r in rows.items())

    parts = [
        "# ผลการทดลอง: FL เทียบ SL บนโจทย์ของ Bilal et al. (2026)",
        "",
        f"> สร้างโดย `python report.py {OUT.relative_to(HERE).as_posix()}` จากไฟล์ใน `runs/` ของโฟลเดอร์นี้ "
        "ทุกตัวเลขในหน้านี้อ่านจากไฟล์ผล ส่วนตัวเลขของเปเปอร์คัดจาก Tables 5–9",
        "",
        (f"ข้อมูล: ฉบับเต็มของทั้งสามชุด (`--source full`) สุ่ม {budget:,} แถวต่อ scenario ตามสัดส่วนจริงของแต่ละชุด"
         if source == "full" else
         f"ข้อมูล: มิเรอร์ฉบับเล็ก (`--source subset`) สุ่ม {budget:,} แถวต่อ scenario"),
        "",
        "## ชุดทดลองที่รัน",
        "",
        "| Scenario | clients | แถวที่สุ่มมา | แถวเทรน | features | classes | rounds |",
        "|---|---|---|---|---|---|---|",
        setup,
        "",
        f"ทุก run ใช้ E = {any_run['hyper']['epochs']}, batch {any_run['hyper']['batch']}, Adam "
        f"(weight decay {any_run['hyper']['weight_decay']}), μ = {any_run['hyper']['mu']} สำหรับ FedProx, "
        "lr 0.001 (LSTM) / 0.0005 (Transformer) ตาม Table 4",
        "",
    ]
    ftz = sorted({k[0] for k, r in runs.items() if r.get("flush_denormal")})
    if ftz:
        parts += [f"Scenario ที่รันด้วย `--flush-denormal` (ทั้ง FL และ SL): {', '.join(ftz)} — "
                  "ค่าที่เล็กกว่า 1e-38 ถูกปัดเป็นศูนย์เพื่อความเร็ว ต่างจากไม่ปัดแค่บิตท้ายๆ (ดู README)", ""]
    parts += [
        "## 1. FL กับ SL ได้โมเดลเดียวกันไหม",
        "",
        eq_text,
        "",
        ("**ได้โมเดลเดียวกันทุกบิตในทุกคู่** ข้อมูล seed และสูตร aggregation เหมือนกัน "
         "สิ่งที่ SL เปลี่ยนคือใครเป็นคนรวมโมเดล (leader ที่ chaincode เลือก แทน server) "
         "และการบันทึก/ตรวจสอบบน ledger ซึ่งไม่แตะตัวเลขของโมเดลเลย ความแม่นยำของ FL และ SL จึงเท่ากันพอดี "
         "ความต่างอยู่ที่ต้นทุน (หัวข้อ 3) และความน่าเชื่อถือ (README)"
         if same == pairs else
         "**มีบางคู่ที่ไม่เหมือนกันทุกบิต** — ดูคอลัมน์ FL = SL ในตารางหัวข้อ 2"),
        "",
        ("ชุดนี้เทรน client ครั้งเดียวต่อรอบ แล้วส่ง update ชุดเดียวกันให้ server ของ FL และ swarm ของ SL ไปรวมแยกกัน "
         "(รอบ subset-50k ที่รันแยกกันทั้งหมดได้ global model ตรงกัน 1,050 / 1,050 รอบ) run จะหยุดทันทีถ้าสองทางได้โมเดลต่างกัน "
         "เวลาเทรนของ FL กับ SL ในหัวข้อ 3 จึงเป็นตัวเลขเดียวกัน ต่างกันที่เวลารวมโมเดลกับเวลาที่รอ Fabric"
         if len(any_run.get("trained_with", [])) > 1 else
         "ชุดนี้รัน FL กับ SL แยกกันทั้งหมด (เทรนแยก, seed เดียวกัน)"),
        "",
        "## 2. ความแม่นยำบนชุดทดสอบ (Tables 5–8)",
        "",
        "ค่าเป็น % · Precision / Recall / F1 เป็น macro · AUC เป็น macro one-vs-rest · "
        "คอลัมน์ Paper คือตัวเลขในเปเปอร์ (FL ทั้งหมด)",
        "",
    ]
    for s in scenarios:
        parts += [f"### {s}" + (f" — {NAMES.get(data.dataset_of(s), s)}" if s in NAMES else ""), "",
                  metrics_table(runs, s), ""]
    if figs["f1"]:
        parts += [f"![macro-F1 เทียบเปเปอร์]({rel(figs['f1'])})", ""]
    parts += [
        "### ข้อมูลชุดนี้มีสัญญาณให้เรียนแค่ไหน (ไม่ใช่ส่วนของเปเปอร์)",
        "",
        "Gradient boosting แบบรวมศูนย์บน feature, split และ scaler ต่อ client ชุดเดียวกับทุก run "
        "ใช้เป็นเพดานอ้างอิงว่า feature เหล่านี้แยกคลาสได้แค่ไหน — ถ้า federated model ต่ำกว่าเพดานมาก "
        "คือการเรียนแบบกระจายเสียไป ถ้าเพดานเองต่ำ คือข้อมูลมีให้เรียนน้อย",
        "",
        ceilings(scenarios, budget, source),
        "",
    ]
    if figs["conf"]:
        parts += ["Confusion matrix (Transformer + FedNova, normalise ตามแถว, ค่า % · FL = SL):", "",
                  f"![confusion]({rel(figs['conf'])})", ""]
    parts += [
        "## 3. ต้นทุนของแต่ละสถาปัตยกรรม",
        "",
        "ต่อรอบ เฉลี่ยสาม algorithm · MB/round ของ FL ใช้สูตรเดียวกับ Table 9 "
        "(2 × clients × parameters × 4 bytes) · SL ส่งระหว่างโหนดโดยตรง leader ไม่ต้องส่ง update ของตัวเอง "
        "· เวลาเทรนรันขนานหลาย lane บน CPU เครื่องเดียว จึงเทียบกันได้ภายในตารางเดียวกันเท่านั้น",
        "",
        cost_table(runs),
        "",
    ]
    if figs["time"]:
        parts += [f"![เวลาต่อรอบ]({rel(figs['time'])})", ""]
    parts += ["### Table 9 — combined federation", "", table9(runs), ""]
    if figs["conv"]:
        parts += [f"![convergence]({rel(figs['conv'])})", ""]
    parts += [
        "## 4. ข้ามชุดข้อมูล (Section 5.3)",
        "",
        "macro-F1 (%) เฉลี่ยสาม algorithm · แถว = ชุดที่ใช้เทรน (schema ร่วม 10 features, 4 classes) "
        "· คอลัมน์ = ชุดที่ใช้ทดสอบ · ทแยง = ทดสอบในชุดเดียวกัน · Combined = โมเดลที่เทรนรวมทุกชุด "
        "ทดสอบกับ test split ของแต่ละชุด",
        "",
        cross_table(runs),
    ]
    (OUT / "REPORT.md").write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"wrote {OUT / 'REPORT.md'} from {len(runs)} runs; figures in {FIGS}")


if __name__ == "__main__":
    main()
