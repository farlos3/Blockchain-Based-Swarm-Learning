// Package main holds sl-ledger, the chaincode that records swarm learning rounds.
//
// It enforces the same rules as poc/sl-blockchain/swarm_ledger.py, but leans on Fabric
// for the parts that PoC had to build by hand:
//
//	identity      the submitter is taken from the client certificate (GetMSPID), never
//	              from an argument, so a node cannot claim to be someone else
//	immutability  the ordering service and the peers' block store replace the hand-rolled
//	              hash chain
//	endorsement   a transaction is committed only if enough orgs ran this code and agreed
//
// What stays the same: model weights never touch the ledger, only their hash, plus the
// per-round bookkeeping needed to audit who submitted what and who aggregated.
package main

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"sort"
	"strconv"
	"strings"

	"github.com/hyperledger/fabric-contract-api-go/contractapi"
)

const (
	configKey     = "swarm-config"
	updateIndex   = "update~round~node"
	aggregatedKey = "aggregation~round"
)

// SwarmConfig is written once at InitSwarm and read by every later transaction.
// Members are MSP IDs; their order fixes the leader rotation, so it is sorted on write
// and never rewritten.
type SwarmConfig struct {
	Members []string `json:"members"`
	Quorum  int      `json:"quorum"` // minimum updates before a round may be aggregated
}

// ModelUpdate is one node's claim about its local training result for a round.
// WeightHash pins the parameters without revealing them.
type ModelUpdate struct {
	Type       string `json:"type"`
	Round      int    `json:"round"`
	NodeID     string `json:"node_id"`
	WeightHash string `json:"weight_hash"`
	SizeBytes  int    `json:"size_bytes"`
	NSamples   int    `json:"n_samples"`
	Model      string `json:"model"`     // which architecture produced it, for the comparison runs
	Timestamp  int64  `json:"timestamp"` // from the transaction, not the peer's clock
}

// Aggregation is the round leader's record of the global model it produced.
type Aggregation struct {
	Type             string   `json:"type"`
	Round            int      `json:"round"`
	Aggregator       string   `json:"aggregator"`
	AggregatedHash   string   `json:"aggregated_hash"`
	ParticipantCount int      `json:"participant_count"`
	Participants     []string `json:"participants"`
	TotalSamples     int      `json:"total_samples"`
	Accuracy         float64  `json:"accuracy"`
	Model            string   `json:"model"`
	Timestamp        int64    `json:"timestamp"`
}

// SmartContract is the chaincode entry point.
type SmartContract struct {
	contractapi.Contract
}

// ---------- helpers ----------

// caller returns the MSP ID of whoever signed this proposal. Everything that needs to
// know "who is doing this" goes through here, never through a function argument.
func caller(ctx contractapi.TransactionContextInterface) (string, error) {
	mspID, err := ctx.GetClientIdentity().GetMSPID()
	if err != nil {
		return "", fmt.Errorf("cannot read the caller identity: %w", err)
	}
	return mspID, nil
}

// txTime returns the ordering-service timestamp. time.Now() would differ between
// endorsing peers and their read-write sets would never match.
func txTime(ctx contractapi.TransactionContextInterface) (int64, error) {
	ts, err := ctx.GetStub().GetTxTimestamp()
	if err != nil {
		return 0, fmt.Errorf("cannot read the transaction timestamp: %w", err)
	}
	return ts.AsTime().Unix(), nil
}

func (s *SmartContract) config(ctx contractapi.TransactionContextInterface) (*SwarmConfig, error) {
	raw, err := ctx.GetStub().GetState(configKey)
	if err != nil {
		return nil, fmt.Errorf("cannot read the swarm config: %w", err)
	}
	if raw == nil {
		return nil, fmt.Errorf("the swarm is not initialised, call InitSwarm first")
	}
	var cfg SwarmConfig
	if err := json.Unmarshal(raw, &cfg); err != nil {
		return nil, fmt.Errorf("the stored swarm config is corrupt: %w", err)
	}
	return &cfg, nil
}

