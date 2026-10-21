# sl-fabric

Swarm learning on **Hyperledger Fabric 2.5**: one organization per swarm node, training
image classifiers on BloodMNIST while every round is recorded on a real ledger. The same
network also carries the IDS replication in [`architecture/centric`](../../architecture/centric),
whose largest swarm has ten nodes, so it runs ten organizations.

This is the step after [`../sl-blockchain`](../sl-blockchain), which built the same rules
on a hand-written hash chain. What changes here is who enforces them:

| | sl-blockchain (PoC) | sl-fabric (this) |
|---|---|---|
| identity | ed25519 keys managed by the code | X.509 per org, checked by the peer's MSP |
| who is the submitter | a field in the transaction | the client certificate — nothing to forge |
| immutability | hand-written hash chain + `validate()` | ordering service and the peers' block store |
| who agrees | one leader signs the block | a **majority of the swarm's organizations** endorse it |
| processes | one | 22 containers, real gRPC between them |

## Layout

| Path | What it is |
|---|---|
| `network/` | the 10-org network: `swarms.conf`, `crypto-config.yaml`, `configtx.yaml`, `compose.yaml`, `network.sh` |
| `chaincode/sl-ledger/` | the smart contract (Go) plus its Dockerfile |
| `gateway/` | a Go REST service holding one Fabric identity per org, and the monitor page |
| `network/.env` | channel list and package ids written by `network.sh`, read by compose (generated, not source) |
| `client/` | the Python swarm: data partition, models, the round loop, the experiment runner |

## Running it

```bash
# 1. everything that runs in Docker: orderer, 10 peers, 10 chaincode services, gateway
cd network
./network.sh up          # certificates, containers, channel  (~2 minutes cold)
./network.sh deploy      # package, install, approve, commit the chaincode (re-runnable)

# 2. the swarm itself, on the host — the IDS replication of ../../architecture/centric
cd ../../architecture/centric
python run.py
```

(`client/` below is a separate, earlier PoC — image classification on BloodMNIST/PathMNIST.
It needs its own line in `network/swarms.conf`, commented out by default; see below.)

The monitor is at **http://127.0.0.1:8899** as soon as `up` finishes.

Everything runs as one compose project named `sl-fabric`, so `docker compose ps`, Docker
Desktop and `down` all treat the 22 containers as a single unit rather than leaving
strays behind:

```
orderer.swarm.local          peer0.org1..10.swarm.local
sl-ledger.org1..10.swarm.local (chaincode)    sl-gateway
```

`./network.sh down` removes every container, volume, generated certificate and the
`.env` compose reads; `up` rebuilds them all from `swarms.conf` and the YAML files, so a
broken run is never worth debugging.

To move the monitor off 8899:

```bash
SL_GATEWAY_PORT=9500 ./network.sh up            # publishes 9500 instead
SL_GATEWAY_URL=http://127.0.0.1:9500 python run_experiment.py   # or --gateway
```

Prerequisites: Docker, Go 1.23+, Python with `numpy scikit-learn psutil torch`, and the
Fabric 2.5.13 binaries in `bin/` (`./install-fabric.sh --fabric-version 2.5.13 binary docker`).

Under Git Bash on Windows, do **not** set `MSYS_NO_PATHCONV=1`: the Fabric binaries are
native Windows executables and depend on MSYS rewriting `/d/...` arguments to `D:\...`.

## The network

Ten peer organizations, one peer each, and a single-node Raft orderer:

```
Org1MSP   peer0.org1.swarm.local   localhost:7051     ...one port block of 1000 per org...
Org5MSP   peer0.org5.swarm.local   localhost:11051
Org10MSP  peer0.org10.swarm.local  localhost:16051
orderer.swarm.local                localhost:7050 (admin 7053)
```

**Which swarms and models the network runs is configuration**, in `network/swarms.conf`:
one line per dataset with its number of organizations and the models trained on it.
Every dataset-model pair gets its own channel, `swarm-<dataset>-<model>`, holding only the
organizations of that swarm, always Org1..OrgN (`SwarmN` profiles in `configtx.yaml`).
`network.sh` writes the channel list into `.env`; the gateway and its monitor read it from
there, and `architecture/centric/run.py` refuses a model that has no channel. The shipped
file runs only the paper's two IDS backbones, on the paper's four federations:

