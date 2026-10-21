"""The two architectures being compared: a federated server, and a swarm on Fabric.

FL (Bilal et al., Fig. 1)                 SL (Warnat-Herresthal et al. 2021, on Fabric)
--------------------------------------    ------------------------------------------------
a central server owns the global model    no server: every round one node is the leader,
                                          elected by the chaincode's sha256 rule
clients send weights to the server        nodes commit sha256(weights) to the ledger, signed
                                          by their own organization, then hand the weights
                                          to the leader peer to peer
the server merges, nobody can check it    the leader merges only updates whose bytes match
                                          the ledger, weighting by the n_samples on the
                                          ledger, and records the merged model's hash
clients take whatever the server sends    every node checks the merged model against the
                                          ledger before adopting it
star traffic: 2 * K * P per round         peer traffic: 2 * (K - 1) * P (the leader keeps
                                          its own update), plus small ledger transactions

The merge itself is the same function (federation.aggregate) in both, so with the same
seeds the two produce the same global model bit for bit; what SL adds is who may merge,
the audit trail, and the cost of agreeing on both.
"""

from __future__ import annotations

import importlib.util
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

import numpy as np

import models
from federation import Update

REPO = Path(__file__).resolve().parents[2]

# The Fabric client of the image-classification swarm, reused unchanged. Loaded by path
# under its own name: that directory also has a data.py and a models.py, which must not
# shadow the ones here.
_spec = importlib.util.spec_from_file_location(
    "sl_fabric_ledger", REPO / "poc" / "sl-fabric" / "client" / "ledger.py")
ledger = sys.modules[_spec.name] = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ledger)


def node_name(index: int) -> str:
    """Client k of a scenario is organization k+1 of the network (configtx SwarmN profiles)."""
    return f"Org{index + 1}MSP"


class CentralServer:
    """Federated learning as in the paper: one aggregator every client trusts."""

    name = "fl"

    def open(self, tag: str, n_clients: int) -> dict:
        self.n_clients = n_clients
        return {"topology": "star", "aggregator": "server"}

    def merge(self, round_num: int, start: np.ndarray, updates: list[Update],
              combine: Callable[[np.ndarray, list[Update]], np.ndarray]) -> tuple[np.ndarray, dict]:
        started = time.perf_counter()
        merged = combine(start, updates)
        return merged, {
            "aggregate_seconds": time.perf_counter() - started,
            "coordination_seconds": 0.0,
            # Table 9's formula: every client uploads P floats and downloads P floats
            "bytes": 2 * len(updates) * models.size_bytes(start),
            "aggregator": "server",
        }

    def publish(self, round_num: int, params: np.ndarray, val_accuracy: float) -> dict:
        return {}

    def close(self) -> dict:
        return {}


