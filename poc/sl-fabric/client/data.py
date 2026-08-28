"""Loading BloodMNIST and splitting it across swarm nodes.

The split is the experiment's main knob. Every node holds a private shard and never
shares it; how skewed those shards are decides how hard averaging the local models is.
`poc/image/explore.ipynb` shows what the skew looks like for a range of alpha values.

Normalisation constants come from the public training split and are the same for every
node on purpose. If nodes normalised with their own statistics they would be fitting
different functions, and averaging their weights would be meaningless.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

DATASET = Path(__file__).resolve().parents[2] / "image" / "dataset" / "bloodmnist.npz"

CLASS_NAMES = [
    "basophil",
    "eosinophil",
    "erythroblast",
    "immature granulocytes",
    "lymphocyte",
    "monocyte",
    "neutrophil",
    "platelet",
]
N_CLASSES = len(CLASS_NAMES)
IMAGE_SHAPE = (3, 28, 28)  # channels first, the layout the CNN expects


@dataclass(frozen=True)
class Shard:
    """One node's private data, plus the identity it submits under."""

    msp_id: str
    X: np.ndarray  # (n, 3, 28, 28) float32, normalised
    y: np.ndarray  # (n,) int64

    @property
    def n_samples(self) -> int:
        return len(self.y)

    def class_counts(self) -> np.ndarray:
        return np.bincount(self.y, minlength=N_CLASSES)


@dataclass(frozen=True)
class SwarmData:
    """The per-node shards plus the two held-out sets.

    They have different jobs. Validation is scored every round: it drives the curve, the
    "best round" figure and any decision about how long to train. Test is scored once,
    after the last round, and is the only number that should appear as a result — a test
    set that influenced a decision is no longer held out.
    """

    shards: list[Shard]
    X_val: np.ndarray
    y_val: np.ndarray
    X_test: np.ndarray
    y_test: np.ndarray
    alpha: float

    @property
    def total_samples(self) -> int:
        return sum(s.n_samples for s in self.shards)


def _normalise(images: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    """uint8 HWC to float32 CHW, standardised per channel."""
    x = images.astype(np.float32) / 255.0
    x = (x - mean) / std
    return np.ascontiguousarray(x.transpose(0, 3, 1, 2))


def dirichlet_partition(y: np.ndarray, n_nodes: int, alpha: float,
                        seed: int = 42) -> list[np.ndarray]:
    """Split indices across nodes, skewing each class by a Dirichlet draw.

    Small alpha means a node may hold almost only one class; large alpha approaches an
    even, IID split. This is the standard construction in the federated learning
    literature, which makes the results comparable to published numbers.
    """
    rng = np.random.default_rng(seed)
    shards: list[list[int]] = [[] for _ in range(n_nodes)]
    for cls in np.unique(y):
        idx = rng.permutation(np.where(y == cls)[0])
        proportions = rng.dirichlet(np.repeat(alpha, n_nodes))
        cuts = (np.cumsum(proportions) * len(idx)).astype(int)[:-1]
        for node, part in enumerate(np.split(idx, cuts)):
            shards[node].extend(part.tolist())
    return [np.array(sorted(s)) for s in shards]


def load_swarm_data(msp_ids: list[str], alpha: float = 0.5, seed: int = 42,
                    path: Path = DATASET) -> SwarmData:
    """Load the dataset and hand each MSP ID its own shard."""
    if not path.exists():
        raise FileNotFoundError(
            f"{path} is missing. Download it with:\n"
            "  curl -L -o poc/image/dataset/bloodmnist.npz "
            "https://huggingface.co/datasets/albertvillanova/medmnist-v2/resolve/main/data/bloodmnist.npz"
        )

    data = np.load(path)
    X_train_raw, y_train = data["train_images"], data["train_labels"].ravel().astype(np.int64)
    X_val_raw, y_val = data["val_images"], data["val_labels"].ravel().astype(np.int64)
    X_test_raw, y_test = data["test_images"], data["test_labels"].ravel().astype(np.int64)

    flat = X_train_raw.reshape(-1, 3).astype(np.float32) / 255.0
    mean, std = flat.mean(axis=0), flat.std(axis=0)

    X_train = _normalise(X_train_raw, mean, std)
    X_val = _normalise(X_val_raw, mean, std)
    X_test = _normalise(X_test_raw, mean, std)

    parts = dirichlet_partition(y_train, len(msp_ids), alpha, seed)
    shards = [
        Shard(msp_id=msp_id, X=X_train[idx], y=y_train[idx])
        for msp_id, idx in zip(msp_ids, parts)
    ]
    return SwarmData(shards=shards, X_val=X_val, y_val=y_val,
                     X_test=X_test, y_test=y_test, alpha=alpha)


def describe(data: SwarmData) -> str:
    lines = [f"BloodMNIST, Dirichlet alpha={data.alpha}, {data.total_samples} train / "
             f"{len(data.y_val)} val / {len(data.y_test)} test"]
    global_dist = np.bincount(
        np.concatenate([s.y for s in data.shards]), minlength=N_CLASSES
    ) / data.total_samples
    for shard in data.shards:
        local = shard.class_counts() / max(shard.n_samples, 1)
        tv = 0.5 * np.abs(local - global_dist).sum()
        lines.append(f"  {shard.msp_id:9s} n={shard.n_samples:5d}  "
                     f"skew(TV)={tv:.3f}  classes={shard.class_counts().tolist()}")
    return "\n".join(lines)
