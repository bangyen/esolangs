"""Exhaustive Boolean contracts and an independent set-tape reference."""

from itertools import product
from random import Random

import esolangs
from tests.support.generator_support import evaluate_generated


def _reference(code: str) -> tuple[int, int, set[int]]:
    stack = []
    pairs = {}
    for i, c in enumerate(code):
        if c == "{":
            stack.append(i)
        elif c == "}":
            j = stack.pop()
            pairs[i], pairs[j] = j, i
    cursor = pointer = 0
    direction = 1
    tape: set[int] = set()
    for _ in range(10_000):
        if not 0 <= cursor < len(code):
            return pointer, direction, tape
        c = code[cursor]
        if c in "*<>/\\":
            if c == ">":
                pointer += direction
            elif c == "<":
                pointer -= direction
            elif (
                c == "*"
                or (c == "/" and direction > 0)
                or (c == "\\" and direction < 0)
            ):
                tape.symmetric_difference_update((pointer,))
        elif pointer in tape:
            cursor = pairs[cursor]
            direction *= -1
        cursor += direction
    raise AssertionError("reference step cap")


def check_boolean_tables() -> None:
    _check_constants()
    n3_source = 0
    for n in (1, 2, 3):
        for value in range(2 ** (1 << n)):
            table = format(value, f"0{1 << n}b")
            assert evaluate_generated("Retrograde", table) == table
            if n == 3:
                n3_source += len(esolangs.generate("Retrograde", table))
    assert n3_source == 12399
    for n in (4, 5, 6):
        rng = Random(1000 * n)
        table = "".join(rng.choice("01") for _ in range(1 << n))
        template = esolangs.generate("Retrograde", table)
        for row, bits in enumerate(product((0, 1), repeat=n)):
            source = esolangs.instantiate("Retrograde", template, bits)
            pointer, direction, tape = _reference(source)
            assert (pointer, direction) == (n, 1)
            assert tuple(int(i in tape) for i in range(n)) == bits
            expected = str(int(pointer in tape))
            assert esolangs.run("Retrograde", source) == expected == table[row]
    source = esolangs.instantiate(
        "Retrograde", esolangs.generate("Retrograde", "01"), (0,)
    )
    at = source.index("/")
    broken = source[:at] + "\\" + source[at + 1 :]
    assert esolangs.run("Retrograde", broken, max_steps=1000) != "0"


def _check_constants() -> None:
    from esolangs.languages.retrograde.interpreter import run
    from esolangs.runtime.io import ScriptedIO

    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                template = esolangs.generate("Retrograde", bit * (1 << n), **options)
                assert template.count("$") == n
                for bits in ([0] * n, [1] * n):
                    source = esolangs.instantiate("Retrograde", template, bits)
                    pointer, direction, tape = _reference(source.replace("\n", ""))
                    assert (pointer, direction) == (n, 1)
                    assert [int(i in tape) for i in range(n)] == bits
                    io = ScriptedIO("7")
                    run(source, io)
                    assert io.getvalue() == bit
                    assert io.reads == 0
                    assert io.input_char() == ord("7")
