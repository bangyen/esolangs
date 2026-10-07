"""Independent word and execution controls for typed divergence counting."""

import itertools
import re

import pytest

from tests.proofs._brainfuck_count import ALPHABET
from tests.proofs._brainfuck_divergence import _append, typed_counts
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
