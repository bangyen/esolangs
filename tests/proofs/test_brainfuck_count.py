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


def _regular_rewrite_variants() -> list[tuple[str, str]]:
    """Instantiate all fifteen monitors with their stated body restrictions."""
    import re

    from tests.proofs._brainfuck_count import regular_patterns

    stationary_rf = ("", "+-", ".", "[-]", ".[--]", ".[-]")
    stationary_io = ("", ",", "[,-]", ".,", ",[-]", ".[,-]")
    confined_rf = ("", ".", "[-]", ">+<", ".>--<", ">.+<")
    confined_io = ("", ",", "[,-]", ">+<", ".>,<", ">.,+<")
    silent = ("", "+", "[--]", ">+<", "+[-]", ">-<")
    halting = ("", "+", "[-]", ">+<", "+[-]", ">+-<")
    readfree = ("", "-", "+.", ">+<", "[-]", "<>")
    body = ("", "+", ",", ">+<", "[-]", "<,>")
    cases = []
    for i in range(len(body)):
        s0, s1 = stationary_rf[i], stationary_io[i]
        f0, f1, ni, h = confined_rf[i], confined_io[i], silent[i], halting[i]
        loop = "[" + ("", ",", ".-", "+-", ",.-", "--")[i] + "]"
        p0, p1 = ".>" + f0 + "<", ".>" + f1 + "<"
        residue = "+" * (256 if i == 5 else i)
        command = ".+-"[i % 3]
        increment = "+-"[i % 2]
        variants = [
            (">[]<" + s0 + ">", s0 + ">[]"),
            ("[]>" + f0 + "<", ">" + f0 + "<[]"),
            ("[-]>" + f1 + "<", ">" + f1 + "<[-]"),
            (">[-]<" + s1 + ">", s1 + ">[-]"),
            (">" + ni + "<" + command, command + ">" + ni + "<"),
            (">" + h + "<,", ",>" + h + "<"),
            (">" + f1 + "<" + increment, increment + ">" + f1 + "<"),
            ("[" + "+" * i + "[-]" + residue + "]", "[-]" if i in (0, 5) else "[]"),
            (loop + ">" + h + "<", ">" + h + "<" + loop),
            (">" + loop + "<" + "+" * i + ">", "+" * i + ">" + loop),
            (
                "[" + readfree[i] + "[" + readfree[-i - 1] + "].." + increment + ".]",
                "[]",
            ),
            (">" + f1 + "<>", ">" + f1),
            ("[-]" + p1 + "[.,].", "[-]" + p1 + "."),
            ("[" + p0 + "[],.>]", "[]"),
            ("[." + body[i] + "].", ".[" + body[i] + ".]"),
        ]
        for pattern, (left, right) in zip(regular_patterns(), variants, strict=True):
            assert re.search(pattern, left), (pattern, left)
            assert left != right
            # Every instance decreases the paper's shortlex order.
            order = {char: index for index, char in enumerate(".,-+<>[]")}
            assert (len(right), tuple(order[c] for c in right)) < (
                len(left),
                tuple(order[c] for c in left),
            )
        cases.extend(variants)
    return cases


def _local_rewrite_variants() -> list[tuple[str, str]]:
    """Exercise cancellation, dead stores, preserved-cell loops and excursions."""
    cases = [(word, "") for word in ("+-", "-+", "><")]
    cases += [(word, "[-]") for word in ("+[-]", "-[-]")]
    cases += [(word, ",") for word in ("+,", "-,", "[-],")]
    cases += [("[" + "+" * k + "]", "[" + "-" * k + "]") for k in range(1, 5)]
    cases.append(("[].", ".[]"))
    preserved = ("", ".", "+-", ">+<", ".>.<")
    for first in preserved:
        cases.append(("[-]" + first + "[+,.]", "[-]" + first))
        if first:
            cases.extend([("[" + first + "]", "[]"), ("[]" + first, first + "[]")])
        for second in preserved:
            cases.append(("[" + first + "[" + second + "],.>]", "[]"))
    for excursion in (">+<", ">>+<<", ">+-<"):
        cases.extend((excursion + command, command + excursion) for command in ".,+-")
        cases.append(("[-]" + excursion, excursion + "[-]"))
    for excursion in (">.<", ">,<", ">.,<"):
        cases.extend((excursion + command, command + excursion) for command in "+-")
        cases.append(("[-]" + excursion, excursion + "[-]"))
    for body in ("", "+", ".,", ">+<"):
        cases.append((">" + body + "<>", ">" + body))
    return cases


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
    stdin = "".join(chr(byte) for byte in (*tape, *remaining))
    for left, right in (
        *_REWRITES,
        *_regular_rewrite_variants(),
        *_local_rewrite_variants(),
    ):
        lhs = _observe(prefix + left + ".<.>.", stdin)
        rhs = _observe(prefix + right + ".<.>.", stdin)
        assert lhs == rhs, (left, right, tape, start, remaining, lhs, rhs)


