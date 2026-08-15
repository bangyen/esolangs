"""Unit tests for the Trash interpreter."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.trash import run


def run_and_capture(code: str) -> str:
    io = ScriptedIO()
    run(code, io)
    return io.getvalue()


class TestTrash:
    def test_no_ts_prints_nothing(self) -> None:
        assert run_and_capture("5") == ""

    def test_no_ts_with_trailing_text_prints_nothing(self) -> None:
        assert run_and_capture("42abc") == ""

    def test_advance_one_prime(self) -> None:
        assert run_and_capture("t5") == "7"

    def test_advance_two_primes(self) -> None:
        assert run_and_capture("tt11") == "17"

    def test_advance_four_primes(self) -> None:
        assert run_and_capture("tttt3") == "13"

    def test_advance_from_thirteen(self) -> None:
        assert run_and_capture("tt13") == "19"

    def test_non_prime_start_prints_zero(self) -> None:
        assert run_and_capture("tt12") == "0"

    def test_start_value_one_prints_zero(self) -> None:
        assert run_and_capture("t1") == "0"

    def test_two_is_prime(self) -> None:
        """2 is the smallest prime (per the wiki), so t2 prints 3."""
        assert run_and_capture("t2") == "3"

    def test_leading_zeros(self) -> None:
        assert run_and_capture("t07") == "11"

    def test_trailing_characters_ignored(self) -> None:
        assert run_and_capture("tt5x") == "11"

    def test_chars_before_first_digit_ignored(self) -> None:
        assert run_and_capture("ab5") == ""

    def test_sign_before_digit_ignored(self) -> None:
        assert run_and_capture("t-5") == "7"

    def test_t_after_first_digit_ignored(self) -> None:
        assert run_and_capture("5t") == ""

    def test_malformed_no_digits(self) -> None:
        for code in ["", "t", "ttt", "abc", "  "]:
            with pytest.raises(ValueError, match="at least one digit"):
                run_and_capture(code)
