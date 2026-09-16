# Limitations and contracts

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

Parameterized generators embed inputs in the program. `%^2^-1` cannot compute
a two-input function from runtime input. Its screened reorder requires a
permuted template or fill mapping; with both fixed, interleaving only lengthens
the identity template. Input reordering has no useful effect on Alight,
Container, Grapheme, Home Row, or Packlang; do not reopen this with a
blind search.

`scripts/screen_input_reorder.py` measures the size of permuted-table builds,
not an admissible reorder under the fixed input-template and fill contract.
Interprogck8, Dig, Flowchart, BrainIf, Sophie, and SLOW ACV MAMMALIAN must test
stream inputs in read order; BF-PDA must consume its fixed stack order. No
instruction-only wire is derived for 123, Minifuck, WII2D, or COD. ArrowQueue's
conditional re-enqueue route remains open.

| Generator | Dense | Parity | Limit |
| --- | ---: | ---: | --- |
| Polynomial | 10 | 10 | 1,934-instruction guard; dense n=11 is 124 MB and runs in 267 s. |
| WII2D | 9 | 10 | Cost policy: dense n=10 leaves a domain past the admitted 256. |
| ZTOALC L | 10 | 10 | n=11 needs 545–587 command slots; the line ceiling admits at most 395. |

WII2D n=9 is partial: 37 of 64 sampled dense tables build and the rest refuse
promptly. Its magnitude guard is load-bearing. A per-node re-embed tree can
build dense n=13, but is outside the generator contract. None of that is a
coverage gap: `proofs.md` now carries a total decode that stays inside the
contract, folding the extremal same-colour pair instead of the cheapest one.
It is refused here on cost, not reach — the extremal fold spells its centres
in unary, so the four refusing dense n=9 tables cost 0.8–1.6 MB each, and the
decode alone reaches domain 512.

Uncapped dense-program sizes at n=8/n=9: Circuit Diagram 7.91/11.39 MB,
Polynomial 3.38/10.90 MB, SLOW ACV MAMMALIAN 456/799 KB, 123 22.4/44.7 KB,
bit~ 27.5/55.3 KB, Factor 17.2/35.5 KB, ROTfuck 14.9/28.8 KB, COD
294/554 bytes. Run generated programs before claiming size or equivalence.

COD and 123 are in that list because they used to be its largest entries:
linearizing them took COD from 942,692 characters at n=8 to 294 and 123 from
94,589 to 22,988. Their sizes stayed in this paragraph, and in the test that
pins it, for every commit in between -- that test carries the `slow` marker,
so PR CI never ran it.

The retired A Painter Ant tree was Theta(T log T): on parity every subtree was
live, and each depth traversed Theta(T) weighted edges.  Its lookup strip is
linear: `ePEP` both establishes a white corridor on pass one and traverses it on
later passes, while the adjacent answer row costs at most three characters per
one entry.  The tree that remains below the crossover shares every common
prefix in one depth-first walk and prunes all-zero subtrees, which cuts a dense
n=9 head from 517348 to 19684 characters.  Input reordering leaves only 3.3% on
it at n=3 (96 of 256 tables), so it stays unwired.

123's retired wide construction used `_phase_a` with tight marks `(i+1)*2T+1`
and emits Theta(mark) movement four times for every input; their sum is Theta(T
(log T)^2).  Its replacement conditionally paints one mark per earlier prefix:
level `i` uses a span and a single separator of O(2^i), with marks and their
shadows in different residue classes modulo four.  Rows finish at `9 +
4*(T-1+bit_reverse(row))`; emitting from that closed form rather than simulating
T width-T tapes makes source and construction O(T).

COD's retired leaf cascade was Theta(T^2): each of T leaf rows contains a prefix
of length `3(k+1)` and a gate tail of length `2(T-k-1)`, so every row is
Theta(T) and rotation cannot change the number of cells.  Its replacement is
four rows wide: each parameterized input contributes its binary-weight water run
once, the resulting path stops over one of the complete strip's T baked-in
answer cells, and that cod drops through the cell to a shared border print.  The
template and filled program are both O(T).

Minifuck's retired sculpt was Theta(T^2) in the worst case: an adversarial table
fired every triangular rewind.  The replacement preloads a control strip and
uses `[x<[x<[x<[x`, which advances one cell while restoring an arbitrary tape.
Its separator, selection, and final parity sweep total O(T).

Factor is Theta(T log T) on parity under the current encoding.  The folded
Brainfuck tree has Theta(T) maximal command runs.  Each run consumes the next
prime in one of eight nonzero residue classes modulo 11; the k-th such prime has
Theta(log k) decimal digits, and the encoded integer's digit count is the sum of
those logarithms.  Run compression changes exponents, not the number of distinct
primes.  A decoder that can reuse a prime or encode runs by position is required
for linear output.

No alternate Factor generator can have O(T) output for every table.  Let D be
the decimal digit count of its integer and m the number of active prime factors,
hence decoded Brainfuck runs.  The first m primes have log-product Theta(m log
m), so m = O(D/log D).  Exponents sum to O(D); the number of their compositions
into at most m runs is `exp(O(m log(D/m))) = exp(O(D log log D/log D))`.  The
eight active residues add only `8**m`, the same subexponential order.  Thus
D-digit Factor texts decode to `2**o(D)` Brainfuck programs.  If D = O(T), they
realize `2**o(T)` functions, fewer than the `2**T` truth tables for large T.
Some tables therefore require super-linear Factor text, independent of
construction.

AddSubJump's retired decision tree was Theta(T log T) on parity.  It emitted
Theta(T) four-word instructions and a data cell per `next` edge.  A constant
fraction of those words are positive instruction or data addresses in a
Theta(T)-cell memory, so their space-separated decimal rendering uses Theta(log
T) characters each.  The packed-chunk decoder replaced it.

ArrowQueue's retired full tree was Theta(T log T): `_connect` shifted both
children three columns right at every level, and parity retains Theta(T)
occupied leaf rows through all log T levels.  Compaction removes empty rows and
columns but none of those occupied prefixes.  Its marker-count construction is
linear: input `i` contributes either zero or `2**(n-1-i)` down headings, one
right sentinel follows them, and the sentinel selects one of T constant-size
cascade stages.  The arm lengths are `1+2+4+...+T/2 = T-1`.

Bitdeque's retired tree was Theta(T log T): every parity leaf emitted `n+1`
`POP` commands and absolute `GOTO` operands.  Its head/tail discard lookup is
linear.

RAM0's retired tree had linear command count but Theta(T) absolute one-branch
targets of Theta(log T) digits.  Its straight-line RAM initializer and
unary-weight lookup are linear.

BrainIf's retired tree is Theta(T log T) on parity: it emits Theta(T) branch
`goto`s, and a constant fraction target line numbers in a Theta(T)-line program,
requiring Theta(log T) decimal digits.  Its spatial lookup is linear.

Container's retired tree has the same bound through names: Theta(T) leaf
containers are each defined and referenced a constant number of times, while
distinct identifiers over its fixed 52-letter alphabet require Theta(log T)
characters for a constant fraction of them.  Its replacement stores the reversed
table as one decimal 0/1 literal and repeatedly divides it by ten in a fixed
two-bank network.  The input weights sum to `T-1`, so source and construction
are O(T); execution time is intentionally not bounded by that source-size result
and is enormous for dense wide tables -- measured under "Execution time" below,
where the division is what makes a fourteen-command program cost Theta(T).

