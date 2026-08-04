package registry

import "testing"

func TestParseRequiresPinnedLicensedManifestAndSafeTransport(t *testing.T) {
	data := []byte(`{"schema_version":"registry.v1","repository":"https://github.com/example/agents","revision":"abc123","license":"Apache-2.0","entries":[{"id":"agent","name":"Agent","version":"1.0.0","source":"https://github.com/example/agent","digest":"sha256:0123456789012345678901234567890123456789012345678901234567890123","transport":{"type":"a2a","url":"https://agent.example/a2a"}}]}`)
	manifest, err := Parse(data)
	if err != nil {
		t.Fatal(err)
	}
	if manifest.Entries[0].Transport.URL != "https://agent.example/a2a" {
		t.Fatalf("unexpected transport: %#v", manifest)
	}
}

func TestParseRejectsUnknownFieldsCredentialsAndUnpinnedEntries(t *testing.T) {
	if _, err := Parse([]byte(`{"schema_version":"v1","repository":"repo","revision":"rev","license":"MIT","unexpected":true}`)); err == nil {
		t.Fatal("expected unknown field rejection")
	}
	if _, err := Parse([]byte(`{"schema_version":"v1","repository":"repo","revision":"rev","license":"MIT","entries":[{"id":"x","name":"x","version":"1","source":"x","digest":"sha256:0000000000000000000000000000000000000000000000000000000000000000","transport":{"type":"a2a","url":"https://x","headers":{"Authorization":"secret"}}}]}`)); err == nil {
		t.Fatal("expected credential header rejection")
	}
	if _, err := Parse([]byte(`{"schema_version":"v1","repository":"repo","revision":"rev","license":"MIT","entries":[{"id":"x","name":"x","version":"1","source":"x","digest":"git:head"}]}`)); err == nil {
		t.Fatal("expected unpinned digest rejection")
	}
}
