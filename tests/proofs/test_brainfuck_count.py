"""Sound rewrites and exact Brainfuck behaviour-count certificates."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.brainfuck import _Machine


def _result(code: str) -> tuple[str, str]:
    """Execute a closed witness; a repeated complete state proves divergence."""
    io = ScriptedIO()
    machine = _Machine(code, io)
    seen: set[tuple[object, ...]] = set()
    for _ in range(64):
        if machine.halted:
            return "halt", io.getvalue()
        state = machine.snapshot()
        if state in seen:
            return "diverge", ""
        seen.add(state)
        machine.step()
    raise AssertionError("witness neither halted nor repeated a state")


@pytest.mark.parametrize("prefix", ["-", "[-]"])
def test_read_free_prefix_can_zero_the_empty_loop_test(prefix: str) -> None:
    # Both withdrawn certificates discarded [Y[] for read-free balanced Y.
    assert _result(f"+[{prefix}[]].") == ("halt", "\x00")
    assert _result("+[].") == ("diverge", "")


def test_cell_preservation_is_the_missing_hypothesis() -> None:
    assert _result("+[>+<[]].") == _result("+[].") == ("diverge", "")


def _observe(code: str, stdin: str) -> tuple[str, str, tuple[int, ...], int, int]:
    io = ScriptedIO(stdin)
    machine = _Machine(code, io)
    seen: set[tuple[object, ...]] = set()
    for _ in range(8192):
        if machine.halted:
            tape = list(machine.tape)
            while tape and tape[-1] == 0:
                tape.pop()
            return "halt", io.getvalue(), tuple(tape), machine.ptr, io.reads
        state = machine.snapshot()
        if state in seen:
            return "diverge", "", (), 0, 0
        seen.add(state)
        try:
            machine.step()
        except EOFError:
            return "eof", io.getvalue(), (), 0, io.reads
    raise AssertionError("witness neither halted, reached EOF, nor repeated a state")


# One representative per regular monitor; halting cases compare tape, pointer,
# input consumption, and output. EOF and divergence use the paper's observations.
_REWRITES = (
    ("[]>.[-]>+<<", ">.[-]>+<<[]"),
    (">[]<.[.-]>", ".[.-]>[]"),
    ("[-]>.,>[-]<<", ">.,>[-]<<[-]"),
    (">[-]<.[,-]>", ".[,-]>[-]"),
    (">[--]>+<<.", ".>[--]>+<<"),
    (">[-]>+<<,", ",>[-]>+<<"),
    (">.,[,-]<+", "+>.,[,-]<"),
    ("[++[-]--]", "[]"),
    ("[.,-]>[-]>+<<", ">[-]>+<<[.,-]"),
    (">[.,-]<++>", "++>[.,-]"),
    ("[>+<[-].+..]", "[]"),
    (">[,-]>+<<>", ">[,-]>+<"),
    ("[-].>.,<[,].", "[-].>.,<."),
    ("[.>.[-]<[],-]", "[]"),
    ("[.>.,<-].", ".[>.,<-.]"),
)


@pytest.mark.medium
@pytest.mark.parametrize(
    "tape", [(0, 1, 2, 0), (1, 0, 2, 0), (2, 255, 0, 1), (255, 2, 1, 0)]
)
@pytest.mark.parametrize("start", [0, 1])
@pytest.mark.parametrize("remaining", [(), (1, 0, 1)])
def test_regular_rewrite_execution(
    tape: tuple[int, ...], start: int, remaining: tuple[int, ...]
) -> None:
    prefix = ",>,>,>,<<<" + ">" * start
    stdin = "".join(chr(byte) + "\n" for byte in (*tape, *remaining))
    for left, right in _REWRITES:
        lhs = _observe(prefix + left + ".<.>.", stdin)
        rhs = _observe(prefix + right + ".<.>.", stdin)
        assert lhs == rhs, (left, right, tape, start, remaining, lhs, rhs)


@pytest.mark.medium
def test_io_commutation_negative_controls() -> None:
    prefix = ",>,>,>,<<<"
    stdin = "\x00\n\x01\n\x00\n\x00\n"
    assert _observe(prefix + ">[]<,", stdin)[0] == "diverge"
    assert _observe(prefix + ",>[]<", stdin)[0] == "eof"
    assert _observe(prefix + ">.<.", stdin)[1] != _observe(prefix + ".>.<", stdin)[1]


@pytest.mark.medium
def test_clear_suffix_uses_byte_residue() -> None:
    assert _observe("+[++]", "")[0] == "diverge"
    assert _observe("+[--]", "")[0] == "diverge"
    assert _observe("+[++[-]" + "+" * 256 + "]", "") == _observe("+[-]", "")


@pytest.mark.medium
def test_regular_certificate() -> None:
    from tests.proofs._brainfuck_count import accepts, certificate, check_certificate

    rows, vector = certificate()
    check_certificate(rows, vector)
    from scripts.perron_certificate import check_certificate as independent_check
    from tests.proofs._brainfuck_count import ALPHABET, BOUND

    independent_check(rows, vector, BOUND, ALPHABET)
    corrupted = list(vector)
    corrupted[0] = 0
    with pytest.raises(ValueError, match="vector"):
        independent_check(rows, corrupted, BOUND, ALPHABET)
    with pytest.raises(ValueError, match="spectral"):
        independent_check(rows, vector, (1, 1), ALPHABET)
    corrupted_rows = [list(row) for row in rows]
    corrupted_rows[0][0] = len(rows)
    with pytest.raises(ValueError, match="transition"):
        independent_check(corrupted_rows, vector, BOUND, ALPHABET)
    # These are behaviours that the discarded grammar incorrectly excluded.
    assert accepts(rows, "[]")
    assert accepts(rows, "+[-[]].")
    assert accepts(rows, ">[]<,")
    assert accepts(rows, ">.<.")
    assert not accepts(rows, "[.+].")
    assert accepts(rows, ".[+.]")
    assert not accepts(rows, "[[.-]+]")
    with pytest.raises(AssertionError):
        check_certificate(rows, [1] * len(rows))


def test_factor_automaton_matches_regex_oracle() -> None:
    import itertools
    import re

    from tests.proofs._brainfuck_count import (
        ALPHABET,
        accepts,
        automaton,
        intersect,
        minimize,
    )

    factors = {"+-", "]["}
    patterns = [r"\[\](?:\.|>\+<)*\.", r"\[\.[+.,\-]*\]\."]
    direct = automaton(factors, patterns)
    product = minimize(automaton(factors, []))
    for pattern in patterns:
        product = intersect(product, minimize(automaton([], [pattern])))
    words = ["[]>+<.", "[]>+<>+<.", "[.+].", ".[]", "+[.,].."]
    words += [
        "".join(chars)
        for length in range(5)
        for chars in itertools.product(ALPHABET, repeat=length)
    ]
    for word in words:
        expected = not any(factor in word for factor in factors) and not any(
            re.search(pattern, word) for pattern in patterns
        )
        assert accepts(direct, word) == expected
        assert accepts(product, word) == expected
