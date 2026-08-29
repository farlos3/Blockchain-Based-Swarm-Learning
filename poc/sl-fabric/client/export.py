"""Flatten every saved run into two CSV files, for comparing them outside this project.

    python export.py                 # writes results/runs.csv and results/rounds.csv
    python export.py --archive       # include results/archive/ as well

The JSON files are the record, but they are nested and one per run, which is awkward to
compare. These two tables are the same data in the shape a spreadsheet or a dataframe
wants:

    runs.csv    one row per training run — accuracy next to what it cost
    rounds.csv  one row per round — the accuracy curve, and where each round's time went

Both carry dataset, model, alpha, local_epochs and seed, because two runs are only
comparable when those match.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import results as results_io

RUN_COLUMNS = [
    "created", "dataset", "model", "rounds", "local_epochs", "alpha", "seed", "nodes",
    "n_parameters", "kib_per_node_per_round",
    "best_val_accuracy", "final_val_accuracy", "test_accuracy",
    "wall_seconds", "train_seconds", "ledger_seconds",
    "wall_seconds_per_round", "peer_cpu_seconds_per_round", "orderer_cpu_seconds_per_round",
    "blocks_per_round", "transactions_per_round",
    "ledger_bytes_per_round", "off_chain_bytes_per_round",
    "peer_cpu_seconds_per_transaction", "ledger_bytes_per_transaction",
    "peak_rss_mb", "source",
]

ROUND_COLUMNS = [
    "created", "dataset", "model", "local_epochs", "alpha", "seed",
    "round", "leader", "participants", "val_accuracy",
    "train_seconds", "aggregate_seconds", "ledger_seconds",
    "bytes_per_node", "verified",
]


def run_row(payload: dict[str, Any], run: dict[str, Any], source: str) -> dict[str, Any]:
    cost = run.get("cost") or {}
    per_round = cost.get("per_round") or {}
    per_tx = cost.get("per_transaction") or {}
    rounds = run.get("rounds") or []
    return {
        "created": payload.get("created"),
        "dataset": payload.get("dataset"),
        "model": run.get("model"),
        "rounds": len(rounds),
        "local_epochs": payload.get("local_epochs"),
        "alpha": payload.get("alpha"),
        "seed": payload.get("seed"),
        "nodes": cost.get("nodes"),
        "n_parameters": run.get("n_parameters"),
        "kib_per_node_per_round": round(rounds[0]["bytes_per_node"] / 1024, 1) if rounds else None,
        "best_val_accuracy": run.get("best_accuracy"),
        "final_val_accuracy": run.get("final_accuracy"),
        "test_accuracy": run.get("test_accuracy"),
        "wall_seconds": cost.get("wall_seconds") or run.get("total_seconds"),
        "train_seconds": run.get("train_seconds"),
        "ledger_seconds": run.get("ledger_seconds"),
        "wall_seconds_per_round": per_round.get("wall_seconds"),
        "peer_cpu_seconds_per_round": per_round.get("peer_cpu_seconds"),
        "orderer_cpu_seconds_per_round": per_round.get("orderer_cpu_seconds"),
        "blocks_per_round": per_round.get("blocks"),
        "transactions_per_round": per_round.get("transactions"),
        "ledger_bytes_per_round": per_round.get("ledger_bytes"),
        "off_chain_bytes_per_round": per_round.get("off_chain_bytes"),
        "peer_cpu_seconds_per_transaction": per_tx.get("peer_cpu_seconds"),
        "ledger_bytes_per_transaction": per_tx.get("ledger_bytes"),
        "peak_rss_mb": run.get("peak_rss_mb"),
        "source": source,
    }


def round_rows(payload: dict[str, Any], run: dict[str, Any]):
    for entry in run.get("rounds") or []:
        yield {
            "created": payload.get("created"),
            "dataset": payload.get("dataset"),
            "model": run.get("model"),
            "local_epochs": payload.get("local_epochs"),
            "alpha": payload.get("alpha"),
            "seed": payload.get("seed"),
            "round": entry.get("round"),
            "leader": entry.get("leader"),
            "participants": len(entry.get("participants") or []),
            "val_accuracy": entry.get("accuracy"),
            "train_seconds": entry.get("train_seconds"),
            "aggregate_seconds": entry.get("aggregate_seconds"),
            "ledger_seconds": entry.get("ledger_seconds"),
            "bytes_per_node": entry.get("bytes_per_node"),
            "verified": entry.get("verified"),
        }


def collect(include_archive: bool) -> tuple[list[dict], list[dict]]:
    paths = sorted(results_io.RESULTS_DIR.glob("swarm-*.json"))
    if include_archive:
        paths += sorted((results_io.RESULTS_DIR / "archive").glob("swarm-*.json"))

    runs, rounds = [], []
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            print(f"  skipped unreadable {path.name}")
            continue
        for run in payload.get("results", []):
            if not run.get("rounds"):
                continue  # a model that was cancelled before its first round
            runs.append(run_row(payload, run, path.name))
            rounds.extend(round_rows(payload, run))
    return runs, rounds


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--archive", action="store_true",
                        help="include runs that were archived after a network rebuild")
    args = parser.parse_args()

    runs, rounds = collect(args.archive)
    if not runs:
        print("no finished runs to export")
        return 1

    runs_csv = results_io.RESULTS_DIR / "runs.csv"
    rounds_csv = results_io.RESULTS_DIR / "rounds.csv"
    write_csv(runs_csv, RUN_COLUMNS, runs)
    write_csv(rounds_csv, ROUND_COLUMNS, rounds)

    print(f"{len(runs)} runs  -> {runs_csv}")
    print(f"{len(rounds)} rounds -> {rounds_csv}")
    print()
    header = f"{'dataset':7s} {'model':9s} {'rnds':>5s} {'ep':>3s} {'best val':>9s} {'test':>8s} {'s/round':>8s} {'KiB/rnd':>8s}"
    print(header)
    print("-" * len(header))
    for row in sorted(runs, key=lambda r: (r["dataset"] or "", r["model"] or "")):
        print(f"{str(row['dataset']):7s} {str(row['model']):9s} {row['rounds']:5d} "
              f"{str(row['local_epochs'] or '-'):>3s} "
              f"{(row['best_val_accuracy'] or 0):9.4f} {(row['test_accuracy'] or 0):8.4f} "
              f"{(row['wall_seconds_per_round'] or 0):8.2f} {(row['kib_per_node_per_round'] or 0):8.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
