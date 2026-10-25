"""The paper's experiments: CL and SL (mean, coordmedian, geomedian) for the packet, flow and
multimodal networks on Scenarios 1-3, every SL round on Fabric.

    python run.py                                    # everything missing
    python run.py --scenarios 3 --models multimodal --merges mean
    python run.py --scenarios 2 3 --models multimodal --no-cl --weighting samples --on-train-end inactive

One JSON per run in results/runs/scenario<N>/<arch>-<model>[-<merge>[-<variant>]].json, the
variant naming whatever differs from SwarmCallback's defaults; existing ones are skipped
unless --force.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch

import data
import models
import swarm

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scenarios", type=int, nargs="+", default=sorted(data.SCENARIOS))
    parser.add_argument("--models", nargs="+", default=list(models.ARCHITECTURES), choices=list(models.ARCHITECTURES))
    parser.add_argument("--merges", nargs="+", default=list(swarm.MERGES), choices=list(swarm.MERGES))
    parser.add_argument("--no-cl", action="store_true", help="skip the centralised baselines")
    parser.add_argument("--no-sl", action="store_true", help="skip the swarm runs")
    parser.add_argument("--weighting", default="equal", choices=swarm.WEIGHTINGS,
                        help="nodeWeightage: equal (default) or each node's training rows")
    parser.add_argument("--on-train-end", default="snapshot", choices=swarm.ON_TRAIN_END,
                        help="checkinModelOnTrainEnd of a node that finishes early")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--gateway", default=swarm.ledger.DEFAULT_URL)
    parser.add_argument("--force", action="store_true", help="rerun runs that already have a result")
    args = parser.parse_args()

    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
    (RESULTS / "logs").mkdir(parents=True, exist_ok=True)
    # one log per scenario set: separate processes can run separate scenarios (separate chains)
    logfile = (RESULTS / "logs" / f"run-{'-'.join(map(str, args.scenarios))}.log").open("a", encoding="utf-8")

    def log(line: str) -> None:
        line = f"{time.strftime('%H:%M:%S')} {line}"
        print(line, flush=True)
        logfile.write(line + "\n")
        logfile.flush()

    if not args.no_sl:
        have = {c["channel"] for c in swarm.ledger.LedgerClient(args.gateway).channels()}
        missing = sorted({swarm.channel(s, m) for s in args.scenarios for m in args.models} - have)
        if missing:
            raise SystemExit(f"no Fabric channel for {missing}: add the eai lines to "
                             "poc/sl-fabric/network/swarms.conf and run ./network.sh deploy")

    for number in args.scenarios:
        scenario = data.load(number)
        log(f"scenario {number}: {[(h.name, len(h.train.y)) for h in scenario.hosts]}, "
            f"{scenario.n_features} packet features, {swarm.rounds_needed(scenario.hosts, swarm.Hyper())} SL rounds")
        out = RESULTS / "runs" / f"scenario{number}"
        out.mkdir(parents=True, exist_ok=True)
        variant = swarm.variant_name(args.weighting, args.on_train_end)
        suffix = f"-{variant}" if variant else ""
        for model in args.models:
            jobs = [] if args.no_cl else [(out / f"cl-{model}.json", None)]
            jobs += [] if args.no_sl else [(out / f"sl-{model}-{m}{suffix}.json", m) for m in args.merges]
            for target, method in jobs:
                if target.exists() and not args.force:
                    log(f"skip {target.relative_to(HERE)}")
                    continue
                if method is None:
                    record = swarm.central(scenario, model, device=args.device, log=log)
                else:
                    coordinator = swarm.FabricSwarm(number, model, args.gateway)
                    record = swarm.swarm(scenario, model, method, coordinator, device=args.device, log=log,
                                         weighting=args.weighting, on_train_end=args.on_train_end)
                record["features"] = scenario.features
                target.write_text(json.dumps(record, indent=1))
                t = record["test"]
                log(f"done {target.relative_to(HERE)}: acc {t['accuracy']:.4f} p {t['precision']:.4f} "
                    f"r {t['recall']:.4f} f1 {t['f1']:.4f} loss {t['loss']:.4f} "
                    f"({record['seconds']['wall']:.0f}s)")


if __name__ == "__main__":
    main()
