"""Unit tests for the binary function generator tool."""

from unittest.mock import patch

import pytest

from esolangs.tools import binary
from esolangs.tools.binary import convert


class TestMain:
    def test_usage(self, capsys: pytest.CaptureFixture) -> None:
        with patch("sys.argv", ["esolangs.tools.binary"]):
            with pytest.raises(SystemExit):
                binary.main()
        assert "usage: python -m esolangs.tools.binary" in capsys.readouterr().out

    def test_bad_length(self, capsys: pytest.CaptureFixture) -> None:
        with patch("sys.argv", ["esolangs.tools.binary", "011"]):
            with pytest.raises(SystemExit):
                binary.main()
        assert "must be a power of 2" in capsys.readouterr().out

    def test_valid_table(self, capsys: pytest.CaptureFixture) -> None:
        with patch("sys.argv", ["esolangs.tools.binary", "0111"]):
            binary.main()
        program = capsys.readouterr().out
        assert program.startswith("'")
        assert "$30:@" in program

    def test_entry_point(self, capsys: pytest.CaptureFixture) -> None:
        """Running the module as __main__ dispatches to main()."""
        import runpy

        with patch("sys.argv", ["esolangs.tools.binary", "0110"]):
            runpy.run_module("esolangs.tools.binary", run_name="__main__")
        assert capsys.readouterr().out.startswith("'")


class TestConvert:
    def test_xor_matches_wiki(self) -> None:
        """The XOR gate output matches the example on esolangs.org."""

        def xor(a, b):
            return a ^ b

        expected = (
            "'           >  $30:@\n"
            "     >  2$~;#@\n"
            "            >  $31:@\n"
            ">2$~;#@       \n"
            "            >  $31:@\n"
            "     >  2$~;#@\n"
            "            >  $30:@"
        )
        assert convert(xor) == expected

    def test_single_argument(self) -> None:
        def not_gate(a):
            return 1 - a

        program = convert(not_gate)
        assert "@" in program
        assert "$3" in program

    def test_explicit_argument_count(self) -> None:
        def fn(*args):
            return args[0] and args[1]

        program = convert(fn, num=2)
        assert program.startswith("'")
