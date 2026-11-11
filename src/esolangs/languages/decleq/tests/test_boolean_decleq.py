"""decleq generator tests."""

import random
from itertools import product
from unittest.mock import patch

import pytest

from esolangs.generation.wrap import balance_program, balance_score, wrap_program
from esolangs.languages.decleq import generator as boolean
from esolangs.languages.decleq.generator import (
    _CodeBuilder,
    _owner_family,
    _OwnerBuilder,
)
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from tests.generators.boolean_runners import _runner
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import assert_oisc_constants
from tests.support.witness_tables import parity as _parity

run_decleq = _runner("decleq")


class TestDecleq:
    def test_essential_bits_share_one_pass_loop(self) -> None:
        """Decrement once; ``0110`` tests input 2 under both input-1 arms."""
        assert_analysis_complement("Decleq", "read_at")
        assert_analysis_complement("Decleq", "subtree_ids")
        for table, tests in (("0110", (1, 2)), ("11110000", (1, 0, 0))):
            n = len(table).bit_length() - 1
            program = boolean.decleq(table)
            cells = [int(tok) for tok in program.split()]
            instrs = [cells[i : i + 3] for i in range(0, len(cells) - 2, 3)]
            assert sum(1 for ins in instrs if ins[0] == -1) == n  # one read each
            for i in range(n):
                rc = 17 + i
                decs = sum(1 for ins in instrs if ins[0] == ins[1] == rc)
                assert decs == (1 + tests[i] if tests[i] else 0), (table, i)

    def test_constant_subtrees_fold(self) -> None:
        halves = "1" * 16 + "0" * 16
        parity = "".join(str((row).bit_count() & 1) for row in range(32))

        def outputs(table: str) -> int:
            cells = [int(tok) for tok in boolean.decleq(table).split()]
            return cells.count(-2)

        # Addresses and ASCII operands cannot be -2; only the two gadgets print.
        _check_gadgets_and_owner_families()
        assert outputs(halves) == 2
        assert outputs(parity) == 2
        assert len(boolean.decleq(halves)) < len(boolean.decleq(parity))

    def test_size_is_linear_in_the_table(self) -> None:
        per_entry = [len(boolean.decleq(_parity(n))) / 2**n for n in (8, 10, 12)]
        assert per_entry[0] > per_entry[1] > per_entry[2]
        assert per_entry[2] < 8
        rng = random.Random(6)
        table = "".join(rng.choice("01") for _ in range(64))
        program = boolean.decleq(table)
        for combo in range(64):
            assert run_decleq(program, list(f"{combo:06b}")) == table[combo]

    def test_folded_tables_still_print_correctly(self) -> None:
        for table in ("11111111", "11110000", "11001100", "00001111"):
            program = boolean.decleq(table)
            n = len(table).bit_length() - 1
            for combo in range(2**n):
                assert run_decleq(program, list(f"{combo:0{n}b}")) == table[combo]

    def test_a_repeated_subtree_is_emitted_once(self) -> None:
        rng = random.Random(8)
        block, other = ("".join(rng.choice("01") for _ in range(64)) for _ in "ab")
        table = block + other + block + block
        program = boolean.decleq(table)
        assert len(program) < 0.9 * len(
            boolean.decleq(block + other + other[::-1] + block[::-1])
        )
        for combo in rng.sample(range(256), 48):
            assert run_decleq(program, list(f"{combo:08b}")) == table[combo]

    def test_untaken_jumps_target_zero(self) -> None:
        """Untaken jumps target 0; I/O's next-address target also fits SUBBIG."""
        cells = [int(tok) for tok in boolean.decleq("01101001").split()]
        instrs = [cells[i : i + 3] for i in range(0, len(cells) - 2, 3)]
        io = [(3 * i, c) for i, (a, _b, c) in enumerate(instrs) if a in (-1, -2)]
        assert io == [(3, 6), (9, 12), (21, 24), (24, 27), (27, 30)]
        for rc in (17, 18, 19):  # each loop decrement
            assert instrs.count([rc, rc, 0]) == 1


def test_mixed_digit_operands_share_one_grid_cell() -> None:
    # All three subleq OISCs share wrap_grid, so the language is not an axis.
    language = "decleq"
    for count in range(3, 65):
        program = " ".join(("1", "22", "333")[index % 3] for index in range(count))
        balanced = balance_program(program, language)
        optimum = min(
            [program]
            + [
                wrap_program(program, language, width)
                for width in range(1, len(program) + 1)
            ],
            key=balance_score,
        )
        assert balance_score(balanced) == balance_score(optimum)
        assert balanced.split() == program.split()


