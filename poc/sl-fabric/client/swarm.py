"""The swarm learning loop, with every round recorded on Fabric.

One round:

    1. every node loads the previous round's global model
    2. it trains on its own private shard for a few local epochs
    3. it hashes the resulting parameters and submits that hash to the ledger,
       signed by its own organization — the weights themselves stay off chain
    4. the round's leader, chosen by a rule anyone can recompute, averages the
       parameters it received and records the global model's hash
    5. every node checks the model it was handed against the hash on the ledger

The accuracy recorded on the ledger each round is measured on the **validation** split.
The test split is scored once, after the final round, and never influences anything: a
test set consulted every round would quietly become part of the training loop.

The chaincode enforces the rules: one update per node per round, quorum before a round
can close, only the leader may close it, and a closed round stays closed.

Weights move outside the ledger. In this PoC all five nodes live in one process, so
"moving" is an in-memory handoff; the ledger is what makes the round auditable, not what
carries the model. A real deployment would ship those bytes over its own channel, which
is why the byte counts are measured and reported.

The five updates are submitted concurrently, which is both realistic — five independent
organizations do not take turns — and what lets the ordering service batch them. Sending
them one at a time and waiting for each to commit produced one block per transaction;
sending them together puts the whole round's updates in a single block and cuts the
ledger time per round by roughly the number of nodes.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

import models
from data import SwarmData
from ledger import LedgerClient, LedgerError


@dataclass
class RoundResult:
    round_num: int
    leader: str
    participants: list[str]
    accuracy: float
    train_seconds: float
    aggregate_seconds: float
    ledger_seconds: float
    bytes_per_node: int
    verified: bool


@dataclass
class RunResult:
    model: str
    rounds: list[RoundResult] = field(default_factory=list)
    n_parameters: int = 0
    peak_rss_mb: float = 0.0
    total_seconds: float = 0.0
    # scored once, on the untouched test split, after the last round
    test_accuracy: float = 0.0
    # filled in by whoever brackets the run with resource snapshots; see cost.py
    cost: dict = field(default_factory=dict)

    @property
    def final_accuracy(self) -> float:
        """Validation accuracy after the last round."""
        return self.rounds[-1].accuracy if self.rounds else 0.0

    @property
    def best_accuracy(self) -> float:
        """Best validation accuracy over the run. Selecting on test would leak it."""
        return max((r.accuracy for r in self.rounds), default=0.0)

    @property
    def train_seconds(self) -> float:
        return sum(r.train_seconds for r in self.rounds)

    @property
    def ledger_seconds(self) -> float:
        return sum(r.ledger_seconds for r in self.rounds)

    @property
    def bytes_per_round(self) -> int:
        """What every node ships in one round, summed over the swarm."""
        return sum(r.bytes_per_node * len(r.participants) for r in self.rounds[:1])


def fedavg(params: list[np.ndarray], weights: list[int]) -> np.ndarray:
    """Average the parameter vectors, weighted by how much data produced each.

    A node with more samples pulls the global model harder. That is FedAvg, and it is
    also why n_samples is on the ledger: an auditor can recompute the weighting.
    """
    total = sum(weights)
    stacked = np.stack([p * (w / total) for p, w in zip(params, weights)])
    return stacked.sum(axis=0)


def accuracy(model: models.SwarmModel, X: np.ndarray, y: np.ndarray) -> float:
    return float((model.predict(X) == y).mean())


def run_swarm(model_name: str, data: SwarmData, ledger: LedgerClient, rounds: int,
              local_epochs: int = 1, round_offset: int = 0, seed: int = 0,
              verbose: bool = True,
              on_event: Callable[[dict], None] | None = None,
              should_stop: Callable[[], bool] | None = None) -> RunResult:
    """Train one model across the swarm for `rounds` rounds, recording each on Fabric.

    Each model type has its own channel, so rounds simply start at 1 and continue from
    whatever that chain already holds. round_offset exists only to resume a chain that is
    not empty; comparing models no longer means carving up a shared round-number space.

    on_event reports every step as it happens — each local epoch, each submission, the
    aggregation and the verification — so a caller can show what the swarm is doing inside
    a round rather than only between rounds. should_stop is checked between rounds, so a
    cancelled run always stops on a round boundary and never leaves a round half-submitted.
    """
    import psutil

    process = psutil.Process()
    started_total = time.perf_counter()

    # every node starts from the same parameters, which is what makes averaging them
    # meaningful in the first round; after that the global model plays that role
    node_models = {shard.msp_id: models.build(model_name, data.n_classes, seed=seed)
                   for shard in data.shards}
    global_params = models.build(model_name, data.n_classes, seed=seed).get_params()

    def emit(stage: str, **fields: object) -> None:
        if on_event is not None:
            on_event({"stage": stage, "model": model_name, **fields})

    result = RunResult(model=model_name, n_parameters=len(global_params))
    emit("model_start", parameters=len(global_params),
         bytes_per_node=models.params_size_bytes(global_params))
    if verbose:
        print(f"\n=== {model_name}: {len(global_params):,} parameters, "
              f"{models.params_size_bytes(global_params) / 1024:.1f} KiB per node per round ===")

    for offset in range(rounds):
        if should_stop is not None and should_stop():
            break
        round_num = round_offset + offset + 1
        leader = ledger.leader(round_num)
        emit("round_start", round=round_num, leader=leader, nodes=len(data.shards))

        submitted: dict[str, np.ndarray] = {}
        weights: dict[str, int] = {}
        train_seconds = 0.0
        # wall clock, not the sum of call durations: the five submissions overlap, and
        # adding their individual latencies would report five seconds of ledger time for
        # one second of waiting
        ledger_elapsed = 0.0

        # train locally first, one node at a time so the timings stay attributable
        trained: dict[str, tuple[np.ndarray, str, int]] = {}
        for shard in data.shards:
            model = node_models[shard.msp_id]
            model.set_params(global_params)

            # shards are stored raw; a node's data becomes float32 only while it trains,
            # which is what keeps the larger dataset inside memory
            batch = data.prepare(shard.X)
            started = time.perf_counter()
            model.train(
                batch, shard.y, epochs=local_epochs,
                on_epoch=lambda epoch, seconds, node=shard.msp_id: emit(
                    "epoch", round=round_num, node=node, epoch=epoch,
                    epochs=local_epochs, seconds=round(seconds, 3),
                    samples=shard.n_samples),
            )
            train_seconds += time.perf_counter() - started

            del batch
            params = model.get_params()
            trained[shard.msp_id] = (params, models.hash_params(params),
                                     models.params_size_bytes(params))

        # then submit together: the transactions reach the orderer inside one batch
        # window and land in a single block instead of one block each
        emit("submitting", round=round_num, nodes=len(trained))
        submit_started = time.perf_counter()

        def submit_one(item: tuple[str, tuple[np.ndarray, str, int]]) -> tuple[str, object]:
            msp_id, (_, weight_hash, size_bytes) = item
            samples = next(s.n_samples for s in data.shards if s.msp_id == msp_id)
            try:
                return msp_id, ledger.submit_update(
                    msp_id=msp_id, round_num=round_num, weight_hash=weight_hash,
                    size_bytes=size_bytes, n_samples=samples, model=model_name,
                )
            except LedgerError as exc:
                return msp_id, exc

        with ThreadPoolExecutor(max_workers=len(trained)) as pool:
            outcomes = list(pool.map(submit_one, trained.items()))
        ledger_elapsed += time.perf_counter() - submit_started

        for msp_id, outcome in outcomes:
            params, weight_hash, size_bytes = trained[msp_id]
            if isinstance(outcome, LedgerError):
                emit("rejected", round=round_num, node=msp_id, reason=str(outcome))
                print(f"  round {round_num}: {msp_id} rejected — {outcome}")
                continue
            emit("submit", round=round_num, node=msp_id,
                 weight_hash=weight_hash[:16], size_bytes=size_bytes,
                 latency_ms=outcome.get("latency_ms"))
            submitted[msp_id] = params
            weights[msp_id] = next(s.n_samples for s in data.shards if s.msp_id == msp_id)

        if not submitted:
            raise LedgerError(f"round {round_num}: no node managed to submit")

        # the leader aggregates off chain, then records only the hash of the result
        started = time.perf_counter()
        global_params = fedavg(list(submitted.values()), list(weights.values()))
        aggregate_seconds = time.perf_counter() - started

        evaluator = node_models[leader] if leader in node_models else next(iter(node_models.values()))
        evaluator.set_params(global_params)
        round_accuracy = accuracy(evaluator, data.X_val, data.y_val)

        aggregated_hash = models.hash_params(global_params)
        emit("aggregating", round=round_num, leader=leader,
             participants=len(submitted), accuracy=round(round_accuracy, 4))
        commit_started = time.perf_counter()
        commit = ledger.record_aggregation(
            msp_id=leader, round_num=round_num,
            aggregated_hash=aggregated_hash, accuracy=round_accuracy, model=model_name,
        )
        emit("committed", round=round_num, leader=leader,
             aggregated_hash=aggregated_hash[:16], latency_ms=commit.get("latency_ms"))

        # what a node receiving the global model would do before trusting it
        verified = ledger.verify_round(round_num, aggregated_hash)
        ledger_elapsed += time.perf_counter() - commit_started
        ledger_seconds = ledger_elapsed

        round_result = RoundResult(
            round_num=round_num,
            leader=leader,
            participants=sorted(submitted),
            accuracy=round_accuracy,
            train_seconds=train_seconds,
            aggregate_seconds=aggregate_seconds,
            ledger_seconds=ledger_seconds,
            bytes_per_node=models.params_size_bytes(global_params),
            verified=verified,
        )
        result.rounds.append(round_result)
        result.peak_rss_mb = max(result.peak_rss_mb, process.memory_info().rss / 1024 / 1024)
        emit("round", round=round_num, leader=leader,
             participants=sorted(submitted), accuracy=round(round_accuracy, 4),
             train_seconds=round(train_seconds, 2),
             ledger_seconds=round(ledger_seconds, 2), verified=verified)

        if verbose:
            print(f"  round {round_num:3d}  leader {leader:8s}  "
                  f"val {round_accuracy:.4f}  train {train_seconds:6.2f}s  "
                  f"ledger {ledger_seconds:5.2f}s  verified {verified}")

    # the one look at the test set, on the model the run actually ended with
    if result.rounds:
        final = node_models[next(iter(node_models))]
        final.set_params(global_params)
        result.test_accuracy = accuracy(final, data.X_test, data.y_test)

    result.total_seconds = time.perf_counter() - started_total
    emit("model_done", rounds=len(result.rounds),
         best_accuracy=round(result.best_accuracy, 4),
         test_accuracy=round(result.test_accuracy, 4),
         seconds=round(result.total_seconds, 1))
    return result
