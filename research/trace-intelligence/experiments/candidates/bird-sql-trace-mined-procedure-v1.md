Before answering a database question:
1. Inspect the available schema and use the exact table and column names.
2. Map the requested entities and relationships through declared foreign keys.
3. Translate every filter and comparison from the question into an explicit SQL predicate.
4. Use joins or EXISTS only where the relationship requires them; preserve the requested output columns and order.
5. Produce one read-only SELECT or WITH query and stop after the query is complete.
