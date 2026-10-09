"""Polynomial through the shared API, CLI and machinery."""

import pytest

import esolangs
from tests.test_answer_plumbing_refusals import _big_table


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