Three retired or current grid layouts spend one depth-width strip per table row.
Clockwise's retired flat form used Theta(T) columns across Theta(log T) active
rows; its bounded-width stack instead uses Theta(log T) columns across Theta(T)
rows.  Alternating the two compositions makes both dimensions O(sqrt(T)), hence
O(T) area.

Dig's retired two-band form left Theta(T) occupied leaf rows reaching across
Theta(log T) columns.  Its alternating-axis tree swaps dimensions at each level
and doubles each once per pair, giving O(T) area.

Flowchart's retired tree placed Theta(T) leaves on fixed pitch and drew one
Theta(T)-wide selector level per input.  Its five-row deque layout is linear: it
preloads T answers, then its two arms discard opposite halves; setting the arms
to 1/0 before a shared switch makes both incoming headings leave east.

Circuit Diagram's H-layout quarters its minterm tree every two inputs.  Its side
recurrence is `S(n) = 2*S(n-2) + O(n) = O(sqrt(T))`, so its rendered area is
O(T); routing records at most one horizontal and one vertical signal per cell
and tries a fixed local catalogue, keeping construction linear too.

Inject's and Jaune's retired trees are Theta(T log T) on parity because both
assign a distinct label to every tree branch or leaf.  Inject emits each of
Theta(T) labels twice from a fixed 52-letter alphabet, so a constant fraction
have Theta(log T) characters.  Jaune emitted Theta(T) numeric labels and jump
operands, likewise with Theta(log T) decimal width for a constant fraction.
Jaune's spatial table now uses two labels.  Inject's single table block is
halved by O(log T) conditional regex substitutions whose literal text totals
O(T).

LaserFuck's and Streetcode's retired trees use Theta(T) rows whose live paths
extend across Theta(log T) level columns on parity; trimming removes only suffix
blanks.  LaserFuck now conditionally walks arms of total length `T-1`, selects
one of T prewritten cells, then cleans all cells in one sweep.  Streetcode's
alternating-axis H-tree fits its two-wide roads in O(T) area.

Vandevelo's retired spelling emitted one depth-`n` guard chain for each of
Theta(T) selected rows, hence Theta(T log T).

Its replacement peels the 1-set by affine cubes.  Every value a Vandevelo
program can bind is affine in the inputs and only `::` chains evaluate
conditionally, so a program's hang-set is exactly a union of affine cosets,
and the generator emits one guard line per coset of a cover.
[Cohen--Shinkar][dnf-parities] bound the peel at `1 + 9T/log2(T)` clauses, so
guard parts total O(T); while the remainder is dense a capped candidate scan
that misses the pigeonhole average falls back to an exact Walsh--Hadamard
autocorrelation, which is what makes that a bound rather than a heuristic.
Reduced elimination keeps every constraint at most `dim+1` inputs wide.

What is not proven O(T) is register upkeep: spelling those constraints costs
`O(T log log T)` worst case, measured under half the emitted text.  Dense
random tables hold 8.1--8.9 characters per entry flat across n=8..12 (9,397
at n=10 against the retired 36,829) and parity is one hyperplane, 259 against
52,821.  No matching lower bound: random tables admit no monochromatic cube
above dimension `log2(n) + log2(log2(n)) + O(1)`, which forces only
`Omega(T / log n)` guard parts, so the upkeep gap is open in both
directions.

[dnf-parities]: https://eccc.weizmann.ac.il/report/2014/099/

S*bleq's retired tree emitted Theta(T) instructions and data triples with
absolute decimal addresses into a Theta(T)-cell memory, so a constant fraction
of its operands had Theta(log T) digits.  Its packed-chunk decoder is linear.

SLOW ACV MAMMALIAN's retired tree was super-linear even though its measured
ratio was close to two: for a child cap `C`, `_widths` reserved a trampoline
slot of Omega(C/255) and `_subtree` emitted that whole slot plus two
children, so `S(d) >= (2 + 1/255) S(d-1)`.  The recurrence was never forced
by the language -- the shipped construction reads all n inputs in one chain,
banks each 1-bit as a 256-multiple weight on a side array's non-head sum,
and lands one final trampoline at `nonhead + b = leaf_base + row * 256` in a
flat table of 256-token leaves, which is O(T) text and build (456 KB against
the tree's 1.67 MB at dense n=8; per-entry cost falls toward the slot
floor).  What made the chain possible where the tree forked is that every
other divergence between the branch paths cancels before they merge: both
leave through trampolines aimed at the same address, so the post-jump
non-head sums are equal by the jump identity itself, and a one-chunk tuning
byte zeroes the (always even) head residue at slope -2.

A **pump-loop** lane was researched first and is retired; its negative
results priced the loop route out.  The loop itself worked -- a fixed
~20-token body raising an address by thousands for O(1) text, with the
address-space fault repaired by settling every address against exact dry
runs -- and built and executed n=1/2/3 completely.  But its measured reach
law is affine (~10,000 per counted round, ratio falling to `R/(R-1)`), so a
counted exit spells each node's climb in unary counter cells and the climbs
sum to Theta(T log T); fixed nesting only trades the exponent (`L` levels
leave `C = Theta(span^(1/L))`), per-entry cost at n=3 was ~200x the tree's,
and no cheap value-triggered exit exists in the instruction set.  One
warning from that lane still binds every construction here: correctness is
address-sensitive -- a variant build once passed every builder-side check
and failed one row with empty output -- so a build only counts once its
rows have executed.

What made that lane's cost legible is that a SLOW ACV program's emitted
size is its **address space, not its laid text**: `generate` renders
`" ".join(b.text.get(i, "SEED") for i in range(max(b.text) + 1))`, so every
address the construction never writes still ships a literal `SEED`.  From
n=1 to n=2 the written cells grow x1.939 -- slower than linear -- while the
unwritten gaps grow x3.410 and carry the span to x2.112 and the emitted
characters to x2.142.  The gaps, not the text, are the super-linear term,
and they are paid per tree node: every one sits immediately below a
`subtree` node, and the count tracks the node count.  `SEED` is what a
padded address renders as, which is why it reaches 91.5% of the program at
n=3 while growing x6.87.  The counter compounds it, because `generate`
doubles `CCELLS` on reach exhaustion: 60 at n<=2 but 240 at n=3, so the
march is `Theta(T * CCELLS)` rather than one constant per node.  That
doubling is also a trap for short sweeps -- per-entry cost moves x1.993
from n=1 to n=2, which reads as linear, then x5.342 to n=3.

Attribute that cost from the **artifact, not the call graph**.  Three
attempts to instrument the builder all misreported it: first by id reuse,
then by an undercount that charged 131 tokens against a ~400k-token
program, and finally by an instance-keyed pass that showed laid tokens flat
between arities while the program more than doubled.  The reads that worked
-- span, token census, gap census -- take the emitted string and count.
The growth is in how many gadgets run, not how large one is.

