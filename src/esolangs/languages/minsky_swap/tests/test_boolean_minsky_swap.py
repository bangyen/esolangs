"""minsky_swap generator tests."""

from itertools import pairwise
from unittest.mock import patch

import pytest

import esolangs
from esolangs.generation.helpers import TEMPLATE_CHAR, fill_runs, runs
from esolangs.languages.minsky_swap import generator as boolean
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from scripts.docs.evidence import construction_boundaries
from tests.support.analysis_support import assert_analysis_complement
from tests.support.event_io import count_steps
from tests.support.generator_support import (
    assert_saved_rows,
    measure_run,
    three_input_corpus_size,
)
from tests.support.witness_tables import witnesses


class TestParameterizedMinskySwap:
    """Input-by-substitution boolean generator for the no-input language Minsky Swap."""

    def run_minsky_swap(self, prog: str) -> str:
        from esolangs.languages.minsky_swap.interpreter import run

        io = ScriptedIO()
        run(prog, io)
        return io.getvalue().split()[1]

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Bind native source with explicitly declared setters."""
        from esolangs.languages.minsky_swap.generator import minsky_swap_setters

        bindings = esolangs.TemplateBindings(
            setters=minsky_swap_setters(tpl, len(bits))
        )
        template = esolangs.TemplateArtifact(tpl, "Minsky Swap", bindings)
        return esolangs.instantiate("Minsky Swap", template, bits).source

    @pytest.mark.parametrize("width", [1, 10, 15, 40, 80])
    def test_rmsn_templates_preserve_command_targets(self, width: int) -> None:
        """Public and example fills use the notation's one equal-width pair."""
        from esolangs.generation.examples import BOOLEAN_EXAMPLES
        from esolangs.languages.minsky_swap.generator import minsky_swap_setters

        if width == 1:
            _check_constant_templates()
        example = BOOLEAN_EXAMPLES["minsky-swap"]
        assert example.fill is not None
        for n in (1, 2, 3, 5):
            table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
            template = esolangs.generate("Minsky Swap", table, width=width)
            pairs = minsky_swap_setters(template.source, n)
            assert len(set(pairs)) == 1
            assert len(pairs[0][0]) == len(pairs[0][1])
            assert max(map(len, template.source.splitlines())) <= max(
                width, 8 + len(str(2 ** (n + 1) + 7 * n + 6))
            )
            for row in range(1 << n):
                bits = list(map(int, f"{row:0{n}b}"))
                program = esolangs.instantiate("Minsky Swap", template, bits)
                assert self.run_minsky_swap(program.source) == table[row]
                assert (
                    self.run_minsky_swap(example.fill(template.source, bits))
                    == table[row]
                )

    def test_short_rmsn_public_floor(self) -> None:

        language = esolangs.Language("minsky_swap")
        witnesses = construction_boundaries(language.name)[
            "compact_width_one_arity_cutoff"
        ]
        for witness in witnesses:
            table = witness.table()
            with patch.object(
                boolean, "_rmsn_small", wraps=boolean._rmsn_small
            ) as route:
                artifact = language.generate(table, width=1)
            assert route.call_count == int(witness.arity == 2)
            assert_saved_rows(language, artifact, table, range(len(table)))

        template = esolangs.generate("Minsky Swap", "0110", width=1)
        assert template.bindings.setters == (("decnz(2);", "inc();   "),) * 2
        assert max(map(len, template.source.splitlines())) == 9
        for bits in ([0, 0], [0, 1], [1, 0], [1, 1]):
            program = esolangs.instantiate("Minsky Swap", template, bits)
            assert max(map(len, program.source.splitlines())) == 9
            assert self.run_minsky_swap(program.source) == str(bits[0] ^ bits[1])

    @pytest.mark.parametrize("n", [1, 2])
    def test_single_digit_router_for_every_small_table(self, n: int) -> None:
        import esolangs

        for table in witnesses(n):
            for width in (1, 8, 9, 10, 15):
                generated = esolangs.generate("Minsky Swap", table, width=width)
                assert len(generated.bindings.setters) == n
                assert len(set(generated.bindings.setters)) == 1
                assert len(generated.bindings.setters[0][0]) == len(
                    generated.bindings.setters[0][1]
                )
                for template in (
                    generated,
                    esolangs.load_program(
                        "Minsky Swap", esolangs.dump_program("Minsky Swap", generated)
                    ),
                ):
                    for row in range(1 << n):
                        bits = list(map(int, f"{row:0{n}b}"))
                        program = esolangs.instantiate(
                            "Minsky Swap", template, bits, truth_table=table
                        )
                        assert self.run_minsky_swap(program.source) == table[row]
                    with pytest.raises(esolangs.TemplateError):
                        esolangs.instantiate(
                            "Minsky Swap",
                            template,
                            [0] * n,
                            truth_table="".join(
                                "1" if bit == "0" else "0" for bit in table
                            ),
                        )

    def test_rmsn_growth_remains_linear(self) -> None:
        _check_pair_source_cap()
        from esolangs.languages.minsky_swap import generator as generators

        sizes = [
            len(generators.minsky_swap("01101001" * (2 ** (n - 3)), 1))
            for n in (7, 8, 9)
        ]
        assert all(b <= 2 * a for a, b in pairwise(sizes))

    @pytest.mark.parametrize("bits", [(0, 0), (0, 1), (1, 0), (1, 1)])
    def test_examples_fill_sets_either_bit_in_either_position(
        self, bits: tuple[int, int]
    ) -> None:
        """Native setters preserve set bits above the least significant one."""
        from esolangs.generation.examples import AND2
        from esolangs.languages.minsky_swap.generator import minsky_swap

        program = self.instantiate(minsky_swap(AND2), list(bits))
        assert self.run_minsky_swap(program) == AND2[(bits[0] << 1) | bits[1]]

    def test_tables_with_ignored_inputs_execute(self) -> None:
        """An ignored input's stage is a run plus two ``~`` and adds nothing.

        Its target count must still advance by exactly the text it
        emits: every later stage's skip target is counted from it, so
        a drift of one lands each later skip a command too far.
        """
        assert_analysis_complement("Minsky Swap", "input_weights")
        assert_analysis_complement("Minsky Swap", "symmetric_weights", "0001")
        _check_pair_leaves()
        for table in ("1010", "0011", "0101", "01010000", "00001111"):
            n = len(table).bit_length() - 1
            template = esolangs.generate("Minsky Swap", table)
            for row in range(1 << n):
                bits = list(map(int, f"{row:0{n}b}"))
                program = esolangs.instantiate("Minsky Swap", template, bits)
                assert self.run_minsky_swap(program.source) == table[row]


