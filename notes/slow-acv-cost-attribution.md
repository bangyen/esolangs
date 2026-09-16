# SLOW ACV MAMMALIAN: where the program size actually goes

Replaces sixteen probe scripts (`acv_padding`, `acv_gaps`, `acv_tokens`,
`acv_where`, `acv_pad`, `acv_seed_runs`, `acv_ccells`, `acv_reach_law`,
`acv_yield`, `acv_pinned`, `acv_arrays`, `acv_routable`, `acv_scaling`,
`acv_corpus`, `acv_drive`, `acv_cost_audit`) with their executed results.
The prototype they all import, `notes/acv_swap.py`, is kept -- it is the
only executable record of the retired pump-loop construction.

**All numbers below were re-executed 2026-09-15** against
`notes/acv_swap.py` at commit `f90a2447`, not copied from the scripts'
docstrings.  Where a docstring disagreed with the run, the run wins and
the disagreement is recorded.

---

## The headline

A SLOW ACV program's emitted size is its **address space, not its laid
text**.  `generate` renders

```python
" ".join(b.text.get(i, "SEED") for i in range(max(b.text) + 1))
```

so every address the construction never writes still ships a literal
`SEED`.  The linearity question is therefore about how the *top address*
grows, not about how many tokens any phase emits.

Measured, n=1 (`01`) to n=2 (`0110`):

| quantity | n=1 | n=2 | growth |
|---|---|---|---|
| emitted chars | 876,739 | 1,878,218 | **x2.142** |
| address span (tokens) | 160,307 | 338,619 | **x2.112** |
| cells written | 141,390 | 274,118 | x1.939 |
| cells padded (unwritten) | 18,917 (11.8%) | 64,501 (19.0%) | **x3.410** |

Linear in `T` needs x2.0 per arity.  Written text grows *slower* than
linear (x1.939); the gaps grow at x3.410 and drag the total over the
line.  **The written text is not the super-linear term -- the gaps are.**

The span ratio reproduces from a cold build: 338,619 / 160,307 = 2.112.

## Where the gaps sit

Every gap sits immediately below a `subtree` node, and the top-10 runs
are 100% of all gap mass at both arities:

```
n=1: span 160,307,  18,917 in 3 gaps   largest  9,042 below subtree d0:root
n=2: span 338,619,  64,501 in 9 gaps   largest 11,258 below subtree d2:11
```

Gap count tracks node count (3 -> 9), so padding is paid **per tree
node**.

## Which token carries it

Read off the artifact -- count the emitted string's tokens by type:

| token | n=1 | n=2 | n=3 | 1->2 | 2->3 |
|---|---|---|---|---|---|
| SEED | 134,377 | 274,957 | 1,887,675 | x2.05 | **x6.87** |
| EXCRETE | 12,927 | 31,762 | 87,346 | x2.46 | x2.75 |
| DIGEST | 2,547 | 5,790 | 48,403 | x2.27 | x8.36 |
| CONSUME | 10,402 | 26,000 | 38,980 | x2.50 | x1.50 |
| SPRINT | 46 | 90 | 178 | x1.96 | x1.98 |
| **TOTAL** | 160,307 | 338,619 | 2,062,626 | x2.14 | **x5.74** |

`SEED` is 83.8% -> 81.2% -> **91.5%** of the program and is the only
large term growing faster than x2 at both steps.  It is also what a
padded address renders as, which closes the loop with the gap
measurement above.

## The SEED run-length distribution

`SEED` is emitted in contiguous runs, so the run lengths say which fix
applies.  Measured:

```
n=1    134,377 SEED in  2,379 runs   >=1000:  3 runs holding 14.1%
n=2    274,957 SEED in  5,631 runs   >=1000:  9 runs holding 23.5%
n=3  1,887,675 SEED in 48,268 runs   >=1000: 21 runs holding 10.3%
```

At every arity the **100..999 band dominates** (83.9% / 74.4% / 87.6%),
and runs under 100 are always ~2%.  This is the "many runs, each at node
scale" case: the cost is per-node padding, not a few enormous sites.  The
fix implied is to *share* a raise across branches rather than pay it per
node -- anchors only ever rise, so a delta raise should be paid once.

## Why the counter term is not constant

The counter march costs `(dist_c - rounds)` pairs per node, which is O(T)
only if `CCELLS` is constant.  It is not -- `generate` doubles it on
reach exhaustion:

```
n=1  CCELLS 60 -> 60      36 nested gadgets
n=2  CCELLS 60 -> 60     264 nested gadgets
n=3  CCELLS asked 120, settled 240
```

So the construction is `Theta(T * CCELLS)`, not `O(T)`.

**The two-arity trap.**  At n<=2 the doubling has not fired, and
per-entry cost looks flat -- which reads as linear:

```
n=1  per-entry    506,738      -
n=2  per-entry    504,908   x1.993     <- looks linear
n=3  per-entry  1,348,680   x5.342     <- it was not
```

Do not read an n<=2 run as evidence the counter is constant.  Verdicts
here read in one direction only: a ratio near 2 is not evidence of O(T),
but a ratio above 2 that keeps climbing *is* evidence against it.

## The reach law: affine, so loops lose

Whether nesting a second counter level can reach O(T) depends on how
reach grows with counter rounds:

