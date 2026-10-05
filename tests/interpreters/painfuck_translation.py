"""Painfuck suffix substitution expressed as permutation composition."""

from tests.interpreters.painfuck_translation_rule import NEXT, PREVIOUS


def apply(source, rule):
    permutation = {letter: letter for letter in NEXT}
    result = []
    for char in source:
        if char not in NEXT:
            continue
        result.append(permutation[char])
        permutation = {letter: rule[value] for letter, value in permutation.items()}
    return "".join(result)


def translate(source):
    return apply(source, NEXT)


def encode(commands):
    if any(char not in NEXT for char in commands):
        raise ValueError("unknown command")
    return apply(commands, PREVIOUS)
