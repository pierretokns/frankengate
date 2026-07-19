package main

import (
	"flag"
	"fmt"
	"os"
)

func main() {
	var ecosystem, packageJSON, packageLock, evidence, evidenceRoot, goLock, manifest, goSum, sourceRoot, inventoryOut, spdxOut, created string
	flag.StringVar(&ecosystem, "ecosystem", "npm", "generator ecosystem: npm or go")
	flag.StringVar(&packageJSON, "package-json", "", "path to package.json")
	flag.StringVar(&packageLock, "package-lock", "", "path to package-lock.json (lockfileVersion 3)")
	flag.StringVar(&evidence, "evidence", "", "path to hash-bound license evidence JSON")
	flag.StringVar(&evidenceRoot, "evidence-root", "", "root for evidence paths (defaults to the evidence file directory)")
	flag.StringVar(&goLock, "go-lock", "", "path to prehydrated Go provenance lock JSON")
	flag.StringVar(&manifest, "manifest", "", "path to root go.mod")
	flag.StringVar(&goSum, "go-sum", "", "path to root go.sum")
	flag.StringVar(&sourceRoot, "source-root", "", "root for prehydrated Go source archives")
	flag.StringVar(&inventoryOut, "inventory-out", "", "output inventory TSV path")
	flag.StringVar(&spdxOut, "spdx-out", "", "output SPDX 2.3 JSON path")
	flag.StringVar(&created, "created", "1970-01-01T00:00:00Z", "SPDX creation time in RFC3339 form")
	flag.Parse()

	if inventoryOut == "" || spdxOut == "" {
		fmt.Fprintln(os.Stderr, "inventory-out and spdx-out are required")
		os.Exit(2)
	}

	var inv, spdx []byte
	var err error
	switch ecosystem {
	case "npm":
		if packageJSON == "" || packageLock == "" || evidence == "" {
			fmt.Fprintln(os.Stderr, "npm requires package-json, package-lock, and evidence")
			os.Exit(2)
		}
		inv, spdx, err = GenerateFiles(packageJSON, packageLock, evidence, evidenceRoot, created)
	case "go":
		if goLock == "" || manifest == "" || goSum == "" {
			fmt.Fprintln(os.Stderr, "go requires go-lock, manifest, and go-sum")
			os.Exit(2)
		}
		inv, spdx, err = GenerateGoFiles(goLock, manifest, goSum, sourceRoot, evidenceRoot, created)
	default:
		fmt.Fprintf(os.Stderr, "unsupported ecosystem %q\n", ecosystem)
		os.Exit(2)
	}
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
