# Proofs

Two results were machine-checked in Lean 4 + mathlib.

A third, MAMMALIAN generator totality, is not kept: it stated that the text generator's per-character search never reaches its `ValueError`, and the text generators were removed.

- **Factor round-trip.** The renderer round-trips its encoded program.
- **The `%^2^-1` wall.** A program reading its own inputs cannot compute a two-input Boolean function.
- **The 123 geometry reduction.** A per-arity certificate, and of different provenance: a prose argument over a finite certificate the code recomputes from scratch every process, never a Lean theorem.

These results do not extend to parameterized programs beyond the construction models they state.

The totality section below is of the 123 entry's provenance, not the other two: prose arguments over machinery the code recomputes, each with a named executable witness.

## Totality of the boolean generators

**The claim.** For each of the 69 boolean generators `g` and each truth table `t` of length `2**n` with `1 <= n <= 10`, the call `g(t)` terminates and returns a non-empty program — with one pinned exception, WII2D on a dense-shaped table at `n == 10`, whose cap `_ARITY_CAPPED` records and `test_arity_caps_are_still_caps` asserts is still binding.

The exception is in the claim rather than in a footnote on purpose: this file's top line has to be the refutable one, and a version without the carve-out is refuted by the repo's own suite.

**What it is not.** Not that the program is *correct* — Grapheme returned a healthy string for four years while emitting something its own interpreter could not run, and only executing it caught that.

**Two obligations,** and the table below settles each per generator: the work terminates, and no raise fires inside the domain.

### Termination

Sixty-one of the 69 reach no unbounded loop at all.

Eight reach a `while True`, and each carries its own measure.

- **Algebraic Programming Language** — `_apl_name` counts a name in base 26; `index // 26 - 1` strictly decreases and the walk returns below zero.
- **Alight** and **Super SNUSP** — a folding pass over `pending`.
- **ROTfuck** — `_rotfuck_move_cycle` walks an offset mod 8 and stops at the first repeat against `seen`, so at most eight passes.
- **WII2D** — `_wii2d_compress` applies runs that each strictly shrink the span, and stops once the extreme magnitude is at most one.
- **SLOW ACV MAMMALIAN** — `_subtree` stashes 255-chunks; a chunk moves the landing by 256 while the threshold it has to clear moves by 3 plus a bounded sawtooth.
- **123** — `_normalize` steps deterministically over position vectors and only the four ring cells can hold a negative row, so a cycle repeats within a handful of steps; the repeat is detected against `seen` and refuses rather than spinning to a cap.
- **Interprogck8** — three loops.

### No raise inside the domain

Forty-nine generators reach only a shape guard: forty-eight the shared one in `_validate_truth_table`, and Circlefuck its own equivalent.

- a **declared cap**, `GeneratorCapError`, at a size or cost policy;
- an **internal invariant**, `AssertionError`, that the construction claims cannot fail;
- a **construction refusal** — the route ran out of candidates.

One of them is *known* to fire inside `1 <= n <= 10`: WII2D's cost guard on a dense table at `n == 10`, which `_ARITY_CAPPED` pins with the measurement that put it there.

Several guards say in the source that they are unreachable: 123's construction refusal, Eval's and Unsquare's missing-arrangement guards, and 6-5's `n > 35` label cap all carry `# pragma: no cover`.

### Witnesses

Three sweeps in `tests/tools/test_boolean_contract.py`, and they cover different halves of the claim:

- `test_every_generator_is_total_on_every_small_table` — *every* table at `n <= 3`, all 276, through all 69.
- `test_every_generator_builds_up_to_ten_inputs` — two shapes, dense and parity, at every arity to ten.
- `test_arity_caps_are_still_caps` — that WII2D's entry is still a cap and not a pinned-in limitation that has since been lifted.

A fourth, `test_every_generator_runs_what_it_builds`, is what separates this claim from correctness: it executes a one-minterm program at `n == 6`, the arity that would have caught Grapheme.

### Per generator

`bounded` is the tree-recursion-and-finite-iteration argument above; a named loop is one of the eight, with its measure in that list.

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

The rows are not hand-collected.
