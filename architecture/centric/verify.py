"""Evidence that SL can replace FL, checked against the Fabric network and the result files.

    python verify.py                        # all three, into results/full-500k/verify.json
    python verify.py --only audit rules     # some of them; the rest of the file is kept

independent  FL and SL trained separately, each from scratch on the same rows, must reach
             the same global model in every round. The grid trains once per round and
             hands the same updates to both, so this is what shows their equality is not
             an artefact of sharing the updates.
audit        every SL round in the result files is on the ledger: the same global-model
             hash, closed by the leader the election rule picks (recomputed here, not read
             back), with an update from every client carrying that client's sample count.
rules        attempts that break the swarm's rules, on every channel. Each must be refused,
             and the ledger must be the same afterwards.

report.py turns verify.json into the report's "หลักฐานว่า SL แทน FL ได้" section, and
web.py runs the same three checks from a page.
"""

from __future__ import annotations

import os

# cuBLAS reads this when it starts, so before torch is imported anywhere
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import argparse
import hashlib
import json
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

import architectures
import data
import federation

HERE = Path(__file__).resolve().parent
EXPERIMENT = HERE / "results" / "full-500k"
GATEWAY = os.getenv("SL_GATEWAY_URL", "http://127.0.0.1:8899")
LedgerClient, LedgerError = architectures.ledger.LedgerClient, architectures.ledger.LedgerError

# Every swarm once, every algorithm, both models and so both devices: small, so the whole
# set trains in a few minutes, and on its own chain rounds like any SL run
INDEPENDENT = [
    ("edge", "lstm", "fedavg"), ("edge", "transformer", "fedprox"),
    ("cic", "lstm", "fednova"), ("cic", "transformer", "fedavg"),
    ("tii", "lstm", "fedprox"), ("tii", "transformer", "fednova"),
    ("combined", "lstm", "fedavg"), ("combined", "transformer", "fedprox"),
]
INDEPENDENT_ROWS, INDEPENDENT_ROUNDS = 20_000, 3
FAKE_HASH = "f" * 64


def elected(round_num: int, members: list[str]) -> str:
    """The chaincode's election rule (sl-ledger electLeader), recomputed independently:
    sha256("round-N:member,member,...") mod the number of members."""
    digest = hashlib.sha256(f"round-{round_num}:{','.join(members)}".encode()).hexdigest()
    return members[int(digest, 16) % len(members)]


def device_for(model: str) -> str:
    """As run.py places lanes: the Transformer on the GPU when there is one."""
    import torch

    return "cuda" if model == "transformer" and torch.cuda.is_available() else "cpu"


# ---------- independent ----------

def independent(scenario: str, model: str, algorithm: str, rows: int = INDEPENDENT_ROWS,
                rounds: int = INDEPENDENT_ROUNDS, gateway: str = GATEWAY,
                log: Callable[[str], None] = print) -> dict:
    """Train FL, then SL, each with its own coordinator only, and compare round by round."""
    import torch

    torch.use_deterministic_algorithms(True)
    log(f"loading {scenario}, {rows:,} rows")
    fed = data.build(scenario, rows)
    device = device_for(model)
    log(f"FL on {device}: {rounds} rounds, merged by a central server")
    fl = federation.train(fed, model, algorithm, [architectures.CentralServer()], rounds,
                          log=log, device=device)[0][0]
    swarm = architectures.FabricSwarm(data.dataset_of(scenario), model, gateway)
    log(f"SL on {device}: {rounds} rounds, merged by the elected leader on {swarm.channel}")
    sl = federation.train(fed, model, algorithm, [swarm], rounds, log=log, device=device)[0][0]
    per_round = [{"round": a["round"], "fl": a["global_hash"], "sl": b["global_hash"],
                  "same": a["global_hash"] == b["global_hash"], "chain_round": b["chain_round"]}
                 for a, b in zip(fl["history"], sl["history"])]
    return {
        "scenario": scenario, "model": model, "algorithm": algorithm, "device": device,
        "rows": rows, "rounds": rounds, "channel": sl["coordinator"]["channel"],
        "same_rounds": sum(r["same"] for r in per_round),
        "same_final": fl["final_hash"] == sl["final_hash"],
        "fl_f1": fl["test"]["f1"], "sl_f1": sl["test"]["f1"], "per_round": per_round,
    }


