// Command gateway exposes the sl-ledger chaincode over HTTP so the Python swarm client
// can use it.
//
// Fabric 2.5 has no supported Python SDK, and reimplementing the Gateway protocol in
// Python would mean reimplementing proposal signing and endorsement collection. Instead
// this small service holds one Fabric Gateway connection per organization and translates
// REST calls into chaincode invocations. The ML side stays plain Python.
//
// One connection per org matters: every request is signed by *that* organization's
// identity, so the chaincode's GetMSPID check sees the real submitter. A node cannot post
// as another node by changing a request body — only by holding another org's private key.
//
// Demo scope: it listens on localhost, has no authentication of its own, and loads all
// five identities. In a real deployment each organization would run its own copy with
// only its own key.
package main

import (
	"crypto/x509"
	"embed"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/hyperledger/fabric-gateway/pkg/client"
	"github.com/hyperledger/fabric-gateway/pkg/identity"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/status"
)

const chaincodeName = "sl-ledger"

// defaultChannels is only a fallback: ./network.sh deploy writes the real list into .env
// and compose passes it in as SL_CHANNELS.
const defaultChannels = "swarm-blood-logistic,swarm-blood-mlp,swarm-blood-cnn," + "swarm-path-logistic,swarm-path-mlp,swarm-path-cnn"

// The monitor page is compiled into the binary, so the gateway is the only thing that
// has to be running to watch the ledger. It reads through the same endpoints the Python
// client uses — there is no second view of the state to keep in sync.
//
//go:embed web/index.html web/compare.html
var webFS embed.FS

// When this process started. A browser tab left open keeps running the JavaScript it
// loaded, however fresh the page on the server is, so the monitor prints this on load:
// a timestamp older than the gateway means the tab is stale and needs a reload.
var startedAt = time.Now()

// orgConfig is everything needed to connect as one organization.
type orgConfig struct {
	MSPID    string
	Peer     string // host:port on the machine running this gateway
	Hostname string // the name in the peer's TLS certificate
	Dir      string // that org's directory under organizations/peerOrganizations
	Ops      string // that peer's operations endpoint, where Fabric publishes its metrics
}

// node holds one organization's live connection to its own peer, with one contract
// handle per channel. Each model trains on its own chain, so "which contract" is decided
// by the channel the request names, not by a single hard-coded one.
type node struct {
	cfg       orgConfig
	conn      *grpc.ClientConn
	gateway   *client.Gateway
	contracts map[string]*client.Contract // keyed by channel
}

func (n *node) contract(channel string) (*client.Contract, bool) {
	c, ok := n.contracts[channel]
	return c, ok
}

type server struct {
	nodes         map[string]*node // keyed by MSP ID
	orgs          []orgConfig      // in declaration order, so the monitor's tables stay stable
	channels      []string         // one per model, in declaration order
	ordererOpsURL string
	trainer       string // base URL of the Python trainer the page drives
}

// channelOf resolves the ?channel= parameter, falling back to the first one so a request
// without it still answers rather than failing.
func (s *server) channelOf(r *http.Request) (string, error) {
	name := r.URL.Query().Get("channel")
	if name == "" {
		return s.channels[0], nil
	}
	for _, known := range s.channels {
		if known == name {
			return name, nil
		}
	}
	return "", fmt.Errorf("unknown channel %q, this network has %v", name, s.channels)
}

