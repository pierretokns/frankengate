# NL2SQL pinned-suite checkpoint (2026-08-01)

The NL2SQL capability suite was run through the repository’s locked dependency
environment:

```text
uv run --frozen python -m unittest discover -s nl2sql_capabilities/tests -p 'test_*.py'
Ran 61 tests in 1.330s
OK
```

This is the authoritative NL2SQL capability result. The host-level `make
verify` target remains useful as a no-install smoke, where two `sqlglot`
modules are explicit skips because system Python does not have the locked
dependency.
