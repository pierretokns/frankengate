package contractsource_test

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/maximhq/bifrost/core/contractsource"
)

func TestCommittedSourceLockValidatesOffline(t *testing.T) {
	path := filepath.Join("..", "..", "tests", "conformance", "bedrock", "sources", "source-lock.v1.json")
	file, err := os.Open(path)
	if err != nil {
		t.Fatalf("open committed source lock: %v", err)
	}
	defer file.Close()
	if _, err := contractsource.Decode(file); err != nil {
		t.Fatalf("committed source lock is invalid: %v", err)
	}
}

func TestSourceLockFailsClosed(t *testing.T) {
	data, err := os.ReadFile(filepath.Join("..", "..", "tests", "conformance", "bedrock", "sources", "source-lock.v1.json"))
	if err != nil {
		t.Fatal(err)
	}
	for _, test := range []struct {
		name string
		old  string
		new  string
	}{
		{"moving revision", "v2.46.0", "latest"},
		{"bad digest", "sha256:672381db55efb3a1e2610f29304c130cccdd0b319bace4d492b2443cb64c1e7c", "sha256:nope"},
		{"authority escalation", "emitted request routing and serialization only", "server acceptance"},
		{"forbidden emulator", "openai-python", "localstack"},
		{"moving github ref", "blob/ee5bce84fccb97135948a4838255804d4af1b7dd/", "blob/main/"},
		{"unknown discrepancy source", "openai-ruby-mantle-0.71.0\"],", "missing-source\"],"},
		{"invalid discrepancy status", "\"status\": \"resolved\"", "\"status\": \"hand-waved\""},
		{"absence search digest", "sha256:3f516f976a4e4b10d53057aeb0a2973f5b38dda67ece19465fa493fd9ab87d2b", "sha256:nope"},
		{"absence positive result", "\"result\": \"absent\"", "\"result\": \"present\""},
		{"absence pattern drift", "\"bedrock-mantle\", \"bedrock_mantle\"", "\"BedrockMantle\", \"bedrock_mantle\""},
		{"duplicate JSON key", "\"schema\": \"bedrock-mantle-source-lock/v1\",", "\"schema\": \"bedrock-mantle-source-lock/v1\", \"schema\": \"bedrock-mantle-source-lock/v1\","},
	} {
		t.Run(test.name, func(t *testing.T) {
			mutated := strings.Replace(string(data), test.old, test.new, 1)
			if _, err := contractsource.Decode(strings.NewReader(mutated)); err == nil {
				t.Fatal("mutated source lock unexpectedly validated")
			}
		})
	}
}
