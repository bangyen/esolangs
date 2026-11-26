"""bitdeque generator tests."""

import itertools

import pytest

import esolangs
from esolangs import run as execute
from esolangs._bindings import TEMPLATE_CHAR, runs
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState
from tests.proofs.conventions import _embedding, _tables
from tests.support.analysis_support import assert_analysis_complement
from tests.support.generator_support import three_input_corpus_size
from tests.support.witness_tables import witnesses


@pytest.mark.parametrize("width", [None, 9])
def test_exit_jump_lands_on_an_operation(width: int | None) -> None:
    from esolangs.languages.bitdeque.interpreter import _Machine

    table = "0001"
    language = esolangs.Language("Bitdeque")
    template = language.generate(table, width=width)
    for row, answer in enumerate(table):
        program = language.instantiate(template, list(map(int, f"{row:02b}")))
        machine = _Machine(program.source, ScriptedIO())
        destinations = []
        while not machine.halted:
            token = machine.tokens[machine.ind]
            if machine.reg and token.startswith("GOTO "):
                destination = int(token[5:])
                assert 1 <= destination <= machine.size
                destinations.append(destination)
            machine.step()
        assert destinations[-1] == machine.size - 1
        assert machine.deq == (int(answer),)
        assert machine.reg == 1


class TestParameterizedBitdeque:
    """Input-by-substitution boolean generator for the no-input language Bitdeque."""

    def run_bitdeque(self, prog: str) -> str:
        from esolangs.languages.bitdeque.interpreter import run

        io = ScriptedIO()
        run(prog, io)
        return io.getvalue().strip()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        # Deliberately the shipped fill rather than a copy of its rule: an
        # earlier duplicate here kept passing after the load order changed
        # under it, so the suite disagreed with the harness it is meant to
        # mirror.
        """Bind native source with explicitly declared setters."""
        from esolangs.languages.bitdeque.generator import bitdeque_setters

        bindings = esolangs.TemplateBindings(setters=bitdeque_setters(tpl, len(bits)))
        template = esolangs.TemplateArtifact(
            tpl,
            "Bitdeque",
            bindings,
            spans=tuple(runs(tpl, bindings.char, bindings.setters)),
        )
        return esolangs.instantiate("Bitdeque", template, bits).source

    def test_template_is_input_independent(self) -> None:
        """The template has input runs, not hardcoded bits."""
        from esolangs.languages.bitdeque import generator as generators
        from esolangs.languages.bitdeque.generator import BITDEQUE_PAIR

        for n in (2, 5):
            template = generators.bitdeque("0110" * 2 ** (n - 2))
            assert "{X" not in template
            setters = (BITDEQUE_PAIR,) * n
            spans = runs(template, "$", setters)
            assert [end - start for start, end in spans] == [11] * n

    def test_odd_inputs_are_pushed_complemented(self) -> None:
        """The load flips the register per block; the tree's table absorbs it."""
        from esolangs.languages.bitdeque import generator as generators
        from esolangs.languages.bitdeque.interpreter import run

        template = generators.bitdeque("0101")
        prelude_and_load = " ".join(self.instantiate(template, [0, 1]).split()[:12])
        io = ScriptedIO()
        run(prelude_and_load, io)
        assert io.getvalue() == "0 0"  # input 1's one pushed as a zero
        for bits in ([0, 0], [0, 1], [1, 0], [1, 1]):
            assert self.run_bitdeque(self.instantiate(template, bits)) == str(bits[1])

    def test_constant_leaf_and_shared_halt_trampoline(self) -> None:
        """Whole constants need no trampoline; branching leaves still share one."""
        from esolangs.languages.bitdeque import generator as generators

        assert_analysis_complement("Bitdeque", "decision_layers")
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

    for n in range(1, 4):
        for table in witnesses(n):
            template = esolangs.generate("Bitdeque", table, width=width)
            for row, expected in enumerate(table):
                bits = list(map(int, format(row, f"0{n}b")))
                program = esolangs.instantiate("Bitdeque", template, bits)
                assert execute("Bitdeque", program).unwrap().output == expected


