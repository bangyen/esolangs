# Roadmap

Only live work belongs here. Completed findings, negative results, and
conditional ideas stay in [`docs/walls.md`](walls.md) and
[`docs/limitations.md`](limitations.md).

## New interpreters

The candidate list is empty: DINAC, Alight, function x(y), Packlang and
Interprogck8 are implemented, and Pinyin is rejected. Both outcomes are
recorded in [`docs/limitations.md`](limitations.md) — Pinyin's routing
pinned and its two-input program priced at 4 characters, but its triples
did not: the page's own selection rule reroutes 8 of 23 Hello, world!
characters, and its truth machine on input 1 is unreachable under all 384
readings.

The list refills by survey rather than by waiting — APL arrived that way and
is now implemented, with its own boolean generator.

## Research

- **Take what the reordering screen names.** The screen is re-run and
  permanent: `scripts/screen_input_reorder.py` measures, at n=3 over all
  256 tables, the shortest build over the six input orders against the
  identity's, for all 70 registry languages (the deleted 59-generator
  ledger's method, `46a32c85`). Its metric reproduces every prior figure
  still verified at HEAD exactly (dig 19.8%, flowchart 17.1%, modulous
  16.4%, arrowqueue 12.4%), and its premise is executed, not assumed: 288
  runs over polynomial and brainfuck, all six orders, every row of three
  tables. It re-runs in ~4s — re-run it rather than citing this list once
  a generator moves.

  Unwired with real upside: `%^2^-1` 36.3%, Interprogck8 21.1%, Dig
  19.8%, Flowchart 17.1%, Minifuck 13.1%, 123 13.0%, BF-PDA
  12.6%, ArrowQueue 12.4% (own entry below), Sophie 8.1%, WII2D 5.1%,
  BrainIf 4.9%, COD 3.2% (concentrated in 12/256 tables), SLOW ACV
  MAMMALIAN 3.2%; everything else screens under 3%. Two stale figures
  moved with their generators — polynomial 25.1% -> 15.9% (the dense
  rework, `22f0dce9`..`57caea1d`) and sophie 16.4% -> 8.1% (the
  subfunction merge, `cbca1f46`) — and COD's old clean verdict is gone
  (0% -> 3.2%, the dependency reduction, `a25f266f`). Polynomial's and
  Modulous's language walls stand (`docs/walls.md`); Dig and Flowchart
  are grid placements, 2D layout
  surgery rather than renaming a branch operand. Every wired generator
  screens at 3.1% residual (Back) or less.

  *For the no-input languages the wire may be renaming.* Their inputs are
  substituted, not read from a stream, so building the permuted table and
  renaming `{Xi}` slots would reach the screened figure without any build
  entering a permuted frame — untested. Where a build must enter one, the
  trap stands: a generator that validates its own output during
  construction needs that check frame-mapped, or it rejects every correct
  placement and reports a clean 0.00% — ZTOALC L did exactly that, and
  wii2d's budget machinery is the next likely instance. A 0% where the
  screen shows upside is a diagnosis, not a verdict.

## Conditional follow-up

- **WII2D's exactly-once embed convention.** Dense n=10 is a wall of the
  convention, not the machine: a per-node re-embed does dense n=10 in 14432
  characters and dense n=13 in 146540, every row executed. Re-examine the
  convention only if the arity ever matters — it is fenced by the invariant
  in `tests/tools/test_boolean_parameterized.py`, and Dotlang and 2dFish were
  removed rather than exempted from it. The audit is in
  [`docs/walls.md`](walls.md).
- **Minifuck's mux round loop.** The rest of the sculpt closed (pool code in
  `5b35c66b`, the named accumulator from nine); the round loop did not, and is
  *measured* not to. Over 36864 round transitions at exhaustive n=3 no round
  moved a row above the frontier, but 27656 moved one below it, so the
  post-fix column is not predictable without walking. Reopen only with a rule
  for the `_mux_probe` cascade — now 69% of the build — not a wider search.
- **ArrowQueue reusable drain.** Ship the verified deep-fold drain only if a
  proof makes folding meaningfully testable at `n >= 5`; current coverage does
  not reach its crossover.
- **Reorder ArrowQueue inputs.** A three-input screen leaves 12.4% headroom,
  but its queued inputs cannot be renamed in place. Find a re-enqueue and
  grid-routing construction, then compare emitted, executed programs against
  the current template; abandon it if the routing spends the apparent gain.
- **`%^2^-1` fourteen inputs.** The staged fold's endgame strands its last
  duplicated cofactor pairs: rank order is steerable (pulsed doubling), but a
  merge needs the pair's value gap `d` inside a wipe window, and diving the
  partner maps `d -> amount - d` with the amount free in the window -- a
  derived, unbuilt alignment controller. Build it only if a ~20x-thirteen
  build cost (~430k plan ops, ~8MB templates, ~226 ops per merge) is
  acceptable; the walls around it are recorded in
  [`docs/walls.md`](walls.md).
