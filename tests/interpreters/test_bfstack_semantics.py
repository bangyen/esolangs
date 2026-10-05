"""Independent mutable-stack semantics, including state after runtime errors."""

import itertools
import random

import pytest

import esolangs
from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.bfstack import _Machine
from tests.interpreters.semantic_oracles import StackObservation, bfstack
from tests.interpreters.views import view as vm_view


def observed(code, stdin, cap):
    io = ScriptedIO(stdin)
    machine = _Machine(code, io)
    error = None
    try:
        for _ in range(cap):
            if machine.halted:
                break
            machine.step()
    except EOFError:
        error = "EOFError"
    except HaltError:
        error = "HaltError"
    except ValueError:
        error = "ValueError"
    return StackObservation(
        io.getvalue(),
        tuple(vm_view(machine, "stack")),
        tuple(machine.lst),
        tuple(vm_view(machine, "memory")),
        vm_view(machine, "ip"),
        io.position(),
        machine.halted,
        error,
    )


def programs():
    yield from (
        "".join(commands)
        for n in range(4)
        for commands in itertools.product("><+-.,", repeat=n)
    )
    yield from [
        ">+.",
        ">++.",
        ">+>+<.",
        ">,.",
        ">+[>+<-]>+.",
        ">[>]",
        ">[[-]]",
        ">+-.",
        ">++-.",
        ">+>++>+++.<.<.",
        ">+>++>+++-<.",
        ">+,<.",
        ">-.",
        ">" + "+" * 256 + ".",
        ">" + "+" * 255 + ".",
        ">+[",
        ">[",
        ">[[",
        ">[[]",
        ">]",
        ">+[>+[-]<-]",
        ">+[]",
        "ignored >+.",
        ",.<,.",
        "+",
        "-",
        "<",
        ".",
        "[",
        "]",
    ]
    rng = random.Random(1704)
    pieces = [">", "<", "+", "-", ".", ",", "[", "]", "[[-]]", "[>+<-]"]
    for _ in range(64):
        yield "".join(rng.choices(pieces, k=8))


@pytest.mark.parametrize("stdin", ["", "\x00\xff", "Z\nλ"])
def test_bounded_stack_and_loop_states_match_independent_engine(stdin):
    for code in programs():
        for cap in (0, 1, 2, 5, 17, 400):
            assert observed(code, stdin, cap) == bfstack(code, stdin, cap), (
                code,
                stdin,
                cap,
            )


def test_independent_controls_pin_byte_wrap_and_stack_preservation():
    for code, stdin, output in [
        (">+.", "", "\x01"),
        (">++.", "", "\x02"),
        (">+>+<.", "", "\x01"),
        (">,.", "Z\n", "Z"),
        (">+[>+<-]>+.", "", "\x01"),
        (">[>]", "", ""),
        (">[[-]]", "", ""),
        (">+-.", "", "\x00"),
        (">++-.", "", "\x01"),
        (">+>++>+++.<.<.", "", "\x03\x02\x01"),
        (">+,<.", "Z", "\x01"),
        (">-.", "", "\xff"),
        (">" + "+" * 256 + ".", "", "\x00"),
        (",.", "λ", "λ"),
        (",+.", "λ", chr((ord("λ") + 1) % 256)),
    ]:
        result = bfstack(code, stdin, 400)
        assert result.halted
        assert result.error is None
        assert result.output == output
        assert observed(code, stdin, 400) == result


def test_independent_controls_distinguish_errors_from_step_exhaustion():
    for code, kind, halted in [
        (".", "HaltError", False),
        ("[", "HaltError", False),
        (">[", "ValueError", True),
        (">]", "HaltError", False),
        (",", "EOFError", False),
        (">+[", None, True),
    ]:
        result = bfstack(code, "", 400)
        assert result.error == kind
        assert result.halted == halted
        assert observed(code, "", 400) == result
    loop = bfstack(">+[]", "", 400)
    assert not loop.halted
    assert loop.error is None
    assert observed(">+[]", "", 400) == loop


def test_inner_close_cannot_balance_a_missing_outer_close():
    # The old suite survived mapping a close to the oldest unmatched open.
    result = bfstack(">[[]", "", 2)
    assert result.error == "ValueError"
    assert result.halted
    assert result.ip == 4
    assert observed(">[[]", "", 2) == result


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
def test_every_small_generated_table_in_independent_engine(n):
    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        code = esolangs.generate("BFStack", table)
        for row, answer in enumerate(table):
            stdin = format(row, f"0{n}b")
            result = bfstack(code, stdin, 100 * n + 8192)
            assert result.halted, (table, row)
            assert result.error is None, (table, row)
            assert result.output == answer, (table, row)
            assert observed(code, stdin, 100 * n + 8192) == result, (table, row)


@pytest.mark.medium
def test_generated_prefix_router_and_byte_decoder_in_independent_engine():
    rng = random.Random(1704)
    tables = [
        "0" * 256,
        "".join(str(row.bit_count() % 2) for row in range(256)),
        format(rng.getrandbits(256), "0256b"),
    ]
    for table in tables:
        code = esolangs.generate("BFStack", table)
        for row in (0, 1, 127, 128, 254, 255):
            stdin = format(row, "08b")
            result = bfstack(code, stdin, 8992)
            assert result.halted, (table, row)
            assert result.error is None, (table, row)
            assert result.output == table[row], (table, row)
            assert observed(code, stdin, 8992) == result, (table, row)
