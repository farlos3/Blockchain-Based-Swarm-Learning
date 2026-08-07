#!/usr/bin/env bash
# Query sl-ledger (read-only, single peer, no orderer round-trip).
# Usage: cc-query.sh <org 1|2|3> <function> [arg1 arg2 ...]
set -euo pipefail

ORG="$1"; FUNC="$2"; shift 2
ARGS_JSON=$(printf '"%s",' "$@")
ARGS_JSON="[${ARGS_JSON%,}]"

HERE="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
POC_ROOT="$( cd "${HERE}/.." && pwd )"
TEST_NETWORK="${POC_ROOT}/fabric-samples/test-network"

export PATH="${POC_ROOT}/fabric-samples/bin:${PATH}"
export FABRIC_CFG_PATH="${POC_ROOT}/fabric-samples/config"

cd "${TEST_NETWORK}"
export TEST_NETWORK_HOME="${TEST_NETWORK}"
export OVERRIDE_ORG=""
export VERBOSE="false"
source scripts/utils.sh
source scripts/envVar.sh

CHANNEL_NAME=slchannel
CC_NAME=sl-ledger

setGlobals "${ORG}"

peer chaincode query -C "${CHANNEL_NAME}" -n "${CC_NAME}" \
  -c "{\"function\":\"${FUNC}\",\"Args\":${ARGS_JSON}}"
