r"""Unit tests for the parameterized (no-input) boolean generators."""

import importlib
import io
import random
import re
from collections.abc import Iterable
from contextlib import redirect_stdout

import pytest

from esolangs.interpreters.io import IO
from esolangs.tools.boolean.parameterized import _instantiate_arrowqueue
from tests.tools.boolean_runners import one_two_three_result


def _parameterized_generators():
    r"""Return every parameterized generator the module exports."""
    from esolangs.tools.boolean import parameterized

    return [
        (name, parameterized.__dict__[name])
        for name in parameterized.__all__
        if name != "instantiate"
    ]


@pytest.mark.slow  # ~3s: builds every generator,.
def test_parameterized_generators_embed_each_input_once() -> None:
    r"""Every no-input generator embeds each input exactly once."""

    checked = 0
    for name, gen in _parameterized_generators():
        for n in (1, 2, 3, 4):
            table = format(0, f"0{2**n}b")
            try:
                template = gen(table)
            except ValueError:
                # pylint: disable=duplicate-code
                # pylint: disable=duplicate-code
                # pylint: disable=duplicate-code
                # pylint: disable=duplicate-code
                # pylint: disable=duplicate-code
                continue
            checked += 1
            xs = re.findall(r"\{X(\d+)\}", template)
            cs = re.findall(r"\{C(\d+)\}", template)
            assert sorted(xs) == [str(i) for i in range(n)], (name, n, xs)
            assert len(xs) == n, (name, n, xs)
            assert not cs, (name, n, cs)
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    assert checked >= len(_parameterized_generators()), checked


# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code
# pylint: disable=duplicate-code

_SLOT_ORDER_TABLES = ("0110", "01101001", "10101010", "11110000", "00111100")


def _all_derived_plans(derived_plans, staged_arities, n: int) -> dict:
    r"""Every staging the enumeration places at ``n``, in one pass."""
    if n not in staged_arities:
        return derived_plans(n, ())
    every = tuple(format(v, f"0{2**n}b") for v in range(2 ** (2**n)))
    return derived_plans(n, every)


def _slot_order(gen: object, table: str) -> list[int] | None:
    r"""The ``{Xi}`` indices in the order ``gen`` emits them, or None."""

    try:
        template = gen(table)
    except ValueError:
        return None  # a generator need not cover.
    return [int(s[2:-1]) for s in re.findall(r"\{X\d+\}", template)]


@pytest.mark.slow  # builds every generator over.
def test_slots_run_in_name_order() -> None:
    r"""Every template emits ``{X0}``..``{Xn-1}`` in ascending order."""
    checked = 0
    for name, gen in _parameterized_generators():
        for table in _SLOT_ORDER_TABLES:
            slots = _slot_order(gen, table)
            if slots is None:
                continue
            checked += 1
            assert slots == sorted(slots), (name, table, slots)
    assert checked >= len(_parameterized_generators()), checked


def _drawing(template: str) -> str:
    r"""The template with every placeholder *name* erased."""

    return re.sub(r"\{X\d+\}", "{X}", template)


@pytest.mark.slow  # builds every permuting.
def test_a_permuting_generator_changes_its_drawing() -> None:
    r"""A generator that permutes its slots must emit a different *drawing*."""
    from itertools import permutations

    from esolangs.tools.boolean import parameterized
    from esolangs.tools.boolean.helpers import permute_truth_table

    checked = 0
    for name in ("back",):
        build = parameterized._back_ordered  # noqa: SLF001
        for table in ("10101010", "11001100", "00111100"):
            n = 3
            builds: dict[str, set[int]] = {}
            for perm in permutations(range(n)):
                built = build(permute_truth_table(table, perm), perm)
                builds.setdefault(_drawing(built), set()).add(len(built))
            checked += 1
            # pylint: disable=duplicate-code
            # pylint: disable=duplicate-code
            assert len(builds) > 1, (
                name,
                table,
                "every input order draws the same program, so permuting the "
                "slots emits an identical program and books a fake saving",
            )
            # pylint: disable=duplicate-code
            # pylint: disable=duplicate-code
            for drawing, sizes in builds.items():
                assert len(sizes) == 1, (name, table, len(drawing), sorted(sizes))
    assert checked >= 3, checked


class TestParameterizedBIO:
    r"""Input-by-substitution generators for the no-input language BIO."""

    def run_bio(self, prog: str, bits: list[int]) -> str:
        from tests.interpreters.runner import run_program

        run = importlib.import_module("esolangs.interpreters.register_based.bio").run
        return run_program(run, prog, "".join(f"{b}\n" for b in bits))

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        r"""Fill the template the way the example harness does."""
        from esolangs.tools.boolean.examples import _fill_bio

        return _fill_bio(tpl, bits)

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("01", 1),
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("11111110", 3),  # NAND3.
            ("01101001", 3),  # XOR3.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.bio(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_bio(self.instantiate(template, bits), bits)
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        r"""The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.bio("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_each_input_is_stored_once(self) -> None:
        r"""The packing scheme embeds each input exactly once."""

        from esolangs.tools.boolean import parameterized

        for n in (1, 2, 3):
            table = format(0, f"0{2**n}b")
            template = parameterized.bio(table)
            assert len(re.findall(r"\{X\d+\}", template)) == n

    def test_both_bits_embed_at_the_same_width(self) -> None:
        r"""A zero pads against the unread ``z``, so the program's length does."""
        from esolangs.tools.boolean.examples import _fill_bio

        for n in (1, 2, 3):
            for i in range(n):
                placeholder = "{X" + str(i) + "}"
                zeros = [0] * n
                ones = list(zeros)
                ones[i] = 1
                assert len(_fill_bio(placeholder, zeros)) == len(
                    _fill_bio(placeholder, ones)
                ), f"n={n} input {i}"

    def test_padding_never_touches_a_read_register(self) -> None:
        r"""``z`` is inert: the generator emits no command that reads it."""
        from esolangs.tools.boolean import parameterized

        for n in (1, 2, 3):
            template = parameterized.bio(format(0, f"0{2**n}b"))
            assert "z" not in template.lower()


