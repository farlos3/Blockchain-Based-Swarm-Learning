# sl-blockchain

A small blockchain for the **Blockchain-Based Swarm Learning** PoC, written in Python.
It uses **Proof of Authority (PoA)** as its consensus mechanism — no Docker, no network
setup, everything runs on one machine.

Designed as the step before moving to Hyperledger Fabric: method and field names match
the `sl-ledger` chaincode already written (`SubmitUpdate` / `RecordAggregation` /
`GetRoundUpdates` / `GetAggregation`), so swapping the backend changes as little
node-side code as possible.

## Files

| File | Purpose |
|---|---|
| `blockchain.py` | `Block` + `Blockchain` — hash chain, `validate()`, save/load JSON |
| `consensus.py` | `ProofOfAuthority` (default) + `ProofOfWork` (for comparison), ed25519 keys, the leader rule |
| `swarm_ledger.py` | `SwarmLedger` — the swarm learning layer, signed transactions, `audit_chain()` |
| `demo.py` | A 5-node, 3-round demo + the rejected rules + two attempts at rewriting history |
| `test_swarm_ledger.py` | 28 test cases (runs with or without pytest) |
| `web/server.py` | Web simulator — a thin HTTP API over the same `SwarmLedger` `demo.py` uses |
| `web/index.html` | The simulator's page (no external dependencies) |

## Running

```bash
cd poc
.venv/bin/python sl-blockchain/demo.py              # terminal demo
.venv/bin/python sl-blockchain/test_swarm_ledger.py # tests
.venv/bin/python sl-blockchain/web/server.py        # web simulator (port 8000)
```

`cryptography` is required for the ed25519 signatures (already in `poc/requirements.txt`)

## Web simulator

`demo.py` runs straight through to the end; the web simulator lets you take one step at a
time and watch what changes in the chain. Useful when presenting, or for capturing figures.

```bash
python sl-blockchain/web/server.py        # http://127.0.0.1:8000
python sl-blockchain/web/server.py 9000   # different port
```

The browser simulates nothing on its own. Every button sends an HTTP request that calls the
real `SwarmLedger`, so the ed25519 signatures, the leader election, and the rejection rules
are the same ones the tests cover.

| Panel | What it does |
|---|---|
| authority set | each node's public key + the leaders of the next 5 rounds (derived from the rule, not remembered) |
| current round | `submit_update` one node at a time, or run a whole round and let the leader seal it |
| verify the global model | `verify_round()` against the real parameters and against ones altered by `1e-9` |
| rules the ledger rejects | fires the same 6 rule-breaking transactions as `demo.py` and shows why each is refused |
| rewriting history | edits a copy of the chain (mid-chain / last block with a recomputed hash) for `validate()` to catch |
| the chain | click through a block's transactions, `prev_hash`, `tx_root`, and the sealer's signature |

State lives in the process's memory and is gone when the server stops — press
"Save to chain.json" to write it out and have `audit_chain()` re-verify it from the file.

This is a local demo server. It binds to `127.0.0.1` only, has no user authentication, and
anyone who can open the page can sign transactions on behalf of every node (the PoC keeps
all node keys in one process). Do not expose it to a public network.

## Why Proof of Authority

Our swarm is a consortium whose members already know each other (each organization joins by
agreement). The problem is not "anyone can show up and mine" but "prove that an authorized
node really sealed this block".

- **PoW** solves Sybil attacks on open networks, paid for in CPU and time — there is no Sybil
  problem here to begin with, so burning CPU only adds a power bill and latency (still
  available, so the thesis can show the comparison)
- **PoA** ties the right to seal to a published identity, at nearly zero cost per block, and
  matches Fabric's model (what you may do depends on who you are, not how much compute you have)

PoA here has the three parts the definition calls for:

| Part | How it works here |
|---|---|
| **authority set** | `node_id -> ed25519 public key`, published on the chain (private keys stay with their node) |
| **leader rule** | `sha256(round number + member list) mod member count`, computed independently by every node with the same result |
| **block seal** | the leader signs the block hash with its own private key; anyone holding the chain file can check it |

