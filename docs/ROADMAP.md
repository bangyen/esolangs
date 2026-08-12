# Roadmap

Planned work, in priority order.  Language assessments, documented walls,
and ruled-out ideas live in `docs/limitations.md`; completed ideas live in
the commit history.  This file only tracks what is still on the table.

## Planned

### S*bleq boolean generator
S*bleq has an interpreter and a text generator (both committed).  A boolean
generator is the remaining gap to make it a first-class language.  It is
genuinely harder than the text generator: S*bleq's operands are addresses, so
a cell holding a transient 0/1 value gets misread as an address if any
instruction references it — the generator must keep constant cells (never
written) separate from value cells (only read as values).  Each input bit
needs a read/normalize/branch sequence (~4 instructions), every branch needs
an indirect jump target cell, and the decision tree compounds the address
bookkeeping.  Prototyped the 1-input NOT gate (read -> normalize -> branch ->
output -> halt) as the core building block; generalizing it to n inputs is a
multi-session task.  The text generator emits only the base instruction
(`-3` output and `0 0` halt), which is also valid for the two store-target
variants but not the S**bleq indirect family.
