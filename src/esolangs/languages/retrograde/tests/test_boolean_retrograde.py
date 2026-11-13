"""Exhaustive Boolean contracts and an independent set-tape reference."""

from itertools import product
from random import Random

import esolangs
from esolangs import run as execute
from esolangs.runtime.io import ScriptedIO
from tests.support.analysis_support import assert_analysis_complement
from tests.support.generator_support import constant_artifacts, evaluate_generated


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
                n3_source += len(esolangs.generate("Retrograde", table).source)
    assert n3_source == 12399
    for n in (4, 5, 6):
        rng = Random(1000 * n)
        table = "".join(rng.choice("01") for _ in range(1 << n))
        template = esolangs.generate("Retrograde", table)
        for row, bits in enumerate(product((0, 1), repeat=n)):
            source = esolangs.instantiate("Retrograde", template, bits)
            pointer, direction, tape = _reference(source.source)
            assert (pointer, direction) == (n, 1)
            assert tuple(int(i in tape) for i in range(n)) == bits
            expected = str(int(pointer in tape))
            assert execute("Retrograde", source).output == expected == table[row]
    source = esolangs.instantiate(
        "Retrograde", esolangs.generate("Retrograde", "01"), (0,)
    )
    at = source.source.index("/")
    broken = source.source[:at] + "\\" + source.source[at + 1 :]
    assert (
        execute(
            "Retrograde", broken, limits=esolangs.ExecutionLimits(max_steps=1000)
        ).output
        != "0"
    )


def _check_constants() -> None:
    assert_analysis_complement("Retrograde", "subtree_ids")
    from esolangs.languages.retrograde.interpreter import run

    for n, bit, _options, template in constant_artifacts("Retrograde", range(1, 13)):
        assert template.source.count("$") == n
        for bits in ([0] * n, [1] * n):
            source = esolangs.instantiate("Retrograde", template, bits)
            pointer, direction, tape = _reference(source.source.replace("\n", ""))
            assert (pointer, direction) == (n, 1)
            assert [int(i in tape) for i in range(n)] == bits
            io = ScriptedIO("7")
            run(source.source, io)
            assert io.getvalue() == bit
            assert io.reads == 0
            assert io.input_char() == ord("7")
