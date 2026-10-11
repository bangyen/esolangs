"""Factor through the shared API, CLI and machinery."""

import pytest

import esolangs


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
