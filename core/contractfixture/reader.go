package contractfixture

import (
	"fmt"
	"sort"
)

type SealedCorpus struct {
	Index       Index
	Entries     []CorpusEntry
	Provenance  ProvenanceArtifact
	Coverage    CoverageArtifact
	Discrepancy DiscrepancyArtifact
}

func ReadSealedCorpus(artifacts SealedArtifacts) (*SealedCorpus, error) {
	var index Index
	if err := decodeStrict(artifacts.Index, &index, "corpus index"); err != nil {
		return nil, err
	}
	switch index.Schema {
	case IndexSchemaV1:
		return readV1(index, artifacts)
	case LegacyIndexSchemaV0:
		return readLegacyV0(index, artifacts)
	default:
		return nil, fmt.Errorf("unsupported corpus index schema %q", index.Schema)
	}
}

func readV1(index Index, artifacts SealedArtifacts) (*SealedCorpus, error) {
	if index.FormatVersion != 1 || index.MinReaderVersion < 1 || index.MinReaderVersion > ReaderVersion {
		return nil, fmt.Errorf("unsupported corpus index reader version")
	}
	if index.BundleLength != len(artifacts.Bundle) || index.BundleDigest != digestBytes(artifacts.Bundle) {
		return nil, fmt.Errorf("corpus bundle length or digest mismatch")
	}
	if !containsString(index.PriorVersions, "bedrock-mantle-corpus/v0") {
		return nil, fmt.Errorf("corpus index omits prior-version compatibility")
	}
	if err := verifyArtifactRefs(index.Artifacts, artifacts); err != nil {
		return nil, err
	}
	entries, err := readBundleEntries(index, artifacts.Bundle)
	if err != nil {
		return nil, err
	}
	var provenance ProvenanceArtifact
	if err := decodeStrict(artifacts.Provenance, &provenance, "corpus provenance"); err != nil {
		return nil, err
	}
	if provenance.Schema != ProvenanceSchemaV1 {
		return nil, fmt.Errorf("unsupported provenance schema %q", provenance.Schema)
	}
	var coverage CoverageArtifact
	if err := decodeStrict(artifacts.Coverage, &coverage, "corpus coverage"); err != nil {
		return nil, err
	}
	if coverage.Schema != CoverageSchemaV1 {
		return nil, fmt.Errorf("unsupported coverage schema %q", coverage.Schema)
	}
	var discrepancies DiscrepancyArtifact
	if err := decodeStrict(artifacts.Discrepancies, &discrepancies, "corpus discrepancies"); err != nil {
		return nil, err
	}
	if discrepancies.Schema != DiscrepancySchemaV1 {
		return nil, fmt.Errorf("unsupported discrepancy schema %q", discrepancies.Schema)
	}
	if err := verifyCoverage(coverage, entries); err != nil {
		return nil, err
	}
	if err := verifyProvenance(provenance, discrepancies); err != nil {
		return nil, err
	}
	if err := verifyEntryProvenanceSources(entries, provenance); err != nil {
		return nil, err
	}
	return &SealedCorpus{
		Index:       index,
		Entries:     entries,
		Provenance:  provenance,
		Coverage:    coverage,
		Discrepancy: discrepancies,
	}, nil
}

func verifyEntryProvenanceSources(entries []CorpusEntry, provenance ProvenanceArtifact) error {
	sourceIDs := map[string]bool{}
	for _, source := range provenance.Sources {
		sourceIDs[source.ID] = true
	}
	for _, entry := range entries {
		for _, sourceID := range entry.SourceIDs {
			if !sourceIDs[sourceID] {
				return fmt.Errorf("corpus entry %q references unknown provenance source %q", entry.ID, sourceID)
			}
		}
	}
	return nil
}

func readLegacyV0(index Index, artifacts SealedArtifacts) (*SealedCorpus, error) {
	if index.FormatVersion != 0 || index.MinReaderVersion > ReaderVersion {
		return nil, fmt.Errorf("unsupported legacy corpus index")
	}
	if index.BundleLength != len(artifacts.Bundle) || index.BundleDigest != digestBytes(artifacts.Bundle) {
		return nil, fmt.Errorf("legacy corpus bundle length or digest mismatch")
	}
	entries, err := readBundleEntries(index, artifacts.Bundle)
	if err != nil {
		return nil, err
	}
	return &SealedCorpus{Index: index, Entries: entries}, nil
}

func verifyArtifactRefs(refs []ArtifactRef, artifacts SealedArtifacts) error {
	expected := map[string][]byte{
		artifactCoverage:      artifacts.Coverage,
		artifactDiscrepancies: artifacts.Discrepancies,
		artifactProvenance:    artifacts.Provenance,
	}
	if len(refs) != len(expected) {
		return fmt.Errorf("corpus index artifact refs are incomplete")
	}
	for index, ref := range refs {
		if index > 0 && refs[index-1].Name >= ref.Name {
			return fmt.Errorf("corpus index artifact refs must be sorted")
		}
		data, ok := expected[ref.Name]
		if !ok {
			return fmt.Errorf("corpus index references unknown artifact %q", ref.Name)
		}
		if ref.Length != len(data) || ref.Digest != digestBytes(data) {
			return fmt.Errorf("artifact %q length or digest mismatch", ref.Name)
		}
	}
	return nil
}