// orgConfigs describes how to reach each organization. The addresses differ depending on
// where the gateway runs: inside the compose network it uses the container names and each
// peer's own ports, from the host it uses localhost and the published ports. Everything
// else — identities, TLS roots, the API — is identical either way.
func orgConfigs(orgsDir string, inCluster bool) []orgConfig {
	ports := []string{"7051", "8051", "9051", "10051", "11051"}
	hostOpsPorts := []string{"9441", "9442", "9443", "9444", "9445"}
	configs := make([]orgConfig, 0, len(ports))
	for i, port := range ports {
		n := i + 1
		domain := fmt.Sprintf("org%d.swarm.local", n)
		hostname := "peer0." + domain

		peer := "localhost:" + port
		ops := "http://localhost:" + hostOpsPorts[i]
		if inCluster {
			peer = hostname + ":" + port
			ops = "http://" + hostname + ":9440"
		}

		configs = append(configs, orgConfig{
			MSPID:    fmt.Sprintf("Org%dMSP", n),
			Peer:     peer,
			Hostname: hostname,
			Dir:      filepath.Join(orgsDir, "peerOrganizations", domain),
			Ops:      ops,
		})
	}
	return configs
}

// connect opens one org's gRPC channel to its peer and wraps it in a Gateway client.
// The Gateway is what collects endorsements from the other organizations, using
// discovery — which is why the anchor peers in configtx.yaml matter.
func connect(cfg orgConfig, channels []string) (*node, error) {
	tlsCert, err := loadCertPool(filepath.Join(cfg.Dir, "peers", cfg.Hostname, "tls", "ca.crt"))
	if err != nil {
		return nil, err
	}
	conn, err := grpc.NewClient(cfg.Peer,
		grpc.WithTransportCredentials(credentials.NewClientTLSFromCert(tlsCert, cfg.Hostname)))
	if err != nil {
		return nil, fmt.Errorf("cannot dial %s: %w", cfg.Peer, err)
	}

	userDir := filepath.Join(cfg.Dir, "users", "User1@"+filepath.Base(cfg.Dir))

	id, err := newIdentity(cfg.MSPID, filepath.Join(userDir, "msp", "signcerts"))
	if err != nil {
		conn.Close()
		return nil, err
	}
	sign, err := newSigner(filepath.Join(userDir, "msp", "keystore"))
	if err != nil {
		conn.Close()
		return nil, err
	}

	gw, err := client.Connect(id,
		client.WithSign(sign),
		client.WithClientConnection(conn),
		client.WithEvaluateTimeout(30*time.Second),
		client.WithEndorseTimeout(60*time.Second),
		client.WithSubmitTimeout(30*time.Second),
		client.WithCommitStatusTimeout(2*time.Minute),
	)
	if err != nil {
		conn.Close()
		return nil, fmt.Errorf("cannot connect the gateway for %s: %w", cfg.MSPID, err)
	}

	contracts := make(map[string]*client.Contract, len(channels))
	for _, channel := range channels {
		contracts[channel] = gw.GetNetwork(channel).GetContract(chaincodeName)
	}
	return &node{cfg: cfg, conn: conn, gateway: gw, contracts: contracts}, nil
}

func (n *node) close() {
	n.gateway.Close()
	n.conn.Close()
}

// ---------- HTTP ----------

func (s *server) routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /{$}", s.page("web/index.html"))
	mux.HandleFunc("GET /compare", s.page("web/compare.html"))
	mux.HandleFunc("GET /health", s.health)
	mux.HandleFunc("GET /channels", s.channelList)
	mux.HandleFunc("GET /config", s.evaluateAsAny("GetSwarmConfig"))
	mux.HandleFunc("GET /rounds", s.evaluateAsAny("GetCommittedRounds"))
	mux.HandleFunc("GET /resources", s.resources)
	mux.HandleFunc("POST /train", s.proxyToTrainer("/train"))
	mux.HandleFunc("GET /train/status", s.proxyToTrainer("/status"))
	mux.HandleFunc("GET /train/metrics", s.proxyToTrainer("/metrics"))
	mux.HandleFunc("GET /train/runs", s.proxyToTrainer("/runs"))
	mux.HandleFunc("POST /train/runs/archive", s.proxyToTrainer("/runs/archive"))
	mux.HandleFunc("POST /network/rebuild", s.proxyToTrainer("/network/rebuild"))
	mux.HandleFunc("GET /network/status", s.proxyToTrainer("/network/status"))
	mux.HandleFunc("POST /train/stop", s.proxyToTrainer("/stop"))
	mux.HandleFunc("GET /leader/{round}", s.leader)
	mux.HandleFunc("GET /rounds/{round}/updates", s.roundUpdates)
	mux.HandleFunc("GET /rounds/{round}/aggregation", s.roundAggregation)
	mux.HandleFunc("POST /nodes/{msp}/updates", s.submitUpdate)
	mux.HandleFunc("POST /nodes/{msp}/aggregations", s.recordAggregation)
	mux.HandleFunc("POST /reset", s.reset)
	return mux
}

