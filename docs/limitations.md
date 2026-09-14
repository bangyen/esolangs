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

Uncapped dense-program sizes at n=8/n=9: Polynomial 3.38/10.90 MB, COD
0.94/3.67 MB, SLOW ACV MAMMALIAN 1.67/3.38 MB, Circuit Diagram 0.15/0.32 MB,
123 0.09/0.23 MB, ROTfuck 0.02/0.03 MB, bit~ 0.03/0.06 MB, Factor
0.02/0.04 MB. Run generated programs before claiming size or equivalence.

The retired A Painter Ant tree was Theta(T log T): on parity every subtree was
live, and each depth traversed Theta(T) weighted edges.  Its lookup strip is
linear: `ePEP` both establishes a white corridor on pass one and traverses it
on later passes, while the adjacent answer row costs at most three characters
per one entry.  In 123, `_phase_a` uses the tight
marks `(i+1)*2T+1` and emits Theta(mark) movement four times for every input;
their sum is Theta(T (log T)^2).  These prove bounds on the shipped
constructions, not on either language; a different geometry could evade them.
Circuit Diagram's current layout is likewise Theta(T log T) on parity: all
`n` selector rails remain live across Theta(T) columns.  Localizing each rail
to its mux level remains an open route around that construction bound.
COD's leaf cascade is Theta(T^2): each of T leaf rows contains a prefix of
length `3(k+1)` and a gate tail of length `2(T-k-1)`, so every row is
Theta(T) and rotation cannot change the number of cells.  A non-cascade
decoder is required for linear output.
Minifuck's fixed mux is Theta(T^2) in the worst case.  Its triangular planner
visits targets sequentially; after prior choices fix row `i`'s predicted bit,
choosing the opposite table bit forces that row to fire.  This recursively
defines a valid table that fires every row.  Fired row `i` spells both `<` and
`[x` across Theta(T-i) cells, whose sum is Theta(T^2).  A shared or packed
sculpt is required for linear output.
Factor is Theta(T log T) on parity under the current encoding.  The folded
Brainfuck tree has Theta(T) maximal command runs.  Each run consumes the next
prime in one of eight nonzero residue classes modulo 11; the k-th such prime
has Theta(log k) decimal digits, and the encoded integer's digit count is the
sum of those logarithms.  Run compression changes exponents, not the number
of distinct primes.  A decoder that can reuse a prime or encode runs by
position is required for linear output.

No alternate Factor generator can have O(T) output for every table.  Let D be
the decimal digit count of its integer and m the number of active prime
factors, hence decoded Brainfuck runs.  The first m primes have log-product
Theta(m log m), so m = O(D/log D).  Exponents sum to O(D); the number of their
compositions into at most m runs is
`exp(O(m log(D/m))) = exp(O(D log log D/log D))`.  The eight active residues
add only `8**m`, the same subexponential order.  Thus D-digit Factor texts
decode to `2**o(D)` Brainfuck programs.  If D = O(T), they realize `2**o(T)`
functions, fewer than the `2**T` truth tables for large T.  Some tables
therefore require super-linear Factor text, independent of construction.
AddSubJump's retired decision tree was Theta(T log T) on parity.  It emitted
Theta(T) four-word instructions and a data cell per `next` edge.  A constant
fraction of those words are positive instruction or data addresses in a
Theta(T)-cell memory, so their space-separated decimal rendering uses
Theta(log T) characters each.  The packed-chunk decoder replaced it.
ArrowQueue's retired full tree was Theta(T log T): `_connect` shifted both children
three columns right at every level, and parity retains Theta(T) occupied leaf
rows through all log T levels.  Compaction removes empty rows and columns but
none of those occupied prefixes.  Its marker-count construction is linear:
input `i` contributes either zero or `2**(n-1-i)` down headings, one right
sentinel follows them, and the sentinel selects one of T constant-size cascade
stages.  The arm lengths are `1+2+4+...+T/2 = T-1`.  Bitdeque's retired tree
was Theta(T log T):
every parity leaf emitted `n+1` `POP` commands and absolute `GOTO` operands.
Its head/tail discard lookup is linear.  RAM0's retired tree had linear command
count but Theta(T) absolute one-branch targets of Theta(log T) digits.  Its
straight-line RAM initializer and unary-weight lookup are linear.
BrainIf's retired tree is Theta(T log T) on parity: it emits Theta(T) branch `goto`s, and a
constant fraction target line numbers in a Theta(T)-line program, requiring
Theta(log T) decimal digits.  Its spatial lookup is linear.  Container has the same bound through names:
Theta(T) leaf containers are each defined and referenced a constant number of
times, while distinct identifiers over its fixed 52-letter alphabet require
Theta(log T) characters for a constant fraction of them.