@pytest.mark.medium
def test_io_commutation_negative_controls() -> None:
    prefix = ",>,>,>,<<<"
    stdin = "\x00\x01\x00\x00"
    assert _observe(prefix + ">[]<,", stdin)[0] == "diverge"
    assert _observe(prefix + ",>[]<", stdin)[0] == "eof"
    assert _observe(prefix + ">.<.", stdin)[1] != _observe(prefix + ".>.<", stdin)[1]
    # Moving a read before a possibly diverging silent excursion changes EOF.
    assert _observe(">[--]<,", "")[0] == "eof"
    assert _observe(">+[--]<,", "")[0] == "diverge"
    assert _observe(",>+[--]<", "")[0] == "eof"
    # A read-free prefix is insufficient: the tested cell must be preserved.
    assert _observe("+[-[]].", "")[0] == "halt"
    assert _observe("+[].", "")[0] == "diverge"
    # Clipping forbids cancelling <> at cell zero.
    assert _observe(prefix + "<>.", stdin) != _observe(prefix + ".", stdin)


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
    from scripts.grammar_certificate import check_grammar
    from tests.proofs._brainfuck_count import local_patterns, regular_patterns

    assert check_grammar(
        rows, ".,-+<>[]", sorted(local_patterns()), regular_patterns()
    ) >= len(rows)
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


def test_independent_grammar_rejects_legal_but_wrong_transitions() -> None:
    from scripts.grammar_certificate import check_grammar

    # The spectral checker can accept this matrix, but it forbids no factors.
    with pytest.raises(ValueError, match="grammar mismatch on '\\+-'"):
        check_grammar([[0, 0]], "+-", ["+-"], [])
    with pytest.raises(ValueError, match="grammar mismatch"):
        check_grammar([[-1, 0]], "+-", [], [])
    with pytest.raises(ValueError, match="budget"):
        check_grammar([[0, 0]], "+-", [], [r"\+\+-"], state_cap=1)
    with pytest.raises(ValueError, match="empty regular"):
        check_grammar([[0]], "+", [], [r"\+*"])


def test_independent_position_monitor_matches_regex_engine() -> None:
    import itertools
    import re

    from scripts.grammar_certificate import _RegexMonitor

    alphabet = "+-[]"
    patterns = [r"\[\](?:\+|\[-*\])*\+", r"\[[+\-]*\]\+", r"(?:\+-|\[\])*-"]
    for pattern in patterns:
        monitor = _RegexMonitor(pattern, alphabet)
        for length in range(6):
            for chars in itertools.product(alphabet, repeat=length):
                state = 0
                for char in chars:
                    state = monitor.transitions(state)[alphabet.index(char)]
                    if state == -1:
                        break
                assert (state == -1) == bool(re.search(pattern, "".join(chars)))


def test_independent_literal_monitor_matches_substring_oracle() -> None:
    import itertools

    from scripts.grammar_certificate import _LiteralMonitor

    factors = ["aaba", "bab", "aba", "bba"]
    monitor = _LiteralMonitor(factors, "ab")
    for length in range(8):
        for chars in itertools.product("ab", repeat=length):
            state = 0
            for char in chars:
                state = monitor.rows[state]["ab".index(char)]
                if monitor.bad[state]:
                    break
            assert monitor.bad[state] == any(
                factor in "".join(chars) for factor in factors
            )


@pytest.mark.parametrize(
    ("factors", "regexes", "message"),
    [
        ([""], [], "literal"),
        (["z"], [], "literal"),
        ([], ["["], "invalid regular"),
        ([], ["z"], "outside alphabet"),
        ([], ["[a-z]"], "character class"),
        ([], ["(?i:a)"], "flags"),
        ([], ["(?i)a"], "flags"),
        ([], ["a+"], "operator"),
    ],
)
def test_independent_grammar_rejects_unsupported_factors(
    factors, regexes, message
) -> None:
    from scripts.grammar_certificate import check_grammar

    with pytest.raises(ValueError, match=message):
        check_grammar([[0, 0]], "ab", factors, regexes)


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
