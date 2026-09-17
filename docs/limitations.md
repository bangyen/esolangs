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
([proofs](proofs.md)). Its screened
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
| ZTOALC L | 10 | 10 | n=11 needs 545–587 command slots; the line ceiling admits at most 395. |

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
super-linear on both; the roadmap's audit
table carries the figures, with Vandevelo (candidate scoring on 2**n-bit
masks) still open on build time.  A build stays linear by walking the
table once: Circlefuck's greedy puts the essential inputs first and
scores at most eight levels, its essential-input scan compares sibling
blocks of the packed table, `n * T / 2` bytes in all, which at word width
`w` is `n * T / (2 w)` word operations with `n <= w` for any table that
fits in memory.

**Factor is Theta(T log T) on parity and super-linear for some table under
every encoding.**  The folded Brainfuck tree has Theta(T) maximal command
runs; each consumes the next prime in one of eight nonzero residue classes
modulo 11, the k-th such prime has Theta(log k) digits, and run compression
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

Vandevelo's open cell is its peel, which restarts per cube and scores
~50 candidate directions on a 2**n-bit mask per round, Theta(T^2 /
word).  Keeping the chain of intersected sets across cubes reads x2.14
at n<=12 but is quadratic too: a level's direction switches Theta(T)
times and each switch rebuilds the level above at its parent's size.  A
window of a level's lowest 512 rows is linear in count and no faster; a
sampled score with growth through the lowest row is linear and 0.07 s
but +13--20% of cover.  Every non-restarting peel also trades
Cohen--Shinkar's O(T) clause bound for a measurement, since the popular
direction is no longer exact over the remainder.

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

Nopstacle is open on size alone: a full decision tree of corridors,
level `i` reading its input at `2**i` node columns of one row, in a
padded rectangle `4 * 2**n` wide by `3n + 7` high, `Theta(n 2**n)` by
construction (31,774 characters at n=8, x2.21 there and x2.13 at n=12
on the contract's two-step mean, per-entry cost 44.5 rising by twelve
per input).  The same H-tree question as COD's: a linear-area layout
puts level `i`'s cells on `2**(i/2)` rows, and one run fills one line;
every layout with a line per input is a `2**n`-wide row per input.

Nopstacle's two `Language` cells (the roadmap's conventions table) are one fact
about its walker: the alphabet is the blank and `#`, so a zero bit *is*
a blank and there is no command to spell it with; and a cell acts on
the walk only as the target of a neighbour heading into it
(`_advance` tests `grid[ny][nx]`), so an embed of fixed width `k` has
`2k + 2` ports and a template with one such embed per input is a
branching program with at most `2k + 2` nodes per input.  Fewer than
`2**450` of those exist against `2**512` tables at n=9 for `k = 1`
(n=10 for `k = 2`, n=11 for `k = 4`), so no uniform embed keeps the
generator total; below that bound an exact SAT model of the walker
finds a program for every table tried at n<=5, each a per-table search
with re-reads, which is not a construction.  To refute: a bit-dependent
mechanism in `_advance` other than a port read, or a total rule drawing
at most four ports per input.  (%^2^-1 is uniform through eleven
inputs -- every input is the one pair `s`/`i`, the template carries the
weight as doublings between the runs and the table as the fold's
relocations -- and past them the staged route lays its last two inputs
with pairs of its own, above the arities the audit measures.)

Polynomial's remaining question is a left-half-plane multiple of the
mandatory root product with more terms than the Descartes minimum:
instruction count, monomial count, right-half-plane coefficient mass, and
the Descartes-minimal class are all language-forced, every searched
escape is closed, and the Rolle reduction behind Descartes cannot lower
the kernel's rank; the open class carries O(1) primorial-sized
coefficients and has degree `0.72 L log L` or more unless a second
coefficient reaches the primorial's square root.
[polynomial](polynomial.md) has the proofs, the measured negatives, and
the literature match.

WII2D's remaining question is the decode: the last junction's two
branches turn the Horner index into the table's columns by folding
(`'-' * c + 's'`, one character per unit of the centre) and halving, and
the emitted size per table entry climbs 11 -> 16 -> 15 -> 58 -> 153 from
n=5 to n=9 on the suite's dense fixture.  A linear construction needs the
answer readable as the accumulator's *top* bit -- floor-halving discards
low bits and a digit discards everything, so nothing discards the bits
above -- and every cheap placement found (shifts by `2 ** q`, squaring's
cross terms, a dot product by multiplication) leaves other entries or
monomials above it.  Refuted by an op-string family of length O(T) that
computes an arbitrary column from the index, or from `2 ** (K +- q)`,
which the chain can emit in O(n) characters.  A readout that tolerates
junk above the answer is refuted too: every op but `s` is monotone on
non-negative values and `~` needs the exact 48 or 49, so after the last
squaring the readout is a monotone map onto two values -- a threshold
in value order -- and anything else needs another `s`, which is a fold
with a unary centre.  "Nothing discards the bits above" holds only over
a low field wider than one bit: `-` then `K - 1` halvings carry a one-bit
low field up as a borrow, leaving `2a + b - 1`, and integer-centre folds
then read `b` under any top field `a` at the price of `a`'s *value
count* (a two-bit `a` at `K = 30` executes in 72 characters).  So the
last junction is cheap given its two-bit class: `3x - 2y` on top yields
`x` by a threshold and `x ^ y` by one fold, both O(K), executed on all
four classes.  What that costs is the class, two functions of `n - 1`
inputs -- the same problem.  Recursing instead (store the table, let
each junction keep one half) needs the branch keeping the *lower* half
to forget the upper one above a multi-bit field: the borrow carries one
bit, halving further destroys the field, and a fold's centre there is
spelled at that field's weight, `2 ** m` characters for an `m`-bit
half.  The layout adds nothing: for a dense table every run reads every
input, a second read order would put a cycle some assignment follows,
and a junction cell can be entered from at most four headings, so any
fill yields a fixed chain read at most four times, never a tree.
WII2D's lift is the extremal-fold rule, total but at megabyte sizes,
and its three open cells are one question.

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

