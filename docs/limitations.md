# Limitations and contracts

Standing contracts and walls.  The open Polynomial row is in
[polynomial](polynomial.md); closed scaling rows are recorded in their commits.

## Interpreter conventions

- Empty input is a no-op unless a language requires a seed or grid.
- Exhausted input raises `EOFError` unless the language specifies a sentinel.
  Malformed programs raise `ValueError`; runtime failure raises `HaltError`.
- Character input is line-delimited. A blank line is the package convention
  for `0`; it is not inferred from any language specification.
- Explicit frame stacks are uncapped. Forbin expression-position calls retain
  their documented host-recursion limit.
- Streetcode's four-way junction is an implementation convention: the wiki
  only specifies a choice between two roads, and its examples exercise none.

## Source positions

`esolangs debug --tui` marks only a source position. `ip_shape` is `offset`
(45 languages), `grid` (11), `line` (2), or `opaque` (7); undeclared tuple
positions are refused. `opaque` positions have no program mark.

Line extraction accepts anti-aliased PNGs while strokes retain a connected dark
core; the 3px scan fixture executes addition correctly. A one-third-pixel shift
of a 1px stroke followed by resampling erases that core and is rejected with 921
unaccounted pixels rather than returning a different program.

## Boolean generators

Parameterized generators embed inputs in the program, each exactly once.
`%^2^-1` cannot compute a two-input function from runtime input, and as a
template it cannot compute every table either: between two placeholders its
accumulator has 6263 distinguishable classes, and the suite's dense
seventeen-input fixture needs more at every thirteen-input cut
([proofs](proofs.md)).  Below that wall the shipped construction reaches
fourteen inputs on every table tried (dense fourteen is 1.8 MB, built in
about ten seconds) and refuses the dense fifteen-input fixture, whose
eleven-input cut has 2017 distinct cofactors among 2048 rows: nothing
compacts before the next lay, and the laid points jam the fold's one-slot
landing window.  Its screened
reorder requires a permuted template or fill mapping; with both fixed,
interleaving only lengthens the identity template. Input reordering has no
useful effect on Alight, Container, Grapheme, Home Row, or Packlang; do not
reopen this with a blind search.

`scripts/screen_input_reorder.py` measures the size of permuted-table builds,
not an admissible reorder under the fixed input-template and fill contract.
Interprogck8, Dig, Flowchart, BrainIf, Sophie, and SLOW ACV MAMMALIAN must test
stream inputs in read order; BF-PDA must consume its fixed stack order. No
instruction-only wire is derived for 123, Minifuck, WII2D, or COD. ArrowQueue's
conditional re-enqueue route remains open.

Every emitted character is build work.  Input reordering is optional
around a construction, but its work counts toward end-to-end generation
time: order selection builds at most four named candidates and its generic
greedy scorer stops at n=10; factorial and exponential contests are
test-only oracles.  No generator construction may use BFS or DFS; test-only
oracle searches may.

| Generator | Dense | Parity | Limit |
| --- | ---: | ---: | --- |
| Polynomial | 10 | 10 | 1,934-instruction guard; dense n=11 priced at 267 s and over 100 MB; not re-run. |
| WII2D | 9 | 10 | Cost policy: dense n=10 leaves a domain past the admitted 256. |

WII2D n=9 is partial: 54 of 64 sampled dense tables build and the rest refuse
promptly. Its magnitude guard is load-bearing. A per-node re-embed tree can
build dense n=13, but is outside the generator contract. `proofs.md` carries
a total decode inside the contract, folding the extremal same-colour pair; it
is refused here on cost, not reach -- the four refusing dense n=9 tables cost
0.8–1.6 MB each and the decode reaches domain 512. Under the shipped centre
and magnitude caps that rule refuses from n=7 (2 of 20 seeded tables) and is
3x the size at n=6, so it is not a drop-in decoder. The scaling is open: the
decode spells each fold centre in unary and the dense per-entry size climbs
58 -> 153 characters from n=8 to n=9; the roadmap's audit row states what a
linear construction has to get past.

Uncapped dense-program sizes at n=8/n=9: Circuit Diagram 1.78/2.51 MB,
Polynomial 1.59/5.02 MB, SLOW ACV MAMMALIAN 456/799 KB, 123 22.4/44.7 KB,
bit~ 27.5/55.3 KB, Factor 17.2/35.5 KB, ROTfuck 14.9/28.8 KB, COD
943 KB/3.67 MB. Run generated programs before claiming size or equivalence.

