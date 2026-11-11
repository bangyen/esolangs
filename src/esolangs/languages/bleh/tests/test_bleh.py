"""Tests for the Bleh interpreter."""

from itertools import product

import pytest

from esolangs.languages.bleh.interpreter import _Machine, run
from tests.interpreters.oracle_support import check_terminal
from tests.interpreters.runner import native_runner

#: The page's pattern table: pattern, arguments, ``1`` if they match.
TABLE = [
    ("1", "1", "1"),
    ("0", "1", "0"),
    ('"a"', "01100001", "1"),
    ('"a"', "1100001", "0"),
    ("x", "1", "1"),
    ("[a, b]", "11", "1"),
    ("[_, b]", "10", "1"),
    ("[a, b]", "101", "0"),
    ("[a, b..]", "101", "1"),
    ("x[_, ..]", "1011", "1"),
    ("x[_, ..]", "[]", "0"),
    ("x[a, b..]", "1011", "1"),
    ("[x, x]", "00", "1"),
    ("[x, x]", "11", "1"),
    ("[x, x]", "10", "0"),
    ("x, 1", "1, 1", "1"),
    ("x, 1", "1, 0", "0"),
    ("x..", "1, 0, 10, 1", "1"),
]


_out = native_runner(run)


@pytest.mark.parametrize(("pattern", "args", "expected"), TABLE)
def test_the_page_pattern_table(pattern: str, args: str, expected: str) -> None:
    code = (
        f"^:std::io; main := f({args}); f : {pattern} = io::debug 1 : .. = io::debug 0;"
    )
    assert _out(code) == expected


def test_a_forced_argument_is_read_once(monkeypatch) -> None:
    """Call by need: ``x`` is forced by the literal and reused, not reread."""
    code = '^:std::io; main := f(io::next()); f : "a" = 1 : x = io::print(x, x);'

    def check(program, expected, stdin="", consumed=0):
        check_terminal(
            _Machine,
            program,
            stdin,
            lambda m: (
                (m.state.control.value, m.state.kont, m.ahead) if m.halted else None
            ),
            (("", None, None), True, expected, consumed, consumed),
            cap=256,
        )

    # The first and last bits must agree. Reprinting the bound middle
    # checks that the rest pattern consumes precisely the intervening bits.
    for length in range(6):
        for parts in product("01", repeat=length):
            bits = "".join(parts)
            program = (
                f"^:std::io; main := f({bits or '[]'}); "
                "f : [x, middle.., x] = io::debug(middle, middle) "
                ": _ = io::debug 0;"
            )
            expected = "0"
            if length >= 2 and bits[0] == bits[-1]:
                expected = bits[1:-1] * 2 or "[]"
            check(program, expected)
            assert _out(program) == expected, bits

    for bits in ("001", "010", "01101", "01110"):
        program = (
            f"^:std::io; main := f({bits}); "
            "f : [x, middle.., x, 1] = io::debug(middle) "
            ": _ = io::debug 0;"
        )
        expected = (
            (bits[1:-2] or "[]") if bits[0] == bits[-2] and bits[-1] == "1" else "0"
        )
        check(program, expected)
        assert _out(program) == expected, bits

    for char, sentinel in product(("b", "é", "😀"), ("z", "!")):
        assert _out(code, char + sentinel) == char * 2
        check(code, char * 2, char + sentinel, 1)

    from esolangs.languages.bleh import interpreter
    from tests.support.prepared_support import check_image_reuse

    check_image_reuse(
        "Bleh",
        code,
        interpreter,
        "_prepare_source",
        monkeypatch,
        cases=(("bz", "bb"), ("cz", "cc"), ("dz", "dd")),
    )
