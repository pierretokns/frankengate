#!/usr/bin/env python3
"""Run pinned SkillGen on an executable, failure-bearing SQL cohort.

SkillGen itself supplies proposal/refinement mechanics, while this adapter
replaces its generic LLM judge with an independent SQLite execution oracle.
The model still sees only the natural-language task and schema; expected SQL
is never placed in the prompt.  The result is explicitly a bounded adapter
experiment, not a claim about native OpenRouter parity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "research/trace-intelligence/experiments/results"
SUMMARIES = ROOT / "research/trace-intelligence/experiments/summaries"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skillgen_codex_frontier_reproduction import CodexAdapter, _hash_embed  # noqa: E402


def _schema() -> str:
    return (
        "customers(id INTEGER PRIMARY KEY, name TEXT, region TEXT); "
        "orders(id INTEGER PRIMARY KEY, customer_id INTEGER, amount REAL, "
        "status TEXT, created TEXT); "
        "products(id INTEGER PRIMARY KEY, name TEXT, category TEXT); "
        "order_items(order_id INTEGER, product_id INTEGER, quantity INTEGER, "
        "unit_price REAL)."
    )


def _seed_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE customers(id INTEGER PRIMARY KEY, name TEXT, region TEXT);
        CREATE TABLE orders(id INTEGER PRIMARY KEY, customer_id INTEGER, amount REAL, status TEXT, created TEXT);
        CREATE TABLE products(id INTEGER PRIMARY KEY, name TEXT, category TEXT);
        CREATE TABLE order_items(order_id INTEGER, product_id INTEGER, quantity INTEGER, unit_price REAL);
        INSERT INTO customers VALUES
          (1,'Ana','NA'),(2,'Bo','EU'),(3,'Cy','NA'),(4,'Di','APAC'),(5,'Eli','EU'),(6,'Fox','LATAM');
        INSERT INTO orders VALUES
          (101,1,120.0,'completed','2024-01-03'),(102,1,80.0,'cancelled','2024-01-05'),
          (103,1,200.0,'completed','2024-02-11'),(104,2,50.0,'completed','2024-01-08'),
          (105,2,75.0,'completed','2024-03-02'),(106,3,300.0,'completed','2024-02-18'),
          (107,3,10.0,'pending','2024-02-20'),(108,4,90.0,'completed','2024-01-22'),
          (109,5,40.0,'cancelled','2024-01-29'),(110,5,160.0,'completed','2024-03-09');
        INSERT INTO products VALUES
          (201,'Widget','hardware'),(202,'Gadget','hardware'),(203,'Cable','accessories'),
          (204,'Adapter','accessories');
        INSERT INTO order_items VALUES
          (101,201,2,60.0),(103,202,4,50.0),(104,203,5,10.0),(105,201,1,75.0),
          (106,202,3,100.0),(108,204,2,45.0),(110,201,2,80.0);
        """
    )
    conn.commit()
    conn.close()


