// sl-ledger runs as a chaincode service: the peer does not build or launch it, it dials
// this process over gRPC instead (Fabric's "chaincode as a service" mode).
//
// Two reasons for that here. The peer's built-in builder shells out to the Docker daemon,
// which is unreliable through Docker Desktop's socket proxy on Windows; and running the
// chaincode as an ordinary container means it is built once, by us, with a Dockerfile we
// can read — closer to how a real deployment ships chaincode anyway.
//
// Each organization runs its own instance, so no org endorses through another's process.
package main

import (
	"log"
	"os"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/hyperledger/fabric-contract-api-go/contractapi"
)

func main() {
	contract, err := contractapi.NewChaincode(&SmartContract{})
	if err != nil {
		log.Panicf("cannot create sl-ledger chaincode: %v", err)
	}

	ccid := os.Getenv("CHAINCODE_ID")
	address := os.Getenv("CHAINCODE_SERVER_ADDRESS")
	if ccid == "" || address == "" {
		log.Panicf("CHAINCODE_ID and CHAINCODE_SERVER_ADDRESS must both be set " +
			"(the package id comes from 'peer lifecycle chaincode calculatepackageid')")
	}

	server := &shim.ChaincodeServer{
		CCID:    ccid,
		Address: address,
		CC:      contract,
		// TLS is off between peer and chaincode: both sit on the same private Docker
		// network in this demo. A real deployment would issue a certificate here.
		TLSProps: shim.TLSProperties{Disabled: true},
	}

	log.Printf("sl-ledger listening on %s as %s", address, ccid)
	if err := server.Start(); err != nil {
		log.Panicf("cannot start sl-ledger chaincode server: %v", err)
	}
}
