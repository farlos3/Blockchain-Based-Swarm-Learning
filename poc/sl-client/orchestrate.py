"""Drives the blockchain-based swarm-learning PoC: runs R rounds across 3
nodes (Org1, Org2, Org3), timing every blockchain interaction so we can
report how much latency/resource the consortium ledger adds on top of
plain local training.
"""
import csv
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sl_node  # noqa: E402

POC_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = POC_ROOT / "scripts"
RESULTS_DIR = POC_ROOT / "results"

NODES = [
    {"id": "node-org1", "org": "1", "index": 0},
    {"id": "node-org2", "org": "2", "index": 1},
    {"id": "node-org3", "org": "3", "index": 2},
]


def run_script(script_name: str, *args: str) -> tuple[str, float]:
    t0 = time.time()
    proc = subprocess.run(
        ["bash", str(SCRIPTS / script_name), *args],
        capture_output=True, text=True,
    )
    elapsed = time.time() - t0
    if proc.returncode != 0:
        raise RuntimeError(
            f"{script_name} {args} failed (rc={proc.returncode})\n"
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
        )
    return proc.stdout, elapsed


def ledger_size_bytes(container: str = "peer0.org1.example.com") -> int:
    proc = subprocess.run(
        ["docker", "exec", container, "du", "-sb", "/var/hyperledger/production/ledgersData"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return -1
    return int(proc.stdout.split()[0])


def run_rounds(num_rounds: int, local_epochs: int = 3, start_round: int = 1):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    metrics_path = RESULTS_DIR / "round_metrics.csv"
    fields = [
        "round", "node_id", "org", "train_seconds", "weight_size_bytes",
        "submit_latency_s", "query_latency_s", "agg_latency_s",
        "ledger_size_bytes_before", "ledger_size_bytes_after",
    ]

    with open(metrics_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for round_num in range(start_round, start_round + num_rounds):
            print(f"=== round {round_num}/{num_rounds} ===", file=sys.stderr)
            ledger_before = ledger_size_bytes()

            node_ids = [n["id"] for n in NODES]
            for node in NODES:
                weights_path, weight_hash, size_bytes, train_seconds = sl_node.local_train(
                    node["id"], node["index"], len(NODES), round_num, local_epochs
                )
                ts = datetime.now(timezone.utc).isoformat()

                _, submit_latency = run_script(
                    "cc-invoke.sh", node["org"], "SubmitUpdate",
                    str(round_num), node["id"], weight_hash, str(size_bytes), ts,
                )

                query_out, query_latency = run_script(
                    "cc-query.sh", node["org"], "GetRoundUpdates", str(round_num)
                )

                writer.writerow({
                    "round": round_num, "node_id": node["id"], "org": node["org"],
                    "train_seconds": f"{train_seconds:.4f}",
                    "weight_size_bytes": size_bytes,
                    "submit_latency_s": f"{submit_latency:.4f}",
                    "query_latency_s": f"{query_latency:.4f}",
                    "agg_latency_s": "", "ledger_size_bytes_before": "",
                    "ledger_size_bytes_after": "",
                })
                f.flush()
                print(f"  {node['id']}: train={train_seconds:.3f}s "
                      f"submit={submit_latency:.3f}s query={query_latency:.3f}s", file=sys.stderr)

            agg_path, agg_hash = sl_node.aggregate(round_num, node_ids)
            ts = datetime.now(timezone.utc).isoformat()
            aggregator_org = NODES[round_num % len(NODES)]["org"]  # round-robin aggregator
            _, agg_latency = run_script(
                "cc-invoke.sh", aggregator_org, "RecordAggregation",
                str(round_num), agg_hash, str(len(NODES)), ts,
            )
            ledger_after = ledger_size_bytes()

            writer.writerow({
                "round": round_num, "node_id": "__aggregation__", "org": aggregator_org,
                "train_seconds": "", "weight_size_bytes": agg_path.stat().st_size,
                "submit_latency_s": "", "query_latency_s": "",
                "agg_latency_s": f"{agg_latency:.4f}",
                "ledger_size_bytes_before": ledger_before,
                "ledger_size_bytes_after": ledger_after,
            })
            f.flush()
            print(f"  aggregation (org{aggregator_org}): {agg_latency:.3f}s, "
                  f"ledger {ledger_before} -> {ledger_after} bytes", file=sys.stderr)

    last_round = start_round + num_rounds - 1
    accuracy = sl_node.evaluate_global(last_round)
    print(f"final global-model accuracy on full digits set: {accuracy:.4f}", file=sys.stderr)
    return metrics_path, accuracy


if __name__ == "__main__":
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    epochs = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    start = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    path, acc = run_rounds(rounds, epochs, start_round=start)
    print(f"wrote {path}")
    print(f"accuracy={acc:.4f}")
