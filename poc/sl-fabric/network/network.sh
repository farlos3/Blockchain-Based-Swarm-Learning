#!/usr/bin/env bash
# Bring the ten-organization swarm network up, down, or deploy the chaincode onto it.
#
#   ./network.sh up       generate crypto material, start containers, create and join the channels
#   ./network.sh deploy   create any channel swarms.conf added, then build, install, approve
#                         and commit the sl-ledger chaincode where it is not yet
#   ./network.sh stop     stop the containers, keeping the ledger
#   ./network.sh start     start them again
#   ./network.sh status   what is running and how far each configured chain has grown
#   ./network.sh down     stop everything and delete all generated material
#
# Everything it generates (organizations/, channel-artifacts/) is disposable: `down`
# followed by `up` always produces the same network from swarms.conf and the YAML files.
#
# Under Git Bash, do NOT set MSYS_NO_PATHCONV=1: the Fabric binaries are native Windows
# executables and rely on MSYS rewriting /d/... arguments into D:\... paths for them.

set -euo pipefail

cd "$(dirname "$0")"

# One channel per dataset-and-model pair: each is its own chain, with its own blocks
# and its own round numbers starting at 1. Training one model on two datasets is two
# separate experiments, and sharing a ledger between them would mix their rounds.
#
# Which pairs exist, and how many organizations each dataset's swarm has, is read from
# swarms.conf; the gateway and its monitor read the resulting channel list from .env.
SWARMS=${SWARMS:-swarms.conf}
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

PEER_PORTS=(7051 8051 9051 10051 11051 12051 13051 14051 15051 16051)
ORGS_N=(1 2 3 4 5 6 7 8 9 10)

# channel names allow [a-z0-9.-] only, so underscores in a name become dashes
channel_for() { echo "swarm-${1//_/-}-${2//_/-}"; }

# swarms prints swarms.conf's "dataset orgs model..." lines, without comments or blanks
swarms() { sed -e 's/#.*//' -e '/^[[:space:]]*$/d' "$SWARMS"; }

# every dataset-model pair, one "dataset model" per line
pairs() {
  local dataset orgs models model
  while read -r dataset orgs models; do
    for model in $models; do
      echo "$dataset $model"
    done
  done < <(swarms)
}

# members_of says how many organizations a dataset's swarm has; the swarm is always
# Org1..OrgN
members_of() { swarms | awk -v d="$1" '$1 == d { print $2; exit }'; }

