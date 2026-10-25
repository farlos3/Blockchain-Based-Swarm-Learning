"""The three networks of Nguyen-Khanh et al. (2025), Section 3.2 and Fig. 3.

flow        Table 3, LUCID's CNN: Conv2D 64 kernels of 3 x 11 over the 10 x 11 fragment,
            ReLU, global max pooling, one sigmoid unit (2,176 + 65 parameters)
packet      Table 4: Conv1D 74 x 5, Conv1D 50 x 5, global average pooling, Dense 60,
            Dropout, Dense 60, Dropout, one sigmoid unit (25,775 parameters)
multimodal  Fig. 3: both branches without their output unit, their features concatenated
            (64 + 60) and classified by a hidden Dense layer and one sigmoid unit

Layers are initialised as Keras initialises them (Glorot-uniform kernels, zero biases),
the framework the paper's Table 3 and 4 shapes come from. Outputs are logits; the sigmoid
lives in the loss. Weights travel as one flat float32 vector, so merging never needs to
know which network it holds and the ledger can pin a model by hashing its bytes.
"""

from __future__ import annotations

import hashlib

import numpy as np
import torch
from torch import nn

from data import FLOW_FEATURES

DROPOUT = 0.2      # Table 4 has Dropout layers but no rate
FUSION = 64        # Fig. 3's hidden layer after the concatenation; its width is not given


class FlowBranch(nn.Module):
    """Table 3 up to the flattened 64 features."""

    def __init__(self) -> None:
        super().__init__()
        self.conv = nn.Conv2d(1, 64, (3, FLOW_FEATURES))
        self.width = 64

    def forward(self, flow: torch.Tensor) -> torch.Tensor:
        h = torch.relu(self.conv(flow.unsqueeze(1)))       # (N, 64, 8, 1)
        return h.amax(dim=(2, 3))                          # GlobalMaxPooling2D + Flatten


class PacketBranch(nn.Module):
    """Table 4 up to the second Dropout's 60 features."""

    def __init__(self) -> None:
        super().__init__()
        self.conv1 = nn.Conv1d(1, 74, 5)
        self.conv2 = nn.Conv1d(74, 50, 5)
        self.dense1 = nn.Linear(50, 60)
        self.dense2 = nn.Linear(60, 60)
        self.drop = nn.Dropout(DROPOUT)
        self.width = 60

    def forward(self, packet: torch.Tensor) -> torch.Tensor:
        h = torch.relu(self.conv1(packet.unsqueeze(1)))
        h = torch.relu(self.conv2(h)).mean(dim=2)          # GlobalAveragePooling1D
        h = self.drop(torch.relu(self.dense1(h)))
        return self.drop(torch.relu(self.dense2(h)))


class FlowNet(nn.Module):
    def __init__(self, n_features: int) -> None:
        super().__init__()
        self.flow = FlowBranch()
        self.out = nn.Linear(self.flow.width, 1)

    def forward(self, packet: torch.Tensor, flow: torch.Tensor) -> torch.Tensor:
        return self.out(self.flow(flow)).squeeze(1)


class PacketNet(nn.Module):
    def __init__(self, n_features: int) -> None:
        super().__init__()
        self.packet = PacketBranch()
        self.out = nn.Linear(self.packet.width, 1)

    def forward(self, packet: torch.Tensor, flow: torch.Tensor) -> torch.Tensor:
        return self.out(self.packet(packet)).squeeze(1)


class MultimodalNet(nn.Module):
    def __init__(self, n_features: int) -> None:
        super().__init__()
        self.flow = FlowBranch()
        self.packet = PacketBranch()
        self.fuse = nn.Linear(self.flow.width + self.packet.width, FUSION)
        self.out = nn.Linear(FUSION, 1)

    def forward(self, packet: torch.Tensor, flow: torch.Tensor) -> torch.Tensor:
        h = torch.cat([self.flow(flow), self.packet(packet)], dim=1)     # late fusion
        return self.out(torch.relu(self.fuse(h))).squeeze(1)


ARCHITECTURES = {"packet": PacketNet, "flow": FlowNet, "multimodal": MultimodalNet}


def build(name: str, n_features: int, seed: int) -> nn.Module:
    torch.manual_seed(seed)
    net = ARCHITECTURES[name](n_features)
    for m in net.modules():
        if isinstance(m, (nn.Conv1d, nn.Conv2d, nn.Linear)):
            nn.init.xavier_uniform_(m.weight)
            nn.init.zeros_(m.bias)
    return net


def get_params(model: nn.Module) -> np.ndarray:
    return torch.cat([p.detach().reshape(-1) for p in model.parameters()]).cpu().numpy().copy()


def set_params(model: nn.Module, flat: np.ndarray) -> None:
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

