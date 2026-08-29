"""An HTTP front for the swarm loop, so training can be started from the monitor page.

    python trainer.py            # listens on 127.0.0.1:8900

The gateway proxies /train, /train/status and /train/stop here. Training has to live on
this side: the models are Python, the dataset is on this machine, and the gateway only
knows how to talk to Fabric.

One run at a time, on purpose. Two concurrent runs would race for round numbers, and the
ledger would reject the loser halfway through — a confusing failure to debug from a web
page. A second start while one is running is refused with 409.

Demo scope: it binds to localhost and has no authentication. Anything that can reach it
can start a job that writes to the ledger.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import traceback
import time
import pathlib
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import cost as cost_model
import hostmetrics
import models
import results as results_io
import data as data_module
from data import describe, load_swarm_data
from ledger import DEFAULT_URL, LedgerClient, LedgerError, channel_for
from swarm import RunResult, run_swarm

# Which models can be trained is decided by which channels the network created — see
# MODELS in network/network.sh. Keeping a second list here would let the two drift, and a
# model without a chain fails deep inside a run instead of at the request.
def known_pairs() -> list[dict[str, str]]:
    """The dataset-and-model pairs this network has a chain for."""
    try:
        return LedgerClient(DEFAULT_URL).channels()
    except LedgerError:
        return []


def known_models(dataset: str | None = None) -> list[str]:
    pairs = known_pairs()
    if not pairs:
        return sorted(models.BUILDERS)
    names = [c["model"] for c in pairs if dataset is None or c.get("dataset") == dataset]
    return sorted(set(names))


def known_datasets() -> list[str]:
    pairs = known_pairs()
    if not pairs:
        return sorted(data_module.DATASETS)
    return sorted({c["dataset"] for c in pairs if c.get("dataset")})
MAX_ROUNDS = 500


class Job:
    """The state of one training run, readable while it is still going.

    Every field the page needs is updated under the same lock the reader takes, so a
    status poll never sees a half-written round.
    """

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        self.running = False
        self.cancelled = False
        self.settings: dict[str, Any] = {}
        self.models: list[str] = []
        self.current_model: str | None = None
        self.model_index = 0
        self.round_index = 0
        self.rounds_per_model = 0
        self.history: list[dict[str, Any]] = []   # one entry per completed round
        self.events: list[dict[str, Any]] = []    # every step, newest last
        self.event_seq = 0
        self.stage: str | None = None
        self.channel: str | None = None
        # wall time of each completed round, used to estimate what is left
        self.round_seconds: list[float] = []
        self._round_started: float | None = None
        self.summary: list[dict[str, Any]] = []
        self.error: str | None = None
        self.started_at: str | None = None
        self.finished_at: str | None = None
        self.results_file: str | None = None
        self.shards: dict[str, int] = {}

    def eta_seconds(self) -> float | None:
        """Rough seconds remaining, from how long recent rounds actually took.

        The median of the last several rounds, not the mean: rounds vary by a factor of
        two when something else on the machine takes the CPU, and a mean over a slow patch
        predicts hours that never happen. Only recent rounds count, because the first round
        of a torch model pays a one-off warm-up. Rounds of models still queued are costed
        at the current model's pace, which is a guess — a CNN round takes several times a
        logistic one.
        """
        if not self.running or not self.round_seconds:
            return None
        recent = sorted(self.round_seconds[-9:])
        pace = recent[len(recent) // 2]
        done = self.model_index * self.rounds_per_model + self.round_index
        remaining = max(len(self.models) * self.rounds_per_model - done, 0)
        return round(pace * remaining, 1)

    def snapshot(self) -> dict[str, Any]:
        eta = self.eta_seconds()
        with self.lock:
            done = self.model_index * self.rounds_per_model + self.round_index
            total = max(len(self.models) * self.rounds_per_model, 1)
            return {
                "running": self.running,
                "cancelled": self.cancelled,
                "settings": dict(self.settings),
                "models": list(self.models),
                "current_model": self.current_model,
                "round_index": self.round_index,
                "rounds_per_model": self.rounds_per_model,
                "completed_rounds": done,
                "total_rounds": total,
                "progress": round(done / total, 4),
                # only the tail: a long run would otherwise grow the poll response
                # without bound, and the ledger already holds every round in full
                "history": self.history[-40:],
                "events": self.events[-60:],
                "event_seq": self.event_seq,
                "stage": self.stage,
                "channel": self.channel,
                "eta_seconds": eta,
                "seconds_per_round": (round(sorted(self.round_seconds[-9:])[
                                          len(self.round_seconds[-9:]) // 2], 1)
                                      if self.round_seconds else None),
                "summary": list(self.summary),
                "error": self.error,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "results_file": self.results_file,
                "shards": dict(self.shards),
            }


JOB = Job()

NETWORK_SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "network" / "network.sh"

# A rebuild destroys the ledger volumes and builds the channels again, which is the only
# way block height goes back to its starting point: committed blocks cannot be deleted,
# so the chain has to be replaced rather than emptied. It also restarts the gateway, so
# the monitor loses its connection for a couple of minutes.
REBUILD = {"running": False, "stage": None, "error": None, "finished_at": None}
_rebuild_lock = threading.Lock()


def rebuild_network() -> None:
    """Tear the network down and bring it back, on this thread."""
    steps = [("down", ["down"]), ("up", ["up"]), ("deploy", ["deploy"])]
    try:
        for name, args in steps:
            with _rebuild_lock:
                REBUILD["stage"] = name
            print(f"[rebuild] {name}", flush=True)
            result = subprocess.run(
                ["bash", str(NETWORK_SCRIPT), *args],
                cwd=str(NETWORK_SCRIPT.parent),
                capture_output=True, text=True, timeout=900,
            )
            if result.returncode != 0 and name != "down":
                # `down` fails harmlessly when there is nothing to remove
                tail = (result.stderr or result.stdout).strip().splitlines()[-3:]
                raise RuntimeError(f"network.sh {name} failed: " + " / ".join(tail))
    except Exception as exc:
        with _rebuild_lock:
            REBUILD["error"] = str(exc)
        print(f"[rebuild] failed: {exc}", flush=True)
    finally:
        with _rebuild_lock:
            REBUILD["running"] = False
            REBUILD["stage"] = None
            REBUILD["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        print("[rebuild] done", flush=True)


def validate(body: dict[str, Any]) -> dict[str, Any]:
    """Reject a bad request before any ledger write happens."""
    models = body.get("models") or ["logistic"]
    if not isinstance(models, list) or not models:
        raise ValueError("models must be a non-empty list")
    dataset = str(body.get("dataset") or (known_datasets() or ["blood"])[0])
    if dataset not in known_datasets():
        raise ValueError(f"no chains for dataset {dataset!r}; this network has {known_datasets()}")

    available = known_models(dataset)
    unknown = [m for m in models if m not in available]
    if unknown:
        raise ValueError(f"no chain for {unknown} on {dataset}; it has {available}")

    try:
        rounds = int(body.get("rounds", 30))
        local_epochs = int(body.get("local_epochs", 3))
        alpha = float(body.get("alpha", 0.5))
        seed = int(body.get("seed", 42))
    except (TypeError, ValueError):
        raise ValueError("rounds, local_epochs and seed must be integers, alpha a number")

    if not 1 <= rounds <= MAX_ROUNDS:
        raise ValueError(f"rounds must be between 1 and {MAX_ROUNDS}")
    if not 1 <= local_epochs <= 20:
        raise ValueError("local_epochs must be between 1 and 20")
    if alpha <= 0:
        raise ValueError("alpha must be positive")

    return {"dataset": dataset, "models": models, "rounds": rounds,
            "local_epochs": local_epochs, "alpha": alpha, "seed": seed}


def record_event(event: dict[str, Any]) -> None:
    """Store one step of the run for the monitor to pick up on its next poll.

    The events list is the fine-grained view (each local epoch, each submission, each
    commit); history keeps only completed rounds, which is what the summary needs.
    """
    with JOB.lock:
        JOB.event_seq += 1
        JOB.stage = event["stage"]
        JOB.events.append({"seq": JOB.event_seq, **event})

        if event["stage"] == "round_start":
            JOB._round_started = time.time()
        elif event["stage"] == "round" and JOB._round_started is not None:
            JOB.round_seconds.append(time.time() - JOB._round_started)
            JOB._round_started = None
        # the full list is unbounded on a long run and nothing reads the middle of it
        del JOB.events[:-400]

        if event["stage"] == "round":
            JOB.round_index += 1
            JOB.history.append({
                "model": event["model"],
                "round": event["round"],
                "leader": event["leader"],
                "participants": len(event["participants"]),
                "accuracy": event["accuracy"],
                "train_seconds": event["train_seconds"],
                "ledger_seconds": event["ledger_seconds"],
                "verified": event["verified"],
            })


def train(settings: dict[str, Any]) -> None:
    """Run the models one after another. Runs on its own thread; never raises out of it."""
    ledger = LedgerClient(DEFAULT_URL)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = results_io.RESULTS_DIR / f"swarm-{stamp}.json"
    finished: list[RunResult] = []

    try:
        config = ledger.config()
        data = load_swarm_data(config["members"], dataset=settings["dataset"],
                               alpha=settings["alpha"], seed=settings["seed"])
        with JOB.lock:
            JOB.shards = {s.msp_id: s.n_samples for s in data.shards}
        print(describe(data), flush=True)

        for index, model_name in enumerate(settings["models"]):
            # each model type trains on its own chain, so its rounds simply continue
            # from where that chain left off — no shared round-number space to carve up
            channel = channel_for(settings["dataset"], model_name)
            model_ledger = ledger.for_channel(channel)
            committed = model_ledger.committed_rounds()
            # past the aggregated rounds, and past any round left half-written by a run
            # that was interrupted between submitting and aggregating
            offset = model_ledger.next_free_round(max(committed) if committed else 0)

            with JOB.lock:
                JOB.current_model = model_name
                JOB.model_index = index
                JOB.round_index = 0
                JOB.channel = channel

            # snapshot the counters around the run: the difference is what this model
            # cost the blockchain, which is the number a future deployment is sized from
            before = cost_model.Snapshot.take(ledger.resources(), hostmetrics.sample(),
                                              channel=channel)
            started = time.time()

            run = run_swarm(
                model_name=model_name, data=data, ledger=model_ledger,
                rounds=settings["rounds"], local_epochs=settings["local_epochs"],
                round_offset=offset, seed=settings["seed"],
                verbose=True, on_event=record_event,
                should_stop=lambda: JOB.cancelled,
            )
            # the volume sizes are cached for 20s, so force a fresh look before measuring
            hostmetrics.invalidate_volume_cache()
            after = cost_model.Snapshot.take(ledger.resources(), hostmetrics.sample(),
                                             channel=channel)
            run.cost = cost_model.measure(
                before, after,
                rounds=len(run.rounds), nodes=len(data.shards),
                seconds=time.time() - started,
                off_chain_bytes_per_round=(run.rounds[0].bytes_per_node * len(data.shards)
                                           if run.rounds else 0),
            )

            finished.append(run)
            results_io.write(out, settings, config, data, finished)

            with JOB.lock:
                JOB.results_file = out.name
                JOB.summary.append({
                    # the filter that keeps a row only when its dataset-and-model pair has
                    # a chain needs both halves; without this the model being trained right
                    # now is the one row that disappears
                    "dataset": settings["dataset"],
                    "model": run.model,
                    "n_parameters": run.n_parameters,
                    "rounds": len(run.rounds),
                    "best_accuracy": round(run.best_accuracy, 4),
                    "final_accuracy": round(run.final_accuracy, 4),
                    "test_accuracy": round(run.test_accuracy, 4),
                    "train_seconds": round(run.train_seconds, 1),
                    "ledger_seconds": round(run.ledger_seconds, 1),
                    "peak_rss_mb": round(run.peak_rss_mb, 1),
                    "kib_per_round": round(run.rounds[0].bytes_per_node / 1024, 1) if run.rounds else 0,
                    "cost": run.cost,
                })

            if JOB.cancelled:
                break

    except (LedgerError, ValueError, FileNotFoundError) as exc:
        with JOB.lock:
            JOB.error = str(exc)
    except Exception:  # a bug here must still leave the page a readable status
        traceback.print_exc()
        with JOB.lock:
            JOB.error = "unexpected error in the trainer, see its terminal"
    finally:
        with JOB.lock:
            JOB.running = False
            JOB.current_model = None
            JOB.finished_at = datetime.now(timezone.utc).isoformat(timespec="seconds")


class Handler(BaseHTTPRequestHandler):
    server_version = "sl-trainer"

    def log_message(self, fmt: str, *args: Any) -> None:
        pass  # the training output is what matters in this terminal

    def _send(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path in ("/status", "/train/status"):
            self._send(200, JOB.snapshot())
        elif self.path in ("/runs", "/train/runs"):
            # the live session first, so a model just finished shows its fresh numbers
            # rather than the file from a previous run of the same model
            snapshot = JOB.snapshot()
            live = {(m.get("dataset"), m["model"]): m for m in snapshot["summary"]}
            saved = {(r.get("dataset"), r["model"]): r for r in results_io.latest_per_model()}
            merged = {**saved, **live}

            # a results file outlives the network it was produced on. Rows for models this
            # network has no chain for are dropped outright, and the rest carry the file
            # they came from so a stale one can be recognised rather than trusted.
            # a result belongs to a dataset as much as to a model, so rows are keyed by
            # both; a run whose pair has no chain here is from another network
            available = {(c["dataset"], c["model"]) for c in known_pairs()}
            rows = [m for m in merged.values()
                    if not available or (m.get("dataset"), m["model"]) in available]
            self._send(200, sorted(rows, key=lambda m: (m.get("dataset") or "", m["model"])))
        elif self.path in ("/network/status", "/train/network"):
            with _rebuild_lock:
                self._send(200, dict(REBUILD))
        elif self.path in ("/metrics", "/train/metrics"):
            self._send(200, hostmetrics.sample())
        elif self.path == "/health":
            self._send(200, {"status": "ok", "datasets": known_datasets(),
                             "models": known_models(), "max_rounds": MAX_ROUNDS})
        else:
            self._send(404, {"error": f"no such route: {self.path}"})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError as exc:
            self._send(400, {"error": f"body is not JSON: {exc}"})
            return

        if self.path in ("/runs/archive", "/train/runs/archive"):
            if not body.get("confirm"):
                self._send(400, {"error": 'send {"confirm": true} to archive past results'})
                return
            moved = results_io.archive()
            self._send(200, {"archived": moved})
            return

        if self.path in ("/network/rebuild", "/train/network"):
            if not body.get("confirm"):
                self._send(400, {"error": 'send {"confirm": true} to rebuild the network'})
                return
            with JOB.lock:
                if JOB.running:
                    self._send(409, {"error": "a training run is in progress"})
                    return
            with _rebuild_lock:
                if REBUILD["running"]:
                    self._send(409, {"error": f"already rebuilding ({REBUILD['stage']})"})
                    return
                REBUILD.update(running=True, stage="starting", error=None, finished_at=None)
            threading.Thread(target=rebuild_network, daemon=True).start()
            self._send(202, {"rebuilding": True,
                             "note": "the gateway restarts during this; the monitor will "
                                     "reconnect on its own in a couple of minutes"})
            return

        if self.path in ("/stop", "/train/stop"):
            with JOB.lock:
                if not JOB.running:
                    self._send(409, {"error": "nothing is running"})
                    return
                JOB.cancelled = True
            self._send(200, {"stopping": True})
            return

        if self.path not in ("/train", "/"):
            self._send(404, {"error": f"no such route: {self.path}"})
            return

        try:
            settings = validate(body)
        except ValueError as exc:
            self._send(400, {"error": str(exc)})
            return

        with JOB.lock:
            if JOB.running:
                self._send(409, {"error": f"{JOB.current_model} is still running, "
                                          "stop it first or wait for it to finish"})
                return
            JOB.reset()
            JOB.running = True
            JOB.settings = settings
            JOB.models = settings["models"]
            JOB.rounds_per_model = settings["rounds"]
            JOB.started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

        threading.Thread(target=train, args=(settings,), daemon=True).start()
        self._send(202, JOB.snapshot())


def main() -> None:
    # the Windows console defaults to cp1252 and dies on non-ASCII output
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8900
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"sl-fabric trainer: http://127.0.0.1:{port}  (ledger via {DEFAULT_URL})")
    print("Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
