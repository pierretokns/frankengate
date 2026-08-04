# Legacy candidate stability on a real Claude Code history export

## Question

Do the modernized Termolator/TermSuite-style termhood and
AcronymExpansion-style contextual extraction produce candidates that recur
across real project histories, rather than only on a small synthetic or single
corpus probe?

## Corpus and protocol

The study scanned the locally available `.claude/projects` export from the
public [`bbuchsbaum/brainflow2`](https://github.com/bbuchsbaum/brainflow2)
repository. It contained 442 JSONL files, 432 sessions, 65 project-directory
labels, and 202,393 parsed messages. Project names, messages, terms, paths,
and identifiers were not written to the receipt; project labels and candidate
strings were replaced with hashes. The legacy ports were run as deterministic
candidate generators over each project's sessions. For terms, the top 100
document-frequency candidates per project were compared. Acronym results were
kept only when the initials check passed.

## Results

| Candidate family | Result |
|---|---:|
| Unique top-term hashes | 2,249 |
| Top terms in exactly one project | 1,472 |
| Top terms in two or more projects | 777 |
| Top terms in all 65 projects | 0 |
| Pairwise top-term Jaccard (min / median / max) | `.005025 / .092896 / .449275` |
| Valid acronym hashes | 170 |
| Acronym hashes in two or more projects | 36 |
| Exact acronym-definition pairs | 341 |
| Exact pairs in two or more projects | 57 |
| Exact pairs in all projects | 0 |

## Interpretation

This is stronger evidence for the **candidate-generation** value of the old
ideas than the earlier 49-document probe: a real multi-project history has a
substantial recurring vocabulary layer. It still does not tell us whether a
recurring term is a corporate concept, shared open-source boilerplate, a
framework name, or accidental lexical overlap. The absence of any candidate in
all 65 projects and the low median overlap argue against a global alias table
built from frequency alone. Acronym definitions are even more local; only 36
of 170 valid acronym hashes crossed a project boundary.

The practical use is therefore a **project- and time-scoped review queue**:

```text
termhood/acronym candidates
  -> exact identifier and scope filters
  -> project/time recurrence and hard-negative checks
  -> human/frontier adjudication
  -> replay or retrieval impact test
  -> only then a versioned alias/term projection
```

This does not establish enterprise alias precision, semantic equivalence,
embedding lift, skill improvement, or user benefit. The source is a public
research proxy, not an authorized enterprise cohort with outcome labels.

## Receipts

- [content-free result](../results/claude-history-legacy-candidate-stability-2026-08-09.json)
- [independent verification](../results/claude-history-legacy-candidate-stability-verification-2026-08-09.json)
- [`claude_history_legacy_candidate_stability.py`](../../claude_history_legacy_candidate_stability.py)
