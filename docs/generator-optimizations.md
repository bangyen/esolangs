# Generator optimization policy

Optimize emitted programs only after executing the generated result. The
source generators and tests are authoritative; this page records the standing
rules.

- Fold constant Boolean subtrees before optimizing layout.
- Reduce unused inputs when the generator's cost depends on arity.
- Reorder inputs only when the reachable orders and program mapping are known.
- Prefer literal embedding or delta reuse when the language supports it.
- Price grid width, routing, and setup separately; a local reduction can grow
  the complete program.
- Preserve a positive control for any negative search result.

Closed experiments, per-language measurements, and rejected rewrites are in
git history. Reopen one only with a new construction or a measurable gain that
clears the repository's normal optimization threshold.
