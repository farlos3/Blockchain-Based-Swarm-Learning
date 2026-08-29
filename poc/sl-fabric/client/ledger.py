"""Talking to the Fabric ledger through the Go gateway.

The gateway holds one signing identity per organization, so which endpoint this client
posts to decides which identity signs — a node cannot submit as another node by changing
a field in the body. That is the property the chaincode's GetMSPID check relies on, and
the reason this client never sends a node id.

Only the standard library is used: the gateway speaks plain JSON over HTTP on localhost.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

# Keep this in step with the gateway's default in gateway/main.go. SL_GATEWAY_URL moves
# both without editing either file.
DEFAULT_URL = os.getenv("SL_GATEWAY_URL", "http://127.0.0.1:8899")


def channel_for(dataset: str, model: str) -> str:
    """Each dataset-and-model pair trains on its own chain, named as network.sh names it.

    Channel names allow only [a-z0-9.-], so underscores become dashes.
    """
    return f"swarm-{dataset.replace('_', '-')}-{model.replace('_', '-')}"


class LedgerError(Exception):
    """The chaincode rejected the transaction, with the reason it gave."""


@dataclass
class LedgerTiming:
    """How much wall time the ledger cost, kept apart from training time.

    A swarm round is training plus consensus. Reporting them together would hide which
    one the blockchain is responsible for, so every call adds to one of these.
    """

    submit_ms: float = 0.0
    aggregate_ms: float = 0.0
    read_ms: float = 0.0
    calls: int = 0
    per_call_ms: list[float] = field(default_factory=list)

    @property
    def total_ms(self) -> float:
        return self.submit_ms + self.aggregate_ms + self.read_ms


class LedgerClient:
    """A thin REST client for the sl-ledger gateway."""

    def __init__(self, base_url: str = DEFAULT_URL, channel: str | None = None,
                 timeout: float = 180.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.channel = channel
        self.timeout = timeout
        self.timing = LedgerTiming()

    def for_channel(self, channel: str) -> "LedgerClient":
        """A view of the same gateway pointed at another chain, sharing nothing but the URL.

        Timing is per client on purpose: each model's run reports its own ledger cost.
        """
        return LedgerClient(self.base_url, channel=channel, timeout=self.timeout)

    # ---------- transport ----------

    def _call(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        import time

        data = None if body is None else json.dumps(body).encode("utf-8")
        if self.channel:
            path += ("&" if "?" in path else "?") + urllib.parse.urlencode({"channel": self.channel})
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=data, method=method,
            headers={"Content-Type": "application/json"},
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read() or b"null")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            try:
                message = json.loads(detail).get("error", detail)
            except json.JSONDecodeError:
                message = detail
            raise LedgerError(message) from None
        except urllib.error.URLError as exc:
            raise LedgerError(
                f"cannot reach the gateway at {self.base_url} ({exc.reason}). "
                "Start the stack with: cd poc/sl-fabric/network && ./network.sh up. "
                "A different port needs SL_GATEWAY_PORT there and SL_GATEWAY_URL here."
            ) from None
        finally:
            elapsed = (time.perf_counter() - started) * 1000
            self.timing.calls += 1
            self.timing.per_call_ms.append(elapsed)
            self._last_ms = elapsed
        return payload

    # ---------- reads ----------

    def channels(self) -> list[dict[str, str]]:
        """Which chains this network has, and the model each one belongs to."""
        result = self._call("GET", "/channels")
        self.timing.read_ms += self._last_ms
        return result or []

    def resources(self) -> dict[str, Any]:
        """What the peers and the orderer report about their own CPU, memory and blocks.

        Taken before and after a run, the difference is what that run cost the blockchain
        layer — which is the number needed to size a deployment, unlike a live gauge.
        """
        result = self._call("GET", "/resources")
        self.timing.read_ms += self._last_ms
        return result

    def health(self) -> dict[str, Any]:
        result = self._call("GET", "/health")
        self.timing.read_ms += self._last_ms
        return result

    def config(self) -> dict[str, Any]:
        result = self._call("GET", "/config")
        self.timing.read_ms += self._last_ms
        return result

    def leader(self, round_num: int) -> str:
        result = self._call("GET", f"/leader/{round_num}")
        self.timing.read_ms += self._last_ms
        return result["leader"]

    def committed_rounds(self) -> list[int]:
        result = self._call("GET", "/rounds")
        self.timing.read_ms += self._last_ms
        return result or []

    def round_updates(self, round_num: int) -> list[dict[str, Any]]:
        result = self._call("GET", f"/rounds/{round_num}/updates")
        self.timing.read_ms += self._last_ms
        return result or []

    def aggregation(self, round_num: int) -> dict[str, Any]:
        result = self._call("GET", f"/rounds/{round_num}/aggregation")
        self.timing.read_ms += self._last_ms
        return result

    # ---------- writes ----------

    def submit_update(self, msp_id: str, round_num: int, weight_hash: str,
                      size_bytes: int, n_samples: int, model: str) -> dict[str, Any]:
        """One node announces its local result. Signed by msp_id, because of the path."""
        result = self._call("POST", f"/nodes/{msp_id}/updates", {
            "round": round_num,
            "weight_hash": weight_hash,
            "size_bytes": size_bytes,
            "n_samples": n_samples,
            "model": model,
        })
        self.timing.submit_ms += self._last_ms
        return result

    def record_aggregation(self, msp_id: str, round_num: int, aggregated_hash: str,
                           accuracy: float, model: str) -> dict[str, Any]:
        """The round leader closes the round. Rejected unless msp_id really is the leader."""
        result = self._call("POST", f"/nodes/{msp_id}/aggregations", {
            "round": round_num,
            "aggregated_hash": aggregated_hash,
            "accuracy": accuracy,
            "model": model,
        })
        self.timing.aggregate_ms += self._last_ms
        return result

    def next_free_round(self, start: int = 0, look_ahead: int = 50) -> int:
        """The first round number on this chain that nothing has been written to yet.

        committed_rounds() only lists rounds that were *aggregated*. A run interrupted
        between submitting and aggregating leaves that round's updates in state where the
        committed list cannot see them, and starting there would be rejected as a
        duplicate by every node at once. So the search steps past any round that already
        holds updates.

        look_ahead bounds the probing: a chain with a long stretch of half-finished rounds
        is a problem to report, not to walk through one query at a time.
        """
        candidate = start + 1
        for _ in range(look_ahead):
            if not self.round_updates(candidate):
                return candidate - 1  # the caller adds 1 for the first round
            candidate += 1
        raise LedgerError(
            f"rounds {start + 1}..{candidate - 1} all hold updates already; "
            "clear the rounds before starting a new run"
        )

    # ---------- verification ----------

    def verify_round(self, round_num: int, aggregated_hash: str) -> bool:
        """Check the global model a node holds against what the ledger recorded."""
        return self.aggregation(round_num)["aggregated_hash"] == aggregated_hash