def _cases() -> list[dict]:
    s = _schema()
    # The first eight are the induction cohort; the final four are held out
    # and are evaluated only after the candidate is finalized.
    rows = [
        ("sql01", "Which customer has the most completed orders? Return name and count.", "SELECT c.name, COUNT(*) AS order_count FROM customers c JOIN orders o ON o.customer_id=c.id WHERE o.status='completed' GROUP BY c.id,c.name ORDER BY order_count DESC,c.id LIMIT 1;"),
        ("sql02", "Return completed revenue by region as region and total, highest total first.", "SELECT c.region, ROUND(SUM(o.amount),2) AS total FROM customers c JOIN orders o ON o.customer_id=c.id WHERE o.status='completed' GROUP BY c.region ORDER BY total DESC,c.region;"),
        ("sql03", "Which customers have never placed a completed order? Return names alphabetically.", "SELECT c.name FROM customers c LEFT JOIN orders o ON o.customer_id=c.id AND o.status='completed' WHERE o.id IS NULL ORDER BY c.name;"),
        ("sql04", "For each customer with at least two completed orders, return name and average completed amount rounded to two decimals.", "SELECT c.name, ROUND(AVG(o.amount),2) AS average_amount FROM customers c JOIN orders o ON o.customer_id=c.id WHERE o.status='completed' GROUP BY c.id,c.name HAVING COUNT(*) >= 2 ORDER BY c.name;"),
        ("sql05", "Return the product with the highest completed-order revenue, including ties, as product and revenue.", "SELECT p.name, ROUND(SUM(oi.quantity*oi.unit_price),2) AS revenue FROM products p JOIN order_items oi ON oi.product_id=p.id JOIN orders o ON o.id=oi.order_id WHERE o.status='completed' GROUP BY p.id,p.name HAVING revenue=(SELECT MAX(x.revenue) FROM (SELECT SUM(oi2.quantity*oi2.unit_price) AS revenue FROM order_items oi2 JOIN orders o2 ON o2.id=oi2.order_id WHERE o2.status='completed' GROUP BY oi2.product_id) x) ORDER BY p.name;"),
        ("sql06", "For each region return the date of its latest completed order; include regions with no completed orders and use NULL for those.", "SELECT c.region, MAX(CASE WHEN o.status='completed' THEN o.created END) AS latest_completed FROM customers c LEFT JOIN orders o ON o.customer_id=c.id GROUP BY c.region ORDER BY c.region;"),
        ("sql07", "Return the two customers with the greatest completed spend, including name and spend, highest first.", "SELECT c.name, ROUND(SUM(o.amount),2) AS spend FROM customers c JOIN orders o ON o.customer_id=c.id WHERE o.status='completed' GROUP BY c.id,c.name ORDER BY spend DESC,c.name LIMIT 2;"),
        ("sql08", "For each product category return completed revenue, but only categories above 300, highest revenue first.", "SELECT p.category, ROUND(SUM(oi.quantity*oi.unit_price),2) AS revenue FROM products p JOIN order_items oi ON oi.product_id=p.id JOIN orders o ON o.id=oi.order_id WHERE o.status='completed' GROUP BY p.category HAVING revenue > 300 ORDER BY revenue DESC,p.category;"),
        ("sql09", "Return the latest completed order id and amount for each customer who has one, ordered by customer name.", "SELECT c.name, o.id, o.amount FROM customers c JOIN orders o ON o.customer_id=c.id WHERE o.status='completed' AND o.created=(SELECT MAX(o2.created) FROM orders o2 WHERE o2.customer_id=c.id AND o2.status='completed') ORDER BY c.name;"),
        ("sql10", "Return each region's completed-order count and its share of all completed orders as a percentage rounded to one decimal.", "SELECT c.region, COUNT(*) AS order_count, ROUND(100.0*COUNT(*)/(SELECT COUNT(*) FROM orders WHERE status='completed'),1) AS pct FROM customers c JOIN orders o ON o.customer_id=c.id WHERE o.status='completed' GROUP BY c.region ORDER BY c.region;"),
        ("sql11", "Return customers whose completed spend exceeds the average completed spend per customer; return name and spend alphabetically.", "WITH spend AS (SELECT c.id,c.name,SUM(o.amount) AS total FROM customers c JOIN orders o ON o.customer_id=c.id WHERE o.status='completed' GROUP BY c.id,c.name) SELECT name, ROUND(total,2) AS spend FROM spend WHERE total > (SELECT AVG(total) FROM spend) ORDER BY name;"),
        ("sql12", "Return completed revenue by product, counting only products sold in at least two distinct orders, ordered by revenue descending.", "SELECT p.name, ROUND(SUM(oi.quantity*oi.unit_price),2) AS revenue FROM products p JOIN order_items oi ON oi.product_id=p.id JOIN orders o ON o.id=oi.order_id WHERE o.status='completed' GROUP BY p.id,p.name HAVING COUNT(DISTINCT o.id)>=2 ORDER BY revenue DESC,p.name;"),
    ]
    return [
        {"instance_id": iid, "input": f"Schema: {s}\nQuestion: {question}\nReturn only SQL.", "ground_truth": sql, "metadata": {"benchmark": "sqlite_exact"}}
        for iid, question, sql in rows
    ]


def _extract_sql(text: str) -> str:
    text = (text or "").strip()
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            text = parts[1]
            if text.lstrip().lower().startswith("sql"):
                text = text.lstrip()[3:]
    upper = text.upper()
    starts = [p for p in (upper.find("SELECT"), upper.find("WITH")) if p >= 0]
    if not starts:
        return text.strip().strip("`")
    return text[min(starts):].strip().strip("`").strip()


