# Roadmap

Planned work, in priority order.  Language assessments, documented walls,
and ruled-out ideas live in `docs/limitations.md`; completed ideas live in
the commit history.  This file only tracks what is still on the table.

## Planned

### Dimensional v3.0 C++ reference
The wiki documents Dimensional **v3.0** (an n-slot/n-pointer model with
`$AXIS`, `d`, `x`), and the in-package Python interpreter
(`src/esolangs/interpreters/tape_based/dimensional.py`) implements it and is
registered.  The previous C++ reference (`extra/c++/dimensional.cpp`)
implemented the incompatible **v1.0** dialect (a single pointer over a
product-of-primes tape) and its 32-bit `int` cell addresses overflow past
~30 cells — the very reason v3 exists — and it was removed when the v3.0
Python interpreter landed.

With the Python interpreter as the only v3.0 implementation, generator
verification is circular (same author, same codebase, shared reading of the
under-specified spec).  A fresh `extra/c++/dimensional.cpp` implementing v3.0
would restore the independent differential cross-check and keep Dimensional
in the C++ reference family.  It must handle the addressing itself (a
`long long` key covers `n <= 28`; a small bignum for unbounded) — the very
overflow that motivates the change.

### Magnitude interpreter or reference
Magnitude has a text generator (`tools/generators/other.py`) that is tested
only for *producing* output — no in-package interpreter and no `extra/`
reference, so nothing round-trips its programs.  It is the one generator-only
language without any executable to verify against (Home Row, Jaune, etc. are
compiled and checked by `verify_x86_unicorn.py`; the rest have `extra/`
references).  A small interpreter (register-based, magnitudes over powers of
2/3) or a native reference would let the generator's output be round-trip
verified like every other generator-only language.