Factor's row stays for its two language lower bounds.  `%^2^-1`'s
`Exception` cannot close ([limitations](limitations.md)); what is left
is finite -- which tables through sixteen inputs the language admits
and the planners refuse: every table tried through thirteen builds,
from fourteen the dense fixture refuses while parity and other tables
whose suffix cofactors compact still build, and no cut below seventeen
can exceed 4096 classes, so a construction there is not ruled out by
counting.

ZTOALC L's cap and its size are one fact: every command sits on a value
of one Collatz trajectory, and a trajectory crosses each scale band a
few times, so the L-th smallest value grows exponentially in L.  The
best start under `2**22` supplies 395 lines (a sieve of every start);
dense n=10 is 311 commands on 1,477,714 lines, 14.5 -> 58.7 -> 1446
characters per entry over n=8..10 (x8.1, x49 per input), and n=11 needs
545-587 commands.  The ledger's lift, start `2**k`, is the same
placement at `2**k` lines.  Neither is language-forced: `jump if` moves
the pointer to the next line instead, and with it a program can execute
about 0.7 of its lines in one straight run -- an exact search over every
start and jump set is 28 of 36 lines at L=36 and 0.68-0.83 at every
fourth L from 8 to 44, executed on the interpreter as 28 commands on 36
lines where the trajectory placement needs 106, and a backtracking
search (20 s, most-constrained line first) reaches 205 commands on 500
lines, 379 on 1,000 and 748 on 2,000, so dense n=10's 311 commands fit
in about 850 lines against 1,477,714.  What is missing is a rule.  The
run must be a simple path in `p -> p/2 | 3p+1 | p+1`; a fixed local
rule drifts by a power of 3/2 per round and visits O(log L) lines, and
a boundary-reflected greedy (take the Collatz edge unless its landing
is used, else jump) stops when both exits are used, about L^(2/3):
2,387 commands from 100,000 lines.  No choice function of the line
alone does better: its path is the depth of line 1 in the function's
in-tree, about `sqrt(pi M / 2)` for a random mapping
(Flajolet--Odlyzko 1989), and all 4,096 residue rules mod 12 at
M=3000 top out at 138 commands, the plain trajectory's figure.  Two
facts bound any rule.  19% of the lines below M have no Collatz
predecessor (all in `(M/2, M]`), so a path spends at least that many
jumps and density is at most 0.81.  A command on line `a` forbids a
jump onto `collatz(a)`, so line `collatz(a) - 1` is another command or
an unused line; the M=200 search path chains 52 of its 88 commands
that way and wastes a line on the other 34.  A choice function that
enters every line at most once is simple by construction, but its
orbit at every root tried through M=100,000 is under 40 lines: the
mass sits in cycles.  Splicing those cycles into one path is bounded
too: a perfect path cover of the lines (every line matched, so every
cycle can be cut in) holds at most 0.18 M Collatz edges at M=500 and
0.053 M at M=5000 by exact assignment, and a cover that keeps 0.81 M
of them leaves a fifth of the lines as separate fragments that
head-absorption joins 2-79 times before it stops (best 0.276 at M=500,
under 0.13 above).  The search's density comes from choosing *which*
fifth of the Collatz edges to give up so the jumps thread the fragments
into one path, a global condition no assignment sees.  Dense paths are
found only by search.

### Execution time

Source size and execution time are separate axes.  Execution is measured for
all 65 by stepping every row and keeping the worst, out to eleven inputs,
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

The collection has 65 languages. The floor is 35: the languages that own a
generator construction, Polynomial and Modulous for their walls, and
brainfuck for Factor's decoder. The 69→65 cut removed DINAC, MyScript,
Basicfuck, and Nevermind: ordinary imperative languages with shared-shim
generators and no downstream consumer. The second band removed Suptiftam,
Lamfunc, `function x(y)`, Between, and Point Break on the same criterion,
leaving 60. Crement, Nopstacle, Vandevelo, B-tapemark, and EGL were added
afterwards, and all five raise the floor.

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
