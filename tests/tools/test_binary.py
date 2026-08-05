"""Unit tests for the binary function generator tool."""

from esolangs.tools.binary import convert


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
