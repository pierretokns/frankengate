package autoeval

import (
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"strings"
	"time"
)

type Server struct {
	Store  *Store
	Token  string
	Logger *slog.Logger
}

func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, map[string]any{"status": "ok", "service": "frankengate-analytics"})
	})
	mux.HandleFunc("GET /readyz", s.ready)
	mux.HandleFunc("POST /v1/traces", s.ingestTrace)
	mux.HandleFunc("POST /v1/evaluations", s.scoreEvaluation)
	mux.HandleFunc("GET /v1/reports/evaluations", s.evaluationReport)
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/healthz" && !s.authorized(r) {
			writeError(w, http.StatusUnauthorized, "unauthorized")
			return
		}
		mux.ServeHTTP(w, r)
	})
}

func (s *Server) authorized(r *http.Request) bool {
	if s.Token == "" {
		return true
	}
	return strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer ") == s.Token
}

func (s *Server) ready(w http.ResponseWriter, r *http.Request) {
	if s.Store == nil {
		writeError(w, http.StatusServiceUnavailable, "clickhouse is not configured")
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
	defer cancel()
	if err := s.Store.Ping(ctx); err != nil {
		writeError(w, http.StatusServiceUnavailable, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ready"})
}

func (s *Server) ingestTrace(w http.ResponseWriter, r *http.Request) {
	var trace Trace
	if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 8<<20)).Decode(&trace); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	if tenant := r.Header.Get("X-Tenant-ID"); tenant == "" || tenant != trace.TenantID {
		writeError(w, http.StatusBadRequest, "X-Tenant-ID must match trace.tenant_id")
		return
	}
	prepared, report, err := Prepare(trace)
	if err != nil {
		writeError(w, http.StatusUnprocessableEntity, err.Error())
		return
	}
	if s.Store == nil {
		writeError(w, http.StatusServiceUnavailable, "clickhouse is not configured")
		return
	}
	if err := s.Store.InsertTrace(r.Context(), prepared); err != nil {
		writeError(w, http.StatusBadGateway, err.Error())
		return
	}
	writeJSON(w, http.StatusAccepted, map[string]any{"trace_id": trace.TraceID, "admission": report})
}

func (s *Server) scoreEvaluation(w http.ResponseWriter, r *http.Request) {
	var req struct {
		TenantID   string           `json:"tenant_id"`
		Rubric     Rubric           `json:"rubric"`
		Assessment ActionAssessment `json:"assessment"`
	}
	if err := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1<<20)).Decode(&req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	if req.TenantID == "" || r.Header.Get("X-Tenant-ID") != req.TenantID {
		writeError(w, http.StatusBadRequest, "X-Tenant-ID must match tenant_id")
		return
	}
	judgment, err := Score(req.Rubric, req.Assessment)
	if err != nil {
		writeError(w, http.StatusUnprocessableEntity, err.Error())
		return
	}
	if s.Store == nil {
		writeError(w, http.StatusServiceUnavailable, "clickhouse is not configured")
		return
	}
	if err := s.Store.InsertJudgment(r.Context(), req.TenantID, judgment); err != nil {
		writeError(w, http.StatusBadGateway, err.Error())
		return
	}
	writeJSON(w, http.StatusAccepted, judgment)
}

func (s *Server) evaluationReport(w http.ResponseWriter, r *http.Request) {
	tenantID := r.Header.Get("X-Tenant-ID")
	if tenantID == "" {
		writeError(w, http.StatusBadRequest, "X-Tenant-ID is required")
		return
	}
	if s.Store == nil {
		writeError(w, http.StatusServiceUnavailable, "clickhouse is not configured")
		return
	}
	report, err := s.Store.EvaluationReport(r.Context(), tenantID, r.URL.Query().Get("trace_id"))
	if err != nil {
		writeError(w, http.StatusBadGateway, err.Error())
		return
	}
	writeJSON(w, http.StatusOK, report)
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}
func writeError(w http.ResponseWriter, status int, message string) {
	writeJSON(w, status, map[string]string{"error": message})
}
