"""bitdeque generator tests."""

import itertools

import pytest

from tests.proofs.conventions import _embedding, _tables
from tests.support.witness_tables import witnesses


class TestParameterizedBitdeque:
    """Input-by-substitution boolean generator for the no-input language Bitdeque."""

    def run_bitdeque(self, prog: str) -> str:
        from esolangs.languages.bitdeque.interpreter import run
        from esolangs.runtime.io import ScriptedIO

        io = ScriptedIO()
        run(prog, io)
        return io.getvalue().strip()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        # Deliberately the shipped fill rather than a copy of its rule: an
        # earlier duplicate here kept passing after the load order changed
        # under it, so the suite disagreed with the harness it is meant to
        # mirror.
        from tests.generators.fills import fill

        _fill_bitdeque = fill("Bitdeque")

        return _fill_bitdeque(tpl, bits)

    def test_template_is_input_independent(self) -> None:
        """The template has input runs, not hardcoded bits."""
        from esolangs.generation.helpers import runs
        from esolangs.languages import generators
        from esolangs.languages.bitdeque.generator import BITDEQUE_PAIR

        for n in (2, 5):
            template = generators.bitdeque("0110" * 2 ** (n - 2))
            assert "{X" not in template
            setters = (BITDEQUE_PAIR,) * n
            spans = runs(template, "$", setters)
            assert [end - start for start, end in spans] == [11] * n

    def test_odd_inputs_are_pushed_complemented(self) -> None:
        """The load flips the register per block; the tree's table absorbs it."""
        from esolangs.languages import generators
        from esolangs.languages.bitdeque.interpreter import run
        from esolangs.runtime.io import ScriptedIO

        template = generators.bitdeque("0101")
        prelude_and_load = " ".join(self.instantiate(template, [0, 1]).split()[:12])
        io = ScriptedIO()
        run(prelude_and_load, io)
        assert io.getvalue() == "0 0"  # input 1's one pushed as a zero
        for bits in ([0, 0], [0, 1], [1, 0], [1, 1]):
            assert self.run_bitdeque(self.instantiate(template, bits)) == str(bits[1])

    def test_constant_leaf_and_shared_halt_trampoline(self) -> None:
        """Whole constants need no trampoline; branching leaves still share one."""
        from esolangs.languages import generators

        template = generators.bitdeque("0000")
        assert "POP" in template
        assert "GOTO" not in template
        template = generators.bitdeque("0011")
        assert template.startswith("GOTO 4 INVERT GOTO 5 GOTO ")
        assert f"{template} ".count("GOTO 1 ") == 2
        # No constant above the leaves: each last level halts through it.
        template = generators.bitdeque("01101001")
        assert f"{template} ".count("GOTO 1 ") == 4


@pytest.mark.parametrize("width", [1, 7, 9, 10, 11, 40, 80])
def test_bitdeque_short_load_witness_tables(width: int) -> None:
    import esolangs

    for n in range(1, 4):
        for table in witnesses(n):
            template = esolangs.generate("Bitdeque", table, width=width)
            for row, expected in enumerate(table):
                bits = list(map(int, format(row, f"0{n}b")))
                program = esolangs.instantiate("Bitdeque", template, bits)
                assert esolangs.run("Bitdeque", program) == expected


