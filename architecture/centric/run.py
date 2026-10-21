"""Run the paper's experiment grid under FL and under SL.

    python run.py                                   # everything the downloaded data allows
    python run.py --scenarios edge --models lstm --algorithms fedavg --rounds 3

Each experiment set has its own folder, results/<source>-<rows>k/ (results/full-500k for
the defaults). Every run writes runs/<scenario>/<arch>-<model>-<algorithm>.json there and
is skipped next time unless --force, so an interrupted grid resumes where it stopped.

A run trains once per round and hands the same local updates to the FL server and to the
SL swarm; federation.train checks every round that both arrive at the same global model.
Runs are grouped into lanes by (dataset, model). A lane is one Fabric channel, and two runs
on one channel would race for round numbers, so a lane runs its runs one after another
while lanes run in parallel. Lanes of the --gpu-models go to the GPU, which one process
already saturates (measured: 1 process 1,900 LSTM steps/s, 3 processes 2,300 together);
the rest train on the CPU, one thread per lane.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import Future, ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

import data
import federation
import models
from federation import ALGORITHMS, Hyper

HERE = Path(__file__).resolve().parent

MODELS = tuple(models.ARCHITECTURES)     # the backbones models.py defines
ARCHITECTURES = ("fl", "sl")
DEFAULT_ROWS = 500_000
# Section 4.1: "typically 50 rounds for single-dataset cases and up to 100 for the combined"
DEFAULT_ROUNDS = {"combined": 100}


def experiment_dir(source: str, rows: int) -> Path:
    return HERE / "results" / f"{source}-{rows // 1000}k"


def result_path(experiment: Path, scenario: str, arch: str, model: str, algorithm: str) -> Path:
    return experiment / "runs" / scenario / f"{arch}-{model}-{algorithm}.json"


def cross_targets(scenario: str, source: str) -> list[str]:
    """The federations a scenario's model is also tested on (Section 5.3)."""
    if not scenario.endswith("-h"):
        return []
    return [f"{d}-h" for d in data.available(source) if f"{d}-h" != scenario]


def run_lane(jobs: list[tuple[str, str, str]], archs: list[str], feds: dict[str, data.Federation],
             experiment: Path, rows: int, rounds: int | None, gateway: str, device: str,
             flush_denormal: bool) -> list[str]:
    """One lane, in its own process: the runs of one (dataset, model)."""
    # cuBLAS reads this when it starts, so before torch touches the GPU
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    import torch

    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(1)
    torch.set_flush_denormal(flush_denormal)
    import architectures

    dataset, model = data.dataset_of(jobs[0][0]), jobs[0][1]
    logs = experiment / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    log_file = (logs / f"{dataset}-{model}.log").open("a", encoding="utf-8")
    log = lambda line: (log_file.write(line + "\n"), log_file.flush())
    done = []
    for scenario, model, algorithm in jobs:
        fed = feds[scenario]
        coordinators = [architectures.CentralServer() if arch == "fl"
                        else architectures.FabricSwarm(dataset, model, gateway) for arch in archs]
        n_rounds = rounds or DEFAULT_ROUNDS.get(scenario, 50)
        try:
            records, net, params = federation.train(fed, model, algorithm, coordinators, n_rounds,
                                                    log=log, device=device)
        except Exception as exc:
            # re-raised as a plain RuntimeError: the ledger's own error class is loaded by
            # path, so the parent could not unpickle it and would report only a dead worker
            log(f"{scenario}/{model}/{algorithm} failed: {type(exc).__name__}: {exc}")
            raise RuntimeError(f"{scenario}/{model}/{algorithm}: {type(exc).__name__}: {exc}") from None
        cross = cross_dataset(fed, net, params, [feds[t] for t in cross_targets(scenario, fed.source)])
        for record in records:
            record.update(cross=cross, rows_budget=rows, flush_denormal=flush_denormal,
                          finished=time.strftime("%Y-%m-%dT%H:%M:%S"))
            path = result_path(experiment, scenario, record["architecture"], model, algorithm)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(record, indent=1), encoding="utf-8")
        t = records[0]["test"]
        done.append(f"{scenario:9s} {model:11s} {algorithm:8s} {device:4s} acc {t['accuracy']:.4f} "
                    f"f1 {t['f1']:.4f} auc {t['auc']:.4f}  {records[0]['seconds']['wall']:7.0f}s")
    log_file.close()
    return done


def cross_dataset(fed: data.Federation, net, params: np.ndarray,
                  targets: list[data.Federation]) -> dict:
    """Section 5.3. A model trained on one dataset's shared-schema view is tested on every
    other dataset's, through the source federation's scaler; the combined model is tested
    on each dataset it was trained with, one client's test split at a time."""
    n_classes = len(fed.classes)
    if fed.scenario == "combined":
        return {source: federation.evaluate(net, params, c.X_test, c.y_test, n_classes)
                for source, c in zip(fed.sources, fed.clients)}
    mean, scale = fed.pooled_scaler()
    out = {}
    for target in targets:
        X = np.concatenate([c.raw_test for c in target.clients])
        y = np.concatenate([c.y_test for c in target.clients])
        out[target.sources[0]] = federation.evaluate(
            net, params, ((X - mean) / scale).astype(np.float32), y, n_classes)
    return out


