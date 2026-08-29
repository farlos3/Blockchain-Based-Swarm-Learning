"""The models the swarm can train, behind one interface.

Averaging weights across nodes only works if every node holds the *same* architecture in
the *same* parameter layout. So each model exposes its parameters as one flat float64
vector and can be restored from one, and the swarm loop never needs to know which
architecture it is driving.

Five are provided, spanning two orders of magnitude in size, to separate "more
parameters" from "better suited to images":

    logistic   multinomial logistic regression on raw pixels — the cheapest thing that
               can learn 8 classes at all, and the baseline the earlier PoC used
    mlp        one hidden layer on raw pixels — more capacity, still no spatial structure
    mlp_deep   two hidden layers — more depth on the same blind representation
    cnn        a small convolutional network — knows pixels have neighbours, which is
               what actually matters for images
    cnn_wide   the same shape with twice the channels — more capacity where it helps

They differ by orders of magnitude in parameter count and training cost, and that
difference is the point of the comparison: on this ledger every parameter is traffic
between nodes, even though only its hash is recorded on chain.
"""

from __future__ import annotations

import hashlib
import time
from typing import Callable, Protocol

import numpy as np

from data import IMAGE_SHAPE

N_FEATURES = int(np.prod(IMAGE_SHAPE))


class SwarmModel(Protocol):
    """What the swarm loop needs from a model. Everything else is the model's business."""

    name: str

    def get_params(self) -> np.ndarray: ...
    def set_params(self, flat: np.ndarray) -> None: ...
    def predict(self, X: np.ndarray) -> np.ndarray: ...

    # on_epoch(index, seconds) is called as each local epoch finishes, so a caller can
    # show progress inside a round instead of only between rounds
    def train(self, X: np.ndarray, y: np.ndarray, epochs: int,
              on_epoch: Callable[[int, float], None] | None = None) -> None: ...


def hash_params(flat: np.ndarray) -> str:
    """The fingerprint that goes on the ledger, over the canonical float64 bytes.

    The shape is folded in so two different architectures can never collide, and float64
    is forced so a node that happens to hold float32 weights still agrees with one that
    does not.
    """
    values = np.ascontiguousarray(flat, dtype=np.float64)
    digest = hashlib.sha256()
    digest.update(str(values.shape).encode("utf-8"))
    digest.update(values.tobytes())
    return digest.hexdigest()


def params_size_bytes(flat: np.ndarray) -> int:
    """Bytes a node would actually ship per round (float32 on the wire)."""
    return int(np.asarray(flat, dtype=np.float32).nbytes)


# ---------- scikit-learn models ----------


class _SklearnModel:
    """Shared plumbing for the scikit-learn estimators.

    Both need one `partial_fit` before their coefficient arrays exist, so the constructor
    does a warm-up pass over a single batch that contains every class. After that the
    layout is fixed and flatten/restore is just concatenation.
    """

    name = "sklearn"

    def __init__(self, estimator, n_classes: int, seed: int = 0) -> None:
        self.estimator = estimator
        self.n_classes = n_classes
        rng = np.random.default_rng(seed)
        warmup_X = rng.normal(size=(n_classes, N_FEATURES)).astype(np.float32)
        warmup_y = np.arange(n_classes)
        self.estimator.partial_fit(warmup_X, warmup_y, classes=np.arange(n_classes))
        # scikit-learn's SGD requires its coefficients to have the same dtype as the
        # training data, so the layout captured here records dtype as well as shape
        self._shapes = [a.shape for a in self._arrays()]
        self._dtypes = [a.dtype for a in self._arrays()]

    def _arrays(self) -> list[np.ndarray]:
        raise NotImplementedError

    def _assign(self, arrays: list[np.ndarray]) -> None:
        raise NotImplementedError

    def get_params(self) -> np.ndarray:
        return np.concatenate([np.asarray(a, dtype=np.float64).ravel() for a in self._arrays()])

    def set_params(self, flat: np.ndarray) -> None:
        arrays, offset = [], 0
        for shape, dtype in zip(self._shapes, self._dtypes):
            size = int(np.prod(shape))
            arrays.append(flat[offset:offset + size].reshape(shape).astype(dtype, copy=True))
            offset += size
        if offset != len(flat):
            raise ValueError(f"expected {offset} parameters, got {len(flat)}")
        self._assign(arrays)

    def train(self, X: np.ndarray, y: np.ndarray, epochs: int,
              on_epoch: Callable[[int, float], None] | None = None) -> None:
        flat_X = X.reshape(len(X), -1)
        for epoch in range(epochs):
            started = time.perf_counter()
            self.estimator.partial_fit(flat_X, y, classes=np.arange(self.n_classes))
            if on_epoch is not None:
                on_epoch(epoch + 1, time.perf_counter() - started)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.estimator.predict(X.reshape(len(X), -1))


class LogisticModel(_SklearnModel):
    """Multinomial logistic regression trained with SGD — one weight per pixel per class."""

    name = "logistic"

    def __init__(self, n_classes: int, seed: int = 0, learning_rate: float = 0.01) -> None:
        from sklearn.linear_model import SGDClassifier

        super().__init__(
            SGDClassifier(loss="log_loss", learning_rate="constant", eta0=learning_rate,
                          random_state=seed),
            n_classes=n_classes, seed=seed,
        )

    def _arrays(self) -> list[np.ndarray]:
        return [self.estimator.coef_, self.estimator.intercept_]

    def _assign(self, arrays: list[np.ndarray]) -> None:
        self.estimator.coef_, self.estimator.intercept_ = arrays


