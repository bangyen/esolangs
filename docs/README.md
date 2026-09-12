# Documentation

Four entry points: [roadmap](roadmap.md) is live work only; [limitations](limitations.md)
is the boundary ledger of contracts and conventions; [walls](walls.md) holds
structural impossibility claims, each falsifiable and several already fallen;
[languages](languages.md) is the capability matrix, generated from the registry by
`scripts/make_languages_doc.py` and not edited by hand.

## Generators, languages, and proofs

- [a_painter_ant_generator](generators/a_painter_ant_generator.md) — the invariants that make the
  construction valid: distinct separated leaves, collapse before the cycle-2 dance.
- [a_painter_ant_uniform_proof](generators/a_painter_ant_uniform_proof.md) — why those invariants
  hold at every arity. Lemmas are checked by `tests/tools/apa_uniform_proof_check.py`.
- [arrowqueue_generator](generators/arrowqueue_generator.md) — `arrowqueue(t)` is total at every
  arity; halts iff the selected bit is `0`. Lemmas run executably in 0.8s.
- [minifuck_generator](generators/minifuck_generator.md) — staged and sculpted constructions, both
  verified against the joint simulator before a template returns.
- [pct_squared_minus_one_generator](generators/pct_squared_minus_one_generator.md) — six
  constructions; the packed ladder covers all tables through four inputs.
- [wii2d_generator](generators/wii2d_generator.md) — source-size and runtime policies, not
  language walls; the source is authoritative.
- [painfuck](painfuck.md) — a run of `c` or `t` is one counted operator, not one per
  character.
- [streetcode](streetcode.md) — road-graph, heading, and junction rules; a junction is a
  runtime choice, not a compile-time branch.
- [proofs](proofs.md) — the two Lean results that survived `4317b0bb` as prose, plus the
  123 geometry certificate.

## Tooling and policy

- [verification_tooling](verification_tooling.md) — `scripts/verify.py` is authoritative;
  why mutmut is pinned and what `mutate_one.py` bundles.
- [line_tooling](line_tooling.md) — renderer, extractor, and lattice constraints;
  one-pixel clearance and per-render extent caches.
- [CONTRIBUTING](CONTRIBUTING.md) — what earns a new language a place here, and where
  rejected candidates get recorded.
- [SECURITY](SECURITY.md) — interpreters run untrusted programs by design; what that
  puts in and out of scope.
