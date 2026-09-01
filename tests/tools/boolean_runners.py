"""Interpreter runners shared by the boolean-generator test modules.

Each ``run_*`` helper feeds ``inputs`` to one language's interpreter and
returns everything it wrote to stdout, so the test modules can assert on a
generated program's output without repeating the capture plumbing.

The plain ``run_*`` helpers delegate to
:func:`tests.interpreters.runner.run_program`, which drives the interpreter
through :class:`ScriptedIO`.  The ``*_from`` family deliberately does not:
its shared iterator is the *read-count probe* rather than plumbing, since
the caller asserts the feed came back empty to prove a program consumed
exactly ``n`` inputs.  ``ScriptedIO`` owns its input privately and reports
only a count, so routing those through it would rewrite what the boolean
contract checks instead of how it is spelled.
"""

import importlib
import io
import random
from collections.abc import Iterator
from contextlib import redirect_stdout
from unittest.mock import patch

from esolangs.interpreters.io import IO
from tests.interpreters.runner import run_program


def _stdin(inputs: list[str]) -> str:
    """Join input lines into the single stdin string the runner takes.

    An empty list has to stay the empty string rather than a lone newline:
    a language that reads nothing and one that reads a blank line are
    different, and several boolean programs are in the first group.
    """
    return "".join(f"{line}\n" for line in inputs)


