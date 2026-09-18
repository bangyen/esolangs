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
left-half-plane multiple with more terms than Descartes requires, see
[polynomial](polynomial.md).

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

Polynomial's remaining question is a left-half-plane multiple of the
mandatory root product with more terms than the Descartes minimum:
instruction count, monomial count, right-half-plane coefficient mass, and
the Descartes-minimal class are all language-forced, every searched
escape is closed, and the Rolle reduction behind Descartes cannot lower
the kernel's rank; the open class carries O(1) primorial-sized
coefficients and has degree `0.72 L log L` or more unless a second
coefficient reaches the primorial's square root.
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
of at most 2.8.  Counting alone gives `0.21 T`; an accounting bound
(every `s` doubles the bit length of the far points, only `/` removes
bits, a cheap fold sits at the bottom of the window and merges the
short side only) would give `Omega(D log D)` if every fold merged
O(1) points, and the optima's relayouts are exactly folds that do not.
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
2026-09-17 under the roadmap's membership bar: a lookup table in a
language's syntax is not a generator.  Nopstacle's was a full decision
tree of corridors, `Theta(n 2**n)` with Brent--Kung's column-moment bound
on every levelled layout and the merged-node escape unbuilt, and its
alphabet (blank and `#`) could spell neither convention; ZTOALC L's was a
chunked array lookup whose commands sat on Collatz trajectory slots, with
every line-local path rule dead (Flajolet--Odlyzko) and dense paths
found only by search.

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