### Scaling

Every generator's source is O(T) in the table length except two walls, and
the registry-wide contract is `tests/proofs/deep/linearity.py`; its verdicts
read in one direction, since an n=8 -> 9 ratio near 2 is not evidence of
O(T).  Build *time* is a separate axis: Factor, Polynomial and WII2D are
super-linear on both; the roadmap's audit table carries the figures.
Vandevelo's affine-cube peel keeps every working set it scores and
updates them as points leave, and harvests deep-first in phases, so a
set is built once and charged to the points it hands over: O(T) but for
two terms, the size proof's exact-popularity fallback (`n * 2**n` a
call; none on random dense tables to n=14, one at n=15) and each clause's
dual-basis core, at most `sqrt(2**(d + 1))` inputs for a `d`-cube and
so a factor under `sqrt(n)` per clause, 2% of the build at n=15.  It
measures x1.7--2.3 per added input over n=10..15 against the per-cube
peel's x2.5--4.1, at 0.93--1.02 of its size.  A build stays linear by
walking the table once: Circlefuck's greedy puts the essential inputs first and
scores at most eight levels, its essential-input scan compares sibling
blocks of the packed table, `n * T / 2` bytes in all, which at word width
`w` is `n * T / (2 w)` word operations with `n <= w` for any table that
fits in memory.

Decleq and Minsky Swap were `Theta(T log T)` by their jump targets, which
the contract read as linear (x1.92 and x2.20 at n=12).  A full decision
tree in an absolute-jump OISC names `T - 1` distinct targets, `Theta(T
log T)` digits however it folds, so Decleq's tree now stops `k` levels
short, `2**k >= 2n`, and each leaf is a `2**k`-cell table of `48`/`49`
indexed by a counter the low inputs decrement: 41 to 6.5 characters per
entry at n=12 on parity, execution `O(n)`.  Minsky Swap's `2**n` cascade
targets were `2**n` leaf addresses and its leaf `~`s spelled the end
address `2**n` more times; both now name one of two shared leaves at the
head of the program, a one-digit target per row: 18.9 to 5.1 characters
per entry at n=12, every table of one arity the same length.
Interprogck8's per-entry cost is a step function of the arity rather than
a line: one stride class serves fourteen inputs at 805-887 characters per
entry, a second costs 6300-6600 at n=15, and the placer refuses a
forty-first input, so the contract's x1.96 reads the first step's flatness
and nothing past it.

A survey on 2026-09-17 classified the 60 generators outside COD,
Polynomial and WII2D's open cells by reading each construction, since the
contract's measurement cannot see a `log T` factor in twelve doublings:
24 proved O(T), 8 argued, 1 measured only (`%^2^-1`, whose relocations no
invariant bounds), and 27 with a super-linear worst case -- 5 on size
(Factor's language bound, Streetcode, and Decleq, Minsky Swap and
Interprogck8 above) and 22 time-only, mostly `Theta(T log T)` from
per-node table slices and per-level concatenation.  Worst-case classes
come from reading the construction; the measurement is the regression
guard.

Those 22 are now O(T) time by construction, every program byte-identical
to before: each decision-tree generator walks `(lo, hi)` row spans with an
O(1) constant test and appends into one flat piece list joined once, so
no subtree is sliced, partitioned or copied per level (3x, 6-5,
AddSubJump, APL, Back, B-tapemark, BF-PDA, BIO, Bitdeque, brainfuck and
its Dimensional, Painfuck and 3D relatives, Crement, CV(N)(C), EGL,
Forth, Grapheme, Modulous, Packlang, Qoibl, RAM0, S*bleq, Suffolk,
Taglate, Unsquare); Back and B-tapemark render each row from its own
cells rather than the bounding box; Qoibl and 6-5's DAG cost name spans by
their halves so equality is O(1).  Four costs keep one log factor and say
so: `essential_inputs` and `stored_inputs` (`Theta(n 2**n)`, one C-level
slice-compare scan per input, shared by every generator that projects to
its essential inputs), Circlefuck's byte compare (the same scan), Fargo's
Moebius transform (`n` passes of `2**n`, the construction itself), and
Sophie's shared-state build, whose states are the residual subtables as
strings, `n 2**n` characters in all.  Generators that run
`best_input_order` pay its `O(n**2 2**n)` scoring, capped at `n <= 10`.
SLOW ACV MAMMALIAN is O(T) times its ballast iterations, about five per
level; the dry raise inside that loop depends on the chunk-shifted state
and cannot be hoisted without changing the program.