class TestParameterizedBack:
    r"""Input-by-substitution generators for the no-input language Back."""

    def run_back(self, prog: str, n: int) -> str:
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.back import run

        io = ScriptedIO()
        run(prog.splitlines(), io)
        return io.getvalue().split()[n]

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        r"""Fill the template the way the example harness does."""
        from esolangs.tools.boolean.examples import _fill_back

        return _fill_back(tpl, bits)

    def test_program_length_is_the_same_for_every_input(self) -> None:
        r"""Both bits cost one command, so the size reveals nothing."""
        from esolangs.tools.boolean import parameterized
        from esolangs.tools.boolean.examples import _fill_back

        for n in (1, 2, 3):
            template = parameterized.back(format(0, f"0{2**n}b"))
            sizes = {
                len(_fill_back(template, [(c >> (n - 1 - i)) & 1 for i in range(n)]))
                for c in range(2**n)
            }
            assert len(sizes) == 1, f"n={n} sizes {sorted(sizes)}"

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("01", 1),
            ("00", 1),  # constant zero.
            ("11", 1),  # constant one.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("1110", 2),  # NAND.
            ("11111110", 3),  # NAND3.
            ("01101001", 3),  # XOR3.
            ("1111111100000000", 4),  # top half.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.back(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_back(self.instantiate(template, bits), n)
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        r"""Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.back(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_back(self.instantiate(template, bits), n)
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        r"""The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.back("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_each_input_is_stored_once(self) -> None:
        r"""Each input is embedded once in the tape load, not re-embedded."""

        from esolangs.tools.boolean import parameterized

        for n in (1, 2, 3):
            table = format(0, f"0{2**n}b")
            template = parameterized.back(table)
            assert len(re.findall(r"\{X\d+\}", template)) == n

    def test_tree_uses_tape_decision_nodes(self) -> None:
        r"""The decision tree routes via '+\' nodes and a down-transition."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.back("0110")
        assert "+\\" in template  # a decision node.
        assert "*" in template  # leaves halt.

    def test_input_reordering_folds_a_scattered_table(self) -> None:
        r"""The tree splits in whichever order folds most, not load order."""
        from esolangs.tools.boolean import parameterized

        scattered = len(parameterized.back("10101010"))
        aligned = len(parameterized.back("11110000"))
        parity = len(parameterized.back("01101001"))
        assert scattered < parity
        assert aligned < parity
        assert abs(scattered - aligned) < 0.2 * parity

    def test_input_reordering_never_grows_a_template(self) -> None:
        r"""No table comes out larger than its identity build."""
        from esolangs.tools.boolean import parameterized

        for table in ("01101001", "10101010", "11110000", "00111100", "10010110"):
            n = (len(table) - 1).bit_length()
            identity = parameterized._back_ordered(table, tuple(range(n)))  # noqa: SLF001
            assert len(parameterized.back(table)) <= len(identity), table

    @pytest.mark.parametrize(
        "table",
        ["10101010", "11001100", "01011010", "00111100", "10010110"],
    )
    def test_reordered_templates_compute_the_table(self, table: str) -> None:
        r"""A reordered template still computes its function."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.back(table)
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            got = self.run_back(self.instantiate(template, bits), 3)
            assert got == table[combo], f"{table} inputs {bits}"

    def test_reordering_pays_a_walk_and_keeps_name_order(self) -> None:
        r"""A permuted load spends rows on the walk, and keeps its slots sorted."""
        from itertools import permutations

        from esolangs.tools.boolean import parameterized

        walked = 0
        for table in ("0110", "10101010", "01101001"):
            n = (len(table) - 1).bit_length()
            for perm in permutations(range(n)):
                permuted = parameterized.permute_truth_table(table, perm)
                built = parameterized._back_ordered(permuted, perm)  # noqa: SLF001
                names = re.findall(r"\{X(\d+)\}", built)
                assert names == sorted(names), (table, perm, names)
                column = [ln[0] for ln in built.split("\n") if ln[:1].strip()]
                walked += column.count("<")
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        assert walked > 0

    def test_placeholders_run_in_name_order_while_still_reordering(self) -> None:
        r"""Back reorders through the *walk*, not through its slot order."""

        from esolangs.tools.boolean import parameterized

        walked = 0
        for table in ("11110000", "10101010", "01101001", "00111100"):
            template = parameterized.back(table)
            names = re.findall(r"\{X(\d+)\}", template)
            assert names == sorted(names), f"{table} slots {names}"
            assert sorted(names) == ["0", "1", "2"], f"{table} embeds each once"
            # pylint: disable=duplicate-code
            # pylint: disable=duplicate-code
            # pylint: disable=duplicate-code
            column = [line[0] for line in template.split("\n") if line[:1].strip()]
            walked += column.count("<")
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        assert walked > 0

    def test_reordering_keeps_the_equal_width_embedding(self) -> None:
        r"""Reordered loads still cost the same for either bit."""
        from esolangs.tools.boolean import parameterized
        from esolangs.tools.boolean.examples import _fill_back

        for table in ("10101010", "11001100", "01101001"):
            template = parameterized.back(table)
            sizes = {
                len(_fill_back(template, [(c >> (2 - i)) & 1 for i in range(3)]))
                for c in range(8)
            }
            assert len(sizes) == 1, f"{table} sizes {sorted(sizes)}"


class TestParameterizedNoComment:
    r"""Input-by-substitution boolean generator for the no-input language."""

    def run_nocomment(self, prog: str, tape: int | None = None) -> str:
        from esolangs.interpreters.tape_based.nocomment import _TAPE, run

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            run(prog, IO(), _TAPE if tape is None else tape)
        return buffer.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        from esolangs.tools.boolean import parameterized

        return parameterized.instantiate(
            tpl,
            bits,
            lambda _i, b: "c" if b == 0 else "i",
        )

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("01", 1),
            ("00", 1),  # constant zero.
            ("11", 1),  # constant one.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("1110", 2),  # NAND.
            ("11111110", 3),  # NAND3.
            ("01101001", 3),  # XOR3.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.nocomment(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_nocomment(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        r"""Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.nocomment(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_nocomment(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        r"""The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.nocomment("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_program_structure(self) -> None:
        r"""A one-bit template computes the index then skips to the output."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.nocomment("10")
        assert template.startswith("{X0}")
        assert "{C0}" not in template  # the complement is computed at.
        assert template.endswith("o")  # a single final output.
        assert template.count("s") == 3  # NOT gate + guarded increment.
        assert template.count("o") == 1

    def test_four_input_works(self) -> None:
        r"""A dense four-input table assembles and runs correctly."""
        from esolangs.tools.boolean import parameterized

        for combo in range(16):
            bits = [(combo >> (3 - i)) & 1 for i in range(4)]
            template = parameterized.nocomment("1010101010101010")
            got = self.run_nocomment(self.instantiate(template, bits))
            assert got == str(int("1010101010101010"[combo])), f"inputs {bits}"

    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    # pylint: disable=duplicate-code
    @pytest.mark.parametrize(
        "n",
        [
            pytest.param(9, marks=pytest.mark.slow),
            pytest.param(10, marks=pytest.mark.slow),
        ],
    )
    def test_wide_arity_is_exact(self, n: int) -> None:
        r"""Past a byte-sized index the composed-skip decode still computes the."""
        self._check_wide_arity(n, range(2**n))

    @pytest.mark.slow  # ~3s: the same decode at n=11,.
    def test_the_widest_arity_is_exact_on_sampled_rows(self) -> None:
        r"""The n=11 decode is checked where a stage boundary can go wrong."""
        n = 11
        rows = {0, 2**n - 1}
        rows.update(1 << i for i in range(n))
        for edge in (255, 511, 1023, 2047):
            rows.update({edge - 1, edge, edge + 1} & set(range(2**n)))
        rows.update(range(0, 2**n, 41))
        self._check_wide_arity(n, sorted(rows))

    def _check_wide_arity(self, n: int, rows: Iterable[int]) -> None:
        r"""Run the four probe tables at arity ``n`` over ``rows``."""
        from esolangs.tools.boolean import parameterized

        tables = {
            "alternating": "01" * (2 ** (n - 1)),
            "parity": "".join(str(bin(r).count("1") % 2) for r in range(2**n)),
            "constant": "0" * (2**n),
            "and": "0" * (2**n - 1) + "1",
        }
        rows = list(rows)
        for name, table in tables.items():
            template = parameterized.nocomment(table)
            for combo in rows:
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_nocomment(self.instantiate(template, bits))
                assert got == table[combo], f"{name} n={n} inputs {bits}"

    def test_narrow_path_needs_a_byte_sized_index(self) -> None:
        r"""The single-skip decode covers exactly the arities whose index fits."""
        from esolangs.tools.boolean.parameterized import (
            _NOCOMMENT_NARROW_MAX,
            _NOCOMMENT_SKIP_MAX,
        )

        assert 2**_NOCOMMENT_NARROW_MAX - 1 <= _NOCOMMENT_SKIP_MAX
        assert 2 ** (_NOCOMMENT_NARROW_MAX + 1) - 1 > _NOCOMMENT_SKIP_MAX

    def test_cap_is_the_tape_not_the_skip(self) -> None:
        r"""The remaining cap is the interpreter's tape, and it is derived."""
        from esolangs.interpreters.tape_based.nocomment import _TAPE
        from esolangs.tools.boolean import parameterized
        from esolangs.tools.boolean.parameterized import _NOCOMMENT_NARROW_MAX

        widest = 0
        for n in range(1, 16):
            try:
                parameterized.nocomment("0" * (2**n))
            except ValueError:
                break
            widest = n

        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        assert widest > _NOCOMMENT_NARROW_MAX
        with pytest.raises(ValueError, match=str(_TAPE)) as caught:
            parameterized.nocomment("0" * (2 ** (widest + 1)))
        assert "tape" in str(caught.value)

    def test_a_bigger_tape_lifts_the_cap(self) -> None:
        r"""The cap is the tape size, so a bigger tape moves it -- and still."""
        from esolangs.interpreters.tape_based.nocomment import _TAPE
        from esolangs.tools.boolean import parameterized

        n, tape = 12, 16384
        table = "".join(str((r * r + r // 3) % 2) for r in range(2**n))

        with pytest.raises(ValueError, match=str(_TAPE)):
            parameterized.nocomment(table)

        template = parameterized.nocomment(table, tape=tape)
        for combo in (0, 1, 2**n - 1, 2**n - 2, 1234, 2731):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_nocomment(self.instantiate(template, bits), tape)
            assert got == table[combo], f"n={n} inputs {bits}"


class TestParameterizedLamfunc:
    r"""Input-by-substitution boolean generator for the no-input language."""

    def run_lamfunc(self, prog: str) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.other.lamfunc import run

        io = ScriptedIO()
        run(prog, io)
        return io.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        from esolangs.tools.boolean import parameterized

        # pylint: disable=duplicate-code
        return parameterized.instantiate(
            tpl,
            bits,
            lambda _i, b: "0b" + str(b),
        )

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("01", 1),
            ("00", 1),  # constant zero.
            ("11", 1),  # constant one.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("1110", 2),  # NAND.
            ("11111110", 3),  # NAND3.
            ("01101001", 3),  # XOR3.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.lamfunc(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_lamfunc(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        r"""Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.lamfunc(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_lamfunc(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        r"""The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.lamfunc("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_each_input_is_stored_once(self) -> None:
        r"""The store-once scheme embeds each input exactly once."""

        from esolangs.tools.boolean import parameterized

        for n in (1, 2, 3):
            table = format(0, f"0{2**n}b")
            template = parameterized.lamfunc(table)
            assert len(re.findall(r"\{X\d+\}", template)) == n

    def test_constant_table_is_a_leaf(self) -> None:
        r"""A constant table emits the stores plus a single p with no branching."""
        from esolangs.tools.boolean import parameterized

        assert parameterized.lamfunc("0000") == "vs v0 {X0} vs v1 {X1} p 0"
        assert parameterized.lamfunc("1111") == "vs v0 {X0} vs v1 {X1} p 1"


class TestParameterizedBitdeque:
    r"""Input-by-substitution boolean generator for the no-input language."""

    def run_bitdeque(self, prog: str) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.queue_based.bitdeque import run

        io = ScriptedIO()
        run(prog, io)
        return io.getvalue().strip()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        from esolangs.tools.boolean.examples import _fill_bitdeque

        return _fill_bitdeque(tpl, bits)

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("01", 1),  # identity.
            ("00", 1),  # constant zero.
            ("11", 1),  # constant one.
            ("0001", 2),  # AND.
            ("0110", 2),  # XOR.
            ("0111", 2),  # OR.
            ("1110", 2),  # NAND.
            ("11111110", 3),  # NAND3.
            ("01101001", 3),  # majority.
            ("1111111100000000", 4),  # top half.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.bitdeque(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_bitdeque(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        r"""Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.bitdeque(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_bitdeque(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        r"""The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.bitdeque("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_constant_table_is_a_leaf(self) -> None:
        r"""A constant table emits a drain-and-push leaf with no branching."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.bitdeque("0000")
        assert "POP" in template
        assert "GOTO" in template


class TestParameterizedRam0:
    r"""Input-by-substitution boolean generator for the no-input language."""

    def run_ram0(self, prog: str) -> str:

        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.ram0 import run

        io = ScriptedIO()
        run(prog, io)
        m = re.search(r"^z: (\d+)", io.getvalue(), re.MULTILINE)
        assert m is not None
        return m.group(1)

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        from esolangs.tools.boolean import parameterized

        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        return parameterized.instantiate(
            tpl,
            bits,
            lambda _i, b: "Z A" if b else "Z Z",
        )

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("01", 1),  # identity.
            ("00", 1),  # constant zero.
            ("11", 1),  # constant one.
            ("0001", 2),  # AND.
            ("0110", 2),  # XOR.
            ("0111", 2),  # OR.
            ("1110", 2),  # NAND.
            ("11111110", 3),  # NAND3.
            ("01101001", 3),  # majority.
            ("1111111100000000", 4),  # top half.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.ram0(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_ram0(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        r"""Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.ram0(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_ram0(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        r"""The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.ram0("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_constant_table_is_a_leaf(self) -> None:
        r"""A constant table emits a single leaf with no branching."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.ram0("0000")
        assert "C" not in template
        assert "Z" in template


class TestParameterizedMinskySwap:
    r"""Input-by-substitution boolean generator for the no-input language."""

    def run_minsky_swap(self, prog: str) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.minsky_swap import run

        io = ScriptedIO()
        run(prog, io)
        return io.getvalue().split()[1]

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        from esolangs.tools.boolean import parameterized

        n = len(bits)

        def set_bit(i: int, b: int) -> str:
            if i == n - 1:  # LSB: length-4 block, no "~".
                return "+*+*" if b else "****"
            w = 2 ** (n - 1 - i)  # this bit's weight.
            if b:
                return "+" * w + "*" * (2**n - w)
            return "*" * 2**n

        return parameterized.instantiate(
            tpl,
            bits,
            set_bit,
        )

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("01", 1),  # identity.
            ("00", 1),  # constant zero.
            ("11", 1),  # constant one.
            ("0001", 2),  # AND.
            ("0110", 2),  # XOR.
            ("0111", 2),  # OR.
            ("1110", 2),  # NAND.
            ("11111110", 3),  # NAND3.
            ("01101001", 3),  # majority.
            ("1111111100000000", 4),  # top half.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.minsky_swap(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_minsky_swap(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        r"""Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.minsky_swap(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_minsky_swap(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        r"""The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.minsky_swap("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    @pytest.mark.parametrize("bits", [(0, 0), (0, 1), (1, 0), (1, 1)])
    def test_examples_fill_sets_either_bit_in_either_position(
        self, bits: tuple[int, int]
    ) -> None:
        r"""``_fill_minsky_swap`` spells a set bit above the LSB too."""
        from esolangs.tools.boolean import minsky_swap
        from esolangs.tools.boolean.examples import AND2, _fill_minsky_swap

        program = _fill_minsky_swap(minsky_swap(AND2), list(bits))
        assert self.run_minsky_swap(program) == AND2[(bits[0] << 1) | bits[1]]

    def test_examples_fill_weights_the_non_lsb(self) -> None:
        r"""A set non-LSB is its weight in ``+`` then a pad to the block size."""
        from esolangs.tools.boolean import minsky_swap
        from esolangs.tools.boolean.examples import AND2, _fill_minsky_swap

        template = minsky_swap(AND2)
        assert "++**" in _fill_minsky_swap(template, [1, 1])
        assert "++**" not in _fill_minsky_swap(template, [0, 1])


class TestParameterizedArrowQueue:
    r"""Input-by-substitution boolean generator for the no-input language."""

    def run_arrowqueue(self, prog: str) -> str:
        from esolangs.interpreters.grid_based.arrowqueue import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        return "0" if run_until_halt_or_cycle(_Machine(prog.splitlines())) else "1"

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        return _instantiate_arrowqueue(tpl, bits)

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("01", 1),  # identity.
            ("00", 1),  # constant zero.
            ("11", 1),  # constant one.
            ("0001", 2),  # AND.
            ("0110", 2),  # XOR.
            ("0111", 2),  # OR.
            ("1110", 2),  # NAND.
            ("11111110", 3),  # NAND3.
            ("01101001", 3),  # majority.
            ("1111111100000000", 4),  # top half.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every instantiated input halts or loops per its table entry."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.arrowqueue(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_arrowqueue(self.instantiate(template, bits))
            assert got == table[combo], f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        r"""Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.arrowqueue(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_arrowqueue(self.instantiate(template, bits))
                assert got == table[combo], f"{table} inputs {bits}"

    def test_random_tables(self) -> None:
        r"""Seeded random tables through five inputs produce the right result."""
        from esolangs.tools.boolean import parameterized

        random.seed(13)
        for n in (1, 2, 3, 4, 5):
            for _ in range(2):
                table = "".join(random.choice("01") for _ in range(2**n))
                template = parameterized.arrowqueue(table)
                for combo in range(2**n):
                    bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                    got = self.run_arrowqueue(self.instantiate(template, bits))
                    assert got == table[combo], f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        r"""The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.arrowqueue("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    @pytest.mark.parametrize(
        ("table", "mixed"),
        [
            ("1111", "1010"),
            ("11110000", "10010110"),
            ("1111111100000000", "1001011001101001"),
        ],
    )
    def test_constant_subtrees_fold(self, table: str, mixed: str) -> None:
        r"""A constant subtree emits one drained leaf, not a full branch set."""
        from esolangs.tools.boolean import parameterized

        assert len(parameterized.arrowqueue(table)) < len(
            parameterized.arrowqueue(mixed)
        )

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("1" * 16, 4),
            ("0" * 16, 4),
            ("1111111100000000", 4),
            ("1111000000000000", 4),
            ("1" * 32, 5),
            ("1" * 16 + "0" * 16, 5),
        ],
    )
    def test_folded_tables_past_three_inputs(self, table: str, n: int) -> None:
        r"""Folded leaves stay correct deeper than the exhaustive n <= 3 sweep."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.arrowqueue(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_arrowqueue(self.instantiate(template, bits))
            assert got == table[combo], f"inputs {bits}"

    def test_folded_one_leaf_drains_the_bits_it_skipped(self) -> None:
        r"""The drain is required: a ring needs the queue it expects."""
        from esolangs.tools.boolean.parameterized import _TREE_1, _drained_leaf

        undrained = _drained_leaf("1", 0)  # no drains at all.
        assert [row.strip() for row in undrained if row.strip()] == [
            row.strip() for row in _TREE_1
        ]

        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        drained = _drained_leaf("1", 2)
        assert len(drained) == len(_TREE_1) + 2
        assert sum(row.count("+") for row in drained) == 4 + 2  # ring + drains.

    def test_folded_zero_leaf_needs_no_drain(self) -> None:
        r"""A ``0`` leaf halts by leaving the grid, which the queue cannot stop."""
        from esolangs.tools.boolean import parameterized
        from esolangs.tools.boolean.parameterized import _TREE_0, _drained_leaf

        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        assert _drained_leaf("0", 3) == list(_TREE_0)
        for table, n in (("0000", 2), ("0" * 8, 3)):
            template = parameterized.arrowqueue(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                assert self.run_arrowqueue(self.instantiate(template, bits)) == "0"

    def test_folding_never_grows_a_program(self) -> None:
        r"""No instantiated program is larger than its unfolded equivalent."""
        from esolangs.tools.boolean.parameterized import (
            _TREE_0,
            _TREE_1,
            _connect,
            _tree,
        )

        def unfolded(values: list[str]) -> list[str]:
            r"""The pre-fold construction: a branch per level, never collapsed."""
            if len(values) == 2:
                return _connect(
                    _TREE_1 if values[0] == "1" else _TREE_0,
                    _TREE_1 if values[1] == "1" else _TREE_0,
                )
            half = len(values) // 2
            return _connect(unfolded(values[:half]), unfolded(values[half:]))

        for n in (1, 2, 3):
            for value in range(2 ** (2**n)):
                table = format(value, f"0{2**n}b")
                folded = _tree(list(table))
                plain = unfolded(list(table))
                assert sum(len(r.rstrip()) for r in folded) <= sum(
                    len(r.rstrip()) for r in plain
                ), table

    def test_fold_keeps_equal_width_embedding(self) -> None:
        r"""Every instantiation of a folded template is the same length."""
        from esolangs.tools.boolean import parameterized

        for table, n in (("1111", 2), ("1100", 2), ("11110000", 3)):
            template = parameterized.arrowqueue(table)
            sizes = {
                len(
                    self.instantiate(
                        template, [(c >> (n - 1 - i)) & 1 for i in range(n)]
                    )
                )
                for c in range(2**n)
            }
            assert len(sizes) == 1, f"{table}: {sizes}"

    def test_bare_ring_is_entry_sensitive(self) -> None:
        r"""A bare ring sustains on right-entry and *halts* on down-entry."""
        from esolangs.interpreters.grid_based.arrowqueue import _Machine
        from esolangs.tools.boolean.parameterized import _TREE_1
        from esolangs.vm import run_until_halt_or_cycle

        rdlu = (0, 1, 2, 3)

        def verdict(state: tuple[int, int, int, tuple[int, ...]]) -> str:
            machine = _Machine(list(_TREE_1))
            machine.state = (*state, not machine.grid)
            return "0" if run_until_halt_or_cycle(machine) else "1"

        assert verdict((0, 0, 0, rdlu)) == "1"  # right-entry: the ring closes.
        assert verdict((0, 1, 1, rdlu)) == "0"  # down-entry: it does not.

    def test_constant_one_never_tops_out_as_a_bare_ring(self) -> None:
        r"""The top-level tree always carries a drain, so down-entry is safe."""
        from esolangs.tools.boolean.parameterized import (
            _TREE_1,
            _drained_leaf,
            _tree,
        )

        for n in range(1, 6):
            assert _tree(list("1" * (2**n))) == _drained_leaf("1", n)

        for n in (1, 2, 3):
            for value in range(2 ** (2**n)):
                table = format(value, f"0{2**n}b")
                assert _tree(list(table)) != list(_TREE_1), table


class TestParameterizedBfpda:
    r"""Input-by-substitution boolean generator for the no-input language."""

    def run_bfpda(self, prog: str) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.bf_pda import run

        io_ = ScriptedIO("")
        run(prog, io_)
        return io_.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        r"""Fill the template the way the example harness does."""
        from esolangs.tools.boolean.examples import _fill_bfpda

        return _fill_bfpda(tpl, bits)

    def test_both_bits_embed_at_the_same_width(self) -> None:
        r"""The setter is four characters whichever bit it carries."""
        from esolangs.tools.boolean.examples import _fill_bfpda

        for n in (1, 2, 3):
            for i in range(n):
                placeholder = "{X" + str(i) + "}"
                zeros = [0] * n
                ones = list(zeros)
                ones[i] = 1
                assert len(_fill_bfpda(placeholder, zeros)) == len(
                    _fill_bfpda(placeholder, ones)
                ), f"n={n} input {i}"

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("01", 1),  # identity.
            ("00", 1),  # constant zero.
            ("11", 1),  # constant one.
            ("0001", 2),  # AND.
            ("0110", 2),  # XOR.
            ("0111", 2),  # OR.
            ("1110", 2),  # NAND.
            ("11111110", 3),  # NAND3.
            ("01101001", 3),  # majority.
            ("1111111100000000", 4),  # top half.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.bfpda(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_bfpda(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        r"""Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.bfpda(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_bfpda(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        r"""The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.bfpda("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_program_structure(self) -> None:
        r"""Each input is embedded once (pre-loaded), not re-embedded per node."""

        from esolangs.tools.boolean import parameterized

        template = parameterized.bfpda("0110")
        assert template.count("{X0}") == 1
        assert template.count("{X1}") == 1
        assert "{C0}" not in template  # the marker is a constant, not.
        assert "{C1}" not in template
        assert len(re.findall(r"\{X\d+\}", template)) == 2  # n embeds.

    def test_leaf_print_is_balanced(self) -> None:
        r"""A leaf pops the remaining bits, prints the answer, and pops it."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.bfpda("10")  # NOT: one-leaf prints 1.
        assert "<@.>" in template
        assert "<.>" in template


class TestParameterizedHomeRow:
    r"""Input-by-substitution boolean generator for the no-input language."""

    def run_home_row(self, prog: str) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.home_row import run

        io_ = ScriptedIO("")
        run(prog, io_)
        return io_.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        r"""Fill the template the way the example harness does."""
        from esolangs.tools.boolean.examples import _fill_home_row

        return _fill_home_row(tpl, bits)

    def test_both_bits_embed_at_the_same_width(self) -> None:
        r"""The setter is two characters whichever bit it carries."""
        from esolangs.tools.boolean.examples import _fill_home_row

        for n in (1, 2, 3):
            for i in range(n):
                placeholder = "{X" + str(i) + "}"
                zeros = [0] * n
                ones = list(zeros)
                ones[i] = 1
                assert len(_fill_home_row(placeholder, zeros)) == len(
                    _fill_home_row(placeholder, ones)
                ), f"n={n} input {i}"

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("01", 1),  # identity.
            ("00", 1),  # constant zero.
            ("11", 1),  # constant one.
            ("0001", 2),  # AND.
            ("0110", 2),  # XOR.
            ("0111", 2),  # OR.
            ("1110", 2),  # NAND.
            ("11111110", 3),  # NAND3.
            ("01101001", 3),  # majority.
            ("1111111100000000", 4),  # top half.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.home_row(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_home_row(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        r"""Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.home_row(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_home_row(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_five_inputs_sample(self) -> None:
        r"""A sample of dense five-input tables, past the removed n <= 2 cap."""
        import random

        from esolangs.tools.boolean import parameterized

        n = 5
        rng = random.Random(0)
        for _ in range(5):
            table = "".join(rng.choice("01") for _ in range(2**n))
            template = parameterized.home_row(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_home_row(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        r"""The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.home_row("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_each_input_embedded_once(self) -> None:

        from esolangs.tools.boolean import parameterized

        template = parameterized.home_row("0110")
        assert template.count("{X0}") == 1
        assert template.count("{X1}") == 1
        assert "{C0}" not in template
        assert "{C1}" not in template
        assert len(re.findall(r"\{X\d+\}", template)) == 2


class TestParameterizedCOD:
    r"""Input-by-substitution boolean generator for the no-input language."""

    def run_cod(self, prog: str) -> str:
        from esolangs.interpreters.grid_based.cod import run
        from esolangs.interpreters.io import ScriptedIO

        io_ = ScriptedIO("")
        run(prog, io_)
        return io_.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        from esolangs.tools.boolean import parameterized

        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        return parameterized.instantiate(
            tpl,
            bits,
            lambda _i, b: ")" if b else " ",
        )

    @pytest.mark.parametrize(
        "table",
        [
            "0000",  # constant zero.
            "1111",  # constant one.
            "0001",  # AND.
            "0111",  # OR.
            "0110",  # XOR.
            "1001",  # XNOR.
            "1110",  # NAND.
            "1000",  # NOR.
            "0100",  # A and not B.
            "1101",  # A or not B.
        ],
    )
    def test_truth_table(self, table: str) -> None:
        r"""Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.cod(table)
        for combo in range(4):
            bits = [(combo >> (2 - 1 - i)) & 1 for i in range(2)]
            got = self.run_cod(self.instantiate(template, bits))
            assert got == f"{table[combo]}", f"table {table} inputs {bits}"

    def test_all_two_input_tables(self) -> None:
        r"""Every one of the sixteen two-input tables produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(16):
            table = format(table_int, "04b")
            template = parameterized.cod(table)
            for combo in range(4):
                bits = [(combo >> (2 - 1 - i)) & 1 for i in range(2)]
                got = self.run_cod(self.instantiate(template, bits))
                assert got == f"{table[combo]}", f"table {table} inputs {bits}"

    @pytest.mark.slow  # 1.1s: all 256 three-input.
    def test_all_three_input_tables(self) -> None:
        r"""Every one of the 256 three-input tables produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(256):
            table = format(table_int, "08b")
            template = parameterized.cod(table)
            for combo in range(8):
                bits = [(combo >> (3 - 1 - i)) & 1 for i in range(3)]
                got = self.run_cod(self.instantiate(template, bits))
                assert got == f"{table[combo]}", f"table {table} inputs {bits}"

    def test_program_always_terminates_with_one_value(self) -> None:
        r"""Every run prints exactly one value and leaves no cod alive."""
        from esolangs.interpreters.grid_based.cod import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.tools.boolean import parameterized

        template = parameterized.cod("0110")
        for combo in range(4):
            bits = [(combo >> (2 - 1 - i)) & 1 for i in range(2)]
            code = self.instantiate(template, bits)
            io_ = ScriptedIO("")
            machine = _Machine(code, io_)
            for _ in range(500):
                if machine.halted:
                    break
                machine.step()
            assert machine.halted
            # pylint: disable=duplicate-code
            assert len(io_.getvalue()) == 1

    def test_three_input_program_always_terminates_with_one_value(self) -> None:
        r"""Every three-input run prints exactly one value and halts."""
        from esolangs.interpreters.grid_based.cod import _Machine
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.tools.boolean import parameterized

        template = parameterized.cod("01101001")
        for combo in range(8):
            bits = [(combo >> (3 - 1 - i)) & 1 for i in range(3)]
            code = self.instantiate(template, bits)
            io_ = ScriptedIO("")
            machine = _Machine(code, io_)
            for _ in range(500):
                if machine.halted:
                    break
                machine.step()
            assert machine.halted
            # pylint: disable=duplicate-code
            assert len(io_.getvalue()) == 1

    def test_template_is_input_independent(self) -> None:
        r"""The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.cod("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_each_input_is_embedded_once(self) -> None:
        r"""The routing embeds each input exactly once, not per leaf."""

        from esolangs.tools.boolean import parameterized

        template = parameterized.cod("0110")
        assert template.count("{X0}") == 1
        assert template.count("{X1}") == 1
        assert len(re.findall(r"\{X\d+\}", template)) == 2

    @pytest.mark.parametrize(
        ("table", "rows", "columns"),
        [
            ("01", 5, 20),
            ("0110", 9, 44),
            ("0001", 9, 44),
            ("11110000", 8, 20),
            ("01101001", 17, 96),
        ],
    )
    def test_the_template_has_exact_dimensions(
        self, table: str, rows: int, columns: int
    ) -> None:
        r"""The drawing's extents, per table."""
        from esolangs.tools.boolean import parameterized

        grid = parameterized.cod(table).split("\n")
        assert len(grid) == rows
        assert max(len(row) for row in grid) == columns

    def test_a_dead_box_wall_frames_its_contents(self) -> None:
        r"""The wall is two wider than the names it encloses."""
        from esolangs.tools.boolean.cod import _cod_dead_box

        one = _cod_dead_box((0,)).split("\n")
        assert one == ["~~~", "~{X0}~", "~~~"]

        two = _cod_dead_box((0, 1)).split("\n")
        assert two == ["~~~~", "~{X0}{X1}~", "~~~~"]

    def test_the_grid_uses_only_cod_characters(self) -> None:
        r"""Nothing but the language's glyphs, the slots, and layout space."""
        from esolangs.tools.boolean import parameterized

        allowed = set(" ()+-012<>X{}~\n")
        for table in ("01", "0110", "01101001", "11110000"):
            assert set(parameterized.cod(table)) <= allowed, table

    def test_no_row_carries_trailing_space(self) -> None:
        r"""Rows are trimmed, so a row's length is its content's length."""
        from esolangs.tools.boolean import parameterized

        for table in ("01", "0110", "01101001"):
            for row in parameterized.cod(table).split("\n"):
                assert row == row.rstrip(), (table, repr(row))

    def test_a_table_ignoring_inputs_takes_the_reduced_build(self) -> None:
        r"""The reduction is kept only when it is strictly shorter."""
        from esolangs.tools.boolean import parameterized

        for table in ("11110000", "00001111", "10101010"):
            assert len(parameterized.cod(table)) == 113, table
        assert len(parameterized.cod("01101001")) == 1504

    def test_constant_table_rejected(self) -> None:
        r"""n == 0 (a single-entry table, no inputs) is not supported."""
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="n >= 1"):
            parameterized.cod("0")

    def test_four_input_tables(self) -> None:
        r"""n == 4 (beyond the old n <= 3 cap) produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table in ("1111111011111110", "0110100110010110", "1000000000000000"):
            template = parameterized.cod(table)
            for combo in range(16):
                bits = [(combo >> (4 - 1 - i)) & 1 for i in range(4)]
                got = self.run_cod(self.instantiate(template, bits))
                assert got == f"{table[combo]}", f"table {table} inputs {bits}"

    @pytest.mark.parametrize("table", ["10", "01", "00", "11"])
    def test_one_input_truth_table(self, table: str) -> None:
        r"""n == 1 has no fork of its own: a bare entry into the leaf cascade."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.cod(table)
        assert "{X0}" in template
        assert "{X1}" not in template
        for x0 in range(2):
            got = self.run_cod(self.instantiate(template, [x0]))
            assert got == f"{table[x0]}", f"table {table} input {x0}"

    def test_a_width_turns_the_drawing_a_quarter_turn(self) -> None:
        r"""Turning beats banding, because the blocks are joined left to right."""
        from esolangs.tools.boolean import cod as cod_module

        for table in ("0110", "01101001", "0110100110010110"):
            n = len(table).bit_length() - 1
            zeros = [0] * n
            flat = self.instantiate(cod_module(table), zeros)
            wide = max(len(row) for row in flat.splitlines())
            turned = self.instantiate(cod_module(table, 1), zeros)
            floor = max(len(row) for row in turned.splitlines())
            assert floor == 2 ** (n + 1) + 1, (table, floor)
            assert floor < wide, table
            for width in (1, 20, 40, 80, wide):
                template = cod_module(table, width)
                columns = max(
                    len(row) for row in self.instantiate(template, zeros).splitlines()
                )
                assert columns <= max(width, floor), (table, width, columns)
                for combo in range(2**n):
                    bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                    got = self.run_cod(self.instantiate(template, bits))
                    assert got.strip() == table[combo], (table, width, bits)

    def test_the_turn_re_attaches_every_print(self) -> None:
        r"""``---`` prints only as a *horizontal* run touching an edge."""
        from esolangs.tools.boolean import cod as cod_module

        table = "01101001"
        turned = self.instantiate(cod_module(table, 1), [0, 0, 0])
        rows = turned.splitlines()
        prints = [row for row in rows if row.startswith("-")]
        assert len(prints) == len(table), (len(prints), len(table))
        for row in prints:
            assert row.startswith("---"), row
            assert not row.startswith("----"), row


class TestEvalBoolean:
    r"""Input-by-substitution boolean generator for the no-input language."""

    def run_eval(self, prog: str) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.eval import run

        io_ = ScriptedIO("")
        run(prog, io_)
        return io_.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        r"""Fill the template the way the example harness does."""
        from esolangs.tools.boolean.examples import _fill_eval

        return _fill_eval(tpl, bits)

    def test_both_bits_embed_at_the_same_width(self) -> None:
        r"""The setter is two characters whichever bit it carries."""
        from esolangs.tools.boolean.examples import _fill_eval

        for n in (1, 2, 3):
            for i in range(n):
                placeholder = "{X" + str(i) + "}"
                zeros = [0] * n
                ones = list(zeros)
                ones[i] = 1
                assert len(_fill_eval(placeholder, zeros)) == len(
                    _fill_eval(placeholder, ones)
                ), f"n={n} input {i}"

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT.
            ("01", 1),  # identity.
            ("00", 1),  # constant zero.
            ("11", 1),  # constant one.
            ("0001", 2),  # AND.
            ("0110", 2),  # XOR.
            ("0111", 2),  # OR.
            ("1110", 2),  # NAND.
            ("11111110", 3),  # NAND3.
            ("01101001", 3),  # XOR3.
            ("1000000000000000", 4),  # AND4.
            ("1111111100000000", 4),  # top half.
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        r"""Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.eval(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_eval(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        r"""Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.eval(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_eval(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_constant_subtrees_fold_in_place(self) -> None:
        r"""A constant subtree becomes a leaf; its slots empty but remain."""
        from esolangs.tools.boolean import parameterized

        full = parameterized.eval("10010110")
        folded = parameterized.eval("11111111")
        assert len(folded) < len(full)
        # pylint: disable=duplicate-code
        assert folded.count('"') == full.count('"')
        assert '""' in folded

    def test_folding_keeps_both_bits_equal_width(self) -> None:
        r"""Folding shrinks the template, never one instantiation."""
        from esolangs.tools.boolean import parameterized

        for table in ("11111111", "11110000", "11001100", "0001"):
            n = len(table).bit_length() - 1
            template = parameterized.eval(table)
            widths = {
                len(
                    self.instantiate(
                        template, [(c >> (n - 1 - i)) & 1 for i in range(n)]
                    )
                )
                for c in range(2**n)
            }
            assert len(widths) == 1, f"{table} leaks its inputs: {widths}"

    def test_template_is_input_independent(self) -> None:
        r"""The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.eval("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_heap_tree_structure(self) -> None:
        r"""The template is a flat heap tree pushed BFS-order then reversed."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.eval("0110")
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        assert template.startswith("{X0}{X1}")
        assert template.endswith("*!")
        assert '"~=~?;!"' in template  # root node: one discard.
        assert '"~=~?;;!"' in template  # BFS index 1: two discards.
        assert template.count('"~=~?') == 3  # 2**2 - 1 internal nodes.
        assert template.count('"0+.') + template.count('"0.') == 4  # leaves.
        # pylint: disable=duplicate-code
        assert template.endswith('"0.""0+.""0+.""0."*!')

    def test_reordering_only_shrinks(self) -> None:
        r"""No table is longer than the arrangement staging already produces."""
        from esolangs.tools.boolean import parameterized
        from esolangs.tools.boolean.helpers import permute_truth_table
        from esolangs.tools.boolean.parameterized import _eval_ordered

        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        free = tuple(reversed(range(3)))
        improved = 0
        for value in range(256):
            table = format(value, "08b")
            dispatched = len(parameterized.eval(table))
            staged = len(_eval_ordered(permute_truth_table(table, free), ""))
            assert dispatched <= staged, table
            improved += dispatched < staged
        assert improved == 114

    def test_reorder_cost_selects_the_emitted_template(self) -> None:
        r"""The pricing model matches every candidate and picks the shortest."""
        from esolangs.tools import boolean
        from esolangs.tools.boolean.helpers import permute_truth_table
        from esolangs.tools.boolean.parameterized import (
            _eval_cost,
            _eval_ordered,
            _eval_stack_programs,
        )

        for n in (1, 2, 3):
            for value in range(2 ** (2**n)):
                table = format(value, f"0{2**n}b")
                costs = []
                for arrangement, ops in _eval_stack_programs(n).items():
                    permuted = permute_truth_table(table, tuple(reversed(arrangement)))
                    assert _eval_cost(permuted, ops) == len(
                        _eval_ordered(permuted, ops)
                    )
                    costs.append(_eval_cost(permuted, ops))
                assert len(boolean.eval(table)) == min(costs)

    def test_reorder_ops_run_outside_the_placeholders(self) -> None:
        r"""The rearrangement is emitted code, not a change to the fills."""
        from esolangs.tools.boolean import parameterized
        from esolangs.tools.boolean.examples import _fill_eval

        # pylint: disable=duplicate-code
        table = "00001101"
        template = parameterized.eval(table)
        assert template.startswith("{X0}{X1}{X2}")  # slots unmoved.
        widths = {
            len(_fill_eval(template, [(c >> (2 - i)) & 1 for i in range(3)]))
            for c in range(8)
        }
        assert len(widths) == 1  # every fill the same length.

    def test_stack_ops_reach_every_arrangement(self) -> None:
        r"""Two stacks with a reverse and a cross-move permute the bits."""
        from math import factorial

        from esolangs.tools.boolean.parameterized import _eval_stack_programs

        for n in (2, 3, 4):
            assert len(_eval_stack_programs(n)) == factorial(n)
        # pylint: disable=duplicate-code
        assert _eval_stack_programs(3)[(0, 1, 2)] == ""

    def test_reorder_catalog_invariants(self) -> None:
        r"""The built words are capped, deduplicated and (length, ~<*<=)-sorted."""
        from esolangs.tools.boolean.parameterized import (
            _EVAL_MAX_OPS,
            _eval_reorders,
        )

        built = _eval_reorders()
        assert len(set(built)) == len(built)
        assert built[0] == ""
        assert all(len(ops) <= _EVAL_MAX_OPS for ops in built)
        rank = {"~": 0, "*": 1, "=": 2}
        keys = [(len(ops), [rank[op] for op in ops]) for ops in built]
        assert keys == sorted(keys)

    def test_reorder_words_are_the_capped_reachable_set(self) -> None:
        r"""Every built word replays, and the built set is exactly the cap's."""
        from esolangs.tools.boolean.parameterized import _eval_stack_programs

        assert len(_eval_stack_programs(12)) == 735
        assert len(_eval_stack_programs(13)) == 735
        assert len(_eval_stack_programs(7)) == 620
        assert len(_eval_stack_programs(4)) == 24

    def test_reorder_catalog_matches_search(self) -> None:
        r"""The catalog fold reproduces the search it replaced, byte for byte."""
        from collections import deque

        from esolangs.tools.boolean.parameterized import (
            _EVAL_MAX_OPS,
            _eval_stack_programs,
        )

        def searched(n: int) -> dict[tuple[int, ...], str]:
            start: tuple[tuple[int, ...], tuple[int, ...], int] = (
                (),
                tuple(range(n)),
                0,
            )
            seen = {start: ""}
            frontier = deque([start])
            reached: dict[tuple[int, ...], str] = {}
            while frontier:
                state = frontier.popleft()
                tree, read, active = state
                ops = seen[state]
                if active == 0 and not tree and read not in reached:
                    reached[read] = ops
                if len(ops) >= _EVAL_MAX_OPS:
                    continue
                stacks = {0: tree, 1: read}
                moves = [((tree, read, 1 - active), "~")]
                flipped = tuple(reversed(stacks[active]))
                moves.append(
                    ((flipped, read, active), "*")
                    if active == 0
                    else ((tree, flipped, active), "*")
                )
                if stacks[active]:
                    moved, rest = stacks[active][-1], stacks[active][:-1]
                    other = (*stacks[1 - active], moved)
                    moves.append(
                        ((rest, other, active), "=")
                        if active == 0
                        else ((other, rest, active), "=")
                    )
                for next_state, op in moves:
                    if next_state not in seen:
                        seen[next_state] = ops + op
                        frontier.append(next_state)
            return reached

        for n in range(6):
            assert list(_eval_stack_programs(n).items()) == list(searched(n).items())

    def test_scales_to_more_inputs(self) -> None:
        r"""The heap tree grows to any n (spot-checked at n = 6)."""
        from esolangs.tools.boolean import parameterized

        n = 6
        table = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(2**n))
        template = parameterized.eval(table)
        assert len(template) < 3000
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_eval(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"


@pytest.mark.slow  # 2.6s: every fill of every.
def test_fills_embed_a_zero_and_a_one_at_equal_width() -> None:
    r"""No fill may spell a 0 shorter than a 1, or the length leaks the."""
    import itertools

    from esolangs.tools.boolean import examples as ex

    fills = [
        (name, getattr(ex, name))
        for name in dir(ex)
        if name.startswith("_fill_") and callable(getattr(ex, name))
    ]
    assert fills, "no _fill_* functions found"

    for name, fill in fills:
        gen_name = name.removeprefix("_fill_")
        gen = getattr(ex, gen_name, None) or getattr(
            importlib.import_module("esolangs.tools.boolean"), gen_name, None
        )
        if gen is None:  # pragma: no cover - fill without a same-named generator
            continue
        for n in (1, 2):
            template = gen(format(0, f"0{2**n}b"))
            lengths = {
                len(fill(template, list(bits)))
                for bits in itertools.product((0, 1), repeat=n)
            }
            assert len(lengths) == 1, (
                f"{name} embeds bits at unequal width for n={n}: {sorted(lengths)}"
            )


# pylint: disable=duplicate-code
@pytest.mark.medium
class TestParameterizedOneTwoThree:
    r"""Input-by-substitution boolean generator for the no-input language."""

    def run(self, program: str) -> str:
        return one_two_three_result(program)

    def instantiate(self, template: str, bits: list[int]) -> str:
        from esolangs.tools.boolean.one_two_three import ONE, ZERO

        for i, bit in enumerate(bits):
            template = template.replace(f"{{X{i}}}", ONE if bit else ZERO)
        return template

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        r"""Every one-, two- and three-input table halts or loops per its entry."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.one_two_three(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run(self.instantiate(template, bits))
                assert got == table[combo], (table, bits)

    def test_the_tables_walls_md_called_unreachable(self) -> None:
        r"""XOR and NAND build, against the recorded monotone ceiling."""
        from esolangs.tools.boolean import parameterized

        for table in ("0110", "1110", "1001", "1000"):
            template = parameterized.one_two_three(table)
            got = "".join(
                self.run(self.instantiate(template, [(c >> 1) & 1, c & 1]))
                for c in range(4)
            )
            assert got == table

    def test_no_row_diverges(self) -> None:
        r"""No emitted row marches the pointer right forever."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.one_two_three import _Machine
        from esolangs.tools.boolean import parameterized

        for n in (1, 2, 3):
            for table_int in range(2 ** (2**n)):
                table = format(table_int, f"0{2**n}b")
                template = parameterized.one_two_three(table)
                for combo in range(2**n):
                    bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                    code = self.instantiate(template, bits)
                    machine = _Machine(code, ScriptedIO(""))
                    seen = set()
                    for _ in range(10_000):
                        if machine.halted:
                            break
                        state = machine.snapshot()
                        if state in seen:
                            break
                        seen.add(state)
                        machine.step()
                    else:  # pragma: no cover - a diverging row would reach here
                        pytest.fail(f"{code!r} neither halts nor revisits a state")

    def test_batched_gate_agrees_with_the_interpreter(self) -> None:
        r"""The construction's replay gate matches a per-command run."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.one_two_three import _Machine
        from esolangs.tools.boolean import parameterized
        from esolangs.tools.boolean.one_two_three_construct import _replay_verdict

        for n in (1, 2, 3):
            for table_int in range(2 ** (2**n)):
                table = format(table_int, f"0{2**n}b")
                template = parameterized.one_two_three(table)
                for combo in range(2**n):
                    bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                    code = self.instantiate(template, bits)
                    machine = _Machine(code, ScriptedIO(""))
                    seen = set()
                    stepwise = "1"
                    for _ in range(10_000):
                        if machine.halted:
                            stepwise = "0"
                            break
                        state = machine.snapshot()
                        if state in seen:
                            break
                        seen.add(state)
                        machine.step()
                    assert _replay_verdict(code) == stepwise == table[combo], (
                        table,
                        bits,
                    )

    @pytest.mark.slow
    def test_the_replay_gate_agrees_on_programs_it_did_not_build(self) -> None:
        r"""The batched executor is checked against arbitrary 123 code."""
        import random

        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.one_two_three import _Machine
        from esolangs.tools.boolean.one_two_three_construct import _replay_verdict

        def stepwise(code: str) -> str | None:
            r"""The interpreter's own verdict, or None if it is not comparable."""
            machine = _Machine(code, ScriptedIO(""))
            seen = set()
            for _ in range(20_000):
                if machine.halted:
                    return "0"
                state = machine.snapshot()
                if state in seen:
                    return "1"
                seen.add(state)
                try:
                    machine.step()
                except EOFError:
                    return None
            return None

        rng = random.Random(7)
        compared = 0
        for _ in range(300):
            code = "".join(rng.choice("123") for _ in range(rng.randint(1, 12)))
            expected = stepwise(code)
            if expected is None:
                continue
            try:
                got = _replay_verdict(code)
            except ValueError:
                continue  # the executor's own guards;.
            compared += 1
            assert got == expected, code
        assert compared == 177

    def test_the_construction_emits_an_exact_template(self) -> None:
        r"""``construct`` itself, pinned -- not the small route."""
        from esolangs.tools.boolean.one_two_three_construct import construct

        assert construct("01") == (
            "2222{X0}1111121211222222111111233222332233222211112221113311111111"
            "122222222212331111111111"
        )

    def test_the_constructed_lengths_are_stable_over_three_inputs(self) -> None:
        r"""Total emitted bytes over every three-input table."""
        from esolangs.tools.boolean.one_two_three_construct import construct

        total = sum(len(construct(format(value, "08b"))) for value in range(256))
        assert total == 206791

    def test_slots_run_in_name_order(self) -> None:
        r"""Every emitted template embeds {X0} before {X1}."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(16):
            table = format(table_int, "04b")
            template = parameterized.one_two_three(table)
            assert template.index("{X0}") < template.index("{X1}"), table

    def test_both_bits_embed_at_the_same_width(self) -> None:
        r"""A zero and a one embed at equal width, so length leaks nothing."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(16):
            table = format(table_int, "04b")
            template = parameterized.one_two_three(table)
            sizes = {
                len(self.instantiate(template, [(c >> 1) & 1, c & 1])) for c in range(4)
            }
            assert len(sizes) == 1, (table, sizes)

    def test_a_wider_table_is_constructed(self) -> None:
        r"""A four-input table builds through the constructed route."""
        from esolangs.tools.boolean import parameterized

        table = "0000000000000000"
        template = parameterized.one_two_three(table)
        xs = [template.index(f"{{X{i}}}") for i in range(4)]
        assert xs == sorted(xs), table
        sizes = set()
        for combo in range(16):
            bits = [(combo >> (3 - i)) & 1 for i in range(4)]
            program = self.instantiate(template, bits)
            sizes.add(len(program))
            assert self.run(program) == table[combo], (table, bits)
        assert len(sizes) == 1, (table, sizes)

    @pytest.mark.parametrize(
        ("table", "length"),
        [
            ("00000000", 72),
            ("10000000", 368),
            ("00010111", 210),
            ("01101001", 160),
        ],
    )
    def test_three_inputs_take_the_small_route(self, table: str, length: int) -> None:
        r"""``n == 3`` builds from the separation law, not the wide route."""
        from esolangs.tools.boolean import parameterized

        assert len(parameterized.one_two_three(table)) == length

    @pytest.mark.slow
    def test_the_separation_law_is_the_least_mean(self) -> None:
        r"""The law's constants are re-derived, not trusted."""
        from itertools import product

        from esolangs.tools.boolean.one_two_three import (
            _LAWS,
            _WORK_BUDGET,
            ConstructError,
            _Builder,
            _endgame,
            _on_mark,
            _verdict_junky,
            _work,
        )

        def prototype(n: int, walk: int, disps: tuple[int, ...]) -> object:
            r"""Replay one candidate law, or ``None`` if it does not fit."""
            # pylint: disable=duplicate-code
            # pylint: disable=duplicate-code
            # pylint: disable=duplicate-code
            # pylint: disable=duplicate-code
            # pylint: disable=duplicate-code
            # pylint: disable=duplicate-code
            # pylint: disable=duplicate-code
            _work[0] = _WORK_BUDGET
            try:
                b = _Builder(n)
                for i in range(n):
                    if walk:
                        b.run("2" * walk)
                    b.fill(i)
                for d in range(4 * 2**n + 9):
                    probe = b.clone()
                    if d:
                        probe.run("2" * d)
                    if any(r.pos < 0 for r in probe.live()):
                        continue
                    if not any(_on_mark(r) for r in probe.live()):
                        if d:
                            b.run("2" * d)
                        b.test()
                        break
                else:
                    return None
                for i, step in enumerate(disps):
                    b.run(("1" if i % 2 == 0 else "2") * step)
                    b.test()
            except ConstructError:
                return None
            poss = [r.pos for r in b.live()]
            if len(set(poss)) != len(poss) or any(p % 2 == 0 for p in poss):
                return None
            return b

        def mean_length(n: int, proto: object) -> float | None:
            total = 0
            tables = ["".join(t) for t in product("01", repeat=2**n)]
            for table in tables:
                _work[0] = _WORK_BUDGET
                b = proto.clone()  # type: ignore[attr-defined]
                try:
                    _verdict_junky(b, table)
                    _endgame(b)
                except ConstructError:
                    return None
                total += len(b.template())
            return total / len(tables)

        for n in (1, 2):
            ranked = []
            for walk in range(9):
                for depth in range(5):
                    for disps in product(range(1, 11), repeat=depth):
                        proto = prototype(n, walk, disps)
                        if proto is None:
                            continue
                        mean = mean_length(n, proto)
                        if mean is not None:
                            ranked.append((mean, walk, disps))
            assert ranked, n
            ranked.sort()
            _best_mean, best_walk, best_disps = ranked[0]
            assert (best_walk, best_disps) == _LAWS[n], (n, ranked[:3])

    def test_the_wide_route_is_bigger_where_they_overlap(self) -> None:
        r"""The small route earns its place at the arity they share."""
        from esolangs.tools.boolean.one_two_three import one_two_three
        from esolangs.tools.boolean.one_two_three_construct import construct

        for table in ("00000000", "00000001", "01101001"):
            assert len(construct(table)) > len(one_two_three(table)), table

    @pytest.mark.parametrize(
        ("table", "template"),
        [
            ("01", "{X0}223311122212331111"),
            ("0001", "22{X0}22{X1}22331113322331111332133121233111111121121"),
        ],
    )
    def test_the_emitted_template_is_exact(self, table: str, template: str) -> None:
        r"""The construction is deterministic down to the byte."""
        from esolangs.tools.boolean import parameterized

        assert parameterized.one_two_three(table) == template

    def test_the_paint_pass_is_only_run_when_something_was_painted(
        self,
    ) -> None:
        r"""``b.test()`` after the paints is conditional, and the flag varies."""
        from esolangs.tools.boolean import parameterized

        total = 0
        for n in (1, 2, 3):
            for table_int in range(2 ** (2**n)):
                table = format(table_int, f"0{2**n}b")
                total += len(parameterized.one_two_three(table))
        assert total == 55238

    def test_a_seed_with_even_positions_is_refused(self) -> None:
        r"""The junky verdict rejects a seed whose rows are not distinct odd."""
        from esolangs.tools.boolean.one_two_three import (
            _WORK_BUDGET,
            ConstructError,
            _separated,
            _verdict_junky,
            _work,
        )

        _work[0] = _WORK_BUDGET
        builder = _separated(1).clone()
        # pylint: disable=duplicate-code
        builder.live()[0].pos += 1
        assert any(r.pos % 2 == 0 for r in builder.live())
        with pytest.raises(ConstructError) as caught:
            _verdict_junky(builder, "01")
        assert str(caught.value) == "verdict precondition: positions not distinct odd"

    def test_every_pipeline_stage_fires_on_one_table(self) -> None:
        r"""A single table exercises each stage the docstring describes."""
        from esolangs.tools.boolean import one_two_three_construct as construct_mod

        called: set[str] = set()
        originals = {
            name: getattr(construct_mod, name)
            for name in ("_phase_a", "_separate", "_paint_all", "_verdict", "_endgame")
        }

        def watch(name: str, fn: object) -> object:
            def wrapper(*args: object, **kwargs: object) -> object:
                called.add(name)
                return fn(*args, **kwargs)  # type: ignore[operator]

            return wrapper

        for name, fn in originals.items():
            setattr(construct_mod, name, watch(name, fn))
        try:
            # pylint: disable=duplicate-code
            # pylint: disable=duplicate-code
            template = construct_mod.construct("00111000")
        finally:
            for name, fn in originals.items():
                setattr(construct_mod, name, fn)

        assert called == set(originals), called
        for combo in range(8):
            bits = [(combo >> (2 - i)) & 1 for i in range(3)]
            program = self.instantiate(template, bits)
            assert self.run(program) == "00111000"[combo], bits

    def test_the_searched_routes_worst_tables_build_at_once(self) -> None:
        r"""The tables that starved the searched verdict are ordinary now."""
        from esolangs.tools.boolean.one_two_three_construct import construct

        for table in ("1000110011010101", "0100000011001001"):
            # pylint: disable=duplicate-code
            template = construct(table)
            for combo in range(16):
                bits = [(combo >> (3 - i)) & 1 for i in range(4)]
                program = self.instantiate(template, bits)
                assert self.run(program) == table[combo], (table, bits)

    @pytest.mark.slow  # one four-input template, all.
    def test_a_dense_four_input_sweep_witness_stays_exact(self) -> None:
        r"""Pin one mixed table from the exhaustive constructor sweep."""
        from esolangs.tools.boolean.one_two_three_construct import construct

        table = "1100010001000111"
        template = construct(table)
        for combo in range(16):
            bits = [(combo >> (3 - i)) & 1 for i in range(4)]
            program = self.instantiate(template, bits)
            assert self.run(program) == table[combo], (table, bits)

    def test_paint_marks_one_cell_and_restores_every_position(self) -> None:
        r"""``_paint(k)`` flips exactly cell ``pos + k`` per row, in place."""
        from esolangs.tools.boolean.one_two_three_construct import (
            _RING,
            _WORK_BUDGET,
            _Builder,
            _paint,
            _work,
        )

        _work[0] = _WORK_BUDGET
        for k in (1, 2, 3, 17, 100):
            b = _Builder(2)
            tapes = (0, 0b1011 << _RING, 1 << (40 + _RING), 0b110 << _RING)
            for row, pos, tape in zip(b.rows, (1, 5, 29, 41), tapes, strict=True):
                row.pos, row.tape = pos, tape
            before = [(r.pos, r.tape) for r in b.rows]
            _paint(b, k)
            after = [(r.pos, r.tape) for r in b.rows]
            for (p0, t0), (p1, t1) in zip(before, after, strict=True):
                assert p1 == p0, k
                assert t1 == t0 ^ (1 << (p0 + k + _RING)), k

    def test_the_verdict_checks_its_position_preconditions(self) -> None:
        r"""A state violating the parity law raises instead of emitting."""
        from esolangs.tools.boolean.one_two_three_construct import (
            _WORK_BUDGET,
            ConstructError,
            _Builder,
            _verdict,
            _work,
        )

        _work[0] = _WORK_BUDGET
        even = _Builder(1)
        even.rows[0].pos, even.rows[1].pos = 2, 5
        with pytest.raises(ConstructError, match="precondition"):
            _verdict(even, "01")

        shared = _Builder(1)
        shared.rows[0].pos = shared.rows[1].pos = 5
        with pytest.raises(ConstructError, match="precondition"):
            _verdict(shared, "01")

        all_zero = _Builder(1)
        all_zero.rows[0].pos, all_zero.rows[1].pos = 2, 5
        _verdict(all_zero, "00")  # no 1-rows: nothing to prove,.

    def test_an_exhausted_work_budget_is_declined(self) -> None:
        r"""A table that would build still raises once the work runs out."""
        from esolangs.tools.boolean import one_two_three_construct as construct_mod

        original_budget = construct_mod._WORK_BUDGET  # noqa: SLF001
        construct_mod._WORK_BUDGET = 50  # noqa: SLF001
        try:
            with pytest.raises(ValueError, match="work budget ran out"):
                construct_mod.construct("00000000")
        finally:
            construct_mod._WORK_BUDGET = original_budget  # noqa: SLF001

    def test_normalize_reports_a_live_locked_ring(self) -> None:
        r"""Four distinct rows pinned to all four ring cells cannot escape."""
        from esolangs.tools.boolean.one_two_three_construct import (
            ConstructError,
            _Builder,
            _normalize,
            _Row,
            _work,
        )

        rows = []
        for i, pos in enumerate((-1, -2, -3, 0)):
            row = _Row((i,))
            row.pos = pos
            rows.append(row)
        b = _Builder.__new__(_Builder)
        b.n = 1
        b.chunks = []
        b.seg = []
        b.rows = rows
        _work[0] = 100_000  # _normalize is called outside.
        with pytest.raises(ConstructError, match="live-locked"):
            _normalize(b)

    def test_close_reports_no_clean_cell_in_range(self) -> None:
        r"""A row TRUE on every cell in the search window has no exit."""
        from esolangs.tools.boolean.one_two_three_construct import (
            ConstructError,
            _Builder,
            _close,
            _mask,
            _Row,
            _work,
        )

        row = _Row((0,))
        row.pos = 0
        row.tape = _mask(range(100002))
        b = _Builder.__new__(_Builder)
        b.n = 1
        b.chunks = []
        b.seg = []
        b.rows = [row]
        _work[0] = 10_000_000  # _close is called outside.
        with pytest.raises(ConstructError, match="no clean closing cell"):
            _close(b)

    def test_fixpoint_reports_a_non_converging_rerun(self) -> None:
        r"""A segment that never revisits a state within the cap gives up."""
        from esolangs.tools.boolean.one_two_three_construct import (
            ConstructError,
            _Builder,
            _mask,
            _Row,
            _work,
        )

        row = _Row((0,))
        row.pos = 0
        row.tape = _mask(range(200))
        b = _Builder.__new__(_Builder)
        b.n = 1
        b.chunks = []
        b.seg = ["2"]
        b.rows = [row]
        _work[0] = 10_000  # fixpoint is called outside.
        with pytest.raises(ConstructError, match="fixpoint cap"):
            b.fixpoint(row)

    def test_test_reports_a_kill_that_escapes(self) -> None:
        r"""``test(kills=...)`` requires every named victim to provably loop."""
        from esolangs.tools.boolean.one_two_three_construct import (
            ConstructError,
            _Builder,
            _mask,
            _Row,
            _work,
        )

        row = _Row((0,))
        row.pos = 0
        row.tape = _mask({0})
        b = _Builder.__new__(_Builder)
        b.n = 1
        b.chunks = []
        b.seg = ["2"]  # pos 0 -> 1, leaves the tape:.
        b.rows = [row]
        _work[0] = 10_000  # test() is called outside.
        with pytest.raises(ConstructError, match="kill escaped"):
            b.test(kills=frozenset({(0,)}))

    def test_test_reports_a_kill_that_never_fires(self) -> None:
        r"""``test(kills=...)`` refuses a close where a victim tested FALSE."""
        from esolangs.tools.boolean.one_two_three_construct import (
            ConstructError,
            _Builder,
            _Row,
            _work,
        )

        row = _Row((0,))
        row.pos = 0
        row.tape = 0  # nothing marked: the victim.
        b = _Builder.__new__(_Builder)
        b.n = 1
        b.chunks = []
        b.seg = ["2"]
        b.rows = [row]
        _work[0] = 10_000  # test() is called outside.
        with pytest.raises(ConstructError, match="kill missed"):
            b.test(kills=frozenset({(0,)}))

    def test_test_reports_an_unintended_loop(self) -> None:
        r"""A plain ``test()`` requires every TRUE row to escape, not loop."""
        from esolangs.tools.boolean.one_two_three_construct import (
            ConstructError,
            _Builder,
            _mask,
            _Row,
            _work,
        )

        row = _Row((0,))
        row.pos = 0
        row.tape = _mask({0})
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        b = _Builder.__new__(_Builder)
        b.n = 1
        b.chunks = []
        b.seg = ["1"] * 8
        b.rows = [row]
        _work[0] = 10_000  # test() is called outside.
        with pytest.raises(ConstructError, match="unintended loop"):
            b.test()

    def test_an_empty_table_is_declined(self) -> None:
        r"""A table implying zero inputs raises rather than building nothing."""
        from esolangs.tools.boolean import parameterized

        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        with pytest.raises(ValueError, match="at least one input") as caught:
            parameterized.one_two_three("1")
        assert str(caught.value) == (
            "truth table needs at least one input (n >= 1); "
            "a one-entry table is a constant, not a boolean function"
        )

    def test_out_of_order_slots_are_refused(self) -> None:
        r"""The name-order invariant is asserted, not assumed."""
        from esolangs.tools.boolean.one_two_three import _in_name_order

        assert _in_name_order("{X0}{X1}", 2) == "{X0}{X1}"

        with pytest.raises(ValueError, match="out of name order") as caught:
            _in_name_order("{X1}{X0}", 2)
        assert str(caught.value) == (
            "template '{X1}{X0}' emits slots out of name order"
        )

    def test_each_input_is_embedded_once(self) -> None:
        r"""Each placeholder appears exactly once, and no {Ci} appears."""

        from esolangs.tools.boolean import parameterized

        for n in (1, 2, 3):
            for table_int in range(2 ** (2**n)):
                table = format(table_int, f"0{2**n}b")
                template = parameterized.one_two_three(table)
                xs = re.findall(r"\{X(\d+)\}", template)
                assert sorted(xs) == [str(i) for i in range(n)], (table, xs)
                assert not re.findall(r"\{C(\d+)\}", template), table

    def test_every_batched_run_charges_the_work_budget(self) -> None:
        r"""Each closed form in ``_exec_run`` has to stop on a drained budget."""
        from esolangs.tools.boolean.one_two_three_construct import (
            _exec_char,
            _exec_run,
            _Row,
            _work,
            _WorkExhaustedError,
        )

        def drained(budget: int, ch: str, pos: int, w: int) -> None:
            row = _Row((0,))
            row.pos = pos
            _work[0] = budget
            _exec_run(row, ch, w)

        # pylint: disable=duplicate-code
        _work[0] = 0
        with pytest.raises(_WorkExhaustedError):
            _exec_char(_Row((0,)), "1")
        # pylint: disable=duplicate-code
        with pytest.raises(_WorkExhaustedError):
            drained(3, "2", 0, 10)
        # pylint: disable=duplicate-code
        with pytest.raises(_WorkExhaustedError):
            drained(3, "1", 8, 5)
        # pylint: disable=duplicate-code
        with pytest.raises(_WorkExhaustedError):
            drained(2, "1", 5, 20)
        # pylint: disable=duplicate-code
        with pytest.raises(_WorkExhaustedError):
            drained(3, "1", -1, 12)

    def test_the_endgame_parks_survivors_and_reports_a_state_it_cannot(
        self,
    ) -> None:
        r"""Parking is what makes a template halt, so failing it must raise."""
        from esolangs.tools.boolean.one_two_three_construct import (
            _WORK_BUDGET,
            ConstructError,
            _Builder,
            _endgame,
            _Row,
            _work,
        )

        _work[0] = _WORK_BUDGET

        no_survivors = _Builder(1)
        for row in no_survivors.rows:
            row.dead = True
        _endgame(no_survivors)  # returns rather than dividing.

        crowded = _Builder(2)
        for i, row in enumerate(crowded.rows):
            row.pos, row.tape = i, 0
        assert len({row.pos % 4 for row in crowded.live()}) == 4
        _endgame(crowded)
        assert {row.pos for row in crowded.live()} == {-1}

        stranded = _Builder.__new__(_Builder)
        stranded.n = 1  # an allowance of 192 passes.
        stranded.chunks, stranded.seg = [], []
        stranded.rows = []
        for i in range(12):
            row = _Row((i,))
            row.pos, row.tape = i * 977, 0
            stranded.rows.append(row)
        with pytest.raises(ConstructError, match="endgame did not converge"):
            _endgame(stranded)

    def test_a_stage_refusal_surfaces_as_a_value_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        r"""A stage that cannot prove its move is reported, never worked around."""
        from esolangs.tools.boolean import one_two_three_construct as module

        def refuse(*_: object, **__: object) -> None:
            raise module.ConstructError("verdict precondition: constructed refusal")

        monkeypatch.setattr(module, "_verdict", refuse)
        with pytest.raises(ValueError, match="123 construction failed"):
            module.construct("0110")

    def test_a_looping_row_reads_as_a_one(self) -> None:
        r"""A 1-row is decided by cycle detection, not by halting."""
        from esolangs.tools.boolean.one_two_three_construct import (
            _replay_verdict,
            construct,
        )

        template = construct("01")
        for bit in (0, 1):
            program = self.instantiate(template, [bit])
            assert self.run(program) == "01"[bit], bit
            assert _replay_verdict(program) == "01"[bit], bit

    def test_a_spread_of_three_input_tables_builds(self) -> None:
        r"""A stride-17 sample of the 256 three-input tables all build."""
        from esolangs.tools.boolean.one_two_three_construct import construct

        built = 0
        for value in range(0, 256, 17):
            try:
                construct(format(value, "08b"))
            except ValueError:
                continue
            built += 1
        assert built == 16

    def test_the_remaining_batched_run_and_token_paths(self) -> None:
        r"""``2`` from inside the ring batches too, and a plain token is a char."""
        from esolangs.tools.boolean.one_two_three_construct import (
            _WORK_BUDGET,
            _Builder,
            _exec_run,
            _Row,
            _work,
            _WorkExhaustedError,
        )

        inside_the_ring = _Row((0,))
        inside_the_ring.pos = -1
        _work[0] = 2
        with pytest.raises(_WorkExhaustedError):
            _exec_run(inside_the_ring, "2", 10)

        _work[0] = _WORK_BUDGET
        b = _Builder(1)
        b.apply_token(b.rows[0], "1")
        assert b.rows[0].pos == -1

    def test_a_two_at_minus_three_is_refused_rather_than_reading_stdin(self) -> None:
        r"""``2`` at -3 would read real input, so the move is rejected."""
        from esolangs.tools.boolean.one_two_three_construct import (
            _WORK_BUDGET,
            ConstructError,
            _exec_char,
            _Row,
            _work,
        )

        _work[0] = _WORK_BUDGET
        reads_stdin = _Row((0,))
        reads_stdin.pos = -3
        with pytest.raises(ConstructError, match="reads stdin"):
            _exec_char(reads_stdin, "2")

        wraps = _Row((0,))
        wraps.pos = -2
        _exec_char(wraps, "2")
        assert wraps.pos == 0

        steps = _Row((0,))
        steps.pos = 4
        _exec_char(steps, "2")
        assert steps.pos == 5

    def test_closing_walks_only_when_a_row_sits_on_a_true_cell(self) -> None:
        r"""``_close`` emits the walk it needs and nothing when already clean."""
        from esolangs.tools.boolean.one_two_three_construct import (
            _RING,
            _WORK_BUDGET,
            _Builder,
            _close,
            _work,
        )

        _work[0] = _WORK_BUDGET
        already_clean = _Builder(1)
        _close(already_clean)
        assert "2" not in "".join(already_clean.chunks)

        _work[0] = _WORK_BUDGET
        needs_a_walk = _Builder(1)
        needs_a_walk.run("1")  # flips cell 0 TRUE and steps.
        _close(needs_a_walk)
        emitted = "".join(needs_a_walk.chunks)
        assert "2" in emitted
        # pylint: disable=duplicate-code
        assert all(
            row.pos >= 0 and not row.tape >> (row.pos + _RING) & 1
            for row in needs_a_walk.live()
        )

    def test_replaying_twos_handles_the_empty_walk_and_the_stdin_cell(self) -> None:
        r"""A zero-width run is a no-op; a run starting at -3 is refused."""
        from esolangs.tools.boolean.one_two_three_construct import (
            ConstructError,
            _replay_twos,
        )

        # pylint: disable=duplicate-code
        assert _replay_twos(5, 0b1011, 0) == (5, 0b1011)
        assert _replay_twos(-3, 0, -2) == (-3, 0)  # a negative width is empty too.

        with pytest.raises(ConstructError, match="reads stdin"):
            _replay_twos(-3, 0, 1)

    def test_replaying_a_verdict_skips_commandless_and_unknown_characters(
        self,
    ) -> None:
        r"""Only ``1`` and ``2`` are commands; everything else is a NOP."""
        from esolangs.tools.boolean.one_two_three_construct import _replay_verdict

        assert _replay_verdict("") == "0"
        assert _replay_verdict("xyz") == "0"  # no command: nothing to run.
        # pylint: disable=duplicate-code
        assert _replay_verdict("1x1") == _replay_verdict("11")
        assert _replay_verdict("x1y1z") == _replay_verdict("11")


def test_nocomment_wide_declines_when_the_plan_outgrows_the_skip() -> None:
    r"""Past fifteen inputs the summand plan leaves no room to widen."""
    from esolangs.tools.boolean import parameterized

    table = "0" * (2**15 - 1) + "1"
    with pytest.raises(ValueError, match="past the interpreter's 4096-cell tape"):
        parameterized._nocomment_wide(table, 15, parameterized._TAPE)  # noqa: SLF001


class TestConstructorWorkBudget:
    r"""Two paths that lost their exerciser with the text generators."""

    def test_a_fill_token_resolves_to_the_row_own_bit(self) -> None:
        r"""A tuple token is an input fill: the row decides its character."""
        from esolangs.tools.boolean.one_two_three_construct import (
            _ONE,
            _ZERO,
            _Row,
            _row_runs,
        )

        one = _Row((1,))
        zero = _Row((0,))
        assert _row_runs(one, [("x", 0)]) == [(_ONE, 1)]
        assert _row_runs(zero, [("x", 0)]) == [(_ZERO, 1)]

    def test_a_fill_coalesces_with_the_run_beside_it(self) -> None:
        r"""Adjacent equal characters become one run, fills included."""
        from esolangs.tools.boolean.one_two_three_construct import (
            _ONE,
            _Row,
            _row_runs,
        )

        row = _Row((1,))
        assert _row_runs(row, [_ONE * 2, ("x", 0)]) == [(_ONE, 3)]

    def test_painting_past_the_budget_is_refused(self) -> None:
        r"""``_paint_all`` prices its whole paint before writing any of it."""
        from esolangs.tools.boolean.one_two_three_construct import (
            _Builder,
            _paint_all,
            _Row,
            _work,
            _WorkExhaustedError,
        )

        row = _Row((0,))
        row.pos = 1
        b = _Builder.__new__(_Builder)
        b.n = 1
        b.chunks = []
        b.seg = []
        b.rows = [row]
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        # pylint: disable=duplicate-code
        _work[0] = 1  # _paint_all is called outside.
        with pytest.raises(_WorkExhaustedError):
            _paint_all(b, (1, 3))
