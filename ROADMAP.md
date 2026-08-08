# Roadmap

Planned work, in priority order. Completed ideas live in the commit history;
this file only tracks what is still on the table.

## Planned

### PyPI trusted-publishing release pipeline
Publish `esolangs` to PyPI using trusted publishing (an OIDC workflow rather
than a token). The package, public API, CLI, and typing are already in shape
for distribution; this is the remaining step to make it installable by
others.

### Boolean-table transpiler bridge
A dynamic transpiler across the boolean-capable languages — Sophie, Modulous,
BrainIf, Nevermind, and CircleFuck. These are genuinely different machines,
but each has a verified generator that builds a program for any truth table,
so a transpiler can lift a program from one to another:

1. run the source program on all `2**n` inputs to extract its truth table;
2. regenerate in the target with its boolean generator.

It is nontrivial (a real transformation between machines, with the truth
table as the intermediate), bounded (the boolean-program class the
generators already produce), and verified exactly like every other
transpiler — the source and target must agree on every input. It needs a
design decision first: how to detect or take `n` (the input count) and how
to reject programs outside the class loudly.

### Brainfuck boolean generator via the BF-to-6-5 transpiler
A boolean generator for brainfuck, composed with the new BF-to-6-5
transpiler, would give 6-5 truth-table programs for arbitrary `n`.  The
roadblock is loop count: each bf `[`/`]` pair costs two 6-5 `4` markers,
and the transpiler's labels (0..9, A..Z) cap at 18 loops.  A decision-tree
generator needs `2**n - 1` branches, so it only helps up to about 5 inputs;
an arithmetic generator with a constant number of loops would be the
extensible version but has not been designed yet.
