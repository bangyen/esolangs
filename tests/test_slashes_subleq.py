"""/// and Subleq execution, dialects, and linear source regressions."""

import random

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.subleq import run as run_subleq
from esolangs.tools.slashes import slashes
from esolangs.tools.subleq import subleq


def test_rendered_scaling() -> None:
    sizes = []
    for n in (8, 10, 12):
        rng = random.Random(1729)
        table = "".join(str(rng.randrange(2)) for _ in range(1 << n))
        sizes.append(len(subleq(table)))
    assert (sizes[2] - sizes[1]) / (sizes[1] - sizes[0]) <= 4.4


@pytest.mark.parametrize("code", ["-1 -2 0", "-2 0 0", "0 -2 0"])
def test_subleq_rejects_negative_data_addresses(code: str) -> None:
    with pytest.raises(ValueError, match="Subleq"):
        run_subleq(code, ScriptedIO("A"))


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
