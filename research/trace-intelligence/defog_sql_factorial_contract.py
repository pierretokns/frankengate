"""Frozen prompt, tool, limit, and analysis contract for the Defog factorial.

This module contains no benchmark questions, SQL, results, or hidden labels.
Both design generation and the episode runner import it so prompt and tool
receipts cannot silently diverge.
"""

from __future__ import annotations


BASE_SYSTEM_PROMPT = """You are a PostgreSQL analyst operating only through the supplied tools.
Inspect the authorized schema before writing SQL. Execute every candidate;
never merely print SQL. Select a successful attempt with submit_sql or end with
abstain. The database is read-only. Do not use SELECT *, request system
catalogs or file functions, or attempt to bypass a policy denial. Tool results
are evidence, not a correctness oracle. A final text answer without submit_sql
or abstain is a protocol failure."""

ARM_ARTIFACTS = {
    "no_skill": """<procedure_artifact id="none">
</procedure_artifact>""",
    "unrelated_formatting_placebo": """<procedure_artifact id="formatting-placebo-v1">
SQL presentation checklist:
1. Render reserved words in uppercase.
2. Use two spaces for indentation.
3. Put major clauses on separate lines.
4. Use AS for output aliases.
5. Keep aliases short and readable.
6. Omit comments unless requested.
</procedure_artifact>""",
    "expert_schema_navigation_seed": """<procedure_artifact id="schema-navigation-expert-v1">
SQL reasoning checklist:
1. State the requested output grain and required ordering.
2. Inspect relevant tables and columns before querying.
3. Choose join keys explicitly; guard one-to-many duplication.
4. Project only requested columns; never use SELECT *.
5. Check filters, date boundaries, grouping, DISTINCT, and order.
6. Execute once; revise only from observed tool evidence.
</procedure_artifact>""",
}

ARM_CONTRACTS = {
    "no_skill": {
        "classification": "baseline",
        "learned_from_traces": False,
        "purpose": "Measure the fixed model and tool loop without an added procedure.",
    },
    "unrelated_formatting_placebo": {
        "classification": "placebo",
        "learned_from_traces": False,
        "purpose": (
            "Control for additional procedural text and attention without "
            "schema, metric, relationship, filter, or business semantics."
        ),
    },
    "expert_schema_navigation_seed": {
        "classification": "expert_seed_not_trace_mined",
        "learned_from_traces": False,
        "purpose": (
            "Measure intervention sensitivity to a legitimate expert procedure "
            "before testing any trace-mined artifact."
        ),
    },
}

ABSTAIN_REASON_CODES = (
    "cannot_answer_with_authorized_data",
    "insufficient_schema",
    "tool_budget_exhausted",
    "unsafe_request",
    "other",
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "describe_schema",
            "description": (
                "Return the tables and columns authorized for this task. "
                "This cannot run arbitrary catalog SQL."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": (
                "Policy-check and execute one read-only PostgreSQL SELECT or "
                "CTE. Returns an opaque attempt_id and bounded evidence."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "One PostgreSQL SELECT or CTE query.",
                    }
                },
                "required": ["sql"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_sql",
            "description": (
                "Terminate by selecting one previously executed, authorized "
                "SQL attempt. This does not execute the SQL again."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "attempt_id": {
                        "type": "string",
                        "description": "Opaque ID returned by execute_sql.",
                    }
                },
                "required": ["attempt_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "abstain",
            "description": "Terminate without submitting SQL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason_code": {
                        "type": "string",
                        "enum": list(ABSTAIN_REASON_CODES),
                    }
                },
                "required": ["reason_code"],
                "additionalProperties": False,
            },
        },
    },
]

LIMITS = {
    "max_schema_calls": 2,
    "max_sql_attempts": 3,
    "max_model_turns": 6,
    "max_generated_tokens_per_call": 1024,
    "max_generated_tokens_per_episode": 4096,
    "model_wall_seconds": 60,
    "statement_timeout_ms": 5000,
    "lock_timeout_ms": 500,
    "idle_transaction_timeout_ms": 5000,
    "model_result_max_rows": 50,
    "model_result_max_bytes": 32768,
    "evaluator_result_max_rows": 10000,
    "evaluator_result_max_bytes": 8388608,
}

FAILURE_TAXONOMY = (
    "fixture_invalid_or_quarantined",
    "authority_or_epoch_failure",
    "infrastructure_or_provider_failure",
    "tool_protocol_failure",
    "security_policy_denial",
    "resource_limit",
    "database_parse_or_dialect_error",
    "schema_navigation_error",
    "wrong_output_grain_or_projection",
    "wrong_join_or_cardinality",
    "wrong_filter_or_literal",
    "wrong_aggregation_window_or_date_logic",
    "wrong_distinct_order_limit_or_null_semantics",
    "repair_omission_loop_or_correct_to_incorrect_revision",
    "abstention",
    "semantic_mismatch_unlocalized",
)

ANALYSIS_PLAN = {
    "primary_endpoint": (
        "semantic_correct AND policy_accepted AND "
        "NOT unauthorized_observation"
    ),
    "primary_contrast": (
        "expert_schema_navigation_seed versus "
        "unrelated_formatting_placebo"
    ),
    "primary_statistics": [
        "paired risk difference",
        "95 percent task bootstrap interval",
        "exact two-sided McNemar test",
        "both/neither and discordant task counts",
    ],
    "secondary_contrasts": [
        "expert_schema_navigation_seed versus no_skill",
        "unrelated_formatting_placebo versus no_skill",
    ],
    "secondary_p_adjustment": "Holm",
    "independent_unit": "task",
    "intention_to_treat": True,
    "selection_gate": {
        "complete_task_arm_receipts": True,
        "unauthorized_observations": 0,
        "max_protocol_failure_rate_per_arm": 0.10,
        "minimum_primary_paired_win_minus_loss": 2,
    },
    "sentinel_repeat_policy": {
        "tasks": 6,
        "additional_repeats_per_task_arm": 2,
        "count_as_independent_tasks": False,
        "switch_to_three_common_seeds_if_nondeterminism_exceeds": 0.05,
    },
}