Polynomial's current expanded-root encoding is super-linear, and its
instruction count is language-forced even though its text is not.  The input
instruction *overwrites* the register, so between reads every bit about
earlier inputs lives in the cursor alone: just before the k-th read the
reachable configurations number at most twice the instruction count, and a
maximal-width table needs Omega(T/log T) residual classes under every read
order.  Every Polynomial program for such a table therefore carries
`m = Omega(T/log T)` instructions whatever its operands -- the older argument
below covered only the tree/machine splits used here.

That cursor-only step is sound here, unlike the one it resembles under
Interprogck8, and the difference is worth keeping: a Polynomial state is
exactly `(register, cursor)`, the input arm assigns the register rather than
combining with it, and the instruction list is recovered once and never
rewritten -- the language has no slot, no call stack and no `z`.  So here the
cursor really is the only channel.

The text is a different matter, and two of the escapes are now measured.
Negative operands are **legal**: `convert` puts no sign condition on a complex
root's real part, and `f(x) = 1x^6-130x^5+3563x^4+41030x^3+255186x^2+
1107000x^1+4168400` decodes to `[[70, 1], [-5, 1], [0, 1]]` and prints `A`.  A complex instruction `[a, b]` is
`(x-a)^2 + p**(2b)`, so its linear coefficient `-2a` flips sign with `a`, and
that program's own expansion is already not alternating.  The builder was long described here as
encoding negative arithmetic by changing the opcode, its monic factors all
sign-alternating so that products preserve the pattern without cancellation
and give Omega(m^2) total coefficient digits.  That premise is FALSE at
n >= 4: the shipped dense builds carry a few negative operands -- 0/36,
1/70, 4/117, 6/187 complex instructions at n = 3..6, operands -1..-3, all
at b = 3 -- so the builder-specific
argument did not actually cover those builds.  The right-half-plane
theorem below, with its compensation lemma, both repairs that hole and
extends the bound to every cofactor on half the plane; the free parameters
left over are roots with substantially negative real part.

That free parameter is now measured, and it is close to empty.  Over prefixes of a real dense build (the
k=0 machine on the contract's dense n=6 fixture, 187 instructions), total
rendered digits are minimised over the complex operands' sign patterns --
exhaustively to 12 signs, first-improvement hill-climbing from random
restarts above, the two compared wherever both run (one exhaustive minimum
was missed, by 0.4%).  The best pattern saves at most 5.2% anywhere
measured, the saving *shrinks* as `m` grows -- ratio 0.96 at m=4 to 0.998
at m=40 on the built operands -- and the fitted growth exponent does not
move: 2.35 all-positive against 2.37 minimised, and 2.12 against 2.14 with
the built operands replaced by large free offsets (`|a| ~ 2^10..2^12`),
the regime where the operand-carrying terms own the digit mass and
cancellation has the most to bite.  One exact fact says why the family is
this barren: a factor's squared modulus at `x = iy` is
`(q + a^2 - y^2)^2 + 4a^2y^2`, a function of `a^2` alone, and moduli
multiply -- so `|F(iy)|` is *identical* under every sign pattern on the
whole imaginary axis (verified in exact integer arithmetic), and whatever
a sign choice cancels must be invisible there.  A census over two operand
regimes and a local search, not a proof.

The other escape is closed.  Shipping the *product* form -- `m` factors at
`O(log)` characters each, no expansion -- is not a legal encoding: the parser
strips `*` and reads only summed `c*x^d` monomials, keeping the last
coefficient per degree, so `f(x) = (x-2)(x-3)(x-5)` is silently read as
`x - 5` rather than rejected.  Program text
is the expanded coefficient digits and nothing else, which is what the bound
above prices.  Polynomial remains open alongside the other construction
walls.

Extra roots that do not match an instruction code multiply the mandatory
root product without changing execution -- executed, not assumed: `P*(x^2+x+1)` and `P*(x-6)` both decode
to the base program and run identically, on the three-instruction `'A'`
printer and on `polynomial("0110")` over all four rows, while the control
`P*(x-2)` -- whose root is the instruction code `2**1` -- decodes to a
different program and dies on an unmatched bracket.  So a multiple is
legal exactly when every cofactor root dodges the instruction encodings,
and the escape is narrow.  No
two-term multiple exists at all: `x^N - D` vanishing on `a + p**b i` forces
`(z/conj(z))**N = 1`, a rational angle, and Niven's theorem then pins `a` to
0 or `p**b`; even then two factors need `2*p1**(2*b1) = 2*p2**(2*b2)`, which
distinct primes cannot satisfy.  A t-term multiple imposes `2m` vanishing
conditions on its `2t` coefficients and exponents, so `t = Omega(m)`, and
every multiple already spends `Omega(m log m)` digits on its lowest nonzero
coefficient, which the product of the mandatory primes squared divides.
Known rational sparse-multiple algorithms are exponential in the requested
sparsity, `Theta(T/log T)` here.  What remains open is exactly a non-generic
O(T)-digit family for these prime-power roots -- and note the `t = Omega(m)`
above is a dimension count, a necessary condition on a generic solution
rather than an impossibility proof, so it bounds no specific family and does
not by itself forbid a sparser one.

For the real-rooted part that count is now a theorem.  A multiple keeps every root of the
mandatory product, the real instructions contribute `m_r` distinct
positive real roots `p**v`, and Descartes' rule caps a `t`-term real
polynomial's positive roots at its sign changes, at most `t - 1` -- so
*every* multiple of a product carrying `m_r` real factors has
`t >= m_r + 1` terms, whatever the cofactor.  The shipped machines make
that `Omega(m)`: an if/endif pair per state puts the real share at
0.32..0.36 of the instruction list (measured n=3..6), and the expanded
builds' sign changes sit at or above `m_r` as the rule requires, on the
builds and on shape-dodging multiples.  Two limits keep it from
separating.  It is the matching bound arrived at a third way --
`Omega(m)` terms already cost `Omega(m log m)` exponent digits, and a
`Theta(m)`-term multiple with small coefficients would still be O(T)
text.  And it covers only programs that carry real instructions at all.

A program cannot shed them: the routing lemma that was the named gap
here is now a proof.  A read *overwrites*
the register, so after the k-th read the future behaviour is a function
of the read instruction's position alone; between reads every
non-bracket instruction has one successor and every bracket has two,
fixed by its partner.  So a destination reached through at least one
bracket is determined by the last bracket passed and the way it went --
at most `2B` values for `B` real instructions -- while a bracket-free
segment reaches one destination for both bit values, which a correct
program can afford only where the state's two children are the same
subfunction (same position, same future map).  Non-constant
level-`(k+1)` subfunctions must land on distinct read positions, so
`N'(k+1) <= 2B + E(k)`, i.e. `B >= (N'(k+1) - E(k))/2` at every `k`,
with `N'` the non-constant subfunction count per level and `E(k)` the
non-constant level-`k` states whose halves are equal -- a floor that is
a property of the table, and `Theta(T/log T)` on dense ones.  Both
halves execute: on machine- and tree-shaped builds at n=3..5, over every
input, every inter-read destination is the recorded function of its last
bracket and outcome and every bracket-free segment is bit-blind; and the
floor computed from the dense fixture runs 16, 52, 128 at n=8, 10, 12 --
0.38..0.53 of `T/log2 T` throughout, under the shipped machines' actual
real counts as it must be.  A loop changes nothing, and
the mechanism runs through the
interpreter: entries 7 and 10 leave `while (reg > 0) reg -= 3` with
identical state while 7, 8 and 9 leave it pairwise distinguishable --
an exit that depends on the register merges a whole residue class into
one configuration, so the quotient a dispatch would need is destroyed
rather than stored.