```
# dataset   orgs  models
edge        6     lstm transformer
cic         10    lstm transformer
tii         5     lstm transformer
combined    3     lstm transformer
```

To bring back the earlier image swarm (`client/`, BloodMNIST/PathMNIST, models `logistic
mlp cnn`), add its lines back (`blood 5 logistic mlp cnn` and `path 5 logistic mlp cnn`)
and run `./network.sh deploy`. To use another model, put it on its dataset's line and run
`./network.sh deploy`: it creates the channels that do not exist yet on the running network
and deploys the chaincode on them, leaving the existing chains as they are. It also
restarts the gateway so it serves the new list, so do it while nothing is training. A
model taken off the file keeps its chain until the next `down`, but the gateway no longer
serves it. `network.sh` checks the file first: unknown sizes (no `SwarmN` profile), more
than 10 organizations, a dataset listed twice or names a channel cannot carry stop it
before anything is created.

So "majority endorsement" is always a majority of that swarm, and orgs 6-10 existing
changes nothing for a five-org swarm. The quorum `InitSwarm` records is a
majority of the members. `deploy` skips whatever is already installed, approved,
committed or initialised: with ten peers behind Docker Desktop's port forwarding a
connection occasionally times out, and running `deploy` again finishes the job.

One orderer is enough for the property this project needs. What must not be possible is a
single *swarm member* committing a round alone, and that is stopped by the endorsement
policy (`MAJORITY Endorsement` in `configtx.yaml`), not by orderer replication. A
production deployment would run three or five orderers for availability.

**Chaincode runs as a service.** Fabric's default lifecycle has each peer build the
chaincode by driving the Docker daemon, which fails through Docker Desktop's socket proxy
on Windows (`write unix .../docker.proxy.sock: broken pipe`). The chaincode is therefore
packaged as `ccaas`: one image, built once from `chaincode/sl-ledger/Dockerfile`, run as a
container per organization. Each org's package embeds its own container address, so each
has a different package id — which is fine, `approveformyorg` takes each org's own id.

## The smart contract

`chaincode/sl-ledger` keeps the same shape as the PoC's `SwarmLedger`, so nodes written
against one need almost no change to run on the other.

| Function | Rule it enforces |
|---|---|
| `InitSwarm(members, quorum)` | written once; the caller must be one of the members |
| `SubmitUpdate(round, hash, bytes, n, model)` | caller is in the authority set, one update per node per round, round still open |
| `RecordAggregation(round, hash, accuracy, model)` | caller **is** that round's leader, quorum reached, round not already closed |
| `GetRoundUpdates` / `GetAggregation` / `GetCommittedRounds` / `GetLeader` / `GetSwarmConfig` | reads, no side effects |

Two details that matter and are easy to get wrong:

- **the submitter is never an argument.** It comes from `GetClientIdentity().GetMSPID()`,
  so a node can only submit as itself unless it holds another org's private key
- **no wall-clock time.** Timestamps come from `GetTxTimestamp()`, which is identical on
  every endorsing peer. `time.Now()` would differ between them and their read-write sets
  would never match

The leader rule is unchanged from `../sl-blockchain/consensus.py` and `ini_swarm.ipynb`:
`sha256("round-N:member,member,…") mod len(members)`. Any auditor can recompute whose
turn a past round was.

Verified against the running network:

```
leader r1                          Org3MSP
WhoAmI as Org1                     Org1MSP
Org1 submits twice                 rejected: Org1MSP already submitted an update for round 1
aggregate with 1 of 3 quorum       rejected: round 1 has 1 updates, quorum is 3
Org1 aggregates (leader is Org3)   rejected: round 1 belongs to Org3MSP, Org1MSP cannot aggregate it
Org3 aggregates                    committed, participants [Org1MSP Org2MSP Org3MSP]
Org4 submits after close           rejected: round 1 is already aggregated
```

## The gateway

Fabric 2.5 has no supported Python SDK, and the Gateway protocol involves proposal signing
and endorsement collection that is not worth reimplementing. `gateway/` is a small Go
service that holds one Fabric connection per organization and exposes:

| Method | Path | Signed by |
|---|---|---|
| GET | `/health`, `/config`, `/rounds`, `/leader/{round}` | any (reads) |
| GET | `/rounds/{round}/updates`, `/rounds/{round}/aggregation` | any (reads) |
| POST | `/nodes/{msp}/updates` | that org |
| POST | `/nodes/{msp}/aggregations` | that org |

