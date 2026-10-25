"""Checks against the paper's own numbers, and the rules the swarm follows.

Two ways to run:
    python test_eai.py     (no pytest needed)
    pytest test_eai.py

No Fabric network and no dataset are needed: the swarm runs on a stand-in ledger.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import torch

import data
import models
import swarm


def count(net: torch.nn.Module) -> int:
    return sum(p.numel() for p in net.parameters())


def test_parameter_counts_match_tables_3_and_4():
    assert count(models.build("packet", 52, 0)) == 25_775          # Table 4's total
    assert count(models.build("flow", 52, 0)) == 2_176 + 65         # Table 3
    multimodal = models.build("multimodal", 52, 0)
    assert count(multimodal) == 25_775 - 61 + 2_176 + (64 + 60) * models.FUSION + models.FUSION + models.FUSION + 1


def test_branch_shapes_match_tables_3_and_4():
    net = models.build("multimodal", 52, 0)
    x = torch.zeros(2, 1, 52)
    assert net.packet.conv1(x).shape == (2, 74, 48)
    assert net.packet.conv2(net.packet.conv1(x)).shape == (2, 50, 44)
    flow = torch.zeros(2, 1, data.FLOW_PACKETS, data.FLOW_FEATURES)
    assert net.flow.conv(flow).shape == (2, 64, 8, 1)


def test_hosts_add_up_to_tables_7_and_9_to_11():
    totals = {"http-icmp": 231_318, "tcp-syn": 100_853, "udp": 242_738, "mqtt-publish": 131_683,
              "mqtt-connect": 274_734}
    for unit in data.UNITS:
        assert sum(data.ATTACK_ROWS[a] for a in unit.attacks) + unit.benign == totals[unit.name]
    assert sum(totals.values()) == 981_326


def _host(n: int) -> data.Host:
    split = data.Split(np.zeros((n, 3), np.float32), np.zeros((n, 10, 11), np.float32),
                       np.zeros(n, np.float32), np.full(n, "x"))
    return data.Host("h", split, split, split)


def test_round_counts_match_the_paper():
    hyper = swarm.Hyper()
    # Table 10 and Table 11 training rows; the paper reports 27 and 18 aggregation rounds
    assert swarm.rounds_needed([_host(n) for n in (187_368, 278_309, 329_198)], hyper) == 27
    assert swarm.rounds_needed([_host(n) for n in (187_368, 81_691, 196_618, 106_663, 222_535)], hyper) == 18


def test_merges():
    points = [np.array([0.0, 0.0], np.float32), np.array([1.0, 2.0], np.float32), np.array([10.0, 100.0], np.float32)]
    w = [1.0, 1.0, 1.0]
    assert np.allclose(swarm.merge("mean", points, w), [11 / 3, 34.0])
    assert np.allclose(swarm.merge("coordmedian", points, w), [1.0, 2.0])
    # the geometric median of three points with one far away stays near the close pair
    geo = swarm.merge("geomedian", points, w)
    assert np.linalg.norm(geo - points[1]) < 1.5
    # four points on a square: the centre
    square = [np.array(p, np.float32) for p in ([0, 0], [0, 2], [2, 0], [2, 2])]
    assert np.allclose(swarm.merge("geomedian", square, [1.0] * 4), [1.0, 1.0], atol=1e-5)


def test_weighted_merges():
    rng = np.random.default_rng(1)
    for k in (3, 4, 5):          # equal weights: the weighted median is the plain median
        stack = rng.normal(size=(k, 50))
        assert np.array_equal(swarm.weighted_median(stack, np.ones(k)), np.median(stack, axis=0))
    points = [np.array([0.0, 0.0], np.float32), np.array([1.0, 2.0], np.float32), np.array([10.0, 100.0], np.float32)]
    heavy = [1.0, 1.0, 10.0]     # the third node holds most of the data
    assert np.allclose(swarm.merge("mean", points, heavy), [101 / 12, 1002 / 12])
    assert np.allclose(swarm.merge("coordmedian", points, heavy), [10.0, 100.0])
    assert np.allclose(swarm.merge("geomedian", points, heavy), [10.0, 100.0], atol=1e-3)


def test_lucid_fragments():
    # two flows (one seen in both directions), a second window opening after 10 s
    us = np.array([0.0, 0.5, 1.0, 11.0, 11.5]) * 1e6
    packets = pd.DataFrame({
        "us": us.astype(np.int64), "src": [1, 2, 3, 1, 1], "dst": [2, 1, 4, 2, 2],
        "sport": [10, 20, 30, 10, 10], "dport": [20, 10, 40, 20, 20], "proto": [6] * 5,
        **{f"f{i}": np.zeros(5) for i in range(data.FLOW_FEATURES)}})
    out = data.fragments(packets)
    assert out["fragment"].tolist() == [0, 0, 1, 2, 2]
    assert out["pos"].tolist() == [0, 1, 0, 0, 1]
    assert np.allclose(out["f0"] * data.TIME_WINDOW, [0.0, 0.5, 0.0, 0.0, 0.5])


def test_lucid_keeps_first_n_packets():
    n = data.FLOW_PACKETS + 3
    packets = pd.DataFrame({"us": np.arange(n, dtype=np.int64) * 1000, "src": [1] * n, "dst": [2] * n,
                            "sport": [1] * n, "dport": [2] * n, "proto": [17] * n,
                            **{f"f{i}": np.ones(n) for i in range(data.FLOW_FEATURES)}})
    out = data.fragments(packets)
    matrix = data.flow_matrices(out, np.array([0]))
    assert matrix.shape == (1, data.FLOW_PACKETS, data.FLOW_FEATURES)
    assert (matrix[0, :, 1] == 1).all()


def test_edge_keys():
    rows = pd.DataFrame({
        "frame.time": [" 2021 11:35:29.350784000 ", "153.177.200.205", "192.168.0.128", "2021 13:04:34.689590000"],
        "ip.src_host": ["192.168.0.170", "192.168.0.128", "244.158.10.197", "0"],
        "ip.dst_host": ["192.168.0.128", "0", "244.158.10.197", "0"],
        "tcp.srcport": ["55992.0", "12953.0", "0.0", "0.0"], "udp.stream": ["0.0", "41.0", "25282.0", "0.0"],
        "Attack_type": ["DDoS_HTTP", "DDoS_UDP", "DDoS_UDP", "Normal"]})
    keys = data.edge_keys(rows)
    assert keys["by"].tolist() == ["time", "udp", "udp-port", "none"]
    assert keys.loc[0, "tod"] == ((11 * 60 + 35) * 60 + 29) * 1_000_000 + 350_784
    assert keys.loc[1, ["sport", "udp_stream"]].tolist() == [12953, 41]
    assert keys.loc[2, "sport"] == 25282


class LocalLedger:
    """Stands in for Fabric: the same calls, the merge done in-process, nothing recorded."""

    def open(self, tag, n_nodes):
        self.contributions, self.members = [], []
        return {"quorum": n_nodes // 2 + 1}           # a majority, as the chaincode requires

    def merge(self, round_num, members, contributions, n_samples, combine):
        self.contributions.append([c.copy() for c in contributions])
        self.members.append(list(members))
        return combine(contributions, n_samples), {"leader": "Org1MSP"}

    def publish(self, val_accuracy, merged):
        return {"ledger_seconds": 0.0, "verified": True}

    def close(self):
        return {}


def _scenario(sizes: list[int]) -> data.Scenario:
    rng = np.random.default_rng(0)
    hosts = []
    for n in sizes:
        y = rng.integers(0, 2, n).astype(np.float32)
        packet = (rng.normal(size=(n, 12)) + y[:, None]).astype(np.float32)
        split = data.Split(packet, rng.random((n, 10, 11), dtype=np.float32), y, np.where(y > 0, "a", "b"))
        hosts.append(data.Host(f"h{n}", split, split, split))
    return data.Scenario(9, hosts, [f"c{i}" for i in range(12)])


def test_finished_node_keeps_offering_its_snapshot():
    hyper = swarm.Hyper(epochs=2, batch=16, sync_frequency=4)
    scenario = _scenario([64, 200])        # 8 and 26 batches: node 0 stops after round 2
    ledger = LocalLedger()
    record = swarm.swarm(scenario, "packet", "mean", ledger, hyper, device="cpu", log=lambda _: None)
    assert record["rounds"] == 1 + 7 == len(ledger.contributions)
    snapshot = ledger.contributions[2][0]
    for later in ledger.contributions[3:]:
        assert np.array_equal(later[0], snapshot)
    assert all(h["adopted"] == [1] for h in record["history"][3:])


def test_inactive_node_stops_and_rounds_need_a_quorum():
    hyper = swarm.Hyper(epochs=2, batch=16, sync_frequency=4)
    scenario = _scenario([64, 64, 200])    # 8, 8 and 26 batches: nodes 0 and 1 stop after round 2
    ledger = LocalLedger()
    record = swarm.swarm(scenario, "packet", "mean", ledger, hyper, device="cpu", log=lambda _: None,
                         on_train_end="inactive")
    # rounds 3-7 have one contributor, below the quorum of 2: nothing is merged or recorded
    assert ledger.members == [[0, 1, 2]] * 3
    assert record["merged_rounds"] == 3 and record["rounds"] == 8
    assert all(h["leader"] is None and h["adopted"] == [] for h in record["history"][3:])
    # the final model is the last node's own
    assert record["final_hash"] == record["history"][-1]["model_hash"]


def test_swarm_learns_with_every_merge():
    hyper = swarm.Hyper(epochs=3, batch=32, sync_frequency=8)
    for method in swarm.MERGES:
        record = swarm.swarm(_scenario([300, 300, 300]), "packet", method, LocalLedger(), hyper,
                             device="cpu", log=lambda _: None)
        assert record["test"]["accuracy"] > 0.8, method


if __name__ == "__main__":
    tests = [(name, fn) for name, fn in dict(globals()).items() if name.startswith("test_") and callable(fn)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as exc:
            failed += 1
            print(f"  FAIL  {name}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
