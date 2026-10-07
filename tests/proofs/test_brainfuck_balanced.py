"""Balanced-word counting, sound bi-tape mirrors and integer certificates."""

import itertools
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.balanced_certificate import _product, _sum, check_certificate
from scripts.grammar_certificate import check_grammar
from tests.proofs._brainfuck_count import ALPHABET, accepts, automaton, minimize
from tests.proofs.test_brainfuck_count import _observe, _sole_loop_word


def test_balanced_matrix_coefficients_match_words() -> None:
    rows = minimize(automaton({"+-", "-+", "><", "<>", "+,", "-,", "]["}, []))
    identity = [{state: 1} for state in range(len(rows))]
    zero: list[dict[int, int]] = [{} for _ in rows]
    literals: list[dict[int, int]] = []
    for row in rows:
        counts: dict[int, int] = {}
        for target in row[:6]:
            if target >= 0:
                counts[target] = counts.get(target, 0) + 1
        literals.append(counts)
    opening = [{row[6]: 1} if row[6] >= 0 else {} for row in rows]
    closing = [{row[7]: 1} if row[7] >= 0 else {} for row in rows]
    sequences, bodies, loops = [identity], [identity], [zero]
    for size in range(1, 6):
        loop = (
            _product(_product(opening, bodies[size - 2]), closing)
            if size >= 2
            else zero
        )
        loops.append(loop)
        body = _product(literals, sequences[size - 1])
        for width in range(2, size):
            body = _sum(body, _product(loops[width], sequences[size - width]))
        bodies.append(body)
        sequences.append(_sum(body, loop))
    for size, matrix in enumerate(sequences):
        expected = 0
        for letters in itertools.product(ALPHABET, repeat=size):
            word = "".join(letters)
            expected += accepts(rows, word) and _sole_loop_word(word)
        assert sum(matrix[0].values()) == expected


def _rotation_word(word: str) -> bool:
    if not _sole_loop_word(word):
        return False
    openings: list[int] = []
    for position, char in enumerate(word):
        if char == "[":
            openings.append(position)
        elif char == "]":
            opening = openings.pop()
            if word[opening + 1] == "." and word[position + 1 : position + 2] == ".":
                return False
    return True


def test_rotation_matrix_coefficients_match_words() -> None:
    rows = minimize(automaton({"+-", "-+", "><", "<>", "+,", "-,", "]["}, []))
    identity = [{state: 1} for state in range(len(rows))]
    zero: list[dict[int, int]] = [{} for _ in rows]
    literals: list[dict[int, int]] = []
    other_literals: list[dict[int, int]] = []
    for row in rows:
        counts: dict[int, int] = {}
        other: dict[int, int] = {}
        for column, target in enumerate(row[:6]):
            if target >= 0:
                counts[target] = counts.get(target, 0) + 1
                if column:
                    other[target] = other.get(target, 0) + 1
        literals.append(counts)
        other_literals.append(other)
    opening = [{row[6]: 1} if row[6] >= 0 else {} for row in rows]
    closing = [{row[7]: 1} if row[7] >= 0 else {} for row in rows]
    printing = [{row[0]: 1} if row[0] >= 0 else {} for row in rows]
    sequences, tails, bodies, loops, print_loops = (
        [identity],
        [zero],
        [identity],
        [zero],
        [zero],
    )
    for size in range(1, 6):
        loop = (
            _product(_product(opening, bodies[size - 2]), closing)
            if size >= 2
            else zero
        )
        print_loop = (
            _product(
                _product(_product(opening, printing), sequences[size - 3]), closing
            )
            if size >= 3
            else zero
        )
        loops.append(loop)
        print_loops.append(print_loop)
        common = zero
        for width in range(2, size):
            common = _sum(common, _product(loops[width], sequences[size - width]))
            common = _sum(common, _product(print_loops[width], tails[size - width]))
        body = _sum(common, _product(other_literals, sequences[size - 1]))
        bodies.append(body)
        tails.append(_sum(body, _sum(loop, print_loop)))
        sequences.append(
            _sum(
                _sum(common, _product(literals, sequences[size - 1])),
                _sum(loop, print_loop),
            )
        )
    for size, matrix in enumerate(sequences):
        expected = 0
        for letters in itertools.product(ALPHABET, repeat=size):
            word = "".join(letters)
            expected += accepts(rows, word) and _rotation_word(word)
        assert sum(matrix[0].values()) == expected
    assert not _rotation_word(".[[--]]")
    assert _rotation_word(".[[--].]")
    body = "--"
    for _ in range(8):
        body = "[-" + body + "]"
        forbidden = "[." + body + "]."
        assert _sole_loop_word(forbidden)
        assert not _rotation_word(forbidden)
        assert _rotation_word(".[" + body + ".]")


@pytest.mark.parametrize("stdin", ["", "\x00", "\x01"])
def test_unrestricted_rotation_executes(stdin: str) -> None:
    bodies = ["", "-", ",", "[[-],]", ".>,<"]
    nested = "--"
    for _ in range(8):
        nested = "[-" + nested + "]"
        bodies.append(nested)
    for body in bodies:
        for prefix in ("", "+", "++"):
            assert _observe(prefix + "[." + body + "].", stdin) == _observe(
                prefix + ".[" + body + ".]", stdin
            )


