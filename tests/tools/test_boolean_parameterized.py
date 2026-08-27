"""Unit tests for the parameterized (no-input) boolean generators.

Covers :mod:`esolangs.tools.boolean.parameterized`, whose languages take no
input and instead embed each input by substitution, plus the COD and Eval
generators that follow the same convention.
"""

import importlib
import io
import random
from contextlib import redirect_stdout
from unittest.mock import patch

import pytest

from esolangs.interpreters.io import IO
from esolangs.tools.boolean.parameterized import _instantiate_arrowqueue


def _parameterized_generators():
    from esolangs.tools.boolean import parameterized

    return [
        (name, parameterized.__dict__[name])
        for name in (
            "arrowqueue",
            "bio",
            "back",
            "nocomment",
            "bfpda",
            "lamfunc",
            "bitdeque",
            "ram0",
            "minsky_swap",
            "eval",
        )
    ]


def test_parameterized_generators_embed_each_input_once() -> None:
    """Every no-input generator embeds each input exactly once.

    An input-capable language reads each of its n inputs exactly once per
    run; a no-input language's parameterized generator should match, so each
    {Xi} appears exactly once -- never re-embedded at multiple decision
    nodes.

    A {Ci} complement placeholder must not appear at all.  instantiate no
    longer fills one, so a template carrying it would ship the literal text
    to the interpreter instead of failing, which is worth catching here.
    """
    import re

    for name, gen in _parameterized_generators():
        for n in (1, 2, 3, 4):
            table = format(0, f"0{2**n}b")
            template = gen(table)
            xs = re.findall(r"\{X(\d+)\}", template)
            cs = re.findall(r"\{C(\d+)\}", template)
            assert sorted(xs) == [str(i) for i in range(n)], (name, n, xs)
            assert len(xs) == n, (name, n, xs)
            assert not cs, (name, n, cs)