def test_bitdeque_short_load_floor_and_rendered_total() -> None:

    template = esolangs.generate("Bitdeque", "0110", width=1)
    assert max(map(len, template.source.splitlines())) == 7
    for row in range(4):
        program = esolangs.instantiate("Bitdeque", template, [row // 2, row % 2])
        assert max(map(len, program.source.splitlines())) == 7
    assert (
        sum(
            len(esolangs.generate("Bitdeque", format(value, "08b"), width=1).source)
            for value in range(256)
        )
        == 119_547
    )


def test_bitdeque_width_eleven_is_the_normal_load() -> None:
    """Width 10 still takes the short load; from 11 the eleven-cell one is smaller."""

    sizes = [
        len(esolangs.generate("Bitdeque", "0110", width=width).source)
        for width in (10, 11)
    ]
    assert sizes == [322, 154]


@pytest.mark.parametrize("width", [1, 9, 40, 80])
def test_bitdeque_short_load_saved_source_and_large_tables(width: int) -> None:

    for n in range(4, 7):
        table = "".join(str(row.bit_count() % 2) for row in range(2**n))
        template = esolangs.generate("Bitdeque", table, width=width)
        template = esolangs.from_json(
            "Bitdeque", esolangs.to_json("Bitdeque", template)
        )
        for row in [0, 1, 2**n // 3, 2**n - 1]:
            bits = list(map(int, format(row, f"0{n}b")))
            program = esolangs.instantiate(
                "Bitdeque", template, bits, truth_table=table
            )
            assert execute("Bitdeque", program).unwrap().output == table[row]


def test_bitdeque_short_load_rejects_changed_prefix() -> None:
    from esolangs.languages.bitdeque.generator import bitdeque, bitdeque_setters

    template = bitdeque("0110", 1)
    pair = bitdeque_setters(template, 2)
    assert pair == (("POP  ", "EJECT"),) * 2
    with pytest.raises(ValueError, match="shorter than"):
        bitdeque_setters(template.replace("GOTO 17", "GOTO 18"), 2)


def test_bitdeque_short_load_rejects_wrong_table_provenance() -> None:

    template = esolangs.generate("Bitdeque", "0110", width=9)
    with pytest.raises(esolangs.TemplateError, match="not the template"):
        esolangs.instantiate("Bitdeque", template, [0, 1], truth_table="0001")


def test_bitdeque_filled_template_is_one_width() -> None:
    """The route the equal-width test misses stays at one length."""
    example = _embedding()["Bitdeque"]
    assert example.fill is not None
    for n in (4, 5):
        template = example.emit(_tables(n)[0])
        lengths = {
            len(example.fill(template, list(bits)))
            for bits in itertools.product((0, 1), repeat=n)
        }
        assert len(lengths) == 1, (n, sorted(lengths))


@pytest.mark.medium
def test_constant_native_and_short_loads_keep_all_slots() -> None:
    from checks.certification.resource_evidence import resource_bounds
    from esolangs.languages.bitdeque.generator import bitdeque_setters
    from esolangs.languages.bitdeque.interpreter import _Machine

    workspace = resource_bounds("Bitdeque")["workspace"].formula

    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                table = bit * (1 << n)
                template = esolangs.generate("Bitdeque", table, **options)
                short = options == {"width": 1} and n <= 4
                assert template.source.count(TEMPLATE_CHAR) == n * (5 if short else 11)
                assert len(bitdeque_setters(template.source, n)) == n
                if not options:
                    assert len(template.source) == 16 * n + 8 + 7 * int(bit)
                rows = range(1 << n) if n <= 3 else (0, 1, (1 << n) - 1)
                for row in rows:
                    inputs = list(map(int, format(row, f"0{n}b")))
                    program = esolangs.instantiate("Bitdeque", template, inputs)
                    assert len(program.source) == len(template.source)
                    io = ScriptedIO()
                    machine = _Machine(program.source, io)
                    written = WrittenState(machine.workspace_snapshot())
                    steps = 0
                    while not machine.halted and steps < 500:
                        machine.step()
                        written.sample(machine.workspace_snapshot())
                        steps += 1
                    assert machine.halted
                    assert machine.deq == (int(bit),)
                    assert not io.getvalue()
                    machine.step()
                    written.sample(machine.workspace_snapshot())
                    assert io.getvalue() == bit
                    if not options:
                        assert steps + 1 == 3 * n + 3 + int(bit)
                        assert written.bits == workspace(n, template.source)
    assert three_input_corpus_size("Bitdeque") == 54_914
