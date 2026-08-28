// Resource metrics for the running network.
//
// Every peer and the orderer already publish Prometheus metrics on their operations
// endpoint — that is what CORE_METRICS_PROVIDER and ORDERER_METRICS_PROVIDER are for in
// compose.yaml. Rather than adding a Prometheus server to scrape them, the gateway reads
// the handful of series the monitor needs and returns them as one JSON object.
//
// These are the numbers that say what the blockchain layer actually costs: how many
// blocks each node stores, how much memory and CPU it burns holding them, and how many
// proposals it refused. Put next to the training time the Python client measures, they
// are the resource half of the comparison.
package main

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"time"
)

// nodeResources is one peer's or the orderer's slice of the cost.
type nodeResources struct {
	Name               string  `json:"name"`
	Role               string  `json:"role"`
	Endpoint           string  `json:"endpoint"`
	Reachable          bool    `json:"reachable"`
	Error              string  `json:"error,omitempty"`
	// per channel, because each model type has its own chain: a single total would be
	// the sum of five unrelated experiments, which is never the number anyone wants
	Blocks             map[string]float64 `json:"blocks"`
	LedgerTransactions map[string]float64 `json:"ledger_transactions"`
	TotalBlocks        float64            `json:"total_blocks"`
	TotalTransactions  float64            `json:"total_transactions"`
	ProposalsReceived  float64 `json:"proposals_received"`
	ProposalsAccepted  float64 `json:"proposals_accepted"`
	ProposalsRejected  float64 `json:"proposals_rejected"`
	ResidentMB         float64 `json:"resident_mb"`
	HeapMB             float64 `json:"heap_mb"`
	CPUSeconds         float64 `json:"cpu_seconds"`
}

type resourceReport struct {
	ScrapedAt int64           `json:"scraped_at"`
	Channels  []string        `json:"channels"`
	Nodes     []nodeResources `json:"nodes"`
	Totals    struct {
		ResidentMB        float64 `json:"resident_mb"`
		CPUSeconds        float64 `json:"cpu_seconds"`
		ProposalsRejected float64 `json:"proposals_rejected"`
	} `json:"totals"`
	// height of each chain, taken from whichever peer reports it; every peer holds the
	// same chain, so one reading per channel is enough
	ChainHeights map[string]float64 `json:"chain_heights"`
}

// resources scrapes every node at once. One slow or dead node must not hold up the rest,
// so each gets its own short timeout and reports itself unreachable rather than failing
// the whole request — a monitor that goes blank when one peer stops is useless.
func (s *server) resources(w http.ResponseWriter, r *http.Request) {
	targets := s.metricTargets()
	report := resourceReport{ScrapedAt: time.Now().Unix(), Channels: s.channels}
	report.Nodes = make([]nodeResources, len(targets))

	var wg sync.WaitGroup
	for i, target := range targets {
		wg.Add(1)
		go func(i int, t metricTarget) {
			defer wg.Done()
			report.Nodes[i] = scrape(r.Context(), t)
		}(i, target)
	}
	wg.Wait()

	report.ChainHeights = map[string]float64{}
	for _, n := range report.Nodes {
		report.Totals.ResidentMB += n.ResidentMB
		report.Totals.CPUSeconds += n.CPUSeconds
		report.Totals.ProposalsRejected += n.ProposalsRejected
		if n.Role != "peer" {
			continue
		}
		for channel, height := range n.Blocks {
			if height > report.ChainHeights[channel] {
				report.ChainHeights[channel] = height
			}
		}
	}
	writeJSON(w, http.StatusOK, report)
}

type metricTarget struct {
	name string
	role string
	url  string
}

// metricTargets lists the orderer plus one peer per organization, in a stable order so
// the monitor's table does not reshuffle between refreshes.
func (s *server) metricTargets() []metricTarget {
	targets := []metricTarget{{name: "orderer", role: "orderer", url: s.ordererOpsURL}}
	for _, cfg := range s.orgs {
		targets = append(targets, metricTarget{name: cfg.MSPID, role: "peer", url: cfg.Ops})
	}
	return targets
}

