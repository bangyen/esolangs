"""Template for a new esolang interpreter.

Copy this file to ``src/esolangs/interpreters/<category>/<name>.py`` and fill
in the instruction dispatch.  ``<category>`` is one of ``tape_based``,
``stack_based``, ``register_based``, or ``other``; ``<name>`` is the language
name (lowercase, hyphens allowed).

Every interpreter follows the same conventions:

* Expose ``run(code)`` taking the program as a string (or a list of lines for
  grid/line-based languages) and printing output with ``print(..., end="")``;
  the function returns nothing.
* Read input with ``input("\\nInput: "[new:])``.  The ``new`` flag is 1 before
  any output (so the first prompt gets a leading newline), 0 after printing
  (the prompt then stays on the output line), and back to 1 after reading.
* Provide a ``__main__`` block that reads a program file and calls ``run``.

After the interpreter works, wire it into the suite the same way as the
others: a round-trip test in ``tests/tools/test_generate.py``, an entry in
the ``ROUND_TRIP`` (or ``NO_INTERPRETER``) table of
``tests/test_fuzz_generators.py``, a ``examples/hello-world/<name>.txt``
entry in ``tests/test_examples.py``, and -- if the language has input and
value branching -- a truth-table generator in ``tools/boolean.py``.
"""

import sys


def run(code):
    data = 0
    new = 1
    ind = 0

    while ind < len(code):
        c = code[ind]
        if c == "+":  # placeholder: increment the data cell
            data = (data + 1) % 256
        elif c == ".":  # placeholder: print the data cell
            print(chr(data), end="")
            new = 0
        elif c == ",":  # placeholder: read a byte of input
            val = input("\nInput: "[new:])
            data = ord(val[0])
            new = 1
        # add the language's real instructions here
        ind += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data)
