"""Factor through the shared API, CLI and machinery."""

from pathlib import Path

import pytest

import esolangs
from tests.scripts.script_support import load


class TestFactorHasNoDigitBudget:
    """Its refusal named ``max_digits``, a knob the public API never had."""

    @pytest.mark.slow
    def test_the_arity_that_used_to_refuse_builds(self) -> None:
        """Dense n=13 was the 500000-digit refusal; this table is 460907 digits now."""
        import random

        rng = random.Random(7)
        table = "".join(rng.choice("01") for _ in range(2**13))
        program = esolangs.generate("Factor", table)
        assert program.isdigit()
        assert len(program) > 460_000


@pytest.mark.medium
def test_transitive_interpreter_inlined(tmp_path: Path) -> None:
    """Factor's bundle inlines the brainfuck interpreter it depends on."""
    bundle_one = load(Path(__file__).parents[2] / "scripts/bundle_one.py")
    out = tmp_path / "factor.py"
    bundle_one.bundle("Factor", bundle_one.Source(None), out)
    assert "inlined from esolangs/interpreters/tape_based/brainfuck.py" in (
        out.read_text()
    )
