"""Proof of Authority ledger demo: 5 nodes, 3 rounds

  python demo.py

The parameters here are random numbers, not real training, because the point is to
watch the chain mechanics. Wiring this to a real model is covered in the README under
"Using it from the notebook".
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from blockchain import Block, Blockchain, ChainError
from consensus import NodeKey, elect_leader, sign_payload
from swarm_ledger import SwarmLedger, audit_chain, unsigned_view

NODES = ["A", "B", "C", "D", "E"]
N_SAMPLES = {"A": 240, "B": 160, "C": 110, "D": 60, "E": 110}
ROUNDS = 3
CHAIN_FILE = Path(__file__).with_name("chain.json")


def rule(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def fake_params(rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Stands in for parameters from real training (coef 1x10 + one intercept, same as SGDClassifier)"""
    return rng.normal(0, 1, size=(1, 10)), rng.normal(0, 1, size=(1,))


def main() -> None:
    rng = np.random.default_rng(7)
    ledger = SwarmLedger.bootstrap(NODES, seed="demo")

    rule(f"authority set - {len(NODES)} nodes, consensus = {ledger.chain.consensus.name}")
    for node, public_key in ledger.authorities.to_dict().items():
        print(f"  Node {node}  public key = {public_key[:32]}...")
    print("\n  private keys stay with their owner; the chain holds public keys only, for anyone to verify")

    global_params: dict[int, tuple[np.ndarray, np.ndarray]] = {}

    for round_num in range(1, ROUNDS + 1):
        leader = elect_leader(round_num, NODES)
        rule(f"round {round_num} - leader = Node {leader}")

        updates = []
        for node in NODES:
            coef, intercept = fake_params(rng)
            tx = ledger.submit_update(round_num, node, coef, intercept, N_SAMPLES[node])
            updates.append((coef, intercept, N_SAMPLES[node]))
            print(f"  submit_update  node {node}  n={N_SAMPLES[node]:3d}  "
                  f"weight_hash={tx['weight_hash'][:12]}...  sig={tx['signature'][:12]}...")

        # the leader runs FedAvg weighted by sample count (computed off-chain)
        total = sum(n for _, _, n in updates)
        g_coef = np.sum([c * n for c, _, n in updates], axis=0) / total
        g_intercept = np.sum([b * n for _, b, n in updates], axis=0) / total
        global_params[round_num] = (g_coef, g_intercept)

        accuracy = 0.80 + 0.02 * round_num  # pretend this came from a central test set
        block = ledger.record_aggregation(round_num, leader, g_coef, g_intercept, accuracy)
        print(f"  record_aggregation -> block #{block.index}  tx={len(block.transactions)}  "
              f"sealed by {block.sealer}  seal={block.seal[:12]}...")

    # ---------- verification ----------
    rule("verifying the chain")
    report = ledger.audit()
    print(f"audit()              : passed {report}")
    print(f"rounds led per node  : {ledger.leader_counts()}")
    print(f"ledger size          : {ledger.ledger_bytes():,} bytes "
          f"(~{ledger.ledger_bytes() // ROUNDS:,} bytes/round)")

    coef, intercept = global_params[2]
    print(f"verify_round(2) genuine  : {ledger.verify_round(2, coef, intercept)}")
    print(f"verify_round(2) modified : {ledger.verify_round(2, coef + 1e-9, intercept)}")

    # ---------- rules the ledger rejects ----------
    rule("rules the ledger rejects (the equivalent of chaincode rejecting a transaction)")
    probe = 9  # an unused round, to fire rule-breaking transactions at
    outsider = NodeKey.generate("Z", seed="attacker")
    probe_leader = elect_leader(probe, NODES)
    not_leader = next(n for n in NODES if n != probe_leader)

    # an intruder forges a transaction claiming to be Node A, signed with its own key
    forged = {
        "type": "model_update", "round": probe, "node_id": "A",
        "weight_hash": "0" * 64, "size_bytes": 88, "n_samples": 99999, "timestamp": 0.0,
    }
    forged["signature"] = sign_payload(outsider, unsigned_view(forged))

    # a legitimate member, but not the one on duty, tries to seal the block itself
    def seal_out_of_turn() -> None:
        agg = {"type": "aggregation", "round": probe, "aggregator": not_leader,
               "aggregated_hash": "0" * 64, "participant_count": 1, "total_samples": 1,
               "accuracy": None, "timestamp": 0.0}
        agg["signature"] = sign_payload(ledger.keys[not_leader], unsigned_view(agg))
        ledger.chain.add_block([agg], sealer=ledger.keys[not_leader])

    checks = [
        ("a node outside the authority set submits an update",
         lambda: ledger.submit_update(probe, "Z", *fake_params(rng), 10, key=outsider)),
        ("a forged signature claiming to be Node A",
         lambda: ledger.submit_signed_update(forged)),
        ("submitting twice in the same round",
         lambda: (ledger.submit_update(probe, "A", *fake_params(rng), 10),
                  ledger.submit_update(probe, "A", *fake_params(rng), 10))),
        ("a non-leader asks to aggregate",
         lambda: ledger.record_aggregation(probe, not_leader, *fake_params(rng))),
        ("a real member seals out of turn", seal_out_of_turn),
        ("closing an already closed round",
         lambda: ledger.record_aggregation(1, elect_leader(1, NODES), *fake_params(rng))),
    ]
    for label, action in checks:
        try:
            action()
            print(f"  [UNEXPECTED] {label}: was not rejected")
        except Exception as exc:
            print(f"  [rejected] {label}\n             -> {exc}")

    # ---------- save, then let an outsider verify it ----------
    rule("save to file, then let someone holding only the file verify it")
    ledger.chain.save(CHAIN_FILE)
    print(f"audit_chain('{CHAIN_FILE.name}') : {audit_chain(CHAIN_FILE)}")
    print("  an outsider trusts no one and verifies from the file alone, since every public key is in it")

    # ---------- two ways of rewriting history ----------
    rule("attempts to rewrite history")
    raw = json.loads(CHAIN_FILE.read_text(encoding="utf-8"))

    # attempt 1: edit a block in the middle (n_samples is the FedAvg weight; larger pulls the global model harder)
    middle = json.loads(json.dumps(raw))
    for tx in middle["blocks"][1]["transactions"]:
        if tx.get("node_id") == "D":
            print(f"  attempt 1: block #1, node D n_samples {tx['n_samples']} -> 9999")
            tx["n_samples"] = 9999
            break
    try:
        Blockchain.from_dict(middle).validate()
        print("  [UNEXPECTED] still validates after the edit")
    except ChainError as exc:
        print(f"  [caught]   {exc}")

    # attempt 2: a smarter attacker — edit the last block and recompute its hash to match
    last = json.loads(json.dumps(raw))
    victim = last["blocks"][-1]
    for tx in victim["transactions"]:
        if tx.get("node_id") == "D":
            tx["n_samples"] = 9999
            break
    victim["hash"] = Block.from_dict({**victim, "hash": None}).compute_hash()
    print(f"  attempt 2: block #{victim['index']} (the last one, no following block to contradict it), "
          f"then recompute its hash to match")
    try:
        Blockchain.from_dict(last).validate()
        print("  [UNEXPECTED] still validates after the edit")
    except ChainError as exc:
        print(f"  [caught]   {exc}")
    print("  <- this is what PoA buys: even with a recomputed hash, the leader's signature cannot be forged")

    print(f"\nchain file: {CHAIN_FILE}")


if __name__ == "__main__":
    main()
