"""Tests for what the FL vs SL comparison rests on: the merge arithmetic, the Fig. 3
partition, and a partition that does not change between processes.

Two ways to run:
    python test_centric.py     (no pytest needed)
    pytest test_centric.py

No Fabric network is needed; the data tests skip a dataset that is not downloaded.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import numpy as np

import data
from federation import Update, aggregate, local_steps, Hyper

HERE = Path(__file__).resolve().parent


def update(client: int, params: list[float], n: int, steps: int) -> Update:
    return Update(client, np.array(params, dtype=np.float32), n, steps, 0.0)


def test_fedavg_weights_by_samples():
    merged = aggregate("fedavg", np.zeros(2, np.float32),
                       [update(0, [1, 1], 100, 5), update(1, [4, 4], 300, 15)])
    assert np.allclose(merged, [3.25, 3.25])


def test_fedprox_merges_like_fedavg():
    ups = [update(0, [1, 2], 10, 5), update(1, [3, 0], 30, 15)]
    start = np.zeros(2, np.float32)
    assert np.array_equal(aggregate("fedprox", start, ups), aggregate("fedavg", start, ups))


def test_fednova_equals_fedavg_when_work_is_equal():
    # the paper: FedNova and FedAvg coincide if every client does the same amount of work
    start = np.array([1.0, -1.0], np.float32)
    ups = [update(0, [2, 0], 50, 10), update(1, [0, 2], 50, 10)]
    assert np.allclose(aggregate("fednova", start, ups), aggregate("fedavg", start, ups))


def test_fednova_normalises_unequal_work():
    # client 1 took three times the steps for the same distance per step: FedNova moves by
    # tau_eff times the average per-step direction, not by the raw sample-weighted delta
    start = np.zeros(1, np.float32)
    ups = [update(0, [1.0], 100, 10), update(1, [3.0], 300, 30)]
    tau_eff = 0.25 * 10 + 0.75 * 30
    expected = tau_eff * (0.25 * 1.0 / 10 + 0.75 * 3.0 / 30)
    assert np.allclose(aggregate("fednova", start, ups), [expected])


def test_merge_ignores_arrival_order():
    # the leader may receive updates in any order; it must produce the server's bits
    start = np.zeros(3, np.float32)
    ups = [update(k, list(np.random.default_rng(k).normal(size=3)), 10 + k, 5 + k) for k in range(4)]
    for algorithm in ("fedavg", "fednova"):
        assert aggregate(algorithm, start, ups).tobytes() == aggregate(algorithm, start, ups[::-1]).tobytes()


def test_local_steps_match_eq3():
    assert local_steps(1000, Hyper()) == 5 * 8          # E * ceil(1000 / 128)


def test_allocate_keeps_fig3_proportions():
    counts, used = data.allocate([2.0, 1.0], [0.5, 0.5], [("A",), ("A", "B")],
                                 {"A": 0.6, "B": 0.2}, {data.BENIGN: 10_000, "A": 3_000, "B": 1_000}, 6_000)
    assert used == 6_000
    first, second = (sum(c.values()) for c in counts)
    assert abs(first / second - 2.0) < 0.01                  # Fig. 3 size ratio
    assert all(abs(c[data.BENIGN] / sum(c.values()) - 0.5) < 0.01 for c in counts)
    assert "B" not in counts[0]                               # coverage: client 0 has no B
    assert abs(counts[1]["A"] / counts[1]["B"] - 3.0) < 0.01  # the release's A:B, not the pool's


def test_allocate_shrinks_instead_of_overdrawing():
    counts, used = data.allocate([1.0], [0.5], [("A",)], {"A": 0.5},
                                 {data.BENIGN: 100, "A": 1_000}, 10_000)
    assert used == 200 and counts[0][data.BENIGN] == 100


def test_release_share_reweights_a_capped_pool():
    # a pool that kept 2 of 8 rows of family F and both rows of G: F's subclasses keep
    # their mix inside F, and the families weigh as the release does
    family = np.array(["F", "F", "G", "G"])
    pool = data.Pool(np.zeros((4, 1)), ["x"], np.zeros((4, 1)), family,
                     np.array(["a", "b", "c", "c"]), {"F": 8, "G": 2})
    assert pool.release_share(pool.common) == {"a": 0.4, "b": 0.4, "c": 0.2}


def _ready(name: str) -> str | None:
    """The source a data test can use without first sampling a full release (minutes)."""
    if name in data.available("subset"):
        return "subset"
    if (data.POOLS / f"{name}-{data.FAMILY_CAP}-per-family.parquet").exists():
        return "full"
    return None


def test_partition_follows_fig3_coverage():
    # a client never holds a class Fig. 3 does not give it; under a full release's real
    # proportions it can lack the rarest of the ones it is given
    for spec in (data.EDGE, data.CIC):
        source = _ready(spec.name)
        if source is None:
            continue
        fed = data.build(spec.name, 20_000, source=source)
        for client, cspec in zip(fed.clients, spec.clients):
            held = {fed.classes[k] for k in np.unique(np.concatenate([client.y_train, client.y_test]))}
            assert data.BENIGN in held and held <= {data.BENIGN, *cspec.families}, (cspec.key, held)


def test_partition_is_identical_across_processes():
    # string hashing is salted per process; a partition that depended on it would differ
    source = _ready("edge")
    if source is None:
        return
    probe = (f"import hashlib, data; f = data.build('edge', 5000, source='{source}'); "
             "print(hashlib.sha256(b''.join(c.y_train.tobytes() for c in f.clients)).hexdigest())")
    digests = {subprocess.run([sys.executable, "-c", probe], cwd=HERE, capture_output=True,
                              text=True, check=True).stdout.strip() for _ in range(2)}
    assert len(digests) == 1, digests


if __name__ == "__main__":
    tests = [(name, fn) for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)]
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
