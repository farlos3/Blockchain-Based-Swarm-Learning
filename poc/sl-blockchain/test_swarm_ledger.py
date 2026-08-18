"""เทสต์ของ blockchain + swarm ledger

รันได้ 2 แบบ:
    python test_swarm_ledger.py     (ไม่ต้องลง pytest)
    pytest test_swarm_ledger.py
"""

from __future__ import annotations

import numpy as np

from blockchain import GENESIS_PREV_HASH, Blockchain, ChainError
from swarm_ledger import LedgerError, SwarmLedger, elect_leader, hash_params

NODES = ["A", "B", "C", "D", "E"]


def params(seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    return rng.normal(size=(1, 10)), rng.normal(size=(1,))


def make_ledger(difficulty: int = 0) -> SwarmLedger:
    return SwarmLedger(NODES, difficulty=difficulty)


def commit_round(ledger: SwarmLedger, round_num: int, accuracy: float = 0.8):
    for i, node in enumerate(NODES):
        ledger.submit_update(round_num, node, *params(round_num * 100 + i), n_samples=100 + i)
    coef, intercept = params(round_num)
    leader = elect_leader(round_num, ledger.participants)
    block = ledger.record_aggregation(round_num, leader, coef, intercept, accuracy)
    return block, coef, intercept


# ---------- blockchain ----------

def test_genesis_is_fixed_and_alone():
    chain = Blockchain()
    assert len(chain) == 1 and chain.height == 0
    assert chain.blocks[0].prev_hash == GENESIS_PREV_HASH
    assert chain.blocks[0].compute_hash() == Blockchain().blocks[0].compute_hash()


def test_blocks_link_and_validate():
    chain = Blockchain()
    first = chain.add_block([{"type": "t", "v": 1}])
    second = chain.add_block([{"type": "t", "v": 2}])
    assert first.prev_hash == chain.blocks[0].compute_hash()
    assert second.prev_hash == first.compute_hash()
    assert chain.height == 2
    chain.validate()


def test_empty_block_rejected():
    try:
        Blockchain().add_block([])
    except ValueError:
        return
    raise AssertionError("บล็อกว่างควรถูกปฏิเสธ")


def test_tampering_breaks_the_link():
    chain = Blockchain()
    chain.add_block([{"type": "t", "v": 1}])
    chain.add_block([{"type": "t", "v": 2}])
    chain.blocks[1].transactions[0]["v"] = 999  # แก้ประวัติกลางสาย
    try:
        chain.validate()
    except ChainError as exc:
        assert "block 2" in str(exc)  # บล็อกถัดไปชี้ prev_hash ไม่ตรงแล้ว
        return
    raise AssertionError("การแก้ธุรกรรมย้อนหลังควรถูกจับได้")


def test_tampering_last_block_caught_after_reload(tmp_path=None):
    import tempfile
    from pathlib import Path

    chain = Blockchain()
    chain.add_block([{"type": "t", "v": 1}])
    target = Path(tmp_path or tempfile.mkdtemp()) / "chain.json"
    chain.save(target)

    reloaded = Blockchain.load(target)
    reloaded.validate()
    reloaded.blocks[-1].transactions[0]["v"] = 999  # แก้บล็อกท้ายสุด ไม่มีบล็อกถัดไปให้ขัด
    try:
        reloaded.validate()
    except ChainError as exc:
        assert "ถูกแก้" in str(exc)  # จับได้จาก hash ที่บันทึกไว้ในไฟล์
        return
    raise AssertionError("การแก้บล็อกท้ายสุดควรถูกจับได้จาก hash ที่บันทึกไว้")


def test_proof_of_work_meets_difficulty():
    chain = Blockchain(difficulty=2)
    block = chain.add_block([{"type": "t", "v": 1}])
    assert block.compute_hash().startswith("00")
    chain.validate()


def test_save_load_round_trip():
    import tempfile
    from pathlib import Path

    ledger = make_ledger()
    commit_round(ledger, 1)
    target = Path(tempfile.mkdtemp()) / "chain.json"
    ledger.chain.save(target)

    reloaded = Blockchain.load(target)
    reloaded.validate()
    assert reloaded.to_dict() == ledger.chain.to_dict()


# ---------- swarm ledger ----------

def test_one_round_is_one_block():
    ledger = make_ledger()
    block, _, _ = commit_round(ledger, 1)
    assert ledger.chain.height == 1
    assert len(block.transactions) == len(NODES) + 1  # update ทุกโหนด + aggregation
    assert len(ledger.get_round_updates(1)) == len(NODES)
    assert ledger.get_aggregation(1)["participant_count"] == len(NODES)


def test_non_member_rejected():
    ledger = make_ledger()
    try:
        ledger.submit_update(1, "Z", *params(1), n_samples=10)
    except LedgerError:
        return
    raise AssertionError("โหนดนอก swarm ควรถูกปฏิเสธ")


def test_duplicate_update_rejected():
    ledger = make_ledger()
    ledger.submit_update(1, "A", *params(1), n_samples=10)
    try:
        ledger.submit_update(1, "A", *params(2), n_samples=10)
    except LedgerError:
        return
    raise AssertionError("ส่ง update ซ้ำในรอบเดิมควรถูกปฏิเสธ")


def test_wrong_leader_rejected():
    ledger = make_ledger()
    ledger.submit_update(1, "A", *params(1), n_samples=10)
    impostor = next(n for n in NODES if n != elect_leader(1, NODES))
    try:
        ledger.record_aggregation(1, impostor, *params(3))
    except LedgerError as exc:
        assert elect_leader(1, NODES) in str(exc)
        return
    raise AssertionError("คนที่ไม่ใช่ leader ของรอบนั้นควรรวมพารามิเตอร์ไม่ได้")


def test_aggregation_without_updates_rejected():
    ledger = make_ledger()
    try:
        ledger.record_aggregation(1, elect_leader(1, NODES), *params(1))
    except LedgerError:
        return
    raise AssertionError("ปิดรอบที่ไม่มี update ควรถูกปฏิเสธ")


def test_closed_round_is_final():
    ledger = make_ledger()
    commit_round(ledger, 1)
    leader = elect_leader(1, NODES)
    for action in (
        lambda: ledger.submit_update(1, "A", *params(9), n_samples=10),
        lambda: ledger.record_aggregation(1, leader, *params(9)),
    ):
        try:
            action()
        except LedgerError:
            continue
        raise AssertionError("รอบที่ปิดแล้วต้องแก้ไม่ได้")


def test_verify_round_detects_changed_params():
    ledger = make_ledger()
    _, coef, intercept = commit_round(ledger, 1)
    assert ledger.verify_round(1, coef, intercept) is True
    assert ledger.verify_round(1, coef + 1e-12, intercept) is False


def test_leader_rotates_across_rounds():
    ledger = make_ledger()
    for round_num in range(1, 11):
        commit_round(ledger, round_num)
    counts = ledger.leader_counts()
    assert sum(counts.values()) == 10
    assert len([n for n, c in counts.items() if c > 0]) > 1  # ไม่ใช่โหนดเดียวยึดตลอด
    ledger.chain.validate()


def test_hash_params_is_stable_and_sensitive():
    coef, intercept = params(1)
    assert hash_params(coef, intercept) == hash_params(coef.copy(), intercept.copy())
    assert hash_params(coef, intercept) != hash_params(coef, intercept + 1e-12)
    # coef/intercept สลับกันต้องไม่ได้ hash เดียวกัน
    flat = np.ones((1, 3))
    assert hash_params(flat, np.ones((1,))) != hash_params(np.ones((1,)), flat)


def test_ledger_growth_is_reported():
    ledger = make_ledger()
    before = ledger.ledger_bytes()
    commit_round(ledger, 1)
    assert ledger.ledger_bytes() > before


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
    print(f"\n{len(tests) - failed}/{len(tests)} ผ่าน")
    raise SystemExit(1 if failed else 0)