**Factor's folded tree is Theta(T log T) on parity; the language forces
`Omega(T log T / log log T)` for some table under every encoding.**  The
folded Brainfuck tree has Theta(T) maximal command runs; each consumes
the next prime in one of eight nonzero residue classes modulo 11, the k-th such prime has Theta(log k) digits, and run compression
changes exponents, not the number of distinct primes.  Language-level: with D
digits and m active primes, `m = O(D/log D)`, exponents sum to O(D), their
compositions into at most m runs number `exp(O(D log log D/log D))`, and the
residues add `8**m`, so D-digit texts decode to `2**o(D)` programs.  If
D = O(T) that is `2**o(T)` functions against `2**T` tables.

**Polynomial is open.**  Instruction count is language-forced at
`Omega(T/log T)`; every multiple carries `Omega(T/log T)` monomials; every
right-half-plane program is `Omega(T^2/log T)`; every Descartes-minimal
multiple is `Omega(T^2/log^2 T)` on the whole plane.  What remains is a
left-half-plane multiple with `O(T)` coefficient digits over more terms
than Descartes requires, see [polynomial](polynomial.md).

### Searched negatives

The closed searches behind each open roadmap row.  Re-running one is a
budget decision; the numbers here are what it has to beat.

COD's fork/cascade generator embeds each input once, at its own `+`
fork, and is super-linear on all three axes: size x3.9 per added input
over n=5..9 (942,668 characters at n=8, 3.67 MB at n=9; the cascade's T
leaf rows each carry a Theta(T) prefix and gate tail), build time
tracking the size, and the worst row's command count x2.32 per added
input at n=9 (40,464 commands), which the execution contract reads as
its exemption.  The constant-size two-polarity test exists once a bit
reaches a node (`<` keeps only one, `(<` keeps only zero, `(`/`)`
normalize the survivor), so a linear-area H-tree needs input `i` at
every node of level `i`; a shared run cannot distribute the bit to
separate node lanes without losing the lane identity, and carrying that
identity as the cod's value returns to the super-linear numeric decoder.
That is the row's open question on all three axes.

The position-identity decision tree is not inside the contract: lanes
carry value 0, level `i` is a fork row and a test row (blank keeps, `<`
kills), and it is `(3n + 12) T` characters, 8,132 at n=8 -- but its run
for input `i` is the whole test row, `2**i` cells wide, so the audit
measures it as non-uniform and blank-spelled, the shared-run problem
avoided rather than solved.  Its bounds still stand for any tree: a
level's span shrinks to `O(2**i)` only by fanning the next level across
the old boundary with `~2**i` arms on distinct rows, `Theta(4**i)` per
level; a numeric decoder built on `<` kills one value per trajectory
and is external path length, `Omega(T log T)`; `_` is a residue gate (a
U with `k` shifts releases one class mod `2k`, executed at k=1), so
isolating one value from `[0, T)` needs `Theta(T)` shifts, and a nonzero
cod reflected into a corridor `+` spawns copies up and down it
(executed, never halts).  A fork-free keeper of one value out of `K`
costs `>= K/2` shift cells by the residue argument; a keeper *with* `+`
inside, or a classifier mapping the index to the answer without
isolating it, is bounded only by counting at `Omega(T)`.

Executed on the interpreter, the same day: a plain cell with four open
sides is a crossing (a cod goes straight when its forward cell is open),
so planarity forces nothing and a `K_{3,3}` argument does not apply; a
plain cell with three open sides is a random junction for the cod whose
forward is blocked, so every deterministic join is a `+`, and a `+`
entered from a branch copies the cod out through the entry -- a join
always leaks a backward copy; a `_` reflection retraces the whole
arrival path as one block to the nearest `+` or dead end.  Cods never
interact, so the bit reaches a cod only by that cod (or a `+` copy of
it) crossing the input cell, in one of four headings; two cods at one
cell and heading with equal values share every later step, so a level
with more than four nodes carries the node in the value.  A `_` (or the
N-bound input cell, `_` when the bit is zero) releases exactly the cods
whose value is zero, all into one state, so each `_` cell is one
continuation and the rest reverse as a block.  The leak *is* killable
when the lane's value is known: `))<((` before a `+` passes a forward
cod of value 0 and kills a backward copy of value 2, and with a `<`
sibling the N-bound input cell is a halting two-way node of eight commands
(x=1 climbs on with value 2, x=0 reflects into the sibling with value
2, both print once) -- an O(1) node, but one whose input cell serves
one lane, the repeated embed again.  With the lane in the value the
valve has no fixed value to kill and the reflected block re-enters the
forward flow at the nearest `+` shifted by twice the trunk, so it must
lie outside the live range or be met by one `<` per value.  The open
question is therefore one gadget: a two-exit zero test on a block of
`R` values, `o(R)` cells, every stray cod dead.

