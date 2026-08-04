# Fault-category SQL checklist (v1)

Before writing the query, perform a brief internal checklist. Do not mention
the checklist or its reasoning in the answer; return only the requested
read-only SQL statement.

1. **Table selection:** identify the smallest set of schema tables that can
   answer the question. Check every join key and avoid a similarly named table
   from another concept.
2. **Projection/columns:** verify that every selected column exists on the
   chosen table or alias and that the requested measure is not a similarly
   named attribute.
3. **Predicates:** translate every constraint from the question, including
   null, equality, range, and temporal conditions. Do not invent filters.
4. **Joins and aggregation:** check join cardinality, DISTINCT, GROUP BY,
   HAVING, and aggregate scope before applying ORDER BY or LIMIT.
5. **Ordering/limits:** only order or limit when requested, and apply it after
   the intended aggregation.
6. **Final guard:** inspect the generated SQL once for table, projection,
   predicate, and ordering mismatches. If the schema cannot support the
   request, return a conservative query rather than silently substituting a
   different table.
