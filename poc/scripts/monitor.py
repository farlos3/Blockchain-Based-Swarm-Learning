"""Samples `docker stats` for all Fabric containers on a fixed interval and
writes one row per container per sample to a CSV. Run as a background
process for the duration of the PoC; stop with SIGTERM/Ctrl-C.
"""
import csv
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


def docker_stats_snapshot():
    out = subprocess.run(
        ["docker", "stats", "--no-stream", "--format",
         "{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}},{{.NetIO}},{{.BlockIO}}"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    rows = []
    for line in out.splitlines():
        if not line.strip():
            continue
        name, cpu, mem_usage, mem_perc, net_io, block_io = line.split(",")
        mem_used = mem_usage.split("/")[0].strip()
        rows.append((name, cpu.strip(), mem_used, mem_perc.strip(), net_io.strip(), block_io.strip()))
    return rows


def main(interval_seconds: float, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "container", "cpu_pct", "mem_used", "mem_pct", "net_io", "block_io"])
        f.flush()
        print(f"monitor.py: sampling docker stats every {interval_seconds}s -> {out_path}", file=sys.stderr)
        try:
            while True:
                ts = datetime.now(timezone.utc).isoformat()
                try:
                    for name, cpu, mem, mem_pct, net_io, block_io in docker_stats_snapshot():
                        writer.writerow([ts, name, cpu, mem, mem_pct, net_io, block_io])
                    f.flush()
                except subprocess.CalledProcessError as e:
                    print(f"monitor.py: docker stats failed: {e}", file=sys.stderr)
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    interval = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else RESULTS_DIR / "docker_stats.csv"
    main(interval, out)
