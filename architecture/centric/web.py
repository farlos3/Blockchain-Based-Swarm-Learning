"""A page for testing the FL vs SL replication by hand: the results of results/full-500k,
and the three checks of verify.py run from buttons.

    .venv/Scripts/python.exe web.py          # http://127.0.0.1:8901

The checks need the Fabric network up (poc/sl-fabric/network: ./network.sh start). The
ledger's blocks themselves can be browsed on the gateway's own monitor, port 8899.

The audit and the rule check write their sections of verify.json, as `python verify.py`
does, so the report shows the latest run of either. A training test from the page is one
pair with settings chosen there, so it is shown but not saved.

Demo scope: it binds to localhost and has no authentication, and a training test writes
rounds to the ledger like any SL run.
"""

from __future__ import annotations

import json
import os
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

import verify  # first: it sets the cuBLAS workspace before torch is imported

import data
import federation
import models
import report

HERE = Path(__file__).resolve().parent
PAGE = HERE / "web" / "index.html"
ADDRESS = ("127.0.0.1", int(os.getenv("CENTRIC_WEB_PORT", "8901")))
LIMITS = {"rows": (5_000, 500_000), "rounds": (1, 20)}


class Invalid(Exception):
    """The request asks for something the page does not offer (400)."""


class Busy(Exception):
    """The page is already running something (409)."""


class Activity:
    """What the page is doing: one check or one training test at a time. Two SL runs on
    one chain would race for round numbers, and the rule check counts a chain's rounds
    before and after, so nothing else may write to the ledger while it runs."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.what: str | None = None

    def begin(self, what: str) -> None:
        """`what` is verify.py's name for the check: independent, audit or rules."""
        if not self.lock.acquire(blocking=False):
            raise Busy(f"the {self.what} check is running; try again when it finishes")
        self.what = what

    def end(self) -> None:
        self.what = None
        self.lock.release()


ACTIVITY = Activity()


class Job:
    """The training test, readable while it runs and after it ends."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.state: dict[str, Any] = {"running": False, "lines": [], "result": None, "error": None}

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {**self.state, "lines": list(self.state["lines"])}

    def start(self, settings: dict[str, Any]) -> None:
        ACTIVITY.begin("independent")
        with self.lock:
            self.state = {"running": True, "settings": settings, "started": time.time(),
                          "lines": [], "result": None, "error": None}
        threading.Thread(target=self._run, args=(settings,), daemon=True).start()

    def _log(self, line: str) -> None:
        with self.lock:
            self.state["lines"].append(line.strip())

    def _run(self, settings: dict[str, Any]) -> None:
        outcome: dict[str, Any] = {}
        try:
            outcome["result"] = verify.independent(**settings, log=self._log)
        except Exception as exc:                  # the page shows it; the server keeps going
            traceback.print_exc()
            outcome["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            with self.lock:
                self.state.update(running=False, finished=time.time(), **outcome)
            ACTIVITY.end()


JOB = Job()


def channels() -> dict[str, Any]:
    try:
        return {"ok": True, "channels": [c["channel"] for c in verify.LedgerClient(verify.GATEWAY).channels()]}
    except verify.LedgerError as exc:
        return {"ok": False, "error": str(exc), "channels": []}


def options() -> dict[str, Any]:
    """What a training test may be set to: the scenarios whose data is on this machine
    (combined, as data.build, from any two datasets), and the paper's models and algorithms."""
    have = data.available()
    return {
        "scenarios": [s for s in data.SCENARIOS
                      if (len(have) > 1 if s == "combined" else data.dataset_of(s) in have)],
        "models": list(models.ARCHITECTURES), "algorithms": list(federation.ALGORITHMS),
        "defaults": {"rows": verify.INDEPENDENT_ROWS, "rounds": verify.INDEPENDENT_ROUNDS},
        "limits": LIMITS,
    }