# ---------- audit ----------

# in Thai, as the rule attempts below: they are the report's and the page's wording
AUDIT_CHECKS = ("hash ของ global model บน ledger ตรงกับในไฟล์ผล",
                "global model ของ SL ตรงกับของ FL",
                "ผู้ปิดรอบคือ leader ที่คำนวณซ้ำเองจากสูตร sha256(\"round-N:members\") mod จำนวนสมาชิก "
                "(ไม่ได้อ่านคำตอบจาก ledger)",
                "update ของทุก client อยู่บน chain",
                "n_samples บน chain ตรงกับจำนวนข้อมูลจริงของ client นั้น")


def _audit_run(path: Path, gateway: str) -> dict:
    sl = json.loads(path.read_text(encoding="utf-8"))
    fl = json.loads(path.with_name(path.name.replace("sl-", "fl-", 1)).read_text(encoding="utf-8"))
    channel = sl["coordinator"]["channel"]
    client = LedgerClient(gateway, channel=channel)
    members = client.config()["members"]
    nodes = sorted(architectures.node_name(k) for k in range(len(sl["clients"])))
    samples = {architectures.node_name(k): c["train"] for k, c in enumerate(sl["clients"])}
    failures, leaders = [], Counter()
    for h, f in zip(sl["history"], fl["history"]):
        n = h["chain_round"]
        agg = client.aggregation(n)
        updates = {u["node_id"]: u for u in client.round_updates(n)}
        leaders[agg["aggregator"]] += 1
        results = (
            agg["aggregated_hash"] == h["global_hash"],
            h["global_hash"] == f["global_hash"],
            agg["aggregator"] == elected(n, members) == h["aggregator"],
            sorted(agg["participants"]) == nodes == sorted(updates),
            all(updates.get(k, {}).get("n_samples") == samples[k] for k in nodes),
        )
        failures += [f"{sl['scenario']}/{sl['model']}/{sl['algorithm']} round {n}: {name}"
                     for name, ok in zip(AUDIT_CHECKS, results) if not ok]
    return {"channel": channel, "members": members, "rounds": len(sl["history"]),
            "failures": failures, "leaders": leaders}


def audit(experiment: Path = EXPERIMENT, gateway: str = GATEWAY) -> dict:
    files = sorted((experiment / "runs").glob("*/sl-*.json"))
    if not files:
        raise FileNotFoundError(f"no SL results in {experiment / 'runs'}")
    with ThreadPoolExecutor(8) as pool:
        runs = list(pool.map(lambda p: _audit_run(p, gateway), files))
    rotation: dict[str, dict] = {}
    for r in runs:
        entry = rotation.setdefault(r["channel"], {"members": r["members"], "led": Counter()})
        entry["led"].update(r["leaders"])
    failures = [f for r in runs for f in r["failures"]]
    rounds = sum(r["rounds"] for r in runs)
    return {
        "runs": len(runs), "rounds": rounds, "checks": rounds * len(AUDIT_CHECKS),
        "check_names": list(AUDIT_CHECKS), "failed": len(failures), "failures": failures[:50],
        "rotation": {ch: {"members": len(e["members"]), "leaders": len(e["led"]), "led": dict(e["led"])}
                     for ch, e in sorted(rotation.items())},
    }


# ---------- rules ----------

def _answer(exc: Exception) -> str:
    """The chaincode's own words, without Fabric's gRPC wrapping around them."""
    text = str(exc).strip()
    return text.split("chaincode response 500, ", 1)[-1]