Together with Descartes this makes the matching bound language-level:
every multiple of every program for a dense table -- under the standing
convention that each path reads its `n` bits -- carries
`Omega(T/log T)` monomials and therefore `Omega(T)` characters, with no
assumption left about which construction wrote it.  What it still is
not is a full separation: the floor prices exponents, not coefficient
mass, and coefficient mass is where the remaining freedom lives.

Coefficient mass is now priced too, on half the complex plane.  If every root of a program polynomial
has nonnegative real part -- every complex operand `a >= 0` and every
cofactor root in the closed right half-plane -- then substituting
`x -> -x` gives each real factor nonnegative coefficients (`(x - r)`
becomes `-(x + r)`; `(x - a)^2 + q` becomes `x^2 + 2ax + (a^2 + q)`), and
a product of nonnegative-coefficient polynomials cannot cancel.  The
coefficient of `x^k` is then at least the single selection in which the
`k` smallest-constant linear factors contribute their `x` and every other
factor its constant term: `|[x^k] F| >= (prod of all constant terms) /
(c_1 ... c_k)` exactly, checked coefficient-by-coefficient in integers on
the emitted artifacts and on executed right-half-plane multiples.
Summing `k = 0..L` gives at least `(L+1) M / 2` total digit mass, where
`L` counts linear factors and `M` is the log of the product of all
constant terms.  Both are language-forced: the routing floor makes the
real (bracket) count `Omega(T/log T)`, a multiple keeps every mandatory
root, and the mandatory real constants are at least their distinct
primes, so `M = Omega(m_r log m_r)`.  Hence **every right-half-plane
program for a dense table is `Omega(T^2/log T)`** -- superlinear,
whatever the cofactor.  A compensation lemma stretches it past the
axis: a flipped quadratic with negative middle `x^2 - 2bx + c` times an
unused nonnegative one `x^2 + 2b'x + c'` is coefficientwise nonnegative
iff `b' >= b`, `c + c' >= 4bb'` and `b'c >= bc'`, and pairing leaves the
selection bound and the floor formula unchanged -- which is what covers
the shipped builds' few `a = -1..-3` operands (middles at most 6 against
constants at least 65; the matching is found and verified per build).
Unlike Mahler measure, the primorial divisibility, or
the Newton polygons -- norm and divisibility bounds that one heavy
coefficient can absorb -- positivity forces every low coefficient at
once, which is why this crosses the linear matching bound where those
could not.  The hypothesis is load-bearing:
`(x-2)(x-3)(x+2)(x+3) = x^4 - 13x^2 + 36` has `[x^1] = 0` where the
as-if-right-half-plane floor demands 18, so one left-half-plane pair per
magnitude zeroes a coefficient the theorem would force.  A linear-size
program must therefore put roots with negative real part to work, in
force enough to defeat every compensation matching: negative complex
operands (legal, and measured near-empty for sign flips of real builds
above) or left-half-plane cofactor roots (the executed legal multiple
`x^2 + x + 1` is mildly one; its mass still sits above the
right-half-plane floor, measured not proved).  The one cofactor family
with *exact* magnitude matches -- the counterexample's own move, one
negated partner `x + p**v` per real instruction root, legal because
`convert` reads real roots only as positive prime powers, and executed
(decode and output identical on a five-instruction printer) -- is priced,
and it is mass-negative: it zeroes every odd coefficient of the realified
part while each survivor roughly squares, total digit mass x1.51..1.58 on
the dense n=3..6 builds and strictly monotone in the partners added,
24/24 at n=4.  The toy above saves only
against `(x-2)^2(x-3)^2`, a multiple nothing forces; against the program
`(x-2)(x-3)` itself the mirror is strictly more text.  So exact
magnitude matching cancels coefficients without moving mass, and a
working left-half-plane cofactor needs inexact magnitude relations.  The
LLL sweep below never
searched that region for cancellation, so the sparse-multiple question is
now exactly a left-half-plane question.

