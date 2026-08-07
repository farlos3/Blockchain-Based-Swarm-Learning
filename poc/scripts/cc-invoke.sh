#!/usr/bin/env bash
# Submit an sl-ledger write transaction as a given org's identity.
# Usage: cc-invoke.sh <org 1|2|3> <function> [arg1 arg2 ...]
# Endorsement is collected from all three orgs (peer0.org1/2/3), matching
# the channel's default majority-of-members policy for a 3-org consortium.
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

parsePeerConnectionParameters 1 2 3
# parsePeerConnectionParameters sets PEER_CONN_PARMS and (as a side effect)
# leaves globals pointed at org 3; reset identity to the submitting org.
setGlobals "${ORG}"

peer chaincode invoke \
  -o localhost:7050 --ordererTLSHostnameOverride orderer.example.com \
  --tls --cafile "${ORDERER_CA}" \
  -C "${CHANNEL_NAME}" -n "${CC_NAME}" \
  "${PEER_CONN_PARMS[@]}" \
  -c "{\"function\":\"${FUNC}\",\"Args\":${ARGS_JSON}}" \
  --waitForEvent
