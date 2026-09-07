# Proofs

Machine-checked Lean proofs live in `extra/lean/`; source and tests are the
primary evidence. This file records their scope:

- the MAMMALIAN construction is total under its stated arithmetic invariants;
- Factor's renderer round-trips its encoded program;
- a `%^2^-1` program reading its own inputs cannot compute a two-input
  Boolean function;
- the 123 geometry reduction has a per-arity certificate.

These results do not extend to parameterized programs beyond the construction
models they state. A new claim needs an executable witness or a checked proof.