// page serves one of the embedded pages. no-store because a tab left open across a
// redeploy keeps running the JavaScript it already loaded, and a cached copy would make
// that worse.
func (s *server) page(name string) http.HandlerFunc {
	return func(w http.ResponseWriter, _ *http.Request) {
		body, err := webFS.ReadFile(name)
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
			return
		}
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.Header().Set("Cache-Control", "no-store")
		_, _ = w.Write(body)
	}
}

func (s *server) health(w http.ResponseWriter, _ *http.Request) {
	members := make([]string, 0, len(s.nodes))
	for mspID := range s.nodes {
		members = append(members, mspID)
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"status": "ok", "channels": s.channels, "chaincode": chaincodeName,
		"identities": members, "gateway_started": startedAt.Format(time.RFC3339),
	})
}

// channelList tells the monitor which chains exist. One per model type, so the page can
// offer them as a choice instead of hard-coding names it would have to keep in step.
func (s *server) channelList(w http.ResponseWriter, _ *http.Request) {
	type entry struct {
		Channel string `json:"channel"`
		Dataset string `json:"dataset"`
		Model   string `json:"model"`
	}
	out := make([]entry, 0, len(s.channels))
	for _, channel := range s.channels {
		dataset, model := splitChannel(channel)
		out = append(out, entry{Channel: channel, Dataset: dataset, Model: model})
	}
	writeJSON(w, http.StatusOK, out)
}

// splitChannel reverses the naming rule the network script uses:
// swarm-path-cnn -> ("path", "cnn"), swarm-blood-mlp-deep -> ("blood", "mlp_deep").
// The dataset is the first segment, so a model name may contain dashes and a dataset
// name may not.
func splitChannel(channel string) (dataset, model string) {
	rest := strings.TrimPrefix(channel, "swarm-")
	dataset, tail, found := strings.Cut(rest, "-")
	if !found {
		return "", strings.ReplaceAll(rest, "-", "_")
	}
	return dataset, strings.ReplaceAll(tail, "-", "_")
}

// reader returns a contract for the requested channel, using any identity: a read gives
// the same answer whoever asks, and it is evaluated on one peer either way.
func (s *server) reader(w http.ResponseWriter, r *http.Request) (*client.Contract, bool) {
	channel, err := s.channelOf(r)
	if err != nil {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": err.Error()})
		return nil, false
	}
	for _, n := range s.nodes {
		if contract, ok := n.contract(channel); ok {
			return contract, true
		}
	}
	writeJSON(w, http.StatusInternalServerError,
		map[string]string{"error": "no connection holds channel " + channel})
	return nil, false
}

func (s *server) evaluateAsAny(fn string, args ...string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		contract, ok := s.reader(w, r)
		if !ok {
			return
		}
		raw, err := contract.EvaluateTransaction(fn, args...)
		if err != nil {
			writeChaincodeError(w, err)
			return
		}
		writeRaw(w, http.StatusOK, raw)
	}
}

func (s *server) leader(w http.ResponseWriter, r *http.Request) {
	round, err := roundParam(r)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	contract, ok := s.reader(w, r)
	if !ok {
		return
	}
	raw, err := contract.EvaluateTransaction("GetLeader", strconv.Itoa(round))
	if err != nil {
		writeChaincodeError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"round": round, "leader": string(raw)})
}

