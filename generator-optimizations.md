# What each text / boolean generator optimizes

Catalog of the size-and-shape optimizations each of the 45 text and 61 boolean
generators applies to the *emitted program*. Read from source and docstrings on
2026-08-27; the constant-folding column for the boolean side reuses the verified
results in `boolean-constant-folding.md` rather than re-deriving them.

"Optimization" here means what the generator does to make its output smaller
or better-shaped — not the runtime of the generator itself.

---

## The recurring techniques

Nine patterns account for nearly everything. Most generators combine two or
three.

| # | Technique | What it buys | Lives in |
|---|---|---|---|
| 1 | **Delta encoding** | each character costs its distance from the previous one, not its full code point | `text/helpers.py:28` `delta_program` |
| 2 | **Multiply/factor loops** | a byte costs `O(sqrt(v))` instead of `O(v)` via `a*b + r` | `text/helpers.py:71` `_factor_triple` |
| 3 | **Binary doubling** | a byte costs `O(log v)` by walking its bit expansion | addsubjump, unsquare |
| 4 | **Shortest-of-N dispatch** | build two constructions, measure, return the smaller | laserfuck, streetcode, %^2^-1, brainfuck |
| 5 | **Constant-subtree folding** | a subtree whose rows agree emits a leaf, not a branch | `boolean/helpers.py` (both walkers) |
| 6 | **Complement / polarity** | a dense table is evaluated from its zero rows and inverted | `boolean/helpers.py:44` `_maybe_complement` |
| 7 | **Shape-aware width** | honour a width by building a *different* shape, not by reflowing | `laserfuck_layout.py`, `wrap.py` |
| 8 | **Literal batching** | print a whole string in one statement rather than per character | `text/helpers.py` `_literal_chunks` |
| 9 | **Equal-width embedding** | *anti*-optimization: pad both bits to equal width so length can't leak inputs | `boolean/helpers.py:97` `instantiate` |

Technique 9 is the one deliberate refusal to shorten. A zero embedded as
nothing makes `len(program)` a function of the inputs, leaking the very bits
the program is supposed to compute — an earlier Bio embedding ran to 236/240/
244/248 characters for its four instantiations.

---

## Text generators

### Delta-encoded (the dominant family)

Each character costs only its distance from the previous one.

| Generator | Detail |
|---|---|
| `nocomment` | `i`/`d` runs via shared `delta_program` |
| `circlefuck` | tape *is* the program; a no-op char near the first target seeds the cell |
| `basicfuck` | one variable `a`, `+=`/`-=` |
| `six_five` | `_six_five_path` arithmetic tokens |
| `rotfuck` | delta the **shorter way around** the 8-bit wrap |
| `bio` | delta folded mod 256, *plus* `a*b+r` search on the delta itself |
| `polynomial` | `+=`/`-=` deltas, then encoded as polynomial roots |
| `container` | signed delta split across two `A>=i` rules |
| `painfuck` | signed delta in bases 7 and 3 |
| `one_two_three` | running **XOR** in `edi`; emits only the differing bits |
| `bit_tilde` | tracks the tape, toggles only bits that must change |
| `brainfuck` | **hybrid**: delta when close, else `[-]` + multiply-loop rebuild |
| `bfstack` | same hybrid, with a measured threshold |
| `unsquare` | delta chain off the retained accumulator (~21% on "Hello, World!"), **bounded by parity** — `x` can't restore oddness, so odd targets off an even accumulator reseed |

### Arithmetic-construction

| Generator | Optimization |
|---|---|
| `home_row` | `a*b+r` counter loop, `a` searched near `sqrt` → `O(sqrt)` |
| `suffolk` | factors minimizing `a + 2b + 2r` — *not* `sqrt`, because `>!` and `><` cost two characters each |
| `addsubjump` | binary doubling → `O(log byte)` |
| `collatz_multiverse` | two-line multiply-add per constant; **only the bytes actually referenced** are built (`_PLAN` / `_extend_plans`), reaching large values in `O(log)` constants |
| `wii2d` | per character picks cheapest of literal digit / square / double / combination |
| `slow_acv_mammalian` | SEED runs split around the SPRINT walk, solving `(q+1)*K == target (mod 256)` |
| `minifuck` | tracks the bit pool; prints only when nonzero |

### Shortest-of-N