def results() -> list[dict[str, Any]]:
    """One row per (scenario, model, algorithm) of results/full-500k, FL and SL side by side."""
    rows = []
    for fl_path in (verify.EXPERIMENT / "runs").glob("*/fl-*.json"):
        sl_path = fl_path.with_name(fl_path.name.replace("fl-", "sl-", 1))
        if not sl_path.exists():
            continue
        fl = json.loads(fl_path.read_text(encoding="utf-8"))
        sl = json.loads(sl_path.read_text(encoding="utf-8"))
        paper = report.PAPER.get(fl["scenario"], {}).get((fl["algorithm"], fl["model"]))
        rows.append({
            "scenario": fl["scenario"], "model": fl["model"], "algorithm": fl["algorithm"],
            "clients": len(fl["clients"]), "device": fl["device"],
            "paper_f1": paper[3] / 100 if paper else None,
            "fl": {k: fl["test"][k] for k in ("accuracy", "f1", "auc")},
            "sl": {k: sl["test"][k] for k in ("accuracy", "f1", "auc")},
            "same_model": fl["final_hash"] == sl["final_hash"],
            "same_rounds": sum(a["global_hash"] == b["global_hash"]
                               for a, b in zip(fl["history"], sl["history"])),
            "rounds": len(fl["history"]),
            "ledger_s": report.per_round(sl, "coordination_seconds"),
            "fl_mb": fl["bytes_exchanged"] / len(fl["history"]) / 1e6,
            "sl_mb": sl["bytes_exchanged"] / len(sl["history"]) / 1e6,
        })
    order = {s: i for i, s in enumerate(data.SCENARIOS)}
    return sorted(rows, key=lambda r: (order[r["scenario"]], r["model"], federation.ALGORITHMS.index(r["algorithm"])))


def overview() -> dict[str, Any]:
    """Everything the page shows before any button is pressed."""
    import torch

    path = verify.evidence_path()
    return {
        "gateway": {**channels(), "url": verify.GATEWAY},
        "cuda": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "data": data.available(),
        "options": options(),
        "results": results(),
        "evidence": json.loads(path.read_text(encoding="utf-8")) if path.exists() else {},
        "busy": ACTIVITY.what,
    }


def validated(body: dict[str, Any]) -> dict[str, Any]:
    """The training test's settings, or Invalid naming what is wrong."""
    opts = options()
    settings: dict[str, Any] = {}
    for key, allowed in (("scenario", opts["scenarios"]), ("model", opts["models"]),
                         ("algorithm", opts["algorithms"])):
        if body.get(key) not in allowed:
            raise Invalid(f"{key} must be one of {', '.join(allowed)}")
        settings[key] = body[key]
    for key, (low, high) in LIMITS.items():
        value = body.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise Invalid(f"{key} must be a whole number")
        if not low <= value <= high:
            raise Invalid(f"{key} must be between {low:,} and {high:,}")
        settings[key] = value
    channel = verify.architectures.ledger.channel_for(data.dataset_of(settings["scenario"]), settings["model"])
    if channel not in channels()["channels"]:
        raise Invalid(f"the gateway serves no channel {channel}: is the network up?")
    return settings


def check(section: str, run: Callable[[], Any]) -> Any:
    """Run the audit or the rule check and save it into verify.json."""
    ACTIVITY.begin(section)
    try:
        result = run()
        verify.save(section, result)
        return result
    finally:
        ACTIVITY.end()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:  # quiet: the page polls every second
        pass

    def do_GET(self) -> None:
        self._route({"/": lambda: (200, PAGE.read_bytes()),
                     "/api/overview": lambda: (200, overview()),
                     "/api/job": lambda: (200, JOB.snapshot())})

    def do_POST(self) -> None:
        self._route({"/api/audit": lambda: (200, check("audit", verify.audit)),
                     "/api/rules": lambda: (200, check("rules", verify.all_rules)),
                     "/api/independent": self._independent})

    def _independent(self) -> tuple[int, Any]:
        JOB.start(validated(self._body()))
        return 202, JOB.snapshot()

    def _route(self, routes: dict[str, Callable[[], tuple[int, Any]]]) -> None:
        if self.path not in routes:
            self._send(404, {"error": f"no such route: {self.path}"})
            return
        try:
            self._send(*routes[self.path]())
        except Invalid as exc:
            self._send(400, {"error": str(exc)})
        except Busy as exc:
            self._send(409, {"error": str(exc)})
        except verify.LedgerError as exc:
            self._send(502, {"error": f"the Fabric gateway refused: {exc}"})
        except Exception as exc:
            traceback.print_exc()
            self._send(500, {"error": f"{type(exc).__name__}: {exc}"})

    def _body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length") or 0)
            parsed = json.loads(self.rfile.read(length)) if length else {}
        except ValueError:                        # a bad length or a body that is not JSON
            raise Invalid("the request body is not JSON") from None
        if not isinstance(parsed, dict):
            raise Invalid("the request body must be a JSON object")
        return parsed

    def _send(self, code: int, payload: Any) -> None:
        """The page itself is the only bytes payload; everything else is JSON."""
        page = isinstance(payload, bytes)
        body = payload if page else json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8" if page else "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    server = ThreadingHTTPServer(ADDRESS, Handler)
    print(f"FL vs SL test page on http://{ADDRESS[0]}:{ADDRESS[1]}  (gateway {verify.GATEWAY})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
