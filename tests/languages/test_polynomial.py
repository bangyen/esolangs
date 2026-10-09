"""Polynomial through the shared API, CLI and machinery."""

import pytest

import esolangs
from tests.generator_support import evaluate_generated


class TestADeliberateRefusalIsAnEsolangError:
    """The package promises it, and the refusals that broke the promise."""

    def test_it_is_still_a_value_error(self) -> None:
        """Callers catching ValueError must not be broken by the new class."""
        assert issubclass(esolangs.GeneratorCapError, ValueError)
        assert issubclass(esolangs.GeneratorCapError, esolangs.EsolangError)

    @pytest.mark.slow
    def test_no_private_name_leaks_into_a_message(self) -> None:
        """A cap message renders its constant's value, not its name."""
        with pytest.raises(esolangs.GeneratorCapError) as exc:
            esolangs.generate("Polynomial", _big_table())
        assert "_POLYNOMIAL" not in str(exc.value)


def _big_table(arity: int = 11) -> str:
    """Return a dense table at ``arity``, past the cap it is used for."""
    import random

    rng = random.Random(7)
    return "".join(rng.choice("01") for _ in range(2**arity))


def test_the_refusal_is_catchable_at_the_size_it_refuses() -> None:
    """A refusal past the sweep's bound, at the first arity that triggers it."""
    with pytest.raises(esolangs.GeneratorCapError, match="cost"):
        esolangs.generate("Polynomial", _big_table(11))


def test_it_is_catchable_through_evaluate_too() -> None:
    """NoComment's leaked through ``evaluate`` identically."""
    with pytest.raises(esolangs.GeneratorCapError):
        evaluate_generated("Polynomial", _big_table(11))
