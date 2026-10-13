# Complete residual sharing in Circuit Diagram

Let a truth table have length $T=2^n$, indexed most significant input first.
The default generator measures emitted ASCII characters, including spaces
and newlines. Rectangle cells are reported separately. This proof concerns
unconstrained default generation; an explicit width retains the existing
complete shared fold and banding rules.

## Construction and admission

The generator projects ignored inputs and builds complete reduced residual
DAGs in three fixed orders: natural order, and the last three or four
essential inputs moved first. Each node is keyed by its selector level and
its two child identities. Equal children eliminate the selector; identical
keys reuse a node. Thus every repeated residual in each ordered fold shares
one signal, including residuals outside the former node and class caps.
Projection preserves the function because an ignored input cannot change
its output. The physical input ports remain in their original read order.

All three interval models survive until final selection. A prefix H-layout
or a bounded cofactor bank supplies the existing linear-size fallback.
The generator renders that fallback, counts each complete model exactly,
and renders a complete model only when its character count is no greater.
A complete model wins a fallback tie; the first complete model in the fixed
order wins subsequent ties. There is no order search or node-count cutoff.

If the fallback wins, all three complete drawings are strictly larger in
emitted characters. This is a per-table instance of the average-larger
canonical exemption in [Contributing](../CONTRIBUTING.md#what-makes-a-generator-optimization-worth-shipping).
It is not an assertion that every possible physical embedding is larger.

## Modeling work

At residual width $k$, there are at most $2^{n-k}$ occurrences and at most
$2^{2^k}$ distinct Boolean functions. The number $M$ of distinct residual
nodes therefore satisfies

$$M\le\sum_{k=1}^n\min(2^{n-k},2^{2^k}).$$

For $n\ge16$, split at $a=\lfloor\log_2n\rfloor-1$. The low-width sum is at
most $n2^{n/2}\le T/n$, since $n^2\le2^{n/2}$ in this range. The high-width
sum is at most $T/2^a\le4T/n$. Hence $M\le5T/n$. For $8\le n<16$,
$M<T$ and $\log_2(M+n)<16$, which supplies a uniform constant bound for
the finite initial band. Projection cannot increase this count: extending
the projected order with ignored inputs gives the same reduced graph.

Each residual emits at most three binary gates. In the unbanded builder,
gate rows increase, and a tap extends a bus from its last reached row.
Consequently each column's new vertical interval follows its previous
interval. A column is recycled only after the counted last read, and every
later gate lies below that read. Glyph-column insertions append; a gate row
contains a fixed number of horizontal intervals. These facts make interval
insertion append and bound overlap inspections by a constant. Index
bisection, glyph insertion searches and Fenwick column allocation take
logarithmic time. The complete model costs
$O((M+n)\log(M+n))=O(T)$ expected RAM work and $O(M+n)$ records.
Essential-input detection, projection and each fixed transpose also cost
$O(T)$; only three models are built.

## Counting and rendering

The character oracle sweeps vertical-interval starts and exclusive ends.
A heap gives the largest active column, with counts retaining overlapping
same-column intervals until their last end. Empty exclusive intervals,
which bank copies can retain, contribute no cells. Horizontal endpoints,
junctions and glyphs supply the other row maxima. A row ending at column
$x$ contributes $x+1$ characters; an empty row contributes zero. Adding
height minus one counts exactly the newlines inserted by the renderer.

A complete model has $O(M+n)$ intervals, points and rows. The sweep therefore
costs $O((M+n)\log(M+n))=O(T)$ without expanding vertical runs. Unbanded
columns have disjoint intervals, and horizontal runs per gate row are
bounded, so painting a selected complete model costs its emitted length.
The winner never exceeds the fallback's $O(T)$ characters. Rendering the
fallback first avoids applying a logarithmic interval sweep to its
potentially $O(T)$ records. No linear rectangle-area claim is needed for
the complete drawing.

## Execution and written workspace

The two-input residual pool needs at most fourteen binary gates: eight
one-gate functions and two three-gate muxes. Each remaining residual uses
at most three gates. Including at most $n$ shared complements gives
$G\le14+3(T/4-1)+n\le T+n$ for $n\ge6$. The scalar wiring values and
two-input latches use at most $3G+n+2$ written bits, which is below
$7T+2n-9$ for $n\ge8$. A reduced projection only decreases the gate count.
The longest gate path is at most $2n-1$; output and the quiet halt add two
commands, below the existing $2n+2$ contract. The fallback keeps its existing
gate and clock admission checks. Constants and arities below eight retain
the original generator and its stronger bounds.

## Executed evidence

The 17-input spread-pair witness contains 513 distinct seven-input classes.
Its complete drawings emit 56,113,416, 34,953,320 and 30,802,168 characters;
the smallest occupies 24,101 by 1,463 cells and executes zero/one controls
in 33 commands. The public sparse bank emits 30,228,859 characters in
31,716,375 rectangle cells. Every class was checked at both of its one
positions and a zero control: 1,539 native rows, at most 24 commands.
The public program matches audit SHA-256
`7103420777d5ecd1439eac0fc3be24a42b3126021a0e4dfb2df912ca36a1763b`.

Tests compare the character oracle with painted layouts, including empty
rows, overlapping runs and empty bank intervals. Complete folds execute
every row at arities three through five, with projection and port-order
controls at larger arities. Both dense families pass native growth cohorts
8/10/12, 9/11/13 and 10/12/14. The deep diagnostic now reaches thirteen,
supplying three rungs per parity after default H routing begins at eight.
Its unchanged 4.4 threshold passes at 4.271 in 6.8 seconds. The former cap
of ten mixed routing regimes and reported 4.758 before and after this change.
These finite diagnostics are not the linearity proof above.
