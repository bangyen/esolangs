"""Painfuck comparisons against an independent suffix and command model."""

import itertools
import random
from fractions import Fraction
from math import floor

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.painfuck import _advance, _Machine, _translate
from esolangs.tools.painfuck import painfuck
from tests.interpreters.painfuck_observer import Coins, check, compare
from tests.interpreters.painfuck_reference import Reference
from tests.interpreters.painfuck_translation import encode, translate
from tests.interpreters.painfuck_translation_rule import NEXT
from tests.interpreters.painfuck_translation_rule import encode as slow_encode
from tests.interpreters.painfuck_translation_rule import translate as slow_translate


def test_suffix_permutation():
    for length in range(4):
        for word in itertools.product(NEXT, repeat=length):
            source = "".join(word)
            assert translate(source) == slow_translate(source) == _translate(source)
            assert encode(source) == slow_encode(source)
    assert translate("ptt") == "pso"


@pytest.mark.parametrize("shard", range(20))
def test_finite_traces(shard):
    for seed in range(shard * 50, (shard + 1) * 50):
        rng = random.Random(103549 + seed)
        commands = "".join(
            rng.choice("psrlhzwqdouabve") for _ in range(rng.randint(1, 24))
        )
        check(encode(commands), limit=100)


@pytest.mark.parametrize(
    "commands", ["ci", "ccj", "b", "paabpsbb", "ptto", "cypo", "yvpo"]
)
@pytest.mark.parametrize("text", ["", "3 4", "3 nope", "λ🙂"])
def test_terminal_states(commands, text):
    check(encode(commands), text, coins=(0, 1) * 100, limit=100)


@pytest.mark.parametrize("shard", range(8))
def test_halving(shard):
    for value in range(-1024 + shard * 256, min(-1024 + (shard + 1) * 256, 1025)):
        for repeat in (1, 2, 3, 7):
            expected = value
            for _ in range(repeat):
                expected = floor(Fraction(expected, 2))
            state, _ = _advance(((value,), (), 0, 0, repeat), "h", 1, (), ())
            assert state == ((expected,), (), 0, 1, 1)
    if shard == 7:
        state, _ = _advance(((1024,), (), 0, 0, 7), "h", 1, (), ())
        assert state == ((8,), (), 0, 1, 1)


@pytest.mark.parametrize(("commands", "draws"), [("yp", 1), ("cyp", 7), ("cysp", 7)])
def test_random_successors(commands, draws):
    source = encode(commands)
    vm = _Machine(source, ScriptedIO(""), Coins(()))
    before = vm.snapshot()
    observed = vm.branching_successors(vm.branching_snapshot(), 1 << draws)
    expected = []
    for coins in itertools.product((0, 1), repeat=draws):
        ref = Reference(source, "", coins)
        port = ScriptedIO("")
        rng = Coins(coins)
        machine = _Machine(source, port, rng)
        ref.step()
        machine.step()
        compare(machine, ref, port, rng)
        expected.append(
            (tuple(ref.tape), tuple(ref.loops), ref.pointer, ref.cursor, ref.repeat)
        )
    assert sorted(observed, key=repr) == sorted(expected, key=repr)
    assert vm.snapshot() == before


@pytest.mark.parametrize("n", [1, 2, 3])
def test_small_generated_tables(n):
    for bits in itertools.product("01", repeat=1 << n):
        table = "".join(bits)
        source = painfuck(table)
        for row, answer in enumerate(table):
            result = check(source, " ".join(format(row, f"0{n}b")))
            assert result["halted"]
            assert result["output"] == answer
            assert result["reads"] == n


