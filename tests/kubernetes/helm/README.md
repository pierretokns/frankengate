# Helm replacement oracle

`run-replacement-oracle.sh` verifies the public chart and two immutable gateway
images through a complete Helm replacement cycle:

1. install the baseline image;
2. create a virtual key;
3. upgrade to the current image;
4. roll back to the baseline image; and
5. re-upgrade to the current image.

Each phase requires exactly three Ready gateway pods on three distinct nodes,
the expected image index and platform digests, no pods from the previous phase,
zero replicas in old ReplicaSets, and a virtual key that remains present and is
accepted by the inference hotpath on every pod.

Run it against an existing Kubernetes cluster with at least three Ready,
schedulable nodes:

```bash
tests/kubernetes/helm/run-replacement-oracle.sh \
  ./bifrost-2.1.35.tgz \
  ghcr.io/pierretokns/frankengate \
  sha256:<baseline-index-digest> \
  sha256:<current-index-digest>
```

The script creates a disposable namespace and labels exactly three nodes. Set
`KEEP_FIXTURE=1` to retain those resources for diagnosis after a failure.
