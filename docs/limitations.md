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
| Interprogck8 | 10 | 10 | Cost policy: dense n=11 builds only with 1,445 repairs and a 1.2 MB program. |
| Polynomial | 10 | 10 | 1,934-instruction guard; dense n=11 is 124 MB and runs in 267 s. |
| WII2D | 9 | 10 | Dense n=10 conflicts with the exactly-once embedding convention. |
| ZTOALC L | 10 | 10 | n=11 needs 545–587 command slots; the line ceiling admits at most 395. |

WII2D n=9 is partial: 37 of 64 sampled dense tables build and the rest refuse
promptly. Its magnitude guard is load-bearing. A per-node re-embed tree can
build dense n=13, but is outside the generator contract.

Uncapped dense-program sizes at n=8/n=9: Circuit Diagram 7.91/11.39 MB,
Polynomial 3.38/10.90 MB, SLOW ACV MAMMALIAN 1.67/3.38 MB, 123 22.4/44.7 KB,
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
and is enormous for dense wide tables.

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

SLOW ACV MAMMALIAN is super-linear even though its measured ratio is close to
two: for a child cap `C`, `_widths` reserves a trampoline slot of Omega(C/255),
and `_subtree` emits that whole slot plus two children.  Its recurrence is
therefore `S(d) >= (2 + 1/255) S(d-1)`.  This recurrence is not forced by input
itself: with `acc % 256 == 48`, `ACCEPT` appends exactly the input bit without
changing `acc`, so the retained integer can already name one `LEAPFROG` target.
A constant-token update *is* now known, so that is no longer the obstruction.
A **pump loop** -- a fixed ~20-token body that rotates a frozen anchor,
appends `S % 256` to a ballast array and re-enters through
`DIGEST`/`LEAPFROG` on the anchor's non-head sum -- raises an address by
thousands for O(1) text, and exits by planting one trigger in a queue
`SPRINT` marches through, diverting down a pad chain to a second exit
`LEAPFROG` at the pumped value.  An outer counted loop re-enters the inner
one and multiplies its ~87 iterations by the round count.  The pump has an
absorbing state -- an append adds `S % 256` to `S`, so once the low byte
reaches 0 the sum freezes and every later append is 0 -- and the cure is a
two-pair body over an array seeded with odd cells.

The address-space fault that stopped n >= 3 is repaired.  A loop body must
be laid at its anchor's value, and a node's two branches carry independent
machine states in one text space; the collision was a static-bound problem,
not a structural one -- the 1-subtree slot, the chain-gadget clearance, and
the 0-child's placement bound were fixed constants, and at n >= 2 the
0-chain's laid extent outgrew them by ~14,000.  The repair prices nothing
statically: the 1-subtree address settles by fixed point against the
0-chain's dry-run extent, the pump target settles against a scratch-built
1-subtree's actual extent, and the dry runs are exact, so their text is
merged and their worlds adopted rather than rebuilt.  The vertical order is
forced -- chain below the read target `t1`, 1-subtree at `t1 + 1`, 0-subtree
at the pump landing -- because the read leaves array 0's sum at `t1 + 1` in
the 0-branch and anchors only rise.  With that, the prototype builds *and
executes* n=1/2/3: every row of every arity through the interpreter
(876,739 / 1,878,218 / 10,789,439 characters), plus the exhaustive n <= 2
corpus, 20/20.  One warning travels with those numbers: correctness is
address-sensitive.  A faster root settle (a secant step in place of the
naive walk) picked a different root, and the resulting n=3 program fails
one row with empty output while every builder-side check passes -- so a
build only counts once its rows have executed, and the builder's internal
guards are known to be insufficient.