`elect_leader()` is the **same formula used in `ini_swarm.ipynb`** — change it in one file and
the chain immediately rejects the notebook's aggregations.

## What goes on the chain

Real model weights **never touch the chain**: they are far too large for a block, and putting
them there would defeat the reason for using swarm learning in the first place. The chain
holds hashes and the round ledger, nothing more.

**Convention: 1 swarm round = 1 block** — one block holds every node's `model_update` for that
round, closed by the leader's `aggregation`. Every transaction carries its sender's signature.

```jsonc
// model_update — a node announces its local training result
{"type": "model_update", "round": 1, "node_id": "A", "weight_hash": "aae85fb3…",
 "size_bytes": 88, "n_samples": 240, "timestamp": 1755…, "signature": "8f61ea7b…"}

// aggregation — the leader announces the round's global model
{"type": "aggregation", "round": 1, "aggregator": "D", "aggregated_hash": "4c1f…",
 "participant_count": 5, "total_samples": 680, "accuracy": 0.82,
 "timestamp": 1755…, "signature": "00aa333b…"}
```

Beyond the transactions inside it, a block carries `sealer` (who sealed it) and `seal`
(the signature over the block hash).

## Rules that are enforced

This section is what makes it blockchain-based rather than a log file: transactions that break
a rule are rejected, the way chaincode rejects a transaction (`demo.py` demonstrates all of them):

| Rule | Fabric equivalent |
|---|---|
| the sender must be in the authority set | MSP membership |
| the signature must match the published public key | checking the sender's certificate |
| one node may submit once per round | the duplicate composite-key check in `SubmitUpdate` |
| the sealer must be that round's leader | the `AggregatorMSP` check |
| a closed round cannot be modified | the ledger is append-only |

Rewriting history is caught at three layers:

1. edit a mid-chain block -> the next block's `prev_hash` no longer matches
2. edit the last block -> it no longer matches the hash stored in the file
3. edit it and recompute the hash to match -> **it still fails at the leader's signature**,
   because the attacker has no private key
   <- this is what PoA buys, and what a bare hash chain cannot give you

## Verifying without trusting anyone

```python
from swarm_ledger import audit_chain
audit_chain("chain.json")
# {'consensus': 'poa', 'blocks': 3, 'transactions_verified': 18,
#  'authorities': ['A', 'B', 'C', 'D', 'E']}
```

Someone holding nothing but the chain file can verify all three layers themselves (chain
structure + the sealer's signature and turn + every transaction signature), because every
node's public key is in the file.

## Using it from the notebook

`ini_swarm.ipynb` already has the swarm loop; the ledger can be added without touching the
training logic:

```python
import sys; sys.path.append("sl-blockchain")
from swarm_ledger import SwarmLedger

ledger = SwarmLedger.bootstrap(NODE_NAMES, seed="poc")   # in production each node makes its own key

# inside the loop, after each node's local_train
ledger.submit_update(round_num, name, coef, intercept, len(y_nodes[name]))

# after aggregate()
ledger.record_aggregation(round_num, leader, global_coef, global_intercept, swarm_acc)

# once all rounds are done
print(ledger.audit(), ledger.leader_counts(), ledger.ledger_bytes(), "bytes")
ledger.chain.save("swarm_chain.json")
```

A node receiving the global model can check it got the real thing with
`ledger.verify_round(round_num, coef, intercept)`.

## Not in this version

In the order they should be tackled:

1. **Real multi-machine operation** — everything is in-process today, every node shares one
   ledger object. There is no networking and no agreement on who holds the correct chain
   (fork resolution)
2. **Authority set management** — membership is fixed at creation; members cannot be added or
   removed later. In production this needs governance transactions that existing members endorse
3. **A missing leader** — if a round's leader goes offline the system stalls; there is no timeout
   that moves on to the next node (Clique/Aura solve this by letting others seal after a delay)
4. **A Merkle tree** — `tx_root` is currently a single hash over all of a block's transactions,
   so it cannot prove "this transaction is in this block" without sending the whole block
5. **Moving to Fabric** — swap only `SwarmLedger`'s backend to call the `sl-ledger` chaincode,
   while nodes keep calling the same method names
