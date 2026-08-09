"""Unit tests for the Taglate interpreter.

Taglate is a queue-based language: the first line seeds a queue of integers
(0-65535, wrapping), and the remaining lines hold commands (arithmetic,
rotate/discard, loops, character I/O, the ``j`` counter trick, and the
Google Translate URL ``t`` command).
"""

import io
from contextlib import redirect_stdout
from unittest.mock import patch

import esolangs
from esolangs.exceptions import HaltError
from esolangs.interpreters.other.taglate import run
from esolangs.interpreters.io import IO


def run_and_capture(code: list[str], inputs: list[str] | None = None) -> str:
    buffer = io.StringIO()
    with patch("builtins.input", side_effect=inputs or []), redirect_stdout(buffer):
        run(code, IO())
    return buffer.getvalue()


class TestTaglate:
    def test_output_hello(self) -> None:
        assert run_and_capture(["Hi", "ii"]) == "Hi"

    def test_add(self) -> None:
        # ord('1') + ord('2') = 99 = 'c'
        assert run_and_capture(["12", "ai"]) == "c"

    def test_subtract_wraps(self) -> None:
        # ord('1') - ord('2') = -1, wrapping to 65535
        assert run_and_capture(["12", "bi"]) == chr(65535)

    def test_multiply(self) -> None:
        assert run_and_capture(["11", "ci"]) == chr(49 * 49)

    def test_divide(self) -> None:
        assert run_and_capture(["93", "di"]) == chr(57 // 51)

    def test_divide_by_zero_halts(self) -> None:
        """Division by zero is invalid, so the interpreter halts on it."""
        import pytest

        with pytest.raises(HaltError):
            run_and_capture(["1\x00", "di"])

    def test_rotate(self) -> None:
        assert run_and_capture(["12", "ei"]) == "2"

    def test_discard(self) -> None:
        assert run_and_capture(["12", "fi"]) == "2"

    def test_loop_outputs_until_empty(self) -> None:
        assert run_and_capture(["11", "gyigz"]) == "11"

    def test_loop_skipped_when_front_zero(self) -> None:
        assert run_and_capture(["\x001", "gyigz"]) == ""

    def test_j_decrements_nonzero(self) -> None:
        assert run_and_capture(["1", "ji"]) == "0"

    def test_j_zero_becomes_one(self) -> None:
        assert run_and_capture(["11", "bji"]) == chr(1)

    def test_input_appends_to_back(self) -> None:
        assert run_and_capture(["0", "fhi"], inputs=["x"]) == "x"

    def test_empty_program(self) -> None:
        assert run_and_capture([]) == ""
        assert run_and_capture([""]) == ""

    def test_generator_round_trips(self) -> None:
        for text in ("Hello, World!", "Hi", "123", "\x00"):
            assert esolangs.run("Taglate", esolangs.generate("Taglate", text)) == text

    def test_generator_rejects_newlines(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="newline"):
            esolangs.generate("Taglate", "a\nb")

    def test_google_translate_url(self) -> None:
        expected = "https://translate.google.com/?sl=en&tl=es&text=Hi&op=translate"
        program = "Hi" + "\n" + "t" + "i" * len(expected)
        assert esolangs.run("Taglate", program) == expected

    def test_google_translate_url_encodes_unsafe_chars(self) -> None:
        expected = "https://translate.google.com/?sl=en&tl=es&text=a%20b&op=translate"
        program = "a b" + "\n" + "t" + "i" * len(expected)
        assert esolangs.run("Taglate", program) == expected

    def test_lone_g_is_ignored(self) -> None:
        assert run_and_capture(["1", "gi"]) == "1"

    def test_unmatched_loop_markers_halt(self) -> None:
        assert run_and_capture(["\x001", "gy"]) == ""
        assert run_and_capture(["1", "gz"]) == ""