A residue model was then executed (start values 0..23 injected, every
`<` kill and N-bound `_` release logged per cell).  On a single bounce
column (`>` corridor, `(`/`<` cells, `_` at the top) each cell removes
one residue class whose modulus is the round trip's net shift: `(<_`
kills the odd values, `((<_` the values `2 mod 4`, `<(_` kills even and
releases odd.  A `+` with two reflecting trunks (`(_` and `((_`) is not
a program: past 3,000 cods by tick 600 for every start value, no halt,
and one `_` releasing the same value up to 73 times, the classes now
`mod 2`, the gcd of the two round trips, with a finite pre-period.  On
the shipped programs at n=2..6 there is no cycle and no release: every
`<` removes one value per run, and across rows its set is a prefix
interval of the row index of size `2**k` (the zero set of an affine form
in the bits read so far), not a residue class of the full index -- so a
fate map is not a union of residue classes of the decoded index, and a
bound by that family alone is not a bound on the language.

A value-encoded funnel (lanes carry their prefix in the value, one
input cell, then a ladder of `_` rungs back to lanes) was executed on
its smallest ladder, two rungs (`+` with `_` above, `(`, `+` with `_`
above) on a block of start values: value 0 prints once but its east copy
reflects at the second rung and the run passes 5,000 cods by tick 95;
value 2 prints 29 times by tick 105; nothing halts.  A `_` met by a
block of two or more values reflects the rest as a block, which
re-enters the `+` and copies both ways, so no block may meet a `_` and
routing a block to lanes is left to `<`, one prefix zero-set per visit.

A read bound that charges each sibling pair of rows (one bit apart) its
own separating cells does not hold on this machine: on the shipped
program at n=6 the `<` at (40, 1) removes rows 0..31 in one cell, a
prefix zero-set that separates 32 pairs at bit 0 at once, and the
N-bound input cell separates a block of nonzero values on `x_i` with no
`(`/`)` cell at all (x=1 passes with +1, x=0 reflects the block).  So
the per-pair charge is off by the zero-set's size, and a bound over
every program has to price copies against zero-set kills and block
reflections together, which no argument here does.