@pytest.mark.parametrize("width", [0, -1])
def test_nonpositive_width_does_not_wrap(width: int) -> None:
    assert wrap_program("a b c", "decleq", width) == "a b c"


def test_multiline_source_is_untouched() -> None:
    program = "line one\nline two"
    assert wrap_program(program, "decleq", 4) == program


@pytest.mark.medium
def test_constants_reuse_scratch_and_print_after_every_read() -> None:
    from scripts.docs.resource_evidence import resource_bounds

    workspace = resource_bounds("Decleq")["workspace"].formula

    assert_oisc_constants("Decleq", workspace, decrement=True)
    assert sum(len(boolean.decleq(format(v, "08b"))) for v in range(256)) == 42228


def _check_gadgets_and_owner_families() -> None:
    from esolangs.languages.decleq.interpreter import _Machine
    from scripts.docs.resource_evidence import resource_bounds

    workspace = resource_bounds("Decleq")["workspace"].formula

    table = "".join(str(int(row.bit_count() >= 4)) for row in range(128))
    original = boolean.decleq(table)
    with patch.object(boolean, "symmetric_outputs", return_value=None) as disabled:
        fallback = boolean.decleq(table)
        assert disabled.called
    assert len(fallback) > len(original)
    for row in (0, 1, 127):
        bits = list(f"{row:07b}")
        assert run_decleq(original, bits) == run_decleq(fallback, bits) == table[row]
    for bit in "01":
        builder = _CodeBuilder(bit, 2, [])
        assert not hasattr(builder, "is_constant")
        assert not hasattr(builder, "truth_table")
        for row in ("00", "11"):
            assert run_decleq(builder.build(), list(row)) == bit
    for n in range(1, 7):
        table = "0" * ((1 << n) - 1) + "1"
        for case in (table, table.translate(str.maketrans("01", "10"))):
            assert (
                _CodeBuilder(case, n, list(range(n))).build()
                == _OwnerBuilder(case, n, list(range(n))).build()
            )

    cells = list(map(int, boolean.decleq("01").split()))
    tree = cells[2] + 12  # one read, one normalization and its two controls
    assert cells[tree : tree + 3] == [17, 17, 3]
    cases = ["00010100"]
    for n, threshold, admitted in (
        (1, 1, True),
        (4, 2, False),
        (7, 4, True),
        (7, 7, False),
        (8, 6, True),
        (8, 7, False),
        (12, 7, True),
    ):
        table = "".join(str(int(row.bit_count() >= threshold)) for row in range(1 << n))
        assert _owner_family(table, n) == admitted
        cases.extend((table, table.translate(str.maketrans("01", "10"))))
    parity = _parity(7)
    assert not _owner_family(parity, 7)
    cases.append(parity)
    for table in cases:
        n = len(table).bit_length() - 1
        program = boolean.decleq(table)
        for row in (0, (1 << n) // 3, (1 << n) - 1):
            io = ScriptedIO(f"{row:0{n}b}Q")
            machine = _Machine(program, io)
            written = WrittenState(machine.workspace_snapshot())
            while not machine.halted:
                if machine.pc in (3, 9):
                    memory = machine.state[1]
                    assert memory[0] < 0
                    assert memory[15:17] == (48, 49)
                    assert io.reads == n
                machine.step()
                written.sample(machine.workspace_snapshot())
            assert written.bits == workspace(n, program)
            assert io.getvalue() == table[row]
            assert io.past_end == 0
            assert io.input_char() == ord("Q")


@pytest.mark.medium
@pytest.mark.parametrize("n", range(1, 9))
def test_owner_family_accepts_only_the_named_thresholds(n):
    admitted = set()
    for threshold in {3, 4, 5, 6, n // 2 + 1}:
        if threshold <= n:
            profile = "0" * threshold + "1" * (n + 1 - threshold)
            admitted.update((profile, profile.translate(str.maketrans("01", "10"))))
    for bits in product("01", repeat=n + 1):
        profile = "".join(bits)
        table = "".join(profile[row.bit_count()] for row in range(1 << n))
        assert _owner_family(table, n) == (profile in admitted)
    if n >= 2:
        table = "01" * (1 << (n - 1))
        assert not _owner_family(table, n)
