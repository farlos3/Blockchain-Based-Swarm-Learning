// Proxying the training controls to the Python trainer.
//
// Training cannot live in this service: the models are Python and the dataset sits on the
// machine running it. But the monitor page is served from here, and a page that had to
// call a second origin would need CORS and a second URL for the user to remember. So the
// gateway forwards /train, /train/status and /train/stop to the trainer and everything
// stays on one address.
//
// The trainer runs on the host rather than in a container: it needs torch and the 34 MB
// dataset, which would make an image several gigabytes for no benefit in a demo. From
// inside Docker the host is reachable as host.docker.internal.
package main

import (
	"bytes"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"
)

func trainerURL() string {
	if url := os.Getenv("SL_TRAINER_URL"); url != "" {
		return strings.TrimSuffix(url, "/")
	}
	if os.Getenv("SL_IN_CLUSTER") != "" {
		return "http://host.docker.internal:8900"
	}
	return "http://127.0.0.1:8900"
}

// proxyToTrainer forwards one request and passes the trainer's answer straight back,
// including its status code: the page relies on 409 to tell "already running" from a
// real failure.
func (s *server) proxyToTrainer(path string) http.HandlerFunc {
	client := &http.Client{Timeout: 30 * time.Second}

	return func(w http.ResponseWriter, r *http.Request) {
		target := s.trainer + path

		// read the body rather than streaming it: an unknown-length reader goes out
		// with chunked transfer-encoding, and the trainer's http.server reads only
		// Content-Length, so the request would arrive empty and silently use defaults
		payload := []byte("{}")
		if r.Body != nil {
			if raw, err := io.ReadAll(r.Body); err == nil && len(raw) > 0 {
				payload = raw
			}
		}
		req, err := http.NewRequestWithContext(r.Context(), r.Method, target, bytes.NewReader(payload))
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
			return
		}
		req.Header.Set("Content-Type", "application/json")
		req.ContentLength = int64(len(payload))

		resp, err := client.Do(req)
		if err != nil {
			writeJSON(w, http.StatusBadGateway, map[string]string{
				"error": fmt.Sprintf("the trainer is not answering at %s. Start it with: "+
					"cd poc/sl-fabric/client && python trainer.py", s.trainer),
			})
			return
		}
		defer resp.Body.Close()

		responseBody, err := io.ReadAll(resp.Body)
		if err != nil {
			writeJSON(w, http.StatusBadGateway, map[string]string{"error": err.Error()})
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Cache-Control", "no-store")
		w.WriteHeader(resp.StatusCode)
		_, _ = w.Write(responseBody)
	}
}
