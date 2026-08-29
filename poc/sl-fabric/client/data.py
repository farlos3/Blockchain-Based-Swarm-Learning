"""Loading a MedMNIST dataset and splitting it across swarm nodes.

Two datasets are wired up, both 28x28 RGB so the same model code fits either:

    blood   17,092 images, 8 classes  — peripheral blood cells
    path    107,180 images, 9 classes — colon pathology, and the larger of the two

The split is the experiment's main knob. Every node holds a private shard and never
shares it; how skewed those shards are decides how hard averaging the local models is.
`poc/image/explore.ipynb` shows what the skew looks like for a range of alpha values.

Shards are kept as raw uint8 and normalised only when a node is about to train on them.
Holding the larger dataset as float32 would cost about 0.8 GB where the raw form costs
0.2 GB, and that gap decides whether a dataset fits in memory at all.

Normalisation constants come from the training split of the chosen dataset and are the
same for every node on purpose. If nodes normalised with their own statistics they would
be fitting different functions, and averaging their weights would be meaningless.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

DATASET_DIR = Path(__file__).resolve().parents[2] / "image" / "dataset"
IMAGE_SHAPE = (3, 28, 28)  # channels first, the layout the CNN expects

# Anything added here needs the same 28x28 RGB geometry, or the models stop fitting.
DATASETS: dict[str, dict[str, object]] = {
    "blood": {
        "file": "bloodmnist.npz",
        "title": "BloodMNIST — peripheral blood cells",
        "classes": [
            "basophil", "eosinophil", "erythroblast", "immature granulocytes",
            "lymphocyte", "monocyte", "neutrophil", "platelet",
        ],
    },
    "path": {
        "file": "pathmnist.npz",
        "title": "PathMNIST — colorectal cancer histology",
        "classes": [
            "adipose", "background", "debris", "lymphocytes", "mucus",
            "smooth muscle", "normal colon mucosa", "cancer-associated stroma",
            "colorectal adenocarcinoma epithelium",
        ],
    },
}

DOWNLOAD = ("curl -L -o poc/image/dataset/{file} "
            "https://huggingface.co/datasets/albertvillanova/medmnist-v2/resolve/main/data/{file}")


@dataclass(frozen=True)
class Shard:
    """One node's private data, plus the identity it submits under.

    X stays in the archive's own uint8 HWC layout; SwarmData.prepare turns a shard into
    the float32 CHW a model wants, one node at a time.
    """

    msp_id: str
    X: np.ndarray  # (n, 28, 28, 3) uint8
    y: np.ndarray  # (n,) int64
    n_classes: int

    @property
    def n_samples(self) -> int:
        return len(self.y)

    def class_counts(self) -> np.ndarray:
        return np.bincount(self.y, minlength=self.n_classes)


@dataclass(frozen=True)
class SwarmData:
    """The per-node shards plus the two held-out sets.

    They have different jobs. Validation is scored every round: it drives the curve, the
    "best round" figure and any decision about how long to train. Test is scored once,
    after the last round, and is the only number that should appear as a result — a test
    set that influenced a decision is no longer held out.
    """

    dataset: str
    shards: list[Shard]
    X_val: np.ndarray
    y_val: np.ndarray
    X_test: np.ndarray
    y_test: np.ndarray
    alpha: float
    n_classes: int
    mean: np.ndarray
    std: np.ndarray

    @property
    def total_samples(self) -> int:
        return sum(s.n_samples for s in self.shards)

    @property
    def title(self) -> str:
        return str(DATASETS[self.dataset]["title"])

    def prepare(self, images: np.ndarray) -> np.ndarray:
        """uint8 HWC to normalised float32 CHW, for one shard at a time."""
        x = images.astype(np.float32) / 255.0
        x = (x - self.mean) / self.std
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


def load_swarm_data(msp_ids: list[str], dataset: str = "blood", alpha: float = 0.5,
                    seed: int = 42) -> SwarmData:
    """Load one dataset and hand each MSP ID its own shard."""
    if dataset not in DATASETS:
        raise ValueError(f"unknown dataset {dataset!r}, pick from {sorted(DATASETS)}")

    spec = DATASETS[dataset]
    path = DATASET_DIR / str(spec["file"])
    if not path.exists():
        raise FileNotFoundError(
            f"{path} is missing. Download it with:\n  " + DOWNLOAD.format(file=spec["file"])
        )

    archive = np.load(path)
    X_train = archive["train_images"]
    y_train = archive["train_labels"].ravel().astype(np.int64)
    y_val = archive["val_labels"].ravel().astype(np.int64)
    y_test = archive["test_labels"].ravel().astype(np.int64)

    # from the training split only, and shared by every node
    flat = X_train.reshape(-1, 3).astype(np.float32) / 255.0
    mean, std = flat.mean(axis=0), flat.std(axis=0)
    del flat

    n_classes = len(spec["classes"])  # type: ignore[arg-type]
    parts = dirichlet_partition(y_train, len(msp_ids), alpha, seed)
    shards = [
        Shard(msp_id=msp_id, X=X_train[idx], y=y_train[idx], n_classes=n_classes)
        for msp_id, idx in zip(msp_ids, parts)
    ]

    data = SwarmData(
        dataset=dataset, shards=shards,
        X_val=np.empty(0), y_val=y_val, X_test=np.empty(0), y_test=y_test,
        alpha=alpha, n_classes=n_classes, mean=mean, std=std,
    )
    # the held-out sets are small and scored every round, so they are normalised once
    return SwarmData(
        dataset=dataset, shards=shards,
        X_val=data.prepare(archive["val_images"]), y_val=y_val,
        X_test=data.prepare(archive["test_images"]), y_test=y_test,
        alpha=alpha, n_classes=n_classes, mean=mean, std=std,
    )


def describe(data: SwarmData) -> str:
    lines = [f"{data.title}, Dirichlet alpha={data.alpha}, {data.n_classes} classes, "
             f"{data.total_samples:,} train / {len(data.y_val):,} val / {len(data.y_test):,} test"]
    global_dist = np.bincount(
        np.concatenate([s.y for s in data.shards]), minlength=data.n_classes
    ) / data.total_samples
    for shard in data.shards:
        local = shard.class_counts() / max(shard.n_samples, 1)
        tv = 0.5 * np.abs(local - global_dist).sum()
        lines.append(f"  {shard.msp_id:9s} n={shard.n_samples:6d}  "
                     f"skew(TV)={tv:.3f}  classes={shard.class_counts().tolist()}")
    return "\n".join(lines)
