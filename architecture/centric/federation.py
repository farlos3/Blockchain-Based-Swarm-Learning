"""Local training, aggregation and evaluation: everything FL and SL have in common.

The paper's Algorithm 1 is a loop of "every client trains, then the updates are merged".
Swarm learning keeps that loop and changes only who merges and how the merge is agreed
on. So the loop lives here once, and the architecture is a `Coordinator` handed in from
outside (architectures.py): a central server, or a swarm whose leader is elected and
audited on Fabric. Same seeds, same data, same arithmetic — any difference between the
two runs can only come from the coordinator.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Callable, Protocol

import numpy as np
import torch
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support, roc_auc_score
from torch import nn

import models
from data import Client, Federation

ALGORITHMS = ("fedavg", "fedprox", "fednova")


@dataclass(frozen=True)
class Hyper:
    """Table 4 and Section 4.3 defaults, identical for every algorithm and architecture."""
    epochs: int = 5
    batch: int = 128
    weight_decay: float = 1e-4
    mu: float = 1e-3          # FedProx proximal coefficient
    target_accuracy: float = 0.95   # Table 9 measures rounds to 95%


@dataclass
class Update:
    """What one client hands back after LocalTrain."""
    client: int
    params: np.ndarray
    n_samples: int
    steps: int            # tau_k = E * ceil(|D_k| / B), what FedNova normalises by
    seconds: float


def local_steps(n_samples: int, hyper: Hyper) -> int:
    return hyper.epochs * math.ceil(n_samples / hyper.batch)


def local_train(net: nn.Module, start: np.ndarray, client: Client, index: int, algorithm: str,
                hyper: Hyper, lr: float, seed: int) -> Update:
    """Algorithm 3: E epochs of Adam on the client's training split, starting from `start`.

    A fresh optimizer every round: a client keeps no state between rounds beyond its data.
    FedProx adds (mu/2)*||w - w_global||^2 to the loss; the other two train plainly.
    """
    started = time.perf_counter()
    models.set_params(net, start)
    net.train()
    device = next(net.parameters()).device
    torch.manual_seed(seed)                       # dropout masks, on every device
    order_rng = torch.Generator().manual_seed(seed)   # batch order, drawn on the CPU
    X = torch.from_numpy(client.X_train).to(device)
    y = torch.from_numpy(client.y_train).to(device)
    fedprox = algorithm == "fedprox"
    if device.type == "cuda":
        step = CudaStep.of(net, X.shape[1], hyper, lr, fedprox)
        step.reset()
    else:
        optimizer = torch.optim.Adam(net.parameters(), lr=lr, betas=(0.9, 0.999),
                                     weight_decay=hyper.weight_decay)
        anchor = [p.detach().clone() for p in net.parameters()] if fedprox else None

        def step(xb: torch.Tensor, yb: torch.Tensor) -> None:
            optimizer.zero_grad()
            _loss(net, xb, yb, anchor, hyper.mu).backward()
            optimizer.step()

    steps = 0
    for _ in range(hyper.epochs):
        order = torch.randperm(len(y), generator=order_rng).to(device)
        for begin in range(0, len(y), hyper.batch):
            batch = order[begin:begin + hyper.batch]
            step(X[batch], y[batch])
            steps += 1
    return Update(index, models.get_params(net), len(y), steps, time.perf_counter() - started)


def _loss(net: nn.Module, x: torch.Tensor, y: torch.Tensor, anchor: list[torch.Tensor] | None,
          mu: float) -> torch.Tensor:
    """Cross-entropy, plus FedProx's (mu/2)*||w - w_global||^2 when there is an anchor."""
    loss = nn.functional.cross_entropy(net(x), y)
    if anchor is not None:
        loss = loss + mu / 2 * sum(((p - a) ** 2).sum() for p, a in zip(net.parameters(), anchor))
    return loss