def run_dig(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.grid_based.dig import run

    return run_program(run, program.splitlines(), _stdin(inputs))


def run_six_five(program: str, inputs: list[str]) -> str:

    run = importlib.import_module("esolangs.interpreters.tape_based.six_five").run
    return run_program(run, program, _stdin(inputs))


def _run_from(module: str, program: str, feed: Iterator[str]) -> str:
    """Run ``program`` against an iterator, leaving what it did not read.

    The plain ``run_*`` helpers take a list, so a caller cannot tell an
    exact read from an under-read.  Draining a shared iterator instead lets
    the caller assert it came back empty, which is how the "every path
    consumes exactly ``n`` inputs" contract is checked without parsing the
    emission -- an over-read already raises, so the two together pin it.
    """
    run = importlib.import_module(module).run
    buffer = io.StringIO()
    with (
        patch("builtins.input", side_effect=lambda *_: next(feed)),
        redirect_stdout(buffer),
    ):
        run(program, io=IO())
    return buffer.getvalue()


def run_six_five_from(program: str, feed: Iterator[str]) -> str:
    """Run a 6-5 program against an iterator; see :func:`_run_from`."""
    return _run_from("esolangs.interpreters.tape_based.six_five", program, feed)


def run_addsubjump_from(program: str, feed: Iterator[str]) -> str:
    """Run an AddSubJump program against an iterator; see :func:`_run_from`."""
    return _run_from("esolangs.interpreters.register_based.addsubjump", program, feed)


def run_sophie_from(program: str, feed: Iterator[str]) -> str:
    """Run a Sophie program against an iterator; see :func:`_run_from`."""
    return _run_from("esolangs.interpreters.register_based.sophie", program, feed)


def run_inject(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.other.inject import run

    return run_program(run, program, _stdin(inputs))


def run_dimensional(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.tape_based.dimensional import run

    return run_program(run, program, _stdin(inputs))


def run_bf(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.tape_based.brainfuck import run

    return run_program(run, program, _stdin(inputs))


def run_three_d_brainfuck(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.tape_based.three_d_brainfuck import run

    return run_program(run, program, _stdin(inputs))


def run_factor(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.tape_based.factor import run

    return run_program(run, program, _stdin(inputs))


def run_suffolk(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.tape_based.suffolk import run

    return run_program(run, program, _stdin(inputs), limit=1)


def run_painfuck(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.tape_based.painfuck import run

    return run_program(run, program, _stdin(inputs))


def run_rotfuck(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.tape_based.rotfuck import run

    return run_program(run, program, _stdin(inputs))


def run_forth(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.stack_based.forth import run

    return run_program(run, program, _stdin(inputs))


def run_circlefuck(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.tape_based.circlefuck import run

    return run_program(run, program, _stdin(inputs))


def run_bit_tilde(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.tape_based.bit_tilde import run

    return run_program(run, program, _stdin(inputs))


def run_jaune(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.jaune import run

    io = ScriptedIO("\n".join(inputs) + "\n")
    run(program, io)
    return io.getvalue()


def run_123(program: str, inputs: list[str]) -> str:

    run = importlib.import_module("esolangs.interpreters.tape_based.one_two_three").run
    return run_program(run, program, _stdin(inputs))


def run_collatz_multiverse(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.register_based.collatz_multiverse import run

    return run_program(run, program, _stdin(inputs))


def run_decleq(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.register_based.decleq import run

    return run_program(run, program, _stdin(inputs))


def run_cvnc(program: str, inputs: list[str]) -> str:
    """Run a CV(N)(C) program, feeding one input line per bit.

    ``s`` reads a whole line as an integer, so the boolean convention here
    is the ordinary one: each bit is its own line, in the order the tree
    reads them.
    """
    from esolangs.interpreters.other.cvnc import run

    return run_program(run, program, _stdin(inputs))


def run_fargo(program: str, inputs: list[str]) -> str:
    """Run a Fargo program, packing ``inputs`` into its one input number.

    Fargo reads a single *number* before the program starts rather than a
    stream of bits, so the boolean convention is to feed the row index:
    the bits most-significant-first are the number's binary digits, which
    is what makes input ``i`` the generator's ``@ (n - 1 - i)``.
    """
    from esolangs.interpreters.other.fargo import run

    number = int("".join(inputs), 2) if inputs else 0
    return run_program(run, program, f"{number}\n")


def run_forbin_boolean(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.other.forbin import run

    return run_program(run, program, _stdin(inputs))


def run_suptiftam(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.other.suptiftam import run

    io = ScriptedIO("\n".join(inputs) + ("\n" if inputs else ""))
    run(program, io)
    return io.getvalue()


def run_addsubjump(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.register_based.addsubjump import run

    return run_program(run, program, _stdin(inputs))


def run_qoibl(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.register_based.qoibl import run

    return run_program(run, program.splitlines(), _stdin(inputs))


def run_polynomial(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.register_based.polynomial import run

    return run_program(run, program, _stdin(inputs))


def run_polynomial_from(program: str, feed: Iterator[str]) -> str:
    """Run a Polynomial program against an iterator; see :func:`_run_from`."""
    return _run_from("esolangs.interpreters.register_based.polynomial", program, feed)


def run_bfstack(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.stack_based.bfstack import run

    return run_program(run, program, _stdin(inputs))


def run_slow_acv_mammalian(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.tape_based.slow_acv_mammalian import run

    return run_program(run, program, _stdin(inputs))


def run_streetcode(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.grid_based.streetcode import run

    return run_program(run, program.splitlines(), _stdin(inputs))


def run_flowchart(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.grid_based.flowchart import run

    return run_program(run, program.splitlines(), _stdin(inputs))


def run_sophie(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.register_based.sophie import run

    return run_program(run, program, _stdin(inputs))


def run_between(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.register_based.between import run

    return run_program(run, program.splitlines(), _stdin(inputs))


def run_sbleq(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.tape_based.sbleq import run

    return run_program(run, program, _stdin(inputs))


def run_modulous(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.stack_based.modulous import run

    return run_program(run, program, _stdin(inputs))


def run_grapheme(program: str, inputs: list[str]) -> str:
    """Run a Grapheme boolean program on the ``%``/``A`` input alphabet.

    Grapheme reads a whole line with ``W`` and every non-empty string is
    truthy, so the generator's input alphabet is ``%`` (0) and ``A`` (1)
    rather than ``0``/``1``.  This helper maps each ``0``/``1`` bit to the
    matching ``%``/``A`` line.
    """
    from esolangs.interpreters.stack_based.grapheme import run

    alphabet = {"0": "%", "1": "A"}
    return run_program(run, program, _stdin([alphabet[i] for i in inputs]))


def run_brainif(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.tape_based.brainif import run

    return run_program(run, program.splitlines(), _stdin(inputs))


def run_nevermind(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.register_based.nevermind import run

    return run_program(run, program.splitlines(), _stdin(inputs))


def run_container(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.other.container import run

    # EXIT halts via sys.exit rather than by returning.
    return run_program(
        run,
        program.splitlines(),
        _stdin(inputs),
        suppress_exit=True,
    )


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

    return run_program(run, program, _stdin(inputs))


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


def one_two_three_result(program: str) -> str:
    """Run a 123 program; return "0" if it halts and "1" if it loops.

    123's boolean generator answers with the termination convention, the
    same one Point Break uses, so the verdict is a state revisit rather than
    a fuel cap.  There are no ``inputs``: the generator is parameterized, so
    the bits are already substituted into ``program`` and reaching the read
    command would mean the template was wrong.  ``ScriptedIO`` with an empty
    script supplies that -- a read raises instead of consuming real stdin.
    """
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.one_two_three import _Machine
    from esolangs.vm import run_until_halt_or_cycle

    machine = _Machine(program, ScriptedIO(""))
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
