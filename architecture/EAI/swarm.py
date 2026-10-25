"""Swarm learning as the paper runs it (Algorithm 1, HPE's SwarmCallback), its rounds kept on
Hyperledger Fabric, and the centralised baseline it is compared with.

Algorithm 1 / SwarmCallback                 here
------------------------------------------  ---------------------------------------------------
on_train_begin: every node's own initial    round 0 merges the nodes' independently initialised
model is merged by an elected leader        networks; every node starts from that merge
local training, F batches between syncs     each node runs syncFrequency = 1024 batches of 128
(syncFrequency, counted across epochs)      (Table 12), its epochs reshuffled as Keras does
leader elected each round                   Fabric's sl-ledger chaincode elects it:
                                            sha256("round-N:members") mod N, recomputable by all
leader collects and merges with f           nodes commit sha256(weights) on the ledger, signed by
                                            their own organisation; the leader merges only weights
                                            whose bytes match, then records the merge's hash
merged model returned to all nodes          every node checks it against the ledger before use
node reaches 10 epochs before the others    HPE's default checkinModelOnTrainEnd = "snapshot": it
                                            keeps contributing the weights it stopped with and
                                            takes no further merges; the swarm runs until the
                                            node with the most batches finishes
mean / coordmedian / geomedian (Table 2)    `merge`, every node weighted 1 (nodeWeightage default)

So the number of rounds follows from the data: 1 + ceil(max_k 10 * ceil(n_k / 128) / 1024),
which gives the 27 rounds the paper reports for Scenario 2 and 18 for Scenario 3.

Two of those defaults can be changed to look for what limits the swarm (`swarm(...)`):
weighting="samples" weighs each node by its training rows, as the ledger records them
(nodeWeightage proportional to data); on_train_end="inactive" lets a node that has finished
stop contributing (HPE's "inactive"). Fabric closes a round only with a majority of the
swarm's organisations, so once fewer than that are still training there is no merge: the
remaining nodes train on their own and the last node to finish holds the final model.
"""

from __future__ import annotations

import importlib.util
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import torch
from torch import nn

import models
from data import Host, Scenario, Split

REPO = Path(__file__).resolve().parents[2]

# The project's Fabric client, unchanged. Loaded by path under its own name: its directory
# has a data.py and a models.py too, which must not shadow the ones here.
_spec = importlib.util.spec_from_file_location("sl_fabric_ledger", REPO / "poc" / "sl-fabric" / "client" / "ledger.py")
ledger = sys.modules[_spec.name] = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ledger)

MERGES = ("mean", "coordmedian", "geomedian")


@dataclass(frozen=True)
class Hyper:
    """Table 12."""
    learning_rate: float = 1e-3
    batch: int = 128
    epochs: int = 10
    sync_frequency: int = 1024      # batches between two swarm syncs


# ================================================================ merging (Table 2)

def merge(method: str, params: list[np.ndarray], weights: list[float]) -> np.ndarray:
    """The leader's merge of the nodes' weight vectors, in float64, in node order.

    mean         weighted average (FedAvg with the nodes' weightage)
    coordmedian  the (weighted) median of every coordinate on its own
    geomedian    the (weighted) geometric median of the whole vectors, by Weiszfeld's algorithm

    The same inputs give the same bits whichever node is leader.
    """
    stack = np.stack([p.astype(np.float64) for p in params])
    w = np.asarray(weights, dtype=np.float64)
    if method == "mean":
        merged = (w[:, None] * stack).sum(axis=0) / w.sum()
    elif method == "coordmedian":
        merged = np.median(stack, axis=0) if (w == w[0]).all() else weighted_median(stack, w)
    elif method == "geomedian":
        merged = weiszfeld(stack, w)
    else:
        raise ValueError(f"unknown merge method {method!r}")
    return merged.astype(np.float32)


