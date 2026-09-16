# Boolean generator output compressibility

Measured 2026-09-11 on `main` (92e42799).  Every boolean generator's output
recorded and measured; this is about **program size**, not generator runtime
(that is `notes/boolean-generator-optimization-audit.md`, a different axis).

**Nothing here is a verified win.**  A size win needs the shortened program
executed and the change priced against the standing compute budget.  These are
ranked candidates and a classification of why each program is big.

## Method

All 73 generators, both suite shapes (`_dense`, `_parity` lifted verbatim from
`tests/tools/test_boolean_contract.py`), n=3 and n=8.  287 outputs, 21MB, no
timeouts and no refusals -- every generator builds n=8 on both shapes.

Two are not truth-table generators and were recorded in their own form:
`jaune_multiply()` takes no table, `circlefuck_byte` takes a byte-valued one.

Artifacts:

- `notes/boolean_compressibility.csv` -- one row per (generator, n, shape):
  raw bytes, zlib-9 bytes, ratio, growth, alphabet, run share, top repeat.
- `notes/boolean_outputs.tar.gz` -- the 287 programs themselves (2MB packed).

**Reading the growth column.**  Normalized against 32x, the table's own growth
from n=3 to n=8.  A generator linear in `table x n` lands near 2.7, so 1-3 is
baseline.  Flag line is ~7.

## Ranked by compression slack, n=8 dense

| generator | raw | zlib-9 | ratio | growth/32x | top repeat |
|---|---|---|---|---|---|
| cod | 3,458,156 | 7,696 | 449x | 71.9 | 128 spaces x879,127 |
| polynomial | 3,383,048 | 1,587,678 | **2x** | 15.6 | `7741` x141 |
| slow_acv_mammalian | 1,672,368 | 6,631 | 252x | 1.1 | `SEED ` x165,662 |
| rotfuck | 1,158,946 | 16,892 | 69x | 21.2 | `,<>]]][.` x4,972 [1] |
| circuit_diagram | 609,526 | 15,535 | 39x | 45.6 | 16 spaces x118,113 |
| bit_tilde | 507,740 | 2,851 | 178x | 51.5 | `<` run x124,027 |
| one_two_three | 219,937 | 1,019 | 216x | 48.4 | `1` run x80,129 |
| collatz_multiverse | 140,909 | 15,507 | 9x | 4.3 | ` = negativeOne x` x2,722 |
| a_painter_ant | 140,276 | 1,695 | 83x | 11.0 | `s` run x17,157 |
| interprogck8 | 88,306 | 2,798 | 32x | 2.8 | `\n@id` x1,672 |
| streetcode | 60,383 | 2,667 | 23x | 2.8 | 32 spaces x14,796 |
| minifuck | 50,653 | 474 | 107x | 7.3 | `[x` x9,583 |
| suptiftam | 40,885 | 645 | 63x | 4.2 | `mulStep(:p:)if(p)` x861 |
| pct_squared_minus_one | 40,121 | 642 | 62x | 29.9 | `s` run x25,064 |
| flowchart | 39,873 | 1,120 | 36x | 2.9 | 128 spaces x3,736 |

The other 58 sit under 35KB; the floor is `alight` at 474 bytes.  Full table in
the CSV.

[1] the measured block, as the CSV records it.  It is a rotation of the cycle
`][.,<>-+` -- see below.

Trailing whitespace is **zero** in all 287 outputs, so the whitespace in the
grid languages is interior -- positional, not trimmable.

## The finding: the compressible part is unary tape travel

Pointer walks emitted one character at a time dominate every oversized
brainfuck-family program, and what separates the compact generators from the
bloated ones is **how wide an address space the construction allocates**:

| generator | len n=8 | travel% | highest cell | moves | mean move | longest |
|---|---|---|---|---|---|---|
| brainfuck / bf_tree | 3,759 | 47% | 16 | 1,133 | 1 | 15 |
| basicfuck | 22,550 | 0% | 8 | 183 | 1 | 1 |
| circlefuck | 10,964 | 1% | 7 | 189 | 1 | 1 |
| unsquare | 8,496 | 13% | 8 | 1,114 | 1 | 1 |
| laserfuck | 22,993 | 7% | 8 | 1,701 | 1 | 8 |
| super_snusp | 7,373 | 80% | 9 | 1,299 | 4 | 9 |
| minifuck | 50,653 | 33% | 0 | 627 | 27 | 854 |
| rotfuck (un-rotated) | 1,158,946 | 75% | 528 | 142,218 | 6 | 528 |
| suffolk | 32,831 | 98% | 30,018 | 2,805 | 11 | 140 |
| **bit_tilde** | 507,740 | **98%** | **2,032** | 6,530 | **76** | **2,025** |

The tree constructions keep the working set in a fixed window (<=16 cells,
mean move 1).  The ones that allocate a fresh cell per unit of work pay for
every access in unary, and the walk length grows with the allocation.

`rotfuck`'s bulk is the same thing in disguise.  Its top repeat is a rotation
of the cycle `][.,<>-+`, which is the rotation chain `+-><,.[]` reversed --
i.e. the *same logical command* written out k times.  The sign is pinned from
source, not guessed from the histogram: `rotfuck.py:156` builds the translation
tables as `rot(c, -res)` for position residue `res`, so `plain[i] =
rot(source[i], +i)`.  Un-rotated that way the program is **76% `<`/`>`** with
74% of bytes inside runs >=4.

