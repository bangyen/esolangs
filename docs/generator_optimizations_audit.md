# Generator optimizations: inventory and standardization audit

> **Status: the recommendations in this document have been applied.**
> `_ASCII_ZERO`/`_ASCII_ONE` (B2), `shortest()` (B1), the equal-width
> invariant plus its enforcing test (B3), and the wii2d determinism fix
> (D1/D2) are all in the tree.  Section D3 (splitting `other.py`) is
> deliberately **not** done -- see the note there.  Verified: 3555 tests pass,
> ruff and mypy clean, and all 488 sampled generator outputs (truth tables
> through n = 4) are byte-identical to `main`.  At n = 5 the change is
> *intentionally* visible: hard tables that `main` failed on with a
> `ValueError` now succeed -- see the D1 section.
>
> **Reproducing this verification requires `PYTHONPATH=$PWD/src`.**  This
> checkout's `.venv` has an editable install pointing at
> `.claude/worktrees/laserfuck-block-refactor`, so a plain `pytest` or
> `python -c "import esolangs"` imports *that* tree, not this one.  See the
> environment note at the end.

Scope: `src/esolangs/tools/text/` (3,232 lines, 7 files) and
`src/esolangs/tools/boolean/` (7,840 lines, 17 files).

Method: shared helpers were inventoried by grepping every call site; per-generator
optimizations were found by mining docstrings and comments across **all** modules
in both packages for rationale markers (`instead of`, `rather than`, `shorter`,
`cheaper`, `O(`, `avoids`, `minimal`, `fewer`, `saves`). Sizes and timings quoted
below were measured, not estimated.

## Why "optimization" is a real contract here, not a nicety

Output program size is an **asserted contract**, not incidental polish. The
test suite pins it in several places:

- `tests/tools/test_generate.py:135` — `assert len(program) <= reseed`
- `tests/tools/test_generate.py:273` — `assert len(program) <= len(_clockwise_ring(bits, None))`
- `test_streetcode_emits_the_shorter_of_ring_and_street`
- `test_streetcode_ring_beats_the_straight_walk`
- `tests/tools/test_boolean_other.py` — `test_a_narrow_width_beats_the_old_floor`

So the default posture is **keep** the optimization: removing one can break a
test and, more importantly, can push a generator past a width or a language's
real limits. The bar for calling something "overkill" has to be higher than
"this code is dense."

---

## The inventory

### A. Fully standardized already (leave alone)

| Optimization | Location | Reach |
|---|---|---|
| `_validate_truth_table` | `boolean/helpers.py` | **15/15** boolean modules |
| `decision_tree_program` | `boolean/helpers.py` | shared by `tape.py` + `dimensional.py` |
| `_factor_triple` (O(sqrt) not O(value)) | `text/helpers.py` | `text/tape.py`, `text/other.py` |
| `_cm_constants` / `_extend_plans` (O(log) constants) | `text/helpers.py` | `text/register.py`, `boolean/register.py` |
| `_literal_chunks` (honour width by reshaping) | `text/helpers.py` | `other.py`, `stack.py`, `register.py` |
| `_require_bytes` / `_require_ascii` | `text/helpers.py` | 4 modules |
| `_maybe_complement` / `_complement` | `boolean/helpers.py` | 5 boolean modules |

`_validate_truth_table` is the model to imitate: one helper, total adoption,
zero per-call-site cleverness.

### B. Cross-cutting idioms that are NOT yet standardized

**B1. "Build both shapes, emit the shorter" — `min(..., key=len)`**

The single most repeated strategy, present in *both* packages:

- `text/other.py:99` — `min((folded, ring), key=len)`
- `text/other.py:1563` — `min((absolute, magnitude(text)), key=len)`
- `text/other.py:1719` — `min((ringed, folded), key=len)`
- `text/other.py:1726` — `min((ring, straight), key=len)`
- `boolean/dimensional.py:106` — `key=len`
- `boolean/tape.py:353` — `min((_bf_minterm(...), bf_tree(...)), key=len)`
- `boolean/streetcode.py:487` — `min(programs, key=len)` (and the same rule
  stated three more times in its prose: lines 9, 120, 470)
- variants spelled as comparisons: `text/tape.py:97`, `boolean/stack.py:65`

**Recommend standardizing.** It is already the de-facto house style and the
tests encode it. Worth a tiny named helper in a shared module, e.g.
`shortest(*candidates)`, so the intent is declared rather than re-derived, and
the two comparison-spelled variants join the same idiom. This is a readability
*win*, not a cost — it is pure de-duplication of a decision rule.

**B2. `48` as a bare magic number**

`ord('0')` appears as a bare `48` literal **44 times across 11 modules**
(counted by tokenizing, so comments and docstrings are excluded):

```
register.py    12   tape.py        12   stack.py        4
dimensional.py  3   other.py        3   parameterized.py 3
six_five.py     3   helpers.py      2   rotfuck.py       2
wii2d.py        1   ztoalc_l.py     1
```

Every occurrence means the same thing: input digits arrive as 48/49, and output
prints as `48 + bit`.