func readBundleEntries(index Index, bundle []byte) ([]CorpusEntry, error) {
	entries := make([]CorpusEntry, 0, len(index.Entries))
	previousID := ""
	for entryIndex, indexed := range index.Entries {
		if indexed.ID == "" || indexed.Offset < 0 || indexed.Length <= 1 || indexed.Offset+indexed.Length > len(bundle) || !validDigest(indexed.Digest) {
			return nil, fmt.Errorf("invalid index entry[%d]", entryIndex)
		}
		if entryIndex > 0 && previousID >= indexed.ID {
			return nil, fmt.Errorf("index entries must be sorted by unique id")
		}
		segment := bundle[indexed.Offset : indexed.Offset+indexed.Length]
		if segment[len(segment)-1] != '\n' {
			return nil, fmt.Errorf("indexed bundle entry %q is not newline-delimited", indexed.ID)
		}
		if digestBytes(segment) != indexed.Digest {
			return nil, fmt.Errorf("indexed bundle entry %q digest mismatch", indexed.ID)
		}
		var entry CorpusEntry
		if err := decodeStrict(segment[:len(segment)-1], &entry, "corpus entry "+indexed.ID); err != nil {
			return nil, err
		}
		if entry.Schema != EntrySchemaV1 || entry.ID != indexed.ID || entry.Kind == "" || !allowedRoute(entry.Route) || len(entry.SourceIDs) == 0 {
			return nil, fmt.Errorf("corpus entry %q is invalid", indexed.ID)
		}
		if !sort.StringsAreSorted(entry.SourceIDs) {
			return nil, fmt.Errorf("corpus entry %q source ids must be sorted", indexed.ID)
		}
		entries = append(entries, entry)
		previousID = indexed.ID
	}
	return entries, nil
}

func verifyCoverage(coverage CoverageArtifact, entries []CorpusEntry) error {
	entryIDs := map[string]bool{}
	for _, entry := range entries {
		entryIDs[entry.ID] = true
	}
	if len(coverage.Routes) == 0 || len(coverage.AuthorityClasses) == 0 || len(coverage.MutationTargets) == 0 {
		return fmt.Errorf("coverage artifact is incomplete")
	}
	for routeIndex, route := range coverage.Routes {
		if routeIndex > 0 && coverage.Routes[routeIndex-1].Route >= route.Route {
			return fmt.Errorf("coverage routes must be sorted")
		}
		if !allowedRoute(route.Route) {
			return fmt.Errorf("coverage references unknown route %q", route.Route)
		}
		for _, id := range append(append(append(route.Schemas, route.Vectors...), route.Observations...), route.Faults...) {
			if !entryIDs[id] {
				return fmt.Errorf("coverage references unknown entry %q", id)
			}
		}
	}
	if !sort.StringsAreSorted(coverage.MutationTargets) {
		return fmt.Errorf("coverage mutation targets must be sorted")
	}
	for index, class := range coverage.AuthorityClasses {
		if index > 0 && coverage.AuthorityClasses[index-1].Class >= class.Class {
			return fmt.Errorf("coverage authority classes must be sorted")
		}
		if !allowedSourceClass(class.Class) || !sortedUnique(class.Sources) {
			return fmt.Errorf("coverage authority class %q is invalid", class.Class)
		}
	}
	return nil
}

func verifyProvenance(provenance ProvenanceArtifact, discrepancies DiscrepancyArtifact) error {
	if provenance.MetaSchemaDigest == "" || !validDigest(provenance.MetaSchemaDigest) || provenance.ToolchainLock.Schema == "" {
		return fmt.Errorf("provenance is incomplete")
	}
	sourceIDs := map[string]bool{}
	for index, source := range provenance.Sources {
		if index > 0 && provenance.Sources[index-1].ID >= source.ID {
			return fmt.Errorf("provenance sources must be sorted by unique id")
		}
		if source.ID == "" || !allowedSourceClass(source.Class) || !validDigest(source.ArtifactDigest) || source.LicenseOrTerms == "" {
			return fmt.Errorf("provenance source %q is incomplete", source.ID)
		}
		sourceIDs[source.ID] = true
	}
	for _, discrepancy := range discrepancies.Discrepancies {
		for _, sourceID := range discrepancy.ConflictingSourceIDs {
			if !sourceIDs[sourceID] {
				return fmt.Errorf("discrepancy %q references unknown provenance source %q", discrepancy.ID, sourceID)
			}
		}
	}
	return nil
}
