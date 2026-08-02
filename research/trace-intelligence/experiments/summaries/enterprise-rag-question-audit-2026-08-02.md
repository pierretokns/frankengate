# EnterpriseRAG-Bench question audit

Date: 2026-08-02  
Status: completed dataset-structure audit; no retrieval or skill claim

We downloaded only the public 409 KB question parquet, not the 1.4 GB document
parquet. The audit is therefore deliberately about what the benchmark can test,
not about retrieval performance.

The 500 questions contain 2,427 atomic answer facts and 742 expected document
references; 93 questions require more than one document. The taxonomy is not
uniform: basic and semantic lookup account for 300/500 questions, while the
harder safety/evidence slices are smaller but explicit: 30 constrained, 20
conflicting-information, 20 information-not-found, and 20 completeness cases.
Source coverage spans nine enterprise systems, with Jira (100 question-source
assignments), Confluence (114), Slack (79), and Gmail/Drive/GitHub/Linear,
Fireflies, and HubSpot also represented.

Two concrete implications follow for Frankengate:

1. The benchmark is suitable for a document retrieval fixture with fixed slices
   for semantic recall, cross-document aggregation, conflict/temporal choice,
   completeness, and abstention. Those slices should be measured separately,
   not collapsed into one RAG score.
2. The benchmark is not a trace-learning dataset. It has no principals,
   exposure/rejection events, tool inputs or outcomes, correction histories,
   authority epochs, or changed-system replay. It cannot validate a corporate
   ontology, a mined skill, a reusable SQL/tool capsule, or cross-user learning.

The 30 questions without source-type metadata are themselves a useful fixture:
metadata-aware retrieval cannot silently assume every question has a source
filter. We should preserve an explicit “metadata absent” arm and measure whether
the system abstains or overgeneralizes.

Receipt: [`enterprise-rag-question-audit-2026-08-02.json`](../results/enterprise-rag-question-audit-2026-08-02.json)  
Runner: [`enterprise_rag_question_audit.py`](../../enterprise_rag_question_audit.py)