func (s *server) roundUpdates(w http.ResponseWriter, r *http.Request) {
	round, err := roundParam(r)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	contract, ok := s.reader(w, r)
	if !ok {
		return
	}
	raw, err := contract.EvaluateTransaction("GetRoundUpdates", strconv.Itoa(round))
	if err != nil {
		writeChaincodeError(w, err)
		return
	}
	writeRaw(w, http.StatusOK, raw)
}

func (s *server) roundAggregation(w http.ResponseWriter, r *http.Request) {
	round, err := roundParam(r)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	contract, ok := s.reader(w, r)
	if !ok {
		return
	}
	raw, err := contract.EvaluateTransaction("GetAggregation", strconv.Itoa(round))
	if err != nil {
		writeChaincodeError(w, err)
		return
	}
	writeRaw(w, http.StatusOK, raw)
}

type updateRequest struct {
	Round      int    `json:"round"`
	WeightHash string `json:"weight_hash"`
	SizeBytes  int    `json:"size_bytes"`
	NSamples   int    `json:"n_samples"`
	Model      string `json:"model"`
}

func (s *server) submitUpdate(w http.ResponseWriter, r *http.Request) {
	n, ok := s.nodeFor(w, r)
	if !ok {
		return
	}
	channel, err := s.channelOf(r)
	if err != nil {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": err.Error()})
		return
	}
	var req updateRequest
	if decodeErr := json.NewDecoder(r.Body).Decode(&req); decodeErr != nil {
		writeJSON(w, http.StatusBadRequest,
			map[string]string{"error": "body is not JSON: " + decodeErr.Error()})
		return
	}

	contract, ok := n.contract(channel)
	if !ok {
		writeJSON(w, http.StatusNotFound, map[string]string{
			"error": fmt.Sprintf("%s is not joined to %s", n.cfg.MSPID, channel)})
		return
	}

	started := time.Now()
	_, err = contract.SubmitTransaction("SubmitUpdate",
		strconv.Itoa(req.Round), req.WeightHash,
		strconv.Itoa(req.SizeBytes), strconv.Itoa(req.NSamples), req.Model)
	if err != nil {
		writeChaincodeError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"submitted_by": n.cfg.MSPID,
		"channel":      channel,
		"round":        req.Round,
		"latency_ms":   time.Since(started).Milliseconds(),
	})
}

type aggregationRequest struct {
	Round          int     `json:"round"`
	AggregatedHash string  `json:"aggregated_hash"`
	Accuracy       float64 `json:"accuracy"`
	Model          string  `json:"model"`
}

func (s *server) recordAggregation(w http.ResponseWriter, r *http.Request) {
	n, ok := s.nodeFor(w, r)
	if !ok {
		return
	}
	channel, err := s.channelOf(r)
	if err != nil {
		writeJSON(w, http.StatusNotFound, map[string]string{"error": err.Error()})
		return
	}
	var req aggregationRequest
	if decodeErr := json.NewDecoder(r.Body).Decode(&req); decodeErr != nil {
		writeJSON(w, http.StatusBadRequest,
			map[string]string{"error": "body is not JSON: " + decodeErr.Error()})
		return
	}

	contract, ok := n.contract(channel)
	if !ok {
		writeJSON(w, http.StatusNotFound, map[string]string{
			"error": fmt.Sprintf("%s is not joined to %s", n.cfg.MSPID, channel)})
		return
	}

	started := time.Now()
	_, err = contract.SubmitTransaction("RecordAggregation",
		strconv.Itoa(req.Round), req.AggregatedHash,
		strconv.FormatFloat(req.Accuracy, 'f', 6, 64), req.Model)
	if err != nil {
		writeChaincodeError(w, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"aggregated_by": n.cfg.MSPID,
		"channel":       channel,
		"round":         req.Round,
		"latency_ms":    time.Since(started).Milliseconds(),
	})
}

type resetRequest struct {
	Confirm  bool     `json:"confirm"`
	Channels []string `json:"channels"` // empty means every chain
}

