# PoC Architecture

How `poc/` is put together, and why.

## Two layers

The PoC splits into a **blockchain layer** (Hyperledger Fabric — coordination
only) and an **ML layer** (Python — actual training), connected by shell
scripts. Nothing about the ML is on-chain except a hash.

```
poc/
├── chaincode/sl-ledger/   Go chaincode — the ledger's data model
├── scripts/               network lifecycle + chaincode invoke/query + resource sampler
├── sl-client/             Python: local training, aggregation, orchestration
└── results/               measured CSVs from the last run
```

## Blockchain layer: 3-org consortium

`scripts/01-network-up.sh` and `02-join-org3-cc.sh` stand up a Hyperledger
Fabric network via `fabric-samples/test-network`: three orgs (`Org1MSP`/
`Org2MSP`/`Org3MSP`, each with its own Fabric CA), one Raft orderer, one peer
+ CouchDB per org, one channel (`slchannel`). The `sl-ledger` chaincode is
installed and approved by all three orgs, so the channel's default
majority-endorsement policy requires 2-of-3 org signatures on every write —
that's the "consortium" trust model, enforced, not just configured.

The chaincode itself (`chaincode/sl-ledger/contract.go`) is intentionally
thin — it's a coordination ledger, not a model store:

- `SubmitUpdate(round, nodeId, weightHash, sizeBytes, timestamp)` — one
  entry per node per round, keyed by a composite key
  `("update", round, nodeId)` so a node can't overwrite another's
  submission or resubmit for the same round.
- `GetRoundUpdates(round)` — range query over that composite key to list
  every node's submission for a round.
- `RecordAggregation(round, aggregatedHash, participantCount, timestamp)` —
  the merged global-model hash for the round, keyed by `("agg", round)`.

Model weights never touch the chain — only a SHA-256 hash and a byte count.
That's the core design decision: a real 3-org channel has no business
replicating multi-megabyte tensors into every peer's block store on every
round, so the chain's job is strictly *integrity + audit trail* (who
submitted what, when, and what the agreed-upon merge was), while the actual
weight bytes move off-chain.

`scripts/cc-invoke.sh` / `cc-query.sh` are the bridge: given an org number
and a chaincode function, they set that org's MSP identity (via
`envVar.sh`'s `setGlobals`), then either invoke (collecting endorsement from
all 3 peers before submitting to the orderer) or query (single peer, no
ordering round-trip). Everything above the shell level talks to the chain
only through these two scripts.

## ML layer: off-chain SL nodes

`sl-client/sl_node.py` is the "local party" logic — no chain awareness at
all:

- `load_shard(node_index, num_nodes)` splits sklearn's `digits` dataset
  into disjoint shards, one per simulated node.
- `local_train(...)` loads the *previous* round's global weights from a
  local file (`results/weights/round_{N-1}/global.npz`), warm-starts an
  `SGDClassifier`, trains a few epochs on the node's own shard, writes the
  new weights to `results/weights/round_N/{node_id}.npz`, and returns the
  file's SHA-256 hash + size.
- `aggregate(round, node_ids)` — plain FedAvg: loads all three nodes'
  weight files and averages them into `global.npz`.

Since everything runs on one machine, "off-chain weight exchange" here is
simulated as a shared local directory rather than real peer-to-peer
transfer — a deliberate simplification. The point of the PoC is measuring
the *blockchain* overhead, not building a real P2P transport.

## Orchestration: one round, step by step

`sl-client/orchestrate.py` is the loop that ties it together. For each
round:

1. For each of the 3 nodes: `local_train` (pure compute) →
   `cc-invoke.sh <org> SubmitUpdate ...` (write, timed) →
   `cc-query.sh <org> GetRoundUpdates ...` (read-back, timed).
2. `aggregate()` locally (FedAvg over the 3 just-submitted weight files).
3. A round-robin "aggregator" org (`NODES[round_num % 3]`) calls
   `RecordAggregation` — mirrors real Swarm Learning's leader-rotation
   idea, so no single org is a permanent coordinator.
4. Ledger size is sampled before/after via `docker exec ... du -sb` on
   peer0.org1's ledger data, to track on-chain storage growth per round.

Every timing (`train_seconds`, `submit_latency_s`, `query_latency_s`,
`agg_latency_s`) and the ledger size delta get written to
`results/round_metrics.csv` — that CSV is the direct evidence behind the
resource numbers in `poc/README.md`.

`scripts/monitor.py` runs independently alongside a round, polling
`docker stats` every 2s for every Fabric container and writing
`results/docker_stats.csv` — that's where the idle CPU/RAM footprint
numbers came from.

## Why it's shaped this way

- **Off-chain weights, on-chain hash** — keeps the chain's storage/
  bandwidth cost independent of model size, which is what lets the README
  argue the ~2.4s/tx consensus latency is a fixed floor, not something
  that gets worse with bigger models.
- **3 real Fabric orgs, not a mocked chain** — so the "consortium" answer
  to the original resource/permission question is something the PoC
  actually measured (endorsement enforced, verified via
  `querycommitted`), not just asserted.
- **Shell scripts as the only chain interface** — Python never touches the
  Fabric SDK; it shells out to the same `peer` CLI a human operator would
  use. Simpler, and avoids Fabric's patchy Python SDK support, at the cost
  of one `bash` subprocess per chain call (that cost shows up in the
  timings too).
