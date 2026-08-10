"""Template for a new esolang interpreter.

Copy this file to ``src/esolangs/interpreters/<category>/<name>.py`` and fill
in the instruction dispatch.  ``<category>`` is one of ``tape_based``,
``stack_based``, ``register_based``, or ``other``; ``<name>`` is the language
name (lowercase, hyphens allowed).  See ``CONTRIBUTING.md`` for how to wire
the finished interpreter into the suite.

Every interpreter follows the same conventions:

* Expose ``run(code, io)`` taking the program as a string (or a list of
  lines for grid/line-based languages) and a required
  :class:`~esolangs.interpreters.io.IO` instance.  The library passes a
  ``ScriptedIO`` to feed a string as input and capture output; the
  ``__main__`` block passes a plain ``IO()`` for real stdin/stdout.  For
  grid/line-based languages the registry entry sets ``split=True`` so the
  library hands over the program split into lines.
* Print with ``io.print_char``/``io.print_str``/``io.print_num`` and read
  with ``io.input_str``/``io.input_char``/``io.input_num`` instead of calling
  ``print``/``input`` directly.  The IO object owns the newline flag, so
  interpreters never track ``new`` themselves.
* Terminate by ``return`` when the language's own rules stop the program.
  Distinguish invalid programs from invalid operations: raise
  :class:`ValueError` for a structurally malformed
  program (e.g. unbalanced brackets, empty program); raise
  :class:`~esolangs.exceptions.HaltError` for an invalid runtime operation
  (e.g. division by zero, popping an empty stack).  Interpreters must
  terminate by construction -- the fuzz and robustness suites feed random
  and empty programs and assert they never crash.
* Guard input lines before indexing them (``if val:``) when the language
  reads a character: the library raises ``EOFError`` when input runs out and
  an empty line is legal, so ``val[0]`` can fail without a guard.
* Document decisions for genuinely neutral gaps in the language's wiki spec
  in the module docstring rather than choosing silently; do not use this to
  define away invalid operations.  ``suffolk.py`` shows a *spec-gap* note --
  where the wiki is silent and the interpreter picks a behavior.  A gap note
  reads like::

      The wiki does not define <behavior>; this interpreter <decision>
      instead.  It raises :class:`ValueError` for a
      malformed program and :class:`~esolangs.exceptions.HaltError` for an
      invalid runtime operation.
* Provide a ``__main__`` block that reads a program file and calls
  ``run(data, IO())``.
"""

import sys

from esolangs.interpreters.io import IO


def run(code: str, io: IO) -> None:
    data = 0
    ind = 0

    while ind < len(code):
        c = code[ind]
        if c == "+":  # placeholder: increment the data cell
            data = (data + 1) % 256
        elif c == ".":  # placeholder: print the data cell
            io.print_char(chr(data))
        elif c == ",":  # placeholder: read a byte of input
            data = io.input_char()
        # add the language's real instructions here
        ind += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
