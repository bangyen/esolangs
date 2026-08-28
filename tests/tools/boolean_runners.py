"""Interpreter runners shared by the boolean-generator test modules.

Each ``run_*`` helper feeds ``inputs`` to one language's interpreter and
returns everything it wrote to stdout, so the test modules can assert on a
generated program's output without repeating the capture plumbing.
"""

import importlib
import io
import random
from collections.abc import Iterator
from contextlib import redirect_stdout, suppress
from unittest.mock import patch

from esolangs.interpreters.io import IO


def run_dig(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.grid_based.dig import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program.splitlines(), io=IO())
    return buffer.getvalue()


def run_six_five(program: str, inputs: list[str]) -> str:

    run = importlib.import_module("esolangs.interpreters.tape_based.six_five").run
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO())
    return buffer.getvalue()


def run_six_five_from(program: str, feed: Iterator[str]) -> str:
    """Run a 6-5 program against an iterator, leaving what it did not read.

    ``run_six_five`` takes a list, so a caller cannot tell an exact read
    from an under-read.  Draining a shared iterator instead lets the caller
    assert it came back empty, which is how the "every path consumes exactly
    ``n`` inputs" contract is checked without parsing the emission.
    """
    run = importlib.import_module("esolangs.interpreters.tape_based.six_five").run
    buffer = io.StringIO()
    with (
        patch("builtins.input", side_effect=lambda *_: next(feed)),
        redirect_stdout(buffer),
    ):
        run(program, io=IO())
    return buffer.getvalue()


def run_dimensional(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.tape_based.dimensional import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO())
    return buffer.getvalue()


def run_bf(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.tape_based.brainfuck import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO())
    return buffer.getvalue()


def run_three_d_brainfuck(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.tape_based.three_d_brainfuck import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO())
    return buffer.getvalue()


def run_factor(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.tape_based.factor import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO())
    return buffer.getvalue()


def run_suffolk(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.tape_based.suffolk import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO(), limit=1)
    return buffer.getvalue()


def run_painfuck(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.tape_based.painfuck import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO())
    return buffer.getvalue()


def run_rotfuck(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.tape_based.rotfuck import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO())
    return buffer.getvalue()


def run_forth(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.stack_based.forth import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO())
    return buffer.getvalue()


def run_circlefuck(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.tape_based.circlefuck import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO())
    return buffer.getvalue()


def run_bit_tilde(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.tape_based.bit_tilde import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO())
    return buffer.getvalue()


def run_jaune(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.jaune import run

    io = ScriptedIO("\n".join(inputs) + "\n")
    run(program, io)
    return io.getvalue()


def run_123(program: str, inputs: list[str]) -> str:

    run = importlib.import_module("esolangs.interpreters.tape_based.one_two_three").run
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO())
    return buffer.getvalue()


def run_collatz_multiverse(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.register_based.collatz_multiverse import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO())
    return buffer.getvalue()


def run_decleq(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.register_based.decleq import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO())
    return buffer.getvalue()


def run_forbin_boolean(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.other.forbin import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO())
    return buffer.getvalue()