**Recommend standardizing** as a named constant (`_ASCII_ZERO = 48`) in
`boolean/helpers.py`. Cheapest, highest-readability change in the audit — it
converts a number the reader must decode into one that reads itself. Note
`boolean/other.py:345`'s `_LASER_OUTER`/`_LASER_INNER` already does exactly this
locally (`8 * 6 == 48`), proving the pattern is wanted.

**B3. Equal-width bit embedding — a deliberate *anti*-optimization, already
consistent, worth stating as a rule.**

`boolean/examples.py:177-185` and `:231-238` document the same trap twice: an
earlier version embedded a zero as *nothing* (or as a shorter run), which made
the emitted **program's length reveal its own inputs** — at `n == 2` the four
instantiations ran to 236/240/244/248 characters. Both now pad to equal width,
accepting a longer program on purpose. `examples.py:232` proves four characters
is minimal by exhaustive search over `<>@[]`.

This is the inverse of every other entry here: shortness is *given up* for
correctness. It is already applied consistently, but it is nowhere written down
as a package-level invariant, so the next generator is free to reintroduce the
bug. **Recommend documenting it in `boolean/helpers.py`** next to `instantiate`
(whose docstring already records the removal of the unused `set_comp`/`{Ci}`
companion) — the natural home for "how bits get embedded."

### C. Genuinely load-bearing complexity (keep, despite the density)

These look like candidates for simplification and are not:

- **`wii2d`'s popcount reduction + behavioural dedup** (`boolean/wii2d.py`).
  The docstring at line ~100 carries a *counting-bound proof*: there are at most
  `10 * 15**(2n(L+1))` chains against `2**(2**n)` tables, so the general search
  is **guaranteed to fail** at high arity regardless of tuning. The popcount
  closed form is what makes symmetric tables of any arity reachable at all.
  Removing it removes capability, not just speed.
- **`_wii2d_sequences` BFS dedup by behaviour** — avoids enumerating `15**maxlen`
  strings. This is the difference between tractable and not.
- **`unsquare`'s cached BFS + accumulator reuse** (`text/other.py:1385-1455`).
  Documented, ~30 lines, one `@cache`, and the parity argument that bounds it is
  written out. Measured 21% reduction on `"Hello, World!"`. Well-contained.
- **`_pct_path` greedy** (`text/other.py:1515`) — 15 lines, documented as within
  3 ops of optimal, and keeps the accumulator under the interpreter's `acc > 3003`
  reset. The bound is *correctness*-relevant, not just size.
- **`_laserfuck_ring_reader` loop-built counter** (`boolean/other.py:345`) —
  turns 48 straight columns per input into a nested loop whose counter is itself
  loop-built (`_LASER_OUTER * _LASER_INNER == 48`). A shape change, not a
  micro-tweak. (Separately, the *text* LaserFuck generator's base-init is the
  one that shortened a loop body from 176 to 16 cells — a different generator.)
- **`decision_tree_program`'s complement guards** — the guards are what make
  each `]` exit after one pass. Load-bearing for correctness.
- **`six_five.py:145-159`'s packed arithmetic** — an integer constant costs
  `O(value)` instructions with `+5/+6/-5/-6`; the packed form is ~12x shorter and
  is what keeps the generator from trying to materialize an exabyte string.
- **`ztoalc_l.py:5`'s simulator-verified construction** (`_ztoalc_ok`) — searches
  against a simulator rather than constructing directly. Slower to generate, but
  it is the correctness guarantee, not a speed trick.

### D. Overkill / actively harmful

**D1. `wii2d`'s wall-clock deadlines — the one clear defect.**

`boolean/wii2d.py:131` tunes budgets by *seconds*:

```python
for maxlen, budget in ((2, 4.0), (3, 8.0), (4, 12.0), (5, 30.0), (6, 60.0)):
```

with `time.monotonic()` deadlines at lines 158, 246, 248, 313.

This makes **generator output machine-dependent**. Measured on this machine:

```
n=4: 0.0-0.1s  -> len 131-141
n=5: 10.8s, 17.7s, 17.5s  (against a 30.0s budget)
```

n=5 lands at 10-18s inside a 30s budget. The ladder at lines 131-165 *continues
to the next `maxlen`* when `_wii2d_search_start` aborts on the deadline, so the
direction is: a **slower** machine times out at the short length, falls through
to a longer op string, and emits a **longer program** — or exhausts the ladder
and raises `ValueError` on tables that succeed here. A faster machine completes
more of the search at the shorter length and emits a shorter program. Same
input, different output, depending on CPU speed and machine load. That is the worst property a
code generator can have: it defeats reproducible builds, makes CI flaky by
construction, and makes the emitted program un-diffable across contributors.

The optimization worth keeping is the length ladder (2→6) and the dedup. What
should go is *time* as the termination criterion. Replace with a deterministic
budget — a node/expansion counter or an explicit per-length cap. Same pruning
effect, reproducible output. **This is the one item I'd fix regardless of the
rest.**

**D2. Hand-tuned per-length budgets as tuple literals.**