Three retired or current grid layouts spend one depth-width strip per table
row.  Clockwise's retired flat form used Theta(T) columns across Theta(log T)
active rows; its bounded-width stack instead uses Theta(log T) columns across
Theta(T) rows.  Alternating the two compositions makes both dimensions
O(sqrt(T)), hence O(T) area.  Dig's two-band form leaves Theta(T) occupied
leaf rows reaching across Theta(log T) columns.  Flowchart's retired tree placed Theta(T) leaves on
fixed pitch and drew one Theta(T)-wide selector level per input.  Its five-row
deque layout is linear: it preloads T answers, then its two arms discard
opposite halves; setting the arms to 1/0 before a shared switch makes both
incoming headings leave east.  Dig still needs localized or shared routing.
Inject's and Jaune's retired trees are Theta(T log T) on parity because both
assign a distinct label to every tree branch or leaf.  Inject emits each of Theta(T) labels
twice from a fixed 52-letter alphabet, so a constant fraction have
Theta(log T) characters.  Jaune emitted Theta(T) numeric labels and jump
operands, likewise with Theta(log T) decimal width for a constant fraction.
Jaune's spatial table now uses two labels.  Inject's single table block is
halved by O(log T) conditional regex substitutions whose literal text totals
O(T).
LaserFuck's retired tree and Streetcode's current tree use Theta(T) rows whose
live paths extend across Theta(log T) level columns on parity; trimming removes
only suffix blanks.  LaserFuck now conditionally walks arms of total length
`T-1`, selects one of T prewritten cells, then cleans all cells in one sweep.
Vandevelo emits one depth-`n` guard chain for each of Theta(T) selected parity
rows.  The latter two current spellings are Theta(T log T).

S*bleq's retired tree emitted Theta(T) instructions and data triples with absolute decimal
addresses into a Theta(T)-cell memory, so a constant fraction of its operands
had Theta(log T) digits.  Its packed-chunk decoder is linear.  SLOW ACV
MAMMALIAN is super-linear even though its
measured ratio is close to two: for a child cap `C`, `_widths` reserves a
trampoline slot of Omega(C/255), and `_subtree` emits that whole slot plus two
children.  Its recurrence is therefore `S(d) >= (2 + 1/255) S(d-1)`.

Polynomial's current expanded-root encoding is super-linear; this is not a
language-wide lower bound.
Standard maximal ordered-BDD table families have Omega(T/log T) distinct
residual states, so every tree/machine split used here emits that many
instructions.  The builder encodes negative arithmetic by changing the opcode,
not by using a negative operand, so every resulting monic factor has
alternating nonnegative coefficient magnitudes.  Products preserve that sign
pattern without cancellation.  The binomial contributions obtained by taking
the leading or constant term of each factor alone give Omega(m^2) total
coefficient digits for `m` factors.  With `m = Omega(T/log T)`, the expanded
program is Omega(T^2/(log T)^2).  An alternate root family could invalidate
the argument, so Polynomial remains open alongside the other construction
walls.


## Curation

The collection has 60 languages. The floor is 31: the languages that own a
generator construction, Polynomial and Modulous for their walls, and
brainfuck for Factor's decoder. The 69→65 cut removed DINAC, MyScript,
Basicfuck, and Nevermind: ordinary imperative languages with shared-shim
generators and no downstream consumer. The second band removed Suptiftam,
Lamfunc, `function x(y)`, Between, and Point Break on the same criterion.

## Specification decisions

- 6-5 accepts operands beyond its specification; generators use `0..35`.
- Jaune's dispatch to an undefined marker is unspecified.
- Alight expressions are infix, left-to-right; three-argument `at` mutates.
- Packlang numeric literals are decimal. Its cat cannot receive byte 10 under
  this package's line-oriented input model.
- Pinyin is rejected: its spelling-to-pronunciation rule contradicts its own
  examples, and its truth-machine input-1 example has no deterministic reading.

Generated programs are evidence only after execution through their interpreter.