The identity comes from the **path**, not the body, so the Python client cannot post as a
node it does not hold a key for. Chaincode errors are unwrapped from Fabric's gRPC
envelope, so a rejected rule reads as its own message rather than a generic failure.

It runs as a container in the same compose project and reaches the peers by their
container names; `SL_IN_CLUSTER` is what switches those addresses, and without it the same
binary talks to `localhost` and the published ports, which is handy when debugging it
outside Docker (`go build -o sl-gateway.exe . && ./sl-gateway.exe`).

Demo scope: only its own port is published, it has no authentication of its own, and it
loads all ten identities into one process. In a real deployment each organization runs its
own copy with only its own key.

## The monitor

`http://127.0.0.1:8899/` while the project is up. The page is compiled into the
binary (`go:embed`), so nothing else has to be started to watch the ledger, and it reads
through the same endpoints the Python client writes to — there is no second copy of the
state to drift.

It shows the organizations and whose turn the next round is, accuracy per round as a line
per model, and every committed round; clicking a round opens the model updates inside it,
with each node's `weight_hash` and how many bytes it shipped. It polls `/rounds` every
three seconds and fetches only rounds it has not seen — the ledger is append-only, so a
round that has been read never has to be read again. Start a run with
`run_experiment.py` and the rounds appear as they commit.

The **rule checks** panel fires four transactions the chaincode must refuse:

| Check | What the ledger answers |
|---|---|
| unknown identity | `no identity loaded for "Org9MSP"` (the gateway, before Fabric is touched) |
| submit into a closed round | `round 410 is already aggregated, no further updates accepted` |
| non-leader aggregates | `round 1187 belongs to Org5MSP, Org1MSP cannot aggregate it` |
| leader aggregates with no updates | `round 1187 has 0 updates, quorum is 3` |

All four are rejections, so running them writes nothing: the round count is the same
before and after. That is deliberate — the panel demonstrates the guarantees without
leaving probe data in a ledger that cannot be edited.

## The swarm client

`client/` is plain Python. One round:

1. every node loads the previous round's global model
2. it trains on its own private shard for `--local-epochs` epochs
3. it hashes the parameters and submits **the hash** — the weights never touch the ledger
4. the round's leader averages the parameters (FedAvg, weighted by sample count) and
   records the global model's hash
5. every node checks the model it was handed against the hash on the ledger

Data comes from `../image/dataset/bloodmnist.npz`, split across nodes with a Dirichlet
partition. `--alpha` controls the skew: small values give each node a lopsided class mix,
which is the realistic and difficult case. `../image/explore.ipynb` shows what different
alphas look like.

Three models share one interface (flat float64 parameter vector in, same vector out), so
the round loop never knows which it is driving:

| Model | Parameters | Why it is in the comparison |
|---|---|---|
| `logistic` | 18,824 | the cheapest thing that can separate 8 classes; the PoC's baseline |
| `mlp` | ~301k | more capacity, still blind to pixel geometry |
| `cnn` | ~57k | knows pixels have neighbours — fewer parameters than the MLP, more compute |

`run_experiment.py` runs them in turn and writes `client/results/swarm-*.json`, recording
per round: accuracy, training seconds, ledger seconds, bytes a node would ship, the leader,
who participated, and whether the hash verified.

Each model gets its own block of 100 round numbers. The ledger has a single round space
and a closed round cannot be reopened, so without that a second run would collide with the
first.

## What this does not do yet

1. **five processes, not five machines.** The nodes share one Python process, so a shard
   is handed over in memory rather than across a network. The ledger, the peers and the
   endorsement are real; the model transport is not
2. **no model transport at all, in fact.** The ledger proves *which* parameters each node
   claimed; distributing them is left to the deployment. The byte counts are measured so
   that cost is visible
3. **nothing checks that a node trained honestly.** A signed hash proves a node committed
   to a value, not that the value came from real training. Robust aggregation (Krum,
   trimmed mean) and reputation are the usual answers, and neither is implemented
4. **fixed membership.** `InitSwarm` runs once; adding or removing an organization would
   need governance transactions and a channel config update
5. **a missing leader stalls the round.** There is no timeout that lets the next node in
   the rotation close it, the way Clique and Aura do