Polynomial's remaining question is coefficient mass, not term count: a
left-half-plane multiple of the mandatory root product with O(T) digits
across more terms than the Descartes minimum:
instruction count, monomial count, right-half-plane coefficient mass, and
the Descartes-minimal class are all language-forced, every searched
escape is closed, and the Rolle reduction behind Descartes cannot lower
the kernel's rank; the open class carries O(1) coefficients of O(T)
digits and a *sparse* small remainder.  Executed (z3, exact): with
every non-constant coefficient bounded, the bound cannot go below
0.33--0.43 of the primorial at L=3..5 for any degree to 16 (13, 80,
844; LLL agrees to L=7), and the tail-height floor stops falling past
degree ~2L; with K large coefficients allowed and the rest at most B,
L=5 admits no K<=2 at B=11 and no K=1 at B=121 through degree 24, L=6
none of those through 26 (the least K at B = p_L^2 is 1, 1, 2, 3 at
L=3..6), and where the profile exists the
large coefficients are ~2^D and the remainder fills every degree,
which is `T log T` text.  Proved for the profile: above `K <= L - 2`
unbounded low coefficients some remainder coefficient is at least
`p_L - 1` (divided differences; tight at L=5), `Omega(log T)` digits a
term and nothing on the term count; at L=6 no remainder bounded by 13
exists over three low coefficients through degree 26.  Root-set term bounds (Descartes on either
ray, sector and unit-circle fewnomial bounds, cyclic-code weight
bounds, Tao's uncertainty principle) do not apply: the forced roots are
prime powers and `a +- p^b i`, on no ray, circle or root-of-unity set,
and nothing is reduced modulo `x^N - 1`.
[polynomial](polynomial.md) has the proofs, the measured negatives, and
the literature match.  The class is mixed, not Hurwitz: the mandatory
real roots are positive prime powers and only the cofactor sits left,
so coefficient positivity (which proves the right-half-plane bound)
is exactly what the class removes.  In lattice form the coefficients
are a vector of the integer kernel of `[r_i ** c_j]`, rank `t - L`,
determinant `e**Theta(L**2 log L)`, and every coefficient is fixed
mod `prod p_i ** (c_{j+1} - c_j)` by the ones below it, so a member
is one where `Theta(L)` CRT residues are all `poly(L)` small.
Support-restricted LLL over the kernel finds nothing below `P` from
L=4 on (`(x+1) P` wins at L=3 by 6%); constructed cofactors execute
at 1.002--1.055 of the shipped size for `(x+1)`, 1.35 for `(x+1)**L`,
1.44--1.48 for every mirror, exact or offset, and ~2 for cube
mirrors; the rank-2 kernel class is exhausted to L=4, D=12.  Any
legal multiple leaves a root unmatched, and `convert` then scans every
integer to `max|root| + 1`, so multiples load only to n=3 (a root of
`101**4` at n=4 does not load in a minute).

WII2D's remaining question is the decode: the last junction's two
branches turn the Horner index into the table's columns by folding
(`'-' * c + 's'`, one character per unit of the centre) and halving, and
the emitted size per table entry climbs 10 -> 15 -> 17 -> 53 -> 111 from
n=5 to n=9 on the suite's dense fixture.  The language's shape is
pinned from the interpreter: the accumulator is an unbounded integer
under digit, `+`, `-`, `*` (double), `/` (floor-halve, `-1` a fixed
point) and `s` (square); no cell reads it for control (`@` is
positional, `?` random), a junction exits the same way from every
heading, so a halting run reads each input once and every program is a
read-once branching program with one node per input, two edges each,
edge labels straight-line strings, final value 48 or 49.  After the
last `s` the readout is monotone, so the 0-points sit strictly below
the 1-points there; pulling back through a fold halves the alternation
count at most, `>= log2 A` squarings for `A` alternations, and a
monotone segment with `p` unary ops and `b` halvings folds about a
centre at most `p 2**b + 1` (enumerated over all 349,524 strings of
length nine), so a far centre is unary at the current spacing.  None of
that is a wall: the *exact* shortest readout over all op strings from
the index (BFS under a magnitude cap, exhaustive, replayed on the
interpreter) averages 1.42, 1.73, 2.04, 2.37, 2.34 characters per
entry over sampled patterns at domain 6, 8, 10, 12, 14 (caps 2**12,
2**12, 2**12, 2**10, 2**10; every pattern solved) and at most 2.76 at
domain 16 under 2**10, where a cap still shortens (one pattern 45 ->
37 under 2**12) and 2**14 overflows a 2**27-state table at depth 31.
Three to five squarings each behind a centre of one to seven units;
one-hot, sparse, Gray and signed index encodings never win, and moving
the decode up a junction has zero legal folds on seven of eight dense
columns.  The shipped rule spends 6.0 per entry on the same random
domain-16 columns and 7.6, 15, 41, 100 on the dense fixture at domain
16, 64, 128, 256: the cost is the extremal-fold rule's,
and a size proof would have to beat the optima above.  What the optima
do that the rule cannot: 15 of 52 folds in sixteen domain-10 optima
merge nothing (a fractional centre, `**+s`, that only reorders the
points before halving merges them), and the shipped enumeration only
lists centres with a same-colour pair; from the same post-`s` state the
shipped compressor lands on the optimum's live count and magnitude 21
of 52 times at 11% more characters, so the halving side is close and
the fold choice is the gap.  That gap is global: over the small-centre
family (`|c| <= 8`, scale 1/2/4, relayouts included) one-step greedy
under any of four keys ratchets past the magnitude bound on 6--17 of 20
domain-16 columns, and a beam of width 4, 16, 64 builds 16, 18, 20 of
20 at 5.6, 5.5, 6.0 per entry -- the shipped size, against an optimum
of at most 2.8.  Counting alone gives `0.21 T`.  Every domain-8
pattern's exact optimum (254 of them, cap 2**12) averages 1.68 per
entry, median 13 and at most 24 characters (`11010100`:
`++s/-//-----s-//--s-///s`); 38% of the optimal text is unary, 42%
halvings, merges split evenly between `s` (mirror pairs) and `/`
(blocks), an `s`-epoch merges 2.8, 3.4, 4.1 at domain 8, 10, 12, and the
magnitude before each `s` is `log2(live - 1)` minus 0.4, 0.3, 0.1 bits:
the optima never ratchet.  One fact about the readout is deterministic
and pinned in `tests/proofs/test_negatives.py`: an epoch (an `s` and
its `+ - /` tail) that merges `m` and halves `h` times has, for every
`n`, `m >= n - 2 r**2 / 2**h - 2` with `r` the n-th smallest `|w|`
before the `s` (n squares span `r**2`, which meets at most `r**2 /
2**h + 1` block boundaries and as many wide gaps, and every other
consecutive pair merges); at `n = m + 3` that is `2**h <= r**2`, so the
epoch leaves magnitude at least `max|w|**2 / 2**h - unary - 1 >=
(max|w| / r)**2 - unary - 1` (checked on all 1038 epochs of the 342
optima and 231 epochs of shipped decodes at domain 32--256; the m+3
ratio is at most 0.89).  Its contrapositive is the ratchet: an epoch
that does not raise the magnitude needs a centre whose density profile
is sub-quadratic, `N(c, rho) <= m + 2 + 2 rho**2 (M_out + unary + 1) /
d_max**2` at every radius, hence a gap of at least `sqrt(M / (8
(m+2)))` at the centre (1.14--1.5 times that on the tightest
non-ratcheting epochs seen).  On the dense index `0 .. D-1` the first
epoch's `r` is at most `m + 4` unless its centre is more than `D/2`
away, so it leaves magnitude at least `(D-1)**2 / (4 (m+4)**2) - unary
- 1`: a ratchet once `D > 4 (m+4)**2`, about 200 at the m = 3 the
optima show; on that image (points `kappa j**2`, gaps `2 kappa j`) a
second epoch either pays a centre at `D**2 / (4 (m+3)**2)` or beyond,
or has the first epoch ratchet to `D**4 / (512 (m+2)**3)`.  What does
not hold: a density invariant near the origin.  After every epoch of
the shipped decodes at domain 32--256 the origin has at most m+2 live
points within `sqrt(M)/2` (nearest such hole at distance 0--9 on all
60 non-ratcheting epochs), and `s`, `ss`, `sss` on `0 .. 63` leave 6,
7, 7 points within `sqrt(M)/2`: hollowing the origin is free, so
`N_t(X) >= X / f(t)` is false for every `f`, and only the profile
bound above survives.  The shipped decoder at domain 64--256 sits at
`M` between `L**2 / 15` and `L**2 / 8` and pays centres of 0.3--0.6
`M` per epoch of 3--10 merges (1288 and 4335 characters at domain 64
and 128, `D**2 / m`).  An epoch-level beam (width 16, every legal
integer centre to 4096, the shipped compressor per fold, key `length +
2 live + bits / 2`) returns 148 characters on one domain-12 pattern
against the exact 24--35 and times out at 60 s on three: not an
oracle, no beam figure at domain 32 or beyond.  What closes nothing
yet: the halving identity `sum over s of Phi <= length` with `Phi >=
log2 live` gives `Omega(D)` only, and the description bound (an epoch
is `(a, c, h, S)` with `S < r**2` by the lemma, so `2a + O(log
length)` bits) gives `Omega(D / log D)` epochs only -- the two balance
at linear, and the super-linear term would have to come from the
profile bound.  The span-to-gap route was checked and priced: with
`gamma` the plain gap of `V_(t-1)` between the preimages of the two
points of `V_t` bracketing the next centre and `Lambda = d_max /
gamma`, every non-ratcheting epoch with `M >= 16` and `live >= m + 3`
has `|c| + gap >= Lambda**2 / (32 (m+2))` on 108 shipped and 15
optimum epochs (least ratio 2.11; the radial-difference `gamma` fails
once at 0.71, the gap at the previous centre twice at 0.89), and the
plain-gap form follows from the lemma with `28 (m+3)**2` in place of
`32 (m+2)`: at most m+2 points lie within `d_max / sqrt(M + unary +
1)` of a non-ratcheting centre, so a gap of `sqrt(M) / (3 (m+3))`
sits within `sqrt(M)` of it, and a gap of `V_t` at position `P` pulls
back to a gap of at least `(gap - 1) / (2 sqrt(kappa P))` in
`V_(t-1)`.  It prices nothing past the third epoch: the same pullback
unrolled to the dense index gives `gamma_(t-1) <= prod over j < t of
2 sqrt(|c_j| + d_j)` with `d_j` the chain point's radius, so a program
paying `sqrt(M)` per centre has `Lambda` below one from the fourth
epoch on, and on the shipped decodes the forced centre is a median 2%
of `M` against the 30--60% paid.  What it does price is epoch two:
`|c_2| >= D**2 / (42 m (m+4)) - 2 sqrt(M_2)` unless that epoch
ratchets, and a program may ratchet there and un-ratchet later, where
nothing is forced.  Un-ratcheting was priced last: on the shipped
decodes every ratchet run (68 runs, all of one or two epochs, at most
ten non-ratcheting epochs between runs) ends with a centre of at
least 2.8 `sqrt(M_start)` (6.7 with `M_start >= 64`), but the exact
optima end 14 of their 15 runs with `live >= m + 3` and `M >= 16` at
a centre of zero: `01011100` under `-s-/s-///////s-//s` ratchets 7 ->
17 and then halves seven times about the origin, merging three of
seven, so no `sqrt(M_start) / (c m)` price holds.  The origin is a
free hole after any epoch (above), and a free un-ratchet after `k`
free squarings needs only the pre-run set to hold at most m+2 points
within about `sqrt(M)` of it, which the optima have at their size;
the lemma refuses it only once `D > 4 (m+2)**2`, past every exact
optimum.  Incompressibility (Li--Vitanyi
ch. 6) supplies the frame and nothing model-specific;
Mansour--Schieber--Tiwari floor bounds, 1D map folding (crimps and end
folds count folds, not unary creases), addition-chain bounds (one
target, no merging) and merging bounds (no comparisons here) do not
map.  All of this is the readout model: one accumulator from the
Horner index to a bit, no cofactor merging at earlier junctions.
WII2D's lift is the extremal-fold rule, total but at megabyte sizes,
and its three open cells are one question: a rule emitting readouts
within a constant of the optimum, which no one-step or bounded-beam
rule over small centres is.

Factor's row stays for its two language lower bounds (the language
floor is `Omega(T log T / log log T)`: exponents are unary-priced and
primes distinct and ascending, so D-digit texts decode to `2**o(D)`
programs; the folded tree's `Theta(T log T)` is the generator's).
`%^2^-1`'s `Exception` cannot close ([limitations](limitations.md));
what is left is finite -- which tables through sixteen inputs the
language admits and the planners refuse: every table tried through
fourteen builds, from fifteen the dense fixture refuses while parity
and other tables whose suffix cofactors compact still build, and no
cut below seventeen carries a counting witness for any table: the
dense fixture sits within 2--4% of the language-independent ceiling
`min(2**k, 2**(2**(n-k)))` at every cut through sixteen (1007--1022
of 1024 at the 10-cut of fourteen, 3932--4009 of 4096 at the 12-cut of
sixteen).  The ladder-span bound and the wipe alignment are the
planner's facts, not the language's: the language also resets by `m`
on `(1501, 3003]`, a move the planner lacks, and between placeholders
it is a transformation monoid on the 6,263 classes generated by `s`,
`i`, `m`, `p`, `'`, so a wall at fifteen is a finite question on that
monoid, unreachable by counting.