The one routine route to an *unrestricted* bound -- forcing compensation
partners from the semantics -- is closed, negatively
(executed).  The op selector is the
imaginary exponent, so additive negatives are rewritable (`[-c, 1]` is
`[c, 2]` -- the builder's opcode swap), but `[-c, 3]` (reg *= -c) matches
no single nonnegative-operand register map, so sector arithmetic is
semantically real; and a bracket that never fires guards dead code, so a
program can carry arbitrarily many negative-operand instructions against
the routing floor's `Omega(T/log T)` linears -- the padded printer runs
identically with more negatives than linears.  No pairing rule can
therefore be forced language-level, and the positivity method's sector
boundary is final: the unrestricted statement stands or falls with the
open sparse-multiple problem, pinned to programs whose arithmetic mass
sits in the open 90..135-degree sector with too few compensators.

The generic corner of that family is searched, and empty.  The integer multiples of `P` with
cofactor degree at most `k` are exactly the lattice spanned by the shifts
`x^i * P`, so one LLL reduction searches every such multiple at once for a
short member.  On prefixes of the same real dense build (degree to 40)
with `k` from 1 up to the degree, the reduction returns the trivial shifts
*unchanged* -- every reduced row is `±x^i * P` -- so at `delta = 0.75`
nothing in the family renders even one digit shorter than `P` itself.
Bounded three ways: prefix size, cofactor degree, and the l2 objective LLL
minimises, which an unbalanced small-digit multiple could evade.  It
bounds the search rather than closing it, but a sparse multiple, if one
exists, is not hiding at small cofactor degree.

The l2 objective's blind spot is searched now too, and it is also empty.  A linear-size program cannot be l2-short
-- its lowest coefficient is primorial-forced, so its profile is one
heavy bottom coefficient and small everything else, the shape l2
penalizes most.  Scaling column `j` of the shift lattice by
`2^(s0 - s_j)` for a target bit envelope `s` makes the reduction hunt
exactly that unbalanced profile; with the constant term left free and a
flat or tapering budget elsewhere, every searched case over prefixes to
degree 40 and cofactor degree to 8 returns gain 1.000 or worse, the
control envelope (P's own profile) returns the trivial shifts, and the
unstable cases -- sympy's pure-Python LLL loses its bookkeeping on very
wide scaled entries -- are reported as unsearched rather than clean.
Bounded by prefix size, cofactor degree, and the envelope family, as its
predecessor was by the l2 objective.

The obvious *language-level* lower bound also comes out linear, which is
worth stating because it says which way this row can close.  Any valid
program is divisible by the product of its `m` mandatory instruction
factors, and each factor's constant term is at least its prime -- `p**v`
for a real instruction, `a**2 + p**(2b) >= p**2` for a complex one -- so
the polynomial's lowest nonzero coefficient is divisible by the primorial
of `m` and carries `theta(p_m)/ln 10 = Omega(m log m)` digits.  With
`m = Omega(T/log T)` that is `Omega(T)` digits: computed over `n = 6..20`
with `m = T/log2 T`, the forced digit count divided by `T` runs 0.153,
0.180, 0.198, 0.206, 0.220, ... 0.267, creeping toward `ln 2 / ln 10 =
0.301` rather than growing.  So the mandatory primes force a *linear*
amount of text and nothing more.  That is a matching bound, not a
separating one, and it cannot be promoted into a proof of super-linearity
no matter how it is sharpened.  Any language-level proof therefore has to
come from the *other* coefficients -- which is exactly what the
right-half-plane theorem above now does for half the plane, and why
ruling out a left-half-plane multiple is the whole remaining question.
On current evidence this row closes by a construction that exploits
negative real parts, or not at all.

One natural way to promote the two-term argument does *not* work, which is
worth recording so it is not retried.  That argument succeeds because a
two-term multiple forces every root to share one modulus, which distinct
primes cannot do.  The tempting generalisation -- a `t`-term polynomial's
roots take at most `t-1` distinct moduli, via Newton-polygon segments -- is
false: `x^3 - 7x + 6` is `(x-1)(x-2)(x+3)`, three terms and three distinct
moduli.  Sparsity bounds real positive roots by Descartes, but it does not
bound complex root moduli at all (`x^N - 1` has `N` roots on one circle from
two terms), so the modulus route cannot reach `t = Omega(m)`.

What remains is not merely unsolved here; it instantiates a problem the
literature poses and leaves open, and every published case misses it.  [Giesbrecht, Roche and
Tilak][sparse-multiples] (Algorithmica 64:454-480, 2012) is the standing
work on computing sparse multiples, and its rational results are exactly
two: an unconditional algorithm for *binomial* multiples `x^m - a` --
the `t = 2` case Niven's theorem closes for these roots above -- and,
for each *fixed* `t >= 3`, an algorithm needing an a priori height bound
on the output and an input free of repeated cyclotomic factors.  The
caveat is not what excludes the mandatory products: they are
cyclotomic-free, since a cyclotomic root sits on the unit circle while
every instruction root has squared modulus at least 4 (measured 58 at
its smallest over the dense n=3..6 builds).  What excludes them is the
sparsity itself.  Spelling `t` distinct exponents alone costs
`Omega(t log t)` characters, so O(T) text forces `t = O(T/log T)`, and
the Descartes-plus-routing floor forces `t = Omega(T/log T)` -- the
multiple the row needs has `t = Theta(T/log T)`, growing with the
degree.  That is the case the paper's conclusion singles out, verbatim:
"Removing these restrictions is desirable (though not necessarily
possible)", and "we suspect that computing t-sparse multiples is
NP-complete over both Q and F_q, when t is a parameter in the input".
Roche's 2018 survey ([arXiv:1807.08289][sparse-survey]) adds nothing on
multiples and leaves the neighbouring sparse-division and
divisibility-testing questions as its Open Problems 2 and 3.  So no
published result decides this row in either direction -- and since even
the conjectured NP-completeness would not forbid a bespoke family for
these specific prime-power roots, the row stays open rather than
closing as a wall.

[sparse-multiples]: https://arxiv.org/abs/1009.3214
[sparse-survey]: https://arxiv.org/abs/1807.08289

Interprogck8's audit row closed Sep 2026 by construction.  The express
router shipped until then was super-linear, and measurably so rather than as
an artefact of the two-step statistic -- parity per-entry cost climbed
monotonically from 328 to 526 characters over n=3..10, and `DownAccLines`
per entry rose by a near-constant +0.7 an arity, the signature of `a + b*n`
-- where its replacement is flat: per-entry cost oscillates between 805
and 887 characters over n=8..12 on parity with no trend, every row of
every build executed, and the registry scaling contract reads x1.963
against its x2.15 bound with no exemption.  The replacement is the shared corridor the closing
paragraph of this section describes; everything between here and there
prices the *retired* router and the language's state channels, and those
pricings stand -- they are the map of which channels a still-cheaper
construction could and could not use.

A decision diagram is **not** forced, and the paragraph that claimed it was
is retracted.  The accumulator does die at every read -- `u` loads the byte
and `{values/=a/=b/=c}` overwrites it with 84 or 81 -- but it is not the only
state, and the pointer is not the only thing that crosses a read.  Three
other channels do, each executed:

- The **function slot**.  `u` does not touch it, and `<` captures the body
  the pointer is standing on, so two inputs can reach *one* line holding
  different bodies.  The probe's two arms meet at line 301 carrying the
  same accumulator -- 0, normalised on arrival on purpose, so the slot is
  the only thing that differs -- and the same `EXE` prints `A` or `B`.
  Stepped rather than inferred: the pointer and the accumulator are read
  off the state at the call.
- The **call stack**.  A read taken inside a body returns into that body,
  and `IFT`/`IFQ` make the push itself conditional.  Priced below.
- The **program text**, through `z`.  A restart clears the accumulator, the
  slot and the pointer but *not* the input cursor, so
  `["u", "div"] + ["X", "z"] * 3` reads and prints four bytes at two lines
  of text per iteration -- a loop whose memory is the text.

So "one distinct position per residual function" does not follow: after k
reads the residual class is carried by the pointer *and* the slot *and* the
frames *and* the text, and a product of channels needs far fewer positions
than a diagram over positions alone.  The packed-table closure loses the
same premise -- `z` accumulates input history into the text whatever the
accumulator does -- though its second half still stands on its own: on a
computed jump the landing accumulator *is* the index, and the language has
no one-line no-op to cancel it with.

What is unmoved is the information floor: a random table is `T` bits and the
alphabet is `O(1)`, so `Omega(T)` characters are needed regardless.  That
floor is linear, so it does not order this row either way.

Routing *the tree the generator emits* is what costs the log factor.  Every
bound from here down is therefore about that construction, not about the
language: it takes the tree as given, and the paragraph above is why that is
now an assumption rather than a theorem.  The first attempt at saying why was
wrong in a way worth keeping: it claimed relay rungs cannot be shared between
chains with distinct targets.  A rung is a bare `DownAccLines`,
which is stateless -- two chains may land on the same line carrying different
accumulators, and each flies its own stride.  Rungs *are* shareable, and what
matters is the union of the chains' waypoints rather than the sum.

Sharing is nonetheless bounded for any chain that needs *dedicated* rungs,
because it cannot *persist*.  A stride of at most one reach forces
every chain to land at least once in each 256-line window it crosses.  Suppose
two chains share one rung in every window.  Then their consecutive landings are
the same fixed distance apart, so they carry the same stride; being at one
position with one accumulator, they have one future, and so they cannot end at
different targets.  Chains with distinct targets therefore need distinct rung
lines in all but a bounded number of the windows they cross -- two progressions
with different steps meet only every `lcm` of them.  Dismounting has the same
shape: a chain stops only by landing on a line that is not a rung, and changing
stride mid-flight takes an adjuster, which every other chain landing there
would also execute.

That gives the bound the shipped construction runs into.  The far arms have
pairwise distinct targets, the number of them crossing a given position is the
layout's cutwidth, and the sum of that over all positions is the tree's total
edge span.  So the dead lines needed are `Omega(Sum span / 256)`, short edges
contribute only `O(T)` of that sum, and for a complete binary tree the total is
`Theta(N log N)` in any linear arrangement -- `Omega(T log T)` rungs.

That last step is computed rather than cited.  For any layout the total edge
span equals the sum over the `N-1` cut positions of the edges crossing each,
and a cut leaving a part of size `i` crosses at least `mincut(i)` edges, which
is an exact tree DP and mentions no layout.  Summing it bounds every
arrangement at once.  On complete binary trees, `sum mincut(i)` divided by `N`
runs 1.14, 1.47, 1.81, 2.13, 2.43, 2.74, 3.04, 3.34, 3.65, 3.95 for heights 2
through 11 -- a constant `~0.30` per height, so linear in `log N`, holding at
`~0.33 N log2 N`.  It is a lower bound over arrangements, so no cleverer
*layout* of this tree is hiding; a construction that is not this tree is not
covered by it at all.

The one thing that remains a judgement is where the log starts to bite, because
short edges are free and `255` lines is a lot of tree when a node is small.
Spans are in nodes, so a node costing `w` lines makes edges under `255/w` nodes
free, and the long part only dominates past height `~0.3^-1 * 255/w`.  At the
shipped `w` of about 110 lines a node that is height 8, which is why this shows
up in the measured range at all; at a `w` near the gadget's own 16 lines it
would be past height 50.  A slimmer construction would therefore *measure*
linear across every arity anyone can run while still being `Theta(T log T)`,
which is worth saying out loud: the contract passing would not mean this
paragraph was wrong.

None of which closes the row, and the gap is worth naming precisely because it
is the one an attempt should aim at.  Everything above prices *dedicated*
rungs, and a chain does not need one: its landing only has to be a
`DownAccLines`, which then flies that chain's own accumulator and lets it go
on.  The program is already dense with them -- about twelve a table entry --
so the supply is the whole program rather than the meadows, and "distinct dead
lines per window" does not follow from "distinct rungs per window".  Whether
`Theta(T)` chains can be given strides and alignments whose arithmetic
progressions land only on jumps that already exist is a packing question --
now measured on real artifacts, and the free supply does not close it.  A chain flies a progression of step `1 + acc`,
so a hop of span `S` at stride `d` needs its `S/d - 1` interior landings to
be `DownAccLines` already.  The lines are there -- 9.7% to 10.8% of the
program at n=8 and n=10, dense and parity, matching the ~12 an entry quoted
above -- but they are not *aligned*.  Free-riding carries a median of 552 to
597 lines from a start against 256 for a single hop, every successful ride
used two hops (a handful used four), and over 300 sampled hops per case a
span of 2000 or 10000 free-rode 0 times.  The observed rates track what
independent placement at that density predicts -- 12.7% against 9.8%, 11.3%
against 10.1%, 12.3% against 10.9% at span 500 -- so there is no hidden
structure to exploit: a `k`-hop ride costs `rho**(k-1)`, which decays
exponentially in the span.  Both controls fire (a full lattice reaches
999/999 targets, a rung-free program 0/700).

That leaves deliberate alignment as the only route, and it runs straight
into the persistence argument above: rungs placed on a shared lattice give
a shared stride, and a shared stride is one future.  So the narrow gap is
narrower than it looked, though still not shut -- these are the *shipped*
layout's jumps, and a construction that positions its own could do better.

One objection to a deliberate lattice is now removed, which is worth
recording because it was the easy half.  The reason a lattice cannot simply
be threaded through the region that *computes* the answer is that the
accumulator is nonzero there, so every rung fires and corrupts the result.
But `DownAccLines` advances by `acc + 1`, so a rung followed by `k` nops is
**transparent** for every `acc` in `[0, k]`: each value lands somewhere
inside the nop run, all paths converge on the line after it, and none of
them touches the accumulator.  Executed, with a control where a rung
followed by an effect does move the accumulator.  The same probe runs the natural answer phase -- enter a table
of `table[j] - table[j+1]` differences at row `r` and fall through, so the
sum telescopes to `table[r]`, biased by one to keep it in `[0, 2]` -- with
a transparent rung every four lines, and it returns the right bit for every
row of four tables up to sixteen entries.  So navigation lines and answer
lines can share the same region.  What that does *not* solve is
dismounting: a chain riding a regular lattice leaves it only on a non-rung
or an adjuster, and both are seen by every chain that lands there.
Corruption was the easy half; one future is still the hard one.

That is the narrow gap.  The wide one is the retraction above: the tree is an
assumption, so a construction that is not a decision diagram over positions
pays none of this.  Two aim-points fell out, both refutable, and both are now
resolved.  The slot gives a *product* -- `P` positions times `C` captured
bodies reach `P*C` residual classes for `P+C` routing text.  A body cannot
branch on the accumulator the position tree hands it (`DownAccLines` is
rejected inside a body, and `{values}` consumes the accumulator on its first
test, so a body distinguishes one value of `j` and no more) -- but that blocks
one direction only, and the other direction *works*: a captured body writes
the accumulator, frames pop eagerly, so a `DownAccLines` placed right after
`EXE` executes frame-free with the body's value and fans one shared position
out on body identity.  Executed end to end: an
n=4 generator routes two bits into one of four captured bodies, converges,
routes the other two bits into one of four `EXE` blocks, and all 16 rows of
an arbitrary table print correctly through `P+C` routing text and `P*C`
landing cells.

The meet exists; what the same file then prices is the strides.  Two more
executed facts.  `[v v]` with equal dice literals is a *deterministic*
accumulator load with no 255 cap -- a body loading 298 flies a single
298-line hop -- but the line costs about `v` characters (two dice literals
of `v/2` colons), so reach stays char-priced at `Theta(span)` and the rung
economics above stand.  And bodies are pairwise disjoint text: `<` scans to
the next `>` and raises on a second `<`, so a body can never contain one and
no two live bodies share a line.  The price follows for any build of this
shape.  `C` bodies must set `C` distinct strides; arithmetic wraps at 255,
so past that only the literal remains and their total cost is `Omega(C^2)`
characters, while the position router still resolves `log2 P` bits across a
landing region of `Omega(T)` lines -- the same per-level span sum the
arrangement bound above prices, `Omega(T log P)` characters.  Under any
`O(T*f)` character budget the body term forces `C = O(sqrt(T*f))`, hence
`log P >= (log T - log f)/2`: the log survives every `P*C` split, and the
product's best case is halving its coefficient.  The slot channel meets but
cannot linearize.

The `z` loop was the other, and it is closed, negatively
(four executed facts, on top of two more: a read is invisible
across a restart, and input reaches the text only by steering which `z`
fires).  One gadget at the top does read a fresh bit on every pass -- that
half of the shape works.  What kills the route is that **the read never
retires**.  A firing deletes only the `z` and its adjacent predecessor, and
the nearest steerable site is a flight below the `u`, so no steer reaches
its own read; and every pass's route is identical to the previous pass's
until the first read or the first text difference, both of which sit at or
below the read, so once the input-independent burns above it are spent,
every restart re-executes it.  Each post-burn pass therefore consumes an
input line -- at most `n` of them, and the first restart after the input is
spent dies at the `u` -- and each fires one two-line pair, so the whole
input-dependent positional range of the text channel is `2n` lines, not
`T`.  The reading passes are also consecutive and terminal: the route from
line 0 to the read is untouched by any steered deletion (all of them lie
forward of the read), so once one pass reads, every later pass does, and
the run must end during the n-th -- the blind passes that could compute at
scale all come before the first read, where they are input-independent.
In the natural comb -- both arms landing directly on `z`s, which the
one-line accumulator spread makes adjacent -- the record decays too: a
0-bit's pair takes the line above the landing frontier, where the previous
record sits, and inputs `00x` and `10x` leave identical text.  Spreading
the arms through relays dodges the decay but not the rest: one arm's `z`
still survives unfired as a live `z`, and a later walk that touches it
restarts and dies at the read, so a readback may only visit a site whose
bit it already knows -- the positional decision tree the arrangement bound
above already prices.  What `z` buys is `n` restarts and `n` fragile local
sites; with the slot product priced above and the `z` loop closed here, the
one channel left is the call stack, priced next.  (A
handoff note's contrary verdict -- `T/2` passes writing `T` bits -- is
withdrawn there: it needed
input-dependent passes after the reads, which the paragraph above rules
out.)

The call stack now carries the same verdict
(five executed facts).  `IFT`/`IFQ` are
conditional calls -- a data-dependent push with no positional divergence
-- so the frames are a real second store.  What crosses a read inside one
episode (one capture, one body: a body can never contain `<`) is exactly
two things.  The accumulator keeps one *absorbing* bit:
`{values/=u/=/=c}` compares the byte against the incoming accumulator,
and the enumeration over every read form shows each maps 256 incoming
values onto at most two outgoing ones with no swap anywhere -- so an
equality chain threads an AND through the reads (a 52-line NOR at n=6
executes) but never a counter or a parity.  And the stack keeps push
counts: a one-site descent body exits with the accumulator at 82 plus
the count of leading zeros -- the meet again, multi-bit information
crossing reads on frames alone.  The readback is what collapses.  A call
re-runs the whole body from its first line, so every push spends the
body's reads: a body that pushes on both bit values recurses on every
input and dies at EOF (all 16 at n=4); a one-value pusher cannot read
past its stop bit (reads consumed is exactly `lz+1`, executed); and
arming the unwind -- marginal text that can wrap the accumulator back to
a firing value -- makes the resumed site spend a read that is no longer
there (the armed twin dies on the input its disarmed twin exits cleanly,
and the raise itself reports three reads of a two-line input).  Unarmed
unwinds are therefore straight-line arithmetic, the same marginal text
at every depth, so an episode's exit accumulator is an affine tally of
per-site pop counts mod 256 plus the last read: order-blind, eight bits,
and a random table is not an affine functional of its bits.  Episodes
can only feed 8-bit exits to top-level routing, every input-dependent
stride still wraps below 256, and the span sum above prices the rest.
With that, every field of the state is priced or closed: `lines` (`z`,
retired), `slot` (the product above), `frames` (here), the accumulator
(eight bits, one absorbing thread), and the pointer (the arrangement
bound).  None of it is a language-level lower bound -- the affine-exit
step is scoped to unarmed episode shapes the way the slot price is
scoped to stride-coded bodies -- and with the corridor shipped none of
it needs to be: the row closed on the other side.

Two families of long jumps contributed.  The bit-0 arm spanned its sibling
subtree, with pairwise distinct targets -- the family the obstruction bites
on -- and the exit ladder was the easy one, removable for a third of the
program (526 to 352 an entry at n=10) while leaving the construction
super-linear.

What closed the row is the corridor construction, which pays the
persistence bound nothing because it owns no dedicated rungs at all.
Every odd line nothing occupies is a bare `DownAccLines`, so "distinct
rung lines per window" is free: the union of every chain's waypoints is
the corridor itself, half the program, paid once.  The one-future wall
assumed a shared lattice forces a shared future, and it fails twice over.
Chains at one stride with different positions fly translated landing
sets, so position alone separates them; and the input picks dismount
against flight with no adjuster anyone shares -- `u` then two `@dd`
leave 28 or 29, a rung flies `1 + acc`, so from an odd line an even
accumulator lands even, off the corridor in one hop (the 0-arm), while
an odd one keeps its odd residue class until the first non-rung line on
it, the node's stop.
Merging is prevented by phase: each read depth owns a (stride, residue)
channel -- 14 residues at stride 30, then `@nd` adjusters after the read
lift both arms so class `k` flies `30 + 2k`, 1596 depths before a stride
leaves the byte -- and every odd-line instruction avoids every channel
crossing it, checked at placement and re-checked by walking each flight
over the emitted text before the program is returned.  Leaf arms load 65
in one line (`nNnN`) and fly stride 66 to one of two shared printer
stops, so an arm is O(1) and the print code is spelled once, past every
stop, where nothing flies.  A node is O(1) occupied lines plus O(1)
placement slack, the corridor is linear in the layout, and per-entry
cost is flat where the router's climbed: the log's mechanism -- the span
sum over private waypoints -- has no term left to bill.

### What is compressible in the emitted programs

Measured 2026-09-11 at `92e42799`: every generator's output at n=3 and
n=8, on both suite shapes, 287 programs.

**The compressible part is unary tape travel, and the discriminator is how
wide an address space the construction allocates.**  Pointer walks emitted
one character at a time dominate every oversized brainfuck-family program.
Brainfuck's tree reaches cell 16 and stays small; Suffolk reaches 30,018
and is 98% travel.  The generators that were fixable were fixable for one
reason -- they allocated a cell per (input, row) rather than reusing a
bounded window -- and those have since shipped, bit~ among them.

The rest is not an encoding problem, and the classification is what keeps
it from being re-proposed:

- **Forced by semantics.**  `slow_acv_mammalian` is `SEED` repeated
  because that is the language's only primitive; `circlefuck_byte` spells
  unary byte literals; `one_two_three`'s runs *are* its numeric encoding;
  `dig`'s 81% spaces sit on a proved floor.  The ratio measures the
  alphabet, not a missed opportunity.
- **Priced in by a wall or a shipped optimization.**  `polynomial` is
  3.4 MB at a compression ratio of only 2.1x, digits uniform across 0-9 --
  there is no redundancy to remove, the size *is* information.  That is
  the reason a ratio must always be read beside a raw size, and the
  opposite of an opportunity.

A caution on reading this section against the generators: its ranked
candidate list has largely been consumed by the work it prompted, and at
least one of its recorded negatives -- that reordering minterms into Gray
order could not pay -- was superseded two days later, when ROTFuck moved
to a single binary-reflected Gray pass.  A sweep's negatives age against
the constructions they were measured on.

### Execution time

Everything above prices a generator's *source*.  Execution time is a
separate axis, measured here for all 65 by stepping each generated program
over every row of its table and keeping the worst row, out to eleven inputs
where that is affordable.  It is the product of two quantities, and they
have to be measured apart because neither predicts the other: the commands
a program executes, which stepping counts exactly, and the cost of a
command, which is not constant.  Program *loading* is excluded throughout --
real time, but not the program running, and for two languages it is the
entire cost.  The figures are worst-row and were taken on parity tables;
random tables cost the same or less, so they bound rather than flatter.

Every generator's *command count* is now linear or better, which the
execution contract measures and holds.  What separates them is the second
factor.  Where a command costs a constant, the program is linear -- Minifuck,
COD, Forth, Back, ROTfuck, S*bleq, Qoibl, Container and about a dozen more,
which is what walking a table once costs.

Where it does not, run time grows faster than the commands do.  Measured at
nine inputs as the worst row's run time and its growth per added input,
with loading excluded: Flowchart 415 ms at x3.6, BrainIf 82 ms at x2.9,
LaserFuck 47 ms at x2.9, RAM0 17 ms at x3.0, Jaune 18 ms at x2.9, Eval
1.6 ms at x2.1 and Bitdeque 1.2 ms at x2.5, against the x2.0 a linear
program would show.

The magnitudes are quoted because the exponents alone are misleading here.
Only Flowchart costs enough to notice; Bitdeque's x2.5 is a millisecond,
which is a ratio between two timings too small to mean much, and chasing it
would buy nothing.  A growth figure on a run this short is noise wearing an
exponent.  Those share a
mechanism: each rebuilds an immutable tape, association list or pointer
memory on every write, so a write costs the structure's size and Theta(T)
writes cost Theta(T^2).  Minifuck answers the same problem with an integer
bit-vector and pays O(1); the others have not followed because the
structure sits inside the state the cycle detector hashes, so replacing it
is a change to the state type rather than to a function -- and for
Flowchart the pointer is passed between forked pointers as a value, which
is what its tuple of pairs is buying.

B-tapemark used to head that list at x3.8, and it did not belong on it.  Its
grid was a set of ``(x, y, char)`` triples used as a map from point to
symbol, so reading one cell scanned every mark -- a scan, not a rebuild.
Keyed by point it is x1.9, and the run at nine inputs went from 3.8 seconds
to 3.0 milliseconds.  The two mechanisms look alike from a profile and are
not: one is the structure being copied, the other is it being searched.

BIO used to head this list at x3.9.  It is x2.3 now, and the difference was
not its data structure: it searched the program for the closing brace of
every loop it skipped.  Matching the braces once at load is the whole of it,
which is worth stating because the same mistake was in six interpreters and
none of them looked like a data-structure problem.

Minsky Swap was the one whose *command count* was super-linear rather than
its per-command cost, and it was Theta(T log T) on the nose: commands per
table entry ran 4.5, 4.0, 3.9, 4.5, 5.2, 6.1, 7.1, 8.0, 9.0 and 10.0 at one
through ten inputs -- the input count, not a constant.  It padded each
input's setter block to the whole table's length, when equal width is only
required of a bit against *itself*; sized to its own weight, the blocks sum
to `T+2`, and per-entry commands settle at 2.01.  Every construction's
per-entry count now settles.

Twenty-two never look at most of the table, and their command counts are
polynomial in the input count rather than in its size.  brainfuck is the
clean case: its worst row is 113, 179, 251, ... 803 commands for one
through eleven inputs, an arithmetic progression, so it answers a
2048-row table in about eight hundred steps.  Factor, Polynomial, Circuit
Diagram, EGL and Fargo are the same shape.  A generator can therefore emit
a Theta(T) source whose execution never reads it, and the two axes have to
be quoted separately.

Container is the case this section used to leave open.  Its execution time
is not bounded by its O(T) source, as said above, and the reason is the
second factor rather than the first: the program runs a handful of
commands -- fourteen at six inputs -- but each divides a T-digit integer,
so the work is linear in the table while the command count is not.

Loading is where the largest costs turned out to sit, and they are not the
same languages.  A Factor program *is* an integer and loading it means
factoring that integer, so the cost is the language rather than the
implementation; the sieve is chunked and tests each chunk with one gcd
rather than a full-width remainder per prime, which leaves it quadratic in
the digit count but no worse.  Qoibl's loader searched for the shortest
parsing prefix at every cut point and re-sliced its tokens for each trial,
which was cubic and spent a minute on an 18 KB program; spans are now
indices with a memo, and the remaining quadratic is the cost of proving
that a position inside a statement starts nothing.  Circuit Diagram's grid
is superlinear in area by construction -- one band per minterm -- and its
parse is linear in that area.  Streetcode's load is linear with a large
constant.

That mistake -- searching the program for a jump target on every jump, with
no index built at load -- was in six interpreters, and two of them already
walked the whole program at load to check their brackets and threw the
pairing away.  BIO matched its braces once, Jaune indexed its labels, Sophie
and BF-PDA kept the pairing their load pass was computing anyway, Polynomial
stopped finding the same partner twice in one step, and 123, whose jump is a
nearest-neighbour search rather than a nesting one, got two prefix arrays.
Only BIO and Jaune had programs long-running enough for it to show on this
corpus; the rest were latent, and none of them announced itself -- a scan
inside a step function reads like a lookup until its length is measured.


## Curation

The collection has 65 languages. The floor is 34: the languages that own a
generator construction, Polynomial and Modulous for their walls, and
brainfuck for Factor's decoder. The 69→65 cut removed DINAC, MyScript,
Basicfuck, and Nevermind: ordinary imperative languages with shared-shim
generators and no downstream consumer. The second band removed Suptiftam,
Lamfunc, `function x(y)`, Between, and Point Break on the same criterion,
leaving 60. Crement, Nopstacle, Vandevelo, B-tapemark, and EGL were added
afterwards; Crement and Nopstacle specialize their lookup in the host, so they
are prototypes and only the other three raise the floor.

The 2D candidate pool is screened out, and the screen is recorded because
re-running it is expensive.  An earlier pass was attributed to
`Category:Two-dimensional` x `Category:Unimplemented`, which cannot have
produced it: that category does not exist on the wiki, and a query against a
non-existent category returns no members.  The real intersection is
`Category:Unimplemented` (1543 pages) against `Category:Two-dimensional
languages` (567), reduced to 36 survivors by subtracting languages already
carrying a verdict here, rejecting on co-category (no IO, stubs,
works-in-progress, joke, nondeterministic, output-only, non-textual,
uncomputable), and rejecting pages that lack input, output or branch
vocabulary or run under 1500 characters.  Spec reads then tiered the 36, and
the top tier is fully resolved: Super SNUSP and Alight were admitted, as was
B-tapemark from the second tier, and Pinyin was rejected -- its own selection
rule reroutes 8 of 23 `Hello, world!` characters and its truth machine on
input 1 is unreachable under all 384 readings of the page.  ABCDirection is
not a candidate either; it was implemented here and then removed.

## Specification decisions

- 6-5 accepts operands beyond its specification; generators use `0..35`.
- Jaune's dispatch to an undefined marker is unspecified.
- Alight expressions are infix, left-to-right; three-argument `at` mutates.
- Packlang numeric literals are decimal. Its cat cannot receive byte 10 under
  this package's line-oriented input model.
- Pinyin is rejected: its spelling-to-pronunciation rule contradicts its own
  examples, and its truth-machine input-1 example has no deterministic reading.

Generated programs are evidence only after execution through their interpreter.