func scrape(ctx context.Context, target metricTarget) nodeResources {
	out := nodeResources{Name: target.name, Role: target.role, Endpoint: target.url}

	ctx, cancel := context.WithTimeout(ctx, 3*time.Second)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, target.url+"/metrics", nil)
	if err != nil {
		out.Error = err.Error()
		return out
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		out.Error = fmt.Sprintf("cannot reach %s", target.url)
		return out
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		out.Error = err.Error()
		return out
	}
	text := string(body)

	out.Reachable = true
	out.Blocks = byChannel(text, "ledger_blockchain_height", "")
	out.LedgerTransactions = byChannel(text, "ledger_transaction_count", `validation_code="VALID"`)
	for _, v := range out.Blocks {
		out.TotalBlocks += v
	}
	for _, v := range out.LedgerTransactions {
		out.TotalTransactions += v
	}
	out.ProposalsReceived = sumMatching(text, "endorser_proposals_received", "")
	out.ProposalsAccepted = sumMatching(text, "endorser_successful_proposals", "")
	out.ProposalsRejected = out.ProposalsReceived - out.ProposalsAccepted
	out.ResidentMB = sumMatching(text, "process_resident_memory_bytes", "") / (1024 * 1024)
	out.HeapMB = sumMatching(text, "go_memstats_alloc_bytes", "") / (1024 * 1024)
	out.CPUSeconds = sumMatching(text, "process_cpu_seconds_total", "")
	return out
}

// byChannel groups a metric's samples by their channel label, summing the ones that share
// a channel. Fabric reports transaction counts split by chaincode and validation code, so
// several samples belong to the same chain.
func byChannel(text, metric, contains string) map[string]float64 {
	out := map[string]float64{}
	for _, line := range strings.Split(text, "\n") {
		if len(line) == 0 || line[0] == '#' || !strings.HasPrefix(line, metric) {
			continue
		}
		rest := line[len(metric):]
		if len(rest) > 0 && rest[0] != ' ' && rest[0] != '{' {
			continue
		}
		if contains != "" && !strings.Contains(rest, contains) {
			continue
		}
		channel := labelValue(rest, "channel")
		if channel == "" {
			continue
		}
		fields := strings.Fields(rest)
		if len(fields) == 0 {
			continue
		}
		if value, err := strconv.ParseFloat(fields[len(fields)-1], 64); err == nil {
			out[channel] += value
		}
	}
	return out
}

// labelValue reads one label out of a Prometheus label set: channel="swarm-cnn" -> swarm-cnn.
func labelValue(rest, label string) string {
	needle := label + `="`
	start := strings.Index(rest, needle)
	if start < 0 {
		return ""
	}
	start += len(needle)
	end := strings.Index(rest[start:], `"`)
	if end < 0 {
		return ""
	}
	return rest[start : start+end]
}

// sumMatching adds up every sample of one metric whose label set contains `contains`.
// Fabric splits ledger_transaction_count across chaincodes and validation codes, so the
// interesting number is a sum over a filter rather than a single sample.
//
// This reads Prometheus text format directly instead of pulling in a parser: the format
// is one `name{labels} value` per line, and only a fixed handful of metrics are needed.
func sumMatching(text, metric, contains string) float64 {
	total := 0.0
	for _, line := range strings.Split(text, "\n") {
		if len(line) == 0 || line[0] == '#' || !strings.HasPrefix(line, metric) {
			continue
		}
		rest := line[len(metric):]
		// guard against a prefix match: alloc_bytes must not also match alloc_bytes_total
		if len(rest) > 0 && rest[0] != ' ' && rest[0] != '{' {
			continue
		}
		if contains != "" && !strings.Contains(rest, contains) {
			continue
		}
		fields := strings.Fields(rest)
		if len(fields) == 0 {
			continue
		}
		value, err := strconv.ParseFloat(fields[len(fields)-1], 64)
		if err != nil {
			continue
		}
		total += value
	}
	return total
}