// reset clears the recorded rounds so a new experiment starts from round 1.
//
// It needs an explicit confirm in the body: this is reachable from a browser, and a
// stray request should not be able to wipe an experiment that took an hour to produce.
// The blocks themselves are untouched — see ResetSwarm in the chaincode.
func (s *server) reset(w http.ResponseWriter, r *http.Request) {
	var req resetRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest,
			map[string]string{"error": "body is not JSON: " + err.Error()})
		return
	}
	if !req.Confirm {
		writeJSON(w, http.StatusBadRequest,
			map[string]string{"error": `send {"confirm": true} to clear the recorded rounds`})
		return
	}

	targets := req.Channels
	if len(targets) == 0 {
		targets = s.channels
	}

	// any member may reset, so the first identity is as good as another
	var actor *node
	for _, n := range s.nodes {
		actor = n
		break
	}
	if actor == nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "no identity loaded"})
		return
	}

	cleared := map[string]any{}
	for _, channel := range targets {
		contract, ok := actor.contract(channel)
		if !ok {
			cleared[channel] = "unknown channel"
			continue
		}
		raw, err := contract.SubmitTransaction("ResetSwarm")
		if err != nil {
			cleared[channel] = statusMessageOf(err)
			continue
		}
		cleared[channel] = string(raw) + " keys deleted"
	}
	writeJSON(w, http.StatusOK, map[string]any{"reset_by": actor.cfg.MSPID, "channels": cleared})
}

// statusMessageOf pulls the chaincode's own message out of Fabric's error envelope, the
// same way writeChaincodeError does, but returning it instead of writing a response.
func statusMessageOf(err error) string {
	var endorseErr *client.EndorseError
	var submitErr *client.SubmitError
	switch {
	case errors.As(err, &endorseErr):
		return statusMessage(endorseErr.GRPCStatus())
	case errors.As(err, &submitErr):
		return statusMessage(submitErr.GRPCStatus())
	}
	return err.Error()
}

func (s *server) nodeFor(w http.ResponseWriter, r *http.Request) (*node, bool) {
	mspID := r.PathValue("msp")
	n, ok := s.nodes[mspID]
	if !ok {
		writeJSON(w, http.StatusNotFound, map[string]string{
			"error": fmt.Sprintf("no identity loaded for %q", mspID),
		})
		return nil, false
	}
	return n, true
}

func roundParam(r *http.Request) (int, error) {
	round, err := strconv.Atoi(r.PathValue("round"))
	if err != nil || round < 0 {
		return 0, fmt.Errorf("round must be a non-negative integer")
	}
	return round, nil
}

// ---------- responses ----------

func writeJSON(w http.ResponseWriter, code int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(payload)
}

// writeRaw passes a chaincode JSON response straight through instead of decoding and
// re-encoding it, so the client sees exactly what the ledger holds.
func writeRaw(w http.ResponseWriter, code int, raw []byte) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_, _ = w.Write(raw)
}

// writeChaincodeError unwraps Fabric's error envelope down to the message the chaincode
// actually returned. Without this every rejected rule reads as a generic gRPC failure and
// the client cannot tell "quorum not met" from "the peer is down".
func writeChaincodeError(w http.ResponseWriter, err error) {
	message := err.Error()

	var endorseErr *client.EndorseError
	var submitErr *client.SubmitError
	var commitErr *client.CommitError
	switch {
	case errors.As(err, &endorseErr):
		message = statusMessage(endorseErr.GRPCStatus())
	case errors.As(err, &submitErr):
		message = statusMessage(submitErr.GRPCStatus())
	case errors.As(err, &commitErr):
		message = fmt.Sprintf("transaction %s was not committed: %s", commitErr.TransactionID, commitErr.Code)
	}

	// a rejected rule is the client's problem, not the gateway's
	writeJSON(w, http.StatusBadRequest, map[string]string{"error": message})
}

