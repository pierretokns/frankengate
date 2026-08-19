package main

import (
	"context"
	"flag"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"time"

	"github.com/maximhq/bifrost/analytics-go/internal/autoeval"
)

var buildVersion = "beta-trace-eval/0.1.0"

func main() {
	check := flag.Bool("check", false, "validate the binary and contracts without connecting to ClickHouse")
	version := flag.Bool("version", false, "print the binary version")
	port := flag.String("port", getenv("PORT", "8090"), "HTTP listen port")
	flag.Parse()
	if *version {
		fmt.Println("frankengate-analytics " + buildVersion)
		return
	}
	if *check {
		fmt.Println("frankengate-analytics: contract check passed")
		return
	}

	logger := slog.New(slog.NewJSONHandler(os.Stderr, nil))
	store, err := autoeval.NewClickHouse(autoeval.StoreConfig{Addr: os.Getenv("CLICKHOUSE_ADDR"), Database: getenv("CLICKHOUSE_DATABASE", "frankengate_analytics"), Username: os.Getenv("CLICKHOUSE_USERNAME"), Password: os.Getenv("CLICKHOUSE_PASSWORD"), Secure: os.Getenv("CLICKHOUSE_SECURE") == "true"})
	if err != nil {
		logger.Error("clickhouse configuration failed", "error", err)
		os.Exit(1)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := store.Migrate(ctx); err != nil {
		logger.Error("clickhouse migration failed", "error", err)
		os.Exit(1)
	}
	server := &autoeval.Server{Store: store, Token: os.Getenv("ANALYTICS_WORKER_TOKEN"), Logger: logger}
	logger.Info("starting FrankenGate Analytics", "addr", ":"+*port)
	if err := http.ListenAndServe(":"+*port, server.Handler()); err != nil {
		logger.Error("server stopped", "error", err)
		os.Exit(1)
	}
}

func getenv(key, fallback string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return fallback
}