@pytest.mark.slow
def test_rotation_certificate() -> None:
    from tests.proofs._brainfuck_balanced import (
        ROTATION_BOUND,
        SCALE,
        patterns,
        rotation_certificate,
    )

    rows, nonempty, nonprint, bodies = rotation_certificate()
    check_certificate(rows, nonempty, bodies, SCALE, ROTATION_BOUND, nonprint=nonprint)
    assert SCALE + sum(nonempty[0].values()) <= 7539255
    assert check_grammar(rows, ALPHABET, sorted(patterns()), []) >= len(rows)
    with pytest.raises(ValueError, match="supersolution"):
        check_certificate(rows, nonempty, bodies, SCALE, (689, 100), nonprint=nonprint)
    with pytest.raises(ValueError, match="supersolution"):
        check_certificate(rows, nonempty, bodies, SCALE, ROTATION_BOUND)
    with pytest.raises(ValueError, match="nonprint"):
        check_certificate(
            rows, nonempty, bodies, SCALE, ROTATION_BOUND, nonprint=[{} for _ in rows]
        )
    with pytest.raises(ValueError, match="matrix entry"):
        check_certificate(rows, nonempty, bodies, SCALE, ROTATION_BOUND, nonprint=[])


@pytest.mark.parametrize("body", ["", "-", "[-[]]", "[[-],]", ".>,<"])
@pytest.mark.parametrize("stdin", ["", "\x00", "\x01"])
def test_sole_loop_rewrite_executes(body: str, stdin: str) -> None:
    for prefix in ("", "+", "++"):
        assert _observe(prefix + "[[" + body + "]].", stdin) == _observe(
            prefix + "[" + body + "].", stdin
        )


@pytest.mark.parametrize("pointer", ["", ">", "<"])
def test_bi_mirrors_execute(pointer: str) -> None:
    # Left mirrors commute because the repository tape has no clipped edge.
    for left, right in (
        ("<+>.", ".<+>"),
        ("<+>,", ",<+>"),
        ("[-]<,>", "<,>[-]"),
        ("<[-]>+<", "+<[-]"),
        ("[]<.>", "<.>[]"),
        ("+[<+>[]]", "+[]"),
    ):
        for stdin in ("", "\x01"):
            assert _observe(pointer + left, stdin) == _observe(pointer + right, stdin)


@pytest.mark.slow
def test_bi_balanced_certificate() -> None:
    from tests.proofs._brainfuck_balanced import BOUND, SCALE, certificate, patterns

    rows, nonempty, bodies = certificate()
    assert len(rows) == 195
    check_certificate(rows, nonempty, bodies, SCALE, BOUND)
    assert SCALE + sum(nonempty[0].values()) <= 7963437
    assert check_grammar(rows, ALPHABET, sorted(patterns()), []) >= len(rows)
    assert accepts(rows, "+[-[]].")
    assert accepts(rows, "+[-.<+>[]]")
    assert accepts(rows, "[]")
    with pytest.raises(ValueError, match="supersolution"):
        check_certificate(rows, nonempty, bodies, SCALE, (690, 100))
    missing = [dict(row) for row in nonempty]
    missing[0] = {}
    with pytest.raises(ValueError, match="sequence"):
        check_certificate(rows, missing, bodies, SCALE, BOUND)
    missing = [dict(row) for row in bodies]
    missing[0] = {}
    with pytest.raises(ValueError, match="body"):
        check_certificate(rows, nonempty, missing, SCALE, BOUND)


def test_zeroing_prefix_is_not_a_forced_divergence_body() -> None:
    assert _observe("+[-.<+>[]]", "")[0] == "halt"
    assert _observe("+[]", "")[0] == "diverge"


@pytest.mark.parametrize(
    ("rows", "nonempty", "bodies", "scale", "bound", "error"),
    [
        ([], [], [], 1, (7, 1), "scale or size"),
        ([[0] * 8], [{0: 6}], [{0: 7}], 0, (7, 1), "scale or size"),
        ([[0] * 8], [{0: 6}], [{0: 7}], 1, (1, 1), "bound"),
        ([[1] * 8], [{0: 6}], [{0: 7}], 1, (7, 1), "transition"),
        ([[0] * 7], [{0: 6}], [{0: 7}], 1, (7, 1), "transition"),
        ([[0] * 8], [], [{0: 7}], 1, (7, 1), "matrix entry"),
        ([[0] * 8], [{0: -1}], [{0: 7}], 1, (7, 1), "matrix entry"),
        ([[0] * 8], [{1: 6}], [{0: 7}], 1, (7, 1), "matrix entry"),
    ],
)
def test_malformed_balanced_certificates(rows, nonempty, bodies, scale, bound, error):
    with pytest.raises(ValueError, match=error):
        check_certificate(rows, nonempty, bodies, scale, bound)


@pytest.mark.parametrize("rotation", [False, True])
def test_balanced_checker_cli(tmp_path: Path, *, rotation: bool) -> None:
    # Six literal letters and no bracket transitions: N=6, B=7 at x=1/7.
    data = {
        "rows": [[0] * 6 + [-1, -1]],
        "nonempty": [{0: 6}],
        "bodies": [{0: 7}],
        "scale": 1,
        "bound": [7, 1],
        "factors": ["[", "]"],
    }
    if rotation:
        data["nonprint"] = [{0: 5}]
        data["bodies"] = [{0: 6}]
    path = tmp_path / "balanced.json"
    path.write_text(json.dumps(data))
    script = Path(__file__).resolve().parents[2] / "scripts" / "balanced_certificate.py"
    result = subprocess.run(
        [sys.executable, str(script), str(path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "exact balanced supersolution" in result.stdout