def run_suptiftam(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.other.suptiftam import run

    io = ScriptedIO("\n".join(inputs) + ("\n" if inputs else ""))
    run(program, io)
    return io.getvalue()


def run_addsubjump(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.register_based.addsubjump import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO())
    return buffer.getvalue()


def run_qoibl(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.register_based.qoibl import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program.splitlines(), io=IO())
    return buffer.getvalue()


def run_polynomial(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.register_based.polynomial import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO())
    return buffer.getvalue()


def run_polynomial_from(program: str, feed: Iterator[str]) -> str:
    """Run a Polynomial program against an iterator, leaving what it did not read.

    ``run_polynomial`` takes a list, so a caller cannot tell an exact read
    from an under-read.  Draining a shared iterator instead lets the caller
    assert it came back empty, which is how the "every path consumes exactly
    ``n`` inputs" contract is checked without parsing the emission.
    """
    from esolangs.interpreters.register_based.polynomial import run

    buffer = io.StringIO()
    with (
        patch("builtins.input", side_effect=lambda *_: next(feed)),
        redirect_stdout(buffer),
    ):
        run(program, io=IO())
    return buffer.getvalue()


def run_bfstack(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.stack_based.bfstack import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO())
    return buffer.getvalue()


def run_streetcode(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.grid_based.streetcode import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program.splitlines(), io=IO())
    return buffer.getvalue()


def run_flowchart(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.grid_based.flowchart import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program.splitlines(), io=IO())
    return buffer.getvalue()


def run_sophie(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.register_based.sophie import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO())
    return buffer.getvalue()


def run_between(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.register_based.between import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program.splitlines(), io=IO())
    return buffer.getvalue()


def run_sbleq(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.tape_based.sbleq import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO())
    return buffer.getvalue()


def run_modulous(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.stack_based.modulous import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO())
    return buffer.getvalue()


def run_grapheme(program: str, inputs: list[str]) -> str:
    """Run a Grapheme boolean program on the ``%``/``A`` input alphabet.

    Grapheme reads a whole line with ``W`` and every non-empty string is
    truthy, so the generator's input alphabet is ``%`` (0) and ``A`` (1)
    rather than ``0``/``1``.  This helper maps each ``0``/``1`` bit to the
    matching ``%``/``A`` line.
    """
    from esolangs.interpreters.stack_based.grapheme import run

    alphabet = {"0": "%", "1": "A"}
    buffer = io.StringIO()
    with (
        patch("builtins.input", side_effect=[alphabet[i] for i in inputs]),
        redirect_stdout(
            buffer,
        ),
    ):
        run(program, io=IO())
    return buffer.getvalue()


def run_brainif(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.tape_based.brainif import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program.splitlines(), io=IO())
    return buffer.getvalue()


def run_nevermind(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.register_based.nevermind import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program.splitlines(), io=IO())
    return buffer.getvalue()


def run_container(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.other.container import run

    buffer = io.StringIO()
    with (
        patch("builtins.input", side_effect=inputs),
        redirect_stdout(buffer),
        suppress(SystemExit),  # EXIT halts via sys.exit
    ):
        run(program.splitlines(), io=IO())
    return buffer.getvalue()


def run_taglate(program: str, inputs: list[str]) -> str:
    import esolangs

    return esolangs.run("Taglate", program, stdin="\n".join(inputs))


def run_clockwise(program: str, inputs: list[str]) -> str:
    import esolangs

    # Clockwise reads the whole input as one line (7 bits per char)
    return esolangs.run("Clockwise", program, stdin="".join(inputs))


def run_ztoalc(program: str, inputs: list[str]) -> str:
    import esolangs

    return esolangs.run("ZTOALC L", program, stdin="\n".join(inputs))


def run_laserfuck(program: str, inputs: list[str], heading: int) -> str:

    from esolangs.interpreters.grid_based.laserfuck import run
    from esolangs.interpreters.io import IO

    buffer = io.StringIO()

    class FakeIO(IO):
        def __init__(self, ins: list[str]) -> None:
            self._ins = list(ins)

        def input_str(self, _prompt: str = "Input: ") -> str:
            return self._ins.pop(0)

        def print_char(self, char: str) -> None:
            buffer.write(char)

        def print_str(self, text: str) -> None:
            buffer.write(text)

        def print_num(self, num: int) -> None:
            buffer.write(str(num))

    with redirect_stdout(buffer):
        run(program.splitlines(), FakeIO(inputs), heading=heading)
    # The generator runs in decimal output mode and drives the input cells
    # negative, which dump() skips, so the tape prints as exactly the answer
    # -- no filtering needed, and asserting on the raw output is stricter.
    return buffer.getvalue()


def run_myscript(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.register_based.myscript import run

    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs), redirect_stdout(buffer):
        run(program, io=IO())
    return buffer.getvalue()


def point_break_result(program: str, inputs: list[str]) -> str:
    """Run a Point Break program; return "0" if it halts and "1" if it loops.

    Point Break has no output, so the boolean generator's result is read
    from the termination convention (halt for 0, loop for 1).  The run is
    bounded by state-cycle detection instead of a wall-clock timeout: the
    interpreter is step-capable, and a deterministic run that revisits its
    complete internal state has looped forever, so the repeated state is a
    proof of the "1" output and is reported immediately.
    """
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.register_based.point_break import _Machine
    from esolangs.vm import run_until_halt_or_cycle

    machine = _Machine(program, ScriptedIO("\n".join(inputs)))
    return "0" if run_until_halt_or_cycle(machine) else "1"


_PB_TABLES = {
    "10": 1,  # NOT
    "0110": 2,  # XOR
    "0001": 2,  # AND
    "1110": 2,  # NAND
    "10100101": 3,  # mixed
}


_PB_CONSTANTS = ("0", "1", "00", "11", "0000", "1111")


def _pb_random_tables() -> list[str]:
    """The seeded random tables shared by the halting and loop checks."""
    random.seed(7)
    return [
        "".join(random.choice("01") for _ in range(2**n))
        for n in (1, 2, 3, 4)
        for _ in range(2)
    ]


def _pb_combo_bits(combo: int, n: int) -> list[str]:
    return [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
