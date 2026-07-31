# Qwen3 4B family-transfer attempt (incomplete)

Qwen3 4B was started on the same six-task family-disjoint broker fold and the
same schema-injected protocol used by the completed Llama run. The model was
materially slower: after 14/18 raw episode files, one model request exceeded
the practical wall-time budget and the run was interrupted. Thirteen episodes
have task-end receipts (no-skill 5 completed, placebo 5, trace-mined 5); the
remaining no-skill episode has no task-end receipt.

Among completed episodes, the placebo had one semantic-correct result and the
other 12 completed episodes abstained. Because the three-arm matrix is
incomplete and the interrupted episode has no outcome receipt, these numbers
are not entered into the meta-analysis and no Qwen quality or skill claim is
made. The external raw directory is retained for diagnosis; raw content is not
committed.