WII2D's decode still enumerates the legal folds and takes the head of a
ranked shortlist, but the ranking no longer runs the compressor per
candidate: `_wii2d_depth` reads the deepest legal halving level off the
adjacent different-colour arcs of the uncompressed fold, and `magnitude
>> depth` picks the same fold as the compressed contest on 779 of 785
states.  Compressing the winner alone, with the shortlist widened to
`live / 4`, is 0.84x the contest's size and half its time over 100
decode inputs at n=5..9 with no refusal the contest did not make, and
on 64 seeded dense n=9 tables the generator builds 54 where it built 38
(27 s against 57 s, mean 53.9k chars against 69.6k).  What remains is
the enumeration and the rank itself.  One-shot rules lose (nearest-
midpoint centre 1.06x and 0 of 8 dense n=9 against 4 of 8;
most-merges and cheapest-centre build nothing past n=6; the extremal
same-colour fold refuses from n=7 under the shipped caps and needs a
megabyte for dense n=9), and every scalar key over the uncompressed
state (best `log2(mag / gap) + scale + live / 3`) refuses 3-16 of the
18 inputs with domain 128 or more that the contest builds: the arc
union is what carries the rank, the arc sum (rho 0.83) refuses five,
and a per-step guard cannot recover a bad state entered folds earlier.

