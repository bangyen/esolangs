"""Unit tests for the RISC-V assembly compilers."""

import importlib

import pytest

COMPILERS = [
    "esolangs.compilers.assembly.bfstack",
    "esolangs.compilers.assembly.home-row",
    "esolangs.compilers.assembly.jaune",
    "esolangs.compilers.assembly.unsquare",
    "esolangs.compilers.assembly.excon",
    "esolangs.compilers.assembly.bfpda",
    "esolangs.compilers.assembly.RAM0",
]


@pytest.mark.parametrize("module", COMPILERS)
def test_compiler_produces_assembly(module: str) -> None:
    """Each compiler turns a program into RISC-V assembly."""
    mod = importlib.import_module(module)
    output = mod.comp("Hello")
    assert ".global _start" in output
    assert "Hello" not in output  # source text is compiled, not embedded


def test_suffolk_compiler() -> None:
    mod = importlib.import_module("esolangs.compilers.assembly.suffolk")
    output = mod.comp("Hi", 1)
    assert ".global _start" in output


class TestBFStackParse:
    def test_group_consecutive(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        assert mod.parse(">+++.") == [(">", 1), ("+", 3), (".", 1)]

    def test_plus_minus_cancel(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        assert mod.parse("++--") == []

    def test_push_pop_removed(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        assert mod.parse(">[+-]<") == [(">", 1), ("<", 1)]

    def test_zero_loop_optimization(self) -> None:
        """A loop that zeroes its cell compiles to a plain zero."""
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        assert mod.parse("++++[>++<-]") == [("0", 1)]

    def test_empty_program(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        assert mod.parse("") == []

    def test_empty_bracket_removed(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        assert mod.parse(">[]") == [(">", 1)]

    def test_unmatched_loop_returns_empty(self) -> None:
        """An unterminated bracket run makes parse bail out."""
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        assert mod.parse(">[[]") == []

    def test_counted_io(self) -> None:
        """Counted > commands loop the output/input calls."""
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        assert "addi s2, s2, -1" in mod.comp(">>.")
        assert "addi s2, s2, -1" in mod.comp(">>,")

    def test_zero_command(self) -> None:
        """A loop that zeroes its cell compiles to a plain zero."""
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        assert "sb   zero, 0(s1)" in mod.comp("++++[>++<-]")

    def test_counted_left(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        assert "addi s2, s2, -1" in mod.comp("<<")


class TestBFStackComp:
    def test_loop_generates_output_and_syscall(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        output = mod.comp("+[>].")
        assert "output:" in output
        assert "ecall" in output
        assert ".T1:" in output  # loop label emitted

    def test_input_emits_input_label(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        assert "input:" in mod.comp(">,")

    def test_single_plus_minus(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        assert "lbu  t0, 0(s1)" in mod.comp("+")
        assert "lbu  t0, 0(s1)" in mod.comp("-")

    def test_counted_plus_minus(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        assert "addi t0, t0, 3" in mod.comp("+++")
        assert "addi t0, t0, -3" in mod.comp("---")

    def test_counted_movement(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        output = mod.comp(">>")
        assert "li   s2, 2" in output
        assert "call right" in output

    def test_subroutines(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        output = mod.comp(">.<,>")
        for label in ["right:", "left:", "output:", "input:"]:
            assert label in output

    def test_loop_labels(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        output = mod.comp(">+[>]<")
        assert ".T1:" in output
        assert ".B1:" in output


def test_unsquare_emits_syscalls() -> None:
    mod = importlib.import_module("esolangs.compilers.assembly.unsquare")
    assert "ecall" in mod.comp("ab")


class TestHomeRow:
    def test_arithmetic(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.home-row")
        assert "lw   t0, 0(s1)" in mod.comp("a")
        assert "addi t0, t0, 2" in mod.comp("aa")
        assert "lw   t0, 0(s1)" in mod.comp("s")
        assert "addi t0, t0, -2" in mod.comp("ss")

    def test_movement(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.home-row")
        assert "down:" in mod.comp("d")
        assert "right:" in mod.comp("f")

    def test_output(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.home-row")
        assert "print:" in mod.comp("akk")

    def test_conditional_movement_and_output(self) -> None:
        """Commands preceded by j are a single (uncounted) step."""
        mod = importlib.import_module("esolangs.compilers.assembly.home-row")
        assert "call print" in mod.comp("jak")

    def test_cell_shared_function(self) -> None:
        """Both movement commands together emit the shared cell addressing."""
        mod = importlib.import_module("esolangs.compilers.assembly.home-row")
        output = mod.comp("dkf")
        assert "slli t1, t0, 4" in output

    def test_counted_movement(self) -> None:
        """Repeated movement commands emit a count and add to the position."""
        mod = importlib.import_module("esolangs.compilers.assembly.home-row")
        assert "add  s4, s4, t3" in mod.comp("ddk")
        assert "add  s5, s5, t3" in mod.comp("ffk")

    def test_loop_with_skip(self) -> None:
        """A loop combined with a conditional skip emits both labels."""
        mod = importlib.import_module("esolangs.compilers.assembly.home-row")
        output = mod.comp("jl")
        assert ".skip" in output
        assert ".top" in output
        assert ".bot" in output

    def test_odd_loop_count(self) -> None:
        """An odd loop count emits the bnez .top branch."""
        mod = importlib.import_module("esolangs.compilers.assembly.home-row")
        assert "bnez t0, .top" in mod.comp("jlajl")

    def test_conditionals_and_loop(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.home-row")
        assert ".skip" in mod.comp("j")
        assert ".top" in mod.comp("l")
        assert ".bot" in mod.comp("l")

    def test_halt(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.home-row")
        assert "ecall" in mod.comp(";")


class TestJaune:
    def test_arithmetic(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert "lw   t0, 0(s1)" in mod.comp("1+")
        assert "lw   t0, 0(s1)" in mod.comp("1-")

    def test_subroutines(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert "call output" in mod.comp("^")
        assert "call input" in mod.comp("v")
        assert "call left" in mod.comp("<")

    def test_labels_and_jumps(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert ".label" in mod.comp("5:")
        assert "bnez t0" in mod.comp("5?")
        assert "beqz t0" in mod.comp("5!")

    def test_subroutine_call(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert "call sub" in mod.comp("5@")

    def test_control_flow(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert "ecall" in mod.comp(".")
        assert "ret" in mod.comp(";")
        assert "sub  s1, s1" in mod.comp(">")

    def test_counted_commands(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert "li   s3, 2" in mod.comp("^^")
        assert "li   s3, 2" in mod.comp("&&")
        assert "lw   t0, 0(s1)" in mod.comp("2+")
        assert "lw   t0, 0(s1)" in mod.comp("3-")

    def test_load_and_zero(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert "lw   s2, 0(s1)" in mod.comp("#")
        assert "sw   zero, 0(s1)" in mod.comp("%")

    def test_switch_controls(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert ".switch" in mod.comp("v?")
        assert "call switch" in mod.comp("v@")

    def test_register_arithmetic(self) -> None:
        """A bare + or - operates on the register via s7."""
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert "add  t0, t0, s7" in mod.comp("+")
        assert "sub  t0, t0, s7" in mod.comp("-")

    def test_chained_arithmetic(self) -> None:
        """Consecutive digit+ sequences accumulate in count."""
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert "lw   t0, 0(s1)" in mod.comp("1+2+3+")

    def test_switch_table_generation(self) -> None:
        """A label plus a conditional jump generates the switch table."""
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        output = mod.comp("5:v?")
        assert ".switch" in output
        assert "j .label" in output

    def test_multiply(self) -> None:
        """& multiplies via a subroutine when counted, else adds edi."""
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert "call mult" in mod.comp("&&")
        assert "add  t0, t0, s2" in mod.comp("&")

    def test_conditional_sequence(self) -> None:
        """Consecutive ?/! jumps are condensed in prep."""
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        output = mod.comp("1?2!")
        assert "bnez t0" in output
        assert "beqz t0" in output

    def test_conditional_sequence_variants(self) -> None:
        """!-first and ?-only sequences take the other prep branches."""
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert "beqz t0" in mod.comp("1!2?")
        assert "bnez t0" in mod.comp("1?2?")

    def test_multi_label_switch(self) -> None:
        """Multiple labels produce a richer .switch dispatch table."""
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        output = mod.comp("1:v2:v?")
        assert ".switch" in output
        assert "beq  s7, t0" in output
        assert "beq  s7, t0" in output

    def test_subroutine_dispatch_table(self) -> None:
        """Multiple $ subroutines with @ calls generate a dispatch table."""
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        output = mod.comp("5$v@7$v@")
        assert "switch:" in output
        assert "beq  s7, t0" in output

    def test_subroutine_label(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert "sub" in mod.comp("5$")


class TestUnsquare:
    def test_register_commands(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.unsquare")
        assert "call zero" in mod.comp("O")
        assert "call one" in mod.comp("I")
        assert "call down" in mod.comp("A")
        assert "call up" in mod.comp("P")
        assert "call swap" in mod.comp("S")

    def test_io(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.unsquare")
        assert "call output" in mod.comp("o")
        assert "call input" in mod.comp("i")

    def test_arithmetic_and_shift(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.unsquare")
        assert "addi s2, s2" in mod.comp("+")
        assert "addi s2, s2, -2" in mod.comp("-")
        assert "slli s2, s2" in mod.comp("x")

    def test_loops(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.unsquare")
        output = mod.comp("O>I<")
        assert ".T1" in output
        assert ".B1" in output

    def test_zero_one_with_address(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.unsquare")
        assert "li   s2" in mod.comp("OA")
        assert "li   s2" in mod.comp("IA")

    def test_prep_optimization(self) -> None:
        """OA/I-A sequences with a following loop are optimized in prep."""
        mod = importlib.import_module("esolangs.compilers.assembly.unsquare")
        assert ".T1" in mod.comp("OAI>")
        assert "slli s2, s2" in mod.comp("OAIx")

    def test_counted_register(self) -> None:
        """Repeated O/I/A commands emit a count and repeated-call loop."""
        mod = importlib.import_module("esolangs.compilers.assembly.unsquare")
        assert "li   s3, 2" in mod.comp("OO")
        assert "addi s3, s3, -1" in mod.comp("OO")
        assert "addi s3, s3, -1" in mod.comp("AA")

    def test_address_arithmetic(self) -> None:
        """OA followed by +/-/x adjusts the stored value in count."""
        mod = importlib.import_module("esolangs.compilers.assembly.unsquare")
        assert "li   s2" in mod.comp("OA+")
        assert "li   s2" in mod.comp("OA-")
        assert "li   s2" in mod.comp("OAx")

    def test_nested_loop_scan(self) -> None:
        """Nested > in the OI-A scan increments the match counter."""
        mod = importlib.import_module("esolangs.compilers.assembly.unsquare")
        mod.comp("OA>>I<<<")  # must not crash


class TestSuffolkComp:
    def test_compiles_various_programs(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.suffolk")
        for program in ["!<.", "!!", ">", ">!<", "."]:
            output = mod.comp(program, 1)
            assert ".global _start" in output
            assert output

    def test_counted_left(self) -> None:
        """Repeated < commands emit a count via s5."""
        mod = importlib.import_module("esolangs.compilers.assembly.suffolk")
        assert "li   s5" in mod.comp("<<<<", 1)


class TestExcon:
    def test_reset_and_flip(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.excon")
        output = mod.comp(":^")
        assert "li   s1, 0" in output
        assert "li   s2, 7" in output
        assert "xor  s1, s1, t1" in output

    def test_output_emits_syscall(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.excon")
        assert "ecall" in mod.comp("!")


class TestBFPDA:
    def test_push_flip_pop(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.bfpda")
        output = mod.comp("<@>")
        assert "sb   zero, 0(s1)" in output  # push 0
        assert "xori t0, t0, 1" in output  # flip top
        assert "addi s1, s1, 1" in output  # pop

    def test_output_emits_syscall(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.bfpda")
        assert "ecall" in mod.comp(".")


class TestRAM0:
    def test_parse(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.RAM0")
        assert mod.parse("A A 5") == ["A", "A", "5"]
        assert mod.parse("Z A N C L S") == ["Z", "A", "N", "C", "L", "S"]

    def test_dispatch_labels(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.RAM0")
        output = mod.comp("A A")
        assert ".L0:" in output
        assert ".L1:" in output
        assert ".done:" in output

    def test_goto_jumps(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.RAM0")
        assert "j .L0" in mod.comp("1")
        assert "j .done" in mod.comp("9 A")

    def test_c_skip(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.RAM0")
        assert "beqz s1, .done" in mod.comp("C")


class TestCompilerFuzz:
    """Compilers must not crash on arbitrary (possibly malformed) input."""

    ALPHABET = "><+-.,[]{}_|#@$%^&*;:?!\\/'\"" + "asdfjkl;OIAPoi v" + "0123456789"

    @pytest.mark.parametrize(
        "module",
        [
            "esolangs.compilers.assembly.bfstack",
            "esolangs.compilers.assembly.home-row",
            "esolangs.compilers.assembly.jaune",
            "esolangs.compilers.assembly.unsquare",
            "esolangs.compilers.assembly.excon",
            "esolangs.compilers.assembly.bfpda",
            "esolangs.compilers.assembly.RAM0",
        ],
    )
    def test_random_input_does_not_crash(self, module: str) -> None:
        import random

        mod = importlib.import_module(module)
        random.seed(3)
        for _ in range(30):
            code = "".join(
                random.choice(self.ALPHABET) for _ in range(random.randint(1, 40))
            )
            mod.comp(code)  # must not raise

    def test_suffolk_random_input(self) -> None:
        import random

        mod = importlib.import_module("esolangs.compilers.assembly.suffolk")
        random.seed(3)
        for _ in range(30):
            code = "".join(
                random.choice(self.ALPHABET) for _ in range(random.randint(1, 40))
            )
            mod.comp(code, 1)
