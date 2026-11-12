"""Tests for the 1 + i interpreter."""

from fractions import Fraction
from itertools import product
from math import pi
from operator import add, mul
from struct import pack

import pytest

from esolangs.exceptions import HaltError
from esolangs.languages.one_i.interpreter import _Machine, _text, run
from esolangs.languages.one_i.tests.oracle_checks import _text as reference_text
from esolangs.runtime import _isolated
from esolangs.runtime._state import WorkspaceVariant
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from tests.interpreters.runner import native_runner
from tests.support.certification_barrier import guarded_worker
from tests.support.execution import termination_observed

TRUTH = "[$$[(:p)i?]i?][$$p]C:)ii*+?"

#: The wiki's constants table: value, then its shortest known expression.
CONSTANTS = [
    ("-2i", "ic:+"), ("-i", "ic"), ("-2", "ii*:+"), ("-1", "ii*"),
    ("0", "iic+"), ("1", "ici*"), ("2", "ici*:+"), ("3", "ici*::++"),
    ("4", "ii+:c*"), ("5", "ici*::+:++"), ("6", "ici*::++:+"),
    ("7", "ici*:::++:++"), ("8", "ii+:c*:+"), ("9", "ii+i+:c*"),
    ("10", "ici*::+:++:+"), ("11", "ici*:::+:++:++"), ("12", "ii+:c*::++"),
    ("13", "ici*:::++:+:++"), ("14", "ici*:::++:++:+"), ("15", "ii+:c*:*ii*+"),
    ("16", "ii+:c*:*"), ("17", "ii+:c*:*ici*+"), ("18", "ii+i+:c*:+"),
    ("19", "ii+:c*::*+ii*+"), ("20", "ii+:c*::*+"), ("21", "ii+:c*::*+ici*+"),
    ("23", "ii+:c*::++:+ii*+"), ("24", "ii+:c*::++:+"), ("25", "ici*::+:++:*"),
    ("26", "ici*:::++:+:++:+"), ("27", "ici*::++:^"), ("28", "ici*:::++:++:+:+"),
    ("29", "ici*::++::^+ii*+"), ("30", "ici*::++::^+"),
]  # fmt: skip


_run = native_runner(run)


def _value(code: str) -> str:
    machine = _Machine(code, ScriptedIO())
    while not machine.halted:
        machine.step()
    (top,) = machine.stack
    assert not callable(top)
    return _text(top)  # type: ignore[arg-type]


@pytest.mark.parametrize(("value", "code"), CONSTANTS)
def test_wiki_constants(value: str, code: str) -> None:
    assert _value(code) == value


def test_the_wiki_constant_for_22_is_12() -> None:
    # Pinned wiki error: ::: then +, :, +++, :, + is 12 under any operand order.
    assert _value("ici*:::+:+++:+") == "12"


def test_wiki_parts_roots_and_modulus() -> None:
    assert _run("D:c+ici*:+/*p", "3 - 4i\n") == "3"
    assert _run("Dic*:c+ici*:+/*p", "3 - 4i\n") == "-4"
    assert _run("D:c*ici*:+/^p", "3 - 4i\n") == "5"
    assert _run("Dici*:+/^p", "16\n") == "4"


def test_wiki_examples(monkeypatch) -> None:
    assert _run("ici*i+p") == "1 + i"
    assert _run("DD+p", "1 + 2i\n3 - i\n") == "4 + i"
    assert _run("ii+:c*p") == "4"
    assert _run("[][(oA:)ic+?]A:)ic+?", "hi!") == "hi!"
    assert _run(TRUTH, "0\n") == "0"

    from esolangs.languages.one_i import interpreter
    from tests.support.prepared_support import check_image_reuse

    check_image_reuse(
        "1 + i", "[][(oA:)ic+?]A:)ic+?", interpreter, "_prepare_source", monkeypatch
    )


def test_wiki_truth_machine_loops_on_one() -> None:
    io = ScriptedIO("1\n")
    machine = _Machine(TRUTH, io)
    for _ in range(60):
        machine.step()
    assert not machine.halted
    assert set(io.getvalue()) == {"1"}


def test_question_mark_peeks_and_takes_the_top_on_nonzero() -> None:
    # The wiki: i[]i? does not halt, []ii? does (it invokes the i).
    assert _run("i[]i?") == ""
    with pytest.raises(HaltError):
        _run("[]ii?")
    assert _run("[iic+p][ici*p]iic+?") == "0"
    machine = _Machine("[][]i?", ScriptedIO())
    for _ in range(4):
        machine.step()
    assert len(machine.stack) == 2