Even made deterministic, `((2, 4.0), (3, 8.0), (4, 12.0), (5, 30.0), (6, 60.0))`
is five magic numbers fitted to sampled tables. Once D1 converts these to
counted work, they want a documented derivation or a single scale factor rather
than five independently-fitted constants.

**D3. Not overkill, but worth noting: `boolean/other.py` at 1,365 lines and
`text/other.py` at 2,078 lines.**

The optimizations inside are individually justified; the *aggregation* is the
readability problem. `other.py` is a catch-all in both packages, and the
per-language tricks in it are what a reader has to wade through. The
`wii2d.py` / `streetcode.py` / `circuit_diagram.py` split is the better pattern —
one language, one file. This is a file-organization fix, not an
optimization-removal one.

---

## Recommendation summary

| Status | Item | Outcome |
|---|---|---|
| **done** | D1: wii2d wall-clock deadlines -> counted work budget | output is now a pure function of the truth table |
| **done** | B2: `_ASCII_ZERO`/`_ASCII_ONE` in `boolean/helpers.py` | 44 `48`s + 10 `49`s named across 11 modules |
| **done** | B1: `shortest()` in `tools/wrap.py` | 7 `min(..., key=len)` sites now name the rule |
| **done** | B3: equal-width invariant documented + test | `test_fills_embed_a_zero_and_a_one_at_equal_width`, 13 generators |
| **done** | D2: search budgets derived from measurement | five fitted seconds -> counted units with recorded calibration |
| **not done** | D3: split `other.py` per language | out of scope for an optimization pass; see below |
| **kept** | Everything in section C | load-bearing; some proof-backed |

### What the D1 fix changed, concretely

The search now meters `pre` evaluations instead of reading the clock. Measured
cost of a *successful* search, over seeded random tables:

```
n == 3    686 evaluations (every table)
n == 4    1.5K - 32K
n == 5    0.4M - 20.2M
```

Each ladder level gets ~4x the largest success measured at it. The old 30s
level-5 clock was *below* the cost of the slowest success in that sample, so it
failed on tables the new ladder solves.

Demonstration, slowing every unit of work by ~4x without changing the work count:

| | old code | new code |
|---|---|---|
| fast host | 216-char program | 216-char program |
| slowed host | **`ValueError`** | 216-char program (byte-identical) |

`test_output_does_not_depend_on_machine_speed` pins this. The trade-off, stated
in the docstring: a slow machine now takes longer rather than silently emitting
a different program, and the search is not interruptible mid-table. Concretely,
proving a table unreachable now costs the whole ladder -- ~300M evaluations, or
roughly ten minutes at the observed ~0.5M/s -- where the clock capped a failure
at ~114s. That is the price of the answer not depending on the host.

Note this means n = 5 output is **not** byte-identical to `main`, by design:
tables needing 15M-100M evaluations at level 5 previously blew the 30s clock and
either fell through to a longer op string or failed outright. Those now succeed
at level 5. Measured on the truth table

```
01011001010110111000000101100000
```

which needs ~20.2M evaluations:

| | result |
|---|---|
| `main` | `ValueError` after **111.5s** |
| this branch | 212-character program in **42.1s** |

So the fix is not only more reproducible but strictly more capable here: it
solves in 42s a table `main` spent nearly two minutes failing to solve. The
488-output equivalence check above covers n <= 4, where the budget never binds
and the programs are unchanged.

### Why D3 was left alone

Splitting `other.py` (2,078 and 1,365 lines) is a file-organization change that
would touch every import in both packages and move code this audit found to be
correct. It is worth doing, but it is not an optimization fix and it would make
the diff above unreviewable. Recommend it as its own change.

The headline: this codebase's optimizations are unusually well justified — nearly
every one carries a docstring explaining the trade-off, and several are backed by
asymptotic or counting arguments. The problem is not over-optimization. It is that
two *cheap* standardizations were never made (`48`, `min(key=len)`), and one
optimization used wall-clock time as its termination criterion, which quietly
traded determinism for speed.


---

## Environment note: the `.venv` editable install is stale

Worth fixing before anyone else works in this checkout. `.venv` resolves
`esolangs` to a **different worktree**:

```
$ cat .venv/lib/python3.13/site-packages/__editable__.esolangs-0.1.0.pth
/Users/bangyen/Documents/repos/esolangs/.claude/worktrees/laserfuck-block-refactor/src
```

That worktree is `locked` in `git worktree list` and sits at commit `e701e2d`.
`pyproject.toml` sets no `[tool.pytest.ini_options] pythonpath`, so **plain
`pytest` imports the stale tree** -- confirmed directly: a test asserting
`hasattr(helpers, "_ASCII_ZERO")` fails under bare `pytest` and reports the
worktree path, while the same test passes with `PYTHONPATH=$PWD/src`.

This is a silent-false-pass hazard: tests appear green while exercising code
from another branch. Every verification in this document was run with

```
PYTHONPATH=/Users/bangyen/Documents/repos/esolangs/src
```

The durable fix is to reinstall from this root (`uv pip install -e .`), which
was left alone here since it touches the environment and another session's
worktree.
