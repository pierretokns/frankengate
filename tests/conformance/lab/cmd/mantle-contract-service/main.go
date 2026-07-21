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
	flag.Parse()
	service, err := mantleservice.New()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	server := &http.Server{Addr: *address, Handler: service, ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 10 * time.Second, WriteTimeout: 10 * time.Second, IdleTimeout: 30 * time.Second, MaxHeaderBytes: 32 << 10}
	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