def require_channels(lanes: dict[tuple[str, str], list], gateway: str) -> None:
    """Stop before any data is built if a lane's swarm has no chain on the network.

    Which dataset-model pairs get a channel is decided by poc/sl-fabric/network/swarms.conf;
    a model can be defined in models.py and still not be deployed there.
    """
    import architectures

    have = {c["channel"] for c in architectures.ledger.LedgerClient(gateway).channels()}
    missing = sorted(f"{dataset}/{model}" for dataset, model in lanes
                     if architectures.ledger.channel_for(dataset, model) not in have)
    if missing:
        sys.exit(f"no Fabric channel for {', '.join(missing)}: add the model to its dataset's line "
                 "in poc/sl-fabric/network/swarms.conf and run ./network.sh deploy "
                 "(or train FL only with --arch fl)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scenarios", nargs="+", choices=data.SCENARIOS)
    parser.add_argument("--models", nargs="+", choices=MODELS, default=list(MODELS))
    parser.add_argument("--algorithms", nargs="+", choices=ALGORITHMS, default=list(ALGORITHMS))
    parser.add_argument("--arch", nargs="+", choices=ARCHITECTURES, default=list(ARCHITECTURES))
    parser.add_argument("--source", choices=data.SOURCES, default="full",
                        help="full: each dataset's complete release; subset: the small mirrors")
    parser.add_argument("--rows", type=int, default=DEFAULT_ROWS,
                        help="rows drawn per scenario before splitting (paper: the full datasets)")
    parser.add_argument("--rounds", type=int, help="override 50 / 100 rounds")
    parser.add_argument("--gpu-models", nargs="*", choices=MODELS, default=None,
                        help="models whose lanes train on the GPU (default: transformer, if CUDA works)")
    parser.add_argument("--gpu-workers", type=int, default=2,
                        help="GPU lanes at a time; a second one fills the GPU while the first waits on Fabric")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 4),
                        help="CPU lanes at a time")
    parser.add_argument("--gateway", default=os.getenv("SL_GATEWAY_URL", "http://127.0.0.1:8899"))
    parser.add_argument("--force", action="store_true", help="rerun runs that already have a result")
    parser.add_argument("--flush-denormal", action="store_true",
                        help="treat float32 values below 1e-38 as zero on the CPU. A model whose "
                             "units have died fills up with such values, which the CPU handles "
                             "3x slower; results differ from runs without it in the last bits")
    args = parser.parse_args()

    import torch

    gpu_models = args.gpu_models if args.gpu_models is not None else (
        ["transformer"] if torch.cuda.is_available() else [])
    if gpu_models and not torch.cuda.is_available():
        sys.exit("--gpu-models needs a CUDA build of PyTorch: use .venv/Scripts/python.exe (see README)")

    have = data.available(args.source)
    scenarios = args.scenarios or [s for s in data.SCENARIOS
                                   if s == "combined" or data.dataset_of(s) in have]
    missing = [s for s in scenarios if s != "combined" and data.dataset_of(s) not in have]
    if missing:
        sys.exit(f"no data for {missing}; run: python data.py download --source {args.source}")
    experiment = experiment_dir(args.source, args.rows)

    lanes: dict[tuple[str, str], list] = {}
    for scenario in scenarios:
        for model in args.models:
            for algorithm in args.algorithms:
                done = all(result_path(experiment, scenario, arch, model, algorithm).exists() for arch in args.arch)
                if done and not args.force:
                    continue
                lanes.setdefault((data.dataset_of(scenario), model), []).append((scenario, model, algorithm))
    if not lanes:
        print("every requested run already has a result (use --force to rerun)")
        return
    if "sl" in args.arch:
        require_channels(lanes, args.gateway)

    needed = {s for jobs in lanes.values() for s, *_ in jobs}
    needed |= {t for s in needed for t in cross_targets(s, args.source)}
    pools: dict = {}
    feds = {s: data.build(s, args.rows, pools, source=args.source) for s in sorted(needed)}
    del pools

    total = sum(len(j) for j in lanes.values())
    print(f"{total} runs x {'+'.join(args.arch)} in {len(lanes)} lanes -> {experiment}; "
          f"GPU: {gpu_models or 'none'} ({args.gpu_workers} at a time), CPU: {args.workers} at a time")
    started = time.perf_counter()
    futures: dict[Future, tuple[str, str]] = {}
    with ProcessPoolExecutor(max_workers=max(1, args.gpu_workers)) as gpu, \
            ProcessPoolExecutor(max_workers=args.workers) as cpu:
        # longest lanes first, so the last one to finish is a short one
        for key, jobs in sorted(lanes.items(), key=lambda item: -len(item[1])):
            mine = {s for s, *_ in jobs}
            mine |= {t for s in mine for t in cross_targets(s, args.source)}
            device = "cuda" if key[1] in gpu_models else "cpu"
            pool = gpu if device == "cuda" else cpu
            futures[pool.submit(run_lane, jobs, args.arch, {s: feds[s] for s in mine}, experiment,
                                args.rows, args.rounds, args.gateway, device, args.flush_denormal)] = key
        failed = []
        for future in as_completed(futures):
            key = futures[future]
            try:
                for line in future.result():
                    print(line, flush=True)
            except Exception as exc:          # one lane failing must not hide the others
                failed.append(key)
                print(f"lane {key} failed: {type(exc).__name__}: {exc}", flush=True)
    print(f"done in {(time.perf_counter() - started) / 60:.1f} min")
    if failed:
        sys.exit(f"{len(failed)} lanes failed: {failed}")


if __name__ == "__main__":
    main()
