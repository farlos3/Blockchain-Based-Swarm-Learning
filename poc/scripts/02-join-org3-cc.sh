#!/usr/bin/env bash
# Install + approve the already-committed sl-ledger chaincode for Org3,
# so all three consortium members can endorse (mirrors the official
# Fabric addOrg3 tutorial). Must run after 01-network-up.sh's deployCC step.
# NOTE: no `-e` here — installChaincode/approveForMyOrg (from fabric-samples'
# own ccutils.sh) intentionally let a "not installed yet" pipeline return
# non-zero and check it manually via $?; errexit would abort on that.
set -uo pipefail

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
source scripts/ccutils.sh

CHANNEL_NAME=slchannel
CC_NAME=sl-ledger
CC_VERSION=1.0
CC_SEQUENCE=1
INIT_REQUIRED=""
CC_END_POLICY=""
CC_COLL_CONFIG=""

PACKAGE_ID=$(peer lifecycle chaincode calculatepackageid ${CC_NAME}.tar.gz)
echo "PACKAGE_ID=${PACKAGE_ID}"

installChaincode 3
approveForMyOrg 3

echo "Org3 can now endorse ${CC_NAME} on ${CHANNEL_NAME}."
