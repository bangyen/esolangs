# Proofs

Two results were machine-checked in Lean 4 + mathlib. The sources were
deleted in `4317b0bb` and stay recoverable at `528fe2c2`; what is kept here
is prose transcribed from each proof file's docstring, so the statements say
what the theorems said. Source and tests are the primary evidence.

A third, MAMMALIAN generator totality, is not kept: it stated that the text
generator's per-character search never reaches its `ValueError`, and the
text generators were removed. It was the only one carrying `native_decide`;
the two below are kernel-only, and `sorryAx` would mark a gap and never
appeared in any of them.

- **Factor round-trip.** The renderer round-trips its encoded program.
  Kernel-only: `propext`, `Classical.choice`, `Quot.sound`. The prime search
  rests on Dirichlet, not on computation.
- **The `%^2^-1` wall.** A program reading its own inputs cannot compute a
  two-input Boolean function. Kernel-only across the whole chain. It bounds
  the *reading* model, and the shipped generator is parameterized, so it does
  not bound that.
- **The 123 geometry reduction.** A per-arity certificate, and of different
  provenance: a prose argument over a finite certificate the code recomputes
  from scratch every process, never a Lean theorem. Kept here because it
  plays the same role — it is what a size optimization's correctness rests on.

These results do not extend to parameterized programs beyond the construction
models they state. A new claim needs an executable witness or a checked proof.

The totality section below is of the 123 entry's provenance, not the other
two: prose arguments over machinery the code recomputes, each with a named
executable witness. Nothing there is kernel-checked, and it should not be
read as though it were.

## Totality of the boolean generators

**The claim.** For each of the 69 boolean generators `g` and each truth
table `t` of length `2**n` with `1 <= n <= 10`, the call `g(t)` terminates
and returns a non-empty program — with one pinned exception, WII2D on a
dense-shaped table at `n == 10`, whose cap `_ARITY_CAPPED` records and
`test_arity_caps_are_still_caps` asserts is still binding.

The exception is in the claim rather than in a footnote on purpose: this
file's top line has to be the refutable one, and a version without the
carve-out is refuted by the repo's own suite.

**What it is not.** Not that the program is *correct* — Grapheme returned a
healthy string for four years while emitting something its own interpreter
could not run, and only executing it caught that. Not that it holds past ten
inputs — ten is where the contract sweep stops and where several of the caps
below bind, and what any one generator does at eleven is its own
measurement, never a shared ceiling. Not that it holds for a `width`
argument, which is a separate audit — four generators cannot take one at all.

**Two obligations,** and the table below settles each per generator: the work
terminates, and no raise fires inside the domain.

### Termination

Sixty-one of the 69 reach no unbounded loop at all. Their work is bounded
recursion on the decision tree — `decision_tree_tokens`, `decision_tree_program`,
or a hand-written post-order walk — whose measure is `n - level`, strictly
decreasing at every recursive call, so a walk makes at most `2**(n+1) - 1`
of them; everything around it iterates a finite range: the `2**n` rows, the
`n` inputs, the minterms of a table, the characters of a finished string.
`best_input_order` is the one search among them, and it is greedy: `remaining`
loses exactly one input per pass.

Eight reach a `while True`, and each carries its own measure.

- **Algebraic Programming Language** — `_apl_name` counts a name in base 26;
  `index // 26 - 1` strictly decreases and the walk returns below zero.
- **Alight** and **Super SNUSP** — a folding pass over `pending`. The first
  unit of a pass is taken unconditionally, so every pass removes at least
  one, and the pass that empties the list leaves through the break.
- **ROTfuck** — `_rotfuck_move_cycle` walks an offset mod 8 and stops at the
  first repeat against `seen`, so at most eight passes.
- **WII2D** — `_wii2d_compress` applies runs that each strictly shrink the
  span, and stops once the extreme magnitude is at most one.
- **SLOW ACV MAMMALIAN** — `_subtree` stashes 255-chunks; a chunk moves the
  landing by 256 while the threshold it has to clear moves by 3 plus a
  bounded sawtooth.
- **123** — `_normalize` steps deterministically over position vectors and
  only the four ring cells can hold a negative row, so a cycle repeats within
  a handful of steps; the repeat is detected against `seen` and refuses
  rather than spinning to a cap. Measured worst case: nine steps.
- **Interprogck8** — three loops. `_settle` only ever promotes a jump to an
  express and never demotes, so the jump count bounds it; `_route`'s rung
  walk moves `landing` strictly toward a fixed `stop`; the repair round is
  bounded by `_REPAIRS` and refuses past it.

### No raise inside the domain

Forty-nine generators reach only a shape guard: forty-eight the shared one
in `_validate_truth_table`, and Circlefuck its own equivalent. It fires on a
table whose length is not a power of two — that is the domain's
*definition*, not a hole in it. The remaining twenty carry something more,
and it is one of three things:

- a **declared cap**, `GeneratorCapError`, at a size or cost policy;
- an **internal invariant**, `AssertionError`, that the construction claims
  cannot fail;
- a **construction refusal** — the route ran out of candidates.

One of them is *known* to fire inside `1 <= n <= 10`: WII2D's cost guard on
a dense table at `n == 10`, which `_ARITY_CAPPED` pins with the measurement
that put it there. No other guard fires on anything the witnesses below
reach — which is a weaker statement than "no other guard can fire", and the
gap is real above `n == 3`. `%^2^-1` is where it shows: its refusal is not
condition-bounded to an arity, and its own message says "every table *tried*
from five through thirteen". Above the exhaustive band the claim rests on
two shapes and a one-minterm table per arity, not on the whole domain.