def test_rolls_swap_and_comparisons() -> None:
    # Stack 1 2 3 (top last): ( brings 1 up, ) sends 3 down, % swaps ends.
    three = "ici*ici*:+ici*::++"
    assert _run(three + "(ppp") == "132"
    assert _run(three + ")ppp") == "213"
    assert _run(three + "%ppp") == "123"
    assert _run("ici*iic+>p") == "0"
    assert _run("ici*iic+<p") == "1"
    with pytest.raises(HaltError):
        _run("iic+i>")


def test_printing() -> None:
    assert _run("ii+p") == "2i"
    assert _run("icp") == "-i"
    assert _run("ici*:+/p") == "0.5"
    assert _run("ici*ic+p") == "1 - i"
    assert _run("ici*ii++p") == "1 + 2i"

    def spelling(value: complex) -> str:
        return reference_text((Fraction(int(value.real)), Fraction(int(value.imag))))

    # Small Gaussian integers are represented exactly by Python complex.
    values = [complex(a, b) for a, b in product((-3, 0, 2, 65536), repeat=2)]
    for left, right, (opcode, evaluate) in product(
        values, values, (("+", add), ("*", mul))
    ):
        stdin = f"{spelling(left)}\n{spelling(right)}\n"
        assert _run(f"DD{opcode}p", stdin) == spelling(evaluate(left, right))

    for value in values:
        stdin = spelling(value) + "\n"
        assert _run("Dcp", stdin) == spelling(value.conjugate())
        assert _run("[ici*p][ii*p]D?", stdin) == ("-1" if value else "1")


def test_bytes_and_eof() -> None:
    assert _run("ici*i+o") == "\x01"
    assert _run("Ap", "") == "i"
    with pytest.raises(EOFError):
        _run("B", "")


def test_errors_halt() -> None:
    for code in ("p", "[]p", "iic+/", "iic+l", "i[]+", "iic+?"):
        with pytest.raises(HaltError):
            _run(code)


@pytest.mark.parametrize("code", ["x", "[", "]", "i]["])
def test_malformed_programs_raise(code: str) -> None:
    with pytest.raises(ValueError, match="1 \\+ i"):
        run(code, ScriptedIO())


def test_reciprocal_of_a_complex_number() -> None:
    assert _run("D/p", "3 - 4i\n") == "0.12 + 0.16i"


def test_mixing_an_inexact_number_with_an_exact_one() -> None:
    # e leaves floating point; i + or i * then mixes it with an exact value.
    assert _run("iei+p") == "0.5403023058681398 + 1.8414709848078965i"
    assert _run("iei*p") == "-0.8414709848078965 + 0.5403023058681398i"
    keys = []
    for zero, angle in ((0.0, pi), (-0.0, -pi)):
        machine = _Machine("lp", ScriptedIO())
        machine.values.append(complex(-1, zero))
        keys.append(machine.snapshot())
        written = WrittenState(machine.workspace_snapshot())
        machine.step()
        captured = machine.workspace_snapshot()
        assert captured.parts[1] == (
            WorkspaceVariant("inexact", (pack("!dd", 0, angle),)),
        )
        written.sample(captured)
        machine.step()
        written.sample(machine.workspace_snapshot())
        assert written.bits == 131
        assert machine.io.getvalue() == f"{angle}i"
    assert keys[0] != keys[1]
    proof = termination_observed("1 + i", "ie[i?]i?", "", 5)
    assert not proof.decision.halts
    assert proof.decision.commands == 9
    with guarded_worker():
        assert (
            _isolated.termination_result_isolated("1 + i", "ie[i?]i?", "", 5) == proof
        )


def test_equal_reals_are_neither_above_nor_below() -> None:
    assert _run("ici*ici*<p") == "1"
    assert _run("ici*ici*>p") == "1"


def test_bytes_take_the_imaginary_part_from_256() -> None:
    assert _run("Do", "255i\n") == "\x00"
    assert _run("Do", "256i\n") == "\x00\x00"
    assert _run("Do", "257i\n") == "\x00\x01"


def test_zero_to_a_non_integer_power_halts() -> None:
    with pytest.raises(HaltError):
        _run("DD^", "0\n-0.5\n")