The executed regression is also what keeps this row open: per-entry cost
runs 438,370 / 469,554 / 1,348,680 characters, and the growth cannot be
pinned away -- asking for the n=2 counter at n=3 just forces the doubling
(60 cells suffice at n=2, 240 at n=3, against a 6.1x span).  One caution
on reading a law into that: the n=3 jump coincides with a regime change
(the counter doubles twice and nested pumping takes over), and three
points with a discontinuity at the last cannot separate "asymptotically
super-linear" from "a constant-factor cliff at the nesting threshold";
n=4 decides.  The cost itself is located either way: it is total raise
magnitude, chunked at ~254 units per solved append, so the DIGEST count
-- one per chunk (2,547 / 5,790 / 48,403) -- is the metric to watch.  The mechanism is the pump's reach law, measured affine off the
builder's own dry runs: climb ~ 10,000 x rounds - 14,000, with the
round-on-round ratio falling to `R/(R-1)`.  The early acceleration is a
transient, so a counted exit spells its climb in unary counter cells, each
node's climb is ~its 1-subtree's span, and those climbs sum over the tree
to Theta(T log T) addresses.  Fixed nesting does not escape: L counter
levels reach ~ C^L for L*C text, so one level is Theta(T) counter cells at
the root and L levels still leave `C = Theta(span^(1/L))`.  A tower whose
depth grows with the node's own span (~ln of it) makes the per-node cost
logarithmic in a span that halves per level, and `sum 2^d (n - d)` is
`2^(n+1) - n - 2` -- O(T) in total.  The arrays for it exist: a head at
array `i` steps by `i + 1` under SEED, covering all 23 routing classes
exactly when `gcd(i+1, 256) <= 8`, and of the six arrays the construction
leaves free, five qualify (7, 13, 16, 17, 19; only 15 fails, the one array
already noted as having no routable head).  Reach multiplies ~10,000 a
round per level, so a depth-5 tower out-reaches anything buildable; what
remains is engineering each level's divert route and pads, plus keeping
per-node tower depth matched to its own span.  The alternative is an exit
triggered by the pumped value itself rather than a count, which nothing in
the instruction set cheaply provides: `SPRINT`'s length guard compares
against an accumulator the pump can only hold small or whole-sum, and an
XOR-equality reference array must itself be raised to the target -- unless
it too can be pumped in lockstep, which is untested.

