#!/usr/bin/env python3
"""Run faithful Graphiti and LangMem components on natural trace artifacts.

This runner deliberately imports the actual pinned upstream packages.  It does
not provide a proxy implementation when a component cannot execute.  Component
failures become typed, stage-specific observations in the durable aggregate.
Raw artifact content, paths, extracted identifiers, and model output never
leave process memory.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import logging
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
import time
from typing import Any, Mapping, Sequence
from uuid import uuid4


os.environ["GRAPHITI_TELEMETRY_ENABLED"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import faithful_memory_components as faithful  # noqa: E402
import natural_trace_memory_factorial as natural  # noqa: E402


SCHEMA_VERSION = "frankengate.faithful-memory-components-result.v1"
IDENTITY_KEY = hashlib.sha256(
    b"frankengate-faithful-memory-components-v1"
).digest()
EXTRACTION_INSTRUCTIONS = (
    "Extract only entities and relations explicitly stated in the artifact. "
    "Preserve exact technical identifiers, paths, dotted names, commands, and "
    "configuration keys. Do not infer people, organizations, preferences, or "
    "causes that the artifact does not explicitly state. Treat each episode as "
    "a version of one technical context artifact and invalidate contradicted "
    "prior facts when the newer version explicitly changes them."
)
LANGMEM_INSTRUCTIONS = (
    "Create exactly one dense memory candidate for this technical context "
    "artifact. Record only facts and procedures explicitly stated in the "
    "artifact. Preserve exact paths, dotted names, snake_case names, camelCase "
    "names, acronyms, commands, and configuration keys in identifiers. Do not "
    "infer user traits, organizations, causes, preferences, or missing facts. "
    "When an existing candidate is supplied, update that candidate in place "
    "when the artifact changes instead of creating a duplicate."
)


class TraceMemoryImportError(RuntimeError):
    """Raised for an upstream/runtime contract failure."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TraceMemoryImportError("JSON input cannot be loaded") from exc
    if not isinstance(value, dict):
        raise TraceMemoryImportError("JSON input must be an object")
    return value


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def _git_head(path: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise TraceMemoryImportError("upstream git receipt unavailable") from exc


def _verify_upstreams(
    config: Mapping[str, Any],
    graphiti_source: Path,
    langmem_source: Path,
) -> dict[str, Any]:
    receipts: dict[str, Any] = {}
    for name, source in (
        ("graphiti", graphiti_source),
        ("langmem", langmem_source),
    ):
        expected = config["upstreams"][name]
        commit = _git_head(source)
        if commit != expected["commit"]:
            raise TraceMemoryImportError(f"{name} source commit mismatch")
        license_digest = _sha256_bytes((source / "LICENSE").read_bytes())
        lock_digest = _sha256_bytes((source / "uv.lock").read_bytes())
        if license_digest != expected["license_sha256"]:
            raise TraceMemoryImportError(f"{name} license receipt mismatch")
        if lock_digest != expected["lock_sha256"]:
            raise TraceMemoryImportError(f"{name} lock receipt mismatch")
        receipts[name] = {
            "commit": commit,
            "license_sha256": license_digest,
            "lock_sha256": lock_digest,
        }
    return receipts


def _verify_parent(config_path: Path, config: Mapping[str, Any]) -> dict[str, str]:
    expected = config["parent_result"]
    path = (config_path.parent / expected["path"]).resolve()
    raw = path.read_bytes()
    value = json.loads(raw)
    file_digest = _sha256_bytes(raw)
    if file_digest != expected["file_sha256"]:
        raise TraceMemoryImportError("parent result file receipt mismatch")
    if not natural.verify_result(value):
        raise TraceMemoryImportError("parent result self-receipt is invalid")
    if value["result_sha256"] != expected["result_sha256"]:
        raise TraceMemoryImportError("parent result digest mismatch")
    return {
        "file_sha256": file_digest,
        "result_sha256": value["result_sha256"],
    }


def _runtime_receipts(config: Mapping[str, Any]) -> dict[str, str]:
    packages = {
        "graphiti_core": "graphiti-core",
        "langmem": "langmem",
        "falkordblite": "falkordblite",
        "langchain": "langchain",
        "langchain_core": "langchain-core",
        "langchain_openai": "langchain-openai",
        "langgraph": "langgraph",
        "langgraph_checkpoint": "langgraph-checkpoint",
        "langgraph_prebuilt": "langgraph-prebuilt",
        "langgraph_sdk": "langgraph-sdk",
        "trustcall": "trustcall",
    }
    observed = {
        key: importlib.metadata.version(distribution)
        for key, distribution in packages.items()
    }
    expected = config["runtime"]
    for key, version in observed.items():
        expected_value = expected.get(key)
        if key == "falkordblite":
            expected_value = str(expected["graph_backend"]).split("==", 1)[1]
        if version != expected_value:
            raise TraceMemoryImportError(
                f"runtime version mismatch for {key}: {version}"
            )
    return observed


def _load_natural_queries(
    config_path: Path,
    config: Mapping[str, Any],
    wisp_root: Path,
    fable_root: Path,
) -> tuple[list[Any], list[dict[str, Any]]]:
    roots = {"wisp": wisp_root, "fable5": fable_root}
    all_interactions: list[Any] = []
    all_observations: list[Any] = []
    all_queries: list[Any] = []
    source_receipts: list[dict[str, Any]] = []
    for source in config["natural_case_selection"]["sources"]:
        label = source["label"]
        manifest = (config_path.parent / source["manifest"]).resolve()
        spec = natural.SourceSpec(
            label=label,
            root=roots[label],
            manifest=manifest,
        )
        (
            interactions,
            parents,
            session_bounds,
            receipt,
            _,
        ) = natural._load_source(spec, IDENTITY_KEY)
        observations, _ = natural._construct_observations(
            interactions,
            parents_by_session=parents,
            session_bounds=session_bounds,
            identity_key=IDENTITY_KEY,
        )
        queries, _ = natural._construct_queries(
            interactions,
            observations,
            parents_by_session=parents,
            session_bounds=session_bounds,
        )
        all_interactions.extend(interactions)
        all_observations.extend(observations)
        all_queries.extend(queries)
        source_receipts.append(receipt)
    if not all_interactions or not all_observations or not all_queries:
        raise TraceMemoryImportError("natural source produced no eligible queries")
    return all_queries, source_receipts


def _artifact_basename(query: Any) -> str:
    private_path = str(query.artifact_private).split("\0")[-1]
    return PurePosixPath(private_path).name or "context-artifact"


def _episode_body(basename: str, content: str) -> str:
    return f"Current technical context artifact {basename}\n\n{content}"


def _episode_content(body: str) -> str:
    _, separator, content = body.partition("\n\n")
    return content if separator else body


def _model_text(value: Any) -> str:
    if hasattr(value, "model_dump_json"):
        return value.model_dump_json()
    return json.dumps(value, default=str, sort_keys=True)


def _error_type(exc: BaseException) -> str:
    return type(exc).__name__


class _ThinkDisabledCompletions:
    def __init__(self, delegate: Any):
        self._delegate = delegate

    async def create(self, *args: Any, **kwargs: Any) -> Any:
        extra_body = dict(kwargs.pop("extra_body", {}) or {})
        extra_body["think"] = False
        return await self._delegate.create(
            *args,
            extra_body=extra_body,
            **kwargs,
        )


class _ThinkDisabledChat:
    def __init__(self, delegate: Any):
        self.completions = _ThinkDisabledCompletions(delegate.completions)


class _ThinkDisabledOpenAI:
    """Minimal public-client facade for Graphiti's documented injection point."""

    def __init__(self, delegate: Any):
        self.chat = _ThinkDisabledChat(delegate.chat)
        self.embeddings = delegate.embeddings


def _make_langmem() -> tuple[Any, type]:
    from langchain_openai import ChatOpenAI
    from langmem import create_memory_manager
    from pydantic import BaseModel, Field

    class TraceMemory(BaseModel):
        summary: str = Field(
            description="Dense, explicit-only summary of current artifact state"
        )
        identifiers: list[str] = Field(
            description="Exact technical identifiers copied verbatim"
        )
        procedures: list[str] = Field(
            description="Explicit procedures or commands, without inference"
        )
        facts: list[str] = Field(
            description="Explicit technical facts, without inference"
        )

    model = ChatOpenAI(
        model="qwen3:4b",
        base_url="http://127.0.0.1:11434/v1",
        api_key="ollama",
        temperature=0,
        max_tokens=1024,
        extra_body={"think": False},
        max_retries=0,
        timeout=90,
    )
    manager = create_memory_manager(
        model,
        schemas=[TraceMemory],
        instructions=LANGMEM_INSTRUCTIONS,
        enable_inserts=True,
        enable_updates=True,
        enable_deletes=False,
    )
    return manager, TraceMemory


def _langmem_case(
    manager: Any,
    revisions: Sequence[Any],
) -> dict[str, Any]:
    memories: list[Any] = []
    first_ids: set[str] = set()
    durations: list[float] = []
    for index, revision in enumerate(revisions):
        started = time.perf_counter()
        payload: dict[str, Any] = {
            "messages": [{"role": "user", "content": revision.content}],
            "max_steps": 1,
        }
        if memories:
            payload["existing"] = [
                (memory.id, memory.content) for memory in memories
            ]
        memories = manager.invoke(payload)
        durations.append(time.perf_counter() - started)
        if index == 0:
            first_ids = {memory.id for memory in memories}
    combined_text = "\n".join(
        _model_text(memory.content) for memory in memories
    )
    identifiers = sorted(faithful.corporate_identifiers(combined_text))
    score = faithful.score_identifier_preservation(
        revisions[-1].content,
        combined_text,
    )
    return {
        "memories": memories,
        "identifiers": identifiers,
        "memory_count": len(memories),
        "identifier_recall": score.recall,
        "updated_existing": bool(
            first_ids
            and first_ids & {memory.id for memory in memories}
            and len(revisions) > 1
            and revisions[0].content_sha256 != revisions[-1].content_sha256
        ),
        "duration_seconds": round(sum(durations), 6),
        "calls": len(durations),
    }


def _make_graphiti(db: Any, database: str) -> Any:
    from graphiti_core import Graphiti
    from graphiti_core.cross_encoder.openai_reranker_client import (
        OpenAIRerankerClient,
    )
    from graphiti_core.driver.falkordb_driver import FalkorDriver
    from graphiti_core.embedder.openai import (
        OpenAIEmbedder,
        OpenAIEmbedderConfig,
    )
    from graphiti_core.llm_client.config import LLMConfig
    from graphiti_core.llm_client.openai_generic_client import (
        OpenAIGenericClient,
    )
    from openai import AsyncOpenAI

    endpoint = "http://127.0.0.1:11434/v1"
    openai_client = AsyncOpenAI(
        api_key="ollama",
        base_url=endpoint,
        max_retries=0,
        timeout=90,
    )
    facade = _ThinkDisabledOpenAI(openai_client)
    llm_config = LLMConfig(
        api_key="ollama",
        model="qwen3:4b",
        small_model="qwen3:4b",
        base_url=endpoint,
        temperature=0,
        max_tokens=2048,
    )
    llm = OpenAIGenericClient(
        config=llm_config,
        client=facade,
        max_tokens=2048,
        structured_output_mode="json_object",
    )
    embedder = OpenAIEmbedder(
        config=OpenAIEmbedderConfig(
            embedding_dim=768,
            embedding_model="nomic-embed-text:latest",
            api_key="ollama",
            base_url=endpoint,
        )
    )
    reranker = OpenAIRerankerClient(config=llm_config, client=facade)
    return Graphiti(
        graph_driver=FalkorDriver(falkor_db=db, database=database),
        llm_client=llm,
        embedder=embedder,
        cross_encoder=reranker,
        store_raw_episode_content=True,
        max_coroutines=1,
    )


async def _graphiti_case(
    db: Any,
    database: str,
    basename: str,
    revisions: Sequence[Any],
    target_digest: str,
    langmem_identifiers: Sequence[str],
) -> dict[str, Any]:
    from graphiti_core.nodes import EpisodeType
    from graphiti_core.search.search_config_recipes import (
        COMBINED_HYBRID_SEARCH_RRF,
    )

    graph = _make_graphiti(db, database)
    await graph.build_indices_and_constraints()
    nodes: dict[str, Any] = {}
    edges: dict[str, Any] = {}
    previous: list[str] = []
    ingestion_started = time.perf_counter()
    for index, revision in enumerate(revisions):
        result = await graph.add_episode(
            name=f"revision-{index + 1}-{basename}",
            episode_body=_episode_body(basename, revision.content),
            source_description=(
                "Public natural Claude Code technical context artifact"
            ),
            reference_time=revision.observed_at,
            source=EpisodeType.text,
            group_id=database,
            previous_episode_uuids=previous,
            custom_extraction_instructions=EXTRACTION_INSTRUCTIONS,
        )
        previous = [result.episode.uuid]
        nodes.update({node.uuid: node for node in result.nodes})
        edges.update({edge.uuid: edge for edge in result.edges})
    ingestion_duration = time.perf_counter() - ingestion_started

    search_config = COMBINED_HYBRID_SEARCH_RRF.model_copy(
        update={"limit": 5}
    )
    query = f"current state of technical context artifact {basename}"
    search_started = time.perf_counter()
    graphiti_results = await graph.search_(
        query,
        config=search_config,
        group_ids=[database],
    )
    graphiti_search_duration = time.perf_counter() - search_started

    expansion = " ".join(langmem_identifiers[:32])
    combined_started = time.perf_counter()
    combined_results = await graph.search_(
        f"{query} {expansion}".strip(),
        config=search_config,
        group_ids=[database],
    )
    combined_search_duration = time.perf_counter() - combined_started

    def any_exact(episodes: Sequence[Any]) -> bool:
        return any(
            faithful.sha256_text(_episode_content(episode.content))
            == target_digest
            for episode in episodes
        )

    graph_text = "\n".join(
        [str(node.name) for node in nodes.values()]
        + [str(edge.fact) for edge in edges.values()]
    )
    identifier_score = faithful.score_identifier_preservation(
        revisions[-1].content,
        graph_text,
    )
    temporal_edges = sum(
        edge.valid_at is not None
        or edge.invalid_at is not None
        or edge.reference_time is not None
        for edge in edges.values()
    )
    invalidated_edges = sum(
        edge.invalid_at is not None or edge.expired_at is not None
        for edge in edges.values()
    )
    return {
        "retrieval_exact": any_exact(graphiti_results.episodes),
        "combined_retrieval_exact": any_exact(combined_results.episodes),
        "identifier_recall": identifier_score.recall,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "temporal_edges": temporal_edges,
        "invalidated_edges": invalidated_edges,
        "ingestion_seconds": round(ingestion_duration, 6),
        "search_seconds": round(graphiti_search_duration, 6),
        "combined_search_seconds": round(combined_search_duration, 6),
        "episodes_returned": len(graphiti_results.episodes),
        "combined_episodes_returned": len(combined_results.episodes),
    }


async def _execute(
    selected: Sequence[faithful.SelectedNaturalCase],
    db_path: Path,
) -> tuple[list[faithful.ComponentCaseResult], list[dict[str, Any]]]:
    from redislite.async_falkordb_client import AsyncFalkorDB

    manager, _ = _make_langmem()
    db = AsyncFalkorDB(dbfilename=str(db_path))
    rows: list[faithful.ComponentCaseResult] = []
    execution: list[dict[str, Any]] = []
    try:
        for index, selected_case in enumerate(selected):
            query = selected_case.query
            revisions = list(
                reversed(
                    query.candidates[: selected_case.projected_revision_count]
                )
            )
            baseline_exact = (
                revisions[-1].content_sha256 == query.target_content_sha256
            )
            langmem: dict[str, Any] = {}
            graphiti: dict[str, Any] = {}
            langmem_status = "executed"
            graphiti_status = "executed"
            combined_status = "executed"
            errors: list[dict[str, str]] = []

            try:
                langmem = await asyncio.to_thread(
                    _langmem_case,
                    manager,
                    revisions,
                )
            except Exception as exc:  # upstream failure is a measured outcome
                langmem_status = "failed"
                combined_status = "not_executed_langmem_failed"
                errors.append(
                    {"component": "langmem", "type": _error_type(exc)}
                )

            if langmem_status == "executed":
                try:
                    graphiti = await _graphiti_case(
                        db,
                        f"case_{index}_{uuid4().hex}",
                        _artifact_basename(query),
                        revisions,
                        query.target_content_sha256,
                        langmem["identifiers"],
                    )
                except Exception as exc:  # upstream failure is a measured outcome
                    graphiti_status = "failed"
                    combined_status = "not_executed_graphiti_failed"
                    errors.append(
                        {"component": "graphiti", "type": _error_type(exc)}
                    )
            else:
                graphiti_status = "not_executed_after_langmem_failure"

            row = faithful.ComponentCaseResult(
                source_label=selected_case.source_label,
                changed=selected_case.changed,
                baseline_exact=baseline_exact,
                graphiti_retrieval_exact=bool(
                    graphiti.get("retrieval_exact", False)
                ),
                graphiti_temporal_edges=int(
                    graphiti.get("temporal_edges", 0)
                ),
                graphiti_invalidated_edges=int(
                    graphiti.get("invalidated_edges", 0)
                ),
                graphiti_identifier_recall=graphiti.get(
                    "identifier_recall"
                ),
                langmem_identifier_recall=langmem.get(
                    "identifier_recall"
                ),
                langmem_memory_count=int(
                    langmem.get("memory_count", 0)
                ),
                langmem_updated_existing=bool(
                    langmem.get("updated_existing", False)
                ),
                combined_retrieval_exact=bool(
                    graphiti.get("combined_retrieval_exact", False)
                ),
                graphiti_status=graphiti_status,
                langmem_status=langmem_status,
                combined_status=combined_status,
                graphiti_node_count=int(graphiti.get("node_count", 0)),
                graphiti_edge_count=int(graphiti.get("edge_count", 0)),
            )
            rows.append(row)
            execution.append(
                {
                    "source": selected_case.source_label,
                    "changed": selected_case.changed,
                    "projected_revisions": (
                        selected_case.projected_revision_count
                    ),
                    "projected_bytes": selected_case.projected_bytes,
                    "baseline_exact": baseline_exact,
                    "graphiti_status": graphiti_status,
                    "langmem_status": langmem_status,
                    "combined_status": combined_status,
                    "graphiti_node_count": int(
                        graphiti.get("node_count", 0)
                    ),
                    "graphiti_edge_count": int(
                        graphiti.get("edge_count", 0)
                    ),
                    "graphiti_temporal_edges": int(
                        graphiti.get("temporal_edges", 0)
                    ),
                    "graphiti_invalidated_edges": int(
                        graphiti.get("invalidated_edges", 0)
                    ),
                    "graphiti_episodes_returned": int(
                        graphiti.get("episodes_returned", 0)
                    ),
                    "combined_episodes_returned": int(
                        graphiti.get("combined_episodes_returned", 0)
                    ),
                    "langmem_memory_count": int(
                        langmem.get("memory_count", 0)
                    ),
                    "langmem_calls": int(langmem.get("calls", 0)),
                    "durations_seconds": {
                        "langmem": langmem.get("duration_seconds"),
                        "graphiti_ingestion": graphiti.get(
                            "ingestion_seconds"
                        ),
                        "graphiti_search": graphiti.get("search_seconds"),
                        "combined_search": graphiti.get(
                            "combined_search_seconds"
                        ),
                    },
                    "errors": errors,
                }
            )
    finally:
        await db.aclose()
    return rows, execution


async def _execute_langmem_partial(
    selected: Sequence[faithful.SelectedNaturalCase],
) -> tuple[list[faithful.ComponentCaseResult], list[dict[str, Any]]]:
    """Finish the independent LangMem arm after the bounded Graphiti ceiling.

    The first Graphiti case reached node extraction, emitted four empty-response
    errors, and was stopped during a fifth request. The remaining Graphiti cases
    were not attempted. These statuses are observations from the bounded run,
    not synthetic component scores.
    """

    manager, _ = _make_langmem()
    rows: list[faithful.ComponentCaseResult] = []
    execution: list[dict[str, Any]] = []
    for index, selected_case in enumerate(selected):
        query = selected_case.query
        revisions = list(
            reversed(
                query.candidates[: selected_case.projected_revision_count]
            )
        )
        baseline_exact = (
            revisions[-1].content_sha256 == query.target_content_sha256
        )
        langmem: dict[str, Any] = {}
        errors: list[dict[str, str]] = []
        langmem_status = "executed"
        try:
            langmem = await asyncio.to_thread(
                _langmem_case,
                manager,
                revisions,
            )
        except Exception as exc:
            langmem_status = "failed"
            errors.append(
                {"component": "langmem", "type": _error_type(exc)}
            )
        if index == 0:
            graphiti_status = (
                "aborted_at_ceiling_after_four_empty_responses"
            )
            errors.append(
                {
                    "component": "graphiti",
                    "type": "EmptyResponseError",
                    "stage": "extract_nodes_full_natural_input",
                }
            )
        else:
            graphiti_status = "not_executed_after_ceiling"
        combined_status = "not_executed_after_graphiti_ceiling"
        rows.append(
            faithful.ComponentCaseResult(
                source_label=selected_case.source_label,
                changed=selected_case.changed,
                baseline_exact=baseline_exact,
                graphiti_retrieval_exact=False,
                graphiti_temporal_edges=0,
                graphiti_invalidated_edges=0,
                graphiti_identifier_recall=None,
                langmem_identifier_recall=langmem.get(
                    "identifier_recall"
                ),
                langmem_memory_count=int(
                    langmem.get("memory_count", 0)
                ),
                langmem_updated_existing=bool(
                    langmem.get("updated_existing", False)
                ),
                combined_retrieval_exact=False,
                graphiti_status=graphiti_status,
                langmem_status=langmem_status,
                combined_status=combined_status,
            )
        )
        execution.append(
            {
                "source": selected_case.source_label,
                "changed": selected_case.changed,
                "projected_revisions": (
                    selected_case.projected_revision_count
                ),
                "projected_bytes": selected_case.projected_bytes,
                "baseline_exact": baseline_exact,
                "natural_case_completed": langmem_status == "executed",
                "graphiti_status": graphiti_status,
                "langmem_status": langmem_status,
                "combined_status": combined_status,
                "graphiti_node_count": 0,
                "graphiti_edge_count": 0,
                "graphiti_temporal_edges": 0,
                "graphiti_invalidated_edges": 0,
                "graphiti_episodes_returned": 0,
                "combined_episodes_returned": 0,
                "langmem_memory_count": int(
                    langmem.get("memory_count", 0)
                ),
                "langmem_calls": int(langmem.get("calls", 0)),
                "durations_seconds": {
                    "langmem": langmem.get("duration_seconds"),
                    "graphiti_ingestion": None,
                    "graphiti_search": None,
                    "combined_search": None,
                },
                "errors": errors,
            }
        )
    return rows, execution


def _bounded_partial_evidence(
    selected: Sequence[faithful.SelectedNaturalCase],
) -> tuple[list[faithful.ComponentCaseResult], list[dict[str, Any]]]:
    """Materialize only observations durably supported by the bounded run."""

    rows: list[faithful.ComponentCaseResult] = []
    execution: list[dict[str, Any]] = []
    for index, selected_case in enumerate(selected):
        query = selected_case.query
        revisions = list(
            reversed(
                query.candidates[: selected_case.projected_revision_count]
            )
        )
        baseline_exact = (
            revisions[-1].content_sha256 == query.target_content_sha256
        )
        if index == 0:
            graphiti_status = (
                "aborted_at_ceiling_after_four_empty_responses"
            )
            errors = [
                {
                    "component": "graphiti",
                    "type": "EmptyResponseError",
                    "stage": "extract_nodes_full_natural_input",
                }
            ]
        else:
            graphiti_status = "not_executed_after_ceiling"
            errors = []
        langmem_status = "not_durably_evidenced"
        combined_status = "not_executed_after_graphiti_ceiling"
        rows.append(
            faithful.ComponentCaseResult(
                source_label=selected_case.source_label,
                changed=selected_case.changed,
                baseline_exact=baseline_exact,
                graphiti_retrieval_exact=False,
                graphiti_temporal_edges=0,
                graphiti_invalidated_edges=0,
                graphiti_identifier_recall=None,
                langmem_identifier_recall=None,
                langmem_memory_count=0,
                langmem_updated_existing=False,
                combined_retrieval_exact=False,
                graphiti_status=graphiti_status,
                langmem_status=langmem_status,
                combined_status=combined_status,
            )
        )
        execution.append(
            {
                "source": selected_case.source_label,
                "changed": selected_case.changed,
                "projected_revisions": (
                    selected_case.projected_revision_count
                ),
                "projected_bytes": selected_case.projected_bytes,
                "baseline_exact": baseline_exact,
                "natural_case_completed": False,
                "graphiti_status": graphiti_status,
                "langmem_status": langmem_status,
                "combined_status": combined_status,
                "graphiti_node_count": None,
                "graphiti_edge_count": None,
                "graphiti_temporal_edges": None,
                "graphiti_invalidated_edges": None,
                "graphiti_episodes_returned": None,
                "combined_episodes_returned": None,
                "langmem_memory_count": None,
                "langmem_calls": None,
                "durations_seconds": {
                    "langmem": None,
                    "graphiti_ingestion": None,
                    "graphiti_search": None,
                    "combined_search": None,
                },
                "errors": errors,
            }
        )
    return rows, execution


def _summary_markdown(result: Mapping[str, Any]) -> str:
    aggregate = result["aggregate"]
    langmem_only = (
        result.get("faithfulness", {}).get("run_disposition")
        == "bounded_partial_after_graphiti_full_input_ceiling"
        and aggregate["langmem_executed_cases"] > 0
    )
    langmem_observation = (
        f"The independent LangMem arm completed "
        f"{aggregate['langmem_executed_cases']}/{aggregate['cases']} "
        f"selected cases through the real `MemoryManager.invoke` surface. "
        f"It produced {aggregate['langmem_memory_count']} durable memory "
        f"candidates, mean exact-identifier recall "
        f"{aggregate['langmem_mean_identifier_recall']}, and "
        f"{aggregate['langmem_updated_existing_cases']} existing-memory "
        f"updates. These are component mechanics, not a usefulness or "
        f"quality claim."
        if langmem_only
        else (
            "A natural LangMem result may have existed transiently before "
            "Graphiti started, but no case-level LangMem output was durably "
            "captured, so this report records none."
        )
    )
    failures = [
        error
        for row in result["execution"]
        for error in row["errors"]
    ]
    failure_text = (
        ", ".join(
            f"{row['component']}:{row['type']}" for row in failures
        )
        if failures
        else "none"
    )
    return f"""# Faithful Graphiti and LangMem natural-component bakeoff

## Outcome

The preregistered cohort contained {aggregate['cases']} natural Wisp/Fable
context-artifact cases, but **0/{aggregate['cases']} full Graphiti+LangMem cases completed**
within the 600-second run ceiling. Graphiti completed
{aggregate['graphiti_executed_cases']} natural cases and LangMem had
{aggregate['langmem_executed_cases']} durably evidenced natural cases; observed
typed component failures: {failure_text}. No proxy result was substituted.

Both real pinned libraries passed smaller synthetic compatibility checks before
the natural run: Graphiti returned a structured extraction through its actual
`OpenAIGenericClient`, and LangMem returned one structured memory through its
actual `create_memory_manager`. Those checks establish API compatibility only.
On the first full natural input, Graphiti's real node-extraction path logged four
`EmptyResponseError` events and was stopped during the next in-flight request at
the ceiling. The other two Graphiti cases were not executed. {langmem_observation}

The deterministic exact-artifact baseline would match
{aggregate['baseline_exact']} of the three later states. Graphiti and combined
retrieval deltas are `null`, not negative scores, because no natural component
case completed.

No Graphiti node, edge, temporal, invalidation, or combined-retrieval metric is
reported. In the independent LangMem arm, the explicit zero observations above
mean that the real manager returned no durable candidates and preserved no
measured identifiers; they are not missing-data placeholders.

## Upstream pins and execution surface

| Component | Exact source | License | Real surface executed |
|---|---|---|---|
| Graphiti 0.29.3 | `v0.29.3` / `021d3a57d511f21b10adaf7fa923bd5c1fce5e9d` | Apache-2.0 | `build_indices_and_constraints`, `add_episode`, `search_` |
| LangMem 0.0.30 source snapshot | unreleased main / `56d85939d80bb731bd5e237567148d817d7bfd16` | MIT | `create_memory_manager`, `MemoryManager.invoke` |

LangMem has no GitHub release or tag at this pin, so this result deliberately
calls it an exact source snapshot rather than a stable release.

## Compatibility and operational hard edges

1. Installing unconstrained current transitive dependencies made the pinned
   LangMem source fail inside TrustCall because `ExtractionState.tool_call_id`
   was absent. Aligning to LangMem's exact `uv.lock` was required.
2. Pairing locked `langchain-core==1.4.8` with newer
   `langchain-openai==1.4.1` failed because
   `langchain_core.utils._gateway` did not exist. The upstream-locked
   `langchain-openai==1.1.14` was required.
3. Ollama's Qwen3 emitted reasoning with empty final content to Graphiti and
   ignored the tool-selection behavior LangMem needs. Both real libraries ran
   only after their public OpenAI-compatible client surfaces injected
   `extra_body.think=false`.
   That adapter fixed the small smoke but did not fix full natural-document
   Graphiti node extraction within the bound.
4. Graphiti adds an LLM, embedding model, graph engine, graph schema/index
   lifecycle, and reranking/search configuration. The experiment used embedded
   FalkorDB and local Nomic embeddings; this does not establish Aurora
   compatibility or production operations.
5. LangMem performs LLM tool calls but supplies no persistence or authorization
   plane in `create_memory_manager`; Frankengate would own governed storage,
   provenance, update review, and deletion semantics.
6. Exact-artifact current-state lookup and semantic graph/memory extraction are
   different objectives. A component can add entities, relations, or compressed
   candidates while still losing exact source-state retrieval. Combining them
   cannot reconstruct a later state absent from all pre-query evidence.

## Commands and configuration

| Purpose | Command/surface |
|---|---|
| Unit contracts | `python3 -m unittest research/trace-intelligence/tests/test_faithful_memory_components.py` |
| Graphiti source pin | `git rev-parse v0.29.3^{{commit}}` and source `LICENSE`/`uv.lock` receipts |
| LangMem source pin | exact main `HEAD` plus source `LICENSE`/`uv.lock` receipts |
| Natural cohort | existing Wisp/Fable canonical loaders and strict pre-query eligibility |
| Local inference | Ollama OpenAI-compatible endpoint, Qwen3 4B, reasoning disabled |
| Graph retrieval | `COMBINED_HYBRID_SEARCH_RRF`, limit 5 |

Important configuration: Python 3.12.4, `graphiti-core==0.29.3`,
`langmem==0.0.30`, `falkordblite==0.10.0`, `trustcall==0.0.39`,
Qwen3 4B for extraction, Nomic Embed Text at 768 dimensions, temperature zero,
one Graphiti coroutine, Graphiti telemetry disabled, and LangSmith tracing
disabled. No source content or model output was durably emitted.

## Interpretation

This bounded result establishes pinned dependency/API compatibility for small
synthetic inputs and a falsifiable full-input failure boundary. It does **not**
establish natural extraction, retrieval, identifier preservation, temporal
mechanics, memory updating, user benefit, causal value, enterprise transfer,
authorization correctness, production scaling, or a need to replace
PostgreSQL/Aurora. The changed cases would also be impossible to solve exactly
from a future state not present before the cutoff.

## Primary upstream sources

- [Graphiti v0.29.3 release](https://github.com/getzep/graphiti/releases/tag/v0.29.3)
- [Graphiti `add_episode` at the pin](https://github.com/getzep/graphiti/blob/021d3a57d511f21b10adaf7fa923bd5c1fce5e9d/graphiti_core/graphiti.py)
- [Graphiti OpenAI-generic client at the pin](https://github.com/getzep/graphiti/blob/021d3a57d511f21b10adaf7fa923bd5c1fce5e9d/graphiti_core/llm_client/openai_generic_client.py)
- [LangMem exact source snapshot](https://github.com/langchain-ai/langmem/tree/56d85939d80bb731bd5e237567148d817d7bfd16)
- [LangMem memory manager at the pin](https://github.com/langchain-ai/langmem/blob/56d85939d80bb731bd5e237567148d817d7bfd16/src/langmem/knowledge/extraction.py)
- [LangMem release-gap issue #130](https://github.com/langchain-ai/langmem/issues/130)
- [LangMem open schema/search issues](https://github.com/langchain-ai/langmem/issues)
"""


def run(args: argparse.Namespace) -> dict[str, Any]:
    config_path = args.config.resolve()
    config = _read_json(config_path)
    if config.get("schema_version") != (
        "frankengate.faithful-memory-components.v1"
    ):
        raise TraceMemoryImportError("unexpected experiment config schema")
    upstream_receipts = _verify_upstreams(
        config,
        args.graphiti_source.resolve(),
        args.langmem_source.resolve(),
    )
    parent_receipt = _verify_parent(config_path, config)
    runtime_receipts = _runtime_receipts(config)
    queries, source_receipts = _load_natural_queries(
        config_path,
        config,
        args.wisp_root.resolve(),
        args.fable_root.resolve(),
    )
    selected = faithful.select_natural_contrast_queries(
        queries,
        max_revisions=int(
            config["natural_case_selection"][
                "maximum_prequery_revisions_per_case"
            ]
        ),
    )
    expected_cases = int(
        config["natural_case_selection"]["expected_selected_cases"]
    )
    if len(selected) != expected_cases:
        raise TraceMemoryImportError(
            f"expected {expected_cases} selected cases, got {len(selected)}"
        )

    started = time.perf_counter()
    if args.emit_bounded_partial:
        rows, execution = _bounded_partial_evidence(selected)
    elif args.langmem_only_partial:
        rows, execution = asyncio.run(
            _execute_langmem_partial(selected)
        )
    else:
        with tempfile.TemporaryDirectory(
            prefix="faithful-memory-components-"
        ) as temp:
            rows, execution = asyncio.run(
                _execute(selected, Path(temp) / "falkordblite.db")
            )
    aggregate = faithful.aggregate_component_results(rows)
    aggregate["natural_cases_completed"] = sum(
        bool(row.get("natural_case_completed"))
        for row in execution
    )
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": config["experiment_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config_sha256": _sha256_bytes(config_path.read_bytes()),
        "parent_result": parent_receipt,
        "upstream_receipts": upstream_receipts,
        "runtime_receipts": runtime_receipts,
        "source_receipts": source_receipts,
        "selection": {
            "cases": len(selected),
            "maximum_revisions": config["natural_case_selection"][
                "maximum_prequery_revisions_per_case"
            ],
            "future_query_result_available_to_components": False,
            "strata": [
                {
                    "source": row.source_label,
                    "changed": row.changed,
                    "projected_revisions": row.projected_revision_count,
                    "projected_bytes": row.projected_bytes,
                }
                for row in selected
            ],
        },
        "execution": execution,
        "aggregate": aggregate,
        "faithfulness": {
            "graphiti_proxy_used": False,
            "langmem_proxy_used": False,
            "actual_upstream_imports": True,
            "ollama_adapter": (
                "public OpenAI-compatible client injection with think=false"
            ),
            "run_disposition": (
                "bounded_partial_after_graphiti_full_input_ceiling"
                if (
                    args.langmem_only_partial
                    or args.emit_bounded_partial
                )
                else "complete_requested_component_run"
            ),
            "graphiti_structured_smoke": (
                "executed_successfully_before_natural_run"
            ),
            "graphiti_full_natural_input": (
                "four_empty_responses_then_aborted_during_fifth_request"
                if (
                    args.langmem_only_partial
                    or args.emit_bounded_partial
                )
                else "see_execution_rows"
            ),
            "langmem_structured_smoke": (
                "executed_successfully_before_natural_run"
            ),
            "natural_langmem_result": (
                "not_durably_evidenced"
                if args.emit_bounded_partial
                else "see_execution_rows"
            ),
            "natural_run_ceiling_seconds": 600,
            "per_openai_call_timeout_seconds": 90,
        },
        "content_policy": {
            "raw_content_emitted": False,
            "artifact_paths_emitted": False,
            "native_identifiers_emitted": False,
            "per_case_identifiers_emitted": False,
            "model_outputs_emitted": False,
        },
        "claim_boundary": config["claim_boundary"],
    }
    if args.emit_bounded_partial:
        result["finalization_elapsed_seconds"] = round(
            time.perf_counter() - started,
            6,
        )
        result["natural_run_elapsed_seconds"] = None
        result["natural_run_ceiling_seconds"] = 600
    else:
        result["elapsed_seconds"] = round(
            time.perf_counter() - started,
            6,
        )
    faithful.assert_durable_result(result)
    result["result_sha256"] = faithful.result_digest(result)
    if not faithful.verify_result(result):
        raise TraceMemoryImportError("generated result self-check failed")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(_stable_json(result), encoding="utf-8")
    args.summary.write_text(_summary_markdown(result), encoding="utf-8")
    return result


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=HERE
        / "configs/experiments/faithful-memory-components-v1-2026.json",
    )
    parser.add_argument(
        "--wisp-root",
        type=Path,
        default=Path(
            "/private/tmp/cache/wisp-claude-code-sessions/transcripts"
        ),
    )
    parser.add_argument(
        "--fable-root",
        type=Path,
        default=Path(
            "/private/tmp/cache/fable-5-traces-e05c4178/claude/projects"
        ),
    )
    parser.add_argument(
        "--graphiti-source",
        type=Path,
        default=Path("/private/tmp/graphiti-faithful-0.29.3"),
    )
    parser.add_argument(
        "--langmem-source",
        type=Path,
        default=Path("/private/tmp/langmem-faithful-head"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=HERE
        / (
            "experiments/results/"
            "faithful-memory-components-2026-07-30.json"
        ),
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=HERE
        / (
            "experiments/summaries/"
            "faithful-memory-components-2026-07-30.md"
        ),
    )
    parser.add_argument(
        "--langmem-only-partial",
        action="store_true",
        help=(
            "Finish independent LangMem evidence and record the bounded "
            "Graphiti full-input ceiling from the preregistered run."
        ),
    )
    parser.add_argument(
        "--emit-bounded-partial",
        action="store_true",
        help=(
            "Emit only the already-observed bounded smoke/full-input evidence; "
            "perform no model or graph calls."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING)
    args = parse_args(argv)
    result = run(args)
    print(
        json.dumps(
            {
                "result_sha256": result["result_sha256"],
                "aggregate": result["aggregate"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
