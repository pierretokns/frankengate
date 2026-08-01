#!/usr/bin/env python3
"""Bounded SkillGen reproduction on the staged BIRD-SQL corpus."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "research/trace-intelligence/experiments/results"
SUMMARIES = ROOT / "research/trace-intelligence/experiments/summaries"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from skillgen_codex_frontier_reproduction import CodexAdapter, _hash_embed  # noqa: E402
from skillgen_codex_sql_frontier_reproduction import _sql_eval  # noqa: E402


def _load_cases(base: Path, split: str, ids: list[int]) -> list[dict]:
    rows = [json.loads(line) for line in (base / "data" / f"{split}.jsonl").read_text().splitlines() if line.strip()]
    by_index = {int(row["task_id"].rsplit("-", 1)[1]): row for row in rows}
    out = []
    for idx in ids:
        row = by_index[idx]
        task_id = row["task_id"]
        db_name = row["data"]["db_name"]
        gold = json.loads((base / "gold" / f"{task_id}.json").read_text())["gold_sql"]
        schema = (base / "schemas" / f"{db_name}.sql").read_text()
        out.append({
            "instance_id": task_id,
            "input": f"Schema for database {db_name}:\n{schema}\n\nQuestion:\n{row['prompt']}\n\nReturn only SQL.",
            "ground_truth": gold,
            "metadata": {"benchmark": "sqlite_exact", "db_path": str(base / "databases" / f"{db_name}.sqlite"), "db_name": db_name, "question_id": row["data"]["question_id"]},
        })
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", default="/private/tmp/world-model-harness-v0.2.2/packages/environment-capture/bird-sql")
    parser.add_argument("--upstream", default="/private/tmp/skillgen-upstream.edLvQw")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    corpus = Path(args.corpus).resolve()
    upstream = Path(args.upstream).resolve()
    sys.path.insert(0, str(upstream))
    import main as skillgen_main  # type: ignore  # noqa: E402
    import pipeline  # type: ignore  # noqa: E402
    import trajectory  # type: ignore  # noqa: E402
    import effectiveness  # type: ignore  # noqa: E402
    import llm  # type: ignore  # noqa: E402

    adapter = CodexAdapter(timeout=args.timeout)
    llm.chat = lambda prompt, **kw: adapter.text(prompt, kw.get("system", ""))
    llm.chat_json = lambda prompt, **kw: adapter.obj(prompt, kw.get("system", ""))
    llm.chat_multi_turn = lambda messages, **kw: SimpleNamespace(role="assistant", content=adapter.text("\n\n".join(f"{m.get('role','user').upper()}: {m.get('content','')}" for m in messages)), tool_calls=None)
    llm.embed = lambda texts, **kw: _hash_embed(texts)
    llm.reset_token_stats = lambda: None
    llm.get_token_stats = lambda: []
    trajectory.evaluate_trajectory = _sql_eval

    # Mix nested, multi-table, aggregation, and cross-database questions in
    # training; hold out a different family of questions and databases.
    train = _load_cases(corpus, "train", [13, 14, 15, 16, 41, 42, 43, 44])
    held = _load_cases(corpus, "train", [45, 46, 47, 48, 70, 71, 136, 137])
    started = time.time(); status = "passed"; error = None; skill = None; heldout = None
    with tempfile.TemporaryDirectory(prefix="skillgen-bird-codex-") as td:
        tmp = Path(td); dataset_path = tmp / "dataset.json"; config_path = tmp / "config.yaml"
        dataset_path.write_text(json.dumps({"dataset_id": "skillgen-bird-codex-2026-08-02", "task_name": "BIRD-SQL executable synthesis", "task_type": "binary", "metadata": {"corpus": str(corpus)}, "instances": train}, indent=2))
        config_path.write_text("""models:\n  default: codex-frontier\n  baseline_agent: codex-frontier\n  baseline_judge: codex-frontier\n  induction: codex-frontier\n  induction_contextual: codex-frontier\n  induction_summary: codex-frontier\n  induction_pattern: codex-frontier\n  induction_contrastive: codex-frontier\n  generation_plan: codex-frontier\n  generation_execute: codex-frontier\n  verification_agent: codex-frontier\n  verification_judge: codex-frontier\n  verification_case_analyst: codex-frontier\n  verification_revision_synthesiser: codex-frontier\nllm:\n  temperature: 0.0\n  max_tokens_generation: 2048\nembedding:\n  model: hashed-256\nclustering:\n  method: kmeans\n  n_clusters: 2\n  min_cluster_size: 1\ninduction:\n  max_contrastive_pairs: 2\ngeneration:\n  use_web_search: false\n  max_search_queries: 0\n  candidate_output_dir: ./candidates\nverification:\n  sample_size: 12\n  min_sample: 4\n  seed: 42\n  min_net_gain_abs: 1\n  min_net_gain_rel: 0.0\npipeline:\n  max_refine_rounds: 1\n  baseline_runs_per_instance: 1\n  max_workers: 1\n  artifact_root: ./artifacts/runs\nskill_output:\n  path: ./skill_output\n""")
        os.chdir(tmp)
        try:
            dataset = skillgen_main.load_dataset(str(dataset_path))
            skill = pipeline.run_pipeline(dataset.instances, dataset.task_type, config_path=str(config_path), dataset_id=dataset.dataset_id, task_name=dataset.task_name, dataset_metadata=dataset.metadata)
            if skill is not None:
                from models import TaskInstance, TaskType  # type: ignore
                held_instances = [TaskInstance(instance_id=r["instance_id"], input=r["input"], ground_truth=r["ground_truth"], metadata=r["metadata"]) for r in held]
                cfg = trajectory.AgentConfig(model="codex-frontier", judge_model="codex-frontier", temperature=0.0)
                base = trajectory.collect_trajectories(held_instances, TaskType.BINARY, config=cfg, max_workers=1)
                base_map = {t.instance_id: t for t in base}
                failures = [i for i in held_instances if not base_map[i.instance_id].success]
                successes = [i for i in held_instances if base_map[i.instance_id].success]
                eff, _ = effectiveness.verify_effectiveness(skill, failures, successes, TaskType.BINARY, baseline_cache=base_map, baseline_agent_model="codex-frontier", baseline_judge_model="codex-frontier", agent_model="codex-frontier", judge_model="codex-frontier", min_net_gain_abs=1, min_net_gain_rel=0.0, artifact_dir=str(tmp / "heldout"), artifact_prefix="heldout")
                heldout = {"n": eff.paired_n, "baseline_acc": eff.baseline_acc, "skill_acc": eff.skill_acc, "repair": eff.repair_count, "regression": eff.regression_count, "net_gain": eff.net_gain, "passed": eff.passed, "baseline_failures": len(failures), "baseline_successes": len(successes)}
        except Exception as exc:
            status = "runtime_failed"; error = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"; skill = None
        run_files = sorted(str(p.relative_to(tmp)) for p in tmp.rglob("*") if p.is_file())
        baselines = []
        for p in tmp.glob("artifacts/runs/*/baseline_trajectories.jsonl"):
            baselines.extend(json.loads(line) for line in p.read_text().splitlines() if line.strip())
    receipt = {"experiment": "skillgen-codex-bird-frontier", "date": "2026-08-02", "status": status, "provider": "Codex non-interactive harness (subscription-backed)", "corpus": str(corpus), "corpus_split": "BIRD-SQL train questions with local gold sidecars and SQLite databases", "train_task_ids": [r["instance_id"] for r in train], "heldout_task_ids": [r["instance_id"] for r in held], "outcome_oracle": "SQLite execution and exact ordered row comparison", "embedding_substitution": "deterministic hashed-256; not semantic", "caps": {"train_tasks": len(train), "heldout_tasks": len(held), "baseline_runs": 1, "max_workers": 1, "max_refine_rounds": 1, "timeout_seconds": args.timeout}, "codex_calls": adapter.calls, "adapter_failures": adapter.failures, "elapsed_seconds": round(time.time() - started, 3), "baseline_trajectories": len(baselines), "baseline_successes": sum(bool(r.get("success")) for r in baselines), "baseline_failures": sum(not bool(r.get("success")) for r in baselines), "generated_skill": bool(skill), "heldout": heldout, "artifacts": run_files, "error": error}
    RESULTS.mkdir(parents=True, exist_ok=True); SUMMARIES.mkdir(parents=True, exist_ok=True)
    (RESULTS / "skillgen-codex-bird-frontier-2026-08-02.json").write_text(json.dumps(receipt, indent=2) + "\n")
    (SUMMARIES / "skillgen-codex-bird-frontier-2026-08-02.md").write_text("# SkillGen BIRD-SQL frontier reproduction (2026-08-02)\n\n" + f"Status: **{status}**. Pinned SkillGen ran on {len(train)} BIRD-SQL train tasks using Codex and an independent SQLite execution oracle. Baseline: {receipt['baseline_successes']}/{receipt['baseline_trajectories']} passed; generated skill: {bool(skill)}.\n\n" + (f"Held-out replay: `{heldout}`\n\n" if heldout else "No held-out replay was possible because the baseline produced no mined-failure candidate.\n\n") + "The provider and hashed embedding substitutions are explicit. This is not native OpenRouter parity; promotion still requires repeated family-held-out cohorts and independent replay.\n")
    print(json.dumps(receipt, indent=2)); return 0


if __name__ == "__main__":
    raise SystemExit(main())
