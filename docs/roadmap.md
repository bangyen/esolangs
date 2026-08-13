# Roadmap

Planned work, in priority order.  Language assessments, documented walls,
and ruled-out ideas live in `docs/limitations.md`; completed ideas live in
the commit history.  This file only tracks what is still on the table.

## Boolean generators (in priority order)

### NoComment parameterized boolean generator
NoComment has no input, but its `s`/`b` commands jump forward/backward by a
peeked stack value when the current cell is nonzero, and setting a cell to 0
or 1 is constant-length (`c` vs `i`), so the parameterized template class
(BIO/Back) applies directly: the harness substitutes each input bit's
constant and a decision tree routes on the cells.  It is the cleanest
candidate for that class since the setter never shifts the jump distances.

### Minifuck partial boolean generator (low priority)
The documented wall caps Minifuck at 0-preserving tables with `n <= 3`.  A
generator for exactly that subset is possible but low value; the working
prefixes and the exact reachable table set are recorded in
`docs/limitations.md`.

## Text generators: exhausted

Every language whose interpreter can emit arbitrary bytes already has a text
generator.  The remaining interpreter-only languages (ArrowQueue, Back,
BitDeque, DSDLAI, Keys, Lightlang, Minsky Swap, Movesum, RAM0) either have no
output, print numeric state, or print a fixed string, so none can emit
arbitrary text.  The newly assessed boolean candidates that fell through
(Temporary, Movesum, WII2D, EXCON, Huf, Lightlang, DSDLAI) are recorded in
`docs/limitations.md`.
