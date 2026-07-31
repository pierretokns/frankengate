#!/usr/bin/env python3
import argparse
import hashlib
import json
import pathlib
import faithful_diagnosis_concept_audit as audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", type=pathlib.Path)
    parser.add_argument("--result", type=pathlib.Path, required=True)
    parser.add_argument("--summary", type=pathlib.Path, required=True)
    args = parser.parse_args()
    result = audit.run_audit(
        args.corpus,
        receipt_hmac_key=b"frankengate-faithful-diagnosis-key-2026",
        scope_ref="internal-research-authorized",
        dataset_id="crispwisp/wisp-claude-code-sessions",
        dataset_revision="c2c90b59174318ab0b163ec9c9ac82bb879288ce",
        review_budget=21,
        run_date="2026-07-30",
    )
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    digest = hashlib.sha256(args.result.read_bytes()).hexdigest()
    summary = audit.render_summary(result).replace(
        "**Run date:** 2026-07-30",
        f"**Run date:** 2026-07-30\n\n**Result SHA-256:** `{digest}`",
    )
    args.summary.write_text(summary)
    print(json.dumps({"result_sha256": digest, "result": str(args.result)}))


if __name__ == "__main__":
    main()
