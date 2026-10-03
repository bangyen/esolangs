"""Independent Eval state, call and generated-function verification."""

import itertools
import random

import pytest

from esolangs import generate
from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.eval import _Machine
from esolangs.tools.eval_lang import eval as generate_eval
from esolangs.vm import run_until_halt_or_ancestor
from tests.interpreters.eval_reference import InvalidOperationError, Reference


def check(source, limit=128):
    reference = Reference(source)
    io = ScriptedIO("")
    native = _Machine(source, io)
    for _ in range(limit):
        assert native.snapshot() == reference.state(), source
        assert native.ip == (
            len(reference.frames),
            reference.frames[-1][1] if reference.frames else len(source),
        )
        assert native.stack == reference.stacks[reference.active]
        assert io.getvalue() == reference.output, source
        assert native.halted == reference.halted
        if reference.halted:
            native.step()
            assert native.snapshot() == reference.state()
            assert io.getvalue() == reference.output
            return reference
        try:
            reference.step()
        except InvalidOperationError:
            with pytest.raises(HaltError):
                native.step()
            assert native.snapshot() == reference.state()
            assert io.getvalue() == reference.output
            return reference
        native.step()
    pytest.fail("bounded Eval control exhausted")


@pytest.mark.medium
def test_short_commands_and_string_stack_contexts():
    for length in range(5):
        for symbols in itertools.product("0`^+-.=;~*?!", repeat=length):
            check("".join(symbols))
    for prefix in ('""', '"abc"', '"`"', "'x\"", '"0+."', "0=~", "0+0++"):
        for length in range(3):
            for symbols in itertools.product("^+-.=;~*?!", repeat=length):
                check(prefix + "".join(symbols))


@pytest.mark.parametrize(
    "source",
    [
        '"unterminated',
        "'unterminated",
        '0+."a"."b".',
        '"0+."!.',
        '"0+."!0+.',
        '"`0+.``!"!',
        '""!0+.',
    ],
)
def test_literals_nested_calls_and_returns(source):
    check(source)


def test_every_printable_unknown_command_is_inert():
    for codepoint in range(0x20, 0x7F):
        if chr(codepoint) not in "0`^+-.=;~*?!\"'":
            check('"abc"0' + chr(codepoint) + ".")


def instantiate(template, bits):
    chunks = template.split("$$")
    assert len(chunks) == len(bits) + 1
    return (
        "".join(
            piece + ("`=" if bit == "1" else "0=")
            for piece, bit in zip(chunks[:-1], bits, strict=True)
        )
        + chunks[-1]
    )


def check_generated(template, table):
    n = len(table).bit_length() - 1
    for row, expected in enumerate(table):
        reference = check(instantiate(template, f"{row:0{n}b}"), limit=10000)
        assert reference.halted
        assert reference.output == expected
        assert all(not stack for stack in reference.stacks)


@pytest.mark.slow
def test_all_small_generated_tables_and_public_widths():
    for n in range(1, 4):
        for value in range(1 << (1 << n)):
            table = f"{value:0{1 << n}b}"
            for width in (None, 1, 3, 11):
                template = (
                    generate_eval(table)
                    if width is None
                    else str(generate("Eval", table, width=width))
                )
                check_generated(template, table)


@pytest.mark.slow
def test_wider_generated_tables():
    for n in (4, 5, 6):
        rng = random.Random(n)
        tables = [f"{rng.getrandbits(1 << n):0{1 << n}b}" for _ in range(4)]
        tables += [
            "0" * (1 << n),
            "1" * (1 << n),
            "01" * (1 << (n - 1)),
            "1" + "0" * ((1 << n) - 1),
            "".join(str(row.bit_count() & 1) for row in range(1 << n)),
        ]
        for table in tables:
            check_generated(generate_eval(table), table)


@pytest.mark.medium
def test_recursive_replay_and_changing_store_positive_controls():
    for counter in (1, 2, 7, 16):
        source = '"^~-^=~?!"0' + "+" * counter + "=^!"
        reference = check(source, limit=1000)
        assert reference.halted
        assert reference.stacks[1] == [0]
        assert run_until_halt_or_ancestor(_Machine(source, ScriptedIO("")))
    for source in ('"^!"^!', '"0+.^!"^0+?!0.'):
        reference = Reference(source)
        keys = []
        for _ in range(100):
            depth = len(reference.frames)
            reference.step()
            if len(reference.frames) > depth:
                key = (
                    reference.frames[-1][0],
                    reference.active,
                    tuple(tuple(stack) for stack in reference.stacks),
                )
                keys = keys[: depth - 1]
                if key in keys:
                    break
                keys.append(key)
        else:
            pytest.fail("recursive control failed to replay its entry state")
        assert run_until_halt_or_ancestor(_Machine(source, ScriptedIO(""))) is False


@pytest.mark.medium
def test_generated_positive_controls():
    for table in (
        "00",
        "01",
        "10",
        "11",
        "0110",
        "0011",
        "10000000",
        "01101001",
        "0100",
        "01000000",
    ):
        check_generated(generate_eval(table), table)
