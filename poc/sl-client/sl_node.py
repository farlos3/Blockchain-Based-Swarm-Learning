"""Local-training half of a swarm-learning node.

Each simulated node holds a disjoint shard of sklearn's digits dataset,
trains a small multinomial logistic-regression model for a few local
epochs on top of the current global weights, and writes the resulting
weights off-chain (weights never touch the ledger — only their hash does).
"""
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from sklearn.datasets import load_digits
from sklearn.linear_model import SGDClassifier

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
WEIGHTS_DIR = RESULTS_DIR / "weights"
NUM_CLASSES = 10


def load_shard(node_index: int, num_nodes: int):
    digits = load_digits()
    x, y = digits.data, digits.target
    rng = np.random.RandomState(42)
    order = rng.permutation(len(x))
    x, y = x[order], y[order]
    shards_x = np.array_split(x, num_nodes)
    shards_y = np.array_split(y, num_nodes)
    return shards_x[node_index], shards_y[node_index]


def _global_weights_path(round_num: int) -> Path:
    return WEIGHTS_DIR / f"round_{round_num - 1}" / "global.npz"


def _node_weights_path(round_num: int, node_id: str) -> Path:
    return WEIGHTS_DIR / f"round_{round_num}" / f"{node_id}.npz"


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def local_train(node_id: str, node_index: int, num_nodes: int, round_num: int, local_epochs: int = 3):
    """Train locally starting from the previous round's global weights.

    Returns (weights_path, weight_hash, size_bytes, train_seconds).
    """
    x, y = load_shard(node_index, num_nodes)

    clf = SGDClassifier(loss="log_loss", max_iter=1, learning_rate="optimal",
                         warm_start=True, random_state=node_index)

    t0 = time.time()
    prev_path = _global_weights_path(round_num)
    if prev_path.exists():
        prev = np.load(prev_path)
        clf.partial_fit(x[:1], y[:1], classes=np.arange(NUM_CLASSES))
        clf.coef_ = prev["coef"].copy()
        clf.intercept_ = prev["intercept"].copy()

    classes = np.arange(NUM_CLASSES)
    for _ in range(local_epochs):
        clf.partial_fit(x, y, classes=classes)
    train_seconds = time.time() - t0

    out_dir = WEIGHTS_DIR / f"round_{round_num}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = _node_weights_path(round_num, node_id)
    np.savez(out_path, coef=clf.coef_, intercept=clf.intercept_)

    weight_hash = sha256_of_file(out_path)
    size_bytes = out_path.stat().st_size
    return out_path, weight_hash, size_bytes, train_seconds


def aggregate(round_num: int, node_ids: list[str]):
    """FedAvg: average every node's local weights for this round."""
    coefs, intercepts = [], []
    for node_id in node_ids:
        data = np.load(_node_weights_path(round_num, node_id))
        coefs.append(data["coef"])
        intercepts.append(data["intercept"])

    avg_coef = np.mean(coefs, axis=0)
    avg_intercept = np.mean(intercepts, axis=0)

    out_dir = WEIGHTS_DIR / f"round_{round_num}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "global.npz"
    np.savez(out_path, coef=avg_coef, intercept=avg_intercept)

    return out_path, sha256_of_file(out_path)


def evaluate_global(round_num: int) -> float:
    """Accuracy of the aggregated global model on the full digits set (sanity check only)."""
    digits = load_digits()
    data = np.load(_global_weights_path(round_num + 1))
    clf = SGDClassifier(loss="log_loss")
    clf.classes_ = np.arange(NUM_CLASSES)
    clf.coef_ = data["coef"]
    clf.intercept_ = data["intercept"]
    preds = clf.predict(digits.data)
    return float((preds == digits.target).mean())
