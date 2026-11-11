"""brainfuck generator tests."""

from unittest.mock import patch

import pytest

import esolangs
from esolangs.debugger import make_vm
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from scripts.docs.evidence import construction_boundaries
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import ReadFirstIO, count_steps
from tests.support.generator_support import (
    assert_shared_program,
    constant_programs,
    evaluate_generated,
    measure_run,
    three_input_corpus_size,
)
from tests.support.reference import REFERENCE


@pytest.mark.medium
def test_affine_stream_all_small_coefficients_within_ledger() -> None:
    from esolangs.languages.brainfuck.generator import _affine_stream

    assert_analysis_complement("brainfuck", "affine_form", "0110100110010110")
    with pytest.raises(ImportError):
        exec("from esolangs.languages.brainfuck.generator import bf_tree")
    _check_constants()
    _check_zero_guards()
    admitted = 0
    for n in range(1, 6):
        for mask in range(1 << n):
            for bias in (0, 1):
                table = "".join(
                    str((row & mask).bit_count() % 2 ^ bias) for row in range(1 << n)
                )
                source = _affine_stream(table)
                if source is None:
                    continue
                admitted += 1
                for row, expected in enumerate(table):
                    vm = make_vm(REFERENCE, source, stdin=f"{row:0{n}b}")
                    commands, written = measure_run(vm, limit=69 * n + 44)
                    assert vm.halted
                    assert vm.output == expected
                    assert commands <= 69 * n + 44
                    assert (
                        written.bits
                        <= 2 * n
                        + 6
                        + (2 * n).bit_length()
                        + n.bit_length()
                        + len(source).bit_length()
                    )
    assert admitted > 0
    assert _affine_stream("0001") is None


@pytest.mark.medium
def test_affine_stream_reduces_cap_parity_within_ledger() -> None:
    from esolangs.languages.brainfuck.generator import _bf_ordered

    n = 16
    table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
    previous = _bf_ordered(table, tuple(range(n)))
    assert_shared_program(
        REFERENCE,
        table,
        previous,
        69 * n + 44,
        lambda p: (
            2 * n + 6 + (2 * n).bit_length() + n.bit_length() + len(p).bit_length()
        ),
        rows=[0, 1, 2, 3, 32767, 32768, 65534, 65535],
    )


@pytest.mark.parametrize("blocks", [((1, 0), (1, 4)), ((2, 0), (1, 0)), ((3, 0),)])
def test_deferred_flags_require_ordered_distinct_levels(blocks) -> None:
    from esolangs.generation.shared_flag import flag_tree_body

    with pytest.raises(ValueError, match="deferred levels"):
        flag_tree_body("01101001", (0, 1, 2), 4, 6, shared_blocks=blocks)


@pytest.mark.medium
def test_multiple_residuals_reduce_guarded_parity_within_ledger() -> None:
    assert_analysis_complement("brainfuck", "flag_tree_body", "0001")
    with pytest.MonkeyPatch.context() as patch:
        _check_shared_body_must_be_strictly_shorter(patch)
    from esolangs.generation.shared_block import repeated_block
    from esolangs.generation.shared_flag import flag_tree_body

    n = 10
    residual = "".join(str(row.bit_count() & 1) for row in range(1 << (n - 4)))
    table = "0" * (15 * len(residual)) + residual
    body, _ = flag_tree_body(
        table, tuple(range(n)), 2 * (n - 1), 2 * n, shared=repeated_block(table)
    )
    previous = ">>".join("," + "-" * 48 for _ in range(n)) + body + "+" * 48 + "."
    assert len(esolangs.generate(REFERENCE, table).source) < len(previous)
    assert_shared_program(
        REFERENCE,
        table,
        previous,
        69 * n + 44,
        lambda p: (
            2 * n + 6 + (2 * n).bit_length() + n.bit_length() + len(p).bit_length()
        ),
        rows=[
            *range(15 * len(residual), len(table)),
            *[prefix * len(residual) + len(residual) - 1 for prefix in range(15)],
        ],
    )


