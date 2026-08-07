package main

import (
	"log"

	"github.com/hyperledger/fabric-contract-api-go/contractapi"
)

func main() {
	chaincode, err := contractapi.NewChaincode(&SLContract{})
	if err != nil {
		log.Panicf("error creating sl-ledger chaincode: %v", err)
	}
	if err := chaincode.Start(); err != nil {
		log.Panicf("error starting sl-ledger chaincode: %v", err)
	}
}
