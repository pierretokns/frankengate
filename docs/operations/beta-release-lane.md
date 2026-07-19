# FrankenGate beta release lane

The fast lane builds a binary from the current workspace, attaches a local
test report, and verifies the archive before publication. GitHub authentication
is required only for the final upload.

For local consumers or CI jobs that do not have release credentials, use the
preparation mode:

```sh
BETA_PLATFORM=linux BETA_ARCH=amd64 \
  scripts/publish-beta-local.sh \
    --binary ./dist/frankengate \
    --tests ./local-test-report \
    --tag beta-local-example \
    --prepare-only ./dist/beta
```

The command emits a verified `frankengate-*.tar.gz` archive and a matching
`SHA256SUMS` file in the destination directory. It does not contact GitHub or
create a release. The normal mode uses the same archive verification before
creating a draft prerelease and publishing only after both assets are visible.
