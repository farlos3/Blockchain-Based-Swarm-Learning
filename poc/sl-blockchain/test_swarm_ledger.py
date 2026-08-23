"""Tests for the blockchain + Proof of Authority + swarm ledger

Two ways to run:
    python test_swarm_ledger.py     (no pytest needed)
    pytest test_swarm_ledger.py
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np

from blockchain import GENESIS_PREV_HASH, Block, Blockchain, ChainError
from consensus import AuthoritySet, NodeKey, ProofOfAuthority, ProofOfWork, elect_leader
from swarm_ledger import (
    LedgerError,
    SwarmLedger,
    audit_chain,
    hash_params,
    sign_payload,
    unsigned_view,
)

NODES = ["A", "B", "C", "D", "E"]


def params(seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    return rng.normal(size=(1, 10)), rng.normal(size=(1,))


def make_ledger() -> SwarmLedger:
    return SwarmLedger.bootstrap(NODES, seed="test")


def commit_round(ledger: SwarmLedger, round_num: int, accuracy: float = 0.8):
    for i, node in enumerate(ledger.participants):
        ledger.submit_update(round_num, node, *params(round_num * 100 + i), n_samples=100 + i)
    coef, intercept = params(round_num)
    leader = elect_leader(round_num, ledger.participants)
    return ledger.record_aggregation(round_num, leader, coef, intercept, accuracy), coef, intercept


def tmp_file(name: str = "chain.json") -> Path:
    return Path(tempfile.mkdtemp()) / name


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
    raise AssertionError("an empty block should be rejected")


def test_tampering_breaks_the_link():
    chain = Blockchain()
    chain.add_block([{"type": "t", "v": 1}])
    chain.add_block([{"type": "t", "v": 2}])
    chain.blocks[1].transactions[0]["v"] = 999  # rewrite history mid-chain
    try:
        chain.validate()
    except ChainError as exc:
        assert "block 2" in str(exc)  # the next block's prev_hash no longer matches
        return
    raise AssertionError("editing a past transaction should be caught")


def test_tampering_last_block_caught_after_reload():
    chain = Blockchain()
    chain.add_block([{"type": "t", "v": 1}])
    target = tmp_file()
    chain.save(target)

    reloaded = Blockchain.load(target)
    reloaded.validate()
    reloaded.blocks[-1].transactions[0]["v"] = 999  # edit the last block, nothing after it to contradict
    try:
        reloaded.validate()
    except ChainError as exc:
        assert "was modified" in str(exc)  # caught by the hash stored in the file
        return
    raise AssertionError("editing the last block should be caught by the stored hash")


def test_proof_of_work_still_available_for_comparison():
    chain = Blockchain(consensus=ProofOfWork(difficulty=2))
    block = chain.add_block([{"type": "t", "v": 1}])
    assert block.compute_hash().startswith("00")
    chain.validate()


# ---------- proof of authority ----------

def test_block_is_sealed_by_the_round_leader():
    ledger = make_ledger()
    block, _, _ = commit_round(ledger, 1)
    assert block.sealer == elect_leader(1, ledger.participants)
    assert block.seal  # a real signature is present
    ledger.chain.validate()


def test_seal_by_member_out_of_turn_rejected():
    ledger = make_ledger()
    leader = elect_leader(1, ledger.participants)
    usurper = next(n for n in ledger.participants if n != leader)
    agg = {"type": "aggregation", "round": 1, "aggregator": usurper,
           "aggregated_hash": "0" * 64, "participant_count": 1, "total_samples": 1,
           "accuracy": None, "timestamp": 0.0}
    agg["signature"] = sign_payload(ledger.keys[usurper], unsigned_view(agg))
    try:
        ledger.chain.add_block([agg], sealer=ledger.keys[usurper])
    except ChainError as exc:
        assert leader in str(exc)
        assert ledger.chain.height == 0  # the block must not join the chain
        return
    raise AssertionError("a member who is not on duty must not be able to seal")


def test_seal_by_outsider_rejected():
    ledger = make_ledger()
    outsider = NodeKey.generate("Z", seed="attacker")
    try:
        ledger.chain.add_block([{"type": "t", "v": 1}], sealer=outsider)
    except ChainError as exc:
        assert "authority set" in str(exc)
        return
    raise AssertionError("someone outside the authority set must not be able to seal")


def test_unsigned_block_rejected():
    ledger = make_ledger()
    try:
        ledger.chain.add_block([{"type": "t", "v": 1}])  # no sealer given
    except ChainError:
        return
    raise AssertionError("PoA must not accept a block without an identifiable sealer")


def test_recomputed_hash_still_fails_the_seal():
    """An attacker smart enough to recompute the hash still cannot forge the leader's signature"""
    ledger = make_ledger()
    commit_round(ledger, 1)
    target = tmp_file()
    ledger.chain.save(target)

    raw = json.loads(target.read_text(encoding="utf-8"))
    victim = raw["blocks"][-1]
    victim["transactions"][0]["n_samples"] = 9999
    victim["hash"] = Block.from_dict({**victim, "hash": None}).compute_hash()

    try:
        Blockchain.from_dict(raw).validate()
    except ChainError as exc:
        assert "signature" in str(exc)
        return
    raise AssertionError("editing content and recomputing the hash must still fail at the signature")


