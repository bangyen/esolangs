# Roadmap

Planned work, in priority order.  Language assessments, documented walls,
and ruled-out ideas live in `docs/limitations.md`; completed ideas live in
the commit history.  This file only tracks what is still on the table.

## New interpreters (in priority order)

Candidates from re-scanning the esolangs wiki's Category:Unimplemented and
from User:PythonshellDebugwindow's language list.  The original scan is
exhausted: every candidate with a usable file-based I/O protocol, a complete
specification, and a plausible generator or boolean story now has an
interpreter.  What shipped and what was ruled out (Gravity, Earfuck,
Conveyor, Chainlang, Binary ///, Fourfuck, Aaargh++, Bitwise Cyclic Teast,
and the languages already implemented elsewhere) is in the commit history and
`docs/limitations.md`.

### Procedure (medium priority)
A Turing-complete pseudonatural English language with `Set the variable
'x' to ...`, `Connect to STDOUT`/`Write ... to the connection`, functions,
repeat-gotos, and if-then-otherwise conditionals.  Working Hello World, cat,
and truth-machine examples given.  The English-syntax parser is a heavier
lift.

Deferred on a spec gap: the only arithmetic operator the wiki defines is
`the sum of ...` (in the ``addthree`` example); there is no documented
subtraction, multiplication, or division.  A faithful interpreter cannot
implement the comparisons and GOTOs that make it Turing-complete without
inventing arithmetic semantics the spec never gives, and the English parser
is heavy enough that the arithmetic question should be settled before that
work starts.  Revisit if the wiki (or its successor Pure) defines the rest
of the operator set.

### Lamfunc (medium priority)
A Turing-complete functional language of prefix calls and `F name - code`
definitions with lambdas (`` .f ``) and builtins for equality, branching,
bit ops, and variable storage.  `p` prints a value, so text output goes
bit-by-bit and a text generator is awkward.

### Point Break (low priority)
A Turing-complete language with four commands (`LET`, `POINT`, `BREAK`,
`END`) that simulates Minsky machines; `?` reads an integer in a `LET`.  It
has no output at all, so like Crement and A Painter Ant it can only be a
self-contained interpreter without a generator.

### State and Main (low priority)
A language of `main` and numbered `state N` definitions whose only
statements are `(state N!)` changes and `(return)` — the truth-machine
example explicitly has "No output".  Like Point Break it can only be a
self-contained interpreter.

### Your Time Is Up (low priority)
A Turing-complete string-rewriting language in binary (`(1+0)(1+0)` rule
groups followed by the initial datastring), where execution picks a matching
rule at random.  The output is therefore non-deterministic, and like DSDLAI
the interpreter would be faithful but its behavior only testable
mechanically; it also has no I/O, so it is a self-contained interpreter.

### COD (low priority)
A two-dimensional concurrency-heavy language of cods swimming in waves
enclosed ponds, where each cod carries an unbounded integer and `+`/`-`
duplicate or remove it.  Branches resolve to random directions, so like
LaserFuck/DSDLAI the output is non-deterministic but the interpreter can be
faithful to the spec.  It has I/O (`...` input, `---` output).

### Suptiftam (low priority)
Two-dimensional tape-tapes of bytes or integers, permissive function
definitions, includes, and I/O via the `read`/`term` tapes.  The spec is
complete but has undefined behaviors and its examples are untested, so it is
a heavier, riskier implementation.

### Crement (low priority)
A self-modifying language with ADDRESS/DATA/JUMP opcodes and a polarity
field, fully specified including a Minsky-machine reduction.  It has no
I/O, so like A Painter Ant it can only be a self-contained interpreter
without a generator.

## Transpilers

A direct transpile between languages with no shared core is not a rewrite —
it needs a full runtime of one inside the other.  The transpilers that
shipped (the brainfuck family, `Decleq → S*bleq`, Dimensional → LaserFuck,
and the dropped silent-dropper/round-trip-only ones) are in the commit
history; the walls are in `docs/limitations.md`.  The candidates still on
the table:

- **Forth-family ↔ Forþ.**  Forþ is Forth-like (single-char stack,
  arithmetic, ``(``/``[`` loops, ``;`` calls); adding a second Forth dialect
  (e.g. plain Forth) would share the stack+arithmetic+loop core and
  transpile directly.
- **Boolfuck ↔ ABCDrection / Minifuck.**  A Boolfuck (bit tape, little-endian
  byte I/O) shares ABCDrection's bit-tape model; Minifuck's
  flip-and-conditional-skip is further away.

## VM / debugging interface (remaining work)

`esolangs.make_vm` (step-and-inspect wrappers for nine interpreters:
brainfuck, S*bleq, Dimensional, Grapheme, Qoibl, Eval, Modulous, The
Temporary Stack, LaserFuck) and `esolangs.make_debugger` (breakpoints and
watches over the VM) shipped.  The medium-priority work that remains:

- **More step-capable interpreters.**  Convert more of the registry to a
  step()/halted state object, growing the VM set per state model.  The
  other grid languages (2dFish, Dotlang, A Painter Ant, ...) are the
  natural next batch: their position/direction is the ``ip``, as LaserFuck
  demonstrated.
- **A richer ``ip`` for the recursive languages.**  Grapheme's ``ip`` is
  currently the active call frame's cursor; a language with nested calls
  should expose the call stack, not fold it into one frame's position.
