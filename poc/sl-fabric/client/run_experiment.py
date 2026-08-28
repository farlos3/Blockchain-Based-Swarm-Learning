"""Run the swarm on Fabric for several models and compare them.

    python run_experiment.py                          # all three models, 10 rounds each
    python run_experiment.py --models cnn --rounds 25
    python run_experiment.py --alpha 0.1              # harder, more skewed split

Two axes are reported, because a model that wins on one can lose badly on the other:

    accuracy   what the swarm reached on the held-out test set
    resources  parameters, bytes shipped per round, training time, memory, and how much
               of the wall clock the ledger itself accounted for

Results are written to results/ as JSON so they can be plotted without re-running, which
matters because a full run takes minutes and writes to a real ledger.

The network and the gateway must already be running:

    cd ../network  && ./network.sh up && ./network.sh deploy
    cd ../gateway  && ./sl-gateway.exe
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import results as results_io
from data import describe, load_swarm_data
from ledger import DEFAULT_URL, LedgerClient, LedgerError, channel_for
from swarm import RunResult, run_swarm

RESULTS_DIR = results_io.RESULTS_DIR


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", nargs="+", default=["logistic", "mlp", "cnn"],
                        help="which models to compare")
    parser.add_argument("--rounds", type=int, default=30, help="swarm rounds per model")
    parser.add_argument("--local-epochs", type=int, default=3,
                        help="local epochs each node trains before submitting. One epoch "
                             "is only ~18 gradient steps on the smallest shard, which is "
                             "too little to justify a 15-second consensus round")
    parser.add_argument("--alpha", type=float, default=0.5,
                        help="Dirichlet concentration: small = more skewed, non-IID data")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--gateway", default=DEFAULT_URL,
                        help="gateway base URL (also settable with SL_GATEWAY_URL)")
    return parser.parse_args()


def summarise(results: list[RunResult]) -> str:
    header = (f"{'model':10s} {'params':>10s} {'KiB/round':>10s} {'best val':>9s} "
              f"{'test acc':>9s} {'train s':>9s} {'ledger s':>9s} {'peak MB':>9s}")
    lines = [header, "-" * len(header)]
    for r in results:
        kib = r.rounds[0].bytes_per_node / 1024 if r.rounds else 0
        lines.append(f"{r.model:10s} {r.n_parameters:10,d} {kib:10.1f} "
                     f"{r.best_accuracy:9.4f} {r.test_accuracy:9.4f} "
                     f"{r.train_seconds:9.1f} {r.ledger_seconds:9.1f} {r.peak_rss_mb:9.1f}")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    ledger = LedgerClient(args.gateway)

    try:
        health = ledger.health()
        config = ledger.config()
    except LedgerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    msp_ids = config["members"]
    print(f"gateway {args.gateway}  chains {health['channels']}")
    print(f"members {msp_ids}  quorum {config['quorum']}")

    data = load_swarm_data(msp_ids, alpha=args.alpha, seed=args.seed)
    print(describe(data))

    run_settings = {
        "alpha": args.alpha,
        "rounds": args.rounds,
        "local_epochs": args.local_epochs,
        "seed": args.seed,
        "models": list(args.models),
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = RESULTS_DIR / f"swarm-{stamp}.json"

    results: list[RunResult] = []
    for model_name in args.models:
        # each model type has its own chain; its rounds continue from that chain's height
        model_ledger = ledger.for_channel(channel_for(model_name))
        committed = model_ledger.committed_rounds()
        offset = model_ledger.next_free_round(max(committed) if committed else 0)
        try:
            results.append(run_swarm(
                model_name=model_name, data=data, ledger=model_ledger,
                rounds=args.rounds, local_epochs=args.local_epochs,
                round_offset=offset, seed=args.seed,
            ))
        except LedgerError as exc:
            print(f"ERROR while running {model_name}: {exc}", file=sys.stderr)
            if results:
                # a long comparison is tens of minutes of real ledger writes; whatever
                # finished is worth keeping even when the next model fails
                results_io.write(out, run_settings, config, data, results)
                print(f"the models that finished are in {out}", file=sys.stderr)
            return 1
        results_io.write(out, run_settings, config, data, results)
        print(f"  {model_name} done, results so far in {out.name}", flush=True)

    print("\n" + summarise(results))
    print(f"\nwritten to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
