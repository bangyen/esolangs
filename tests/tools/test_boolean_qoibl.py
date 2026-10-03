"""qoibl generator tests."""

from esolangs import tools as boolean


class TestQoibl:
    def test_narrow_horner_floor_and_corpus_size(self) -> None:
        assert max(map(len, boolean.qoibl("0110", 1).splitlines())) == 2
        assert (
            sum(len(boolean.qoibl(format(v, "08b"), 1)) for v in range(256)) == 520366
        )

    def test_the_table_is_one_literal(self) -> None:
        """The whole table rides in a single binary literal, bit k for row k.

        The per-entry cost is that literal and nothing else, so the
        construction stands or falls on it appearing exactly once.
        """
        program = boolean.qoibl("0001")
        # 0b1000: row 3 is the only one set, and it is bit 3.
        assert program.count(" yeee ") == 1
        assert program.endswith("tt")

    def test_the_reads_are_one_statement_each(self) -> None:
        """Only the input count scales the statements; the table does not."""
        counts = [
            boolean.qoibl(
                "".join(str(row.bit_count() & 1) for row in range(2**n))
            ).count("\n")
            for n in range(1, 6)
        ]
        assert counts == [2, 3, 4, 5, 6]

    def test_a_constant_table_still_reads_its_inputs(self) -> None:
        """A constant function packs to zero but keeps the reads it owes."""
        program = boolean.qoibl("0000")
        assert program.count(" et ") == 2
        assert "we y we e ry yy ry" in program
