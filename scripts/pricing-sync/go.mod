module github.com/pierretokns/frankengate/scripts/pricing-sync

// This helper uses only the standard library and intentionally remains
// runnable on the local Go toolchain; the GitLab job supplies its own pinned
// golang:1.26 image for publication.
go 1.22
