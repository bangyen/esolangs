# Limitations and contracts

Standing contracts and walls.  Polynomial's scaling wall is proved in
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

Every generator's worst-case class, read from its construction rather
than measured, is the Scaling column of the [proofs ledger](proofs.md#generator-ledger),
checked against the roadmap's audit by `tests/proofs/test_linearity.py`.

The survey behind that column found 22 time-only super-linear terms, mostly
`Theta(T log T)` from per-node table slices and per-level concatenation.
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
SLOW ACV MAMMALIAN's per-node retry loop dry-runs a candidate landing
before committing to it, and used to re-simulate an O(weight) weight-raise
and trampoline build on every retry just to size and length-check the
candidate.  Both are now O(1): the weight-raise's chunk sequence is a
residue orbit over 256 states that a cycle detector skips through by
multiplication, and the trampoline's chunk count is closed by division
once past its first two chunks (each spends exactly one `SEED`).  Measured
flat at ~0.021 microseconds per emitted token across four doublings.

**Factor's folded tree is Theta(T log T) on parity; the language forces
`Omega(T log T / log log T)` for some table under every encoding.**  The
folded Brainfuck tree has Theta(T) maximal command runs; each consumes
the next prime in one of eight nonzero residue classes modulo 11, the k-th such prime has Theta(log k) digits, and run compression
changes exponents, not the number of distinct primes.  Language-level: with D
digits and m active primes, `m = O(D/log D)`, exponents sum to O(D), their
compositions into at most m runs number `exp(O(D log log D/log D))`, and the
residues add `8**m`, so D-digit texts decode to `2**o(D)` programs.  If
D = O(T) that is `2**o(T)` functions against `2**T` tables.

**Polynomial's text is `Omega(T^2/log T)` for some table under every
encoding.**  Instruction count is language-forced at `Omega(T/log T)`: the
input instruction overwrites the register, so between reads every bit about
earlier inputs lives in the cursor, and the routing lemma puts
`L = Omega(T/log T)` of those instructions on real prime-power roots.  Every
program's text is the coefficient digits of a multiple of the mandatory root
product, and the iterated elimination's slack certificate -- the pure
exponential sum on the `L - u` largest roots, whose tail each leading zero
divides by one more `(rho - 1)` -- forces a `(u+1)`-th coefficient of at
least `prod_{i>2u} (p_i - 1)` times the leading one, for free positions
anywhere and every degree.  Summing over `u <= (L-1)/2` gives
`(1/4 - o(1)) L**2 log L` nats of coefficient mass, for every cofactor,
every operand sign and every degree, so the text is `Omega(T**2/log T)`
characters.  The proof is in [polynomial](polynomial.md) and every link is
pinned in `tests/proofs/test_negatives.py`; the earlier partial bounds it
subsumes (right half-plane `Omega(T^2/log T)`, Descartes-minimal
`Omega(T^2/log^2 T)`, the primorial's linear floor) are recorded there
too.

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

A per-station substitution of the one-lane node's valve (a shared
corridor, station `k` decrementing once and printing on a `+`/valve/`<`
sibling) was executed and refuted: the valve's `))<((` only guarantees
survival of a compile-time-known value (0, the very first read) through
the `<` in its middle, by shifting it to a range the `<` never kills
(`+2` then `<` excludes only `-2`).  Substituting station `k` does not
make the *arriving* value compile-time known -- it is `v - k`, fixed
only for `k = 0`.  Fed a compile-time nonzero value instead (extra `)`
cells before the same eight commands), the valve still passes the `<`
(nothing excludes a positive value), so the `_` sibling that was meant
to pass through on a known zero now reflects instead, re-entering the
shared `+` and re-forking without end: still unhalted and past 700
printed characters at 3,000 ticks, for every offset tried
(`test_the_valve_only_works_on_a_compile_time_known_value`).  A shared
corridor needs the same O(1) valve at every station, and only station 0
has a value fixed at compile time.

A shared decrement corridor with an *ungated* tap was then tried, size
rather than execution the target (a `+` fork: north continues, west
jogs and forced-turns north into `_`, then a bit-adjust and a private
O(1)-width dash to the left edge -- no valve, strays meant to be
tolerated since execution can stay `Theta(T**2)`).  Executed at n=2, the
simplest case (value 0 at the very first station): it does not tolerate.
A `_`-reflected copy returns to the same `+` heading the opposite way it
left, and `+`'s entry exclusion only blocks *that* one direction --
both the original entry and the original continue direction are open
again, so every round trip re-forks into both and the live population
doubles every four ticks (1, 2, 2, 2, 2, 2, 4, ..., 128 cods unhalted at
tick 26, nothing ever printed;
`test_a_shared_decrement_column_with_plain_fork_taps_explodes`).  A
plain `+` cannot host an ungated tap on a shared corridor at all; the
valve (compile-time-only) and an O(distance) gauntlet (the shipped
generator) are the only two ways found to keep a stray from re-entering
live, and neither gives `Theta(T)` size.  Round 3, and the row rests:
three obstructions pinned this session (concurrent strays, the valve's
compile-time requirement, the ungated tap's re-entry) on top of the
prior rounds'.

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

Concurrency was then executed on the shipped program (n=7, single-one
table, `test_the_t_squared_wall_is_concurrent_strays_not_walk_length`):
the worst index drives peak live cods to `T` (128), one stray per
still-open row converging on the same tick, because row `j`'s stray
needs exactly `V - j` steps to die and rows are peeled off one tick
apart -- but total ticks (7,713) stays far under `T**2` (16,384).  The
wall is `ticks * live-cod-count`, a *width* cost, not walk length; index
0 never builds the population (every stray dies within a tick or two).
So a fix that keeps the `T**2` grid but shortens the live walk (killing
a stray in O(1) rather than `O(V - j)`) does not exist on this
primitive set either: the only kill is `<` against zero, so an O(1)
stray kill needs a zero test independent of `|V - j|`, and none of
`)`/`(`/`<`/`_` offers one -- each only reaches zero by walking the
distance.

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

Interprogck8's corridor is the whole reach of the machine: every control
transfer is `DownAccLines` on an 8-bit accumulator, so a jump spelled past
255 wraps rather than lands (`NnNn` + 26 `@id` + 1 `@nd` then
`DownAccLines` reaches 6 lines on, not 262), and a residue shared for a
long flight's transit collides with a nested node's own landing marker on
it (a stride-30 flight built to reach +60 stops at +30, on the marker).
Both executed and pinned in `tests/tools/test_boolean_interprogck8.py`.
Every other stateful primitive was surveyed the same way: `{values...}`
writes only 81/84, never a target; a bare `$py` assigns acc with no
`% 256` wrap but only by consuming an extra stdin read outside the n-bit
convention; the function slot skips a captured body of any size with no
jump-distance arithmetic and branches on it with no `DownAccLines`, and a
one-read tree built on it alone (`TestPrimitiveSurvey`) executes all four
rows correctly -- but nesting a second read inside it is refused
unconditionally (`HaltError: nested function opener`), so it cannot
compose into an n>1 tree.

Polynomial's question was coefficient mass, not term count, and it is
closed: the class that survived every search -- a left-half-plane multiple
of the mandatory root product with O(T) digits across more terms than the
Descartes minimum, O(1) coefficients of O(T) digits and a *sparse* small
remainder -- has no member, because the slack certificate bounds *every*
multiple below.  What the searches established stands as the record of the
route.  Instruction count, monomial count, right-half-plane coefficient
mass, and the Descartes-minimal class are all language-forced, every
searched escape is closed, and the Rolle reduction behind Descartes cannot
lower the kernel's rank.  Executed (z3, exact): with
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
exists over three low coefficients through degree 26.  The full linear
program's certificate lifts that to `prod_{i>K+1} (p_i - 1)` times the
leading coefficient, asymptotically in the degree, for the lowest `K+1`
positions (integer z3: unsat at 60/120/192 and sat at 80/160/300 for
L=5,6,7); if it held for every unbounded set and degree, iterating it
would give every multiple `Omega(T^2/log T)` digits.  Those two
conditions are measured (every set of size <= 3 at L=4,5 and <= 2 at
L=6; the exact-degree certificate above the limit for every K at
L=5..7, degrees to 40, pinned in the proofs tests).  Proved for the two
largest roots at every degree: with the `L-2` lowest coefficients free,
some coefficient reaches `(p_{L-1}-1)(p_L-1)` (a Cauchy--Binet induction
on adjoined roots from an explicit two-root identity).  What remains is
the same inequality for `c >= 3` designated roots at the boundary of the
Toeplitz matrix (an equality in its interior by a Schur-function
identity; measured at c=3,4) and the free-position minimum, which is a
quotient gauge on a Descartes system, not a moment-cone principal
representation.  The exact minimum coefficient-digit mass over every
integer multiple is the product's own at L=3..7 in every cofactor
degree that finished (to D=12; 7, 12, 18, 25, 36 digits, exponent 1.93
over L=3..7, `Theta(L^2 log L)` exactly), so no O(T)-digit multiple
exists at those sizes and the target of the elimination is the truth;
over real monic cofactors the minimum is the product's mass less one
digit (L=3..6), so the linear-programming route is sound and the bound
is not an integrality fact.  The whole bound rests on one lemma
about pure exponential sums, now a theorem: a `c`-root certificate with
`c-1` prescribed zeros, the first `f` leading, has tail at most
`1/prod(rho-1)` over the `f+1` largest roots, with equality exactly when
every zero is leading.  It is proved by peeling one root and one zero
together -- `u = F + lambda G` with `F` on the `c-1` largest roots and `G`
vanishing at `0` as well, whose anti-aligned signs make `tail(F) - tail(u)
= mu T_G - 2 sum_{d>z}|u_d|` an identity, reduce the step to
`Gamma_G <= Gamma_F/(1-y_c)`, and end in a count of the zeros of one
`(c-1)`-root sum.  With it every program is `Omega(T^2/log T)` with
constant 1/4, the `c >= 3` truncation question and the free-position
exchange argument both disappear (the slack certificate forms no truncated
Toeplitz minor), and Desnanot--Jacobi is recorded as not lifting `c=2`.
Superseded en route and kept as record: the tail is not monotone in the
zero positions, so no principal-representation theorem applies and the
peel compares against the escaping limit instead; the `k=1` convolution
is the peel's degenerate case; and the lossy triangle induction
(`K(c) <= K(c-1) + 0.7`, c=3..8) and the Lagrange-basis decomposition of
`E` are not needed, the identity being exact where the triangle inequality
was not.  Root-set term bounds (Descartes on either
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
edge labels straight-line strings, final value 48 or 49.  Executed:
resolving the last input from `_WII2D_JUNCTIONS`' fixed catalogue alone
(no fold) misreads AND (`0001`, n=2) at row 01 -- three surviving
accumulator values (0, 1, 2) need two digits (0, 0, 1), the catalogue's
edge labels are the same two strings for every value on an edge, and no
instruction inspects the value to choose a third, so the fold is not a
search layered on the decision tree; it supplies the last two edges'
labels the catalogue cannot.  Fourteen executed rounds on WII2D have now
ended in the measured target, an unproved lemma, and this model; four of
them were on the readout rule alone (Phi-potential, an added merge-free
relayout vocabulary, an algebraic two-fold lookahead) and each ranked no
better than the shipped depth predictor -- Phi ratchets to refusal past
domain 16, the relayout vocabulary won 0 of many decode steps under the
shipped ranker, and the two-fold lookahead (relayout kept) was 0 relayout
wins over 30 tables and +5% to +65% chars/entry worse at domain 32--256
(one table -27% better, most 15--90% worse).  After the
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
optimum.  The linear reading of the optima was then tried as a rule
and fails at the first epoch: over every centre in `[-2D, 3D]` with
up to two doublings and every legal `(h, S)` (shifts sampled), the
least magnitude a first epoch can leave on the dense index with a
centre within 8 is 10--21, 33--39, 258--281, 528, 2096 at domain 16,
32, 64, 128, 256 (merging 1--6), and over all centres 7, 24, 87, 177,
383, at centres of 22, 17--44, 85--95, 86, 188 units merging 3--9 --
the small-centre ratchet begins between domain 32 and 64, and from 64
on a non-ratcheting epoch costs 0.7--1.4 `D` unary for at most nine
merges.  The greedy structured rule (fold within `C`, up to two
doublings, then the legal `(h, S)` with the most merges that pulls
the magnitude back to the live count) builds domain 16 at 3.7 per
entry with `C = 24` (exact optimum at most 2.8, shipped 6.0), domain 32
at 7.8 with `C = 48`, and nothing at domain 64 with `C = 96`; with
`C = 8` it builds domain 12 at 4.5 and nothing at 16.  **What is
proved about the readout model's first two epochs** (readout only:
one accumulator from the Horner index, no cofactor merging at earlier
junctions): write an epoch as `a` doublings, a centre `c`, `s`, then
`h` halvings with `un` unary among them (a global translation of the
image by at most `un`, absorbed into the next centre), and `kappa =
4**a / 2**h`.  On the dense index `0 .. D-1`, the every-radius lemma
at radius `1 / (4 kappa)` gives `kappa >= 1 / (16 (m_1 + 2) + 8
max(0, -c))` (or `m_1 >= D/16 - 2`), so the first epoch leaves `M_1
>= kappa D**2 / 4 - 1` and an image whose consecutive points at
radius `d` from `c` lie at most `kappa (2d + 1) + 1` apart.  A second
epoch with effective centre `C` that merges `m_2` and leaves
magnitude at most `4 live` has at most `2 m_2 + 6` live points within
`R = (M_1 - |C|) / sqrt(4 live + un_2 + 1)` of `C`, while that
window holds at least `2R / (2 sqrt(kappa (|C| + R + 1)) + kappa + 2)
- m_1 - 1` of them; with `Q = m_1 + 2 m_2 + 7` this forces `|C| >=
(R - Q (kappa + 2) / 2)**2 / (Q**2 kappa) - R - 1` when `|C| <= M_1 /
2`, and `|C| >= M_1 / 2` otherwise, so `max(|c|, |C|) >= min(D / 12,
D**1.5 / (50 Q))` up to the unoptimised constants of that derivation
(`un_1, un_2 <= D`, else the unary alone exceeds `D`).  With
`m = O(log D)` merges per epoch on a random pattern that is
super-linear for the prefix.  The exact two-epoch search (family:
`a <= 2`, `|c| <= live / 4` at resolution `2**-a`, `h <= 22`, every
legal `S < 2**h`, at least one merge per epoch, final magnitude at
most `4 live` -- every epoch without a halving before its `s` and
with at most two doublings; `two.c` in the scratch record) finds no
such pair from the dense index at domain 64 (three random patterns
and the alternating one, 1,168--16,103 first and 1.8e8--1.3e9 second
epochs each, exhaustive), 96 or 128 (one random and the alternating
pattern exhaustive each, the rest capped at 180--240 s) except one
at 0.62 `D` on a domain-128 pattern (centres -24.5 and -29.5 below
the index, nine halvings each, 12 and 7 merges), the all-ones pattern
doing it for 12--13 characters; and none from any of the 62 states
with 14 or more live that the shipped decoder passes through after a
return to `4 live` (eight per table, six tables at domain 128 and
three at 256; 54 exhaustive, 8 capped), the nine states at 8--24
live flooring at 0.83--2.9 `live` where the decoder's next two
epochs cost 1.3--4.4 `live`, and with every centre allowed the floor
is 1.55 and 1.86 `live` at 22 and 14 live (domain 64, exhaustive)
against the decoder's 3.0 and 2.7, and at most 2.0 `live` at 42 live
(domain 128, capped) against 4.2.  The decoder's live count falls by
5--20 per return, not by half (domain 128: 95, 79, 67, 42, 36, 24,
15, 9; domain 256 returns start at 73--127 live, its first 15--26
epochs running above `4 live`), so a floor of `c live` per two
epochs sums to `Omega(D**2 / m)` over the `D / m` epochs, the
decoder's own `D**2 / m`.  The floor is a set fact, not a path fact:
on random subsets of `[-4L, 4L]` and of `[-16L, 16L]` with `L`
random-labelled points, and on every-other and every-third
progressions (`L` = 16, 24, 32, 48, ten each, centres to `L / 4`,
40 s), the least pair found costs 0.62--1.19 `L` and no class is
cheaper than the real states (the sparser class floors at 1.19 `L`
at `L` = 16 and finds nothing at 24); at `L` = 16--48 two epochs'
halvings alone are about `4 log2 L`, so these sizes do not separate
`c L` from a logarithm.  With the largest gap `g` carried as a parameter the dense-start
proof reads: a window of radius `rho` inside the hull holds at least
`rho / g - 1` points, so a first epoch whose centre lies within `e`
of the hull has `kappa >= (m_1 + 3.5) / (e + 4 g (m_1 + 3))**2`; a
one-epoch return to `4 live` (`kappa <= 1 / (4 live)`) therefore
needs `e >= live / (2g) - g (2 m_1 + 5)`, and otherwise the epoch
leaves `M_1 >= live**2 / (64 g**2 (m_1 + 3)) - 1` with image gaps at
position `P` at most `2 g sqrt(kappa (P + 1)) + 1`; a second epoch
returning from there has at most `2 m_2 + 6` live points within `R
= (M_1 - |C|) / sqrt(4 live + 1)` of its centre, which the image
denies for every centre inside its hull once `sqrt(live) / (4g) > 2
m_2 + 6`, and a centre `e_2` below the hull needs `e_2 >= kappa
(live**1.5 / 8 - g**2 (2 m_2 + 6)**2)`, so the two-epoch cost is at
least `min(live / (2g) - g (2 m_1 + 5), live**1.5 / (256 g**2 (m_1 +
3)), M_1 / 2)` for `live >= 16 g**2 (2 m_2 + 6)**2`.  With `g = 2`
that is `live / 4` past about 20,000 live and nothing below, so it
is consistent with every measured floor and explains none of them;
and `g` is not 2: the largest gap at the shipped decoder's returns is
7--35 (domain 128: 10, 10, 9, 8, 7, 6, 10, 2, 4, 4, 1 at 95 down to
9 live; 25 at 84 and 35 at 20 live on one table; domain 256: 12--24
above 40 live), because an epoch at stable magnitude doubles the top
gap (`2 g sqrt(kappa M_1)` with `kappa M_1` about 1) -- no operation
pays magnitude to open a gap, the fold opens one for free at the far
end and the halving closes only the near end.  The invariant "gap at
most 2 after a return" is therefore false, and with the measured
`g` the theorem prices only `sqrt(live)`.  The profile class the image-gap
formula names, `S(a, L)`: `L` points in `[0, 4L]` with the gap at
position `P` at most `a sqrt(P) + 2`.  Every one of the 89 real
return states (domain 64--256) lies in it with `a <= 2.1` but one
(3.8 at 20 live), median 0.8, and `a` does not grow along the
decoder's path; it is not closed under cheap epochs -- a fold near
the origin at stable magnitude maps `a` to about `2a` at the top of
the image (`2 sqrt(kappa P) (a sqrt(P_pre) + 2)` with `kappa P` near
1 and `P_pre` near `4L`), while a fold about the top, which costs
about `4L` unary, maps it to `2 / sqrt(L)`; the decoder's bounded `a`
is bought by its centres.  On the class, a one-epoch return is
priced: a centre inside the hull at position `P_0` sees gaps `g_0 =
a sqrt(P_0) + 2`, so `kappa >= 1 / (16 g_0**2 (m_1 + 3))`, and the
return needs `kappa <= 1 / L`, hence `P_0 >= (sqrt(L / (16 (m_1 +
3))) - 2)**2 / a**2` unary; below the hull it costs `L / 4 - O(1)`,
above it `4L` -- all `Omega(L)` for bounded `a`.  The two-epoch
branch is not: the count condition (at most `2 m_2 + 6` live points
within `R = M_1 / (2 sqrt(4L + 1))` of the second centre) against
image gaps `2 sqrt(kappa X) (a sqrt(P_0) + (X / kappa)**(1/4)) + ...`
yields `X >= kappa L**2 / (4.5 a (2 m_2 + 7))**(4/3)` and exceeds `R`
only past `L` of about `((4.5 a (2 m_2 + 7))**(4/3) / 2.24)**2`,
20,000 at `a = 1` and five merges, so it proves nothing at any
measured size.  Resumption point: the two-epoch branch on `S(a, L)`
with the count condition replaced by legality -- the count is what
costs the `4/3` power and the `(2 m_2 + 7)**2`, and the measured
floors (none under `live / 4` from 71 states) say legality is doing
the work.  The model: the shipped chain
merges no cofactors before the readout on any of the nine tables
above nor on 59 of 60 random tables at five to seven inputs (first
junction `("", "+")`, then Horner), and the exact optima are readouts
by construction, so every program measured lives in the readout
model -- evidence that the model is the language's for random
tables, not a reduction.  Incompressibility (Li--Vitanyi
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