def rules(channel: str, gateway: str = GATEWAY) -> dict:
    """Five attempts that break the swarm's rules; none may get through or change anything."""
    client = LedgerClient(gateway, channel=channel)
    config = client.config()
    members = config["members"]
    committed = client.committed_rounds()
    if not committed:
        raise LedgerError(f"{channel} has no finished round to test against")
    closed = max(committed)
    kept = client.aggregation(closed)["aggregated_hash"]
    probe = closed + 100_000                       # far past any round a run will reach
    probe_leader = elected(probe, members)
    other = next(m for m in members if m != probe_leader)
    # an organisation of this network outside the swarm, or, when the swarm already spans
    # them all, a name the gateway holds no key for
    outsider = next((i for i in sorted(client.health()["identities"]) if i not in members), "Org99MSP")

    attempts = [
        (f"{outsider} ซึ่งไม่อยู่ใน swarm นี้ ส่ง update",
         lambda: client.submit_update(outsider, probe, FAKE_HASH, 1, 1, "verify")),
        (f"{members[0]} ส่ง update เข้ารอบ {closed} ที่ปิดไปแล้ว",
         lambda: client.submit_update(members[0], closed, FAKE_HASH, 1, 1, "verify")),
        (f"{other} ปิดรอบ {probe} ทั้งที่ leader คือ {probe_leader}",
         lambda: client.record_aggregation(other, probe, FAKE_HASH, 0.0, "verify")),
        (f"{probe_leader} (leader) ปิดรอบ {probe} โดยไม่มี update เลย",
         lambda: client.record_aggregation(probe_leader, probe, FAKE_HASH, 0.0, "verify")),
        (f"{elected(closed, members)} (leader ของรอบ {closed}) แก้ global model ของรอบนั้น",
         lambda: client.record_aggregation(elected(closed, members), closed, FAKE_HASH, 0.0, "verify")),
    ]
    outcomes = []                                  # `what` is in Thai, as AUDIT_CHECKS
    for what, call in attempts:
        try:
            call()
            outcomes.append({"what": what, "refused": False, "answer": "accepted"})
        except LedgerError as exc:
            outcomes.append({"what": what, "refused": True, "answer": _answer(exc)})

    after = client.committed_rounds()
    return {
        "channel": channel, "members": len(members), "quorum": config["quorum"],
        "attempts": outcomes, "refused": sum(o["refused"] for o in outcomes),
        "finished_rounds_before": len(committed), "finished_rounds_after": len(after),
        "probe_updates_after": len(client.round_updates(probe)),
        "closed_round": closed, "closed_hash_kept": client.aggregation(closed)["aggregated_hash"] == kept,
        "unchanged": (len(after) == len(committed) and not client.round_updates(probe)
                      and client.aggregation(closed)["aggregated_hash"] == kept),
    }


def all_rules(gateway: str = GATEWAY) -> list[dict]:
    return [rules(c["channel"], gateway) for c in LedgerClient(gateway).channels()]


# ---------- the evidence file ----------

def evidence_path(experiment: Path = EXPERIMENT) -> Path:
    return experiment / "verify.json"


def save(section: str, value, experiment: Path = EXPERIMENT) -> None:
    """Write one section of verify.json, keeping the others."""
    path = evidence_path(experiment)
    evidence = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    evidence[section] = {"checked": time.strftime("%Y-%m-%dT%H:%M:%S"), "result": value}
    path.write_text(json.dumps(evidence, indent=1), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", nargs="+", choices=("independent", "audit", "rules"),
                        default=["independent", "audit", "rules"])
    parser.add_argument("--experiment", type=Path, default=EXPERIMENT)
    parser.add_argument("--gateway", default=GATEWAY)
    args = parser.parse_args()

    if "audit" in args.only:
        result = audit(args.experiment, args.gateway)
        save("audit", result, args.experiment)
        print(f"audit: {result['runs']} SL runs, {result['rounds']} rounds, {result['checks']} checks, "
              f"{result['failed']} failed")
    if "rules" in args.only:
        result = all_rules(args.gateway)
        save("rules", result, args.experiment)
        for r in result:
            print(f"rules: {r['channel']:28s} {r['refused']}/{len(r['attempts'])} refused, "
                  f"ledger unchanged {r['unchanged']}")
    if "independent" in args.only:
        pairs = []
        for scenario, model, algorithm in INDEPENDENT:
            pair = independent(scenario, model, algorithm, gateway=args.gateway, log=lambda s: None)
            pairs.append(pair)
            print(f"independent: {scenario:8s} {model:11s} {algorithm:8s} {pair['device']:4s} "
                  f"same rounds {pair['same_rounds']}/{pair['rounds']}, same final model {pair['same_final']}")
        save("independent", pairs, args.experiment)
    print(f"wrote {evidence_path(args.experiment)}")


if __name__ == "__main__":
    main()
