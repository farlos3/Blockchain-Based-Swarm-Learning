"""Writing a run's results to disk.

Both entry points produce the same file: `run_experiment.py` from the command line and
`trainer.py` when the monitor page starts a run. Keeping the shape in one place means a
result written by a button press and one written by a script can be compared without
checking which produced it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from data import SwarmData
from swarm import RunResult

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def run_to_dict(result: RunResult) -> dict[str, Any]:
    return {
        "model": result.model,
        "n_parameters": result.n_parameters,
        "peak_rss_mb": round(result.peak_rss_mb, 1),
        "total_seconds": round(result.total_seconds, 2),
        "train_seconds": round(result.train_seconds, 2),
        "ledger_seconds": round(result.ledger_seconds, 2),
        # validation, scored every round
        "best_accuracy": result.best_accuracy,
        "final_accuracy": result.final_accuracy,
        # test, scored once at the end; this is the number to report
        "test_accuracy": result.test_accuracy,
        "cost": result.cost,
        "rounds": [
            {
                "round": r.round_num,
                "leader": r.leader,
                "participants": r.participants,
                "accuracy": r.accuracy,
                "train_seconds": round(r.train_seconds, 3),
                "aggregate_seconds": round(r.aggregate_seconds, 4),
                "ledger_seconds": round(r.ledger_seconds, 3),
                "bytes_per_node": r.bytes_per_node,
                "verified": r.verified,
            }
            for r in result.rounds
        ],
    }


def latest_per_model() -> list[dict[str, Any]]:
    """The most recent finished run of every model, read back from results/.

    The monitor needs this to compare models that were trained at different times: the
    trainer's in-memory summary only holds the current session, so after a restart — or
    when each model was run separately — the comparison table would be missing most of
    its rows. Files are the record; memory is just the live view of one run.

    A model that was run twice keeps only the newer file, by the timestamp in its name.
    """
    latest: dict[tuple[str | None, str], dict[str, Any]] = {}
    for path in sorted(RESULTS_DIR.glob("swarm-*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue  # a run still being written, or a file someone edited by hand
        for run in payload.get("results", []):
            rounds = run.get("rounds") or []
            if not rounds:
                continue
            latest[(payload.get("dataset"), run["model"])] = {
                "dataset": payload.get("dataset"),
                "model": run["model"],
                "n_parameters": run.get("n_parameters", 0),
                "rounds": len(rounds),
                "best_accuracy": run.get("best_accuracy"),
                "final_accuracy": run.get("final_accuracy"),
                # older files were written before validation and test were separated;
                # their accuracy came from the test split every round, so they have no
                # honest test number to show
                "test_accuracy": run.get("test_accuracy"),
                "train_seconds": run.get("train_seconds"),
                "ledger_seconds": run.get("ledger_seconds"),
                "peak_rss_mb": run.get("peak_rss_mb"),
                "kib_per_round": round(rounds[0]["bytes_per_node"] / 1024, 1),
                "cost": run.get("cost") or {},
                "source": path.name,
                "created": payload.get("created"),
                "local_epochs": payload.get("local_epochs"),
                "alpha": payload.get("alpha"),
            }
    return [latest[key] for key in sorted(latest, key=lambda k: (k[0] or "", k[1]))]


def archive() -> int:
    """Move finished result files into results/archive/ and report how many.

    Rebuilding the network leaves the old files behind, and the comparison table then
    shows numbers from a ledger that no longer exists. Moving rather than deleting keeps
    the record: a run that took an hour should not be thrown away because the chain it
    was written to was replaced.
    """
    target = RESULTS_DIR / "archive"
    target.mkdir(parents=True, exist_ok=True)
    moved = 0
    for path in sorted(RESULTS_DIR.glob("swarm-*.json")):
        path.rename(target / path.name)
        moved += 1
    return moved


def write(path: Path, settings: dict[str, Any], config: dict[str, Any],
          data: SwarmData, results: list[RunResult]) -> None:
    """Write what has finished so far.

    Called after every model rather than once at the end: a long comparison is tens of
    minutes of real ledger writes, and losing all of it because the last model hit a
    rejected transaction would be the expensive kind of failure.
    """
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({
        "created": path.stem.removeprefix("swarm-"),
        **settings,
        "members": [s.msp_id for s in data.shards],
        "quorum": config.get("quorum"),
        "shards": {s.msp_id: int(s.n_samples) for s in data.shards},
        "results": [run_to_dict(r) for r in results],
    }, indent=2) + "\n", encoding="utf-8")
