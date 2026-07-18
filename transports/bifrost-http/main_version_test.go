package main

import "testing"

func TestUntaggedBuildUsesDevelopmentVersion(t *testing.T) {
	if Version != "v0.0.0-dev" {
		t.Fatalf("untagged build version = %q, want v0.0.0-dev", Version)
	}
}
