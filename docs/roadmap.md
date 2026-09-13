# Roadmap

Only live work belongs here.  Completed findings and negative results go to
[walls](walls.md) and [limitations](limitations.md).

## New interpreters

The candidate list is empty.  Alight, function x(y), Packlang and
Interprogck8 are implemented; Pinyin is rejected, and DINAC was
implemented and then pruned (see below).  Both outcomes are
recorded in [limitations](limitations.md) -- Pinyin's routing pinned and its
two-input program priced at 4 characters, but its triples did not pin: the
page's own selection rule reroutes 8 of 23 Hello, world! characters, and its
truth machine on input 1 is unreachable under all 384 readings.

The list refills by survey rather than by waiting.  APL arrived that way and
is implemented, with its own boolean generator.

## Curation: the prune to 60

65 languages now.  The prune to 65 removed the four ordinary imperative
languages in costume (DINAC, MyScript, Basicfuck, Nevermind); the
criterion, the bands below it, and the floor are in
[limitations](limitations.md#curation-what-the-collection-can-afford-to-lose).

**Live: the second band, 65 -> 60.**  It exhausts the same criterion --
Suptiftam, Lamfunc, `function x(y)`, Between, Point Break.  All five are
ordinary imperative or functional languages whose generator is a shared
decision-tree shim in `other.py` or `parameterized.py`, so no construction
goes with them.

Two costs to pay before taking it, neither a blocker:

- **Suptiftam is the worked example** in [walls](walls.md)'s
  verification-boundaries section -- the program whose unbounded frame
  growth is what `run_until_halt_or_ancestor` decides and
  `run_until_halt_or_cycle` cannot.  It is also one of the six languages
  where an exhausted read is a *value*.  Re-point both at another language
  that defines `frame_entry_key` before deleting it, the way the prune to
  65 re-pointed three tests at Flowchart, or the wall loses its evidence.
- **The 0%-upside list** in [limitations](limitations.md) names Point Break
  and Suptiftam among the eight generators the reorder screen closes.  The
  list is re-run, not cited, so it will shrink on its own -- but the
  sentence's count needs the same edit.

Do not take the band below it (60 -> 55) on this criterion: it cuts family
duplicates rather than costume, which is a different argument and is
recorded as such.

## Research: take what the reordering screen names

`scripts/screen_input_reorder.py` is permanent and re-run.  It measures, at
n=3 over all 256 tables, the shortest build over the six input orders
against the identity's, for all 65 registry languages -- the deleted
59-generator ledger's method (`46a32c85`).  It re-runs in ~4s, so **re-run
it rather than citing this list** once a generator moves.

Its metric reproduces every prior figure still verified at HEAD exactly (dig
19.8%, flowchart 17.1%, modulous 16.4%, arrowqueue 12.4%), and its premise
is executed rather than assumed: 288 runs over polynomial and brainfuck, all
six orders, every row of three tables.

Unwired, with real upside:

| Generator | Upside | Generator | Upside |
| --- | --- | --- | --- |
| `%^2^-1` | 36.3% | 123 | 13.0% |
| Interprogck8 | 21.1% | BF-PDA | 12.6% |
| Dig | 19.8% | ArrowQueue | 12.4% |
| Flowchart | 17.1% | Sophie | 8.1% |
| Minifuck | 13.1% | WII2D | 5.1% |
| BrainIf | 4.9% | COD | 3.2% |
| SLOW ACV MAMMALIAN | 3.2% | | |

Everything else screens under 3%; every wired generator screens at 3.1%
residual (Back) or less.  COD's is concentrated in 12 of 256 tables.
ArrowQueue has its own entry below.

Three figures moved with their generators, and one verdict was lost:

| Generator | Was | Now | Cause |
| --- | --- | --- | --- |
| Polynomial | 25.1% | 15.9% | the dense rework, `22f0dce9`..`57caea1d` |
| Sophie | 16.4% | 8.1% | the subfunction merge, `cbca1f46` |
| COD | 0% | 3.2% | the dependency reduction, `a25f266f` |

Polynomial's and Modulous's language walls stand ([walls](walls.md)); Dig
and Flowchart are grid placements, so 2D layout surgery rather than renaming
a branch operand.

**For the no-input languages the wire may be renaming.**  Their inputs are
substituted rather than read from a stream, so building the permuted table
and renaming `{Xi}` slots would reach the screened figure without any build
entering a permuted frame -- untested.

Where a build *must* enter one, the trap stands: a generator that validates
its own output during construction needs that check frame-mapped, or it
rejects every correct placement and reports a clean 0.00%.  ZTOALC L did
exactly that, and wii2d's budget machinery is the next likely instance.  **A
0% where the screen shows upside is a diagnosis, not a verdict.**

## Conditional follow-up

- **WII2D's exactly-once embed convention.**  Dense n=10 is a wall of the
  convention, not the machine: a per-node re-embed does dense n=10 in 14432
  characters and dense n=13 in 146540, every row executed.  Re-examine the
  convention only if the arity ever matters -- it is fenced by the invariant
  in `tests/tools/test_boolean_parameterized.py`, and Dotlang and 2dFish
  were removed rather than exempted from it.  The audit is in
  [walls](walls.md#wii2d-a-wall-of-the-embed-convention).

- **Minifuck's mux round loop.**  The rest of the sculpt closed (pool code
  in `5b35c66b`, the named accumulator from nine); the round loop did not,
  and is *measured* not to.  Over 36864 round transitions at exhaustive n=3
  no round moved a row above the frontier, but 27656 moved one below it, so
  the post-fix column is not predictable without walking.  Reopen only with
  a rule for the `_mux_probe` cascade -- now 69% of the build -- not a wider
  search.

- **ArrowQueue reusable drain.**  Ship the verified deep-fold drain only if
  a proof makes folding meaningfully testable at `n >= 5`; current coverage
  does not reach its crossover.

- **Reorder ArrowQueue inputs.**  The three-input screen leaves 12.4%
  headroom, but its queued inputs cannot be renamed in place.  Find a
  re-enqueue and grid-routing construction, then compare emitted, executed
  programs against the current template; abandon it if the routing spends
  the apparent gain.

- **`%^2^-1` fourteen inputs.**  The staged fold's endgame strands its last
  duplicated cofactor pairs.  Rank order is steerable (pulsed doubling), but
  a merge needs the pair's value gap `d` inside a wipe window, and diving
  the partner maps `d -> amount - d` with the amount free in the window --
  a derived, unbuilt alignment controller.  Build it only if a ~20x
  thirteen-input build cost (~430k plan ops, ~8MB templates, ~226 ops per
  merge) is acceptable; the walls around it are in [walls](walls.md).