| Generator | Competing forms |
|---|---|
| `laserfuck` | `_laserfuck_multiply` (spread values) vs `_laserfuck_base_ring` (clustered) — compared by **bounding-box area**, not `len` |
| `pct_squared_minus_one` | `_pct_path` (high-delta) vs `magnitude` (low-delta, repetitive) |
| `streetcode` | ring vs plain, and both again folded; shorter wins |
| `clockwise` | weave vs bare ring — ring only ever won on 1-char text by ≤1.26x, so it was **removed**; the loss is recorded |

### Literal batching

`between`, `taglate`, `myscript`, `three_x`, `eval`, `modulous`, `nevermind`,
`sbleq`, `forbin`, `suptiftam`, `dimensional`, `qoibl`, `sophie`, `forth`,
`decleq` — print via string literal or embedded data rather than per-character
arithmetic. `forth` still builds each char as `m * 15**n + p`.

### Special cases

- **`streetcode`** — the *first* character (whole code point: 72 for `H`, 937
  for omega) uses a counting ring, making it a product; later characters keep
  the unary walk, since adjacent gaps are almost always cheaper than a ring's
  fixed row block.
- **`brainif`** — starts a falling character from the **largest parked value
  not above it** rather than from zero. The `l` of "Hello, World!" costs 66
  lines from the comma's parked 44 vs 110 from zero.
- **`ztoalc_l`** — precomputed anchor table (`ztoalc_starts.py`) of Collatz
  starts with the smallest trajectory peak per length interval.
- **`factor`** / **`three_d_brainfuck`** — reuse `brainfuck`'s output unchanged.

### Width handling (9 of them lay out their own shape)

`clockwise`, `dig`, `eval`, `laserfuck`, `modulous`, `myscript`, `streetcode`,
`three_x`, `wii2d`. The rest are reflowed afterward by token-aware wrappers in
`wrap.py` (never a blind character slice — that would split `-6` or BIO's `0ox`
triples). A width too small is answered with the narrowest available shape
rather than an exception; `dig` even stands the program on end and runs it down
two columns.

---

## Boolean generators

### Constant-subtree folding — the single biggest lever

Verified in `boolean-constant-folding.md` by a ones-count-controlled length
test (equal ones-counts prevent complement effects from confounding).

**Fold (16):** addsubjump, back, bfpda, bio, bitdeque, grapheme, jaune,
lamfunc, nocomment, polynomial, ram0, rotfuck, sbleq, six_five_arithmetic,
three_x, ztoalc_l — plus basicfuck, brainif, dig, laserfuck, between, and the
`decision_tree_program` pair (brainfuck/bf_tree, dimensional/dimensional_tree),
which fold inside their own construction.

**Build a tree but never fold (16):** myscript, nevermind, clockwise,
forbin_boolean, flowchart, circlefuck, circlefuck_byte, decleq, sophie, forth,
modulous, unsquare, eval, arrowqueue, streetcode, six_five (n≤5).

Three generators inherit folding rather than implementing it: `factor`,
`painfuck`, and `three_d_brainfuck` all call `brainfuck()` and transform its
output, so they fold because it does. Their docstrings still describe a
"shorter of minterm and tree" dispatch that no longer exists — stale prose, not
stale code. Folding matters most to `factor`, which encodes the program as an
integer and refuses tables whose encoding exceeds Python's digit limit, so
folding turns some previously unrenderable tables into runnable ones.

Folding was decisive enough to **retire whole constructions**: both `brainfuck`
and `dimensional` used to return the shorter of a tree and a minterm evaluator;
once the tree folded it won on every table at n≤4 (bar two constants, by a
bounded 2.5x), so the second construction and its dispatch were deleted.

Two constraints govern the fold:
- **Reads must not be skipped.** A folded leaf still consumes every input, or a
  caller feeding several programs from one stream desyncs.
- **The leaf must be path-independent.** `basicfuck` folds because its leaf just
  names `out`; BrainIf's leaves once jumped to a shared routine assuming the
  pointer had passed every marker, which cancelled the fold exactly until the
  answer byte was moved to cell 0 and built first.

### Complement / polarity

`_maybe_complement` flips a table with more ones than zeros, evaluating the
zero rows and inverting — one term saved per row, paid for once.

