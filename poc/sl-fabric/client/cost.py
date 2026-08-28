"""What one training run actually cost, in units you can multiply.

A live gauge answers "is it busy right now". Sizing a deployment needs the other
question: how much CPU, disk and wall time does *one round* consume, so that a plan for
50 rounds across 20 organizations can be costed before anyone builds it.

Everything here is a difference between two snapshots taken around a run, divided by the
work done in between. Differences matter because the machine is never idle: the peers
were already burning CPU keeping gossip alive, and the disk already held a ledger.

Two properties of this system make the arithmetic simple, and both are measured rather
than assumed:

  the on-chain cost per round does not depend on the model, because only a hash is
  recorded — so bytes and CPU scale with the number of nodes, not parameter count

  the off-chain cost does depend on the model, because the weights themselves have to
  reach the leader — so that term scales with parameters times nodes
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Snapshot:
    """One reading of the counters that only ever go up."""

    cpu_seconds: dict[str, float] = field(default_factory=dict)  # per node name
    blocks: float = 0.0
    transactions: float = 0.0
    ledger_bytes: int = 0
    resident_mb: dict[str, float] = field(default_factory=dict)

    @classmethod
    def take(cls, resources: dict[str, Any], host: dict[str, Any] | None = None,
             channel: str | None = None) -> Snapshot:
        """Read the counters. `channel` narrows blocks and transactions to one chain.

        Each model type trains on its own chain, so counting blocks across all five would
        charge one model for another's rounds. Without a channel the totals are used,
        which is only meaningful for a network-wide figure.
        """
        nodes = [n for n in resources.get("nodes", []) if n.get("reachable")]
        peers = [n for n in nodes if n.get("role") == "peer"]
        volumes = (host or {}).get("ledger_volumes", [])

        def per_peer(field: str, total_field: str) -> float:
            # every peer holds the same chain, so the highest reading is the chain's
            if channel is None:
                return max((float(n.get(total_field, 0.0)) for n in peers), default=0.0)
            return max((float((n.get(field) or {}).get(channel, 0.0)) for n in peers), default=0.0)

        return cls(
            cpu_seconds={n["name"]: n["cpu_seconds"] for n in nodes},
            blocks=per_peer("blocks", "total_blocks"),
            transactions=per_peer("ledger_transactions", "total_transactions"),
            ledger_bytes=sum(v["size_bytes"] for v in volumes),
            resident_mb={n["name"]: n["resident_mb"] for n in nodes},
        )


def measure(before: Snapshot, after: Snapshot, rounds: int, nodes: int,
            seconds: float, off_chain_bytes_per_round: int) -> dict[str, Any]:
    """Turn two snapshots into per-round and per-transaction costs.

    rounds is what the run actually completed, so a cancelled run still reports honest
    per-unit numbers rather than dividing by what was planned.
    """
    if rounds <= 0:
        return {}

    cpu_delta = {
        name: round(after.cpu_seconds.get(name, 0.0) - value, 2)
        for name, value in before.cpu_seconds.items()
    }
    peer_cpu = sum(v for name, v in cpu_delta.items() if name != "orderer")
    orderer_cpu = cpu_delta.get("orderer", 0.0)
    blocks = max(after.blocks - before.blocks, 0.0)
    transactions = max(after.transactions - before.transactions, 0.0)
    ledger_bytes = max(after.ledger_bytes - before.ledger_bytes, 0)

    return {
        "rounds": rounds,
        "nodes": nodes,
        "wall_seconds": round(seconds, 1),
        "blocks": blocks,
        "transactions": transactions,
        "per_round": {
            "wall_seconds": round(seconds / rounds, 2),
            "blocks": round(blocks / rounds, 2),
            "transactions": round(transactions / rounds, 2),
            "peer_cpu_seconds": round(peer_cpu / rounds, 2),
            "orderer_cpu_seconds": round(orderer_cpu / rounds, 2),
            "ledger_bytes": int(ledger_bytes / rounds),
            # what the nodes ship to each other outside the ledger, which the chain
            # never sees but a real deployment still has to pay for
            "off_chain_bytes": off_chain_bytes_per_round,
        },
        "per_transaction": {
            "peer_cpu_seconds": round(peer_cpu / transactions, 3) if transactions else None,
            "ledger_bytes": int(ledger_bytes / transactions) if transactions else None,
        },
        "peak_resident_mb": {
            name: round(max(value, before.resident_mb.get(name, 0.0)), 1)
            for name, value in after.resident_mb.items()
        },
    }


def project(per_round: dict[str, Any], rounds: int, nodes: int, measured_nodes: int) -> dict[str, Any]:
    """Extrapolate a measured round to a different swarm size and length.

    The split matters more than the precision. Per-round ledger work grows with the
    number of nodes, because each one submits a transaction; wall time does not, because
    those transactions are submitted concurrently and batched into the same block. Off-chain
    traffic grows with nodes as well, and with the model, which is why it dominates first.

    This is a linear model fitted to one point. It is honest for "roughly how much iron",
    not for capacity planning at ten times the size, where batch limits and endorsement
    fan-out start to bend the curve.
    """
    if not per_round or measured_nodes <= 0:
        return {}
    scale = nodes / measured_nodes

    return {
        "rounds": rounds,
        "nodes": nodes,
        "wall_hours": round(per_round["wall_seconds"] * rounds / 3600, 2),
        "peer_cpu_hours": round(per_round["peer_cpu_seconds"] * scale * rounds / 3600, 2),
        "orderer_cpu_hours": round(per_round["orderer_cpu_seconds"] * rounds / 3600, 2),
        "ledger_mb": round(per_round["ledger_bytes"] * scale * rounds / 1024 / 1024, 1),
        "off_chain_gb": round(per_round["off_chain_bytes"] * scale * rounds / 1024**3, 2),
    }