class MLPModel(_SklearnModel):
    """One hidden layer. More capacity than logistic, still blind to pixel geometry."""

    name = "mlp"
    hidden_layers: tuple[int, ...] = (128,)

    def __init__(self, n_classes: int, seed: int = 0, learning_rate: float = 0.01) -> None:
        from sklearn.neural_network import MLPClassifier

        super().__init__(
            MLPClassifier(hidden_layer_sizes=self.hidden_layers,
                          learning_rate_init=learning_rate, random_state=seed),
            n_classes=n_classes, seed=seed,
        )

    def _arrays(self) -> list[np.ndarray]:
        return [*self.estimator.coefs_, *self.estimator.intercepts_]

    def _assign(self, arrays: list[np.ndarray]) -> None:
        half = len(arrays) // 2
        self.estimator.coefs_ = arrays[:half]
        self.estimator.intercepts_ = arrays[half:]


class MLPDeepModel(MLPModel):
    """Two hidden layers: depth on top of the same pixel-blind representation.

    Here to answer the obvious objection to the mlp result — that it lost to the CNN for
    lack of capacity rather than lack of structure.
    """

    name = "mlp_deep"
    hidden_layers = (256, 128)


# ---------- torch model ----------


class CNNModel:
    """A small convolutional network: two conv blocks, then two dense layers.

    Kept deliberately small. The comparison is about what convolution buys over dense
    layers on the same data and the same number of rounds, not about reaching the best
    published accuracy on BloodMNIST.
    """

    name = "cnn"
    channels: tuple[int, int] = (16, 32)
    dense: int = 64

    def __init__(self, n_classes: int, seed: int = 0, learning_rate: float = 0.001,
                 batch_size: int = 64) -> None:
        import torch
        from torch import nn

        torch.manual_seed(seed)
        torch.set_num_threads(max(1, (torch.get_num_threads() or 2) // 2))

        self.torch = torch
        self.batch_size = batch_size
        c1, c2 = self.channels
        self.net = nn.Sequential(
            nn.Conv2d(IMAGE_SHAPE[0], c1, 3), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(c1, c2, 3), nn.ReLU(), nn.MaxPool2d(2),
            nn.Flatten(),
            nn.Linear(c2 * 5 * 5, self.dense), nn.ReLU(),
            nn.Linear(self.dense, n_classes),
        )
        self.loss_fn = nn.CrossEntropyLoss()
        self.learning_rate = learning_rate
        self._shapes = [tuple(p.shape) for p in self.net.parameters()]

    def get_params(self) -> np.ndarray:
        with self.torch.no_grad():
            return np.concatenate([p.detach().numpy().ravel().astype(np.float64)
                                   for p in self.net.parameters()])

    def set_params(self, flat: np.ndarray) -> None:
        offset = 0
        with self.torch.no_grad():
            for param, shape in zip(self.net.parameters(), self._shapes):
                size = int(np.prod(shape))
                chunk = flat[offset:offset + size].reshape(shape)
                param.copy_(self.torch.from_numpy(np.ascontiguousarray(chunk, dtype=np.float32)))
                offset += size
        if offset != len(flat):
            raise ValueError(f"expected {offset} parameters, got {len(flat)}")

    def train(self, X: np.ndarray, y: np.ndarray, epochs: int,
              on_epoch: Callable[[int, float], None] | None = None) -> None:
        torch = self.torch
        # a fresh optimiser each round: its momentum belongs to the local model, and
        # carrying it across an aggregation would mix in gradients from a model that no
        # longer exists
        optimiser = torch.optim.Adam(self.net.parameters(), lr=self.learning_rate)
        dataset = torch.utils.data.TensorDataset(
            torch.from_numpy(np.ascontiguousarray(X, dtype=np.float32)),
            torch.from_numpy(np.ascontiguousarray(y, dtype=np.int64)),
        )
        loader = torch.utils.data.DataLoader(dataset, batch_size=self.batch_size, shuffle=True)

        self.net.train()
        for epoch in range(epochs):
            started = time.perf_counter()
            for batch_X, batch_y in loader:
                optimiser.zero_grad()
                self.loss_fn(self.net(batch_X), batch_y).backward()
                optimiser.step()
            if on_epoch is not None:
                on_epoch(epoch + 1, time.perf_counter() - started)

    def predict(self, X: np.ndarray) -> np.ndarray:
        torch = self.torch
        self.net.eval()
        out = []
        with torch.no_grad():
            for start in range(0, len(X), 256):
                batch = torch.from_numpy(np.ascontiguousarray(X[start:start + 256], dtype=np.float32))
                out.append(self.net(batch).argmax(dim=1).numpy())
        return np.concatenate(out)


class CNNWideModel(CNNModel):
    """The same architecture with twice the channels and a wider dense layer.

    Its parameter count lands near the mlp's, which makes the pair a fair test of where
    capacity is better spent: on convolution or on fully connected weights.
    """

    name = "cnn_wide"
    channels = (32, 64)
    dense = 128


# ---------- registry ----------

BUILDERS = {
    "logistic": LogisticModel,
    "mlp": MLPModel,
    "mlp_deep": MLPDeepModel,
    "cnn": CNNModel,
    "cnn_wide": CNNWideModel,
}


def build(name: str, n_classes: int, seed: int = 0) -> SwarmModel:
    """Every model is sized to the dataset it will train on, so its output layer matches."""
    if name not in BUILDERS:
        raise ValueError(f"unknown model {name!r}, pick one of {sorted(BUILDERS)}")
    return BUILDERS[name](n_classes=n_classes, seed=seed)
