"""suffolk generator tests."""

import pytest

import esolangs
from esolangs.languages.suffolk import generator as boolean
from esolangs.languages.suffolk.tests.lookup_support import _suffolk_lookup
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from scripts.docs.evidence import construction_boundaries
from tests.generators.boolean_runners import _runner
from tests.support.event_io import ReadFirstIO, count_steps
from tests.support.witness_tables import row_bits

run_suffolk = _runner("suffolk")


class TestSuffolk:
    def test_streaming_fold_scales_linearly(self) -> None:
        """Doubling a dense table stays below twice plus fixed setup."""
        sizes = []
        for n in (8, 9, 10):
            table = "".join(str((i * 73 + i.bit_count()) & 1) for i in range(2**n))
            sizes.append(len(boolean.suffolk(table)))
        assert sizes == [1612, 2447, 2920]
        assert sizes[2] < 2 * sizes[1]

    def test_constant_tables_collapse_but_still_read(self) -> None:
        """Constants print after n reads, then stop at the first EOF probe."""
        _check_stored_input_records()

        from esolangs.languages.suffolk.interpreter import _Machine

        for n in range(1, 13):
            for bit in "01":
                length = 2 * n + 51 + int(bit)
                for options in ({}, {"width": 1}, {"balance": True}):
                    program = esolangs.generate(
                        "Suffolk", bit * (1 << n), **options
                    ).source
                    for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                        stdin = f"{row:0{n}b}"
                        io = ReadFirstIO(stdin + "Q", expected=n)
                        machine = _Machine("".join(program.split()), io)
                        for _ in range(length):
                            machine.step()
                        assert io.getvalue() == bit
                        assert io.input_char() == ord("Q")
                        io = ReadFirstIO(stdin, expected=n)
                        machine = _Machine("".join(program.split()), io)
                        written = WrittenState(machine.workspace_snapshot())
                        for _ in range(length + 1):
                            machine.step()
                            written.sample(machine.workspace_snapshot())
                        assert machine.halted
                        assert io.getvalue() == bit
                        assert (
                            written.bits
                            == 13 + (length - 1).bit_length() + n.bit_length()
                        )
        assert sum(len(boolean.suffolk(f"{v:08b}")) for v in range(256)) == 121196

    def test_size_tracks_steps_rather_than_ones(self) -> None:
        """Cost is one op per *step* of a half-table, not per one-row."""
        tables = "10000000 10010000 11100000 11101000 11111000 11111001 11111110"
        groups: dict[tuple[int, ...], set[int]] = {}
        for table in tables.split():
            half = len(table) // 2
            profile = tuple(
                sum(a != b for a, b in zip(part, f"{part[1:]}0", strict=True))
                for part in (table[:half], table[half:])
            )
            groups.setdefault(profile, set()).add(len(_suffolk_lookup(table)))
            assert len(boolean.suffolk(table)) <= len(_suffolk_lookup(table))
        assert sorted(groups) == [(1, 0), (1, 1), (1, 3), (3, 0)]
        assert all(len(sizes) == 1 for sizes in groups.values())  # profile fixes it
        assert min(groups[(1, 0)]) < min(groups[(3, 0)])  # more steps cost more
        assert min(groups[(1, 1)]) < min(groups[(1, 3)])

    @pytest.mark.parametrize(
        "table",
        ["11111110", "1111111111111110", "0111111111111111", "11111100"],
    )
    def test_complemented_tables_still_compute(self, table: str) -> None:
        """The inverted print stage answers the original table, not its flip."""
        n = (len(table) - 1).bit_length()
        program = boolean.suffolk(table)
        for combo in range(2**n):
            bits = row_bits(combo, n)
            got = run_suffolk(program, [str(b) for b in bits])
            assert got == table[combo], f"inputs {bits}"


def _check_stored_input_records() -> None:
    from esolangs.languages.suffolk.interpreter import _Machine
    from scripts.docs.resource_evidence import resource_bounds

    workspace = resource_bounds("Suffolk")["workspace"].formula
    for n in (2, 6, 8):
        for ignored in (False, True):
            table = "".join(
                str((row >> int(ignored)).bit_count() % 2) for row in range(1 << n)
            )
            records = (0, (1 << n) - 1, (1 << n) // 3)
            for options in ({}, {"width": 1}, {"balance": True}):
                program = esolangs.generate("Suffolk", table, **options).source
                commands = "".join(program.split())
                io = ScriptedIO("".join(f"{r:0{n}b}" for r in records))
                machine = _Machine(commands, io)
                written = WrittenState(machine.workspace_snapshot())
                count_steps(
                    machine,
                    3 * len(commands) + commands.index(",") + 1,
                    written=written,
                )
                assert io.getvalue() == "".join(table[r] for r in records)
                assert io.progress() == 3 * n
                assert io.past_end == 1
                if n >= 3:
                    # Three records enlarge only the input-cursor field.
                    assert written.bits <= workspace(n, commands) + 2
                io = ScriptedIO(f"{records[0]:0{n}b}Q")
                machine = _Machine(commands, io)
                for _ in commands:
                    machine.step()
                assert io.getvalue() == table[records[0]]
                assert io.input_char() == ord("Q")


def test_countdown_reader_cutoff() -> None:
    from esolangs.languages.suffolk.interpreter import _Machine

    for witness in construction_boundaries("Suffolk")["stored_inputs_to_countdown"]:
        n, table = witness.arity, witness.table()
        program = _suffolk_lookup(table)
        assert program.index(",") + 1 == (51 if n == 10 else 153)
        records = (0, (1 << n) - 1, (1 << n) // 3)
        machine = _Machine(program, ScriptedIO("".join(f"{r:0{n}b}" for r in records)))
        count_steps(machine, 3 * len(program) + program.index(",") + 1)
        assert machine.io.getvalue() == "".join(table[r] for r in records)
        assert machine.io.past_end == 1
