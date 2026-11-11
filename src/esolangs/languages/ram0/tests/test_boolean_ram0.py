"""Covers :mod:`esolangs.languages.ram0.generator`: the shared tree."""

import random
import re
from unittest.mock import patch

import pytest

import esolangs
from esolangs._bindings import TEMPLATE_CHAR, runs
from esolangs.generation.template import layout_tokens
from esolangs.languages.ram0 import generator as boolean
from esolangs.languages.ram0.descriptor import PAIR as RAM0_PAIR
from esolangs.languages.ram0.generator import _ram0_ordered
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from scripts.docs.evidence import construction_boundaries
from tests.support.event_io import count_steps
from tests.support.generator_support import assert_parity_at_most_doubles
from tests.support.witness_tables import row_bits


class TestParameterizedRam0:
    """Input-by-substitution boolean generator for the no-input language RAM0."""

    def run_ram0(self, prog: str) -> str:

        from esolangs.languages.ram0.interpreter import run

        io = ScriptedIO()
        run(prog, io)
        m = re.search(r"^z: (\d+)", io.getvalue(), re.MULTILINE)
        assert m is not None
        return m.group(1)

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Bind native source with explicitly declared setters."""
        from esolangs.languages.ram0.descriptor import PAIR

        bindings = esolangs.TemplateBindings(setters=(PAIR,) * len(bits))
        template = esolangs.TemplateArtifact(tpl, "RAM0", bindings)
        return esolangs.instantiate("RAM0", template, bits).source

    def test_template_is_input_independent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The template has one run per input, not hardcoded bits."""
        from esolangs.languages.ram0 import generator as generators

        assert not hasattr(generators, "PAIR")
        template = generators.ram0("0110")
        assert "{X" not in template
        assert len(runs(template, TEMPLATE_CHAR, (RAM0_PAIR,) * 2)) == 2

        for width in (None, 1):
            analyze = generators.subtree_ids
            with monkeypatch.context() as patch:
                patch.setattr(
                    generators,
                    "subtree_ids",
                    lambda table, analyze=analyze: [
                        [1] * len(layer) for layer in analyze(table)
                    ],
                )
                damaged = generators.ram0("0001", width=width)
            assert (
                "".join(
                    self.run_ram0(self.instantiate(damaged, [row >> 1, row & 1]))
                    for row in range(4)
                )
                == "1111"
            )

    def test_leaves_share_a_low_address_halt_trampoline(self) -> None:
        """Every leaf jumps to 2; only the trampoline names the end."""
        from esolangs.languages.ram0 import generator as generators

        tokens = generators.ram0("01101001").split()
        assert tokens[0] == "C"
        assert tokens.count("2") == 2
        plain = layout_tokens(_ram0_ordered("01101001", (0, 1, 2))).source.split()
        assert plain.count("2") == 8

    @staticmethod
    def _sharing_totals(tables: list[str]) -> tuple[int, int]:
        """(before, shipped) totals, each table checked not to grow."""
        from esolangs.languages.ram0 import generator as generators

        before = after = 0
        for table in tables:
            old = len(
                layout_tokens(
                    _ram0_ordered(table, tuple(range(len(table).bit_length() - 1)))
                ).source
            )
            new = len(generators.ram0(table))
            before, after = before + old, after + new
        return before, after

    def test_sharing_three_input_total(self) -> None:
        """All 256 three-input tables: 27,554 to 22,258 characters, 19.2%."""
        tables = [format(i, "08b") for i in range(256)]
        assert self._sharing_totals(tables) == (27554, 22258)

    def test_shared_tree_executes_wide_rows(self) -> None:
        """A seeded seven-input table, every row, through the shared tree."""
        from esolangs.languages.ram0 import generator as generators

        language = esolangs.Language("RAM0")
        for witness in construction_boundaries(language.name)[
            "width_one_nand_arity_cutoff"
        ]:
            n, table = witness.arity, witness.table()
            with patch.object(
                generators, "_ram0_nand", wraps=generators._ram0_nand
            ) as nand:
                artifact = language.generate(table, width=1)
            assert nand.call_count == int(n == 3)
            restored = language.load_program(language.dump_program(artifact))
            assert restored.spans == artifact.spans
            for row, expected in enumerate(table):
                result = language.evaluate(restored, row_bits(row, n))
                assert result.bit == expected
                assert result.observation.input_position == 0
                assert result.observation.input_reads == 0

        n = 7
        table = format(random.Random(7).getrandbits(2**n), f"0{2**n}b")
        template = generators.ram0(table)
        for row in range(2**n):
            bits = row_bits(row, n)
            assert self.run_ram0(self.instantiate(template, bits)) == table[row]


@pytest.mark.medium
def test_parity_source_at_most_doubles_per_input() -> None:
    assert_parity_at_most_doubles(boolean.ram0, range(11, 15))


@pytest.mark.medium
def test_constants_execute_every_fixed_width_setter() -> None:
    import esolangs
    from esolangs.languages.ram0.descriptor import PAIR
    from esolangs.languages.ram0.interpreter import _Machine
    from scripts.docs.resource_evidence import resource_bounds

    workspace = resource_bounds("RAM0")["workspace"].formula

    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                template = esolangs.generate("RAM0", bit * (1 << n), **options)
                assert len(runs(template.source, TEMPLATE_CHAR, (PAIR,) * n)) == n
                assert len(template.source) == 4 * n + 1 + 2 * int(bit)
                peak = 0
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    program = esolangs.instantiate("RAM0", template, row_bits(row, n))
                    io = ScriptedIO()
                    machine = _Machine(program.source, io)
                    written = WrittenState(machine.workspace_snapshot())
                    steps = count_steps(machine, 2 * n + 1 + int(bit), written=written)
                    machine.step()  # RAM0's post-halt dump is one command.
                    written.sample(machine.workspace_snapshot())
                    assert steps + 1 == 2 * n + 2 + int(bit)
                    assert esolangs.read_answer("RAM0", io.getvalue()) == bit
                    assert written.bits <= workspace(n, template.source)
                    peak = max(peak, written.bits)
                assert peak == workspace(n, template.source)
