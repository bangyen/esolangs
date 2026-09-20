# Limitations and contracts

Standing contracts and walls. Closed scaling work belongs in its commit;
Polynomial's proved wall is in [polynomial](polynomial.md).

## Interpreter conventions

- Empty input is a no-op unless a language requires a seed or grid.
- Exhausted input raises `EOFError`; malformed programs raise `ValueError`;
  runtime failure raises `HaltError`, unless the language says otherwise.
- Character input is line-delimited; a blank line means `0` by package
  convention, not language inference.
- Explicit frame stacks are uncapped. Forbin expression calls retain their
  documented host-recursion limit.
- Streetcode's four-way junction is an implementation convention: the source
  specifies only a two-road choice.

## Source positions

`esolangs debug --tui` marks only a source position. `ip_shape` is `offset`,
`grid`, `line`, or `opaque` -- `tests/test_vm_protocol.py` sweeps every language
and refuses an undeclared or misspelled value. Opaque positions have no program
mark.

Line extraction accepts anti-aliased PNGs only when strokes retain a connected
dark core. The 3px scan fixture executes addition; a one-third-pixel shift of
a 1px stroke is rejected with 921 unaccounted pixels rather than silently
changing the program.

## Boolean generators

Parameterized generators embed each input exactly once. Every emitted
character is build work. Reordering is optional around a construction, but
its selection cost counts; named candidates are capped at four and the generic
greedy scorer stops at n=10. Generator constructions may not use BFS or DFS;
test-only oracles may.

The screen script measures permuted-table builds, not an admissible reorder
under a fixed input template and fill mapping. Dig, Flowchart,
BrainIf, Sophie, and SLOW ACV MAMMALIAN must read streams in order; BF-PDA uses
its fixed stack order. No instruction-only wire is derived for 123 or Minifuck.
ArrowQueue re-enqueue remains open.

Malbolge registers no generator. Its only data operations are the crazy
operation and rotation, and control reaches memory only through `d`
(`i`/`j` set `c`/`d` from `memory[d]`); the input byte lands in `a`. Two
measured obstacles sit between that and a linear generator, neither a lower
bound.

Without `i`/`j` the machine is straight-line (`c == d` from the reset state),
so a `p`'s operand is its own cell's instruction character -- one of 94 values
in 33..126 -- and no earlier write is ever read back. A BFS over the input
pair `(48, 49)` under those 94 maps closes at 216 states, and every reachable
low-byte pair is `(n, n)` or `(n, n+1)`; `(49, 48)` is unreachable. NOT is not
expressible at any length, so the no-jump model is dead for every nontrivial
table.

With `i`/`j` a conditional branch does exist: hold `V` in `memory[d]`, read
the input into `a`, `p` writes `crazy(a, V)` back, and an `i` jumps there.
`crazy(48, V)` and `crazy(49, V)` differ by 0 or -1, so the targets are
adjacent; rotating the input before the `p` moves the distinguishing trit and
separates them by `3**k`, the shape a ternary-address tree wants. But the
operand `V` must be in memory before `p`, and `_load` admits only source
characters that decipher to an instruction at their position: source data is 8
values per cell, all at most 126. Source `V`, `V = rotate^k(s)`, and an input
rotation together give only 1050 distinct target pairs (differences `-3**k`,
`k = 0..9`), while a tree has `2**(n+1) - 1` nodes (1023 at n=9, 2047 at
n=10). BFS from 33..126 under rotation and `crazy` with a source operand
reaches 44007 of 59049 words, so a source-driven builder cannot name every
operand either. Building `V` is the ternary ALU this entry used to call an
obstacle. The per-node tree also spends tens of cells a node, near the fixed
59049-word store at n=10, so the fit is bf2malbolge's `O(1)`-code computed
branch into a `T`-cell corridor -- which needs the row index, the same ALU.
Scheffer's compiler gives the shape (arbitrary load/store in about four `p`s
per word), so an O(T) generator is not ruled out; it needs a generator-side
Malbolge assembler. The language stays interpreter-only with `generate`
refusing it until that is built.

