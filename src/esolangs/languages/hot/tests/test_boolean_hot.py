"""Tests for the Hot Boolean generator."""

from unittest.mock import patch as mock_patch

import pytest

import esolangs
from esolangs.runtime.io import ScriptedIO
from scripts.docs.evidence import construction_boundaries
from tests.support.event_io import ReadFirstIO
from tests.support.generator_support import assert_every_row, three_input_corpus_size
from tests.support.witness_tables import SMALL_TABLES as TABLES


def test_every_row_prints_its_answer(monkeypatch) -> None:
    """Each row's stdin is what the registry's BooleanContract encodes."""
    for table in (*TABLES, "00010111", "01101001", "11101000"):
        assert_every_row("Hot", table)
    from esolangs.languages.hot import generator

    canonical = generator.subtree_ids

    def wrong_children(table):
        ids = [list(row) for row in canonical(table)]
        ids[1][1] = ids[1][0]
        return ids

    with monkeypatch.context() as patch:
        patch.setattr(generator, "subtree_ids", wrong_children)
        with pytest.raises(AssertionError):
            assert_every_row("Hot", "0011")


def test_the_bits_are_one_unseparated_string(monkeypatch) -> None:
    assert esolangs.encode_inputs("Hot", [1, 0]) == "10"

    from esolangs.languages.hot import interpreter
    from tests.support.prepared_support import check_image_reuse

    check_image_reuse(
        "Hot",
        esolangs.generate("Hot", "01").source,
        interpreter,
        "_prepare_source",
        monkeypatch,
        cases=(("1", "1"), ("0", "0"), ("1", "1")),
    )


def test_an_ignored_input_folds_its_subtree() -> None:
    """Inputs 0 and 1 are ignored, so their pairs are ``K`` of one half."""
    folded = len(esolangs.generate("Hot", "0110" * 4).source)
    assert folded < len(esolangs.generate("Hot", "0110100110010110").source)


@pytest.mark.parametrize("n", [1, 3, 4, 6, 7, 8, 12])
def test_constants_read_first_and_leave_the_next_record(n) -> None:
    from esolangs.languages.hot.interpreter import _Machine

    rows = range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1)
    for bit in "01":
        for options in ({}, {"width": 1}, {"balance": True}):
            program = esolangs.generate("Hot", bit * (1 << n), **options).source
            if not options:
                assert len(program) == 4 * n + 3
            for row in rows:
                io = ReadFirstIO(format(row, f"0{n}b") + "Q", expected=n)
                machine = _Machine(program, io)
                steps = 0
                while not machine.halted and steps <= 4 * n + 3:
                    machine.step()
                    steps += 1
                assert machine.halted
                assert steps == 4 * n + 3
                assert machine.pending is None
                assert io.getvalue() == bit
                assert io.reads == n
                assert io.input_char() == ord("Q")


def test_three_input_corpus_size(monkeypatch) -> None:
    _check_majority()
    assert three_input_corpus_size("Hot") == 98234
    from esolangs.languages.hot import generator

    table = "00010111"
    admitted = esolangs.generate("Hot", table)
    with monkeypatch.context() as patch:
        patch.setattr(generator, "symmetric_outputs", lambda _table, _n: None)
        generic = esolangs.generate("Hot", table)
        assert len(generic.source) > len(admitted.source)
        assert_every_row("Hot", table, program=generic)


def _check_majority() -> None:
    from esolangs.languages.hot import generator
    from esolangs.languages.hot.interpreter import _Machine

    language = esolangs.Language("Hot")
    for witness in construction_boundaries(language.name)["majority_pair_admission"]:
        n, table = witness.arity, witness.table()
        with mock_patch.object(generator, "_tree", wraps=generator._tree) as tree:
            artifact = language.generate(table)
        assert tree.call_count == 1
        assert tree.call_args.kwargs["majority"] == (witness.rule == "majority")
        restored = language.from_json(language.to_json(artifact))
        prepared = language.prepare(restored)
        for row, expected in enumerate(table):
            bits = [int(bit) for bit in f"{row:0{n}b}"]
            result = prepared.evaluate(bits)
            assert result.answer == expected
            assert result.observation.input_position == len(
                language.encode_inputs(bits)
            )

    for n, size in ((2, 253), (3, 353), (7, 1313), (8, 1999)):
        table = "".join(str(int(2 * row.bit_count() > n)) for row in range(1 << n))
        for options in ({}, {"width": 1}, {"balance": True}):
            program = esolangs.generate("Hot", table, **options).source
            if not options:
                assert len(program) == size
            for row in (0, (1 << n) // 3, (1 << n) - 1):
                io = ScriptedIO(f"{row:0{n}b}" + "Q")
                machine = _Machine(program, io)
                while not machine.halted:
                    machine.step()
                assert io.getvalue() == table[row]
                assert io.reads == n
                assert io.past_end == 0
                assert machine.pending is None
                assert io.input_char() == ord("Q")
