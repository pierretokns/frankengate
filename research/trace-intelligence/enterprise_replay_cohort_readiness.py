#!/usr/bin/env python3
"""Check a candidate cohort against the governed changed-system protocol.

The checker emits only structural counts and hashes. It is intentionally a
readiness audit, not a semantic-label or enterprise-outcome evaluator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


REQUIRED_RECORD_FIELDS = {
    "principal_id",
    "team_id",
    "project_id",
    "system_id",
    "effective_time",
    "task_id",
    "annotator_a_label",
    "annotator_b_label",
    "changed_environment_id",
    "independent_outcome",
}


def audit(path: Path) -> dict:
    raw = path.read_bytes()
    value = json.loads(raw)
    rows = value.get("cases", value.get("records", [])) if isinstance(value, dict) else value
    rows = rows if isinstance(rows, list) else []
    keys = set().union(*(row.keys() for row in rows if isinstance(row, dict))) if rows else set()
    labels = []
    for row in rows:
        if isinstance(row, dict):
            labels.extend([row.get("annotator_a_label"), row.get("annotator_b_label")])
    label_counts = {str(label): labels.count(label) for label in sorted(set(labels), key=str) if label is not None}
    principal_count = len({row.get("principal_id") for row in rows if isinstance(row, dict) and row.get("principal_id") is not None})
    project_count = len({row.get("project_id") for row in rows if isinstance(row, dict) and row.get("project_id") is not None})
    system_count = len({row.get("system_id") for row in rows if isinstance(row, dict) and row.get("system_id") is not None})
    missing = sorted(REQUIRED_RECORD_FIELDS - keys)
    return {
        "schema": "frankengate-enterprise-replay-cohort-readiness-v1",
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "record_count": len(rows),
        "field_names": sorted(keys),
        "missing_required_record_fields": missing,
        "principal_count": principal_count,
        "project_count": project_count,
        "system_count": system_count,
        "label_counts": label_counts,
        "minimum_gate": {
            "100_labeled_targets": len(rows) >= 100,
            "50_hard_negatives": False,
            "25_nil_or_unclear": label_counts.get("nil", 0) + label_counts.get("unclear", 0) >= 25,
            "two_annotators": "annotator_a_label" in keys and "annotator_b_label" in keys,
            "principal_project_system_time_splits": all(field in keys for field in ("principal_id", "project_id", "system_id", "effective_time")),
            "changed_environment": "changed_environment_id" in keys,
            "independent_outcome": "independent_outcome" in keys,
        },
        "ready_for_causal_replay": not missing and len(rows) >= 100 and principal_count >= 2 and project_count >= 2 and system_count >= 2,
        "claim_boundary": "A readiness pass does not establish semantic labels, artifact validity, changed-system utility, or enterprise outcomes.",
        "content_policy": "No prompt, SQL, tool argument, row, or identifier value is emitted; only aggregate field names, counts, and a source hash.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--input", type=Path, required=True); parser.add_argument("--out", type=Path, required=True); args = parser.parse_args()
    result = audit(args.input); args.out.parent.mkdir(parents=True, exist_ok=True); args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(json.dumps({k: result[k] for k in ("record_count", "principal_count", "project_count", "system_count", "minimum_gate", "ready_for_causal_replay")}, indent=2))


if __name__ == "__main__": main()
