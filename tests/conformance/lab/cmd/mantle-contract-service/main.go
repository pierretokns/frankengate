package main

import (
	"flag"
	"fmt"
	"net/http"
	"os"
	"time"

	"github.com/maximhq/bifrost/tests/conformance/lab/mantleservice"
)

func main() {
	address := flag.String("listen", ":8080", "listen address")
	certificate := flag.String("tls-cert", "", "TLS server certificate")
	privateKey := flag.String("tls-key", "", "TLS server private key")
	integration := flag.Bool("integration", false, "require exact Mantle authority and emit transcript JSONL")
	flag.Parse()
	var handler http.Handler
	service, err := mantleservice.New()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	handler = service
	if *integration {
		handler, err = mantleservice.NewIntegrationHandler(os.Stdout)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	}
	if (*certificate == "") != (*privateKey == "") {
		fmt.Fprintln(os.Stderr, "both TLS certificate and key are required")
		os.Exit(1)
	}
	server := &http.Server{Addr: *address, Handler: handler, ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 10 * time.Second, WriteTimeout: 10 * time.Second, IdleTimeout: 30 * time.Second, MaxHeaderBytes: 32 << 10}
	serve := server.ListenAndServe
	if *certificate != "" {
		serve = func() error { return server.ListenAndServeTLS(*certificate, *privateKey) }
	}
	if err := serve(); err != nil && err != http.ErrServerClosed {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