def test_primitive_transitions():
    for tape, ptr, repeats, command in itertools.product(
        [(0,), (-3,), (-1, 2), (0, 7, 2), (2, -1, 3)],
        range(3),
        [1, 2, 3, 7],
        "psrlkzwqdeou",
    ):
        if ptr >= len(tape):
            continue
        memory = list(tape)
        pointer = ptr
        output = []
        halted = False
        for _ in range(repeats):
            if command == "p":
                memory[pointer] += 2
            elif command == "s":
                memory[pointer] -= 1
            elif command == "r":
                pointer += 2
                memory.extend([0] * max(0, pointer + 1 - len(memory)))
            elif command == "l":
                pointer = max(0, pointer - 1)
            elif command == "k":
                memory[pointer] *= memory[pointer]
            elif command == "z":
                memory[pointer] = 0
            elif command == "w":
                memory[pointer] = (
                    memory[pointer + 1] if pointer + 1 < len(memory) else 0
                )
            elif command == "q":
                if pointer:
                    memory[pointer] = memory[pointer - 1]
            elif command == "d":
                pointer = 0
            elif command == "e":
                halted = True
                break
            else:
                output.append(
                    (
                        memory[pointer] if command == "o" else memory[pointer] % 256,
                        command == "u",
                    )
                )
        observed, effects = _advance((tape, (), ptr, 0, repeats), command, 1, (), ())
        assert observed == (tuple(memory), (), pointer, 1, 0 if halted else 1), (
            tape,
            ptr,
            repeats,
            command,
            observed,
        )
        expanded = [
            (effect.value, effect.as_char)
            for effect in effects
            for _ in range(effect.count)
        ]
        assert expanded == output


@pytest.mark.parametrize("count", range(6))
def test_chained_previous_repeat(count):
    result = check(encode("p" + "t" * count + "o"))
    assert result["output"] == str(3 ** (count + 1) - 1)


@pytest.mark.parametrize("runs", [1, 2])
@pytest.mark.parametrize("trailing", [1, 2, 3])
def test_repeat_multiplier(runs, trailing):
    commands = "c" * runs + "t" * trailing + "p"
    state, effects = _advance(((0,), (), 0, 0, 1), commands, len(commands), (), ())
    assert state == (
        (2 * (7**runs) ** ((3 ** (trailing + 1) - 1) // 2),),
        (),
        0,
        len(commands),
        1,
    )
    assert not effects


@pytest.mark.parametrize(
    ("commands", "text"),
    [
        ("t", ""),
        ("tt", ""),
        ("ijo", "7 A"),
        ("ju", "λ"),
        ("pab", ""),
        ("zab", ""),
        ("pajb", "AAAA"),
        ("ppassb", ""),
        ("paaabb", ""),
    ],
)
def test_io_loops_and_empty_repeat(commands, text):
    check(encode(commands), text, limit=100)


@pytest.mark.parametrize("table", ["1111111100000000", "1000000000000000"])
def test_legacy_generated_sources(table):
    source = painfuck(table)
    for row, answer in enumerate(table):
        result = check(source, " ".join(format(row, "04b")))
        assert result["halted"]
        assert result["output"] == answer
        assert result["reads"] == 4


@pytest.mark.parametrize(
    ("n", "perm", "start"),
    [
        (n, perm, start)
        for n in range(1, 4)
        for perm in itertools.permutations(range(n))
        for start in range(0, 1 << (1 << n), 16)
    ],
)
def test_private_input_orders(n, perm, start):
    from esolangs.tools.painfuck import _painfuck_ordered

    count = 1 << n
    for number in range(start, min(start + 16, 1 << count)):
        table = format(number, f"0{count}b")
        ordered = []
        for row in range(count):
            physical = 0
            for level, bit in enumerate(perm):
                physical |= ((row >> (n - 1 - level)) & 1) << (n - 1 - bit)
            ordered.append(table[physical])
        source = _painfuck_ordered("".join(ordered), perm)
        for row, answer in enumerate(table):
            result = check(source, " ".join(format(row, f"0{n}b")))
            assert result["halted"]
            assert result["output"] == answer
            assert result["reads"] == n


@pytest.mark.parametrize(
    ("commands", "expected"),
    [("pco", "2" * 7), ("pcu", "\x02" * 7), ("pot", "2" * 4), ("sut", "ÿ" * 4)],
)
def test_repeated_output(commands, expected):
    result = check(encode(commands))
    assert result["halted"]
    assert result["output"] == expected