def _rows(conn: sqlite3.Connection, sql: str) -> list[tuple]:
    cur = conn.execute(sql)
    return [tuple(row) for row in cur.fetchall()]


def _sql_eval(traj, instance, task_type, **kwargs):
    sql = _extract_sql(traj.final_output)
    conn = sqlite3.connect(instance.metadata["db_path"])
    try:
        expected = _rows(conn, instance.ground_truth)
        actual = _rows(conn, sql)
        # SQLite returns ints/floats consistently enough for this fixture; a
        # numeric tolerance avoids representation noise while preserving row
        # order and exact cardinality.
        ok = len(expected) == len(actual) and all(
            len(a) == len(e) and all(
                abs(float(x) - float(y)) <= 1e-6 if isinstance(x, (int, float)) and isinstance(y, (int, float)) else x == y
                for x, y in zip(a, e)
            ) for a, e in zip(actual, expected)
        )
        traj.success = bool(ok)
        traj.score = 1.0 if ok else 0.0
        traj.metadata = dict(traj.metadata or {})
        traj.metadata["sqlite_exact_eval"] = {"passed": bool(ok), "sql": sql, "expected_rows": expected, "actual_rows": actual}
        if not ok:
            traj.error_summary = "result mismatch"
    except Exception as exc:
        traj.success = False
        traj.score = 0.0
        traj.error_summary = f"{type(exc).__name__}: {exc}"
        traj.metadata = dict(traj.metadata or {})
        traj.metadata["sqlite_exact_eval"] = {"passed": False, "sql": sql, "error": str(exc)}
    finally:
        conn.close()
    return traj


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", default="/private/tmp/skillgen-upstream.edLvQw")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
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
    llm.chat_multi_turn = lambda messages, **kw: SimpleNamespace(
        role="assistant", content=adapter.text("\n\n".join(f"{m.get('role','user').upper()}: {m.get('content','')}" for m in messages)), tool_calls=None
    )
    llm.embed = lambda texts, **kw: _hash_embed(texts)
    llm.reset_token_stats = lambda: None
    llm.get_token_stats = lambda: []
    trajectory.evaluate_trajectory = _sql_eval

    started = time.time()
    status = "passed"
    error = None
    heldout = None
    train_rows = _cases()[:8]
    heldout_rows = _cases()[8:]
    with tempfile.TemporaryDirectory(prefix="skillgen-sql-codex-") as td:
        tmp = Path(td)
        db = tmp / "fixture.sqlite"
        _seed_db(db)
        for row in train_rows + heldout_rows:
            row["metadata"]["db_path"] = str(db)
        dataset_path = tmp / "dataset.json"
        dataset_path.write_text(json.dumps({"dataset_id": "skillgen-sql-codex-2026-08-02", "task_name": "executable SQL synthesis", "task_type": "binary", "metadata": {"benchmark": "sqlite_exact"}, "instances": train_rows}, indent=2))
        config_path = tmp / "config.yaml"
        config_path.write_text("""models:\n  default: codex-frontier\n  baseline_agent: codex-frontier\n  baseline_judge: codex-frontier\n  induction: codex-frontier\n  induction_contextual: codex-frontier\n  induction_summary: codex-frontier\n  induction_pattern: codex-frontier\n  induction_contrastive: codex-frontier\n  generation_plan: codex-frontier\n  generation_execute: codex-frontier\n  verification_agent: codex-frontier\n  verification_judge: codex-frontier\n  verification_case_analyst: codex-frontier\n  verification_revision_synthesiser: codex-frontier\nllm:\n  temperature: 0.0\n  max_tokens_generation: 2048\nembedding:\n  model: hashed-256\nclustering:\n  method: kmeans\n  n_clusters: 2\n  min_cluster_size: 1\ninduction:\n  max_contrastive_pairs: 2\ngeneration:\n  use_web_search: false\n  max_search_queries: 0\n  candidate_output_dir: ./candidates\nverification:\n  sample_size: 8\n  min_sample: 4\n  seed: 42\n  min_net_gain_abs: 1\n  min_net_gain_rel: 0.0\npipeline:\n  max_refine_rounds: 1\n  baseline_runs_per_instance: 1\n  max_workers: 1\n  artifact_root: ./artifacts/runs\nskill_output:\n  path: ./skill_output\n""")
        os.chdir(tmp)
        try:
            dataset = skillgen_main.load_dataset(str(dataset_path))
            skill = pipeline.run_pipeline(dataset.instances, dataset.task_type, config_path=str(config_path), dataset_id=dataset.dataset_id, task_name=dataset.task_name, dataset_metadata=dataset.metadata)
            # Independent held-out replay: re-collect baseline trajectories,
            # split by the SQLite oracle, then replay the finalized skill.
            from models import TaskInstance, TaskType  # type: ignore
            held_instances = [TaskInstance(instance_id=r["instance_id"], input=r["input"], ground_truth=r["ground_truth"], metadata=r["metadata"]) for r in heldout_rows]
            if skill is not None:
                cfg = trajectory.AgentConfig(model="codex-frontier", judge_model="codex-frontier", temperature=0.0)
                base = trajectory.collect_trajectories(held_instances, TaskType.binary, config=cfg, max_workers=1)
                base_map = {t.instance_id: t for t in base}
                failures = [i for i in held_instances if not base_map[i.instance_id].success]
                successes = [i for i in held_instances if base_map[i.instance_id].success]
                eff, _ = effectiveness.verify_effectiveness(skill, failures, successes, TaskType.binary, baseline_cache=base_map, baseline_agent_model="codex-frontier", baseline_judge_model="codex-frontier", agent_model="codex-frontier", judge_model="codex-frontier", min_net_gain_abs=1, min_net_gain_rel=0.0, artifact_dir=str(tmp / "heldout"), artifact_prefix="heldout")
                heldout = {"n": eff.paired_n, "baseline_acc": eff.baseline_acc, "skill_acc": eff.skill_acc, "repair": eff.repair_count, "regression": eff.regression_count, "net_gain": eff.net_gain, "passed": eff.passed, "baseline_failures": len(failures), "baseline_successes": len(successes)}
        except Exception as exc:
            status = "runtime_failed"
            error = f"{type(exc).__name__}: {exc}"
            skill = None
        run_files = sorted(str(p.relative_to(tmp)) for p in tmp.rglob("*") if p.is_file())
        baselines = []
        for p in tmp.glob("artifacts/runs/*/baseline_trajectories.jsonl"):
            baselines.extend(json.loads(line) for line in p.read_text().splitlines() if line.strip())
    receipt = {"experiment": "skillgen-codex-sql-frontier", "date": "2026-08-02", "status": status, "provider": "Codex non-interactive harness (subscription-backed)", "upstream_checkout": str(upstream), "dataset": {"train_tasks": 8, "heldout_tasks": 4, "outcome_oracle": "SQLite execution and exact row comparison"}, "embedding_substitution": "deterministic hashed-256; not semantic", "caps": {"baseline_runs": 1, "max_workers": 1, "max_refine_rounds": 1, "timeout_seconds": args.timeout}, "codex_calls": adapter.calls, "adapter_failures": adapter.failures, "elapsed_seconds": round(time.time() - started, 3), "baseline_trajectories": len(baselines), "baseline_successes": sum(bool(r.get("success")) for r in baselines), "baseline_failures": sum(not bool(r.get("success")) for r in baselines), "generated_skill": bool(skill), "heldout": heldout, "artifacts": run_files, "error": error}
    RESULTS.mkdir(parents=True, exist_ok=True); SUMMARIES.mkdir(parents=True, exist_ok=True)
    (RESULTS / "skillgen-codex-sql-frontier-2026-08-02.json").write_text(json.dumps(receipt, indent=2) + "\n")
    (SUMMARIES / "skillgen-codex-sql-frontier-2026-08-02.md").write_text("# SkillGen executable SQL frontier reproduction (2026-08-02)\n\n" + f"Status: **{status}**. This run used pinned SkillGen with a Codex adapter and an independent SQLite execution oracle. Train baseline: {receipt['baseline_successes']}/{receipt['baseline_trajectories']} passed; generated skill: {bool(skill)}.\n\n" + (f"Held-out replay: `{heldout}`\n\n" if heldout else "No held-out replay was possible because no candidate was produced.\n\n") + "The Codex provider and hashed embedding substitutions are explicit. Results are not native OpenRouter parity and no candidate is eligible for integration without a larger, repeated, family-held-out study.\n")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