| Generator | Cost of the flip |
|---|---|
| `circuit_diagram` | **free-ish and huge**: a dense 3-input table drops ~7000 → ~130 characters |
| `collatz_multiverse` | **free** — the OR already ends on the flip it would have added |
| `point_break` | **free** — `g` is `1 - f` for its own loop-guard reasons |
| `suptiftam` | one line, against four lines per input per minterm |
| `qoibl`, `bit_tilde`, `grapheme` | fewer minterms; grapheme picks whichever row-set is shorter |
| `six_five_arithmetic` | evaluates `T'` when the complement integer is smaller — rescues NAND-n from outright rejection |

`_maybe_complement`'s docstring flags the trap: an all-ones table complements to
*no* minterms, indistinguishable from all-zeros. Fine where the sum feeds an
inversion; wrong for `circuit_diagram`, which special-cases constants to a
single self-fed gate.

### Layout and geometry

| Generator | Optimization |
|---|---|
| `laserfuck` | ring reader does 48 subtractions as a **loop** — 2 rows regardless of n, vs 49 columns per input. Tree rows scale with *one* edges only; the all-zeros path is a straight line. Cell 0 doubles as counter **and** answer cell. A zero answer emits no code |
| `clockwise` | hoists the root's 7 reads onto row 0, retiring seven rows (~⅕ of blanks). Printing `'0'`/`'1'` costs one `+` since they differ by one bit |
| `flowchart` | leaves laid on exact `(( ))` pitch with **no gutter** — n=4 drops 2444 → 1557 characters |
| `back` | load runs down column 0 so no row carries it as indent; one `/` does both turns |
| `streetcode` | shapes differ in aspect; a width picks among them. `_streetcode_lift` moves the leading run to the oncoming lane, taking columns off every row |
| `dig` | pruned rows are **never written**; `$` covers a run of cells so the forced reads need no block each |
| `wii2d` | bit-vector requirement sets, dedup of routes sharing a preimage effect; budget counted in *work units* so output is machine-independent |

### Structural / algorithmic

| Generator | Optimization |
|---|---|
| `bf_tree` | tree shares bit tests: `O(2**n)` vs minterm's `O(n * 2**n)` — XOR-n at n=8 is 20K vs 33M characters |
| `nocomment` | computes the numeric index and uses it as a byte-sized skip into a staircase — straight-line, no leaf chains. `s` doubles as a NOT gate, so the complement is computed at runtime from one embed |
| `home_row` | packs bits into one accumulator + linear chain; the removed routing generator walled at n=2 |
| `six_five_arithmetic` | builds `x` by a **loop**, not unrolled per bit, so marker count is constant in n (removes the 35-label cap) |
| `bfstack` | avoids branching entirely — encodes inputs as a number, decodes with nested loops |
| `suffolk` | branch-free minterms at `limit=1`; **constant tables need no reads at all** |
| `three_x` | result defaults to the **majority** table value, so only differing rows emit an override |
| `bitdeque` / `ram0` | fixed-length setters keep absolute `GOTO` targets stable — this is what unblocked the earlier "variable-length setter" wall |
| `lamfunc` / `ram0` | each input stored once and read back, rather than re-embedded at every node |
| `ztoalc_l_boolean` | tries every `b1` in turn with the simulator as sole gate, keeping any smaller start that places without collision |
| `point_break` / `arrowqueue` | no output command — use the halt/loop termination convention |

### Equal-width embedding (the deliberate non-optimization)

`bio` (`0oz;` to a dead register), `bfstack` (4-char run proved minimal by
exhaustive search over `<>@[]`), `back` (constant `-` primer, then `+` or `-`),
`home_row` (`a` then `s` or `j`), `bfpda` (4 chars), `eval` (2 chars),
`bitdeque`/`ram0`/`minsky_swap` (fixed-length setters), `wii2d` (one-column
junction slot). `back`'s zero once embedded as a blank that `rstrip` removed,
making the program's *height* reveal the input.

---

## Sources

- Shared machinery: `text/helpers.py`, `boolean/helpers.py`, `wrap.py`,
  `laserfuck_layout.py`, `ztoalc_starts.py`, `_polynomial.py`
- Folding classification: `boolean-constant-folding.md` (measured, not inferred)
  — currently untracked in the working checkout, not on this branch
- Everything else: generator docstrings and bodies under
  `src/esolangs/tools/{text,boolean}/`
