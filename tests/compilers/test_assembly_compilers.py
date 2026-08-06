"""Unit tests for the x86 assembly compilers."""

import importlib

import pytest

COMPILERS = [
    "esolangs.compilers.assembly.bfstack",
    "esolangs.compilers.assembly.home-row",
    "esolangs.compilers.assembly.jaune",
    "esolangs.compilers.assembly.unsquare",
]


@pytest.mark.parametrize("module", COMPILERS)
def test_compiler_produces_assembly(module: str) -> None:
    """Each compiler turns a program into x86 assembly."""
    mod = importlib.import_module(module)
    output = mod.comp("Hello")
    assert output.startswith("global _start")
    assert "Hello" not in output  # source text is compiled, not embedded


def test_suffolk_compiler() -> None:
    mod = importlib.import_module("esolangs.compilers.assembly.suffolk")
    output = mod.comp("Hi", 1)
    assert output.startswith("global _start")


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
        assert "dec esi" in mod.comp(">>.")
        assert "dec esi" in mod.comp(">>,")


class TestBFStackComp:
    def test_loop_generates_output_and_syscall(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        output = mod.comp("+[>].")
        assert "output:" in output
        assert "int 80h" in output
        assert ".T1:" in output  # loop label emitted

    def test_input_emits_input_label(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        assert "input:" in mod.comp(">,")

    def test_single_plus_minus(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        assert "inc byte" in mod.comp("+")
        assert "dec byte" in mod.comp("-")

    def test_counted_plus_minus(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        assert "add byte [ecx], 3" in mod.comp("+++")
        assert "sub byte [ecx], 3" in mod.comp("---")

    def test_counted_movement(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.bfstack")
        output = mod.comp(">>")
        assert "mov esi, 2" in output
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
    assert "int 80h" in mod.comp("ab")


class TestHomeRow:
    def test_arithmetic(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.home-row")
        assert "inc dword" in mod.comp("a")
        assert "add dword" in mod.comp("aa")
        assert "dec dword" in mod.comp("s")
        assert "sub dword" in mod.comp("ss")

    def test_movement(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.home-row")
        assert "down:" in mod.comp("d")
        assert "right:" in mod.comp("f")

    def test_output(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.home-row")
        assert "print:" in mod.comp("akk")

    def test_conditional_movement_and_output(self) -> None:
        """Commands preceded by j emit the count via eax."""
        mod = importlib.import_module("esolangs.compilers.assembly.home-row")
        assert "mov eax" in mod.comp("jak")

    def test_cell_shared_function(self) -> None:
        """Both movement commands together emit the shared cell function."""
        mod = importlib.import_module("esolangs.compilers.assembly.home-row")
        output = mod.comp("dkf")
        assert "cell:" in output
        assert "mov ebx, edi" in output

    def test_counted_movement(self) -> None:
        """Repeated movement commands emit a count and add to the position."""
        mod = importlib.import_module("esolangs.compilers.assembly.home-row")
        assert "add edi, eax" in mod.comp("ddk")
        assert "add esi, eax" in mod.comp("ffk")

    def test_loop_with_skip(self) -> None:
        """A loop combined with a conditional skip emits both labels."""
        mod = importlib.import_module("esolangs.compilers.assembly.home-row")
        output = mod.comp("jl")
        assert ".skip" in output
        assert ".top" in output
        assert ".bot" in output

    def test_conditionals_and_loop(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.home-row")
        assert ".skip" in mod.comp("j")
        assert ".top" in mod.comp("l")
        assert ".bot" in mod.comp("l")

    def test_halt(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.home-row")
        assert "int 80h" in mod.comp(";")


class TestJaune:
    def test_arithmetic(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert "inc dword" in mod.comp("1+")
        assert "dec dword" in mod.comp("1-")

    def test_subroutines(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert "call output" in mod.comp("^")
        assert "call input" in mod.comp("v")
        assert "call left" in mod.comp("<")

    def test_labels_and_jumps(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert ".label" in mod.comp("5:")
        assert "jne" in mod.comp("5?")
        assert "je " in mod.comp("5!")

    def test_subroutine_call(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert "call sub" in mod.comp("5@")

    def test_control_flow(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert "int 80h" in mod.comp(".")
        assert "ret" in mod.comp(";")
        assert "sub ecx" in mod.comp(">")

    def test_counted_commands(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert "mov esi, 2" in mod.comp("^^")
        assert "mov esi, 2" in mod.comp("&&")
        assert "add dword" in mod.comp("2+")
        assert "sub dword" in mod.comp("3-")

    def test_load_and_zero(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert "mov edi" in mod.comp("#")
        assert "mov dword [ecx], 0" in mod.comp("%")

    def test_switch_controls(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert ".switch" in mod.comp("v?")
        assert "call switch" in mod.comp("v@")

    def test_register_arithmetic(self) -> None:
        """A bare + or - operates on the register via eax."""
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert "add [ecx]" in mod.comp("+")
        assert "sub [ecx]" in mod.comp("-")

    def test_chained_arithmetic(self) -> None:
        """Consecutive digit+ sequences accumulate in count."""
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert "add dword" in mod.comp("1+2+3+")

    def test_switch_table_generation(self) -> None:
        """A label plus a conditional jump generates the switch table."""
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        output = mod.comp("5:v?")
        assert ".switch" in output
        assert "jmp .label" in output

    def test_multiply(self) -> None:
        """& multiplies via a subroutine when counted, else adds edi."""
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert "call mult" in mod.comp("&&")
        assert "add [ecx], edi" in mod.comp("&")

    def test_conditional_sequence(self) -> None:
        """Consecutive ?/! jumps are condensed in prep."""
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        output = mod.comp("1?2!")
        assert "jne" in output
        assert "je " in output

    def test_conditional_sequence_variants(self) -> None:
        """!-first and ?-only sequences take the other prep branches."""
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        assert "je " in mod.comp("1!2?")
        assert "jne" in mod.comp("1?2?")

    def test_multi_label_switch(self) -> None:
        """Multiple labels produce a richer .switch dispatch table."""
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        output = mod.comp("1:v2:v?")
        assert ".switch" in output
        assert "cmp eax" in output
        assert "je .lab" in output

    def test_subroutine_dispatch_table(self) -> None:
        """Multiple $ subroutines with @ calls generate a dispatch table."""
        mod = importlib.import_module("esolangs.compilers.assembly.jaune")
        output = mod.comp("5$v@7$v@")
        assert "switch:" in output
        assert "cmp eax" in output
        assert "je .sub" in output

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
        assert "add edi" in mod.comp("+")
        assert "sub edi" in mod.comp("-")
        assert "shl edi" in mod.comp("x")

    def test_loops(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.unsquare")
        output = mod.comp("O>I<")
        assert ".T1" in output
        assert ".B1" in output

    def test_zero_one_with_address(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.unsquare")
        assert "mov edi" in mod.comp("OA")
        assert "mov edi" in mod.comp("IA")

    def test_prep_optimization(self) -> None:
        """OA/I-A sequences with a following loop are optimized in prep."""
        mod = importlib.import_module("esolangs.compilers.assembly.unsquare")
        assert ".T1" in mod.comp("OAI>")
        assert "shl edi" in mod.comp("OAIx")

    def test_counted_register(self) -> None:
        """Repeated O/I/A commands emit a count and repeated-call loop."""
        mod = importlib.import_module("esolangs.compilers.assembly.unsquare")
        assert "mov esi, 2" in mod.comp("OO")
        assert "dec esi" in mod.comp("OO")
        assert "dec esi" in mod.comp("AA")

    def test_address_arithmetic(self) -> None:
        """OA followed by +/-/x adjusts the stored value in count."""
        mod = importlib.import_module("esolangs.compilers.assembly.unsquare")
        assert "mov edi" in mod.comp("OA+")
        assert "mov edi" in mod.comp("OA-")
        assert "mov edi" in mod.comp("OAx")


class TestSuffolkComp:
    def test_compiles_various_programs(self) -> None:
        mod = importlib.import_module("esolangs.compilers.assembly.suffolk")
        for program in ["!<.", "!!", ">", ">!<", "."]:
            output = mod.comp(program, 1)
            assert output.startswith("global _start")
            assert output


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
