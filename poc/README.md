# Blockchain-Based Swarm Learning — PoC

Goal of this PoC: measure how much resource a blockchain-coordinated Swarm
Learning (SL) round actually costs, and settle what kind of permissioned
blockchain fits the SL trust model, using a real Hyperledger Fabric network
(not a simulation).

## Architecture

- **Blockchain**: Hyperledger Fabric 2.5, 3-org **consortium** channel
  (`slchannel`), identities issued per-org by Fabric CA (not just static
  `cryptogen` certs — closer to how a real multi-institution deployment
  would provision identities).
- **Chaincode** (`chaincode/sl-ledger`, Go): records SL coordination
  metadata only — `SubmitUpdate(round, nodeId, weightHash, sizeBytes, ts)`
  and `RecordAggregation(round, aggregatedHash, participantCount, ts)`.
  Model weights themselves stay off-chain (a real 3-org channel has no
  business storing multi-MB tensors in every peer's block store); only a
  SHA-256 integrity hash is committed.
- **SL nodes** (`sl-client/`): 3 simulated parties (one per org), each
  training a small multinomial logistic-regression model (`sklearn`,
  digits dataset, disjoint shards) for a few local epochs, then submitting
  its update hash to the chaincode. A round-robin "aggregator" node reads
  all three updates back, FedAvg's the weights, and records the merged
  hash on-chain.
- **Resource monitor** (`scripts/monitor.py`): samples `docker stats` for
  every Fabric container every 2s for the run's duration.

## Permission type: consortium, not public / not single-org

Implemented as a **permissioned consortium blockchain**: three independent
Fabric orgs (`Org1MSP`, `Org2MSP`, `Org3MSP`), each modeling one SL
party/institution, each with its own CA and MSP. The channel uses Fabric's
**default majority-endorsement policy**, which is evaluated against
*current* channel membership — so once Org3 joined, every write
(`SubmitUpdate`, `RecordAggregation`) needs endorsement signatures from at
least **2 of the 3 orgs** before the orderer commits it. `querycommitted`
after Org3's approval confirms `[Org1MSP: true, Org2MSP: true, Org3MSP: true]`.

This is the right fit for SL specifically because SL's whole premise is
mutually-distrusting parties (hospitals, banks, etc.) who need a shared,
tamper-evident coordination log *without* a central trusted server — a
public/permissionless chain gives no identity accountability for who
submitted what, and a single-org private chain gives no actual multi-party
trust guarantee (one party could unilaterally forge a "consensus"
aggregation record). A consortium chain with N-of-M endorsement is the
standard answer to that, and is what this PoC actually enforces, not just
asserts.

## Resource findings

All numbers measured on this machine (Windows, Docker Desktop, no GPU) via
`docker stats`, 2s sampling, over a 5-round run. Raw data:
`results/docker_stats.csv`, `results/round_metrics.csv`.

### Idle footprint (network up, no SL traffic)

| Layer | Containers | Avg RAM | Avg CPU |
|---|---|---|---|
| Fabric CA (identity issuance) | 3 | ~9.1 MiB each (~27 MiB total) | ~0% |
| Ordering service | 1 | ~16–19 MiB | ~0.3% |
| Peers (1 per org) | 3 | ~85–104 MiB each (~275 MiB total) | ~3% each |
| CouchDB (per-org world state) | 3 | ~94–106 MiB each (~300 MiB total) | ~1.3% each |
| Chaincode containers (1 per org, spun up on first invoke) | 3 | ~7 MiB each (~21 MiB total) | <1% |
| **Total** | **13** | **≈ 649 MiB RSS** | low, bursty |

Disk (Docker images, shared layers, one-time pull — not per-container):
`fabric-peer` 232 MB, `fabric-orderer` 182 MB, `fabric-ca` 381 MB,
`couchdb` 419 MB, `fabric-baseos` 257 MB (chaincode runtime base),
`fabric-ccenv` 1.01 GB (chaincode **build** image, only used transiently
when chaincode is packaged/installed, not running at steady state) — **≈
2.48 GB total unique image weight** for a full 3-org stack. Ledger/state
volumes after 6 committed blocks: ~128 MB (orderer, mostly fixed Raft/WAL
indexing overhead) + ~14 MB per peer. Crypto material (certs/keys for all
3 orgs + orderer): 780 KB.

### Per-round cost (blockchain coordination vs. actual ML)

| Operation | Avg latency | What it includes |
|---|---|---|
| Local training (toy model, 3 epochs) | **28–70 ms** | pure `sklearn` compute, no chain involved |
| `SubmitUpdate` invoke | **2.41 s** (min 2.36, max 2.54) | proposal → 3-of-3 peer endorsement → order → commit → event wait |
| `GetRoundUpdates` query | **0.32 s** | single-peer read, no ordering |
| `RecordAggregation` invoke | **2.39 s** | same write path as SubmitUpdate |
| Ledger growth | **≈ 30.4 KB/round** | 4 chaincode writes/round (3 submits + 1 aggregation) → ~7.6 KB/tx |

Per round (3 nodes): ≈ 3×2.41 s (submits) + 3×0.32 s (queries) + 1×2.39 s
(aggregation) ≈ **10.6 s of blockchain-interaction latency**, against
**< 0.2 s** of actual model training. For this toy model, consensus
overhead dominates wall-clock time by roughly 50–70×.

**Why this ratio matters more than it looks**: the ~2.4 s write latency is
consensus/endorsement-round-trip-bound (proposal simulation on 3 peers +
Raft ordering + commit + event notification), not payload-size-bound —
because only a 64-byte hash goes on-chain, not the model weights. So this
floor stays roughly flat regardless of model size; a real SL round training
a large model for minutes would make the blockchain overhead comparatively
negligible, while a toy/fast model (like this one, or federated learning on
small tabular data) makes the ~10s/round consensus tax the dominant cost.

### Bottom line

- Idle 3-org consortium network: **~650 MB RAM**, **~2.5 GB disk** (images), negligible idle CPU.
- Each SL round adds **~10.6 s** of blockchain-mediated coordination latency and **~30 KB** of ledger growth, independent of model size (since weights stay off-chain).
- 3-of-3 endorsement + majority commit policy is enforced and verified (`querycommitted` shows all three orgs approved), confirming the consortium/permissioned design actually provides the intended N-of-M trust guarantee, not just on paper.

## Reproducing

Requires Docker Desktop running. **Run everything from a path with no
spaces** — `fabric-samples`' own tooling breaks on spaces (see caveats
below); this repo's `poc/` lives under a spaced path, so the runtime was
executed from a mirrored `D:\swarm-poc` (fabric-samples + copies of
`chaincode/`, `scripts/`, `sl-client/`).