def _check_constant_templates() -> None:
    import esolangs
    from esolangs.languages.minsky_swap.generator import minsky_swap_setters
    from esolangs.languages.minsky_swap.interpreter import _Machine

    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                template = esolangs.generate("Minsky Swap", bit * (1 << n), **options)
                pairs = minsky_swap_setters(template.source, n)
                assert len(set(pairs)) == 1
                assert len(pairs[0][0]) == len(pairs[0][1])
                assert len(runs(template.source, TEMPLATE_CHAR, pairs)) == n
                sizes = set()
                for row in range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1):
                    program = esolangs.instantiate(
                        "Minsky Swap", template, list(map(int, f"{row:0{n}b}"))
                    )
                    sizes.add(len(program.source))
                    io = ScriptedIO()
                    machine = _Machine(program.source, io)
                    written = WrittenState(machine.workspace_snapshot())
                    steps = count_steps(machine, 1 + 3 * int(bit), written=written)
                    assert steps == 1 + 3 * int(bit)
                    machine.step()
                    written.sample(machine.workspace_snapshot())
                    assert esolangs.read_answer("Minsky Swap", io.getvalue()) == bit
                    assert (
                        written.bits
                        == (3 * n + 3 * int(bit)).bit_length() + 3 * int(bit) + 1
                    )
                assert len(sizes) == 1
    assert three_input_corpus_size("Minsky Swap") == 21396


def _check_pair_leaves() -> None:
    """Pair leaves and ignored tails preserve their held bit in both notations."""
    import esolangs
    from esolangs.languages.minsky_swap.generator import minsky_swap_setters
    from esolangs.languages.minsky_swap.interpreter import _Machine

    # All pair patterns, then the same function with a physical ignored tail.
    for table in ("00011011", "0000001100111111", "0000000011111111"):
        n = len(table).bit_length() - 1
        for width in (None, 1, 10):
            template = esolangs.generate("Minsky Swap", table, width=width)
            assert len(set(minsky_swap_setters(template.source, n))) == 1
            for row in range(1 << n):
                bits = list(map(int, f"{row:0{n}b}"))
                code = esolangs.instantiate("Minsky Swap", template, bits)
                io = ScriptedIO("sentinel\n")
                machine = _Machine(code.source, io)
                while not machine.halted:
                    machine.step()
                assert io.getvalue() == ""
                machine.step()
                assert io.reads == 0
                if table == "00011011" and row == 1:
                    assert io.getvalue() == "2 0"
                assert esolangs.read_answer("Minsky Swap", io.getvalue()) == table[row]


def _check_pair_source_cap() -> None:
    """A single non-10 pair retains every input and maximizes target digits."""
    from esolangs.languages.minsky_swap.generator import minsky_swap
    from esolangs.languages.minsky_swap.tests.formulas import _full_chars

    for n in range(2, 9):
        table = "10" * ((1 << (n - 1)) - 1) + "11"
        assert len(minsky_swap(table)) == _full_chars(n, "")

    from esolangs.languages.minsky_swap.generator import minsky_swap_setters
    from esolangs.languages.minsky_swap.interpreter import _Machine
    from scripts.docs.resource_evidence import resource_bounds

    bounds = resource_bounds("Minsky Swap")
    scaling = bounds["scaling"].formula
    execution = bounds["execution"].formula
    workspace = bounds["workspace"].formula

    for n in range(1, 9):
        table = "0" * (1 << (n - 1)) + "1" * (1 << (n - 1))
        template = minsky_swap(table)
        assert len(template) <= scaling(n, template)
        code = fill_runs(
            template, TEMPLATE_CHAR, minsky_swap_setters(template, n), [1] * n
        )
        machine = _Machine(code, ScriptedIO(""))
        steps, written = measure_run(machine)
        assert steps == 16 * n - 3
        assert steps <= execution(n, template)
        assert written.bits <= workspace(n, template)
