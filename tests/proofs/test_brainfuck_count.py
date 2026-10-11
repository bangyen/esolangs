"""Sound rewrites and exact Brainfuck behaviour-count certificates."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.brainfuck import _Machine
from esolangs.vm import run_until_halt_or_growth


def _sole_loop_word(word: str) -> bool:
    """Parse balanced words; reject a loop containing just one loop atom."""
    frames: list[list[str]] = [[]]
    for char in word:
        if char == "[":
            frames.append([])
        elif char == "]":
            if len(frames) == 1 or frames.pop() == ["loop"]:
                return False
            frames[-1].append("loop")
        else:
            frames[-1].append("letter")
    return len(frames) == 1


@pytest.mark.parametrize("letters", [5, 6])
def test_six_series_grammar_matches_balanced_words(letters: int) -> None:
    import itertools

    from tests.proofs._brainfuck_count import sole_loop_counts

    alphabet = "+-<>." + ("," if letters == 6 else "") + "[]"
    counts = [
        sum(
            _sole_loop_word("".join(word))
            for word in itertools.product(alphabet, repeat=n)
        )
        for n in range(6)
    ]
    assert sole_loop_counts(5, letters) == counts
    assert _sole_loop_word("+[-[]].")
    assert _sole_loop_word("[[]+]")
    assert not _sole_loop_word("[[+]]")
    assert not _sole_loop_word("[[]]")


def test_six_series_algebraic_identity_and_rate_bracket() -> None:
    from fractions import Fraction

    from tests.proofs._brainfuck_count import sole_loop_counts

    coefficients = sole_loop_counts(40)
    # x^2 P^2 - (1-6x)(1+x^2) P + 1+x^2 = 0.
    for n, coefficient in enumerate(coefficients):
        residual = -coefficient + int(n in (0, 2))
        if n >= 1:
            residual += 6 * coefficients[n - 1]
        if n >= 2:
            residual += (
                sum(coefficients[k] * coefficients[n - 2 - k] for k in range(n - 1))
                - coefficients[n - 2]
            )
        if n >= 3:
            residual += 6 * coefficients[n - 3]
        assert residual == 0
    # On 0 < x < 1/6, 1-6x decreases and 2x/sqrt(1+x^2) increases.
    for rate, sign in ((Fraction(798449, 100000), -1), (Fraction(798450, 100000), 1)):
        x = 1 / rate
        discriminant = (1 - 6 * x) ** 2 * (1 + x * x) - 4 * x * x
        assert 0 < x < Fraction(1, 6)
        assert sign * discriminant > 0


def _canonical(machine: _Machine) -> tuple[object, ...]:
    """Return the state up to translation of the bi-infinite tape.

    Cells outside the trimmed window are all zero on both sides, and every
    command addresses relative to the pointer, so two states equal here
    behave identically: a repeat proves divergence even while the run
    walks into fresh cells (``[+<-]`` leaves one behind each lap).
    """
    ind, ptr, tape, *_ = machine.snapshot()
    cells = [i for i, value in enumerate(tape) if value] + [ptr]
    low, high = min(cells), max(cells) + 1
    return (ind, ptr - low, tape[low:high], machine.io.position())


def _result(code: str) -> tuple[str, str]:
    """Execute a closed witness; a repeated complete state proves divergence."""
    io = ScriptedIO()
    machine = _Machine(code, io)
    seen: set[tuple[object, ...]] = set()
    for _ in range(64):
        if machine.halted:
            return "halt", io.getvalue()
        state = _canonical(machine)
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
        state = _canonical(machine)
        if state in seen:
            return "diverge", "", (), 0, 0
        seen.add(state)
        try:
            machine.step()
        except EOFError:
            return "eof", io.getvalue(), (), 0, io.reads
    # A walk that leaves a trail never repeats, even up to translation.  The
    # bi-infinite tape is mirror-symmetric, so the program with `<` and `>`
    # swapped halts exactly when this one does, and a leftward walk becomes
    # one the rightward growth certificate can prove.
    for program in (code, code.translate(str.maketrans("<>", "><"))):
        try:
            machine = _Machine(program, ScriptedIO(stdin))
            if not run_until_halt_or_growth(machine, 2_000):
                return "diverge", "", (), 0, 0
        except (TimeoutError, EOFError):
            pass
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
@pytest.mark.parametrize("tape", [(0, 1, 2, 0), (255, 2, 1, 0)])
@pytest.mark.parametrize("start", [1])
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
    # Clipping forbids cancelling <> at cell zero.
    assert _observe(prefix + "<>.", stdin) != _observe(prefix + ".", stdin)


@pytest.mark.medium
def test_clear_suffix_uses_byte_residue() -> None:
    assert _observe("+[++]", "")[0] == "diverge"
    assert _observe("+[--]", "")[0] == "diverge"
    assert _observe("+[++[-]" + "+" * 256 + "]", "") == _observe("+[-]", "")


# The depth-one monitors state `[.Y]. <-> .[Y.]`, `[W[Z]D] -> []` and
# `[P0[]G] -> []` for bodies of bracket depth at most one.  These controls
# execute the same rules with depth-two and depth-three bodies, so the side
# conditions hold below and above the stated bound.  A `,` in `Y` exercises
# the EOF convention; read-free W, Z, P0 cannot reach EOF by construction.
_DEPTH_ROTATION_BODIES = (
    "[-[+]]",  # depth 2, read-free
    ",[-[]]",  # depth 2, reads
    "[[[+]]]",  # depth 3, read-free
    "[[-],]",  # depth 2, reads
    "[[+[]]]",  # depth 3, diverges on a nonzero tested cell
    "[[--]]",  # depth 2, a left-hand side the depth-one monitor accepts
)
# `[W[Z]D] -> []`: W and Z are read-free balanced bodies, D holds a `+`/`-`.
_DEPTH_DIVERGENCE_BODIES = (
    ("", "[>+<]", "+.."),
    ("[+<-]", "", "..-"),
    ("[[+]]", "[-]", ".-"),
    ("", "[[-][+]]", "..+"),
    ("[+><-]", "[[-]]", "..-"),
    ("[[+][-]]", "", "+"),
    ("[-[+]]", "", ".-"),
    ("", "[[[-]]]", "..+"),
    ("[--]", "[[+]]", "+"),
    ("[[-]]", "[+]", "..+"),
)
# `[P0[]G] -> []`: P0 is a sequence of prints and read-free excursions that
# return to, and preserve, a nonzero tested cell; G is arbitrary balanced.
_DEPTH_PRESERVED_BODIES = (
    (".", ""),
    (">[-[+]]<", ""),
    (">[[-][+]]<", "+"),
    (".>[[-]]<", "[]"),
    (">[[[-]]]<", "[+[]]"),
    (">[-[+]]<.", "[[-[]]]"),
)
# The tested cell is zero in the first two contexts and nonzero or 255 in the
# rest; the pointer sits at 0 or 1 and the reads may reach EOF.
_DEPTH_OBSERVATION_CONTEXTS = (
    ("", ""),
    (">", ""),
    (",>,>,>,<<<", "\x00\x01\x00\x00"),
    (",>,>,>,<<<", "\x01\x00\x00\x00"),
    ("+", ""),
    ("-", ""),
)


@pytest.mark.medium
def test_depth_two_and_three_side_conditions_execute() -> None:
    for prefix, stdin in _DEPTH_OBSERVATION_CONTEXTS:
        for body in _DEPTH_ROTATION_BODIES:
            left = _observe(prefix + "[." + body + "].", stdin)
            right = _observe(prefix + ".[" + body + ".]", stdin)
            assert left == right, (body, prefix, stdin, left, right)
        for w, z, d in _DEPTH_DIVERGENCE_BODIES:
            loop = "[" + w + "[" + z + "]" + d + "]"
            assert _observe(prefix + loop, stdin) == _observe(prefix + "[]", stdin)
        for p0, g in _DEPTH_PRESERVED_BODIES:
            loop = "[" + p0 + "[]" + g + "]"
            assert _observe(prefix + loop, stdin) == _observe(prefix + "[]", stdin)


@pytest.mark.medium
def test_depth_bodies_agree_on_read_positions() -> None:
    from tests.proofs.test_research_tracks import _trace_reads

    prefix = ",>,>,>,<<< "
    for body in _DEPTH_ROTATION_BODIES:
        for bits in ((0, 1, 0, 0), (1, 0, 0, 0), ()):
            assert _trace_reads(prefix + "[." + body + "].", bits) == _trace_reads(
                prefix + ".[" + body + ".]", bits
            )


def _rotation_congruence_classes(length: int, tail_length: int = 5) -> int:
    """Count Moore classes of the balanced `[.Y].`-avoidance specification."""
    import itertools

    alphabet = ".[]"

    def balance(word: str) -> int | None:
        depth = 0
        for char in word:
            if char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
                if depth < 0:
                    return None
        return depth

    def has_lhs(word: str) -> bool:
        stack: list[int] = []
        pairs: list[tuple[int, int]] = []
        for index, char in enumerate(word):
            if char == "[":
                stack.append(index)
            elif char == "]" and stack:
                pairs.append((stack.pop(), index))
        return any(
            i + 1 < len(word)
            and word[i + 1] == "."
            and j + 1 < len(word)
            and word[j + 1] == "."
            for i, j in pairs
        )

    tails = [
        "".join(chars)
        for n in range(tail_length + 1)
        for chars in itertools.product(alphabet, repeat=n)
        if balance("".join(chars)) == 0
    ]
    valid = [""]
    for n in range(1, length + 1):
        for chars in itertools.product(alphabet, repeat=n):
            word = "".join(chars)
            if balance(word) is not None:
                valid.append(word)
    signatures = {
        word: tuple(has_lhs(word + "]" * (balance(word) or 0) + t) for t in tails)
        for word in valid
    }
    classes = dict(signatures)
    while True:
        refined = {
            word: (
                signatures[word],
                tuple(classes.get(word + char, -1) for char in alphabet),
            )
            for word in valid
        }
        groups: dict[tuple[object, ...], int] = {}
        next_classes = {
            word: groups.setdefault(refined[word], len(groups)) for word in valid
        }
        if next_classes == classes:
            return len(set(classes.values()))
        classes = next_classes


@pytest.mark.medium
def test_unbounded_body_classes_are_not_regular() -> None:
    from tests.proofs._brainfuck_count import accepts, certificate

    rows, _ = certificate()
    # The depth-one monitor accepts a left-hand side at every depth k >= 2, so
    # it does not forbid the unrestricted rotation or divergence classes.
    for depth in range(2, 8):
        nested = "[" * depth + "--" + "]" * depth
        assert accepts(rows, "[." + nested + "].")
        assert accepts(rows, "[" + "[" + nested + "]" + "--]")
    # The balanced-avoidance specification is not a finite right congruence:
    # its Moore classes grow with the observation window.
    assert [_rotation_congruence_classes(w) for w in (4, 6, 8)] == [15, 39, 86]


@pytest.mark.medium
def test_regular_certificate() -> None:
    from tests.proofs._brainfuck_count import accepts, certificate, check_certificate

    rows, vector = certificate()
    check_certificate(rows, vector)
    from tests.proofs._brainfuck_count import local_patterns, regular_patterns
    from tests.proofs.grammar_certificate import check_grammar

    assert check_grammar(
        rows, ".,-+<>[]", sorted(local_patterns()), regular_patterns()
    ) >= len(rows)
    from tests.proofs._brainfuck_count import ALPHABET, BOUND
    from tests.proofs.perron_certificate import check_certificate as independent_check

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
    from tests.proofs.grammar_certificate import check_grammar

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

    from tests.proofs.grammar_certificate import _RegexMonitor

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

    from tests.proofs.grammar_certificate import _LiteralMonitor

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
        ([], ["["], "invalid regular"),
        ([], ["z"], "outside alphabet"),
        ([], ["[a-z]"], "character class"),
        ([], ["(?i:a)"], "flags"),
        ([], ["a+"], "operator"),
    ],
)
def test_independent_grammar_rejects_unsupported_factors(
    factors, regexes, message
) -> None:
    from tests.proofs.grammar_certificate import check_grammar

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