// electLeader is the same rule as consensus.py and ini_swarm.ipynb:
// sha256("round-N:member,member,...") mod member count. Every node derives it
// independently, and any auditor can recheck who was on duty for a past round.
func electLeader(round int, members []string) string {
	digest := sha256.Sum256([]byte(fmt.Sprintf("round-%d:%s", round, strings.Join(members, ","))))
	return members[digestMod(digest[:], len(members))]
}

// digestMod folds the digest byte by byte, which gives the same result as
// int(hexdigest, 16) % n in Python without needing math/big.
func digestMod(digest []byte, n int) int {
	rem := 0
	for _, b := range digest {
		rem = (rem*256 + int(b)) % n
	}
	return rem
}

func (s *SmartContract) aggregationKey(ctx contractapi.TransactionContextInterface, round int) (string, error) {
	return ctx.GetStub().CreateCompositeKey(aggregatedKey, []string{strconv.Itoa(round)})
}

// ---------- write ----------

// InitSwarm records the authority set and the quorum. Members are MSP IDs; the caller
// must be one of them, so an outsider cannot bootstrap a swarm that excludes everyone else.
func (s *SmartContract) InitSwarm(ctx contractapi.TransactionContextInterface, membersJSON string, quorum int) error {
	existing, err := ctx.GetStub().GetState(configKey)
	if err != nil {
		return fmt.Errorf("cannot read the swarm config: %w", err)
	}
	if existing != nil {
		return fmt.Errorf("the swarm is already initialised")
	}

	var members []string
	if err := json.Unmarshal([]byte(membersJSON), &members); err != nil {
		return fmt.Errorf("members must be a JSON array of MSP IDs: %w", err)
	}
	if len(members) == 0 {
		return fmt.Errorf("the swarm needs at least one member")
	}
	if quorum < 1 || quorum > len(members) {
		return fmt.Errorf("quorum must be between 1 and %d, got %d", len(members), quorum)
	}
	sort.Strings(members) // the order fixes leader rotation, so pin it here once

	me, err := caller(ctx)
	if err != nil {
		return err
	}
	if !contains(members, me) {
		return fmt.Errorf("%s cannot initialise a swarm it is not a member of", me)
	}

	raw, err := json.Marshal(SwarmConfig{Members: members, Quorum: quorum})
	if err != nil {
		return err
	}
	return ctx.GetStub().PutState(configKey, raw)
}

// SubmitUpdate records one node's local training result for a round. The node is the
// caller's MSP ID, so there is nothing to forge.
func (s *SmartContract) SubmitUpdate(ctx contractapi.TransactionContextInterface,
	round int, weightHash string, sizeBytes int, nSamples int, model string) error {

	cfg, err := s.config(ctx)
	if err != nil {
		return err
	}
	me, err := caller(ctx)
	if err != nil {
		return err
	}
	if !contains(cfg.Members, me) {
		return fmt.Errorf("%s is not a member of this swarm", me)
	}
	if len(weightHash) != 64 {
		return fmt.Errorf("weight_hash must be a 64-character sha256 hex digest")
	}
	if nSamples <= 0 {
		return fmt.Errorf("n_samples must be positive, got %d", nSamples)
	}

	closed, err := s.roundClosed(ctx, round)
	if err != nil {
		return err
	}
	if closed {
		return fmt.Errorf("round %d is already aggregated, no further updates accepted", round)
	}

	key, err := ctx.GetStub().CreateCompositeKey(updateIndex, []string{strconv.Itoa(round), me})
	if err != nil {
		return err
	}
	prior, err := ctx.GetStub().GetState(key)
	if err != nil {
		return fmt.Errorf("cannot read prior updates: %w", err)
	}
	if prior != nil {
		return fmt.Errorf("%s already submitted an update for round %d", me, round)
	}

	when, err := txTime(ctx)
	if err != nil {
		return err
	}
	raw, err := json.Marshal(ModelUpdate{
		Type: "model_update", Round: round, NodeID: me, WeightHash: weightHash,
		SizeBytes: sizeBytes, NSamples: nSamples, Model: model, Timestamp: when,
	})
	if err != nil {
		return err
	}
	return ctx.GetStub().PutState(key, raw)
}