Two raise-cost measurements to keep any retuning honest: the free-chunk
raise decays -- the doubling orbit fills the array with its own small
appends and settles at ~3 units a token -- and a window-steered raise
(a few SEEDs aim `S % 256` into [200, 255], ~30 units a token held) is
16x cheaper than the solved-append raise in isolation but destabilised the
pump's exit search in both attempts to adopt it, so the shipped prototype
keeps solved appends.  Size remains the other reason not to ship: per-entry
cost at n=3 is ~200x the retired tree's, before any of the above is fixed.

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
1107000x^1+4168400` decodes to `[[70, 1], [-5, 1], [0, 1]]` and prints `A`
(`notes/poly_negative_operand.py`).  A complex instruction `[a, b]` is
`(x-a)^2 + p**(2b)`, so its linear coefficient `-2a` flips sign with `a`, and
that program's own expansion is already not alternating.  The builder encodes
negative arithmetic by changing the opcode instead, so *its* monic factors have
alternating nonnegative coefficient magnitudes and products preserve the sign
pattern without cancellation; the binomial contributions from each factor's
leading or constant term alone then give Omega(m^2) total coefficient digits,
and with `m = Omega(T/log T)` the expanded program is Omega(T^2/(log T)^2).
The no-cancellation premise is thus a property of the shipped builder, not of
the language, and mixed-sign operands are the free parameter it does not
cover.

The other escape is closed.  Shipping the *product* form -- `m` factors at
`O(log)` characters each, no expansion -- is not a legal encoding: the parser
strips `*` and reads only summed `c*x^d` monomials, keeping the last
coefficient per degree, so `f(x) = (x-2)(x-3)(x-5)` is silently read as
`x - 5` rather than rejected (`notes/poly_factored_probe.py`).  Program text
is the expanded coefficient digits and nothing else, which is what the bound
above prices.  Polynomial remains open alongside the other construction
walls.

Extra roots that do not match an instruction code may multiply the mandatory
root product without changing execution, but the escape is narrow.  No
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
construction-specific `Omega(m^2)` argument above does, and why ruling out
a sparse multiple is the whole question.  On current evidence this row
closes by construction if it closes at all.

One natural way to promote the two-term argument does *not* work, which is
worth recording so it is not retried.  That argument succeeds because a
two-term multiple forces every root to share one modulus, which distinct
primes cannot do.  The tempting generalisation -- a `t`-term polynomial's
roots take at most `t-1` distinct moduli, via Newton-polygon segments -- is
false: `x^3 - 7x + 6` is `(x-1)(x-2)(x+3)`, three terms and three distinct
moduli.  Sparsity bounds real positive roots by Descartes, but it does not
bound complex root moduli at all (`x^N - 1` has `N` roots on one circle from
two terms), so the modulus route cannot reach `t = Omega(m)`.

[sparse-multiples]: https://arxiv.org/abs/1009.3214

Interprogck8's shipped construction is super-linear, and the roadmap audit row
says so.  It had been exempt by accident: its `proofs.md` row is an `exception`
about the repair budget's totality, which says nothing about size, and nothing
else named it at all.  Measured, the growth is real rather than an
artefact of the two-step statistic -- parity per-entry cost climbs
monotonically from 328 to 526 characters over n=3..10, and `DownAccLines` per
entry rises by a near-constant +0.7 an arity, which is the signature of
`a + b*n` rather than a constant.

A decision diagram is **not** forced, and the paragraph that claimed it was
is retracted.  The accumulator does die at every read -- `u` loads the byte
and `{values/=a/=b/=c}` overwrites it with 84 or 81 -- but it is not the only
state, and the pointer is not the only thing that crosses a read.  Three
other channels do, each executed in `notes/ick8_slot_probe.py`:

- The **function slot**.  `u` does not touch it, and `<` captures the body
  the pointer is standing on, so two inputs can reach *one* line holding
  different bodies.  The probe's two arms meet at line 301 carrying the
  same accumulator -- 0, normalised on arrival on purpose, so the slot is
  the only thing that differs -- and the same `EXE` prints `A` or `B`.
  Stepped rather than inferred: `notes/ick8_slot_confirm.py` reads the
  pointer and the accumulator off the state at the call.
- The **call stack**.  A read taken inside a body returns into that body.
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
now measured on real artifacts, and the free supply does not close it
(`notes/ick8_packing.py`).  A chain flies a progression of step `1 + acc`,
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

That is the narrow gap.  The wide one is the retraction above: the tree is an
assumption, so a construction that is not a decision diagram over positions
pays none of this.  Two aim-points fall out, both refutable.  The slot gives a
*product* -- `P` positions times `C` captured bodies reach `P*C` residual
classes for `P+C` text -- but the two coordinates have to meet at the end, and
a body cannot branch on the accumulator the position tree hands it:
`DownAccLines` is rejected inside a body, and `{values}` consumes the
accumulator on its first test, so a body distinguishes one value of `j` and no
more.  The `z` loop is the other: two lines of text an iteration, input cursor
intact, text as memory, and no bound yet on what a `T`-line text can decide.
Neither is built.  Both are why this row reads Open rather than Language lower
bound.

Two families of long jumps contribute.  The bit-0 arm spans its sibling
subtree, and those targets are all distinct, which is the family the
obstruction above bites on.  The exit ladder is the easy one -- every leaf is
heading to the same place, so a common stride costs nothing -- and it is
removable: deleting it and having each
leaf stop where it stands drops parity per-entry cost from 526 to 352 at n=10,
a third of the program.  That is not shipped because the language has no halt.
Running off the last line is its termination, and the obvious one-line stand-in
is a line the interpreter does not recognise, which raises `HaltError` -- the
boolean runners swallow that, but `run` treats it as a crash, so it fails the
table harness.  The legitimate form is a shared escalator: every leaf hops onto
a lattice of `DownAccLines` rungs spaced one reach apart and rides it off the
end, which is `O(1)` a leaf plus `O(L/255)` shared.  It would leave the bit-0
family, and the generator super-linear, so it is recorded here rather than
built.


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

## Specification decisions

- 6-5 accepts operands beyond its specification; generators use `0..35`.
- Jaune's dispatch to an undefined marker is unspecified.
- Alight expressions are infix, left-to-right; three-argument `at` mutates.
- Packlang numeric literals are decimal. Its cat cannot receive byte 10 under
  this package's line-oriented input model.
- Pinyin is rejected: its spelling-to-pronunciation rule contradicts its own
  examples, and its truth-machine input-1 example has no deterministic reading.

Generated programs are evidence only after execution through their interpreter.
