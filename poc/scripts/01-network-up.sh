#!/usr/bin/env bash
# Bring up a 3-org (Org1, Org2, Org3) Hyperledger Fabric consortium network
# and deploy the sl-ledger chaincode so all three orgs can endorse.
set -euo pipefail

# Git Bash/MSYS rewrites bare "/var/..."-style args into
# "C:\Program Files\Git\var\..." before they reach docker.exe, which then
# fails to create the container's named-volume mount point. Scope the fix
# to the docker CLI only (a blanket MSYS_NO_PATHCONV breaks fabric-ca-client
# and configtxgen, which expect normal MSYS->Windows path conversion).
docker() { MSYS_NO_PATHCONV=1 command docker "$@"; }
export -f docker
docker-compose() { MSYS_NO_PATHCONV=1 command docker-compose "$@"; }
export -f docker-compose

HERE="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
POC_ROOT="$( cd "${HERE}/.." && pwd )"
TEST_NETWORK="${POC_ROOT}/fabric-samples/test-network"
CHANNEL=slchannel
CC_NAME=sl-ledger
CC_PATH="${POC_ROOT}/chaincode/sl-ledger"

export PATH="${POC_ROOT}/fabric-samples/bin:${PATH}"
export FABRIC_CFG_PATH="${POC_ROOT}/fabric-samples/config"

cd "${TEST_NETWORK}"

echo "[1/4] network up + create channel (Org1, Org2) with Fabric CA"
./network.sh up createChannel -c "${CHANNEL}" -ca -s couchdb

echo "[2/4] add Org3 to the consortium channel"
cd "${TEST_NETWORK}/addOrg3"
./addOrg3.sh up -c "${CHANNEL}" -ca -s couchdb

echo "[3/4] deploy sl-ledger chaincode (Org1 + Org2 install/approve/commit)"
cd "${TEST_NETWORK}"
./network.sh deployCC -c "${CHANNEL}" -ccn "${CC_NAME}" -ccp "${CC_PATH}" -ccl go

echo "[4/4] install + approve sl-ledger for Org3 (so it can endorse too)"
"${HERE}/02-join-org3-cc.sh"

echo "Network up. Channel=${CHANNEL} Chaincode=${CC_NAME} orgs=Org1,Org2,Org3"