// RecordAggregation closes a round. Only that round's leader may call it, only once,
// and only when the quorum has been reached.
func (s *SmartContract) RecordAggregation(ctx contractapi.TransactionContextInterface,
	round int, aggregatedHash string, accuracy float64, model string) error {

	cfg, err := s.config(ctx)
	if err != nil {
		return err
	}
	me, err := caller(ctx)
	if err != nil {
		return err
	}
	expected := electLeader(round, cfg.Members)
	if me != expected {
		return fmt.Errorf("round %d belongs to %s, %s cannot aggregate it", round, expected, me)
	}
	if len(aggregatedHash) != 64 {
		return fmt.Errorf("aggregated_hash must be a 64-character sha256 hex digest")
	}

	closed, err := s.roundClosed(ctx, round)
	if err != nil {
		return err
	}
	if closed {
		return fmt.Errorf("round %d already has an aggregation", round)
	}

	updates, err := s.GetRoundUpdates(ctx, round)
	if err != nil {
		return err
	}
	if len(updates) < cfg.Quorum {
		return fmt.Errorf("round %d has %d updates, quorum is %d", round, len(updates), cfg.Quorum)
	}

	participants := make([]string, 0, len(updates))
	total := 0
	for _, u := range updates {
		participants = append(participants, u.NodeID)
		total += u.NSamples
	}
	sort.Strings(participants)

	when, err := txTime(ctx)
	if err != nil {
		return err
	}
	raw, err := json.Marshal(Aggregation{
		Type: "aggregation", Round: round, Aggregator: me, AggregatedHash: aggregatedHash,
		ParticipantCount: len(updates), Participants: participants, TotalSamples: total,
		Accuracy: accuracy, Model: model, Timestamp: when,
	})
	if err != nil {
		return err
	}
	key, err := s.aggregationKey(ctx, round)
	if err != nil {
		return err
	}
	return ctx.GetStub().PutState(key, raw)
}

// ResetSwarm clears every recorded round so experiments can start from round 1 again.
//
// It does not, and cannot, delete blocks: the history of what was submitted stays in the
// chain forever, and this reset is itself a transaction in it. What it clears is the
// world state — the current answer to "which rounds exist" — which is what the duplicate
// and closed-round checks read. An auditor replaying the blocks still sees both the old
// rounds and the moment someone wiped them, and by whom.
//
// The authority set and quorum survive: resetting an experiment is not the same as
// re-founding the swarm.
func (s *SmartContract) ResetSwarm(ctx contractapi.TransactionContextInterface) (int, error) {
	cfg, err := s.config(ctx)
	if err != nil {
		return 0, err
	}
	me, err := caller(ctx)
	if err != nil {
		return 0, err
	}
	if !contains(cfg.Members, me) {
		return 0, fmt.Errorf("%s is not a member of this swarm", me)
	}

	deleted := 0
	for _, prefix := range []string{updateIndex, aggregatedKey} {
		iter, err := ctx.GetStub().GetStateByPartialCompositeKey(prefix, []string{})
		if err != nil {
			return 0, fmt.Errorf("cannot list %s for reset: %w", prefix, err)
		}
		keys := []string{}
		for iter.HasNext() {
			item, err := iter.Next()
			if err != nil {
				iter.Close()
				return 0, err
			}
			keys = append(keys, item.Key)
		}
		iter.Close()

		// delete after the iterator is closed: deleting while ranging over the same
		// prefix is undefined
		for _, key := range keys {
			if err := ctx.GetStub().DelState(key); err != nil {
				return 0, fmt.Errorf("cannot delete %s: %w", key, err)
			}
			deleted++
		}
	}
	return deleted, nil
}

// ---------- read ----------

