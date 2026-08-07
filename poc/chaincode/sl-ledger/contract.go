package main

import (
	"encoding/json"
	"fmt"

	"github.com/hyperledger/fabric-contract-api-go/contractapi"
)

// SLContract records swarm-learning coordination metadata on the ledger.
// Model weights themselves stay off-chain (too large for block storage);
// only integrity hashes and round bookkeeping are committed here.
type SLContract struct {
	contractapi.Contract
}

type ModelUpdate struct {
	Round      int    `json:"round"`
	NodeID     string `json:"nodeId"`
	WeightHash string `json:"weightHash"`
	SizeBytes  int    `json:"sizeBytes"`
	Timestamp  string `json:"timestamp"`
	SubmitterMSP string `json:"submitterMsp"`
}

type Aggregation struct {
	Round             int    `json:"round"`
	AggregatedHash    string `json:"aggregatedHash"`
	ParticipantCount  int    `json:"participantCount"`
	Timestamp         string `json:"timestamp"`
	AggregatorMSP     string `json:"aggregatorMsp"`
}

const updatePrefix = "update"
const aggPrefix = "agg"

// SubmitUpdate records one node's local-training result hash for a round.
func (s *SLContract) SubmitUpdate(ctx contractapi.TransactionContextInterface, round int, nodeID string, weightHash string, sizeBytes int, timestamp string) error {
	key, err := ctx.GetStub().CreateCompositeKey(updatePrefix, []string{fmt.Sprintf("%d", round), nodeID})
	if err != nil {
		return fmt.Errorf("failed to build composite key: %w", err)
	}

	existing, err := ctx.GetStub().GetState(key)
	if err != nil {
		return fmt.Errorf("failed to read state: %w", err)
	}
	if existing != nil {
		return fmt.Errorf("node %s already submitted an update for round %d", nodeID, round)
	}

	mspID, err := ctx.GetClientIdentity().GetMSPID()
	if err != nil {
		return fmt.Errorf("failed to get submitter MSP: %w", err)
	}

	update := ModelUpdate{
		Round:        round,
		NodeID:       nodeID,
		WeightHash:   weightHash,
		SizeBytes:    sizeBytes,
		Timestamp:    timestamp,
		SubmitterMSP: mspID,
	}

	bytes, err := json.Marshal(update)
	if err != nil {
		return fmt.Errorf("failed to marshal update: %w", err)
	}

	return ctx.GetStub().PutState(key, bytes)
}

// GetRoundUpdates returns every node's submitted update for a given round.
func (s *SLContract) GetRoundUpdates(ctx contractapi.TransactionContextInterface, round int) ([]*ModelUpdate, error) {
	iter, err := ctx.GetStub().GetStateByPartialCompositeKey(updatePrefix, []string{fmt.Sprintf("%d", round)})
	if err != nil {
		return nil, fmt.Errorf("failed to query round updates: %w", err)
	}
	defer iter.Close()

	var updates []*ModelUpdate
	for iter.HasNext() {
		kv, err := iter.Next()
		if err != nil {
			return nil, err
		}
		var u ModelUpdate
		if err := json.Unmarshal(kv.Value, &u); err != nil {
			return nil, err
		}
		updates = append(updates, &u)
	}
	return updates, nil
}

// RecordAggregation records the globally merged model hash for a round,
// once every participating node's update has been folded in off-chain.
func (s *SLContract) RecordAggregation(ctx contractapi.TransactionContextInterface, round int, aggregatedHash string, participantCount int, timestamp string) error {
	key, err := ctx.GetStub().CreateCompositeKey(aggPrefix, []string{fmt.Sprintf("%d", round)})
	if err != nil {
		return fmt.Errorf("failed to build composite key: %w", err)
	}

	mspID, err := ctx.GetClientIdentity().GetMSPID()
	if err != nil {
		return fmt.Errorf("failed to get aggregator MSP: %w", err)
	}

	agg := Aggregation{
		Round:            round,
		AggregatedHash:   aggregatedHash,
		ParticipantCount: participantCount,
		Timestamp:        timestamp,
		AggregatorMSP:    mspID,
	}

	bytes, err := json.Marshal(agg)
	if err != nil {
		return fmt.Errorf("failed to marshal aggregation: %w", err)
	}

	return ctx.GetStub().PutState(key, bytes)
}

// GetAggregation returns the recorded global-model hash for a round.
func (s *SLContract) GetAggregation(ctx contractapi.TransactionContextInterface, round int) (*Aggregation, error) {
	key, err := ctx.GetStub().CreateCompositeKey(aggPrefix, []string{fmt.Sprintf("%d", round)})
	if err != nil {
		return nil, fmt.Errorf("failed to build composite key: %w", err)
	}

	bytes, err := ctx.GetStub().GetState(key)
	if err != nil {
		return nil, fmt.Errorf("failed to read state: %w", err)
	}
	if bytes == nil {
		return nil, fmt.Errorf("no aggregation recorded for round %d", round)
	}

	var agg Aggregation
	if err := json.Unmarshal(bytes, &agg); err != nil {
		return nil, err
	}
	return &agg, nil
}

// GetAllUpdates returns every update ever recorded, across all rounds.
func (s *SLContract) GetAllUpdates(ctx contractapi.TransactionContextInterface) ([]*ModelUpdate, error) {
	iter, err := ctx.GetStub().GetStateByPartialCompositeKey(updatePrefix, []string{})
	if err != nil {
		return nil, fmt.Errorf("failed to query all updates: %w", err)
	}
	defer iter.Close()

	var updates []*ModelUpdate
	for iter.HasNext() {
		kv, err := iter.Next()
		if err != nil {
			return nil, err
		}
		var u ModelUpdate
		if err := json.Unmarshal(kv.Value, &u); err != nil {
			return nil, err
		}
		updates = append(updates, &u)
	}
	return updates, nil
}
