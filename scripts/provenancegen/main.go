package main

import (
	"flag"
	"fmt"
	"os"
)

func main() {
	var packageJSON, packageLock, evidence, evidenceRoot, inventoryOut, spdxOut, created string
	flag.StringVar(&packageJSON, "package-json", "", "path to package.json")
	flag.StringVar(&packageLock, "package-lock", "", "path to package-lock.json (lockfileVersion 3)")
	flag.StringVar(&evidence, "evidence", "", "path to hash-bound license evidence JSON")
	flag.StringVar(&evidenceRoot, "evidence-root", "", "root for evidence paths (defaults to the evidence file directory)")
	flag.StringVar(&inventoryOut, "inventory-out", "", "output inventory TSV path")
	flag.StringVar(&spdxOut, "spdx-out", "", "output SPDX 2.3 JSON path")
	flag.StringVar(&created, "created", "1970-01-01T00:00:00Z", "SPDX creation time in RFC3339 form")
	flag.Parse()

	if packageJSON == "" || packageLock == "" || evidence == "" || inventoryOut == "" || spdxOut == "" {
		fmt.Fprintln(os.Stderr, "package-json, package-lock, evidence, inventory-out, and spdx-out are required")
		os.Exit(2)
	}

	inv, spdx, err := GenerateFiles(packageJSON, packageLock, evidence, evidenceRoot, created)
	if err != nil {
		fmt.Fprintf(os.Stderr, "provenance generation failed: %v\n", err)
		os.Exit(1)
	}
	if err := os.WriteFile(inventoryOut, inv, 0o644); err != nil {
		fmt.Fprintf(os.Stderr, "write inventory: %v\n", err)
		os.Exit(1)
	}
	if err := os.WriteFile(spdxOut, spdx, 0o644); err != nil {
		fmt.Fprintf(os.Stderr, "write SPDX: %v\n", err)
		os.Exit(1)
	}
}