class TestParameterizedBIO:
    """Input-by-substitution generators for the no-input language BIO."""

    def run_bio(self, prog: str, bits: list[int]) -> str:

        from esolangs.interpreters.io import IO

        run = importlib.import_module("esolangs.interpreters.register_based.bio").run
        buffer = io.StringIO()
        with (
            patch("builtins.input", side_effect=[str(b) for b in bits]),
            redirect_stdout(buffer),
        ):
            run(prog, io=IO())
        return buffer.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Fill the template the way the example harness does."""
        from esolangs.tools.boolean.examples import _fill_bio

        return _fill_bio(tpl, bits)

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.bio(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_bio(self.instantiate(template, bits), bits)
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.bio("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_each_input_is_stored_once(self) -> None:
        """The packing scheme embeds each input exactly once."""
        import re

        from esolangs.tools.boolean import parameterized

        for n in (1, 2, 3):
            table = format(0, f"0{2**n}b")
            template = parameterized.bio(table)
            assert len(re.findall(r"\{X\d+\}", template)) == n

    def test_both_bits_embed_at_the_same_width(self) -> None:
        """A zero pads against the unread ``z``, so the program's length
        does not reveal the inputs."""
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
        """``z`` is inert: the generator emits no command that reads it."""
        from esolangs.tools.boolean import parameterized

        for n in (1, 2, 3):
            template = parameterized.bio(format(0, f"0{2**n}b"))
            assert "z" not in template.lower()


class TestParameterizedBack:
    """Input-by-substitution generators for the no-input language Back."""

    def run_back(self, prog: str, n: int) -> str:
        # Back has no output instruction: it dumps the whole tape at halt.
        # The generator puts the answer in cell n, so the dump's (n+1)th
        # field is the result -- no need to track the head, which the dump
        # does not report.
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.back import run

        io = ScriptedIO()
        run(prog.splitlines(), io)
        return io.getvalue().split()[n]

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Fill the template the way the example harness does."""
        from esolangs.tools.boolean.examples import _fill_back

        return _fill_back(tpl, bits)

    def test_program_length_is_the_same_for_every_input(self) -> None:
        """Both bits cost one command, so the size reveals nothing."""
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
            ("10", 1),  # NOT
            ("01", 1),
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
            ("1111111100000000", 4),  # top half
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.back(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_back(self.instantiate(template, bits), n)
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.back(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_back(self.instantiate(template, bits), n)
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.back("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_each_input_is_stored_once(self) -> None:
        """Each input is embedded once in the tape load, not re-embedded."""
        import re

        from esolangs.tools.boolean import parameterized

        for n in (1, 2, 3):
            table = format(0, f"0{2**n}b")
            template = parameterized.back(table)
            assert len(re.findall(r"\{X\d+\}", template)) == n

    def test_tree_uses_tape_decision_nodes(self) -> None:
        """The decision tree routes via '+\\' nodes and a down-transition."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.back("0110")
        assert "+\\" in template  # a decision node
        assert "*" in template  # leaves halt


class TestParameterizedNoComment:
    """Input-by-substitution boolean generator for the no-input language NoComment."""

    def run_nocomment(self, prog: str) -> str:
        from esolangs.interpreters.tape_based.nocomment import run

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            run(prog, IO())
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
            ("10", 1),  # NOT
            ("01", 1),
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.nocomment(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_nocomment(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.nocomment(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_nocomment(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.nocomment("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_program_structure(self) -> None:
        """A one-bit template computes the index then skips to the output."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.nocomment("10")
        assert template.startswith("{X0}")
        assert "{C0}" not in template  # the complement is computed at runtime
        assert template.endswith("o")  # a single final output
        assert template.count("s") == 3  # NOT gate + guarded increment + index skip
        assert template.count("o") == 1

    def test_four_input_works(self) -> None:
        """A dense four-input table assembles and runs correctly."""
        from esolangs.tools.boolean import parameterized

        for combo in range(16):
            bits = [(combo >> (3 - i)) & 1 for i in range(4)]
            template = parameterized.nocomment("1010101010101010")
            got = self.run_nocomment(self.instantiate(template, bits))
            assert got == str(int("1010101010101010"[combo])), f"inputs {bits}"

    def test_cap_rejected(self) -> None:
        """n > 8 needs an index beyond a byte and is rejected."""
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="n <= 8"):
            parameterized.nocomment("0" * (2**9))

    def test_bad_table_rejected(self) -> None:
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.nocomment("011")


class TestParameterizedLamfunc:
    """Input-by-substitution boolean generator for the no-input language Lamfunc."""

    def run_lamfunc(self, prog: str) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.other.lamfunc import run

        io = ScriptedIO()
        run(prog, io)
        return io.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        from esolangs.tools.boolean import parameterized

        # each {Xi} fills a `vs v{i}` store with the binary literal
        return parameterized.instantiate(
            tpl,
            bits,
            lambda _i, b: "0b" + str(b),
        )

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.lamfunc(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_lamfunc(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.lamfunc(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_lamfunc(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.lamfunc("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_each_input_is_stored_once(self) -> None:
        """The store-once scheme embeds each input exactly once."""
        import re

        from esolangs.tools.boolean import parameterized

        for n in (1, 2, 3):
            table = format(0, f"0{2**n}b")
            template = parameterized.lamfunc(table)
            assert len(re.findall(r"\{X\d+\}", template)) == n

    def test_constant_table_is_a_leaf(self) -> None:
        """A constant table emits the stores plus a single p with no branching."""
        from esolangs.tools.boolean import parameterized

        assert parameterized.lamfunc("0000") == "vs v0 {X0} vs v1 {X1} p 0"
        assert parameterized.lamfunc("1111") == "vs v0 {X0} vs v1 {X1} p 1"

    def test_bad_table_rejected(self) -> None:
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.lamfunc("011")


class TestParameterizedBitdeque:
    """Input-by-substitution boolean generator for the no-input language Bitdeque."""

    def run_bitdeque(self, prog: str) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.queue_based.bitdeque import run

        io = ScriptedIO()
        run(prog, io)
        return io.getvalue().strip()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        from esolangs.tools.boolean import parameterized

        n = len(bits)
        # The register flips after every load block, so bit i is pushed at
        # load position n-1-i with incoming register (n-1-i) % 2.
        return parameterized.instantiate(
            tpl,
            bits,
            lambda i, b: "PUSH INVERT" if b == (n - 1 - i) % 2 else "INVERT PUSH",
        )

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0001", 2),  # AND
            ("0110", 2),  # XOR
            ("0111", 2),  # OR
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # majority
            ("1111111100000000", 4),  # top half
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.bitdeque(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_bitdeque(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.bitdeque(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_bitdeque(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.bitdeque("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_constant_table_is_a_leaf(self) -> None:
        """A constant table emits a drain-and-push leaf with no branching."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.bitdeque("0000")
        assert "POP" in template
        assert "GOTO" in template

    def test_bad_table_rejected(self) -> None:
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.bitdeque("011")


class TestParameterizedRam0:
    """Input-by-substitution boolean generator for the no-input language RAM0.

    RAM0 prints a full state dump at halt; the generator's answer is the
    final ``z`` value, read from the dump's ``z: N`` line.
    """

    def run_ram0(self, prog: str) -> str:
        import re

        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.register_based.ram0 import run

        io = ScriptedIO()
        run(prog, io)
        m = re.search(r"^z: (\d+)", io.getvalue(), re.MULTILINE)
        assert m is not None
        return m.group(1)

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        from esolangs.tools.boolean import parameterized

        # Z resets absolutely, so the setter is the same at every position:
        # "Z A" for a one, "Z Z" for a zero, each exactly two commands.
        return parameterized.instantiate(
            tpl,
            bits,
            lambda _i, b: "Z A" if b else "Z Z",
        )

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0001", 2),  # AND
            ("0110", 2),  # XOR
            ("0111", 2),  # OR
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # majority
            ("1111111100000000", 4),  # top half
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.ram0(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_ram0(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.ram0(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_ram0(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.ram0("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_constant_table_is_a_leaf(self) -> None:
        """A constant table emits a single leaf with no branching."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.ram0("0000")
        assert "C" not in template
        assert "Z" in template

    def test_bad_table_rejected(self) -> None:
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.ram0("011")


class TestParameterizedMinskySwap:
    """Input-by-substitution boolean generator for the no-input language Minsky Swap.

    Minsky Swap prints the two registers at halt; the generator's answer is
    stored in ``reg[1]``, so it is the second number of the dump line.
    """

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
            if i == n - 1:  # LSB: length-4 block, no "~"
                return "+*+*" if b else "****"
            w = 2 ** (n - 1 - i)  # this bit's weight
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
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0001", 2),  # AND
            ("0110", 2),  # XOR
            ("0111", 2),  # OR
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # majority
            ("1111111100000000", 4),  # top half
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.minsky_swap(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_minsky_swap(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.minsky_swap(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_minsky_swap(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.minsky_swap("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_bad_table_rejected(self) -> None:
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.minsky_swap("011")


class TestParameterizedArrowQueue:
    """Input-by-substitution boolean generator for the no-input language ArrowQueue.

    ArrowQueue has no output, so the generator's answer is read from the
    termination convention: an instantiated program halts for a ``0`` table
    entry and loops forever for a ``1`` entry.  The run is bounded by
    state-cycle detection (the queue stays bounded on the sustaining rings),
    so the repeated-snapshot proof reports the ``1`` cases immediately.
    """

    def run_arrowqueue(self, prog: str) -> str:
        from esolangs.interpreters.grid_based.arrowqueue import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        return "0" if run_until_halt_or_cycle(_Machine(prog.splitlines())) else "1"

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        return _instantiate_arrowqueue(tpl, bits)

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0001", 2),  # AND
            ("0110", 2),  # XOR
            ("0111", 2),  # OR
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # majority
            ("1111111100000000", 4),  # top half
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input halts or loops per its table entry."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.arrowqueue(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_arrowqueue(self.instantiate(template, bits))
            assert got == table[combo], f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.arrowqueue(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_arrowqueue(self.instantiate(template, bits))
                assert got == table[combo], f"{table} inputs {bits}"

    def test_random_tables(self) -> None:
        """Seeded random tables through five inputs produce the right result."""
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
        """The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.arrowqueue("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_bad_table_rejected(self) -> None:
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.arrowqueue("011")


class TestParameterizedBfpda:
    """Input-by-substitution boolean generator for the no-input language BF-PDA."""

    def run_bfpda(self, prog: str) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.bf_pda import run

        io_ = ScriptedIO("")
        run(prog, io_)
        return io_.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Fill the template the way the example harness does."""
        from esolangs.tools.boolean.examples import _fill_bfpda

        return _fill_bfpda(tpl, bits)

    def test_both_bits_embed_at_the_same_width(self) -> None:
        """The setter is four characters whichever bit it carries."""
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
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0001", 2),  # AND
            ("0110", 2),  # XOR
            ("0111", 2),  # OR
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # majority
            ("1111111100000000", 4),  # top half
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.bfpda(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_bfpda(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.bfpda(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_bfpda(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.bfpda("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_program_structure(self) -> None:
        """Each input is embedded once (pre-loaded), not re-embedded per node."""
        import re

        from esolangs.tools.boolean import parameterized

        template = parameterized.bfpda("0110")
        assert template.count("{X0}") == 1
        assert template.count("{X1}") == 1
        assert "{C0}" not in template  # the marker is a constant, not a complement
        assert "{C1}" not in template
        assert len(re.findall(r"\{X\d+\}", template)) == 2  # n embeds

    def test_leaf_print_is_balanced(self) -> None:
        """A leaf pops the remaining bits, prints the answer, and pops it."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.bfpda("10")  # NOT: one-leaf prints 1
        assert "<@.>" in template
        assert "<.>" in template

    def test_bad_table_rejected(self) -> None:
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.bfpda("011")


class TestParameterizedHomeRow:
    """Input-by-substitution boolean generator for the no-input language Home Row."""

    def run_home_row(self, prog: str) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.home_row import run

        io_ = ScriptedIO("")
        run(prog, io_)
        return io_.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Fill the template the way the example harness does."""
        from esolangs.tools.boolean.examples import _fill_home_row

        return _fill_home_row(tpl, bits)

    def test_both_bits_embed_at_the_same_width(self) -> None:
        """The setter is two characters whichever bit it carries."""
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
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0001", 2),  # AND
            ("0110", 2),  # XOR
            ("0111", 2),  # OR
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # majority
            ("1111111100000000", 4),  # top half
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.home_row(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_home_row(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.home_row(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_home_row(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_five_inputs_sample(self) -> None:
        """A sample of dense five-input tables, past the removed n <= 2 cap."""
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
        """The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.home_row("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_each_input_embedded_once(self) -> None:
        import re

        from esolangs.tools.boolean import parameterized

        template = parameterized.home_row("0110")
        assert template.count("{X0}") == 1
        assert template.count("{X1}") == 1
        assert "{C0}" not in template
        assert "{C1}" not in template
        assert len(re.findall(r"\{X\d+\}", template)) == 2

    def test_bad_table_rejected(self) -> None:
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.home_row("011")


class TestParameterizedCOD:
    """Input-by-substitution boolean generator for the no-input language COD."""

    def run_cod(self, prog: str) -> str:
        from esolangs.interpreters.grid_based.cod import run
        from esolangs.interpreters.io import ScriptedIO

        io_ = ScriptedIO("")
        run(prog, io_, limit=500)
        return io_.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        from esolangs.tools.boolean import parameterized

        # each {Xi} sets the cod's value to the bit: ')' for one, space
        # for zero, read at the start of that input's '+' fork
        return parameterized.instantiate(
            tpl,
            bits,
            lambda _i, b: ")" if b else " ",
        )

    @pytest.mark.parametrize(
        "table",
        [
            "0000",  # constant zero
            "1111",  # constant one
            "0001",  # AND
            "0111",  # OR
            "0110",  # XOR
            "1001",  # XNOR
            "1110",  # NAND
            "1000",  # NOR
            "0100",  # A and not B
            "1101",  # A or not B
        ],
    )
    def test_truth_table(self, table: str) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.cod(table)
        for combo in range(4):
            bits = [(combo >> (2 - 1 - i)) & 1 for i in range(2)]
            got = self.run_cod(self.instantiate(template, bits))
            assert got == f"{table[combo]}", f"table {table} inputs {bits}"

    def test_all_two_input_tables(self) -> None:
        """Every one of the sixteen two-input tables produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(16):
            table = format(table_int, "04b")
            template = parameterized.cod(table)
            for combo in range(4):
                bits = [(combo >> (2 - 1 - i)) & 1 for i in range(2)]
                got = self.run_cod(self.instantiate(template, bits))
                assert got == f"{table[combo]}", f"table {table} inputs {bits}"

    def test_all_three_input_tables(self) -> None:
        """Every one of the 256 three-input tables produces the right result.

        Unlike the two-input template, whose forks always split directly
        into leaves, the three-input template has forks whose zero-branch
        is itself an internal node -- so a cod can rejoin an earlier
        junction's row after a deeper fork, and that junction's own reset
        gauntlet is what stops it from circulating forever instead of
        halting.  This test is the only thing that would have caught that
        class of bug (a "backflow" cod wandering junctions indefinitely),
        since it is invisible from reading the grid.
        """
        from esolangs.tools.boolean import parameterized

        for table_int in range(256):
            table = format(table_int, "08b")
            template = parameterized.cod(table)
            for combo in range(8):
                bits = [(combo >> (3 - 1 - i)) & 1 for i in range(3)]
                got = self.run_cod(self.instantiate(template, bits))
                assert got == f"{table[combo]}", f"table {table} inputs {bits}"

    def test_program_always_terminates_with_one_value(self) -> None:
        """Every run prints exactly one value and leaves no cod alive."""
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
            # one print, so one character: the answer, no separator
            assert len(io_.getvalue()) == 1

    def test_three_input_program_always_terminates_with_one_value(self) -> None:
        """Every three-input run prints exactly one value and halts."""
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
            # one print, so one character: the answer, no separator
            assert len(io_.getvalue()) == 1

    def test_template_is_input_independent(self) -> None:
        """The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.cod("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_each_input_is_embedded_once(self) -> None:
        """The routing embeds each input exactly once, not per leaf."""
        import re

        from esolangs.tools.boolean import parameterized

        template = parameterized.cod("0110")
        assert template.count("{X0}") == 1
        assert template.count("{X1}") == 1
        assert len(re.findall(r"\{X\d+\}", template)) == 2

    def test_bad_table_rejected(self) -> None:
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.cod("011")

    def test_constant_table_rejected(self) -> None:
        """n == 0 (a single-entry table, no inputs) is not supported."""
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="n >= 1"):
            parameterized.cod("0")

    def test_four_input_tables(self) -> None:
        """n == 4 (beyond the old n <= 3 cap) produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table in ("1111111011111110", "0110100110010110", "1000000000000000"):
            template = parameterized.cod(table)
            for combo in range(16):
                bits = [(combo >> (4 - 1 - i)) & 1 for i in range(4)]
                got = self.run_cod(self.instantiate(template, bits))
                assert got == f"{table[combo]}", f"table {table} inputs {bits}"

    @pytest.mark.parametrize("table", ["10", "01", "00", "11"])
    def test_one_input_truth_table(self, table: str) -> None:
        """n == 1 has no fork of its own: a bare entry into the leaf cascade."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.cod(table)
        assert "{X0}" in template
        assert "{X1}" not in template
        for x0 in range(2):
            got = self.run_cod(self.instantiate(template, [x0]))
            assert got == f"{table[x0]}", f"table {table} input {x0}"


class TestEvalBoolean:
    """Input-by-substitution boolean generator for the no-input language Eval."""

    def run_eval(self, prog: str) -> str:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.stack_based.eval import run

        io_ = ScriptedIO("")
        run(prog, io_)
        return io_.getvalue()

    def instantiate(self, tpl: str, bits: list[int]) -> str:
        """Fill the template the way the example harness does."""
        from esolangs.tools.boolean.examples import _fill_eval

        return _fill_eval(tpl, bits)

    def test_both_bits_embed_at_the_same_width(self) -> None:
        """The setter is two characters whichever bit it carries."""
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
            ("10", 1),  # NOT
            ("01", 1),  # identity
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0001", 2),  # AND
            ("0110", 2),  # XOR
            ("0111", 2),  # OR
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
            ("1000000000000000", 4),  # AND4
            ("1111111100000000", 4),  # top half
        ],
    )
    def test_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.eval(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_eval(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2, 3])
    def test_all_small_tables(self, n: int) -> None:
        """Every table up to three inputs produces the right result."""
        from esolangs.tools.boolean import parameterized

        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = parameterized.eval(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_eval(self.instantiate(template, bits))
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_template_is_input_independent(self) -> None:
        """The template has {Xi} placeholders, not hardcoded bits."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.eval("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_heap_tree_structure(self) -> None:
        """The template is a flat heap tree pushed BFS-order then reversed."""
        from esolangs.tools.boolean import parameterized

        template = parameterized.eval("0110")
        # inputs MSB-first, staged on the tree stack and moved by each `=`
        assert template.startswith("{X1}{X0}")
        assert template.endswith("*!")
        assert '"~=~?;!"' in template  # root node: one discard
        assert '"~=~?;;!"' in template  # BFS index 1: two discards
        assert template.count('"~=~?') == 3  # 2**2 - 1 internal nodes
        assert template.count('"0+.') + template.count('"0.') == 4  # leaves
        # leaves are the XOR table in heap order: 0 1 1 0
        assert template.endswith('"0.""0+.""0+.""0."*!')

    def test_scales_to_more_inputs(self) -> None:
        """The heap tree grows to any n (spot-checked at n = 6)."""
        from esolangs.tools.boolean import parameterized

        n = 6
        table = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(2**n))
        template = parameterized.eval(table)
        assert len(template) < 3000
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_eval(self.instantiate(template, bits))
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_bad_table_rejected(self) -> None:
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="power-of-two"):
            parameterized.eval("011")

    def test_non_binary_rejected(self) -> None:
        from esolangs.tools.boolean import parameterized

        with pytest.raises(ValueError, match="only '0' and '1'"):
            parameterized.eval("02")


def test_fills_embed_a_zero_and_a_one_at_equal_width() -> None:
    """No fill may spell a 0 shorter than a 1, or the length leaks the input.

    A program whose length depends on its inputs reveals them without being
    read: an earlier BIO embedding ran to 236/240/244/248 characters for the
    four ``n == 2`` instantiations, so ``len(program)`` alone recovered the
    bits.  Every ``_fill_*`` therefore pads the two sides to equal width, an
    invariant stated on :func:`~esolangs.tools.boolean.helpers.instantiate`
    and enforced here.

    The check is per-generator rather than global: fills legitimately differ
    from each other in width, but for one generator and one table every
    instantiation must come out the same length.
    """
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
