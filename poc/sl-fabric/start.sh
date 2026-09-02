#!/usr/bin/env bash
# One command from a fresh clone to a running swarm.
#
#   ./start.sh                 set up whatever is missing, bring the network up, deploy
#   ./start.sh --fresh         tear the old network down first
#   ./start.sh --train         also run the experiment once the ledger is live
#   ./start.sh --train -- --models cnn --rounds 5     args after -- go to run_experiment.py
#
# Everything here is idempotent: the steps that are already done are skipped, so
# re-running it after a failure picks up where it stopped.

set -euo pipefail
cd "$(dirname "$0")"

FABRIC_VERSION=${FABRIC_VERSION:-2.5.13}
GATEWAY_PORT=${SL_GATEWAY_PORT:-8899}
DATASET_DIR="../image/dataset"
DATASET_URL="https://huggingface.co/datasets/albertvillanova/medmnist-v2/resolve/main/data"
PYTHON=${PYTHON:-}

fresh=0
train=0
train_args=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --fresh) fresh=1 ;;
    --train) train=1 ;;
    --) shift; train_args=("$@"); break ;;
    -h|--help) sed -n '2,10p' "$0" | sed 's/^# \?//'; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 1 ;;
  esac
  shift
done

say()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
skip() { printf '\033[2m    %s\033[0m\n' "$*"; }
die()  { printf '\n\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- prerequisites

command -v docker >/dev/null || die "docker not installed"
docker info >/dev/null 2>&1  || die "docker daemon is not running — start Docker Desktop"
command -v go >/dev/null     || die "go not installed (1.23+ needed to build the gateway)"

# The Fabric CLI binaries. network.sh puts $PWD/bin on its PATH, so they belong here
# and nowhere else.
if [[ -x bin/cryptogen && -x bin/configtxgen && -x bin/osnadmin && -x bin/peer ]]; then
  skip "fabric binaries present in bin/"
else
  say "installing Fabric $FABRIC_VERSION binaries and docker images"
  [[ -f install-fabric.sh ]] || curl -sSLO \
    https://raw.githubusercontent.com/hyperledger/fabric/main/scripts/install-fabric.sh
  chmod +x install-fabric.sh
  ./install-fabric.sh --fabric-version "$FABRIC_VERSION" binary docker
fi

# The datasets client/data.py reads. Only the ones network.sh builds channels for.
mkdir -p "$DATASET_DIR"
for name in ${DATASETS:-blood path}; do
  file="${name}mnist.npz"
  if [[ -s "$DATASET_DIR/$file" ]]; then
    skip "$file present"
  else
    say "downloading $file"
    curl -fL --progress-bar -o "$DATASET_DIR/$file" "$DATASET_URL/$file"
  fi
done

# gateway/vendor is gitignored and its Dockerfile builds with -mod=vendor, so compose
# cannot build the image until this exists. (The chaincode's copy is network.sh's job.)
if [[ -d gateway/vendor ]]; then
  skip "gateway dependencies vendored"
else
  say "vendoring the gateway dependencies"
  (cd gateway && go mod vendor)
fi

# ---------------------------------------------------------------- the network

if (( fresh )); then
  say "tearing the previous network down"
  bash network/network.sh down
fi

if [[ -d organizations ]]; then
  skip "network already up (--fresh to rebuild it)"
else
  SL_GATEWAY_PORT="$GATEWAY_PORT" bash network/network.sh up
fi

# network.sh writes .env part-way through deploy, so .env alone does not mean the
# chaincode was committed. The marker is written only after deploy returns, and it
# lives under organizations/ so that `network.sh down` clears it with everything else.
if [[ -f organizations/.sl-deployed ]]; then
  skip "chaincode already deployed"
else
  SL_GATEWAY_PORT="$GATEWAY_PORT" bash network/network.sh deploy
  touch organizations/.sl-deployed
fi

say "waiting for the gateway"
for _ in $(seq 60); do
  if curl -sf "http://127.0.0.1:$GATEWAY_PORT/health" >/dev/null; then
    break
  fi
  sleep 1
done
curl -sf "http://127.0.0.1:$GATEWAY_PORT/health" >/dev/null \
  || die "gateway did not answer on $GATEWAY_PORT — 'docker compose -f network/compose.yaml logs sl-gateway'"

say "ready — monitor at http://127.0.0.1:$GATEWAY_PORT"

# ---------------------------------------------------------------- the swarm

(( train )) || {
  echo
  echo "  train:  cd client && python run_experiment.py --models logistic mlp cnn --rounds 10"
  echo "  stop:   ./network.sh stop     (keeps the ledger)"
  echo "  wipe:   ./network.sh down"
  exit 0
}

# an absolute path, because the run itself happens from client/
if [[ -z "$PYTHON" ]]; then
  for candidate in ../.venv/bin/python .venv/bin/python python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
      PYTHON=$(command -v "$candidate"); break
    fi
  done
fi
[[ -n "$PYTHON" ]] || die "no python found — set PYTHON=/path/to/python"
PYTHON=$(cd "$(dirname "$PYTHON")" && pwd)/$(basename "$PYTHON")

"$PYTHON" -c 'import numpy, sklearn, psutil, torch' 2>/dev/null \
  || die "missing python packages — $PYTHON -m pip install numpy scikit-learn psutil torch"

say "running the swarm"
(cd client && SL_GATEWAY_URL="http://127.0.0.1:$GATEWAY_PORT" \
  "$PYTHON" run_experiment.py "${train_args[@]}")