def weighted_median(stack: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Per coordinate, the value where the cumulative weight reaches half; the mean of the two
    values around it when it lands exactly on half (so equal weights give np.median)."""
    order = np.argsort(stack, axis=0, kind="stable")
    values = np.take_along_axis(stack, order, axis=0)
    cumulative = np.cumsum(weights[order], axis=0)
    half = weights.sum() / 2
    columns = np.arange(stack.shape[1])
    lower = np.argmax(cumulative >= half, axis=0)
    upper = np.argmax(cumulative > half, axis=0)
    return (values[lower, columns] + values[upper, columns]) / 2


def weiszfeld(points: np.ndarray, weights: np.ndarray, tol: float = 1e-7, max_iter: int = 1000) -> np.ndarray:
    """The point minimising sum_k w_k * ||z - x_k||: start at the weighted mean, then move to
    the inverse-distance-weighted mean until the step is below tol (relative)."""
    z = (weights[:, None] * points).sum(axis=0) / weights.sum()
    for _ in range(max_iter):
        distance = np.linalg.norm(points - z, axis=1)
        if (distance < 1e-12).any():           # z sits on a node's vector: that is the median
            return points[int(np.argmin(distance))]
        inverse = weights / distance
        nxt = (inverse[:, None] * points).sum(axis=0) / inverse.sum()
        if np.linalg.norm(nxt - z) <= tol * max(np.linalg.norm(z), 1.0):
            return nxt
        z = nxt
    return z


# ================================================================ evaluation

def evaluate(net: nn.Module, split: Split, device: str, chunk: int = 16384) -> dict:
    """Section 4.2: accuracy, precision, recall and F1 with attack as the positive class,
    the confusion matrix, binary cross-entropy, and the detection rate per traffic type."""
    net.eval()
    with torch.no_grad():
        logits = torch.cat([
            net(torch.from_numpy(split.packet[i:i + chunk]).to(device),
                torch.from_numpy(split.flow[i:i + chunk]).to(device)).float().cpu()
            for i in range(0, len(split.y), chunk)])
    y = torch.from_numpy(split.y)
    loss = float(nn.functional.binary_cross_entropy_with_logits(logits, y))
    pred = (logits > 0).numpy()
    truth = split.y > 0.5
    tp, fp = int((pred & truth).sum()), int((pred & ~truth).sum())
    fn, tn = int((~pred & truth).sum()), int((~pred & ~truth).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "loss": loss,
        "accuracy": (tp + tn) / len(truth),
        "precision": precision, "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "confusion": [[tn, fp], [fn, tp]],      # rows: benign, attack; columns: predicted
        "by_type": {t: float((pred[split.types == t] == truth[split.types == t]).mean())
                    for t in np.unique(split.types)},
        "n": int(len(truth)),
    }


def mean_over_hosts(results: list[dict]) -> dict:
    """The paper's 'average validation accuracy / loss': the nodes' own figures, averaged."""
    return {key: float(np.mean([r[key] for r in results])) for key in ("accuracy", "loss", "f1")}


# ================================================================ a swarm node

def _seed(*parts: int) -> int:
    return int(np.random.SeedSequence(list(parts)).generate_state(1)[0])


class Node:
    """One edge host: its own data, network and Adam, training in syncFrequency slices.

    Its optimizer lives for the whole run (SwarmCallback swaps the weights inside Keras's
    fit; the optimizer's moments stay), and batches are counted across epochs.

    On a GPU a full batch's step (gather, forward, backward, Adam) is captured once as a CUDA
    graph and replayed: these networks are so small that launching their kernels one by one
    from Python costs far more than running them. The weights, Adam's state and the batch
    indices stay at fixed addresses, which is all a replay needs: merges copy into the
    weights in place. An epoch's last, short batch runs eagerly through the same optimizer.
    """

    def __init__(self, index: int, host: Host, model_name: str, n_features: int,
                 hyper: Hyper, seed: int, device: str) -> None:
        self.index, self.host, self.hyper, self.device = index, host, hyper, device
        self.net = models.build(model_name, n_features, _seed(seed, index)).to(device)
        cuda = torch.device(device).type == "cuda"
        self.optimizer = torch.optim.Adam(self.net.parameters(), lr=hyper.learning_rate, eps=1e-7,
                                          capturable=cuda)
        self.packet = torch.from_numpy(host.train.packet).to(device)
        self.flow = torch.from_numpy(host.train.flow).to(device)
        self.y = torch.from_numpy(host.train.y).to(device)
        self.per_epoch = math.ceil(len(self.y) / hyper.batch)
        self.total = hyper.epochs * self.per_epoch
        self.done = 0
        self.order_rng = torch.Generator().manual_seed(_seed(seed, index, 1))
        self.snapshot: np.ndarray | None = None      # weights at the stopping criterion
        self.graph: torch.cuda.CUDAGraph | None | bool = None if cuda else False
        self.loss_sum = torch.zeros((), device=device)
        self.correct = torch.zeros((), device=device)

    @property
    def finished(self) -> bool:
        return self.done >= self.total

    def _step(self, idx: torch.Tensor) -> None:
        """One optimizer step on the rows `idx`, adding to the running loss and hit count."""
        logits = self.net(self.packet[idx], self.flow[idx])
        y = self.y[idx]
        loss = nn.functional.binary_cross_entropy_with_logits(logits, y)
        self.loss_sum += loss.detach() * len(idx)
        self.correct += ((logits.detach() > 0).float() == y).sum()
        loss.backward()
        self.optimizer.step()

    def _capture(self) -> None:
        """Record one full-batch step. Capture needs a few eager steps first, on a side
        stream; they move the weights and fill Adam's state, so both are put back after."""
        self.idx = torch.zeros(self.hyper.batch, dtype=torch.long, device=self.device)
        saved = [p.detach().clone() for p in self.net.parameters()]
        side = torch.cuda.Stream()
        side.wait_stream(torch.cuda.current_stream())
        with torch.cuda.stream(side):
            for _ in range(3):
                self.optimizer.zero_grad(set_to_none=True)
                self._step(self.idx)
        torch.cuda.current_stream().wait_stream(side)
        self.graph = torch.cuda.CUDAGraph()
        self.optimizer.zero_grad(set_to_none=True)
        with torch.cuda.graph(self.graph):
            self._step(self.idx)
        with torch.no_grad():
            for p, value in zip(self.net.parameters(), saved):
                p.copy_(value)
            for state in self.optimizer.state.values():   # a fresh Adam, at the same addresses
                for value in state.values():
                    value.zero_()

    def train(self, steps: int) -> dict:
        """Up to `steps` more batches; returns their mean loss and accuracy."""
        self.net.train()
        if self.graph is None:
            self._capture()
        self.loss_sum.zero_()
        self.correct.zero_()
        seen = batches = 0
        for _ in range(min(steps, self.total - self.done)):
            b = self.done % self.per_epoch
            if b == 0:
                self.order = torch.randperm(len(self.y), generator=self.order_rng).to(self.device)
            idx = self.order[b * self.hyper.batch:(b + 1) * self.hyper.batch]
            if self.graph and len(idx) == self.hyper.batch:
                self.idx.copy_(idx)
                self.graph.replay()
            else:
                self.optimizer.zero_grad(set_to_none=not self.graph)
                self._step(idx)
            seen += len(idx)
            batches += 1
            self.done += 1
        if self.finished and self.snapshot is None:
            self.snapshot = models.get_params(self.net)
        return {"loss": float(self.loss_sum) / max(seen, 1), "accuracy": float(self.correct) / max(seen, 1),
                "batches": batches}


def rounds_needed(hosts: list[Host], hyper: Hyper) -> int:
    """Round 0 plus one sync per syncFrequency batches of the longest node (the last partial)."""
    most = max(hyper.epochs * math.ceil(len(h.train.y) / hyper.batch) for h in hosts)
    return 1 + math.ceil(most / hyper.sync_frequency)


# ================================================================ the ledger

def node_name(index: int) -> str:
    """Host k of a scenario is organisation k+1 of the network (configtx SwarmN profiles)."""
    return f"Org{index + 1}MSP"


def channel(scenario: int, model_name: str) -> str:
    return ledger.channel_for(f"eai{scenario}", model_name)


class FabricSwarm:
    """Who leads each round, what every node contributed, and what the leader merged, on Fabric."""

    def __init__(self, scenario: int, model_name: str, gateway: str = ledger.DEFAULT_URL) -> None:
        self.channel = channel(scenario, model_name)
        self.client = ledger.LedgerClient(gateway, channel=self.channel)

    def open(self, tag: str, n_nodes: int) -> dict:
        self.tag = tag
        self.nodes = [node_name(k) for k in range(n_nodes)]
        config = self.client.config()
        if sorted(config["members"]) != sorted(self.nodes):
            raise ledger.LedgerError(
                f"{self.channel} has members {config['members']}, not the {n_nodes} hosts "
                f"{self.nodes}. Is poc/sl-fabric/network/swarms.conf deployed?")
        # a run starts after anything already on this chain: rounds are never reused
        self.offset = self.client.next_free_round(max(self.client.committed_rounds(), default=0))
        self.client.timing = ledger.LedgerTiming()
        self.rejected = 0
        self.leaders: dict[str, int] = {}
        return {"channel": self.channel, "members": config["members"], "quorum": config["quorum"],
                "first_ledger_round": self.offset + 1}

    def merge(self, round_num: int, members: list[int], contributions: list[np.ndarray], n_samples: list[int],
              combine: Callable[[list[np.ndarray], list[int]], np.ndarray]) -> tuple[np.ndarray, dict]:
        """Node members[i] contributes contributions[i], trained on n_samples[i] rows."""
        chain_round = self.offset + round_num + 1
        started = time.perf_counter()
        self.leader = self.client.leader(chain_round)
        self.leaders[self.leader] = self.leaders.get(self.leader, 0) + 1

        # 1. every contributing node commits to its weights, concurrently, as separate
        #    organisations would; the orderer batches the round into one block
        hashes = [models.hash_params(p) for p in contributions]

        def submit(i: int) -> None:
            self.client.submit_update(self.nodes[members[i]], chain_round, hashes[i],
                                      models.size_bytes(contributions[i]), n_samples[i], self.tag)

        with ThreadPoolExecutor(max_workers=len(contributions)) as pool:
            list(pool.map(submit, range(len(contributions))))   # a rejection raises

        # 2. the leader takes in the others' weights, accepting only bytes that match the ledger,
        #    weighing them by the sample counts the ledger holds
        records = {r["node_id"]: r for r in self._once_visible(
            lambda: self.client.round_updates(chain_round),
            lambda rows: len(rows) >= len(contributions), f"round {chain_round}'s updates")}
        accepted = [i for i, p in enumerate(contributions)
                    if records.get(self.nodes[members[i]], {}).get("weight_hash") == models.hash_params(p)]
        self.rejected += len(contributions) - len(accepted)
        ledger_seconds = time.perf_counter() - started

        started = time.perf_counter()
        merged = combine([contributions[i] for i in accepted],
                         [int(records[self.nodes[members[i]]]["n_samples"]) for i in accepted])
        merge_seconds = time.perf_counter() - started
        self._round, self._ledger_seconds = chain_round, ledger_seconds
        self.merged_hash = models.hash_params(merged)
        return merged, {"leader": self.leader, "chain_round": chain_round, "accepted": len(accepted),
                        "merge_seconds": merge_seconds}

    def publish(self, val_accuracy: float, merged: np.ndarray) -> dict:
        """3. the leader closes the round with the merge's hash; 4. every node checks the
        model it was handed against it before training on."""
        started = time.perf_counter()
        self.client.record_aggregation(self.leader, self._round, self.merged_hash, val_accuracy, self.tag)
        recorded = self._once_visible(lambda: self.client.aggregation(self._round),
                                      lambda _: True, f"round {self._round}'s aggregation")
        return {"verified": recorded["aggregated_hash"] == models.hash_params(merged),
                "ledger_seconds": self._ledger_seconds + time.perf_counter() - started}

    @staticmethod
    def _once_visible(read, ready, what: str, timeout: float = 30.0):
        """Read until a just-committed write reaches the peer being read (a submit returns
        once the submitter's peer has the block; the reading peer may get it a moment later)."""
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
        t = self.client.timing
        return {"ledger_calls": t.calls, "ledger_ms": {"submit": t.submit_ms, "aggregate": t.aggregate_ms,
                                                       "read": t.read_ms},
                "rejected_updates": self.rejected, "leader_rounds": self.leaders,
                "last_ledger_round": self._round}


# ================================================================ the two architectures

WEIGHTINGS = ("equal", "samples")
ON_TRAIN_END = ("snapshot", "inactive")


def variant_name(weighting: str, on_train_end: str) -> str:
    """'' for the paper's defaults, else e.g. 'weighted-inactive'."""
    return "-".join(([] if weighting == "equal" else ["weighted"]) +
                    ([] if on_train_end == "snapshot" else [on_train_end]))


def swarm(scenario: Scenario, model_name: str, method: str, coordinator, hyper: Hyper = Hyper(),
          seed: int = 42, device: str = "cuda", log: Callable[[str], None] = print,
          weighting: str = "equal", on_train_end: str = "snapshot") -> dict:
    """Algorithm 1 on the scenario's hosts, each round agreed on the ledger."""
    torch.manual_seed(seed)
    nodes = [Node(k, h, model_name, scenario.n_features, hyper, seed, device) for k, h in enumerate(scenario.hosts)]
    n_samples = [len(h.train.y) for h in scenario.hosts]
    variant = variant_name(weighting, on_train_end)
    tag = f"eai{scenario.number}/{model_name}/{method}" + (f"/{variant}" if variant else "")
    opening = coordinator.open(tag, len(nodes))
    quorum = opening["quorum"]
    planned = rounds_needed(scenario.hosts, hyper)
    last = max(nodes, key=lambda n: n.total)        # trains every round, so holds the model at the end
    # nodeWeightage: 1 for every node (SwarmCallback's default), or the node's training rows
    combine = lambda params, counts: merge(method, params, [1.0] * len(params) if weighting == "equal" else counts)

    probe = models.build(model_name, scenario.n_features, 0).to(device)    # evaluates each round's model
    members = list(nodes)
    contributions = [models.get_params(n.net) for n in nodes]               # on_train_begin
    adopting = list(nodes)
    history = []
    started = time.perf_counter()
    for r in range(planned):
        train_stats: list[dict | None] = [None] * len(nodes)
        if r > 0:
            adopting = [n for n in nodes if not n.finished]
            for n in adopting:
                train_stats[n.index] = n.train(hyper.sync_frequency)
            # a node that has reached its epochs offers the weights it stopped with ("snapshot"),
            # or nothing once its last sync is done ("inactive")
            members = nodes if on_train_end == "snapshot" else adopting
            contributions = [n.snapshot if n.finished and n not in adopting else models.get_params(n.net)
                             for n in members]
        size = models.size_bytes(contributions[0])
        if len(members) >= quorum:
            merged, trace = coordinator.merge(r, [n.index for n in members], contributions,
                                              [n_samples[n.index] for n in members], combine)
            for n in adopting:
                models.set_params(n.net, merged)
            current = merged
            # the leader keeps its own weights: the others' in, the merge back out to the trainers
            trace["upload_bytes"] = sum(node_name(n.index) != trace["leader"] for n in members) * size
            trace["download_bytes"] = sum(node_name(n.index) != trace["leader"] for n in adopting) * size
        else:
            # fewer than a majority still contribute: the chaincode cannot close the round, so
            # nobody merges and each remaining node keeps its own model
            merged, current = None, models.get_params(last.net)
            trace = {"leader": None, "skipped": f"{len(members)} contributing < quorum {quorum}",
                     "upload_bytes": 0, "download_bytes": 0, "ledger_seconds": 0.0, "verified": None}
        models.set_params(probe, current)
        vals = [evaluate(probe, h.val, device) for h in scenario.hosts]
        val = mean_over_hosts(vals)
        if merged is not None:
            trace.update(coordinator.publish(val["accuracy"], merged))
        history.append({
            "round": r, "val_accuracy": val["accuracy"], "val_loss": val["loss"], "val_f1": val["f1"],
            "val_by_host": [{k: v[k] for k in ("accuracy", "loss", "f1")} for v in vals],
            "train": train_stats, "contributed": [n.index for n in members],
            "adopted": [n.index for n in adopting] if merged is not None else [],
            "epochs_done": [n.done / n.per_epoch for n in nodes],
            "model_hash": models.hash_params(current), **trace,
        })
        log(f"{tag:26s} r{r:2d}/{planned - 1}  val acc {val['accuracy']:.4f}  loss {val['loss']:.4f}  "
            f"leader {trace['leader']}  ledger {trace['ledger_seconds']:.2f}s")
    assert all(n.finished for n in nodes), "the swarm stopped before every node finished its epochs"

    test = evaluate(probe, scenario.stacked("test"), device)     # the model of the last round
    return {
        "architecture": "sl", "scenario": scenario.number, "model": model_name, "merge": method,
        "variant": variant, "weighting": weighting, "on_train_end": on_train_end,
        "hosts": [{"name": h.name, "train": len(h.train.y), "val": len(h.val.y), "test": len(h.test.y),
                   "batches": n.total} for h, n in zip(scenario.hosts, nodes)],
        "n_features": scenario.n_features, "n_parameters": int(current.size),
        "model_bytes": models.size_bytes(current), "hyper": hyper.__dict__, "seed": seed, "device": device,
        "rounds": planned, "merged_rounds": sum(h["leader"] is not None for h in history),
        "test": test, "history": history,
        "upload_bytes": sum(h["upload_bytes"] for h in history),
        "seconds": {"wall": time.perf_counter() - started,
                    "ledger": sum(h["ledger_seconds"] for h in history)},
        "final_hash": models.hash_params(current),
        "ledger": {**opening, **coordinator.close()},
    }


def central(scenario: Scenario, model_name: str, hyper: Hyper = Hyper(), seed: int = 42,
            device: str = "cuda", log: Callable[[str], None] = print) -> dict:
    """The CL baseline: one network on every host's training rows, 10 epochs."""
    torch.manual_seed(seed)
    train = scenario.stacked("train")
    host = Host("all", train, scenario.stacked("val"), scenario.stacked("test"))
    node = Node(0, host, model_name, scenario.n_features, hyper, seed, device)
    history = []
    started = time.perf_counter()
    for epoch in range(1, hyper.epochs + 1):
        stats = node.train(node.per_epoch)
        val = evaluate(node.net, host.val, device)
        history.append({"epoch": epoch, "train_loss": stats["loss"], "train_accuracy": stats["accuracy"],
                        "val_accuracy": val["accuracy"], "val_loss": val["loss"], "val_f1": val["f1"]})
        log(f"cl/{scenario.number}/{model_name:10s} epoch {epoch:2d}  val acc {val['accuracy']:.4f}  "
            f"loss {val['loss']:.4f}")
    params = models.get_params(node.net)
    return {
        "architecture": "cl", "scenario": scenario.number, "model": model_name, "merge": None,
        "hosts": [{"name": h.name, "train": len(h.train.y), "val": len(h.val.y), "test": len(h.test.y)}
                  for h in scenario.hosts],
        "n_features": scenario.n_features, "n_parameters": int(params.size),
        "model_bytes": models.size_bytes(params), "hyper": hyper.__dict__, "seed": seed, "device": device,
        "test": evaluate(node.net, host.test, device), "history": history,
        "seconds": {"wall": time.perf_counter() - started},
        "final_hash": models.hash_params(params),
    }
