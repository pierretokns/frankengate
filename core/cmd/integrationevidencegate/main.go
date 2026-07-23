package main

import (
	"flag"
	"fmt"
	"io"
	"os"
	"time"

	"github.com/maximhq/bifrost/core/evidence"
)

func main() {
	var inputPath string
	var junitPath string
	var nowRaw string
	var includeOptionalRealAWS bool

	flags := flag.NewFlagSet(os.Args[0], flag.ExitOnError)
	flags.SetOutput(os.Stderr)
	flags.StringVar(&inputPath, "input", "-", "JSONL evidence input path, or - for stdin")
	flags.StringVar(&junitPath, "junit", "", "optional JUnit XML output path")
	flags.StringVar(&nowRaw, "now", "", "RFC3339 validation time for deterministic waiver checks")
	flags.BoolVar(&includeOptionalRealAWS, "include-optional-real-aws", false, "include optional real-AWS evidence in the gate")
	if err := flags.Parse(os.Args[1:]); err != nil {
		fmt.Fprintf(os.Stderr, "parse flags: %v\n", err)
		os.Exit(2)
	}

	now := time.Now().UTC()
	if nowRaw != "" {
		parsed, err := time.Parse(time.RFC3339, nowRaw)
		if err != nil {
			fmt.Fprintf(os.Stderr, "parse -now: %v\n", err)
			os.Exit(2)
		}
		now = parsed.UTC()
	}

	input, cleanup, err := openInput(inputPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "open input: %v\n", err)
		os.Exit(2)
	}
	defer cleanup()

	report := evidence.ValidateIntegrationEvidenceJSONL(input, evidence.IntegrationGateOptions{
		Now:                    now,
		IncludeOptionalRealAWS: includeOptionalRealAWS,
	})
	if err := evidence.WriteIntegrationGateReportJSONL(os.Stdout, report); err != nil {
		fmt.Fprintf(os.Stderr, "write JSONL report: %v\n", err)
		os.Exit(2)
	}

	if junitPath != "" {
		junit, err := evidence.IntegrationGateJUnitXML(report)
		if err != nil {
			fmt.Fprintf(os.Stderr, "build JUnit report: %v\n", err)
			os.Exit(2)
		}
		if err := os.WriteFile(junitPath, junit, 0o600); err != nil {
			fmt.Fprintf(os.Stderr, "write JUnit report: %v\n", err)
			os.Exit(2)
		}
	}

	if !report.Summary.Pass {
		fmt.Fprintln(os.Stderr, "integration evidence gate failed")
		os.Exit(1)
	}
}

func openInput(path string) (io.Reader, func(), error) {
	if path == "" || path == "-" {
		return os.Stdin, func() {}, nil
	}
	f, err := os.Open(path)
	if err != nil {
		return nil, func() {}, err
	}
	return f, func() { _ = f.Close() }, nil
}
