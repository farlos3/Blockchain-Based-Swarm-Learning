#!/usr/bin/env bash
# Bring the five-organization swarm network up, down, or deploy the chaincode onto it.
#
#   ./network.sh up       generate crypto material, start containers, create and join the channel
#   ./network.sh deploy   build, install, approve and commit the sl-ledger chaincode
#   ./network.sh stop     stop the containers, keeping the ledger
#   ./network.sh start     start them again
#   ./network.sh status   what is running and which peers joined the channel
#   ./network.sh down     stop everything and delete all generated material
#
# Everything it generates (organizations/, channel-artifacts/) is disposable: `down`
# followed by `up` always produces the same network from the two YAML files here.
#
# Under Git Bash, do NOT set MSYS_NO_PATHCONV=1: the Fabric binaries are native Windows
# executables and rely on MSYS rewriting /d/... arguments into D:\... paths for them.

set -euo pipefail

cd "$(dirname "$0")"

# One channel per dataset-and-model pair: each is its own chain, with its own blocks
# and its own round numbers starting at 1. Training cnn on two datasets is two separate
# experiments, and sharing a ledger between them would mix their rounds.
#
# Adding a dataset or a model here is the only edit needed: the gateway, the trainer
# and the page all read the resulting channel list instead of keeping their own copy.
DATASETS=${DATASETS:-"blood path"}
MODELS=${MODELS:-"logistic mlp cnn"}
CHAINCODE_NAME=${CHAINCODE_NAME:-sl-ledger}
CHAINCODE_VERSION=${CHAINCODE_VERSION:-1.0}
CHAINCODE_SEQUENCE=${CHAINCODE_SEQUENCE:-1}
CHAINCODE_PORT=9999
GATEWAY_PORT=${SL_GATEWAY_PORT:-8899}

ROOT="$(cd .. && pwd)"
ORGS="$ROOT/organizations"
ARTIFACTS="$ROOT/channel-artifacts"
export PATH="$ROOT/bin:$PATH"

ORDERER_CA="$ORGS/ordererOrganizations/swarm.local/orderers/orderer.swarm.local/msp/tlscacerts/tlsca.swarm.local-cert.pem"
ORDERER_ADMIN_CERT="$ORGS/ordererOrganizations/swarm.local/orderers/orderer.swarm.local/tls/server.crt"
ORDERER_ADMIN_KEY="$ORGS/ordererOrganizations/swarm.local/orderers/orderer.swarm.local/tls/server.key"

PEER_PORTS=(7051 8051 9051 10051 11051)
ORGS_N=(1 2 3 4 5)

# channel names allow [a-z0-9.-] only, so underscores in a name become dashes
channel_for() { echo "swarm-${1//_/-}-${2//_/-}"; }

# every dataset-model pair, one "dataset model" per line
pairs() {
  for dataset in $DATASETS; do
    for model in $MODELS; do
      echo "$dataset $model"
    done
  done
}

say() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
die() { printf '\n\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

# peer_env points the peer CLI at one organization: its admin identity, its TLS root,
# and its peer's address on localhost.
peer_env() {
  local n=$1
  export CORE_PEER_TLS_ENABLED=true
  export CORE_PEER_LOCALMSPID="Org${n}MSP"
  export CORE_PEER_MSPCONFIGPATH="$ORGS/peerOrganizations/org${n}.swarm.local/users/Admin@org${n}.swarm.local/msp"
  export CORE_PEER_TLS_ROOTCERT_FILE="$ORGS/peerOrganizations/org${n}.swarm.local/peers/peer0.org${n}.swarm.local/tls/ca.crt"
  export CORE_PEER_ADDRESS="localhost:${PEER_PORTS[$((n - 1))]}"
  export FABRIC_CFG_PATH="$ROOT/config"
}

# every_peer_args builds the --peerAddresses/--tlsRootCertFiles pairs that let one command
# reach a peer in every organization, which the commit and invoke steps need to satisfy
# the MAJORITY endorsement policy.
every_peer_args() {
  for n in "${ORGS_N[@]}"; do
    printf '%s\n%s\n%s\n%s\n' \
      --peerAddresses "localhost:${PEER_PORTS[$((n - 1))]}" \
      --tlsRootCertFiles "$ORGS/peerOrganizations/org${n}.swarm.local/peers/peer0.org${n}.swarm.local/tls/ca.crt"
  done
}

# ---------- up ----------

network_up() {
  [[ -d "$ORGS" ]] && die "organizations/ already exists — run './network.sh down' first"

  say "generating certificates for 5 organizations + the orderer"
  cryptogen generate --config=./crypto-config.yaml --output="$ORGS"

  say "building a genesis block per model channel"
  mkdir -p "$ARTIFACTS"
  while read -r dataset model; do
    channel=$(channel_for "$dataset" "$model")
    FABRIC_CFG_PATH="$PWD" configtxgen \
      -profile SwarmChannel \
      -outputBlock "$ARTIFACTS/$channel.block" \
      -channelID "$channel" 2>/dev/null
  done < <(pairs)

  say "starting the orderer, 5 peers and the gateway"
  SL_GATEWAY_PORT="$GATEWAY_PORT" docker compose -f compose.yaml up -d --build
  wait_for_orderer

  while read -r dataset model; do
    channel=$(channel_for "$dataset" "$model")
    say "creating $channel and joining all 5 organizations"
    osnadmin channel join \
      --channelID "$channel" \
      --config-block "$ARTIFACTS/$channel.block" \
      -o localhost:7053 \
      --ca-file "$ORDERER_CA" \
      --client-cert "$ORDERER_ADMIN_CERT" \
      --client-key "$ORDERER_ADMIN_KEY" > /dev/null

    for n in "${ORGS_N[@]}"; do
      peer_env "$n"
      peer channel join -b "$ARTIFACTS/$channel.block" > /dev/null
    done
  done < <(pairs)

  say "network up — 5 organizations, one channel per model, monitor on http://127.0.0.1:$GATEWAY_PORT"
  network_status
}

# wait_for_orderer polls the orderer's operations endpoint instead of sleeping a fixed
# amount: on a cold start the containers take much longer than on a warm one.
wait_for_orderer() {
  say "waiting for the orderer to accept connections"
  for _ in $(seq 1 60); do
    if curl -sf http://localhost:9440/healthz > /dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  die "the orderer did not become healthy — check 'docker logs orderer.swarm.local'"
}

# ---------- deploy ----------

# The chaincode runs as a service (Fabric's ccaas mode) rather than being built by the
# peers: the peer's built-in builder drives the Docker daemon directly, which breaks
# through Docker Desktop's socket proxy on Windows. Each organization gets its own
# chaincode container, so no org endorses through another org's process.
#
# One consequence of ccaas: the package embeds the address of that org's chaincode
# container, so every org has a *different* package id. That is fine — approveformyorg
# takes each org's own id, and only the definition (name/version/sequence) has to match.
deploy_chaincode() {
  [[ -d "$ORGS" ]] || die "no network — run './network.sh up' first"

  say "vendoring the chaincode dependencies"
  (cd "$ROOT/chaincode/$CHAINCODE_NAME" && GOFLAGS=-mod=mod go mod vendor)

  local -a package_ids=()
  for n in "${ORGS_N[@]}"; do
    package_ids[n]=$(package_for_org "$n")
    say "org${n} package id: ${package_ids[n]}"
  done

  # compose owns the chaincode containers so they belong to the same project as the
  # peers; .env is the only channel compose reads them from
  say "writing the package ids to .env and starting the chaincode services"
  : > .env
  for n in "${ORGS_N[@]}"; do
    echo "CC_ID_ORG${n}=${package_ids[n]}" >> .env
  done
  echo "SL_GATEWAY_PORT=$GATEWAY_PORT" >> .env
  channels=""
  while read -r dataset model; do
    channels="$channels,$(channel_for "$dataset" "$model")"
  done < <(pairs)
  echo "SL_CHANNELS=${channels#,}" >> .env
  docker compose -f compose.yaml --profile chaincode up -d --build

  for n in "${ORGS_N[@]}"; do
    say "installing on peer0.org${n}"
    peer_env "$n"
    peer lifecycle chaincode install "$ARTIFACTS/${CHAINCODE_NAME}-org${n}.tar.gz"
  done

  local -a peer_args=()
  peer_env 1
  # a read loop rather than mapfile: macOS ships bash 3.2, which has no mapfile
  while IFS= read -r arg; do peer_args+=("$arg"); done < <(every_peer_args)

  # install is per peer, but the definition has to be approved and committed on every
  # channel separately: each chain carries its own copy of the agreement
  while read -r dataset model; do
    channel=$(channel_for "$dataset" "$model")
    say "approving and committing on $channel"

    for n in "${ORGS_N[@]}"; do
      peer_env "$n"
      peer lifecycle chaincode approveformyorg \
        -o localhost:7050 --ordererTLSHostnameOverride orderer.swarm.local \
        --tls --cafile "$ORDERER_CA" \
        --channelID "$channel" --name "$CHAINCODE_NAME" \
        --version "$CHAINCODE_VERSION" --package-id "${package_ids[n]}" \
        --sequence "$CHAINCODE_SEQUENCE" > /dev/null 2>&1
    done

    peer_env 1
    peer lifecycle chaincode commit \
      -o localhost:7050 --ordererTLSHostnameOverride orderer.swarm.local \
      --tls --cafile "$ORDERER_CA" \
      --channelID "$channel" --name "$CHAINCODE_NAME" \
      --version "$CHAINCODE_VERSION" --sequence "$CHAINCODE_SEQUENCE" \
      "${peer_args[@]}" > /dev/null

    peer chaincode invoke \
      -o localhost:7050 --ordererTLSHostnameOverride orderer.swarm.local \
      --tls --cafile "$ORDERER_CA" \
      --channelID "$channel" --name "$CHAINCODE_NAME" \
      "${peer_args[@]}" \
      -c '{"function":"InitSwarm","Args":["[\"Org1MSP\",\"Org2MSP\",\"Org3MSP\",\"Org4MSP\",\"Org5MSP\"]","3"]}' \
      --waitForEvent > /dev/null 2>&1

    printf '  %-26s %s\n' "$channel" \
      "$(peer chaincode query -C "$channel" -n "$CHAINCODE_NAME" -c '{"function":"GetSwarmConfig","Args":[]}')"
  done < <(pairs)

  say "chaincode ready on every channel — monitor at http://127.0.0.1:$GATEWAY_PORT"
}

# package_for_org writes the ccaas package for one org and prints its package id.
# A ccaas package is a tarball of metadata.json plus code.tar.gz, where code.tar.gz holds
# only the connection details the peer should dial.
package_for_org() {
  local n=$1
  local dir="$ARTIFACTS/pkg/org${n}"
  mkdir -p "$dir"

  cat > "$dir/connection.json" <<EOF
{
  "address": "$CHAINCODE_NAME.org${n}.swarm.local:$CHAINCODE_PORT",
  "dial_timeout": "10s",
  "tls_required": false
}
EOF
  cat > "$dir/metadata.json" <<EOF
{"type":"ccaas","label":"${CHAINCODE_NAME}_${CHAINCODE_VERSION}"}
EOF

  tar -czf "$dir/code.tar.gz" -C "$dir" connection.json
  tar -czf "$ARTIFACTS/${CHAINCODE_NAME}-org${n}.tar.gz" -C "$dir" metadata.json code.tar.gz

  peer_env "$n"
  peer lifecycle chaincode calculatepackageid "$ARTIFACTS/${CHAINCODE_NAME}-org${n}.tar.gz"
}

# ---------- status / down ----------

network_status() {
  say "containers"
  CC_ID_ORG1=- CC_ID_ORG2=- CC_ID_ORG3=- CC_ID_ORG4=- CC_ID_ORG5=- \
    docker compose -f compose.yaml --profile chaincode ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
  if [[ -d "$ORGS" ]]; then
    say "one chain per dataset and model"
    peer_env 1
    while read -r dataset model; do
      channel=$(channel_for "$dataset" "$model")
      height=$(peer channel getinfo -c "$channel" 2>/dev/null | sed 's/.*"height"://; s/,.*//')
      printf '  %-6s %-9s %-26s height %s\n' "$dataset" "$model" "$channel" "${height:-not created}"
    done < <(pairs)
  fi
}

# stop and start exist because `down` destroys the ledger. Nothing restarts by itself —
# the containers carry restart: "no" — so this is how the network is paused between
# sessions without losing the chains.
network_stop() {
  say "stopping the containers, keeping volumes"
  CC_ID_ORG1=- CC_ID_ORG2=- CC_ID_ORG3=- CC_ID_ORG4=- CC_ID_ORG5=-     docker compose -f compose.yaml --profile chaincode stop
  say "stopped — './network.sh start' brings it back with the ledger intact"
}

network_start() {
  [[ -f .env ]] || die "no .env — run './network.sh up' and './network.sh deploy' first"
  say "starting the containers"
  docker compose -f compose.yaml --profile chaincode start
  wait_for_orderer
  network_status
}

network_down() {
  say "stopping every container in the project and removing volumes"
  # --profile chaincode tears those services down too; the placeholder ids only keep
  # compose parsing when .env has already been deleted
  CC_ID_ORG1=- CC_ID_ORG2=- CC_ID_ORG3=- CC_ID_ORG4=- CC_ID_ORG5=-     docker compose -f compose.yaml --profile chaincode down --volumes --remove-orphans

  say "deleting generated material"
  rm -rf "$ORGS" "$ARTIFACTS" "$ROOT/chaincode/$CHAINCODE_NAME/vendor" .env
  say "down"
}

case "${1:-}" in
  up) network_up ;;
  deploy) deploy_chaincode ;;
  stop) network_stop ;;
  start) network_start ;;
  status) network_status ;;
  down) network_down ;;
  *) die "usage: $0 {up|deploy|stop|start|status|down}" ;;
esac
