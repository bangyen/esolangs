"""/// and Subleq execution, dialects, and linear source regressions."""

import random

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.slashes import _Machine as SlashMachine
from esolangs.interpreters.other.slashes import run as run_slashes
from esolangs.interpreters.tape_based.subleq import run as run_subleq
from esolangs.tools.helpers import TEMPLATE_CHAR, fill_runs
from esolangs.tools.slashes import slashes
from esolangs.tools.subleq import subleq
from tests.witness_tables import witnesses


@pytest.mark.medium
@pytest.mark.parametrize("language", ["slashes", "subleq"])
def test_all_three_input_tables(language: str) -> None:
    for n in range(1, 4):
        for table in witnesses(n):
            code = slashes(table) if language == "slashes" else subleq(table)
            for row in range(1 << n):
                bits = [int(c) for c in f"{row:0{n}b}"]
                io = ScriptedIO("" if language == "slashes" else f"{row:0{n}b}")
                if language == "slashes":
                    run_slashes(
                        fill_runs(code, TEMPLATE_CHAR, (("a", "b"),) * n, bits), io
                    )
                else:
                    run_subleq(code, io)
                assert io.getvalue() == table[row]


@pytest.mark.parametrize("generator", [slashes, subleq])
def test_rendered_scaling(generator) -> None:
    sizes = []
    for n in (8, 10, 12):
        rng = random.Random(1729)
        table = "".join(str(rng.randrange(2)) for _ in range(1 << n))
        sizes.append(len(generator(table)))
    assert (sizes[2] - sizes[1]) / (sizes[1] - sizes[0]) <= 4.4


@pytest.mark.parametrize(
    ("code", "expected"),
    [(r"a\/b\\", "a/b\\"), ("/a/b/aaa", "bbb"), ("/a/", ""), ("/a", "")],
)
def test_slashes_conventions(code: str, expected: str) -> None:
    io = ScriptedIO()
    run_slashes(code, io)
    assert io.getvalue() == expected


def test_slashes_escaped_pattern() -> None:
    io = ScriptedIO()
    run_slashes(r"/a\/b/c/a/b", io)
    assert io.getvalue() == "c"
    run_slashes("/a\\", io)
    assert io.getvalue() == "c"


def test_slashes_divergence_controls() -> None:
    empty = SlashMachine("///", ScriptedIO())
    empty.step()
    before = empty.snapshot()
    empty.step()
    assert empty.snapshot() == before
    assert not empty.halted
    growth = SlashMachine("/a/aa/a", ScriptedIO())
    growth.step()
    growth.step()
    assert growth.state[0] == "aa"
    assert not growth.halted


def test_subleq_direct_jump_and_output() -> None:
    io = ScriptedIO()
    run_subleq("9 -1 3 10 -1 6 0 0 -1 72 105", io)
    assert io.getvalue() == "Hi"


def test_subleq_input_and_eof() -> None:
    code = "-1 9 3 9 -1 6 0 0 -1 0"
    io = ScriptedIO("A")
    run_subleq(code, io)
    assert io.getvalue() == "A"
    with pytest.raises(EOFError):
        run_subleq(code, ScriptedIO())


def test_subleq_truncated_instruction() -> None:
    with pytest.raises(HaltError):
        run_subleq("0 0", ScriptedIO())


@pytest.mark.parametrize("code", ["-1 -2 0", "-2 0 0", "0 -2 0"])
def test_subleq_rejects_negative_data_addresses(code: str) -> None:
    with pytest.raises(ValueError, match="Subleq"):
        run_subleq(code, ScriptedIO("A"))


def test_subleq_zero_extended_memory() -> None:
    run_subleq("10 10 -1", ScriptedIO())


def test_slashes_trailing_escape() -> None:
    io = ScriptedIO()
    run_slashes("\\", io)
    assert io.getvalue() == ""
    run_slashes("/a/\\", io)
    assert io.getvalue() == ""


def test_slashes_literal_dollar_and_serialized_template() -> None:
    import esolangs
    from esolangs.exceptions import TemplateError

    assert esolangs.run("///", "/a/$/a") == "$"
    assert esolangs.run("Slashalash", "$", max_steps=20) == "$"
    with pytest.raises(TemplateError, match="unfilled"):
        esolangs.run("///", str(esolangs.generate("///", "01")))
    partial = str(esolangs.generate("///", "0110")).replace("$", "a", 1)
    with pytest.raises(TemplateError, match="unfilled"):
        esolangs.run("///", partial)


@pytest.mark.parametrize("tail", ["$", ">qAqB", "x>qAqB", "$>qAq", "$>qAqZ", "$>qA"])
def test_slashes_template_recognition_rejects_noncanonical_tails(tail: str) -> None:
    from esolangs.tools.slashes import _DECODE, _UNARY, _is_unfilled_template

    assert not _is_unfilled_template(_UNARY + _DECODE + tail)


def test_slashes_template_recognition_rejects_changed_prefix() -> None:
    from esolangs.tools.slashes import _is_unfilled_template

    assert not _is_unfilled_template("x" + slashes("01"))
