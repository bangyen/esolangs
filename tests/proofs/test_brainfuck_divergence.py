"""Independent word and execution controls for typed divergence counting."""

import itertools
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.balanced_certificate import _product, _sum
from scripts.divergence_certificate import _next, check_certificate
from scripts.grammar_certificate import check_grammar
from tests.proofs._brainfuck_balanced import SCALE, Matrix, patterns
from tests.proofs._brainfuck_count import ALPHABET, accepts, automaton, minimize
from tests.proofs._brainfuck_divergence import (
    BOUND,
    EMPTY,
    _append,
    certificate,
    matrix_image,
    states,
    typed_counts,
)
from tests.proofs.test_brainfuck_count import _observe


def _word(word: str, *, body: bool = False) -> bool:
    atoms: list[str] = []
    position = 0
    while position < len(word):
        char = word[position]
        if char == "]":
            return False
        if char != "[":
            atoms.append(char)
            position += 1
            continue
        depth, end = 1, position + 1
        while end < len(word) and depth:
            depth += (word[end] == "[") - (word[end] == "]")
            end += 1
        if depth:
            return False
        inner = word[position + 1 : end - 1]
        if not _word(inner, body=True):
            return False
        if inner.startswith(".") and word[end : end + 1] == ".":
            return False
        atoms.append("L")
        position = end
    if body:
        if atoms == ["L"]:
            return False
        if "," not in word and re.search(r"L\.*[+-]\.*$", "".join(atoms)):
            return False
    return True


def test_typed_coefficients_match_exhaustive_words() -> None:
    sequences, bodies = typed_counts(6)
    for size in range(7):
        expected = 0
        expected_bodies: dict[tuple[bool, bool], int] = {}
        for letters in itertools.product(ALPHABET, repeat=size):
            word = "".join(letters)
            expected += _word(word)
            if _word(word, body=True):
                key = ("," in word, word.startswith("."))
                expected_bodies[key] = expected_bodies.get(key, 0) + 1
        assert sum(sequences[size].values()) == expected
        assert bodies[size] == expected_bodies


def test_suffix_monitor_controls() -> None:
    assert _append((False, 2, 2, 1), ".", reads=False) is None
    assert not _word("[[--].+.]")
    assert not _word("[[--].-.]")
    assert _word("[[--]++]")
    assert _word("[[--]+>]")
    assert _word("[,[--]+]")
    assert _word("[[,]+]")
    assert not _word("[.[]+]")
    assert _word("[.[]++]")
    assert not _word("[.[]++].")
    assert _word("[]+")  # The forbidden suffix applies only inside a loop.


@pytest.mark.parametrize("sign", ["+", "-"])
def test_unrestricted_nonzero_tail_executes(sign: str) -> None:
    nested = "-"
    for _ in range(8):
        nested = "[-" + nested + "]"
        for prefix in ("", "+", "++", "-"):
            for before, after in (("", ""), (".", ".")):
                program = prefix + "[." + nested + "[" + nested + "]"
                program += before + sign + after + "].,"
                assert _observe(program, "") == _observe(prefix + "[].,", "")


def test_read_free_condition_has_eof_controls() -> None:
    for program in ("+[,[--]+]", "+[[,]+]"):
        assert _observe(program, "")[0] == "eof"
        assert _observe("+[]", "")[0] == "diverge"
        assert _word(program)


