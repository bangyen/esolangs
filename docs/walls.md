# Generator boundaries

A search result is not a wall unless its structural reason is recorded here.
Generated programs must be run before a size, equivalence or impossibility
claim is accepted.

Reopen a result only with a new semantic mechanism, not a wider blind
search.  Historical attacks, measurements and removed generators remain in
git.

## Standing results

- **6-5.** Only 35 branch labels are addressable; labels are global ordinals
  and cannot be reused.  Do not use operands past `Z`.

- **3x, Dotlang, ROTfuck, 2dFish.** Their documented input and control-flow
  mechanics do not support the proposed universal decision-tree
  construction.

- **`%^2^-1`.** A program reading its own inputs cannot compute a two-input
  function.  The staged cofactor fold reaches generic thirteen-input tables,
  and its walls are measured rather than open:

  - no ladder lays `2**12` distinct positions inside the 3003 footprint, so
    there is no fourteen-input prefix;
  - the 256-class compaction a fourteen needs converges at ~226 ops per
    merge but strands its last duplicated pairs in a rules cycle.  Pulsed
    doubling breaks the rank rigidity, yet a merge still needs the pair's
    *value* gap steered into a wipe window -- an unbuilt controller;
  - fifteen-plus generic tables are closed by counting: 16-bit cofactors
    over 2048 prefix points are nearly all distinct, so compaction stops
    biting.

- **Polynomial, Modulous.** Neither can test inputs out of stream order, so
  the measured reorder upside (15.9% and 16.4% respectively at n=3,
  `scripts/screen_input_reorder.py`) is unreachable.  Polynomial has one
  register and nothing else addressable, so a bit must be branched on before
  the next read overwrites it.  Modulous's variables store and print but
  never load back, and every conditional inspects the stack top alone.  Both
  verified against the interpreter and the wiki; the derivation lives in
  `best_input_order`'s docstring.

- **Termination convention.** Use only where a specification supplies a
  reliable halt/loop verdict and the runtime can decide it soundly.

- **Empty input line.** `io.input_char` returns `0`, matching every
  interpreter that guards `io.input_str` at its own call site; the package
  used to answer `10` through one path and `0` through the other, which no
  cross-camp translation could reconcile.  Exhausted input is still
  `EOFError`.  Pinned by `tests/interpreters/test_input_convention.py`,
  which enumerates the registry rather than a list.  Whether any language's
  `0` came from its own specification is settled and no longer live work:
  none did -- see [limitations](limitations.md#interpreter-conventions).

## WII2D: a wall of the embed convention

Routing plus accumulator decoding is the shipped construction, and its
guards are source-cost policies.  The dense ten-input table is a wall of the
**exactly-once embed convention**, not of the machine.

Under that convention the construction is closed.  `^v<>` fills set the
heading *absolutely*, so every prefix leaves a junction at an identical
position and heading with only the accumulator differing -- which makes any
single-embed construction ops interleaved with the n branch pairs, with
exactly the fold algebra's merging power.  Within that family:

- a 512-point decode ratchets.  Raising the guard to 512 refuses the
  sweep's dense n=10 witness anyway (0.22s per branch), and with the
  magnitude abort lifted its live count crawls 512 -> 475 over 19 steps
  while the bit length doubles every step, 9 -> 1089888 bits.  Full
  enumeration ratchets too (512 -> 373, past 670000 bits);
- no op removes high accumulator bits, closing every shifted-table readout
  -- verified exhaustively over op strings to length 5, against controls
  that fire;
- a mid-chain collapse under 4-class labels ratchets as well.

**Drop the convention and the wall goes.**  A per-node re-embed -- a plain
grid decision tree, one row per level -- computes dense n=10 in 14432
characters and dense n=13 in 146540, every row executed.  It embeds input
`i` `2**i` times (512 copies of `{X9}` at n=10), which is what the invariant
in `tests/tools/test_boolean_parameterized.py` forbids and why Dotlang and
2dFish were removed rather than exempted.

So this is a *deliberate* wall, and the thing to re-examine if it ever
matters is the convention, not the fold algebra.
`docs/generators/wii2d_generator.md` has the audit.

## Verification boundaries

Exact-state cycle detection decides only complete, deterministic state
repeats.  Tape-growth and recursive-frame helpers cover their specific
semantic shapes; other nontermination still needs a wall-clock backstop.  A
negative corpus search needs a positive control that exercises the proposed
mechanism.

**Picking the wrong prover is silent, and costs the whole run.**  Suptiftam's
boolean programs handed *no* input recurse without bound: `mulStep` counts
down toward a value the missing read never supplies, so a `_CallFrame` is
pushed and never popped.  Measured on the XOR program at 3000 steps: 908
live frames, and a snapshot growing about 32 bytes per step, so no state
ever repeats.

| Prover | Verdict on that program |
| --- | --- |
| `run_until_halt_or_cycle` | cannot conclude -- holding the states OOM-killed the probe |
| `run_until_halt_or_ancestor` | undecided after 64 pushed frames, in under a second |

Suptiftam supports the second: it defines `frame_entry_key`.

Both facts are in `run_until_halt_or_cycle`'s own docstring -- an
unbounded-growth loop never revisits a state, and the frame helper covers
the recursive shape -- so this is the documented boundary being met, not a
defect.  What it costs is a caller who reaches for the exact-state prover by
default on one of the nine languages that define `frame_entry_key`.
Under-fed programs are the way to reach it: with its inputs supplied, the
same XOR program is correct on all four rows.
