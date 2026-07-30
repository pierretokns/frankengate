#!/usr/bin/env python3
"""Offline JSON-lines token counter for one pinned local tokenizer snapshot.

The worker intentionally emits only token counts. Input text is never logged.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    args = parser.parse_args()
    snapshot = args.snapshot.resolve(strict=True)
    if not snapshot.is_dir():
        raise SystemExit("tokenizer snapshot must be a directory")

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        str(snapshot),
        local_files_only=True,
    )
    for line in sys.stdin:
        try:
            request = json.loads(line)
            if (
                not isinstance(request, dict)
                or set(request) != {"text"}
                or not isinstance(request["text"], str)
            ):
                raise ValueError("invalid request")
            count = len(
                tokenizer.encode(
                    request["text"],
                    add_special_tokens=False,
                )
            )
            response = {"status": "ok", "tokens": count}
        except BaseException:
            response = {"status": "error"}
        sys.stdout.write(
            json.dumps(response, sort_keys=True) + "\n"
        )
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