### Execution time

Source size and execution time are separate axes.  Execution is measured for
all 63 by stepping every row and keeping the worst, out to eleven inputs,
loading excluded, on parity tables (random costs the same or less).  It is
the product of command count and per-command cost, and neither predicts the
other.  The execution contract (`tests/proofs/deep/execution.py`) holds every
generator's command count linear; per-command cost belongs to the
interpreter and is recorded here.

- **Constant per command, linear program:** Minifuck, Forth, Back,
  ROTfuck, S*bleq, Qoibl, Container's command count, and about a dozen more.
- **Per-command cost is constant everywhere it was measured.**  Two
  designs keep it so: a bracket match is a table built at load, never a
  scan per skip, and an immutable tape, association list or pointer store
  is a chunked persistent tuple (`esolangs.interpreters.persistent`: a
  write rebuilds one 32-cell chunk and the outer tuple, untouched chunks
  are shared, and the value stays hashable for the cycle detector), with
  RAM0's store carrying a machine-level address index so a load is a
  lookup.  Either mistake reads x2.5-x2.8 per added input at nine inputs;
  the fixed interpreters read x1.5-x2.0.  Flowchart's pointer memory is a map at
  x2.1; Eval, Bitdeque, Collatz Multiverse and Container read x1.9-x2.35
  on runs of a few milliseconds, which is noise, not an exponent.
