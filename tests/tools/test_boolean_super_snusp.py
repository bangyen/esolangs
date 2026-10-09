"""Super SNUSP through the shared API, CLI and machinery."""

import pytest

from esolangs import tools as boolean


class TestSuperSNUSPWidth:
    """SNUSP's mirrors, which make this the cheapest fold of any generator here."""

    @staticmethod
    def _run(program: str, bits: list[str]) -> str:
        import esolangs

        stdin = "".join(f"{bit}" for bit in bits)
        return esolangs.run("Super SNUSP", program, stdin=stdin, timeout=5.0).strip()

    def test_a_width_folds_the_line_and_it_still_computes(self) -> None:
        """The folded pointer computes what the straight one did."""
        for table in ("0110", "01101001", "0110100110010110"):
            n = len(table).bit_length() - 1
            flat = boolean.super_snusp(table)
            wide = max(len(row) for row in flat.splitlines())
            floor = max(len(row) for row in boolean.super_snusp(table, 1).splitlines())
            assert floor < wide, f"{table} never narrows"
            for width in (1, 6, 12, 20, wide):
                narrow = boolean.super_snusp(table, width)
                columns = max(len(row) for row in narrow.splitlines())
                assert columns <= max(width, floor), (table, width, columns)
                for combo in range(2**n):
                    bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                    assert self._run(narrow, bits) == table[combo], (table, width)

    def test_both_mirrors_are_used(self) -> None:
        """A program long enough to fold twice turns round and back again."""
        table = "".join(str(bin(i).count("1") % 2) for i in range(32))
        narrow = boolean.super_snusp(table, 12)
        assert "\\" in narrow, narrow
        assert "/" in narrow, narrow
        assert narrow.count("\\") >= 2, "an east-to-west turn is two mirrors"
        assert narrow.count("/") >= 2, "so is a west-to-east one"

    def test_a_digit_run_is_never_split_by_a_fold(self) -> None:
        """``48`` has to stay on one row: a mirror in between would make it 4, 8."""
        for width in range(4, 20):
            narrow = boolean.super_snusp("0110100110010110", width)
            # A westward row reads right to left on the page.
            assert "48" in narrow or "84" in narrow, (width, narrow)


@pytest.mark.parametrize("inputs", [1, 3, 5, 8])
@pytest.mark.parametrize("width", [1, 3, 4])
def test_super_snusp_arithmetic_literals_preserve_stack_and_floor(
    inputs: int, width: int
) -> None:
    import esolangs

    table = "".join(str(row.bit_count() % 2) for row in range(1 << inputs))
    program = esolangs.generate("Super SNUSP", table, width=width)
    assert max(map(len, program.splitlines())) <= max(3, width)
    for row in (0, 1, len(table) // 2, len(table) - 1):
        bits = [int(bit) for bit in format(row, f"0{inputs}b")]
        stdin = esolangs.encode_inputs("Super SNUSP", bits)
        assert esolangs.run("Super SNUSP", program, stdin=stdin) == table[row]
