#!/usr/bin/env python3
"""Bounded independent SkillGen reproduction using the Codex harness.

This deliberately does not alter the upstream checkout.  SkillGen expects
OpenRouter/OpenAI clients; the adapter below translates its chat calls into
short, non-interactive Codex turns and uses a deterministic local embedding
replacement.  The receipt labels this provider substitution explicitly and
never treats it as a paper-faithful OpenRouter reproduction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "research/trace-intelligence/experiments/results"
SUMMARIES = ROOT / "research/trace-intelligence/experiments/summaries"


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise
        value = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object, got {type(value).__name__}")
    return value


class CodexAdapter:
    """OpenAI-shaped subset used by SkillGen's LLM module."""

    def __init__(self, timeout: int = 120):
        self.timeout = timeout
        self.calls = 0
        self.failures: list[str] = []

    def _call(self, prompt: str) -> str:
        self.calls += 1
        out = Path(tempfile.mktemp(prefix="skillgen-codex-", suffix=".txt"))
        cmd = [
            "codex", "exec", "--ephemeral", "--skip-git-repo-check",
            "--ignore-user-config", "--ignore-rules", "-s", "read-only",
            "--cd", "/private/tmp", "-o", str(out), prompt,
        ]
        try:
            proc = subprocess.run(
                cmd, cwd="/private/tmp", capture_output=True, text=True,
                timeout=self.timeout,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"codex exit={proc.returncode}: {proc.stderr[-500:]}")
            result = out.read_text(encoding="utf-8")
            if not result.strip():
                raise RuntimeError("codex returned an empty final message")
            return result
        except Exception as exc:
            self.failures.append(str(exc))
            raise
        finally:
            out.unlink(missing_ok=True)

    def text(self, prompt: str, system: str = "") -> str:
        instruction = (
            "You are a backend model called by an experiment. Follow the supplied "
            "system and user messages. Return only the requested answer; do not "
            "describe this wrapper or edit files.\n\n"
            f"SYSTEM:\n{system}\n\nUSER:\n{prompt}"
        )
        return self._call(instruction).strip()

    def obj(self, prompt: str, system: str = "") -> dict:
        instruction = (
            "You are a backend model called by an experiment. Follow the supplied "
            "system and user messages. Return exactly one valid JSON object and no "
            "markdown or commentary.\n\n"
            f"SYSTEM:\n{system}\n\nUSER:\n{prompt}"
        )
        return _extract_json(self._call(instruction))


def _hash_embed(texts: list[str]) -> list[list[float]]:
    """Small deterministic embedding substitute; no semantic claims."""
    dim = 256
    rows = []
    for text in texts:
        row = [0.0] * dim
        for token in text.lower().split():
            idx = int(hashlib.sha256(token.encode()).hexdigest()[:8], 16) % dim
            row[idx] += 1.0
        norm = sum(x * x for x in row) ** 0.5 or 1.0
        rows.append([x / norm for x in row])
    return rows


