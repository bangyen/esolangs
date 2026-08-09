"""Template for a new esolang interpreter.

Copy this file to ``src/esolangs/interpreters/<category>/<name>.py`` and fill
in the instruction dispatch.  ``<category>`` is one of ``tape_based``,
``stack_based``, ``register_based``, or ``other``; ``<name>`` is the language
name (lowercase, hyphens allowed).

Every interpreter follows the same conventions:

* Expose ``run(code, io)`` taking the program as a string (or a list of
  lines for grid/line-based languages) and a required :class:`~esolangs.interpreters.io.IO`
  instance.  The library passes a ``ScriptedIO`` to feed a string as input
  and capture output; the ``__main__`` block passes a plain ``IO()`` for
  real stdin/stdout.
* Print with ``io.print_char``/``io.print_str``/``io.print_num`` and read
  with ``io.input_str``/``io.input_char``/``io.input_num`` instead of calling
  ``print``/``input`` directly.  The IO object owns the newline flag, so
  interpreters never track ``new`` themselves.
* Provide a ``__main__`` block that reads a program file and calls
  ``run(data, IO())``.

After the interpreter works, wire it into the suite the same way as the
others: a round-trip test in ``tests/tools/test_generate.py``, an entry in
the ``ROUND_TRIP`` (or ``NO_INTERPRETER``) table of
``tests/test_fuzz_generators.py``, a ``examples/hello-world/<name>.txt``
entry in ``tests/test_examples.py``, and -- if the language has input and
value branching -- a truth-table generator in ``tools/boolean.py``.
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
