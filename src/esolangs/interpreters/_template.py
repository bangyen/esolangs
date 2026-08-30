"""Template for a new esolang interpreter.

Copy this file to ``src/esolangs/interpreters/<category>/<name>.py`` and fill
in the instruction dispatch.  ``<category>`` is one of ``tape_based``,
``stack_based``, ``register_based``, or ``other``; ``<name>`` is the language
name (lowercase, hyphens allowed).  See ``docs/CONTRIBUTING.md`` for how to wire
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
* Guard input lines before indexing them (``if val:``) whenever you take a
  character off ``io.input_str`` -- the ``;`` branch below.  An empty line is
  legal (the user pressed Enter and the terminator is stripped), so ``val[0]``
  is an ``IndexError`` without the guard; the fuzz and robustness suites feed
  exactly that.  ``io.input_char`` needs no guard, returning a newline for an
  empty line itself.  Input running out is the separate case and raises
  ``EOFError`` either way.
* Keep the run state in a class named ``_Machine``, exposing ``step()``,
  ``halted``, and ``snapshot()``, and let ``run()`` build one and step it to
  completion -- the shape below.  That is the surface ``esolangs.vm`` wraps
  to build a :class:`~esolangs.vm.VM`, and the one
  ``run_until_halt_or_cycle`` steps to prove a hang.  ``snapshot()`` must
  return a hashable tuple of the *complete* state, input cursor included,
  or a repeat is not a real cycle.  The name is checked and looked up, not
  merely conventional: ``tests/test_vm.py`` asserts every language has a
  ``snapshot()``, and ``tests/tools/test_boolean_contract.py`` finds the
  class by ``getattr(module, "_Machine")`` -- when ``dimensional.py`` used
  that name for its pointer hierarchy instead, the lookup built the wrong
  object, the error was suppressed, and the language was silently skipped.
  Where a module needs ``_Machine`` for something else, rename that other
  thing (Dimensional's hierarchy is ``_Tape``).  An interpreter that cannot
  be stepped -- one whose execution is not a command-at-a-time loop -- says
  so in its module docstring instead.
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

The module docstring has a fixed shape, checked by
``scripts/check_docstrings.py``::

    '''Interpreter for <Language>.

    <A short overview: the language's model (tape / stack / registers /
    grid), how input and output work, and what the reader needs to run a
    program.>

    <Documented decisions for gaps the wiki leaves open, one bullet each:
    EOF behavior when the language reads input, malformed programs
    (``ValueError``), invalid runtime operations (``HaltError``), and any
    other place the interpreter picks a behavior.>
    '''

The check enforces the mechanical parts -- the docstring names the language,
and mentions ``EOF``, ``HaltError``, or ``ValueError`` when the interpreter
reads input or raises them -- so the overview and the decision bullets stay
substantive and accurate.
"""

import sys

from esolangs.interpreters.io import IO


class _Machine:
    """The run state: the data cell and the code position.

    Holds everything one run mutates, so that ``step`` advances the program
    by exactly one command and ``snapshot`` can describe where it has got
    to.  A language whose state is bigger than a single cell (a tape, a
    stack, a grid and a pointer) keeps it all here.
    """

    def __init__(self, code: str, io: IO) -> None:
        self.code = code
        self.io = io
        self.data = 0
        self.ind = 0

    @property
    def halted(self) -> bool:
        return self.ind >= len(self.code)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # Every field ``step`` can change, plus the input cursor: a repeat
        # that ignores consumed input is not a real cycle.
        return (self.ind, self.data, self.io.position())

    def step(self) -> None:
        """Execute one command, advancing the code position."""
        c = self.code[self.ind]
        if c == "+":  # placeholder: increment the data cell
            self.data = (self.data + 1) % 256
        elif c == ".":  # placeholder: print the data cell
            self.io.print_char(chr(self.data))
        elif c == ",":  # placeholder: read a byte of input
            self.data = self.io.input_char()
        elif c == ";":  # placeholder: read a line and take its first character
            # ``input_char`` handles the empty line itself, but ``input_str``
            # hands back the raw line: an empty one is legal (the user pressed
            # Enter), so guard before indexing or a bare Enter is an
            # IndexError.  Running out of input is the different case, and
            # still raises EOFError.
            val = self.io.input_str()
            if val:
                self.data = ord(val[0])
        # add the language's real instructions here
        self.ind += 1


def run(code: str, io: IO) -> None:
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