def _dataset(path: Path) -> None:
    # Shared transformation task with deliberately mixed difficulty.  The
    # ground truth is used only by SkillGen's evaluator; no trace is leaked
    # into the generated skill prompt beyond what upstream itself supplies.
    instances = [
        ("t01", "Compute 17 * 23. Return only the integer.", "391"),
        ("t02", "Compute 29 * 14. Return only the integer.", "406"),
        ("t03", "Compute 37 * 16. Return only the integer.", "592"),
        ("t04", "Compute 43 * 19. Return only the integer.", "817"),
        ("t05", "Reverse the characters in the string 'frankengate'. Return only the reversed string.", "etagnekna rf".replace(" ", "")),
        ("t06", "Reverse the characters in the string 'telemetry'. Return only the reversed string.", "yrtemelet"),
        ("t07", "Sort these numbers ascending and return comma-separated: 8, 3, 11, 2.", "2,3,8,11"),
        ("t08", "Sort these numbers ascending and return comma-separated: 14, 1, 9, 6.", "1,6,9,14"),
    ]
    payload = {
        "dataset_id": "skillgen-codex-frontier-mini-2026-08-02",
        "task_name": "bounded deterministic transformations",
        "task_type": "open_ended",
        "metadata": {"provider_adapter": "codex_exec", "embedding": "hashed-256"},
        "instances": [
            {"instance_id": iid, "input": inp, "ground_truth": gt}
            for iid, inp, gt in instances
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", default="/private/tmp/skillgen-upstream.edLvQw")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    upstream = Path(args.upstream).resolve()
    if not (upstream / "pipeline.py").exists():
        raise SystemExit(f"SkillGen checkout missing: {upstream}")
    sys.path.insert(0, str(upstream))
    import llm  # type: ignore  # noqa: E402
    import main as skillgen_main  # type: ignore  # noqa: E402
    import pipeline  # type: ignore  # noqa: E402

    adapter = CodexAdapter(timeout=args.timeout)
    llm.chat = lambda prompt, **kw: adapter.text(prompt, kw.get("system", ""))
    llm.chat_json = lambda prompt, **kw: adapter.obj(prompt, kw.get("system", ""))

    def multi(messages, **kw):
        rendered = "\n\n".join(
            f"{m.get('role', 'user').upper()}: {m.get('content', '')}" for m in messages
        )
        return SimpleNamespace(role="assistant", content=adapter.text(rendered), tool_calls=None)

    llm.chat_multi_turn = multi
    llm.embed = lambda texts, **kw: _hash_embed(texts)
    llm.reset_token_stats = lambda: None
    llm.get_token_stats = lambda: []

    with tempfile.TemporaryDirectory(prefix="skillgen-codex-run-") as td:
        tmp = Path(td)
        dataset_path = tmp / "dataset.json"
        config_path = tmp / "config.yaml"
        _dataset(dataset_path)
        config_path.write_text(
            """models:\n  default: codex-frontier\n  baseline_agent: codex-frontier\n  baseline_judge: codex-frontier\n  induction: codex-frontier\n  induction_contextual: codex-frontier\n  induction_summary: codex-frontier\n  induction_pattern: codex-frontier\n  induction_contrastive: codex-frontier\n  generation_plan: codex-frontier\n  generation_execute: codex-frontier\n  verification_agent: codex-frontier\n  verification_judge: codex-frontier\n  verification_case_analyst: codex-frontier\n  verification_revision_synthesiser: codex-frontier\nllm:\n  temperature: 0.0\n  max_tokens_generation: 2048\nembedding:\n  model: hashed-256\nclustering:\n  method: kmeans\n  n_clusters: 2\n  min_cluster_size: 1\ninduction:\n  max_contrastive_pairs: 2\ngeneration:\n  use_web_search: false\n  max_search_queries: 0\n  candidate_output_dir: ./candidates\nverification:\n  sample_size: 8\n  min_sample: 4\n  seed: 42\n  min_net_gain_abs: 1\n  min_net_gain_rel: 0.0\npipeline:\n  max_refine_rounds: 1\n  baseline_runs_per_instance: 1\n  max_workers: 1\n  artifact_root: ./artifacts/runs\nskill_output:\n  path: ./skill_output\n""",
            encoding="utf-8",
        )
        os.chdir(tmp)
        started = time.time()
        status = "passed"
        error = None
        try:
            dataset = skillgen_main.load_dataset(str(dataset_path))
            skill = pipeline.run_pipeline(
                dataset.instances, dataset.task_type,
                config_path=str(config_path), dataset_id=dataset.dataset_id,
                task_name=dataset.task_name, dataset_metadata=dataset.metadata,
            )
        except Exception as exc:
            status = "runtime_failed"
            error = f"{type(exc).__name__}: {exc}"
            skill = None
        artifacts = sorted(str(p.relative_to(tmp)) for p in tmp.rglob("*") if p.is_file())
        baseline_rows = []
        for traj_path in tmp.glob("artifacts/runs/*/baseline_trajectories.jsonl"):
            for line in traj_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    baseline_rows.append(json.loads(line))
        baseline_successes = sum(bool(row.get("success")) for row in baseline_rows)

        receipt = {
            "experiment": "skillgen-codex-frontier-mini",
            "date": "2026-08-02",
            "status": status,
            "provider": "Codex non-interactive harness (subscription-backed)",
            "upstream_checkout": str(upstream),
            "dataset": "8 synthetic deterministic transformations",
            "embedding_substitution": "deterministic hashed-256; not semantic",
            "caps": {"instances": 8, "baseline_runs": 1, "max_workers": 1, "max_refine_rounds": 1, "timeout_seconds": args.timeout},
            "codex_calls": adapter.calls,
            "adapter_failures": adapter.failures,
            "elapsed_seconds": round(time.time() - started, 3),
            "generated_skill": bool(skill),
            "baseline_trajectories": len(baseline_rows),
            "baseline_successes": baseline_successes,
            "baseline_failures": len(baseline_rows) - baseline_successes,
            "artifacts": artifacts,
            "error": error,
        }

    RESULTS.mkdir(parents=True, exist_ok=True)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    out = RESULTS / "skillgen-codex-frontier-mini-2026-08-02.json"
    out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    summary = SUMMARIES / "skillgen-codex-frontier-mini-2026-08-02.md"
    summary.write_text(
        "# SkillGen Codex frontier reproduction (2026-08-02)\n\n"
        f"Status: **{status}**. The run used the pinned upstream checkout through a "
        "Codex `exec` adapter, with a deterministic hashed embedding substitute. "
        "This is an independent bounded reproduction, not an OpenRouter-equivalent "
        "or benchmark efficacy result.\n\n"
        f"- Codex calls: {adapter.calls}\n"
        f"- Generated skill: {bool(skill)}\n"
        f"- Baseline trajectories: {receipt['baseline_trajectories']} "
        f"({receipt['baseline_successes']} successes, {receipt['baseline_failures']} failures)\n"
        f"- Elapsed seconds: {receipt['elapsed_seconds']}\n"
        + (f"- Runtime error: `{error}`\n" if error else "")
        + "\nThe provider and embedding substitutions are explicit because SkillGen "
        "hard-codes OpenRouter/OpenAI clients. Any generated artifact is exploratory "
        "and is not eligible for promotion without held-out, repeated evaluation.\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