def test_matrix_coefficients_match_factor_words() -> None:
    rows = minimize(automaton(patterns(), []))
    classes = states()
    index = {state: position for position, state in enumerate(classes)}
    starts = {0, *(row[6] for row in rows if row[6] >= 0)}
    zero: Matrix = [{} for _ in rows]
    identity = [{start: 1} if start in starts else {} for start in range(len(rows))]
    coefficients = [[identity if state == EMPTY else zero for state in classes]]
    transitions = [
        [{row[column]: 1} if row[column] >= 0 else {} for row in rows]
        for column in range(8)
    ]
    for size in range(1, 6):
        current = [[dict(row) for row in zero] for _ in classes]
        atoms = [(1, column, transitions[column]) for column in range(6)]
        for width in range(2, size + 1):
            bodies = [[dict(row) for row in zero] for _ in range(4)]
            for state, matrix in zip(classes, coefficients[width - 2], strict=True):
                read, suffix, first, count = state
                if (first, count) == (2, 1) or (not read and suffix == 3):
                    continue
                kind = 2 * read + (first == 1)
                bodies[kind] = _sum(bodies[kind], matrix)
            atoms.extend(
                (
                    width,
                    6 + kind,
                    _product(_product(transitions[6], body), transitions[7]),
                )
                for kind, body in enumerate(bodies)
            )
        for width, column, atom in atoms:
            for state, prefix in zip(classes, coefficients[size - width], strict=True):
                target = _next(state, column)
                if target is not None:
                    position = index[target]
                    current[position] = _sum(current[position], _product(prefix, atom))
        coefficients.append(current)
    for size, matrices in enumerate(coefficients):
        expected: dict[int, int] = {}
        for letters in itertools.product(ALPHABET, repeat=size):
            word = "".join(letters)
            if not _word(word) or not accepts(rows, word):
                continue
            end = 0
            for char in word:
                end = rows[end][ALPHABET.index(char)]
            expected[end] = expected.get(end, 0) + 1
        actual: dict[int, int] = {}
        for matrix in matrices:
            for end, value in matrix[0].items():
                actual[end] = actual.get(end, 0) + value
        assert actual == expected
    assert accepts(rows, "[[--]+]")
    assert not _word("[[--]+]")  # Positive control beyond the length-six factors.


@pytest.mark.slow
def test_nonzero_tail_certificate() -> None:
    rows, classes, matrices = certificate()
    check_certificate(rows, classes, matrices, SCALE, BOUND)
    assert matrix_image(rows, classes, matrices, SCALE, BOUND) == matrices
    assert sum(sum(matrix[0].values()) for matrix in matrices) <= 7675935
    assert check_grammar(rows, ALPHABET, sorted(patterns()), []) == 705
    with pytest.raises(ValueError, match="supersolution"):
        check_certificate(rows, classes, matrices, SCALE, (688, 100))
    damaged = [[dict(row) for row in matrix] for matrix in matrices]
    damaged[classes.index(EMPTY)][0] = {}
    with pytest.raises(ValueError, match="supersolution"):
        check_certificate(rows, classes, damaged, SCALE, BOUND)


@pytest.mark.parametrize(
    "damage", ["scale", "bound", "rows", "classes", "matrix", "entry"]
)
def test_nonzero_tail_checker_rejects_malformed(damage: str) -> None:
    rows, classes, scale, bound = [[-1] * 8], states(), 1, (7, 1)
    matrices: list[Matrix] = [[{}] for _ in classes]
    matrices[classes.index(EMPTY)] = [{0: 1}]
    if damage == "scale":
        scale = 0
    elif damage == "bound":
        bound = (1, 1)
    elif damage == "rows":
        rows[0][0] = 1
    elif damage == "classes":
        classes.pop()
    elif damage == "matrix":
        matrices[0] = []
    else:
        matrices[0][0][0] = -1
    with pytest.raises(ValueError, match="invalid"):
        check_certificate(rows, classes, matrices, scale, bound)


def test_nonzero_tail_checker_cli(tmp_path: Path) -> None:
    rows, classes = [[0] + [-1] * 7], states()
    matrices: list[Matrix] = [[{}] for _ in classes]
    for state in (EMPTY, (False, 0, 1, 1), (False, 0, 1, 2)):
        matrices[classes.index(state)][0][0] = 1
    path = tmp_path / "divergence.json"
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
        Path(__file__).resolve().parents[2] / "scripts" / "divergence_certificate.py"
    )
    result = subprocess.run(
        [sys.executable, str(script), str(path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "exact nonzero-tail supersolution" in result.stdout