A HeLL generator was driven through an LMAO port (GPL-3.0, byte-identical on
the six shipped examples) and run on the repository interpreter.  It exposes a
second wall under the assembler one: the increment subroutine the ternary index
route needs is not re-entrant.  `value` is a pointer advanced by one through a
data web whose flag phases are not restored between calls, so an unrolled
second call nets `+1`, not `+2`:

    n=1 "01"       rows [0],[1] -> '0','1'              correct
    n=2 "0110"     rows [0,0],[0,1],[1,0] -> '0','1','1' correct
                   row [1,1] -> '1', want '0'; value reads corridor+0
    n=3 "01101001" 4 of 8 rows wrong

The failure survives distinct return slots per call, `R_ROT R_ROT` in the
caller, restoring only the current `SUBROUTINE_FLAG`, and a `LOOP2` loop tail,
so it is the subroutine's internal web, not the call site.  `digital_root`
calls `increment_value` repeatedly, but its loop body is a separate top-level
braced block; a caller inside the `ENTRY` block cannot reproduce that layout.
The per-bit trit-set construction (call the increment once per set bit, under a
rotation) therefore needs a per-bit copy of the increment's whole state
machine, not merely a fresh call site.  Reopen with a web-resetting
construction, or with the raw-loader route above.

| Generator | Dense | Parity | Limit |
| --- | ---: | ---: | --- |
| Polynomial | 10 | 10 | 1,934-instruction guard; dense n=11 is priced at 267 s and >100 MB. |

Polynomial's mandatory root product has minimum mass at the product itself;
for programs whose real instruction roots are distinct the slack certificate
proves `Theta(L**2 log L) = Theta(T**2 / log T)` digits for every multiple,
cofactor, and operand sign. Repeated real roots are legal (`(x-2)^3` decodes to
three `[1]` instructions) and that theorem does not cover them, so the general
language bound is open -- the one missing lemma is named in
[polynomial](polynomial.md). Factor has a language floor
`Omega(T log T / log log T)`, a pigeonhole count on D-digit integers
([factor](factor.md)); its folded tree is `Theta(T log T)`.

### Scaling

Size is measured from rendered output, and correctness claims require running
the generated program. Execution measurements exclude loading and use the
worst sampled parity row. A sub-10 ms run does not establish an exponent.
Loading dominates Factor (integer factorization) and Circuit Diagram (parsing
super-linear area); it is intentionally excluded from execution time.

The execution contract in `tests/proofs/deep/execution.py` holds every
generator's command count linear. Bracket matching is precomputed at load.
Persistent stores use shared 32-cell chunks; RAM0 also indexes addresses.
Those choices prevent repeated scans, but command cost and source size remain
separate axes.

## Curation

The collection has 62 languages; its floor is 31. One interpreter-only
classic (Malbolge) is registered with no generator and marked `int` by
`list --details`: it is here for coverage, not for a new construction axis.
Befunge and Whitespace carry loop-less O(T) generators. Ordinary
imperative entries with shared-shim generators and no consumer were removed. Nopstacle and
ZTOALC L left: the former cannot meet embed conventions, the
latter was a searched syntax-level lookup table. The 2D candidate screen is
kept because re-running it is expensive: 1,543 unimplemented pages intersected
with 567 two-dimensional-language pages, then filtered to 36 by implemented
verdicts, co-categories, I/O/branch vocabulary, and 1,500-character pages.
Super SNUSP and Alight were admitted; Pinyin was rejected.

## Specification decisions

- 6-5 accepts operands beyond its specification; generators use `0..35`.
- Jaune dispatch to an undefined marker is unspecified.
- Alight expressions are infix and left-to-right; three-argument `at` mutates.
- Packlang literals are decimal; its cat cannot receive byte 10 under
  line-oriented input.
- Pinyin is rejected: its spelling rule contradicts its examples and its
  input-1 truth-machine example has no deterministic reading.

Generated programs are evidence only after execution through their interpreter.