class CudaStep:
    """One optimizer step of LocalTrain on a GPU, its full batches replayed from a CUDA graph.

    These models are tiny: a batch of 128 costs the GPU microseconds, while launching its
    few hundred kernels one by one from Python costs milliseconds. A captured graph
    launches them all at once (measured ~30x faster for both models). A graph is bound to
    fixed memory, so the network, its Adam state, the proximal anchor and the batch stay at
    fixed addresses, and a client's round resets them in place instead of replacing them.
    Per step it matches the eager path to float rounding; the last, short batch of an epoch
    runs eagerly through the same optimizer.
    """

    def __init__(self, net: nn.Module, n_features: int, hyper: Hyper, lr: float, fedprox: bool) -> None:
        self.net = net
        self.mu = hyper.mu
        self.x = torch.zeros(hyper.batch, n_features, device="cuda")
        self.y = torch.zeros(hyper.batch, dtype=torch.long, device="cuda")
        self.anchor = [p.detach().clone() for p in net.parameters()] if fedprox else None
        self.optimizer = torch.optim.Adam(net.parameters(), lr=lr, betas=(0.9, 0.999),
                                          weight_decay=hyper.weight_decay, capturable=True)
        # capture needs a few eager steps first, on a side stream; they move the weights,
        # so the weights are put back afterwards and reset() clears the optimizer
        saved = [p.detach().clone() for p in net.parameters()]
        side = torch.cuda.Stream()
        side.wait_stream(torch.cuda.current_stream())
        with torch.cuda.stream(side):
            for _ in range(3):
                self.optimizer.zero_grad(set_to_none=True)
                _loss(net, self.x, self.y, self.anchor, self.mu).backward()
                self.optimizer.step()
        torch.cuda.current_stream().wait_stream(side)
        self.graph = torch.cuda.CUDAGraph()
        self.optimizer.zero_grad(set_to_none=True)
        with torch.cuda.graph(self.graph):
            _loss(net, self.x, self.y, self.anchor, self.mu).backward()
            self.optimizer.step()
        with torch.no_grad():
            for p, s in zip(net.parameters(), saved):
                p.copy_(s)

    @classmethod
    def of(cls, net: nn.Module, n_features: int, hyper: Hyper, lr: float, fedprox: bool) -> "CudaStep":
        """The step for this network and setting, captured on first use and kept on the net."""
        cache = net.__dict__.setdefault("_cuda_steps", {})
        key = (n_features, hyper, lr, fedprox)
        if key not in cache:
            cache[key] = cls(net, n_features, hyper, lr, fedprox)
        return cache[key]

    def reset(self) -> None:
        """A fresh Adam, and the weights as they are now as the proximal anchor."""
        with torch.no_grad():
            for state in self.optimizer.state.values():
                for value in state.values():
                    value.zero_()
            if self.anchor is not None:
                for a, p in zip(self.anchor, self.net.parameters()):
                    a.copy_(p)

    def __call__(self, x: torch.Tensor, y: torch.Tensor) -> None:
        if len(y) == len(self.y):
            self.x.copy_(x)
            self.y.copy_(y)
            self.graph.replay()
        else:
            self.optimizer.zero_grad(set_to_none=False)
            _loss(self.net, x, y, self.anchor, self.mu).backward()
            self.optimizer.step()