@pytest.mark.medium
@pytest.mark.parametrize("n", [2, 3, 6])
def test_literal_counter_consumes_inputs_within_revised_bounds(n: int) -> None:
    from esolangs.languages.brainfuck.generator import brainfuck

    if n == 2:
        _check_literal_counter_cutoff()

    size = 1 << n
    for exceptional in (0, size // 3, size - 1):
        product = "0" * exceptional + "1" + "0" * (size - exceptional - 1)
        for table in (product, product.translate(str.maketrans("01", "10"))):
            source = brainfuck(table)
            for row, expected in enumerate(table):
                vm = make_vm(REFERENCE, source, stdin=f"{row:0{n}b}")
                commands, written = measure_run(vm, limit=75 * n + 49)
                assert vm.halted
                assert vm.output == expected
                assert vm.snapshot()[-1] == n
                assert commands <= 75 * n + 49
                assert written.bits <= (
                    max(7 * n, 2 * n + 7)
                    + (2 * n).bit_length()
                    + n.bit_length()
                    + len(source).bit_length()
                )


def _check_literal_counter_cutoff() -> None:
    from esolangs.languages.brainfuck import generator

    language = esolangs.Language(REFERENCE)
    witnesses = construction_boundaries(language.name)["literal_counter_arity_cutoff"]
    for witness in witnesses:
        n, table = witness.arity, witness.table()
        with patch.object(
            generator, "_counter_reads", wraps=generator._counter_reads
        ) as counter:
            artifact = language.generate(table)
        assert counter.call_count == 2 * int(n == 2)
        restored = language.load_program(language.dump_program(artifact))
        prepared = language.prepare(restored)
        for row, expected in enumerate(table):
            result = prepared.evaluate([int(bit) for bit in f"{row:0{n}b}"])
            assert result.bit == expected
            assert result.observation.input_reads == n


def _check_constants() -> None:
    from esolangs.languages.brainfuck.interpreter import _Machine

    for n, bit, _options, program in constant_programs("brainfuck", range(2, 13)):
        for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
            stdin = esolangs.encode_inputs("brainfuck", list(map(int, f"{row:0{n}b}")))
            io = ReadFirstIO(stdin + "Q", expected=n)
            machine = _Machine(program, io)
            written = WrittenState(machine.workspace_snapshot())
            steps = 0
            while not machine.halted:
                command = machine.code[machine.ind]
                machine.step()
                written.sample(machine.workspace_snapshot())
                steps += int(command in "+-<>[],.")
                assert steps <= n + 82 + int(bit)
            assert steps == n + 82 + int(bit)
            assert io.getvalue() == bit
            assert written.bits == 16 + len(program).bit_length() + n.bit_length()
            assert io.input_char() == ord("Q")
    assert three_input_corpus_size("brainfuck") == 64098


def _check_zero_guards() -> None:
    from esolangs.languages.brainfuck.interpreter import _Machine

    inverted = False
    for n, used in ((3, (0, 1, 2)), (5, (1, 3)), (7, (0, 4, 6))):
        table = "".join(
            str(int(any((row >> (n - i - 1)) & 1 for i in used)))
            for row in range(1 << n)
        )
        for options in ({}, {"width": 1}, {"balance": True}):
            source = esolangs.generate("brainfuck", table, **options).source
            inverted |= "-[+" in "".join(source.split())
            for row in (0, 1, (1 << n) - 1):
                io = ReadFirstIO(f"{row:0{n}b}Q", expected=0)
                io.expected = n
                machine = _Machine(source, io)
                written = WrittenState(machine.workspace_snapshot())
                commands = 0
                while not machine.halted:
                    command = machine.code[machine.ind]
                    machine.step()
                    written.sample(machine.workspace_snapshot())
                    commands += int(command in "+-<>[],.")
                    assert commands <= 75 * n + 49
                assert io.getvalue() == table[row]
                assert io.reads == n
                assert io.past_end == 0
                assert io.input_char() == ord("Q")
                assert written.bits <= (
                    max(7 * n, 2 * n + 7)
                    + (2 * n).bit_length()
                    + n.bit_length()
                    + len(source).bit_length()
                )
    assert inverted


def _check_shared_body_must_be_strictly_shorter(monkeypatch) -> None:
    import importlib

    from esolangs.generation.helpers import move_text
    from esolangs.generation.shared_flag import shared_flag_tree
    from esolangs.languages.brainfuck.interpreter import _Machine

    module = importlib.import_module("esolangs.languages.brainfuck.generator")
    assert module.shared_flag_tree is shared_flag_tree
    monkeypatch.setattr(
        module,
        "shared_flag_tree",
        lambda _table, _perm, start, result, **_kw: (
            move_text(start, result, ">", "<") + "+",
            abs(result - start) + 1,
        ),
    )
    assert evaluate_generated("brainfuck", "0001") == "1111"
    table, order, tail = "0011", (0, 1), "+" * 48 + "."
    monkeypatch.setattr(module, "shared_flag_tree", lambda *_a, **_k: None)
    plain = module._tree_for(table, order, tail)
    header = ">>".join("," + "-" * 48 for _ in order)
    body = plain[len(header) : -len(tail)] + "><"
    # An admitted alternative may be equivalent while its text is longer.
    monkeypatch.setattr(
        module, "shared_flag_tree", lambda *_a, **kw: (body, kw["command_budget"])
    )
    assert module._tree_for(table, order, tail) == plain
    for source in (plain, header + body + tail):
        for row in range(4):
            io = ScriptedIO(f"{row:02b}")
            machine = _Machine(source, io)
            count_steps(machine, 69 * 2 + 44)
            assert io.getvalue() == table[row]