Several guards say in the source that they are unreachable: 123's
construction refusal, Eval's and Unsquare's missing-arrangement guards, and
6-5's `n > 35` label cap all carry `# pragma: no cover`. 6-5's *operand*
guard does not — it is argued unreachable, not marked so. Neither is
Minifuck's final `ValueError`, and that one is deliberate: it is a tripwire
whose message names the table that broke the argument.

### Witnesses

Three sweeps in `tests/tools/test_boolean_contract.py`, and they cover
different halves of the claim:

- `test_every_generator_is_total_on_every_small_table` — *every* table at
  `n <= 3`, all 276, through all 69. The exhaustive-domain half, and `n == 3`
  is the last arity where exhaustive is affordable: `n == 4` is 65536 tables
  per generator. 4.7s serial, no generator over 1.8s.
- `test_every_generator_builds_up_to_ten_inputs` — two shapes, dense and
  parity, at every arity to ten. The reach half. Two shapes rather than one
  because a generator can cover one and refuse the other at the same `n`.
- `test_arity_caps_are_still_caps` — that WII2D's entry is still a cap and
  not a pinned-in limitation that has since been lifted.

A fourth, `test_every_generator_runs_what_it_builds`, is what separates this
claim from correctness: it executes a one-minterm program at `n == 6`, the
arity that would have caught Grapheme.

### Per generator

`bounded` is the tree-recursion-and-finite-iteration argument above; a named
loop is one of the eight, with its measure in that list. The last column is
what has to be shown not to fire, beyond the shape guard every row carries.

| Generator | Termination | Guards beyond the shape guard |
| --- | --- | --- |
| A Painter Ant | bounded | — |
| AddSubJump | bounded | — |
| Algebraic Programming Language | `_apl_name` | — |
| Alight | `_alight_folded` | a run walked off the left edge |
| ArrowQueue | bounded | — |
| Back | bounded | — |
| Basicfuck | bounded | — |
| Between | bounded | — |
| BF-PDA | bounded | — |
| BFStack | bounded | — |
| BIO | bounded | — |
| bit~ | bounded | — |
| Bitdeque | bounded | — |
| brainfuck | bounded | — |
| BrainIf | bounded | — |
| Circlefuck | bounded | — (its own shape guard, not the shared one) |
| Circuit Diagram | bounded | wire, glyph and complement placement invariants |
| Clockwise | bounded | a placement invariant |
| COD | bounded | — |
| Collatz Multiverse | bounded | a placement invariant |
| Container | bounded | — |
| CV(N)(C) | bounded | cap: the halting goto's reach |
| Decleq | bounded | — |
| Dig | bounded | a placement invariant |
| Dimensional | bounded | — |
| DINAC | bounded | — |
| Eval | bounded | the free stack arrangement is missing (pragma'd) |
| Factor | bounded | cap: the encoded integer's digit budget |
| Fargo | bounded | — |
| Flowchart | bounded | — |
| Forbin | bounded | — |
| Forþ | bounded | — |
| function x(y) | bounded | — |
| Grapheme | bounded | cap: a slot past the variable keys |
| Home Row | bounded | — |
| Inject | bounded | — |
| Interprogck8 | `_settle`, `_route`, repair | cap: `_REPAIRS` rounds; jump reach; express-window asserts |
| Jaune | bounded | — |
| Lamfunc | bounded | — |
| LaserFuck | bounded | — |
| Minifuck | bounded | the totality tripwire, and the pool/frame invariants |
| Minsky Swap | bounded | — |
| Modulous | bounded | — |
| MyScript | bounded | — |
| Nevermind | bounded | — |
| NoComment | bounded | cap: a cell past the interpreter's tape |
| 123 | `_normalize` | construction refusal (pragma'd); slots in name order |
| Packlang | bounded | — |
| Painfuck | bounded | — |
| %^2^-1 | bounded | refusal: no ladder served — not arity-bounded |
| Point Break | bounded | — |
| Polynomial | bounded | cap: `_POLYNOMIAL_MAX_INSTRS` |
| Qoibl | bounded | — |
| RAM0 | bounded | — |
| ROTfuck | `_rotfuck_move_cycle` | — |
| S*bleq | bounded | — |
| 6-5 | bounded | cap: 35 branch labels; operand range (live, argued) |
| SLOW ACV MAMMALIAN | `_subtree` | a trampoline overflowed its slot |
| Sophie | bounded | — |
| Streetcode | bounded | — |
| Suffolk | bounded | — |
| Super SNUSP | `_super_snusp_folded` | — |
| Suptiftam | bounded | — |
| Taglate | bounded | — |
| 3D Brainfuck | bounded | — |
| 3x | bounded | — |
| Unsquare | bounded | the identity stack arrangement is missing (pragma'd) |
| WII2D | `_wii2d_compress` | **cap: fires at dense `n == 10`** — the one pinned refusal |
| ZTOALC L | bounded | cap: `_MAX_LINES` command lines |

The rows are not hand-collected. `scripts/boolean_totality_report.py` walks
each generator's import-aware call graph and reports the unbounded loops and
live raise sites in its reachable set; re-run it when this table is in
question. A name-only graph gets it wrong — the private helpers here collide
across modules, and one put Minifuck inside 123's constructor, which
Minifuck does not import.
