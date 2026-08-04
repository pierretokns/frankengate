package contract

import (
	"crypto/sha256"
	"crypto/tls"
	"crypto/x509"
	"encoding/hex"
	"encoding/pem"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestSyntheticTLSFixtureFingerprints(t *testing.T) {
	want := map[string]string{
		"ca.pem":     "884247b10492f695899455c699536808921aba65f9df13762abe60c625deccd8",
		"server.pem": "6c9552e83c9c9039d158ea818547cb42bb50961b5c05122705040f4abd3ce12b",
		"server.key": "8fbad7e62ee681e2430ddf52aa3116cae17ae6c8ad05f2f6f446840f02503679",
	}
	for name, expected := range want {
		data, err := os.ReadFile(filepath.Join("..", "tls", name))
		if err != nil {
			t.Fatal(err)
		}
		digest := sha256.Sum256(data)
		if got := hex.EncodeToString(digest[:]); got != expected {
			t.Fatalf("synthetic TLS fixture %s drifted: %s", name, got)
		}
	}
	caPEM, _ := os.ReadFile(filepath.Join("..", "tls", "ca.pem"))
	serverPEM, _ := os.ReadFile(filepath.Join("..", "tls", "server.pem"))
	keyPEM, _ := os.ReadFile(filepath.Join("..", "tls", "server.key"))
	caBlock, _ := pem.Decode(caPEM)
	serverBlock, _ := pem.Decode(serverPEM)
	if caBlock == nil || serverBlock == nil {
		t.Fatal("TLS fixtures are not PEM certificates")
	}
	ca, err := x509.ParseCertificate(caBlock.Bytes)
	if err != nil {
		t.Fatalf("invalid synthetic trust anchor: %v", err)
	}
	server, err := x509.ParseCertificate(serverBlock.Bytes)
	if err != nil {
		t.Fatal(err)
	}
	roots := x509.NewCertPool()
	roots.AddCert(ca)
	if _, err := server.Verify(x509.VerifyOptions{Roots: roots, DNSName: "bedrock-mantle.us-east-1.api.aws", CurrentTime: time.Date(2026, 7, 22, 0, 0, 0, 0, time.UTC)}); err != nil {
		t.Fatalf("server certificate chain/SAN: %v", err)
	}
	pair, err := tls.X509KeyPair(serverPEM, keyPEM)
	if err != nil {
		t.Fatalf("server certificate/key mismatch: %v", err)
	}
	if len(pair.Certificate) != 1 {
		t.Fatalf("unexpected server certificate chain length %d", len(pair.Certificate))
	}
}
