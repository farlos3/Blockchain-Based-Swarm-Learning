"""CPU, GPU, RAM and disk of the machine actually doing the work.

The Fabric peers publish their own CPU and memory through their operations endpoint, but
nothing about the GPU or the disk: a peer has no reason to report either. Training does.
So this module samples the host the trainer runs on, and the gateway serves it next to
the peer metrics so the monitor can show both halves of the cost.

Everything here degrades rather than fails. No NVIDIA driver means `gpu` comes back empty,
not an error; a Docker CLI that is missing or slow means the ledger volume sizes are
simply absent that tick.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
from typing import Any

import psutil

# Docker's disk accounting walks the volumes, which takes about a second. The monitor
# polls far faster than that, and volume sizes barely move, so the answer is cached.
_VOLUME_TTL = 20.0
_volume_cache: tuple[float, list[dict[str, Any]]] = (0.0, [])
_volume_lock = threading.Lock()

# CPU load is computed from cpu_times() deltas kept here rather than from
# psutil.cpu_percent(), whose "since the last call" window is process-global state: any
# other caller — or a second reader of this endpoint — silently shortens the window and
# both readings collapse towards zero.
_cpu_lock = threading.Lock()
_last_cpu: tuple[float, float] | None = None  # (busy seconds, total seconds)


def cpu_percent() -> float:
    """Busy share of all cores since the previous call to this function."""
    global _last_cpu
    times = psutil.cpu_times()
    idle = times.idle + getattr(times, "iowait", 0.0)
    total = sum(getattr(times, field) for field in times._fields)
    busy = total - idle

    with _cpu_lock:
        previous = _last_cpu
        _last_cpu = (busy, total)

    if previous is None:
        return 0.0
    busy_delta = busy - previous[0]
    total_delta = total - previous[1]
    if total_delta <= 0:
        return 0.0
    return round(100.0 * busy_delta / total_delta, 1)


def gpu_metrics() -> list[dict[str, Any]]:
    """Per-GPU utilisation and memory, read from nvidia-smi.

    Returns an empty list when there is no NVIDIA driver. Note that a GPU showing up here
    does not mean training uses it: this project runs the CPU build of torch, so a busy GPU
    in the chart is something else on the machine, and every training second is CPU time.
    """
    if shutil.which("nvidia-smi") is None:
        return []
    try:
        out = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=4, check=True,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return []

    gpus = []
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5:
            continue
        try:
            gpus.append({
                "name": parts[0],
                "utilisation_percent": float(parts[1]),
                "memory_used_mb": float(parts[2]),
                "memory_total_mb": float(parts[3]),
                "temperature_c": float(parts[4]),
            })
        except ValueError:
            continue
    return gpus


def volume_metrics() -> list[dict[str, Any]]:
    """How much disk each Fabric ledger volume is using.

    This is the blockchain's real storage cost: one volume per peer plus the orderer,
    holding the blocks they have committed. Cached, because `docker system df -v` is slow.
    """
    global _volume_cache
    with _volume_lock:
        cached_at, cached = _volume_cache
        if time.time() - cached_at < _VOLUME_TTL:
            return cached

    if shutil.which("docker") is None:
        return []

    try:
        out = subprocess.run(
            ["docker", "system", "df", "-v", "--format", "{{json .Volumes}}"],
            # walking 100+ volumes takes several seconds on a busy Docker install
            capture_output=True, text=True, timeout=60, check=True,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return []

    volumes = []
    try:
        for entry in json.loads(out or "[]"):
            name = entry.get("Name", "")
            if not name.startswith("sl-fabric_"):
                continue
            volumes.append({
                "name": name.removeprefix("sl-fabric_"),
                "size": entry.get("Size", "0B"),
                "size_bytes": _parse_size(entry.get("Size", "0B")),
            })
    except (json.JSONDecodeError, AttributeError):
        return []

    volumes.sort(key=lambda v: v["name"])
    with _volume_lock:
        _volume_cache = (time.time(), volumes)
    return volumes


def invalidate_volume_cache() -> None:
    """Drop the cached volume sizes so the next sample re-measures the ledger on disk."""
    global _volume_cache, _sample_cache
    with _volume_lock:
        _volume_cache = (0.0, [])
    with _sample_lock:
        _sample_cache = (0.0, {})


def _parse_size(text: str) -> int:
    """Turn docker's "12.3MB" into bytes. Returns 0 for anything unparseable."""
    units = {"B": 1, "kB": 1000, "KB": 1000, "MB": 1000**2, "GB": 1000**3, "TB": 1000**4}
    text = (text or "").strip()
    for suffix, factor in sorted(units.items(), key=lambda kv: -len(kv[0])):
        if text.endswith(suffix):
            try:
                return int(float(text[: -len(suffix)]) * factor)
            except ValueError:
                return 0
    return 0


_SAMPLE_TTL = 1.0
_sample_cache: tuple[float, dict[str, Any]] = (0.0, {})
_sample_lock = threading.Lock()


def sample(disk_path: str = ".") -> dict[str, Any]:
    """One reading of everything the host can tell us, shared between readers for a second.

    psutil reports CPU as a percentage *since the previous call*, so two clients polling
    independently would each reset the other's window and both read close to zero. Handing
    every caller within a second the same sample keeps that window equal to the poll
    interval, and saves running nvidia-smi once per request.
    """
    with _sample_lock:
        cached_at, cached = _sample_cache
        if time.time() - cached_at < _SAMPLE_TTL and cached:
            return cached

    return _collect(disk_path)


def _collect(disk_path: str) -> dict[str, Any]:
    memory = psutil.virtual_memory()
    usage = psutil.disk_usage(disk_path)
    io = psutil.disk_io_counters()

    reading = {
        "sampled_at": time.time(),
        "cpu": {
            "percent": cpu_percent(),
            "cores": psutil.cpu_count(logical=True),
        },
        "ram": {
            "used_mb": round((memory.total - memory.available) / 1024 / 1024, 1),
            "total_mb": round(memory.total / 1024 / 1024, 1),
            "percent": memory.percent,
        },
        "disk": {
            "used_gb": round(usage.used / 1024**3, 1),
            "total_gb": round(usage.total / 1024**3, 1),
            "percent": usage.percent,
            # counters since boot; the monitor differentiates them into a rate
            "read_mb": round(io.read_bytes / 1024 / 1024, 1) if io else 0.0,
            "write_mb": round(io.write_bytes / 1024 / 1024, 1) if io else 0.0,
        },
        "gpu": gpu_metrics(),
        "ledger_volumes": volume_metrics(),
    }
    with _sample_lock:
        global _sample_cache
        _sample_cache = (time.time(), reading)
    return reading