# check_swarms refuses a swarms.conf the network cannot build, before anything is created
check_swarms() {
  [[ -f "$SWARMS" ]] || die "no $SWARMS"
  local dataset orgs models model seen=" "
  while read -r dataset orgs models; do
    [[ "$dataset" =~ ^[a-z0-9]+$ ]] || die "$SWARMS: dataset '$dataset' must be lower-case letters and digits"
    [[ "$seen" != *" $dataset "* ]] || die "$SWARMS: dataset '$dataset' appears twice"
    seen="$seen$dataset "
    [[ "$orgs" =~ ^[0-9]+$ ]] && (( orgs >= 1 && orgs <= ${#ORGS_N[@]} )) \
      || die "$SWARMS: '$dataset' needs 1..${#ORGS_N[@]} organizations, got '$orgs'"
    grep -q "^  Swarm${orgs}:" configtx.yaml \
      || die "$SWARMS: '$dataset' has $orgs organizations, but configtx.yaml has no Swarm${orgs} profile"
    [[ -n "$models" ]] || die "$SWARMS: '$dataset' lists no models"
    for model in $models; do
      [[ "$model" =~ ^[a-z0-9_]+$ ]] || die "$SWARMS: model '$model' must be lower-case letters, digits or _"
    done
  done < <(swarms)
  [[ -n "$(pairs)" ]] || die "$SWARMS lists no swarms"
}

# write_env writes .env, which compose reads: the gateway's port and channel list, and the
# chaincode package id of each organization once deploy has computed them
write_env() {
  local channels="" dataset model n
  while read -r dataset model; do
    channels="$channels,$(channel_for "$dataset" "$model")"
  done < <(pairs)
  {
    echo "SL_GATEWAY_PORT=$GATEWAY_PORT"
    echo "SL_CHANNELS=${channels#,}"
    for n in "${ORGS_N[@]}"; do
      [[ -z "${package_ids[n]:-}" ]] || echo "CC_ID_ORG${n}=${package_ids[n]}"
    done
  } > .env
}
declare -a package_ids=()

# orgs_upto N prints 1..N, the organization numbers of an N-member swarm
orgs_upto() { seq 1 "$1"; }

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

# every_peer_args N builds the --peerAddresses/--tlsRootCertFiles pairs that let one
# command reach a peer in every organization of an N-member swarm, which the commit and
# invoke steps need to satisfy that channel's MAJORITY endorsement policy.
every_peer_args() {
  local n
  for n in $(orgs_upto "$1"); do
    printf '%s\n%s\n%s\n%s\n' \
      --peerAddresses "localhost:${PEER_PORTS[$((n - 1))]}" \
      --tlsRootCertFiles "$ORGS/peerOrganizations/org${n}.swarm.local/peers/peer0.org${n}.swarm.local/tls/ca.crt"
  done
}

# ---------- up ----------

network_up() {
  [[ -d "$ORGS" ]] && die "organizations/ already exists — run './network.sh down' first"
  check_swarms

  say "generating certificates for ${#ORGS_N[@]} organizations + the orderer"
  cryptogen generate --config=./crypto-config.yaml --output="$ORGS"

  say "starting the orderer, ${#ORGS_N[@]} peers and the gateway"
  write_env
  docker compose -f compose.yaml up -d --build
  wait_for_orderer

  while read -r dataset model; do
    create_channel "$dataset" "$model"
  done < <(pairs)

  say "network up — ${#ORGS_N[@]} organizations, one channel per model, monitor on http://127.0.0.1:$GATEWAY_PORT"
  network_status
}

# create_channel builds a channel's genesis block from its swarm's SwarmN profile, starts
# the channel on the orderer and joins that swarm's organizations to it
create_channel() {
  local dataset=$1 model=$2 channel orgs n
  channel=$(channel_for "$dataset" "$model")
  orgs=$(members_of "$dataset")
  say "creating $channel and joining its $orgs organizations"
  mkdir -p "$ARTIFACTS"
  FABRIC_CFG_PATH="$PWD" configtxgen \
    -profile "Swarm$orgs" \
    -outputBlock "$ARTIFACTS/$channel.block" \
    -channelID "$channel" 2>/dev/null
  osnadmin channel join \
    --channelID "$channel" \
    --config-block "$ARTIFACTS/$channel.block" \
    -o localhost:7053 \
    --ca-file "$ORDERER_CA" \
    --client-cert "$ORDERER_ADMIN_CERT" \
    --client-key "$ORDERER_ADMIN_KEY" > /dev/null
  for n in $(orgs_upto "$orgs"); do
    peer_env "$n"
    peer channel join -b "$ARTIFACTS/$channel.block" > /dev/null
  done
}

# channel_exists asks Org1's peer, which joins every channel, whether a channel is there
channel_exists() {
  peer_env 1
  peer channel getinfo -c "$1" > /dev/null 2>&1
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
  check_swarms

  # a pair swarms.conf gained since `up` gets its channel now, on the running network
  while read -r dataset model; do
    channel_exists "$(channel_for "$dataset" "$model")" || create_channel "$dataset" "$model"
  done < <(pairs)

  say "vendoring the chaincode dependencies"
  (cd "$ROOT/chaincode/$CHAINCODE_NAME" && GOFLAGS=-mod=mod go mod vendor)

  for n in "${ORGS_N[@]}"; do
    package_ids[n]=$(package_for_org "$n")
    say "org${n} package id: ${package_ids[n]}"
  done

  # compose owns the chaincode containers so they belong to the same project as the
  # peers; .env is the only channel compose reads them from. A changed channel list
  # recreates the gateway, which is how it learns about the new chains.
  say "writing the package ids and channels to .env and starting the chaincode services"
  write_env
  docker compose -f compose.yaml --profile chaincode up -d --build

  # Every step below is skipped when it has already happened, so a deploy cut short — ten
  # peers behind Docker Desktop's port forwarding do occasionally time out a connection —
  # is finished by running deploy again rather than by tearing the network down.
  for n in "${ORGS_N[@]}"; do
    peer_env "$n"
    if peer lifecycle chaincode queryinstalled 2>/dev/null | grep -q "${package_ids[n]}"; then
      say "already installed on peer0.org${n}"
      continue
    fi
    say "installing on peer0.org${n}"
    peer lifecycle chaincode install "$ARTIFACTS/${CHAINCODE_NAME}-org${n}.tar.gz"
  done

  # install is per peer, but the definition has to be approved and committed on every
  # channel separately, by that channel's own members: each chain carries its own copy of
  # the agreement
  while read -r dataset model; do
    channel=$(channel_for "$dataset" "$model")
    peer_env 1
    local config
    if config=$(peer chaincode query -C "$channel" -n "$CHAINCODE_NAME" \
        -c '{"function":"GetSwarmConfig","Args":[]}' 2>/dev/null); then
      printf '  %-26s %s (already deployed)\n' "$channel" "$config"
      continue
    fi
    local size members quorum
    size=$(members_of "$dataset")
    # the authority set as a JSON array, and a majority quorum: no minority of the swarm
    # can close a round (3 of 5 for the image swarm, as before)
    members=$(orgs_upto "$size" | sed 's/.*/\\"Org&MSP\\"/' | paste -sd, -)
    quorum=$((size / 2 + 1))
    say "approving and committing on $channel ($size organizations, quorum $quorum)"

    local -a peer_args=()
    # a read loop rather than mapfile: macOS ships bash 3.2, which has no mapfile
    while IFS= read -r arg; do peer_args+=("$arg"); done < <(every_peer_args "$size")

    peer_env 1
    if ! peer lifecycle chaincode querycommitted -C "$channel" -n "$CHAINCODE_NAME" > /dev/null 2>&1; then
      # approving an unchanged definition twice is an error, so approve only the orgs the
      # channel does not yet count as approved
      local readiness
      readiness=$(peer lifecycle chaincode checkcommitreadiness \
        --channelID "$channel" --name "$CHAINCODE_NAME" \
        --version "$CHAINCODE_VERSION" --sequence "$CHAINCODE_SEQUENCE" --output json)
      for n in $(orgs_upto "$size"); do
        grep -q "\"Org${n}MSP\": true" <<< "$readiness" && continue
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
    fi

    peer chaincode invoke \
      -o localhost:7050 --ordererTLSHostnameOverride orderer.swarm.local \
      --tls --cafile "$ORDERER_CA" \
      --channelID "$channel" --name "$CHAINCODE_NAME" \
      "${peer_args[@]}" \
      -c "{\"function\":\"InitSwarm\",\"Args\":[\"[$members]\",\"$quorum\"]}" \
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
  local package="$ARTIFACTS/${CHAINCODE_NAME}-org${n}.tar.gz"
  peer_env "$n"
  # an existing package is reused, never rebuilt: tar and gzip stamp the time, so a fresh
  # tarball would get a new package id that no channel has approved
  if [[ -f "$package" ]]; then
    peer lifecycle chaincode calculatepackageid "$package"
    return
  fi
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
  tar -czf "$package" -C "$dir" metadata.json code.tar.gz
  peer lifecycle chaincode calculatepackageid "$package"
}

# ---------- status / down ----------

# compose_all runs docker compose over every service, chaincode included, for commands
# that never start the chaincode. Placeholder package ids keep compose parsing when .env
# has not been written yet or has already been deleted.
compose_all() {
  local n
  for n in "${ORGS_N[@]}"; do export "CC_ID_ORG$n=-"; done
  docker compose -f compose.yaml --profile chaincode "$@"
}

network_status() {
  say "containers"
  compose_all ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"
  if [[ -d "$ORGS" ]]; then
    say "one chain per dataset and model"
    peer_env 1
    while read -r dataset model; do
      channel=$(channel_for "$dataset" "$model")
      height=$(peer channel getinfo -c "$channel" 2>/dev/null | sed 's/.*"height"://; s/,.*//')
      printf '  %-8s %-11s %-28s %2s orgs  height %s\n' "$dataset" "$model" "$channel" \
        "$(members_of "$dataset")" "${height:-not created}"
    done < <(pairs)
  fi
}

# stop and start exist because `down` destroys the ledger. Nothing restarts by itself —
# the containers carry restart: "no" — so this is how the network is paused between
# sessions without losing the chains.
network_stop() {
  say "stopping the containers, keeping volumes"
  compose_all stop
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
  # --profile chaincode tears those services down too
  compose_all down --volumes --remove-orphans

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