```bash
# one-time: fetch Fabric binaries/images/samples into <space-free-dir>
curl -sSL https://raw.githubusercontent.com/hyperledger/fabric/main/scripts/install-fabric.sh | bash -s -- docker samples binary

# bring up the 3-org consortium + deploy sl-ledger chaincode
bash scripts/01-network-up.sh

# run N rounds (rounds, local_epochs, start_round)
sl-client/.venv/Scripts/python sl-client/orchestrate.py 5 3 1

# resource sampling (run in background during the above)
sl-client/.venv/Scripts/python scripts/monitor.py 2 results/docker_stats.csv
```

Tear down: `cd fabric-samples/test-network && ./network.sh down`.

## Windows/Git Bash caveats fixed along the way

- **Paths with spaces break `fabric-samples`' bash tooling** (many
  unquoted `$VAR` path usages throughout `network.sh`/`envVar.sh`/etc.) —
  run from a space-free path.
- **Git Bash/MSYS mangles the peer↔Docker-socket bind mount**
  (`${DOCKER_SOCK}:/host/var/run/docker.sock`), producing `mkdir "C:\Program
  Files\Git\var": Access is denied`. Fixed by shadowing *only* `docker` and
  `docker-compose` with `MSYS_NO_PATHCONV=1` (a blanket env var breaks
  `fabric-ca-client`/`configtxgen` instead, which need normal path
  conversion) — see `scripts/01-network-up.sh`.
- Docker Desktop on Windows resolves `docker compose` to the standalone
  `docker-compose.exe` shim, not the `docker compose` plugin — both had to
  be shadowed, not just one.
- `envVar.sh`'s `setGlobals`/`parsePeerConnectionParameters` reference
  `$OVERRIDE_ORG`/`$VERBOSE` without defaulting them; under `set -u` these
  are unbound-variable errors — export them (empty/`false`) before sourcing.
- `ccutils.sh`'s `installChaincode`/`approveForMyOrg` rely on a
  deliberately-nonzero `grep` (to detect "not yet installed") — don't run
  them under `set -e`, or the script aborts on the expected-not-found case.
