package contractfixture

import (
	"bytes"
	"strings"
	"testing"
)

func TestReaderRejectsTamperAndStaleArtifacts(t *testing.T) {
	meta := readMetaSchema(t)
	artifacts, _, err := Compile(marshalManifest(t, validManifest(t, meta)), CompileOptions{MetaSchema: meta, SourceDateEpoch: "1800000000"})
	if err != nil {
		t.Fatalf("compile valid corpus: %v", err)
	}

	tests := []struct {
		name   string
		mutate func(SealedArtifacts) SealedArtifacts
		want   string
	}{
		{
			name: "bundle byte tamper",
			mutate: func(a SealedArtifacts) SealedArtifacts {
				a.Bundle = append([]byte(nil), a.Bundle...)
				a.Bundle[bytes.IndexByte(a.Bundle, 'o')] = 'O'
				return a
			},
			want: "bundle length or digest mismatch",
		},
		{
			name: "index length tamper",
			mutate: func(a SealedArtifacts) SealedArtifacts {
				var index Index
				if err := decodeStrict(a.Index, &index, "index"); err != nil {
					panic(err)
				}
				index.Entries[0].Length--
				a.Index = mustMarshalArtifact(index)
				return a
			},
			want: "not newline-delimited",
		},
		{
			name: "index digest tamper",
			mutate: func(a SealedArtifacts) SealedArtifacts {
				var index Index
				if err := decodeStrict(a.Index, &index, "index"); err != nil {
					panic(err)
				}
				index.Entries[0].Digest = digestBytes([]byte("wrong"))
				a.Index = mustMarshalArtifact(index)
				return a
			},
			want: "digest mismatch",
		},
		{
			name: "provenance tamper",
			mutate: func(a SealedArtifacts) SealedArtifacts {
				a.Provenance = bytes.Replace(a.Provenance, []byte("go1.26.5"), []byte("go1.26.4"), 1)
				return a
			},
			want: "provenance.json",
		},
		{
			name: "missing coverage",
			mutate: func(a SealedArtifacts) SealedArtifacts {
				a.Coverage = nil
				return a
			},
			want: "coverage.json",
		},
		{
			name: "future reader version",
			mutate: func(a SealedArtifacts) SealedArtifacts {
				var index Index
				if err := decodeStrict(a.Index, &index, "index"); err != nil {
					panic(err)
				}
				index.MinReaderVersion = ReaderVersion + 1
				a.Index = mustMarshalArtifact(index)
				return a
			},
			want: "reader version",
		},
		{
			name: "prior compatibility dropped",
			mutate: func(a SealedArtifacts) SealedArtifacts {
				var index Index
				if err := decodeStrict(a.Index, &index, "index"); err != nil {
					panic(err)
				}
				index.PriorVersions = nil
				a.Index = mustMarshalArtifact(index)
				return a
			},
			want: "prior-version",
		},
		{
			name: "coverage references missing entry",
			mutate: func(a SealedArtifacts) SealedArtifacts {
				var coverage CoverageArtifact
				if err := decodeStrict(a.Coverage, &coverage, "coverage"); err != nil {
					panic(err)
				}
				coverage.Routes[0].Faults = append(coverage.Routes[0].Faults, "fault:missing")
				a.Coverage = mustMarshalArtifact(coverage)
				refreshArtifactDigest(&a, artifactCoverage, a.Coverage)
				return a
			},
			want: "unknown entry",
		},
		{
			name: "discrepancy references unknown provenance",
			mutate: func(a SealedArtifacts) SealedArtifacts {
				var discrepancies DiscrepancyArtifact
				if err := decodeStrict(a.Discrepancies, &discrepancies, "discrepancies"); err != nil {
					panic(err)
				}
				discrepancies.Discrepancies[0].ConflictingSourceIDs[0] = "missing-source"
				a.Discrepancies = mustMarshalArtifact(discrepancies)
				refreshArtifactDigest(&a, artifactDiscrepancies, a.Discrepancies)
				return a
			},
			want: "unknown provenance source",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			_, err := ReadSealedCorpus(tt.mutate(*artifacts))
			if err == nil {
				t.Fatal("tampered corpus unexpectedly validated")
			}
			if !strings.Contains(err.Error(), tt.want) {
				t.Fatalf("error %q does not contain %q", err, tt.want)
			}
		})
	}
}

func TestReaderAcceptsLegacyV0Index(t *testing.T) {
	meta := readMetaSchema(t)
	artifacts, _, err := Compile(marshalManifest(t, validManifest(t, meta)), CompileOptions{MetaSchema: meta, SourceDateEpoch: "1800000000"})
	if err != nil {
		t.Fatalf("compile valid corpus: %v", err)
	}
	var index Index
	if err := decodeStrict(artifacts.Index, &index, "index"); err != nil {
		t.Fatal(err)
	}
	index.Schema = LegacyIndexSchemaV0
	index.FormatVersion = 0
	index.MinReaderVersion = 1
	index.Artifacts = nil
	index.PriorVersions = nil
	legacy := SealedArtifacts{Bundle: artifacts.Bundle, Index: mustMarshalArtifact(index)}
	corpus, err := ReadSealedCorpus(legacy)
	if err != nil {
		t.Fatalf("legacy corpus should remain readable: %v", err)
	}
	if len(corpus.Entries) != len(index.Entries) {
		t.Fatalf("legacy entries = %d, want %d", len(corpus.Entries), len(index.Entries))
	}
}

func mustMarshalArtifact(value interface{}) []byte {
	data, err := marshalArtifact(value)
	if err != nil {
		panic(err)
	}
	return data
}

func refreshArtifactDigest(artifacts *SealedArtifacts, name string, data []byte) {
	var index Index
	if err := decodeStrict(artifacts.Index, &index, "index"); err != nil {
		panic(err)
	}
	for refIndex := range index.Artifacts {
		if index.Artifacts[refIndex].Name == name {
			index.Artifacts[refIndex].Length = len(data)
			index.Artifacts[refIndex].Digest = digestBytes(data)
			artifacts.Index = mustMarshalArtifact(index)
			return
		}
	}
	panic("artifact ref not found: " + name)
}
