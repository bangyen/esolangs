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

Vandevelo's current spelling emits one depth-`n` guard chain for each of
Theta(T) selected parity rows, hence Theta(T log T).

The [`O(T/log T)` affine-cover theorem of Cohen and Shinkar][dnf-parities] does
not by itself give linear Vandevelo source: its size measure is the number of
top-level clauses, while one clause may spell Theta(log T) dense parity
equations with Theta(log T) variable references apiece.  A shared linear-form
construction can reduce the XOR-gate count to O(T) by tabulating all parities of
two half-input blocks, but referring to one of Theta(sqrt(T)) live bindings
costs Theta(log T) characters.  A construction that removes that addressing cost
could still close the gap, so this is not a language lower bound.

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
No constant-token update is yet known that changes it to each child's next
absolute label; reconstructing that label from array sum is the trampoline
above.

Polynomial's current expanded-root encoding is super-linear; this is not a
language-wide lower bound.  Standard maximal ordered-BDD table families have
Omega(T/log T) distinct residual states, so every tree/machine split used here
emits that many instructions.  The builder encodes negative arithmetic by
changing the opcode, not by using a negative operand, so every resulting monic
factor has alternating nonnegative coefficient magnitudes.  Products preserve
that sign pattern without cancellation.  The binomial contributions obtained by
taking the leading or constant term of each factor alone give Omega(m^2) total
coefficient digits for `m` factors.  With `m = Omega(T/log T)`, the expanded
program is Omega(T^2/(log T)^2).  An alternate root family could invalidate the
argument, so Polynomial remains open alongside the other construction walls.

Extra roots that do not match an instruction code may multiply the mandatory
root product without changing execution.  The general sparse-multiple problem
does not supply a generator: known rational algorithms are exponential in the
requested sparsity, which is `Theta(T/log T)` here.  A usable result must be a
direct family for these prime-power roots.

[sparse-multiples]: https://arxiv.org/abs/1009.3214

Interprogck8 is super-linear and the scaling contract exempts it only by
accident: its `proofs.md` row is an `exception` about the repair budget's
totality, which says nothing about size.  Measured, it is real rather than an
artefact of the two-step statistic -- parity per-entry cost climbs
monotonically from 328 to 526 characters over n=3..10, and `DownAccLines` per
entry rises by a near-constant +0.7 an arity, which is the signature of
`a + b*n` rather than a constant.

What *is* settled is that a decision tree is forced.  Every read destroys the
accumulator -- `u` loads the byte and `{values/=a/=b/=c}` overwrites it with 84
or 81 -- so no value survives a read, and the only state carrying which rows
remain possible is the instruction pointer.  A program distinguishing 2^k
prefixes therefore needs 2^k distinct positions after k reads.  That also
closes the packed-table route twice: an index cannot be accumulated across
reads, and on a computed jump the landing accumulator *is* the index, which a
fall-through suffix cannot cancel without a one-line no-op the language does
not have.

Routing the tree is then what costs the log factor, and the first attempt at
saying why was wrong in a way worth keeping: it claimed relay rungs cannot be
shared between chains with distinct targets.  A rung is a bare `DownAccLines`,
which is stateless -- two chains may land on the same line carrying different
accumulators, and each flies its own stride.  Rungs *are* shareable, and what
matters is the union of the chains' waypoints rather than the sum.

Sharing is nonetheless bounded, because it cannot *persist*.  A rung has to be
a dead line, so it lives in a meadow, and a stride of at most one reach forces
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
`Theta(N log N)` in any linear arrangement -- `Omega(T log T)` rungs.  One step
of that is still borrowed rather than proved here: the minimum linear
arrangement of a complete binary tree.  Everything else is the interpreter's
own geometry, so that citation is the whole remaining gap, and a layout beating
`Omega(N log N)` on total edge span is exactly what would reopen this.

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