The remaining 24% is alignment padding, and essentially all of it: `+`/`-` are
23.8% of the un-rotated program, and removing adjacent net-neutral `+-`/`-+`/
`><`/`<>` pairs removes 23.8% of it.  So rotfuck's arithmetic is *entirely*
padding -- inserted to shift the rotation offset so the next real command lands
where it is writable.  (An earlier 5.8% figure for this was computed under the
wrong un-rotation sign and is noise; ignore it.)

## Candidates (construction-chosen)

1. **bit~ -- narrow the address space.**  Strongest candidate on the board.
   `bit_tilde` pre-copies every (input, one-row) pair into a *fresh* cell
   (`other.py:1147`), so addresses climb with the minterm count: highest cell
   32 at n=3, 2,032 at n=8, mean move 7 -> 76, longest single walk 2,025.  98%
   of the 508KB program is `move()` output from `other.py:1176`.  Reusing a
   bounded scratch window per minterm -- freed after the row's test -- would cap
   addresses at O(n) and take travel from quadratic toward linear.  This is
   orthogonal to the decision-tree question: bit~ is a minterm sum that was
   never a tree, so the closed tree-migration triage does not cover it.

   *Kill condition, checked:* this is only construction-chosen if a scratch
   cell can be cleared and reused.  It can -- `copy2` zeroes its source, and
   `{ ~ }` is already the shipped clear idiom (`other.py:1213`).  The nuance
   is that the `keep` chain must persist across a slot's rows, while the
   per-`(row, slot)` indicator cells are read only by that row's nested test;
   those are what reuse should target.
2. **rotfuck -- fewer moves, not better-ordered ones.**  142,218 moves for a
   256-row table (~555 per row), 878,610 travel characters.

   *Minterm reordering is refuted -- recorded so it is not re-proposed.*  The
   obvious idea (Gray-code the minterm sum so adjacent minterms differ in one
   literal) only shortens transits *between* minterms.  The move-length
   distribution says those barely exist: **92% of travel sits in 131,211 hops
   of length 4-7**, and only 7% (68,876 chars, 437 moves) is in moves >=50.
   Reordering therefore addresses at most ~5% of the program.

   The cost is per-literal local work -- ~512 short hops per row -- so the
   lever is emitting fewer, longer moves, which is a construction change.  It
   would cut the alignment padding too, since each move-run is tiled against
   the 8-step rotation (`_rotfuck_move_cycle`).  `docs/walls.md` closes the
   *decision-tree* route for ROTfuck, so this must stay inside the minterm sum.
3. **COD -- grid density.**  513 rows x 6,740 columns at n=8, 10.4% filled,
   89% spaces, and the worst growth on the board (72x baseline).  The spaces
   are interior so there is nothing to trim; the cost is the layout spreading
   routes across a mostly-empty plane.  Priced as real work -- it needs the
   interpreter's routing semantics, not a text transform.
4. **Eval -- unary heap index.**  88% of the program is `;`, and the shape is
   `~=~?;;;;!` with the run length encoding a leaf index.  Caveat that makes
   this weaker than it looks: Eval is a *positional* heap layout where a fold
   is blanked in place, so variable-length indices break the layout.  Any
   shorter encoding has to preserve position.
5. **Suffolk -- address reach.**  Highest cell of any generator at 30,018, 98%
   travel, yet only 33KB total, so the construction is already efficient per
   move.  Lowest-value of the five; listed because the reach is an outlier
   worth a reason.

## Not opportunities

**Forced by language semantics** -- high ratio, no construction to change:

- `one_two_three` (98% `1`/`2`): runs *are* the numeric encoding -- a width-`w`
  run is `pos += w` or a `w`-bit XOR mask.  Worked out already; see the 123
  findings.
- `slow_acv_mammalian` (1.67MB, 252x): `SEED ` repeated is the language's only
  primitive.  Growth is 1.1x baseline -- a pure constant factor, not a scaling
  problem.
- `circlefuck_byte` (growth 1.1x): unary byte literals.
- `collatz_multiverse` (ratio 9x, the lowest of the big ones): `negativeOne`,
  `zero`, `, NOT PRINT.` are spelled language constants, not generator-chosen
  names.  Verbose but fixed.
- `a_painter_ant`, `dig` (81% spaces): `dig`'s spacing is a floor with a proof
  (4 mod 6, exactly one turn); APA's runs are movement commands.

**Priced in by a recorded wall or a shipped optimization:**

- `polynomial` -- 3.4MB but **ratio 2.1x**, digits uniform across 0-9.  There is
  no LZ redundancy to remove; the size is information.  The opposite of an
  opportunity, and the reason ratio must be read alongside raw size.  (Note
  the shape sensitivity: dense 3.4MB vs parity 93KB.)
- `rotfuck`, `three_x` -- decision-tree construction is a standing wall
  (`docs/walls.md`).  Candidate 2 above sidesteps it rather than attacking it.
- `pct_squared_minus_one` -- CLOSED topic.
- `minifuck` -- the `[x` walk is the shipped construction (n=10 shipped, the
  frontier-recurrence negative stands).  Its 27-char mean move is by design.
- `interprogck8` -- the `@id` rungs are the residue *after* the shipped express;
  ceiling held at 10 on cost.
- `wii2d`, `circuit_diagram` -- both known large; WII2D's dense n=10 is a
  documented wall of the exactly-once embed convention.
- Tree-shape migration generally -- `decision_tree_tokens` triage is COMPLETE
  with an authoritative exclusion list.  Nothing above proposes re-opening it.
