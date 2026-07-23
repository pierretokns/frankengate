package contractsource_test

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
)

func TestSanitizedMantleObservationsStayNarrowAndSecretFree(t *testing.T) {
	path := filepath.Join("..", "..", "tests", "conformance", "bedrock", "observations", "mantle-frontier-access-denied.v1.json")
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var observation struct {
		Schema       string `json:"schema"`
		Authority    string `json:"authority"`
		Route        string `json:"route"`
		Observations []struct {
			Model     string `json:"model"`
			Status    int    `json:"status"`
			ErrorCode string `json:"error_code"`
		} `json:"observations"`
		Omissions []string `json:"omissions"`
		Claims    []string `json:"claims"`
	}
	if err := json.Unmarshal(data, &observation); err != nil {
		t.Fatal(err)
	}
	if observation.Schema != "bedrock-mantle-sanitized-observation-set/v1" || observation.Authority != "aws-observed-sample" {
		t.Fatal("observation must remain explicitly versioned and observational")
	}
	if observation.Route != "/openai/v1/responses" {
		t.Fatalf("frontier route = %q", observation.Route)
	}
	models := make([]string, 0, len(observation.Observations))
	for _, item := range observation.Observations {
		models = append(models, item.Model)
		if item.Status != 401 || item.ErrorCode != "access_denied" {
			t.Fatalf("unexpected authorization observation for %s", item.Model)
		}
	}
	if len(models) != 4 || !sort.StringsAreSorted(models) {
		t.Fatalf("four-model observation set must be sorted: %v", models)
	}
	joined := strings.ToLower(string(data))
	for _, forbidden := range []string{"secret_access_key", "session_token\"", "credential=", "signature="} {
		if strings.Contains(joined, forbidden) {
			t.Fatalf("observation leaked forbidden credential material %q", forbidden)
		}
	}
	if len(observation.Omissions) == 0 || len(observation.Claims) == 0 {
		t.Fatal("observation must explicitly declare omissions and narrow claims")
	}
}