- **Sublinear:** twenty-two never read most of the table.  brainfuck's worst
  row is 113, 179, 251, ... 803 commands at one through eleven inputs;
  Factor, Polynomial, Circuit Diagram, EGL and Fargo are the same shape.
- **Container** runs fourteen commands at six inputs, each dividing a
  T-digit integer: linear work on a constant command count.
- **Loading** is excluded and is the whole cost for Factor (factoring the
  integer, a language cost, quadratic in digits) and Circuit Diagram (parse
  linear in an area that is super-linear by construction).  Streetcode's
  load is linear with a large constant.

## Curation

The collection has 63 languages. The floor is 34: the languages that own a
generator construction, Polynomial and Modulous for their walls, and
brainfuck for Factor's decoder. The 69→65 cut removed DINAC, MyScript,
Basicfuck, and Nevermind: ordinary imperative languages with shared-shim
generators and no downstream consumer. The second band removed Suptiftam,
Lamfunc, `function x(y)`, Between, and Point Break on the same criterion,
leaving 60. Crement, Nopstacle, Vandevelo, B-tapemark, and EGL were added
afterwards, and all five raised the floor.  Nopstacle and ZTOALC L left on
2026-09-17 under the roadmap's membership bar, on different clauses.
ZTOALC L's generator was a lookup table in the language's syntax: a
chunked array holding the table, its commands sat on Collatz trajectory
slots, with every line-local path rule dead (Flajolet--Odlyzko) and dense
paths found only by search.  Nopstacle's was a decision tree of corridors
like the shared meta-generator's, `Theta(n 2**n)` with Brent--Kung's
column-moment bound on every levelled layout and the merged-node escape
unbuilt; what removed it is that its alphabet (blank and `#`) can spell
neither the no-spaces nor the uniform convention, so no construction
under the conventions exists to be linear.

The 2D candidate pool is screened out; the screen is recorded because
re-running it is expensive.  `Category:Two-dimensional` x
`Category:Unimplemented` does not exist on the wiki.  The real intersection is
`Category:Unimplemented` (1543 pages) against `Category:Two-dimensional
languages` (567), reduced to 36 by subtracting languages already carrying a
verdict here, rejecting on co-category (no IO, stubs, works-in-progress, joke,
nondeterministic, output-only, non-textual, uncomputable), and rejecting
pages lacking input, output or branch vocabulary or under 1500 characters.
The top tier is resolved: Super SNUSP and Alight admitted, B-tapemark from the
second tier, Pinyin rejected -- its selection rule reroutes 8 of 23
`Hello, world!` characters and its truth machine on input 1 is unreachable
under all 384 readings of the page.  ABCDirection was implemented and removed.

## Specification decisions

- 6-5 accepts operands beyond its specification; generators use `0..35`.
- Jaune's dispatch to an undefined marker is unspecified.
- Alight expressions are infix, left-to-right; three-argument `at` mutates.
- Packlang numeric literals are decimal. Its cat cannot receive byte 10 under
  this package's line-oriented input model.
- Pinyin is rejected: its spelling-to-pronunciation rule contradicts its own
  examples, and its truth-machine input-1 example has no deterministic reading.

Generated programs are evidence only after execution through their interpreter.
