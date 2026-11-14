"""/// execution, dialects, and linear source regressions."""

import random

import pytest

import esolangs
from esolangs._bindings import TEMPLATE_CHAR, fill_runs
from esolangs.exceptions import TemplateError
from esolangs.languages.slashes import interpreter as native
from esolangs.languages.slashes.generator import (
    _DECODE,
    _UNARY,
    slashes,
)
from esolangs.languages.slashes.tests.template_shape import _is_unfilled_template
from esolangs.runtime.io import ScriptedIO
from tests.support.witness_tables import witnesses


@pytest.mark.medium
def test_all_three_input_tables() -> None:
    for n in range(1, 4):
        for table in witnesses(n):
            code = slashes(table)
            for row in range(1 << n):
                bits = [int(c) for c in f"{row:0{n}b}"]
                io = ScriptedIO("")
                native.run(fill_runs(code, TEMPLATE_CHAR, (("a", "b"),) * n, bits), io)
                assert io.getvalue() == table[row]


def test_rendered_scaling() -> None:
    sizes = []
    for n in (8, 10, 12):
        rng = random.Random(1729)
        table = "".join(str(rng.randrange(2)) for _ in range(1 << n))
        sizes.append(len(slashes(table)))
    assert (sizes[2] - sizes[1]) / (sizes[1] - sizes[0]) <= 4.4


@pytest.mark.parametrize(
    ("code", "expected"),
    [(r"a\/b\\", "a/b\\"), ("/a/b/aaa", "bbb"), ("/a/", ""), ("/a", "")],
)
def test_slashes_conventions(code: str, expected: str) -> None:
    io = ScriptedIO()
    native.run(code, io)
    assert io.getvalue() == expected


def test_slashes_escaped_pattern() -> None:
    io = ScriptedIO()
    native.run(r"/a\/b/c/a/b", io)
    assert io.getvalue() == "c"
    native.run("/a\\", io)
    assert io.getvalue() == "c"


def test_slashes_divergence_controls() -> None:
    from esolangs.languages.slashes.tests.oracle_checks import check_raw_slashes

    check_raw_slashes()
    empty = native._Machine("///", ScriptedIO())
    empty.step()
    before = empty.snapshot()
    empty.step()
    assert empty.snapshot() == before
    assert not empty.halted
    growth = native._Machine("/a/aa/a", ScriptedIO())
    growth.step()
    growth.step()
    assert growth.state[0] == "aa"
    assert not growth.halted


def test_slashes_trailing_escape() -> None:
    io = ScriptedIO()
    native.run("\\", io)
    assert io.getvalue() == ""
    native.run("/a/\\", io)
    assert io.getvalue() == ""


def test_slashes_literal_dollar_and_serialized_template() -> None:
    assert esolangs.run("///", "/a/$/a").output == "$"
    assert (
        esolangs.run(
            "Slashalash", "$", limits=esolangs.ExecutionLimits(max_steps=20)
        ).output
        == "$"
    )
    template = esolangs.generate("///", "01")
    restored = esolangs.from_json("///", esolangs.to_json("///", template))
    with pytest.raises(TemplateError, match="fill the template"):
        esolangs.run("///", restored)
    partial = esolangs.generate("///", "0110").source.replace("$", "a", 1)
    io = ScriptedIO()
    native.run(partial, io)
    assert esolangs.run("///", partial).output == io.getvalue()


@pytest.mark.parametrize("tail", ["$", ">qAqB", "x>qAqB", "$>qAq", "$>qAqZ", "$>qA"])
def test_slashes_template_recognition_rejects_noncanonical_tails(tail: str) -> None:
    assert not _is_unfilled_template(_UNARY + _DECODE + tail)


def test_slashes_template_recognition_rejects_changed_prefix() -> None:
    assert not _is_unfilled_template("x" + slashes("01"))
