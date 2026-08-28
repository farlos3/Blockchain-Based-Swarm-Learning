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