def test_authority_set_only_holds_public_keys():
    ledger = make_ledger()
    exported = ledger.chain.to_dict()["consensus"]["authorities"]
    assert set(exported) == set(NODES)
    assert all(len(pub) == 64 for pub in exported.values())  # ed25519 public key = 32 bytes


def test_node_keys_are_deterministic_with_seed():
    assert NodeKey.generate("A", seed="s").public_hex() == NodeKey.generate("A", seed="s").public_hex()
    assert NodeKey.generate("A", seed="s").public_hex() != NodeKey.generate("B", seed="s").public_hex()


def test_authority_set_rejects_bad_signature():
    authorities = AuthoritySet.from_keys([NodeKey.generate("A", seed="s")])
    other = NodeKey.generate("A", seed="different")
    assert authorities.verify("A", "msg", other.sign("msg")) is False
    assert authorities.verify("A", "msg", "not-hex") is False


# ---------- swarm ledger ----------

def test_one_round_is_one_block():
    ledger = make_ledger()
    block, _, _ = commit_round(ledger, 1)
    assert ledger.chain.height == 1
    assert len(block.transactions) == len(NODES) + 1  # one update per node + the aggregation
    assert len(ledger.get_round_updates(1)) == len(NODES)
    assert ledger.get_aggregation(1)["participant_count"] == len(NODES)


def test_every_transaction_is_signed():
    ledger = make_ledger()
    commit_round(ledger, 1)
    for tx in ledger.chain.transactions():
        assert tx.get("signature"), tx


def test_forged_signature_rejected():
    ledger = make_ledger()
    outsider = NodeKey.generate("Z", seed="attacker")
    forged = {"type": "model_update", "round": 1, "node_id": "A", "weight_hash": "0" * 64,
              "size_bytes": 88, "n_samples": 99999, "timestamp": 0.0}
    forged["signature"] = sign_payload(outsider, unsigned_view(forged))
    try:
        ledger.submit_signed_update(forged)
    except LedgerError as exc:
        assert "signature" in str(exc)
        return
    raise AssertionError("a transaction claiming someone else's identity must be rejected")


def test_non_member_rejected():
    ledger = make_ledger()
    outsider = NodeKey.generate("Z", seed="attacker")
    try:
        ledger.submit_update(1, "Z", *params(1), n_samples=10, key=outsider)
    except LedgerError:
        return
    raise AssertionError("a node outside the authority set should be rejected")


def test_duplicate_update_rejected():
    ledger = make_ledger()
    ledger.submit_update(1, "A", *params(1), n_samples=10)
    try:
        ledger.submit_update(1, "A", *params(2), n_samples=10)
    except LedgerError:
        return
    raise AssertionError("a second update in the same round should be rejected")


def test_wrong_leader_rejected():
    ledger = make_ledger()
    ledger.submit_update(1, "A", *params(1), n_samples=10)
    impostor = next(n for n in NODES if n != elect_leader(1, NODES))
    try:
        ledger.record_aggregation(1, impostor, *params(3))
    except LedgerError as exc:
        assert elect_leader(1, NODES) in str(exc)
        return
    raise AssertionError("a node that is not the round's leader must not be able to aggregate")


def test_aggregation_without_updates_rejected():
    ledger = make_ledger()
    try:
        ledger.record_aggregation(1, elect_leader(1, NODES), *params(1))
    except LedgerError:
        return
    raise AssertionError("closing a round with no updates should be rejected")


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
        raise AssertionError("a closed round must not be modifiable")


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
    assert len([n for n, c in counts.items() if c > 0]) > 1  # not one node holding the role forever
    ledger.chain.validate()


def test_audit_from_file_only():
    ledger = make_ledger()
    commit_round(ledger, 1)
    commit_round(ledger, 2)
    target = tmp_file()
    ledger.chain.save(target)

    report = audit_chain(target)  # holding only the file is enough for a full check
    assert report["consensus"] == "poa"
    assert report["blocks"] == 2
    assert report["transactions_verified"] == 2 * (len(NODES) + 1)
    assert report["authorities"] == NODES


def test_save_load_round_trip():
    ledger = make_ledger()
    commit_round(ledger, 1)
    target = tmp_file()
    ledger.chain.save(target)

    reloaded = Blockchain.load(target)
    reloaded.validate()
    assert reloaded.to_dict() == ledger.chain.to_dict()


def test_hash_params_is_stable_and_sensitive():
    coef, intercept = params(1)
    assert hash_params(coef, intercept) == hash_params(coef.copy(), intercept.copy())
    assert hash_params(coef, intercept) != hash_params(coef, intercept + 1e-12)
    # swapped coef/intercept must not produce the same hash
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
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
