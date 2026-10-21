"""The two IDS backbones of Bilal et al. (2026), Section "Deep learning models".

LSTM         2 layers (64 then 32 units), dropout 0.2 between them, then two dense
             layers. Each flow is a length-1 sequence, so it behaves like a gated
             feed-forward net, exactly as the paper notes.
Transformer  2 encoder blocks, 4 heads, hidden size 64. The feature vector is cut into
             four equal segments that act as pseudo-positions, positional encodings are
             added, the encoder output is mean-pooled, and one dense layer classifies.

Both end in logits; softmax lives inside the cross-entropy loss. Weights are handled as
one flat float32 vector so the aggregation code never needs to know which model it holds,
and so a model's identity can be pinned on the ledger by hashing those bytes.
"""

from __future__ import annotations

import hashlib
import math

import numpy as np
import torch
from torch import nn

SEGMENTS = 4      # pseudo-positions for the Transformer
D_MODEL = 64      # "hidden size 64"
HEADS = 4
BLOCKS = 2
FFN = 128         # not given in the paper; 2 x d_model keeps it the same order as the LSTM


class LSTMNet(nn.Module):
    def __init__(self, n_features: int, n_classes: int) -> None:
        super().__init__()
        self.lstm1 = nn.LSTM(n_features, 64, batch_first=True)
        self.drop = nn.Dropout(0.2)
        self.lstm2 = nn.LSTM(64, 32, batch_first=True)
        self.dense = nn.Linear(32, 32)
        self.out = nn.Linear(32, n_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h, _ = self.lstm1(x.unsqueeze(1))          # one flow = one timestep
        h, _ = self.lstm2(self.drop(h))
        return self.out(torch.relu(self.dense(h[:, -1])))


class TransformerNet(nn.Module):
    def __init__(self, n_features: int, n_classes: int) -> None:
        super().__init__()
        # four equal segments need a width divisible by four: pad with zero features
        self.padded = math.ceil(n_features / SEGMENTS) * SEGMENTS
        self.pad = self.padded - n_features
        self.embed = nn.Linear(self.padded // SEGMENTS, D_MODEL)
        self.register_buffer("positions", _sinusoidal(SEGMENTS, D_MODEL), persistent=False)
        layer = nn.TransformerEncoderLayer(D_MODEL, HEADS, FFN, batch_first=True)
        self.encoder = nn.TransformerEncoder(layer, BLOCKS, enable_nested_tensor=False)
        self.out = nn.Linear(D_MODEL, n_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.pad:
            x = nn.functional.pad(x, (0, self.pad))
        tokens = self.embed(x.view(len(x), SEGMENTS, -1)) + self.positions
        return self.out(self.encoder(tokens).mean(dim=1))


def _sinusoidal(length: int, dim: int) -> torch.Tensor:
    position = torch.arange(length).unsqueeze(1)
    freq = torch.exp(torch.arange(0, dim, 2) * (-math.log(10000.0) / dim))
    table = torch.zeros(length, dim)
    table[:, 0::2] = torch.sin(position * freq)
    table[:, 1::2] = torch.cos(position * freq)
    return table


ARCHITECTURES = {"lstm": LSTMNet, "transformer": TransformerNet}

# Table 4: 0.001 for LSTM, 0.0005 for Transformer
LEARNING_RATES = {"lstm": 1e-3, "transformer": 5e-4}


def build(name: str, n_features: int, n_classes: int, seed: int) -> nn.Module:
    """Random initialisation at round 0, identical for every client given the seed."""
    torch.manual_seed(seed)
    return ARCHITECTURES[name](n_features, n_classes)


def get_params(model: nn.Module) -> np.ndarray:
    return torch.cat([p.detach().reshape(-1) for p in model.parameters()]).cpu().numpy().copy()


def set_params(model: nn.Module, flat: np.ndarray) -> None:
    """copy_ moves the values to whichever device the model lives on."""
    offset = 0
    with torch.no_grad():
        for p in model.parameters():
            n = p.numel()
            p.copy_(torch.from_numpy(flat[offset:offset + n]).view_as(p))
            offset += n


def hash_params(flat: np.ndarray) -> str:
    """sha256 of the float32 bytes: what a node commits to on the ledger."""
    return hashlib.sha256(np.ascontiguousarray(flat, dtype=np.float32).tobytes()).hexdigest()


def size_bytes(flat: np.ndarray) -> int:
    return flat.size * 4