def aggregate(algorithm: str, start: np.ndarray, updates: list[Update]) -> np.ndarray:
    """Eq. (1) for FedAvg and FedProx, FedNova as in its authors' code.

    The paper's Eq. (3) writes FedNova as w + sum_k (n_k/n) * dw_k / tau_k, which drops the
    effective step count tau_eff = sum_k (n_k/n) * tau_k that the original algorithm (Wang et
    al. 2020) multiplies back in. Without it every round moves the model by one average
    local step, and FedNova could not "coincide with FedAvg when every client does the same
    amount of work", which the paper states it does. The paper also says it used the
    authors' implementation, so that is what this follows.

    Updates are summed in client order in float64, so a merge gives the same bits whoever
    performs it — the server, or whichever swarm node the ledger elects.
    """
    updates = sorted(updates, key=lambda u: u.client)
    total = sum(u.n_samples for u in updates)
    share = [u.n_samples / total for u in updates]
    if algorithm in ("fedavg", "fedprox"):
        merged = sum(p * u.params.astype(np.float64) for p, u in zip(share, updates))
    elif algorithm == "fednova":
        base = start.astype(np.float64)
        tau_eff = sum(p * u.steps for p, u in zip(share, updates))
        direction = sum(p * (u.params.astype(np.float64) - base) / u.steps
                        for p, u in zip(share, updates))
        merged = base + tau_eff * direction
    else:
        raise ValueError(f"unknown algorithm {algorithm!r}")
    return merged.astype(np.float32)


def evaluate(net: nn.Module, params: np.ndarray, X: np.ndarray, y: np.ndarray,
             n_classes: int) -> dict:
    """Section 4.4: accuracy, macro precision / recall / F1, macro one-vs-rest AUC, and the
    confusion matrix, from which per-class rates and attack-vs-benign FPR / FNR follow."""
    models.set_params(net, params)
    net.eval()
    device = next(net.parameters()).device
    with torch.no_grad():
        logits = torch.cat([net(torch.from_numpy(X[i:i + 8192]).to(device)).cpu()
                            for i in range(0, len(X), 8192)])
    probs = torch.softmax(logits, dim=1).numpy().astype(np.float64)
    pred = probs.argmax(axis=1)
    labels = list(range(n_classes))
    # macro over the classes that occur in the labels or the predictions, as sklearn does by
    # default: a class absent from a test set (the rarest families under a full release's
    # real proportions, or a cross-dataset target) is not scored as a zero
    precision, recall, f1, _ = precision_recall_fscore_support(
        y, pred, average="macro", zero_division=0)
    matrix = confusion_matrix(y, pred, labels=labels)

    # AUC is defined per class only where that class occurs; a cross-dataset target can
    # lack a class the source knows
    present = [c for c in labels if (y == c).any()]
    auc = float("nan")
    if len(present) > 1:
        auc = float(np.mean([roc_auc_score(y == c, probs[:, c]) for c in present]))

    benign = matrix[0, 0], matrix[0, 1:].sum()        # benign correctly / flagged as attack
    attack = matrix[1:, 0].sum(), matrix[1:, 1:].sum()  # attacks missed / caught
    return {
        "accuracy": float((pred == y).mean()),
        "precision": float(precision), "recall": float(recall), "f1": float(f1), "auc": auc,
        "fpr": float(benign[1] / max(benign[0] + benign[1], 1)),
        "fnr": float(attack[0] / max(attack[0] + attack[1], 1)),
        "confusion": matrix.tolist(),
        "n": int(len(y)),
    }


class Coordinator(Protocol):
    """Who turns a round's local updates into the next global model."""

    name: str

    def open(self, tag: str, n_clients: int) -> dict: ...

    def merge(self, round_num: int, start: np.ndarray, updates: list[Update],
              combine: Callable[[np.ndarray, list[Update]], np.ndarray]) -> tuple[np.ndarray, dict]: ...

    def publish(self, round_num: int, params: np.ndarray, val_accuracy: float) -> dict: ...

    def close(self) -> dict: ...


def round_seed(seed: int, round_num: int, client: int) -> int:
    return int(np.random.SeedSequence([seed, round_num, client]).generate_state(1)[0])


