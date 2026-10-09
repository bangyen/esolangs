"""Independent grammar and execution controls for preserved-cell prefixes."""

import itertools
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts._brainfuck_preserving import (
    BOUND,
    EMPTY,
    SCALE,
    body_type,
    certificate,
    loop_types,
    matrix_image,
    states,
    typed_counts,
)
from scripts.grammar_certificate import check_grammar
from scripts.preserving_certificate import check_certificate
from tests.proofs._brainfuck_balanced import Matrix, patterns
from tests.proofs._brainfuck_count import ALPHABET, accepts, automaton, minimize
from tests.proofs.test_brainfuck_count import _observe
from tests.proofs.test_brainfuck_divergence import _word as _nonzero_word


def _atoms(word: str) -> list[tuple[str, str, int, int]]:
    result = []
    position = 0
    while position < len(word):
        start = position
        char = word[position]
        position += 1
        inner = ""
        if char == "[":
            depth = 1
            while depth:
                depth += (word[position] == "[") - (word[position] == "]")
                position += 1
            inner = word[start + 1 : position - 1]
        result.append((char, inner, start, position))
    return result


def _confined(word: str, direction: int) -> bool:
    height = 0
    for char, inner, _, _ in _atoms(word):
        if char == ",":
            return False
        if char in "<>":
            height += direction * (1 if char == ">" else -1)
            if not 0 <= height <= 1:
                return False
        if char == "[":
            if height == 0 and not _confined(inner, direction):
                return False
            if height == 1 and any(char in inner for char in ",<>"):
                return False
    return height == 0


def _prefix(word: str) -> bool:
    atoms = _atoms(word)
    position = 0
    balance = 0
    while position < len(atoms):
        char, _, _, begin = atoms[position]
        if char == ".":
            position += 1
            continue
        if char in "+-":
            balance += 1 if char == "+" else -1
            if abs(balance) > 1:
                return False
            position += 1
            continue
        if char not in "<>":
            return False
        direction = 1 if char == ">" else -1
        height = 1
        position += 1
        while position < len(atoms):
            char, _, end, _ = atoms[position]
            if char in "<>":
                height += direction * (1 if char == ">" else -1)
            position += 1
            if height == 0:
                if not _confined(word[begin:end], direction):
                    return False
                break
        else:
            return False
    return balance == 0


def _word(word: str, *, body: bool = False) -> bool:
    if not _nonzero_word(word, body=body):
        return False
    for char, inner, start, _ in _atoms(word):
        if char == "[":
            if not _word(inner, body=True):
                return False
            if body and not inner and _prefix(word[:start]):
                return False
    return True


def test_preserving_coefficients_match_exhaustive_words() -> None:
    coefficients = typed_counts(6)
    kinds = loop_types()
    for size, counts in enumerate(coefficients):
        expected = 0
        expected_bodies = dict.fromkeys(kinds, 0)
        for letters in itertools.product(ALPHABET, repeat=size):
            word = "".join(letters)
            expected += _word(word)
            if _word(word, body=True):
                kind = (_confined(word, 1)) + 2 * (_confined(word, -1))
                key = ("," in word, word.startswith("."), kind, not word)
                expected_bodies[key] += 1
        assert sum(counts.values()) == expected
        actual_bodies = dict.fromkeys(kinds, 0)
        for state, count in counts.items():
            key = body_type(state)
            if key is not None:
                actual_bodies[key] += count
        assert actual_bodies == expected_bodies


def test_preserving_side_conditions() -> None:
    assert _prefix(".>+[->-<]<.<+[<+>]>.")
    assert not _prefix("->+<")
    assert not _prefix(">[<+>]<")  # The inner loop may touch the tested cell.
    assert not _prefix(">,<")
    assert not _prefix(">++")
    assert not _word("[>+<[],]")
    assert _word(">+<[],")  # The forced-prefix exclusion applies inside loops.
    assert _word("[-[]].")
    assert _word("[->+<[],]")
    assert _observe("+[-[]].", "")[0] == "halt"
    assert _observe("+[]", "")[0] == "diverge"
    assert _prefix("+>+<-")
    assert not _prefix("+>+<")
    assert not _prefix("++>+<--")
    assert not _word("[+>+<-[],]")
    assert _word("[+>+<[],]")