func statusMessage(st *status.Status) string {
	if st == nil {
		return "unknown chaincode error"
	}
	for _, detail := range st.Details() {
		if d, ok := detail.(interface{ GetMessage() string }); ok && d.GetMessage() != "" {
			return d.GetMessage()
		}
	}
	return st.Message()
}

// ---------- identity loading ----------

// loadCertPool builds a pool holding one organization's TLS root, so this client only
// trusts that org's peer and not whatever the system trust store happens to contain.
func loadCertPool(path string) (*x509.CertPool, error) {
	pem, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("cannot read the peer TLS root %s: %w", path, err)
	}
	pool := x509.NewCertPool()
	if !pool.AppendCertsFromPEM(pem) {
		return nil, fmt.Errorf("%s holds no usable certificate", path)
	}
	return pool, nil
}

func newIdentity(mspID, certDir string) (*identity.X509Identity, error) {
	certPEM, err := readFirstFile(certDir)
	if err != nil {
		return nil, fmt.Errorf("cannot read the signing certificate for %s: %w", mspID, err)
	}
	cert, err := identity.CertificateFromPEM(certPEM)
	if err != nil {
		return nil, err
	}
	return identity.NewX509Identity(mspID, cert)
}

func newSigner(keyDir string) (identity.Sign, error) {
	keyPEM, err := readFirstFile(keyDir)
	if err != nil {
		return nil, fmt.Errorf("cannot read the private key: %w", err)
	}
	key, err := identity.PrivateKeyFromPEM(keyPEM)
	if err != nil {
		return nil, err
	}
	return identity.NewPrivateKeySign(key)
}

// readFirstFile reads the only file in a directory. cryptogen names signcerts and
// keystore entries unpredictably, so the directory has exactly one file and this reads it.
func readFirstFile(dir string) ([]byte, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	for _, entry := range entries {
		if !entry.IsDir() {
			return os.ReadFile(filepath.Join(dir, entry.Name()))
		}
	}
	return nil, fmt.Errorf("%s is empty", dir)
}

// ---------- main ----------

func main() {
	inCluster := os.Getenv("SL_IN_CLUSTER") != ""

	orgsDir := os.Getenv("SL_ORGS_DIR")
	if orgsDir == "" {
		orgsDir = filepath.Join("..", "organizations")
	}
	// 8080 is the first port anything else on a dev machine claims, so the gateway sits
	// clear of it and of Fabric's own 7050-11051 range. SL_GATEWAY_ADDR overrides it.
	addr := os.Getenv("SL_GATEWAY_ADDR")
	if addr == "" {
		if inCluster {
			addr = "0.0.0.0:8899" // published by compose; binding to loopback would hide it
		} else {
			addr = "127.0.0.1:8899"
		}
	}

	ordererOps := "http://localhost:9440"
	if inCluster {
		ordererOps = "http://orderer.swarm.local:9440"
	}

	channelList := os.Getenv("SL_CHANNELS")
	if channelList == "" {
		channelList = defaultChannels
	}
	channels := strings.Split(channelList, ",")
	for i := range channels {
		channels[i] = strings.TrimSpace(channels[i])
	}

	configs := orgConfigs(orgsDir, inCluster)
	srv := &server{nodes: map[string]*node{}, orgs: configs, channels: channels,
		ordererOpsURL: ordererOps, trainer: trainerURL()}
	for _, cfg := range configs {
		n, err := connect(cfg, channels)
		if err != nil {
			log.Fatalf("cannot connect as %s: %v", cfg.MSPID, err)
		}
		defer n.close()
		log.Printf("connected as %s via %s", cfg.MSPID, cfg.Peer)
		srv.nodes[cfg.MSPID] = n
	}

	log.Printf("sl-fabric gateway listening on http://%s (trainer at %s, channels %v)",
		addr, srv.trainer, channels)
	httpServer := &http.Server{
		Addr:              addr,
		Handler:           srv.routes(),
		ReadHeaderTimeout: 10 * time.Second,
	}
	if err := httpServer.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Fatalf("gateway stopped: %v", err)
	}
}