// GetRoundUpdates returns every update recorded for a round, ordered by node ID.
func (s *SmartContract) GetRoundUpdates(ctx contractapi.TransactionContextInterface, round int) ([]*ModelUpdate, error) {
	iter, err := ctx.GetStub().GetStateByPartialCompositeKey(updateIndex, []string{strconv.Itoa(round)})
	if err != nil {
		return nil, fmt.Errorf("cannot read the updates for round %d: %w", round, err)
	}
	defer iter.Close()

	updates := []*ModelUpdate{}
	for iter.HasNext() {
		item, err := iter.Next()
		if err != nil {
			return nil, err
		}
		var u ModelUpdate
		if err := json.Unmarshal(item.Value, &u); err != nil {
			return nil, fmt.Errorf("a stored update is corrupt: %w", err)
		}
		updates = append(updates, &u)
	}
	sort.Slice(updates, func(i, j int) bool { return updates[i].NodeID < updates[j].NodeID })
	return updates, nil
}

// GetAggregation returns a round's aggregation, or an error if the round is still open.
func (s *SmartContract) GetAggregation(ctx contractapi.TransactionContextInterface, round int) (*Aggregation, error) {
	key, err := s.aggregationKey(ctx, round)
	if err != nil {
		return nil, err
	}
	raw, err := ctx.GetStub().GetState(key)
	if err != nil {
		return nil, fmt.Errorf("cannot read the aggregation for round %d: %w", round, err)
	}
	if raw == nil {
		return nil, fmt.Errorf("round %d has no aggregation", round)
	}
	var a Aggregation
	if err := json.Unmarshal(raw, &a); err != nil {
		return nil, fmt.Errorf("the stored aggregation is corrupt: %w", err)
	}
	return &a, nil
}

// GetCommittedRounds lists the rounds that have been aggregated, in order.
func (s *SmartContract) GetCommittedRounds(ctx contractapi.TransactionContextInterface) ([]int, error) {
	iter, err := ctx.GetStub().GetStateByPartialCompositeKey(aggregatedKey, []string{})
	if err != nil {
		return nil, fmt.Errorf("cannot list the committed rounds: %w", err)
	}
	defer iter.Close()

	rounds := []int{}
	for iter.HasNext() {
		item, err := iter.Next()
		if err != nil {
			return nil, err
		}
		var a Aggregation
		if err := json.Unmarshal(item.Value, &a); err != nil {
			return nil, fmt.Errorf("a stored aggregation is corrupt: %w", err)
		}
		rounds = append(rounds, a.Round)
	}
	sort.Ints(rounds)
	return rounds, nil
}

// GetSwarmConfig exposes the authority set and quorum so a client can derive leaders itself.
func (s *SmartContract) GetSwarmConfig(ctx contractapi.TransactionContextInterface) (*SwarmConfig, error) {
	return s.config(ctx)
}

// GetLeader answers whose turn a round is. Pure function of the round and the member
// list, so a client can compute it without asking, and use this to check itself.
func (s *SmartContract) GetLeader(ctx contractapi.TransactionContextInterface, round int) (string, error) {
	cfg, err := s.config(ctx)
	if err != nil {
		return "", err
	}
	return electLeader(round, cfg.Members), nil
}

// WhoAmI returns the caller's MSP ID. Used by the gateway to confirm which identity a
// wallet actually carries before a node starts submitting as someone it is not.
func (s *SmartContract) WhoAmI(ctx contractapi.TransactionContextInterface) (string, error) {
	return caller(ctx)
}

// ---------- small internals ----------

func (s *SmartContract) roundClosed(ctx contractapi.TransactionContextInterface, round int) (bool, error) {
	key, err := s.aggregationKey(ctx, round)
	if err != nil {
		return false, err
	}
	raw, err := ctx.GetStub().GetState(key)
	if err != nil {
		return false, fmt.Errorf("cannot check whether round %d is closed: %w", round, err)
	}
	return raw != nil, nil
}

func contains(list []string, want string) bool {
	for _, item := range list {
		if item == want {
			return true
		}
	}
	return false
}

