# Defog held-out car replay: larger protocol budget

The same six-task schedule and three arms were rerun with 10 model turns, 5
SQL attempts, and 8,192 episode tokens. No model, task, authority, or arm
artifact changed. All 18 runs were authority-valid with zero unauthorized
observations, but every generated query was rejected by the governed SQL
policy (0 successful SQL, 0 semantic-correct, 6 fallbacks per arm).

The failure was not SQL-attempt exhaustion alone: the model skipped
`describe_schema` and repeatedly generated invalid identifiers, including
columns that were not present in the referenced tables. This is recorded as a
typed model/schema-navigation null. It motivated the subsequent schema-first
and schema-injected controller experiments.