def test_cancelling_tested_updates_execute() -> None:
    for prefix in ("+>+<-", "->+<+", "+>[-[->[-]<]]<-", "+.>+<-."):
        assert _prefix(prefix)
        for value in range(256):
            initial = "+" * value
            assert _observe(initial + "[" + prefix + "[],].", "") == _observe(
                initial + "[].", ""
            )
    # At byte 255 a non-cancelling increment clears the tested cell.
    assert _observe("-" + "[+>+<[]].", "")[0] == "halt"
    assert _observe("-" + "[].", "")[0] == "diverge"


@pytest.mark.parametrize("direction", [1, -1])
def test_unbounded_preserving_prefixes_execute(direction: int) -> None:
    stationary = "-"
    confined = "+>[-]<"
    for _ in range(8):
        stationary = "[-" + stationary + "]"
        confined = "[-" + confined + "]>" + stationary + "<"
        prefix = ".>" + confined + "<."
        if direction < 0:
            prefix = prefix.translate(str.maketrans("<>", "><"))
        assert _prefix(prefix)
        for initial in ("", "+", "++", "-"):
            for suffix in ("", ",", "[>,<]", ".[[-],]"):
                original = initial + "[" + prefix + "[]" + suffix + "].,"
                assert _observe(original, "") == _observe(initial + "[].,", "")


def test_touching_excursion_is_not_preserving() -> None:
    original = "+>+<[>[<->-]<[]]."
    assert _observe(original, "")[0] == "halt"
    assert _observe("+>+<[].", "")[0] == "diverge"
    assert not _prefix(">[<->-]<")


@pytest.mark.slow
def test_preserving_certificate() -> None:
    rows, classes, matrices = certificate()
    check_certificate(rows, classes, matrices, SCALE, BOUND)
    image = matrix_image(rows, classes, matrices, SCALE, BOUND)
    assert all(
        value <= upper.get(end, 0)
        for matrix, bounds in zip(image, matrices, strict=True)
        for row, upper in zip(matrix, bounds, strict=True)
        for end, value in row.items()
    )
    assert sum(sum(matrix[0].values()) for matrix in matrices) <= 793307057
    assert check_grammar(rows, ALPHABET, sorted(patterns()), []) == 705
    with pytest.raises(ValueError, match="supersolution"):
        check_certificate(rows, classes, matrices, SCALE, (688, 100))
    damaged = [[dict(row) for row in matrix] for matrix in matrices]
    damaged[classes.index(EMPTY)][0] = {}
    with pytest.raises(ValueError, match="supersolution"):
        check_certificate(rows, classes, damaged, SCALE, BOUND)


def test_preserving_rule_extends_finite_factors() -> None:
    rows = minimize(automaton(patterns(), []))
    prefix = ">[-[->[-]<]]<"
    word = "[" + prefix + "[],]"
    assert _prefix(prefix)
    assert accepts(rows, word)
    assert _nonzero_word(word)
    assert not _word(word)


@pytest.mark.parametrize("damage", ["classes", "identity", "entry"])
def test_preserving_checker_rejects_bad_candidates(damage: str) -> None:
    rows, classes = [[-1] * 8], states()
    matrices: list[Matrix] = [[{}] for _ in classes]
    matrices[classes.index(EMPTY)][0][0] = 1
    if damage == "classes":
        classes.pop()
    elif damage == "identity":
        matrices[classes.index(EMPTY)][0] = {}
    else:
        matrices[0][0][0] = -1
    with pytest.raises(ValueError, match=r"invalid|supersolution"):
        check_certificate(rows, classes, matrices, 1, (7, 1))


def test_preserving_checker_cli(tmp_path: Path) -> None:
    rows, classes = [[0] + [-1] * 7], states()
    matrices: list[Matrix] = [[{}] for _ in classes]
    for state in (EMPTY, (False, 0, 1, 1, 0, 0, 0, 0), (False, 0, 1, 2, 0, 0, 0, 0)):
        matrices[classes.index(state)][0][0] = 1
    path = tmp_path / "preserving.json"
    path.write_text(
        json.dumps(
            {
                "rows": rows,
                "classes": classes,
                "matrices": matrices,
                "scale": 1,
                "bound": [7, 1],
                "factors": list(",-+<>[]"),
            }
        )
    )
    script = (
        Path(__file__).resolve().parents[2] / "scripts" / "preserving_certificate.py"
    )
    result = subprocess.run(
        [sys.executable, str(script), str(path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "exact preserving-prefix supersolution" in result.stdout