def train(fed: Federation, model_name: str, algorithm: str, coordinators: list[Coordinator],
          rounds: int, hyper: Hyper = Hyper(), seed: int = 42,
          log: Callable[[str], None] = print, device: str = "cpu") -> tuple[list[dict], nn.Module, np.ndarray]:
    """Algorithm 1, its local updates merged by each of the given coordinators every round.

    Local training does not depend on who merges, so with several coordinators (FL's server
    and SL's swarm) a round trains once and hands the same updates to each. Each must
    produce the same global model, bit for bit, or the run stops: from then on they would
    no longer be training the same model. Returns one record per coordinator, the network
    and its final parameters (for any evaluation the caller adds, such as cross-dataset tests).
    """
    n_classes = len(fed.classes)
    net = models.build(model_name, fed.n_features, n_classes, seed).to(device)
    params = models.get_params(net)
    lr = models.LEARNING_RATES[model_name]
    X_val, y_val = fed.stacked("val")
    tag = f"{fed.scenario}/{model_name}/{algorithm}"
    opened = [c.open(tag, len(fed.clients)) for c in coordinators]
    combine = lambda start, ups: aggregate(algorithm, start, ups)

    histories: list[list[dict]] = [[] for _ in coordinators]
    started = time.perf_counter()
    for r in range(1, rounds + 1):
        updates = [local_train(net, params, client, k, algorithm, hyper, lr, round_seed(seed, r, k))
                   for k, client in enumerate(fed.clients)]
        train_seconds = sum(u.seconds for u in updates)
        merges = [c.merge(r, params, updates, combine) for c in coordinators]
        merged = merges[0][0]
        for c, (other, _) in zip(coordinators, merges):
            if other.tobytes() != merged.tobytes():
                raise RuntimeError(f"{tag} round {r}: {c.name} produced a different global model "
                                   f"than {coordinators[0].name}")
        val = evaluate(net, merged, X_val, y_val, n_classes)
        params = merged
        for c, (_, trace), history in zip(coordinators, merges, histories):
            trace.update(c.publish(r, merged, val["accuracy"]))
            history.append({
                "round": r, "val_accuracy": val["accuracy"], "val_f1": val["f1"],
                "train_seconds": train_seconds, "global_hash": models.hash_params(params), **trace,
            })
        log(f"{tag:28s} r{r:3d}  val acc {val['accuracy']:.4f}  f1 {val['f1']:.4f}  "
            f"train {train_seconds:6.1f}s  " + "  ".join(
                f"{c.name} {h[-1].get('coordination_seconds', 0):5.2f}s" for c, h in zip(coordinators, histories)))

    wall = time.perf_counter() - started
    test = evaluate(net, params, *fed.stacked("test"), n_classes)
    records = []
    for c, history, opening in zip(coordinators, histories, opened):
        reached = next((h["round"] for h in history if h["val_accuracy"] >= hyper.target_accuracy), None)
        seconds = {key: sum(h[f"{key}_seconds"] for h in history) for key in ("train", "aggregate", "coordination")}
        records.append({
            "scenario": fed.scenario, "model": model_name, "algorithm": algorithm,
            "architecture": c.name, "rounds": rounds, "seed": seed, "device": device,
            "hyper": hyper.__dict__, "learning_rate": lr,
            "classes": list(fed.classes), "n_features": fed.n_features, "features": fed.features,
            "rows_drawn": fed.rows, "sources": fed.sources,
            "release_rows": fed.source_rows,
            "clients": [{"key": cl.key, "train": cl.n_train, "val": len(cl.y_val), "test": len(cl.y_test),
                         "local_steps": local_steps(cl.n_train, hyper)} for cl in fed.clients],
            "n_parameters": int(params.size),
            "test": test,
            "rounds_to_target": reached,
            "history": history,
            # what this architecture alone takes: the shared training plus its own merging
            # and agreement; `wall` is the joint run, every coordinator included
            "seconds": {"total": sum(seconds.values()), **seconds, "wall": wall},
            "trained_with": [o.name for o in coordinators],
            "bytes_exchanged": sum(h["bytes"] for h in history),
            "final_hash": models.hash_params(params),
            "coordinator": {**opening, **c.close()},
        })
    return records, net, params
