# Defog held-out car replay: schema-first instruction only

The larger protocol budget was retained and every arm received the same
arm-independent instruction to call `describe_schema` before SQL. Llama 3.2
still made zero schema calls; all 18 runs remained policy-denied with 0/6
semantic correctness and 6/6 fallbacks in every arm.

This is a typed model/harness null. The next schema-injected run supplies the
authorized catalog directly so semantic evaluation can be reached without
depending on a model's first tool choice.