| reach law | consequence |
|---|---|
| `~c*R` (linear) | `C = Theta(T)` -> `Theta(T^2)` |
| `~c*R^k` | `C = Theta(T^(1/k))` -> `Theta(T^(1+1/k))` |
| `~c*b^R` (exponential) | `C = Theta(log T)` -> `Theta(T log T)` |

Measured (median climb by rounds requested, n=2, 257 pairs):

```
rounds    n   median climb   per round   ratio vs prev
     2   20          6,302       3,151        -
     3   18         13,891       4,630      2.204
     4   45         25,535       6,384      1.838
     5   36         33,983       6,797      1.331
     6   34         43,576       7,263      1.282
     7   36         53,737       7,677      1.233
     8   35         64,250       8,031      1.196
     9    6         73,598       8,178      1.145
```

The ratio **falls toward 1** rather than holding constant above 1, so
reach is not exponential.  Marginal reach at the top is ~9,300 per round
(64,250 -> 73,598), i.e. roughly **affine at ~10k per round**.  That puts
the family in the first row: `C = Theta(T)` and `Theta(T^2)`.  **Adding
counter levels cannot buy O(T)** -- this is why the pump lane was
retired, and it is a negative result, so it will not be rediscovered by
accident.

Note `acv_swap.py`'s own comment claims "the yield accelerates".  The
measurement above contradicts it.  The comment is wrong.

## The array budget

`SEED` adds `i + 1` to array `i`'s head mod 256, so a head reaches every
residue only when `gcd(i+1, 256) == 1` -- i.e. an **even index**.  Of 23
arrays the construction uses 17, leaving 6 free but only **one free even
array (16)** usable for a counter level.

The odd ones are not entirely useless: routing needs the head in a class
mod 23, and since 23 is prime and `g = gcd(i+1, 256)` is a power of two,
by CRT a head with a given residue mod 23 exists whenever `256/g >= 23`,
i.e. `g <= 8`.  Five of the six free arrays qualify (7, 13, 16, 17, 19);
only 15 fails.

*(The `g <= 8` conclusion and the array list also survive in git history
at `630c11a7^:docs/limitations.md:273`.  The CRT justification does
not.)*

---

## Reconstruction detail

Enough to rebuild the prototype if the code is lost.

- **Arrays**: `Q, C, M, B, P = 3, 5, 1, 2, 4`.  Array 0 payload ballast,
  M=1 mid anchor, B=2 trigger queue (127 cells + head, fillers >= 128),
  Q=3 second ballast, C=5 passthrough, pads 9-12, 21, 22.
- **Head cycle**: `0 -> Q -> C -> M -> B -> 0`, with `P -> B` for the
  outer level's replant hop.  Every gadget keeps the global SEED count at
  0 mod 256.
- **Pad chains**: `21->12->M` (M-pump exit); `22->9->10->11->0`
  (single-level payload exit); `13->14->15->P` (nested payload exit, into
  the outer body); `16->0` (outer counter exit, the final landing).
- **Even-array rule**: the nested chains use only even arrays, so the
  step `i+1` is odd, coprime to 256, and every head value in the routing
  class is reachable.  Array 15 (step 16) could reach only one.
- The root fixed point uses a naive `root_guess = cur + 2` walk that
  contracts at only ~0.49 a round and needs a wide attempt budget (n=3's
  second counter rung settles at attempt 17).  A secant step settles in
  ~4, but picks a different root and built a program whose row 110
  executes wrong (empty output) while every builder-side check passed.
  The naive walk stays: correctness here is address-sensitive and only
  the executed artifact counts.

## Method lessons

**Attribute cost from the artifact, not the call graph.**  Instance-keyed
`lay` instrumentation has now failed **three** times on this
construction: first by id reuse, then by an undercount (131 tokens
against a ~400k-token program), and now a third time -- the re-run of
`acv_where` reports laid tokens essentially *flat* between arities
(120,058 at n=1, 120,075 at n=2) while the program itself more than
doubles.  It is attributing a single builder instance's lays, and at n=2
that is 35% of the program.  Same for `acv_pad`: per-gadget pad pairs are
flat (9,339 -> 9,262) while the gadget *count* goes 36 -> 264.  The
growth is in how many gadgets run, not how big one is -- and only the
artifact reads (span, token census, gap census) saw it.
**`acv_where` and `acv_pad`'s docstring claims (89-91% of text in
`_nested_gadget`, growing x9.66) are not reproducible and should not be
cited.**

**A stale warning is worse than no warning.**  `acv_scaling.py`'s
docstring says the `notes/acv_swap.py` in the primary checkout "is the
older prototype that fails at n=2" and that real numbers require a copy
from `.claude/worktrees/linearize-three/`.  That worktree no longer
exists, and the warning is false: the current `notes/acv_swap.py` builds
n=1 (160,307 tokens) and n=2 (338,619 tokens) without error.  It was
fixed in place and the warning was never updated.

## Reproducing

`notes/acv_swap.py` is importable (its `__main__` guard is inert on
import).  Each measurement above is a short driver over it:

```python
import sys

sys.path[:0] = ["notes", "src", "."]
import acv_swap

p = acv_swap.generate("0110")  # 338,619 tokens
toks = p.split()
```

Span is `len(toks)`; written cells and gaps come from the builder's
`text` dict; the token census is `collections.Counter(toks)`.

## Not verified

`acv_scaling` and `acv_corpus` exceed 240s per build and were not
completed in this pass; the per-entry table above comes from
`acv_pinned`, which did complete.  The n=3 build took 212s.