def test_bitdeque_short_load_floor_and_rendered_total() -> None:
    import esolangs

    template = esolangs.generate("Bitdeque", "0110", width=1)
    assert max(map(len, template.splitlines())) == 7
    for row in range(4):
        program = esolangs.instantiate("Bitdeque", template, [row // 2, row % 2])
        assert max(map(len, program.splitlines())) == 7
    assert (
        sum(
            len(esolangs.generate("Bitdeque", format(value, "08b"), width=1))
            for value in range(256)
        )
        == 115963
    )


def test_bitdeque_width_eleven_is_the_normal_load() -> None:
    """Width 10 still takes the short load; from 11 the eleven-cell one is smaller."""
    import esolangs

    sizes = [
        len(esolangs.generate("Bitdeque", "0110", width=width)) for width in (10, 11)
    ]
    assert sizes == [308, 140]


@pytest.mark.parametrize("width", [1, 9, 40, 80])
def test_bitdeque_short_load_saved_source_and_large_tables(width: int) -> None:
    import esolangs

    for n in range(4, 7):
        table = "".join(str(row.bit_count() % 2) for row in range(2**n))
        template = str(esolangs.generate("Bitdeque", table, width=width))
        for row in [0, 1, 2**n // 3, 2**n - 1]:
            bits = list(map(int, format(row, f"0{n}b")))
            program = esolangs.instantiate(
                "Bitdeque", template, bits, truth_table=table
            )
            assert esolangs.run("Bitdeque", program) == table[row]


def test_bitdeque_short_load_rejects_changed_prefix() -> None:
    from esolangs.languages.bitdeque.generator import bitdeque, bitdeque_setters

    template = bitdeque("0110", 1)
    pair = bitdeque_setters(template, 2)
    assert pair == (("POP  ", "EJECT"),) * 2
    with pytest.raises(ValueError, match="shorter than"):
        bitdeque_setters(template.replace("GOTO 17", "GOTO 18"), 2)


def test_bitdeque_short_load_rejects_wrong_table_provenance() -> None:
    import esolangs

    template = str(esolangs.generate("Bitdeque", "0110", width=9))
    with pytest.raises(esolangs.TemplateError, match="not the template"):
        esolangs.instantiate("Bitdeque", template, [0, 1], truth_table="0001")


def test_bitdeque_filled_template_is_one_width() -> None:
    """The route the equal-width test misses stays at one length."""
    example = _embedding()["Bitdeque"]
    assert example.fill is not None
    for n in (4, 5):
        template = example.generator(_tables(n)[0])
        lengths = {
            len(example.fill(template, list(bits)))
            for bits in itertools.product((0, 1), repeat=n)
        }
        assert len(lengths) == 1, (n, sorted(lengths))


@pytest.mark.medium
def test_constant_native_and_short_loads_keep_all_slots() -> None:
    import esolangs
    from esolangs.generation.helpers import TEMPLATE_CHAR
    from esolangs.languages.bitdeque.generator import bitdeque_setters
    from esolangs.languages.bitdeque.interpreter import _Machine
    from esolangs.languages.bitdeque.proof_formulas import workspace
    from esolangs.runtime.io import ScriptedIO
    from scripts.benchmark import WrittenState

    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                table = bit * (1 << n)
                template = esolangs.generate("Bitdeque", table, **options)
                short = options == {"width": 1} and n <= 4
                assert template.count(TEMPLATE_CHAR) == n * (5 if short else 11)
                assert len(bitdeque_setters(str(template), n)) == n
                if not options:
                    assert len(template) == 16 * n + 8 + 7 * int(bit)
                rows = range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1)
                for row in rows:
                    inputs = list(map(int, format(row, f"0{n}b")))
                    program = esolangs.instantiate("Bitdeque", str(template), inputs)
                    assert len(program) == len(template)
                    io = ScriptedIO()
                    machine = _Machine(program, io)
                    written = WrittenState(machine.snapshot())
                    steps = 0
                    while not machine.halted and steps < 500:
                        machine.step()
                        written.sample(machine.snapshot())
                        steps += 1
                    assert machine.halted
                    assert machine.deq == (int(bit),)
                    assert not io.getvalue()
                    machine.step()
                    assert io.getvalue() == bit
                    if not options:
                        assert steps + 1 == 3 * n + 3 + int(bit)
                        assert written.bits == workspace(n, template)
    assert (
        sum(len(esolangs.generate("Bitdeque", format(v, "08b"))) for v in range(256))
        == 51358
    )