class FabricSwarm:
    """Swarm learning: the round's leader merges, and Fabric decides who that is and keeps
    every node honest about what it sent and what it received."""

    name = "sl"

    def __init__(self, dataset: str, model: str, gateway: str = ledger.DEFAULT_URL) -> None:
        self.channel = ledger.channel_for(dataset, model)
        self.client = ledger.LedgerClient(gateway, channel=self.channel)

    def open(self, tag: str, n_clients: int) -> dict:
        self.tag = tag
        self.nodes = [node_name(k) for k in range(n_clients)]
        config = self.client.config()
        members = config["members"]
        # every client must be a member, and enough of them to close a round. A member
        # may hold no data (the combined swarm's TII org, until TII-SSRC-23 is downloaded):
        # it still takes its turn as leader, merging the others' updates
        outsiders = [n for n in self.nodes if n not in members]
        if outsiders or n_clients < config["quorum"]:
            raise ledger.LedgerError(
                f"{self.channel} has members {members} and quorum {config['quorum']}, which "
                f"does not fit {n_clients} clients ({self.nodes[0]}..{self.nodes[-1]}). Was "
                "the network brought up with the current poc/sl-fabric/network/network.sh?")
        # a run starts after anything already on this chain: rounds are never reused
        committed = self.client.committed_rounds()
        self.offset = self.client.next_free_round(max(committed, default=0))
        self.client.timing = ledger.LedgerTiming()
        self.rejected = 0
        self.leaders: dict[str, int] = {}
        return {"topology": "peer-to-peer", "channel": self.channel,
                "first_ledger_round": self.offset + 1, "members": members}

    def merge(self, round_num: int, start: np.ndarray, updates: list[Update],
              combine: Callable[[np.ndarray, list[Update]], np.ndarray]) -> tuple[np.ndarray, dict]:
        chain_round = self.offset + round_num
        ledger_started = time.perf_counter()
        self.leader = self.client.leader(chain_round)
        self.leaders[self.leader] = self.leaders.get(self.leader, 0) + 1

        # 1. every node commits to its weights, concurrently, as independent orgs would;
        #    the orderer then batches the round into one block
        hashes = {u.client: models.hash_params(u.params) for u in updates}

        def submit(u: Update) -> None:
            self.client.submit_update(self.nodes[u.client], chain_round, hashes[u.client],
                                      models.size_bytes(u.params), u.n_samples, self.tag)

        with ThreadPoolExecutor(max_workers=len(updates)) as pool:
            list(pool.map(submit, updates))      # a rejection raises: the round cannot close

        # 2. the leader takes in the peers' weights and accepts only bytes that match what
        #    each node committed to, with the sample count the ledger holds for it
        records = {r["node_id"]: r for r in self._once_visible(
            lambda: self.client.round_updates(chain_round),
            lambda rows: len(rows) >= len(updates), f"round {chain_round}'s updates")}
        verified = []
        for u in updates:
            record = records.get(self.nodes[u.client])
            if record is None or record["weight_hash"] != models.hash_params(u.params):
                self.rejected += 1
                continue
            verified.append(Update(u.client, u.params, int(record["n_samples"]), u.steps, u.seconds))
        ledger_seconds = time.perf_counter() - ledger_started

        started = time.perf_counter()
        merged = combine(start, verified)
        aggregate_seconds = time.perf_counter() - started
        self.merged_hash = models.hash_params(merged)
        self._round = chain_round
        self._ledger_seconds = ledger_seconds
        # a leader that trained keeps its own update; one without data receives them all
        shipped = len(updates) - (1 if self.leader in self.nodes else 0)
        return merged, {
            "aggregate_seconds": aggregate_seconds,
            "bytes": 2 * shipped * models.size_bytes(start),
            "aggregator": self.leader,
            "chain_round": chain_round,
            "accepted": len(verified),
        }

    def publish(self, round_num: int, params: np.ndarray, val_accuracy: float) -> dict:
        # 3. the leader closes the round with the merged model's hash; 4. every node checks
        #    the model it is handed against that hash before training on it
        started = time.perf_counter()
        self.client.record_aggregation(self.leader, self._round, self.merged_hash,
                                       val_accuracy, self.tag)
        recorded = self._once_visible(lambda: self.client.aggregation(self._round),
                                      lambda _: True, f"round {self._round}'s aggregation")
        verified = recorded["aggregated_hash"] == models.hash_params(params)
        return {"coordination_seconds": self._ledger_seconds + time.perf_counter() - started,
                "verified": verified}

    @staticmethod
    def _once_visible(read, ready, what: str, timeout: float = 30.0):
        """Read until a just-committed write shows up on the peer being read.

        A submit returns once the submitting organization's peer has committed the block;
        the peer a read is evaluated on can receive that block a moment later. A real node
        reads its own peer and waits for the block in the same way. Nothing is retried on
        the write side, so this cannot record anything twice.
        """
        deadline = time.perf_counter() + timeout
        while True:
            try:
                value = read()
                if ready(value):
                    return value
            except ledger.LedgerError as exc:
                if "has no aggregation" not in str(exc):
                    raise
            if time.perf_counter() > deadline:
                raise ledger.LedgerError(f"{what} did not reach the reading peer within {timeout:.0f}s")
            time.sleep(0.2)

    def close(self) -> dict:
        timing = self.client.timing
        return {
            "ledger_calls": timing.calls,
            "ledger_ms": {"submit": timing.submit_ms, "aggregate": timing.aggregate_ms,
                          "read": timing.read_ms},
            "rejected_updates": self.rejected,
            "leader_rounds": self.leaders,
            "last_ledger_round": self._round,
        }
