"""Dialect combinations retain behavior at storage and layout boundaries."""

from functools import cache

import pytest

import esolangs
from esolangs import DialectSettings
from esolangs.debugger import make_debugger
from esolangs.tools.factor import _encode
from tests.interpreters.test_unary import _source as unary_source


@cache
def _source(language: str, code: str) -> str:
    if language == "Factor":
        return str(_encode(code))
    if language == "Unary":
        return unary_source(code)
    return code


@pytest.mark.parametrize("language", ["Brainfuck", "Factor", "Unary"])
@pytest.mark.parametrize("modulus", [2, 255, None])
@pytest.mark.parametrize("tape_size", [1, 2])
@pytest.mark.parametrize("boundary", ["error", "clamp", "wrap"])
@pytest.mark.parametrize("eof", ["error", "zero", "minus_one", "unchanged"])
@pytest.mark.parametrize("direction", ["<", ">"])
def test_boundary_eof_and_cell_arithmetic(
    language, modulus, tape_size, boundary, eof, direction
):
    settings = DialectSettings(
        cell_modulus=modulus, tape_size=tape_size, boundary=boundary, eof=eof
    )
    source = _source(language, "+" + direction + ",+.")
    outside = direction == "<" or tape_size == 1
    pointer = 1 if not outside else (0 if boundary != "wrap" else (-1 % tape_size))
    previous = int(pointer == 0)
    # Supplied input is the positive control: EOF must not govern a real read.
    for stdin in ("", "Ā"):
        error = (
            esolangs.HaltError
            if outside and boundary == "error"
            else (
                esolangs.InputExhaustedError if not stdin and eof == "error" else None
            )
        )
        for bounded in (False, True):
            options = {"max_steps": 32} if bounded else {}
            if error is not None:
                with pytest.raises(error):
                    esolangs.run(language, source, stdin, settings=settings, **options)
                continue
            value = (
                ord(stdin)
                if stdin
                else {"zero": 0, "minus_one": -1, "unchanged": previous}[eof]
            ) + 1
            expected = value if modulus is None else value % modulus
            assert esolangs.run(
                language, source, stdin, settings=settings, **options
            ) == chr(expected)
            debugger = make_debugger(language, source, stdin, settings=settings)
            assert debugger.run(32) == "halted"
            assert debugger.memory[pointer] == expected


@pytest.mark.parametrize(("language", "cells"), [("Brainfuck", 5), ("Factor", 6)])
@pytest.mark.parametrize("modulus", [50, 255, None])
@pytest.mark.parametrize("boundary", ["error", "clamp", "wrap"])
@pytest.mark.parametrize("eof", ["error", "zero", "minus_one", "unchanged"])
@pytest.mark.parametrize("balance", [False, True])
def test_generated_xor_at_minimum_storage(
    language, cells, modulus, boundary, eof, balance
):
    settings = DialectSettings(
        cell_modulus=modulus, tape_size=cells, boundary=boundary, eof=eof
    )
    source = esolangs.generate(language, "0110", balance=balance, settings=settings)
    assert esolangs.evaluate(language, source, inputs=2, settings=settings) == "0110"
    with pytest.raises(esolangs.ArgumentError, match="tape cells"):
        esolangs.generate(
            language,
            "0110",
            balance=balance,
            settings=DialectSettings(
                cell_modulus=modulus, tape_size=cells - 1, boundary=boundary, eof=eof
            ),
        )


@pytest.mark.parametrize("index_base", [0, 1])
@pytest.mark.parametrize("layout", [None, 1, 40, "balanced"])
@pytest.mark.parametrize("table", ["10", "10010110", "1010001111000010"])
def test_bitdeque_bases_across_layouts(index_base, layout, table):
    settings = DialectSettings(index_base=index_base)
    options = {"balance": True} if layout == "balanced" else {"width": layout}
    source = esolangs.generate("Bitdeque", table, settings=settings, **options)
    inputs = len(table).bit_length() - 1
    for row, expected in enumerate(table):
        bits = tuple(map(int, format(row, f"0{inputs}b")))
        for template in (source, str(source)):
            program = esolangs.instantiate(
                "Bitdeque", template, bits, truth_table=table, settings=settings
            )
            assert esolangs.run("Bitdeque", program, settings=settings) == expected


@pytest.mark.medium
@pytest.mark.parametrize("inputs", [1, 2, 4, 6])
@pytest.mark.parametrize("layout", [None, 1, 40, "balanced"])
def test_postfix_chunk_boundaries_across_sizes(inputs, layout):
    # Parity hides reversed input order; this deterministic mix exposes it.
    table = "".join(
        str(((row * 37) ^ (row >> 1)).bit_count() % 2) for row in range(1 << inputs)
    )
    if inputs > 1:
        reversed_inputs = "".join(
            table[int(format(row, f"0{inputs}b")[::-1], 2)]
            for row in range(1 << inputs)
        )
        assert table != reversed_inputs
    settings = DialectSettings(expression_syntax="postfix")
    options = {"balance": True} if layout == "balanced" else {"width": layout}
    source = esolangs.generate("Alight", table, settings=settings, **options)
    assert (
        esolangs.evaluate("Alight", source, inputs=inputs, settings=settings) == table
    )
