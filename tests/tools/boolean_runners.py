"""Interpreter runners shared by the boolean-generator test modules."""

import importlib
import io
from collections.abc import Callable, Iterator
from contextlib import redirect_stdout

from esolangs.interpreters.io import IO
from esolangs.interpreters.randomness import FirstDraw
from tests.interpreters.runner import run_program

Runner = Callable[[str, list[str]], str]


def _stdin(inputs: list[str]) -> str:
    """Join input lines into the single stdin string the runner takes."""
    return "".join(f"{line}\n" for line in inputs)


def _runner(module: str, *, lines: bool = False, newline: bool = False) -> Runner:
    """Build ``run_X(program, inputs)`` for ``esolangs.interpreters.<module>``.

    ``lines`` hands the program over as rows; ``newline`` feeds one input per
    line instead of joining them.  The module is imported on first run.
    """

    def run_language(program: str, inputs: list[str]) -> str:
        run = importlib.import_module(f"esolangs.interpreters.{module}").run
        code = program.splitlines() if lines else program
        return run_program(run, code, _stdin(inputs) if newline else "".join(inputs))

    return run_language


run_dig = _runner("grid_based.dig", lines=True, newline=True)
run_six_five = _runner("tape_based.six_five")
run_algebraic_programming_language = _runner(
    "other.algebraic_programming_language", newline=True
)
run_inject = _runner("other.inject", newline=True)
run_dimensional = _runner("tape_based.dimensional", newline=True)
run_bf = _runner("tape_based.brainfuck")
run_factor = _runner("tape_based.factor")
run_suffolk = _runner("tape_based.suffolk")
run_rotfuck = _runner("tape_based.rotfuck")
run_circlefuck = _runner("tape_based.circlefuck")
run_collatz_multiverse = _runner("register_based.collatz_multiverse", newline=True)
run_decleq = _runner("register_based.decleq")
run_cvnc = _runner("other.cvnc", newline=True)
run_forbin_boolean = _runner("other.forbin")
run_addsubjump = _runner("register_based.addsubjump")
run_qoibl = _runner("register_based.qoibl", lines=True)
run_polynomial = _runner("register_based.polynomial")
run_bfstack = _runner("stack_based.bfstack")
run_sstack = _runner("stack_based.sstack")
run_unsquare = _runner("stack_based.unsquare")
run_streetcode = _runner("grid_based.streetcode", lines=True)
run_flowchart = _runner("grid_based.flowchart", lines=True)
run_sophie = _runner("register_based.sophie")
run_sbleq = _runner("tape_based.sbleq")
run_modulous = _runner("stack_based.modulous", newline=True)
run_brainif = _runner("tape_based.brainif", lines=True)
run_container = _runner("other.container", lines=True)


def _run_from(module: str, program: str, feed: Iterator[str]) -> str:
    """Run ``program`` against an iterator, leaving what it did not read."""
    run = importlib.import_module(module).run
    buffer = io.StringIO()

    class CharacterFeed(IO):
        def input_char(self, _prompt: str = "Input: ") -> int:
            return ord(next(feed))

    with redirect_stdout(buffer):
        run(program, io=CharacterFeed())
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


def run_jaune(program: str, inputs: list[str]) -> str:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.jaune import run

    io = ScriptedIO("\n".join(inputs) + "\n")
    run(program, io)
    return io.getvalue()


def run_fargo(program: str, inputs: list[str]) -> str:
    """Run a Fargo program, packing ``inputs`` into its one input number."""
    from esolangs.interpreters.other.fargo import run

    number = int("".join(inputs), 2) if inputs else 0
    return run_program(run, program, f"{number}\n")


def run_polynomial_from(program: str, feed: Iterator[str]) -> str:
    """Run a Polynomial program against an iterator; see :func:`_run_from`."""
    return _run_from("esolangs.interpreters.register_based.polynomial", program, feed)


def run_grapheme(program: str, inputs: list[str]) -> str:
    """Run a Grapheme boolean program on the ``%``/``A`` input alphabet."""
    from esolangs.interpreters.stack_based.grapheme import run

    alphabet = {"0": "%", "1": "A"}
    return run_program(run, program, _stdin([alphabet[i] for i in inputs]))


def run_taglate(program: str, inputs: list[str]) -> str:
    import esolangs

    return esolangs.run("Taglate", program, stdin="".join(inputs))


def run_clockwise(program: str, inputs: list[str] | list[int]) -> str:
    import esolangs

    # Clockwise loads the complete character stream (7 bits per char).
    return esolangs.run("Clockwise", program, stdin="".join(map(str, inputs)))


def run_laserfuck(program: str, inputs: list[str], heading: int) -> str:

    from esolangs.interpreters.grid_based.laserfuck import run
    from esolangs.interpreters.io import IO

    buffer = io.StringIO()

    class FakeIO(IO):
        def __init__(self, ins: list[str]) -> None:
            self._ins = list(ins)

        def input_char(self, _prompt: str = "Input: ") -> int:
            return ord(self._ins.pop(0))

        def print_char(self, char: str) -> None:
            buffer.write(char)

        def print_str(self, text: str) -> None:
            buffer.write(text)

        def print_num(self, num: int) -> None:
            buffer.write(str(num))

    with redirect_stdout(buffer):
        run(program.splitlines(), FakeIO(inputs), rng=FirstDraw(heading))
    # The generator runs in decimal output mode and drives the input cells
    # negative, which dump() skips, so the tape prints as exactly the answer
    # -- no filtering needed, and asserting on the raw output is stricter.
    return buffer.getvalue()


def one_two_three_result(program: str) -> str:
    """Run a 123 program; return "0" if it halts and "1" if it loops."""
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.one_two_three import _Machine
    from esolangs.vm import run_until_halt_or_cycle

    machine = _Machine(program, ScriptedIO(""))
    return "0" if run_until_halt_or_cycle(machine) else "1"
