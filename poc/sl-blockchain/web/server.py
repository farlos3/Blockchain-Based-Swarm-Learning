"""Web simulator — the page drives the real SwarmLedger over HTTP

    python web/server.py            # opens on http://localhost:8000
    python web/server.py 9000       # different port

Built on http.server from the standard library, so there is no framework to install.
Every button calls the same code demo.py does: real ed25519 signatures, a real chain,
and the rejection rules come from swarm_ledger.py — nothing is re-simulated in JavaScript.

This is a local demo server: state lives in one process's memory, there is no user
authentication, and it must not be exposed to a public network.
"""

from __future__ import annotations

import json
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from blockchain import Block, Blockchain, ChainError  # noqa: E402
from consensus import NodeKey, elect_leader, sign_payload  # noqa: E402
from swarm_ledger import (  # noqa: E402
    LedgerError,
    SwarmLedger,
    audit_chain,
    unsigned_view,
)

HERE = Path(__file__).resolve().parent
INDEX = HERE / "index.html"
CHAIN_FILE = HERE.parent / "chain.json"

DEFAULT_NODES = ["A", "B", "C", "D", "E"]
DEFAULT_SAMPLES = {"A": 240, "B": 160, "C": 110, "D": 60, "E": 110}


class Simulation:
    """One simulation's state — wraps SwarmLedger with a lock against overlapping calls

    It also keeps each round's global parameters in memory, because the chain stores only
    a hash; the page has to ask this side to compare the real values when you press verify.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset(DEFAULT_NODES, DEFAULT_SAMPLES, seed="demo")

    # ---------- create / reset ----------

    def reset(self, nodes: list[str], samples: dict[str, int], seed: str | None) -> None:
        if not nodes:
            raise LedgerError("at least one node is required")
        self.nodes = list(nodes)
        self.samples = {n: int(samples.get(n, 100)) for n in self.nodes}
        self.seed = seed
        self.ledger = SwarmLedger.bootstrap(self.nodes, seed=seed)
        self.rng = np.random.default_rng(7)
        self.round_params: dict[int, list[tuple[np.ndarray, np.ndarray, int]]] = {}
        self.global_params: dict[int, tuple[np.ndarray, np.ndarray]] = {}
        self.log: list[dict[str, str]] = []
        self._note("ok", f"new swarm created with {len(self.nodes)} nodes "
                         f"(consensus = {self.ledger.chain.consensus.name})")

    def _note(self, level: str, text: str) -> None:
        self.log.append({"level": level, "text": text})
        del self.log[:-200]

    def fake_params(self) -> tuple[np.ndarray, np.ndarray]:
        """Stands in for parameters from real training (coef 1x10 + one intercept, same as SGDClassifier)"""
        return self.rng.normal(0, 1, size=(1, 10)), self.rng.normal(0, 1, size=(1,))

    # ---------- current round ----------

    @property
    def current_round(self) -> int:
        """The round in progress = the one after the last round that was sealed"""
        committed = self.ledger.committed_rounds()
        return (max(committed) + 1) if committed else 1

    def leader_of(self, round_num: int) -> str:
        return elect_leader(round_num, self.ledger.participants)

    # ---------- commands from the page ----------

    def submit(self, node_id: str) -> str:
        round_num = self.current_round
        coef, intercept = self.fake_params()
        tx = self.ledger.submit_update(
            round_num, node_id, coef, intercept, self.samples.get(node_id, 100)
        )
        self.round_params.setdefault(round_num, []).append(
            (coef, intercept, self.samples.get(node_id, 100))
        )
        return (f"round {round_num} | node {node_id} submitted an update "
                f"weight_hash={tx['weight_hash'][:12]}... sig={tx['signature'][:12]}...")

    def aggregate(self) -> str:
        """The leader runs FedAvg weighted by sample count (off-chain), then signs the block"""
        round_num = self.current_round
        leader = self.leader_of(round_num)
        parts = self.round_params.get(round_num, [])
        if not parts:
            raise LedgerError(f"round {round_num} has no updates to aggregate")

        total = sum(n for _, _, n in parts)
        g_coef = np.sum([c * n for c, _, n in parts], axis=0) / total
        g_intercept = np.sum([b * n for _, b, n in parts], axis=0) / total
        accuracy = min(0.99, 0.80 + 0.02 * round_num)  # pretend this came from a central test set

        block = self.ledger.record_aggregation(round_num, leader, g_coef, g_intercept, accuracy)
        self.global_params[round_num] = (g_coef, g_intercept)
        return (f"round {round_num} | leader {leader} sealed block #{block.index} "
                f"({len(block.transactions)} tx) seal={block.seal[:12]}...")

    def run_round(self) -> str:
        """Play a whole round: every node that has not submitted does, then the leader seals"""
        round_num = self.current_round
        already = {tx["node_id"] for tx in self.ledger._pending if tx["round"] == round_num}
        for node in self.nodes:
            if node not in already:
                self.submit(node)
        return self.aggregate()

    def verify(self, round_num: int, tampered: bool) -> str:
        """Compare the global parameters we hold against the hash recorded on-chain for that round"""
        if round_num not in self.global_params:
            raise LedgerError(f"no global parameters for round {round_num} in memory")
        coef, intercept = self.global_params[round_num]
        if tampered:
            coef = coef + 1e-9  # a 1e-9 difference is still caught, because the hash changes entirely
        ok = self.ledger.verify_round(round_num, coef, intercept)
        label = "modified (+1e-9)" if tampered else "genuine"
        return f"verify_round({round_num}) {label} -> {ok}"

    # ---------- rules the ledger rejects ----------

    def attack(self, kind: str) -> str:
        """Fire a rule-breaking transaction and report why the ledger rejected it

        Pending state is restored afterwards every time, so an experiment never leaks
        into a real round.
        """
        probe = self.current_round + 100  # an unused round, to fire rule-breaking transactions at
        outsider = NodeKey.generate("Z", seed="attacker")
        probe_leader = self.leader_of(probe)
        not_leader = next((n for n in self.nodes if n != probe_leader), probe_leader)
        snapshot = list(self.ledger._pending)

        def forged_update() -> None:
            forged = {
                "type": "model_update", "round": probe, "node_id": self.nodes[0],
                "weight_hash": "0" * 64, "size_bytes": 88, "n_samples": 99999,
                "timestamp": 0.0,
            }
            forged["signature"] = sign_payload(outsider, unsigned_view(forged))
            self.ledger.submit_signed_update(forged)

        def duplicate_update() -> None:
            node = self.nodes[0]
            self.ledger.submit_update(probe, node, *self.fake_params(), 10)
            self.ledger.submit_update(probe, node, *self.fake_params(), 10)

        def seal_out_of_turn() -> None:
            agg = {"type": "aggregation", "round": probe, "aggregator": not_leader,
                   "aggregated_hash": "0" * 64, "participant_count": 1, "total_samples": 1,
                   "accuracy": None, "timestamp": 0.0}
            agg["signature"] = sign_payload(self.ledger.keys[not_leader], unsigned_view(agg))
            self.ledger.chain.add_block([agg], sealer=self.ledger.keys[not_leader])

        def recommit_round() -> None:
            committed = self.ledger.committed_rounds()
            if not committed:
                raise LedgerError("no sealed round yet to try closing twice")
            done = committed[0]
            self.ledger.record_aggregation(done, self.leader_of(done), *self.fake_params())

        actions: dict[str, tuple[str, Callable[[], Any]]] = {
            "outsider": (
                "a node outside the authority set submits an update",
                lambda: self.ledger.submit_update(probe, "Z", *self.fake_params(), 10,
                                                  key=outsider),
            ),
            "forged": (f"a forged signature claiming to be node {self.nodes[0]}", forged_update),
            "duplicate": ("submitting twice in the same round", duplicate_update),
            "not_leader": (
                "a non-leader asks to aggregate",
                lambda: self.ledger.record_aggregation(probe, not_leader, *self.fake_params()),
            ),
            "out_of_turn": ("a real member seals out of turn", seal_out_of_turn),
            "recommit": ("closing an already closed round", recommit_round),
        }
        if kind not in actions:
            raise LedgerError(f"unknown test {kind!r}")

        label, action = actions[kind]
        try:
            action()
            return f"[UNEXPECTED] {label}: was not rejected"
        except Exception as exc:
            return f"[rejected] {label} -> {exc}"
        finally:
            self.ledger._pending = snapshot

    # ---------- rewriting history ----------

    def tamper(self, mode: str) -> str:
        """Edit a copy of the chain and let validate() catch it — the real one in memory is untouched"""
        if self.ledger.chain.height < 1:
            raise LedgerError("no block to edit yet, seal at least one round first")

        raw = json.loads(json.dumps(self.ledger.chain.to_dict()))
        if mode == "middle":
            victim = raw["blocks"][1]
            note = f"block #{victim['index']} (mid-chain, a later block points at its hash)"
        elif mode == "last":
            victim = raw["blocks"][-1]
            note = f"block #{victim['index']} (the last one, then recompute its hash to match)"
        else:
            raise LedgerError(f"unknown mode {mode!r}")

        target = next((tx for tx in victim["transactions"] if tx.get("type") == "model_update"),
                      None)
        if target is None:
            raise LedgerError("this block has no model_update to edit")
        # n_samples is the FedAvg weight: the larger it is, the harder it pulls the global model
        note += f" | node {target['node_id']} n_samples {target['n_samples']} -> 9999"
        target["n_samples"] = 9999

        if mode == "last":
            # a smarter attacker recomputes the hash, but still cannot forge the leader's signature
            victim["hash"] = Block.from_dict({**victim, "hash": None}).compute_hash()

        try:
            Blockchain.from_dict(raw).validate()
            return f"[UNEXPECTED] {note} - still validates after the edit"
        except ChainError as exc:
            return f"[caught] {note} -> {exc}"

    def save(self) -> str:
        self.ledger.chain.save(CHAIN_FILE)
        return f"saved to {CHAIN_FILE.name} | audit_chain() -> {audit_chain(CHAIN_FILE)}"

    # ---------- state for rendering the page ----------

    def state(self) -> dict[str, Any]:
        chain = self.ledger.chain
        round_num = self.current_round
        try:
            audit = self.ledger.audit()
            audit_error = None
        except Exception as exc:  # a broken chain must still render, so you can see where it broke
            audit, audit_error = None, str(exc)

        return {
            "consensus": chain.consensus.to_dict(),
            "participants": self.ledger.participants,
            "public_keys": self.ledger.authorities.to_dict(),
            "samples": self.samples,
            "current_round": round_num,
            "current_leader": self.leader_of(round_num),
            "leader_preview": {r: self.leader_of(r) for r in range(round_num, round_num + 5)},
            "pending": list(self.ledger._pending),
            "committed_rounds": self.ledger.committed_rounds(),
            "leader_counts": self.ledger.leader_counts(),
            "ledger_bytes": self.ledger.ledger_bytes(),
            "height": chain.height,
            "valid": chain.is_valid(),
            "audit": audit,
            "audit_error": audit_error,
            "verifiable_rounds": sorted(self.global_params),
            "blocks": [
                {
                    "index": b.index,
                    "timestamp": b.timestamp,
                    "prev_hash": b.prev_hash,
                    "hash": b.compute_hash(),
                    "sealer": b.sealer,
                    "seal": b.seal,
                    "tx_root": b.tx_root(),
                    "transactions": list(b.transactions),
                }
                for b in chain.blocks
            ],
            "log": self.log,
        }

    # ---------- the single entry point from HTTP ----------

    def command(self, action: str, body: dict[str, Any]) -> dict[str, Any]:
        """Run one command atomically, then return the whole latest state for a re-render"""
        with self._lock:
            handlers: dict[str, Callable[[], str]] = {
                "state": lambda: "",
                "submit": lambda: self.submit(body["node_id"]),
                "aggregate": self.aggregate,
                "run_round": self.run_round,
                "verify": lambda: self.verify(int(body["round"]), bool(body.get("tampered"))),
                "attack": lambda: self.attack(body["kind"]),
                "tamper": lambda: self.tamper(body["mode"]),
                "save": self.save,
            }
            if action == "reset":
                nodes = [str(n).strip() for n in body.get("nodes", DEFAULT_NODES) if str(n).strip()]
                samples = {n: int(body.get("samples", {}).get(n, DEFAULT_SAMPLES.get(n, 100)))
                           for n in nodes}
                self.reset(nodes, samples, body.get("seed") or None)
                return self.state()

            handler = handlers.get(action)
            if handler is None:
                raise LedgerError(f"unknown command {action!r}")

            try:
                message = handler()
                if message:
                    self._note("ok", message)
                    if message.startswith(("[rejected]", "[caught]")):
                        self.log[-1]["level"] = "reject"
                    elif message.startswith("[UNEXPECTED]"):
                        self.log[-1]["level"] = "error"
            except (LedgerError, ChainError, ValueError, KeyError) as exc:
                self._note("error", f"{type(exc).__name__}: {exc}")

            return self.state()


SIM = Simulation()


class Handler(BaseHTTPRequestHandler):
    server_version = "sl-blockchain-web"

    def log_message(self, fmt: str, *args: Any) -> None:
        pass  # keep http.server's log from burying the output the user is reading

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self._send(200, INDEX.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/chain.json":
            self._send_json(200, SIM.ledger.chain.to_dict())
        else:
            self._send_json(404, {"error": f"no such route: {self.path}"})

    def do_POST(self) -> None:
        if not self.path.startswith("/api/"):
            self._send_json(404, {"error": f"no such route: {self.path}"})
            return

        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError as exc:
            self._send_json(400, {"error": f"body is not JSON: {exc}"})
            return

        action = self.path[len("/api/"):]
        try:
            self._send_json(200, SIM.command(action, body))
        except LedgerError as exc:
            self._send_json(400, {"error": str(exc)})
        except Exception:
            traceback.print_exc()
            self._send_json(500, {"error": "internal server error (see the traceback in the terminal)"})


def main() -> None:
    # the Windows console defaults to cp1252 and dies on non-ASCII output, so force utf-8
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"sl-blockchain web simulator: http://127.0.0.1:{port}")
    print("Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
