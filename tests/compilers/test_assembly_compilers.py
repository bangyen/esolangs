"""Unit tests for the RISC-V assembly compilers."""

import importlib

import pytest

COMPILERS = [
    "esolangs.compilers.bfstack",
    "esolangs.compilers.home_row",
    "esolangs.compilers.jaune",
    "esolangs.compilers.unsquare",
    "esolangs.compilers.bf_pda",
    "esolangs.compilers.ram0",
    "esolangs.compilers.forth",
]


@pytest.mark.parametrize("module", COMPILERS)
def test_compiler_produces_assembly(module: str) -> None:
    """Each compiler turns a program into RISC-V assembly."""
    mod = importlib.import_module(module)
    output = mod.comp("Hello")
    assert ".global _start" in output
    assert "Hello" not in output  # source text is compiled, not embedded


def test_suffolk_compiler() -> None:
    mod = importlib.import_module("esolangs.compilers.suffolk")
    output = mod.comp("Hi", 1)
    assert ".global _start" in output


class TestBFStackParse:
    def test_group_consecutive(self) -> None:
        mod = importlib.import_module("esolangs.compilers.bfstack")
        assert mod.parse(">+++.") == [(">", 1), ("+", 3), (".", 1)]

    def test_plus_minus_cancel(self) -> None:
        mod = importlib.import_module("esolangs.compilers.bfstack")
        assert mod.parse("++--") == []

    def test_push_pop_removed(self) -> None:
        mod = importlib.import_module("esolangs.compilers.bfstack")
        assert mod.parse(">[+-]<") == [(">", 1), ("<", 1)]

    def test_zero_loop_optimization(self) -> None:
        """A loop that zeroes its cell compiles to a plain zero."""
        mod = importlib.import_module("esolangs.compilers.bfstack")
        assert mod.parse("++++[>++<-]") == [("0", 1)]

    def test_empty_program(self) -> None:
        mod = importlib.import_module("esolangs.compilers.bfstack")
        assert mod.parse("") == []

    def test_empty_bracket_removed(self) -> None:
        mod = importlib.import_module("esolangs.compilers.bfstack")
        assert mod.parse(">[]") == [(">", 1)]

    def test_unmatched_loop_returns_empty(self) -> None:
        """An unterminated bracket run makes parse bail out."""
        mod = importlib.import_module("esolangs.compilers.bfstack")
        assert mod.parse(">[[]") == []

    def test_dead_loop_scan_skips_non_bracket_commands(self) -> None:
        """The scan for a dead loop's end steps over ordinary commands.

        Matching ``[`` to ``]`` only counts brackets, so a body command --
        here ``.`` -- is neither an open nor a close and the scanner just
        keeps walking.  The whole skipped loop still disappears.
        """
        mod = importlib.import_module("esolangs.compilers.bfstack")
        assert mod.parse(">[.]") == [(">", 1)]

    def test_counted_io(self) -> None:
        """Counted > commands loop the output/input calls."""
        mod = importlib.import_module("esolangs.compilers.bfstack")
        assert "addi s2, s2, -1" in mod.comp(">>.")
        assert "addi s2, s2, -1" in mod.comp(">>,")

    def test_zero_command(self) -> None:
        """A loop that zeroes its cell compiles to a plain zero."""
        mod = importlib.import_module("esolangs.compilers.bfstack")
        assert "sb   zero, 0(s1)" in mod.comp("++++[>++<-]")

    def test_counted_left(self) -> None:
        mod = importlib.import_module("esolangs.compilers.bfstack")
        assert "addi s2, s2, -1" in mod.comp("<<")


class TestBFStackComp:
    def test_loop_generates_output_and_syscall(self) -> None:
        mod = importlib.import_module("esolangs.compilers.bfstack")
        output = mod.comp("+[>].")
        assert "output:" in output
        assert "ecall" in output
        assert ".T1:" in output  # loop label emitted

    def test_input_emits_input_label(self) -> None:
        mod = importlib.import_module("esolangs.compilers.bfstack")
        assert "input:" in mod.comp(">,")

    def test_single_plus_minus(self) -> None:
        mod = importlib.import_module("esolangs.compilers.bfstack")
        assert "lbu  t0, 0(s1)" in mod.comp("+")
        assert "lbu  t0, 0(s1)" in mod.comp("-")

    def test_counted_plus_minus(self) -> None:
        mod = importlib.import_module("esolangs.compilers.bfstack")
        assert "addi t0, t0, 3" in mod.comp("+++")
        assert "addi t0, t0, -3" in mod.comp("---")

    def test_counted_movement(self) -> None:
        mod = importlib.import_module("esolangs.compilers.bfstack")
        output = mod.comp(">>")
        assert "li   s2, 2" in output
        assert "call right" in output

    def test_subroutines(self) -> None:
        mod = importlib.import_module("esolangs.compilers.bfstack")
        output = mod.comp(">.<,>")
        for label in ["right:", "left:", "output:", "input:"]:
            assert label in output

    def test_loop_labels(self) -> None:
        mod = importlib.import_module("esolangs.compilers.bfstack")
        output = mod.comp(">+[>]<")
        assert ".T1:" in output
        assert ".B1:" in output


def test_unsquare_emits_syscalls() -> None:
    mod = importlib.import_module("esolangs.compilers.unsquare")
    assert "ecall" in mod.comp("ab")


class TestUnsquareLoopCollapse:
    """A zero-or-one ``OA`` before a *balanced* loop drops the loop.

    The loop can never run in that case, so ``prep`` removes it -- but only
    once the scan has matched the ``>`` with a ``<``.  An unbalanced ``>``
    is left exactly as written, since eliding it would change where the
    program's brackets pair up.
    """

    def test_a_balanced_loop_after_a_zero_is_dropped(self) -> None:
        mod = importlib.import_module("esolangs.compilers.unsquare")
        assert mod.prep("OA><") == "OA"
        assert mod.prep("OA>OA<") == "OA"

    def test_an_unbalanced_loop_is_left_alone(self) -> None:
        mod = importlib.import_module("esolangs.compilers.unsquare")
        assert mod.prep("OA>") == "OA>"
        assert mod.prep("IA>") == "IA>"


class TestUnsquareDoubledPairCollapse:
    """``(OO|II|PP)S+`` keeps the pair and drops the ``S``s after it.

    The replacement was once written ``"\\1"`` rather than ``r"\\1"``, which
    is the single byte 1 and not a backreference, so the whole match --
    including the pair the rewrite exists to keep -- was replaced by a
    character the dispatch loop then ignored.  A program was silently
    compiled as though its doubled pair were not there.
    """

    def test_the_pair_survives_the_rewrite(self) -> None:
        mod = importlib.import_module("esolangs.compilers.unsquare")
        assert mod.prep("OOS") == "OO"
        assert mod.prep("IIS") == "II"
        assert mod.prep("PPS") == "PP"
        assert mod.prep("OOSSS") == "OO"

    def test_no_control_byte_reaches_the_output(self) -> None:
        """The bug's signature was a stray ``\\x01`` in the prepared code."""
        mod = importlib.import_module("esolangs.compilers.unsquare")
        for program in ("OOS", "IIS", "PPS", "OOSo", "IISi"):
            assert "\x01" not in mod.prep(program), program

    def test_the_pair_still_compiles_to_instructions(self) -> None:
        """``OOS`` emits the body ``OO`` does, not an empty program."""
        mod = importlib.import_module("esolangs.compilers.unsquare")
        body = [
            line
            for line in mod.comp("OOS").splitlines()
            if line.startswith("\t") and "a7" not in line and "ecall" not in line
        ]
        assert body, "the doubled pair compiled to nothing"
        assert mod.comp("OOS") == mod.comp("OO")


class TestHomeRow:
    def test_arithmetic(self) -> None:
        mod = importlib.import_module("esolangs.compilers.home_row")
        assert "lw   t0, 0(s1)" in mod.comp("a")
        assert "addi t0, t0, 2" in mod.comp("aa")
        assert "lw   t0, 0(s1)" in mod.comp("s")
        assert "addi t0, t0, -2" in mod.comp("ss")

    def test_movement(self) -> None:
        mod = importlib.import_module("esolangs.compilers.home_row")
        assert "down:" in mod.comp("d")
        assert "right:" in mod.comp("f")

    def test_output(self) -> None:
        mod = importlib.import_module("esolangs.compilers.home_row")
        assert "print:" in mod.comp("akk")

    def test_conditional_movement_and_output(self) -> None:
        """Commands preceded by j are a single (uncounted) step."""
        mod = importlib.import_module("esolangs.compilers.home_row")
        assert "call print" in mod.comp("jak")

    def test_cell_shared_function(self) -> None:
        """Both movement commands together emit the shared cell addressing."""
        mod = importlib.import_module("esolangs.compilers.home_row")
        output = mod.comp("dkf")
        assert "slli t1, t0, 4" in output

    def test_counted_movement(self) -> None:
        """Repeated movement commands emit a count and add to the position."""
        mod = importlib.import_module("esolangs.compilers.home_row")
        assert "add  s4, s4, t3" in mod.comp("ddk")
        assert "add  s5, s5, t3" in mod.comp("ffk")

    def test_loop_with_skip(self) -> None:
        """A loop combined with a conditional skip emits both labels."""
        mod = importlib.import_module("esolangs.compilers.home_row")
        output = mod.comp("jl")
        assert ".skip" in output
        assert ".top" in output
        assert ".bot" in output

    def test_odd_loop_count(self) -> None:
        """An odd loop count emits the bnez .top branch."""
        mod = importlib.import_module("esolangs.compilers.home_row")
        assert "bnez t0, .top" in mod.comp("jlajl")

    def test_conditionals_and_loop(self) -> None:
        mod = importlib.import_module("esolangs.compilers.home_row")
        assert ".skip" in mod.comp("j")
        assert ".top" in mod.comp("l")
        assert ".bot" in mod.comp("l")

    def test_halt(self) -> None:
        mod = importlib.import_module("esolangs.compilers.home_row")
        assert "ecall" in mod.comp(";")


class TestJaune:
    def test_repeated_markers_collapse(self) -> None:
        """A run of one marker compiles as a single one.

        The dedup wrote its backreference as ``"\\1"`` in both the pattern
        and the replacement, which is the byte 1 rather than a group
        reference, so the pattern matched nothing and the rewrite never
        fired.  It was harmless -- an earlier pass already collapses these,
        which is why no output changed when it was corrected -- but a rule
        that cannot match is not a rule, and this pins that it now can.
        """
        mod = importlib.import_module("esolangs.compilers.jaune")
        for marker in "#.;%":
            assert mod.comp(marker * 3) == mod.comp(marker), marker

    def test_arithmetic(self) -> None:
        mod = importlib.import_module("esolangs.compilers.jaune")
        assert "lw   t0, 0(s1)" in mod.comp("1+")
        assert "lw   t0, 0(s1)" in mod.comp("1-")

    def test_subroutines(self) -> None:
        mod = importlib.import_module("esolangs.compilers.jaune")
        assert "call output" in mod.comp("^")
        assert "call input" in mod.comp("v")
        assert "call left" in mod.comp("<")

    def test_labels_and_jumps(self) -> None:
        mod = importlib.import_module("esolangs.compilers.jaune")
        assert ".label" in mod.comp("5:")
        assert "bnez t0" in mod.comp("5?")
        assert "beqz t0" in mod.comp("5!")

    def test_subroutine_call(self) -> None:
        mod = importlib.import_module("esolangs.compilers.jaune")
        assert "call sub" in mod.comp("5@")

    def test_control_flow(self) -> None:
        mod = importlib.import_module("esolangs.compilers.jaune")
        assert "ecall" in mod.comp(".")
        assert "ret" in mod.comp(";")
        assert "sub  s1, s1" in mod.comp(">")

    def test_counted_commands(self) -> None:
        mod = importlib.import_module("esolangs.compilers.jaune")
        assert "li   s3, 2" in mod.comp("^^")
        assert "li   s3, 2" in mod.comp("&&")
        assert "lw   t0, 0(s1)" in mod.comp("2+")
        assert "lw   t0, 0(s1)" in mod.comp("3-")

    def test_load_and_zero(self) -> None:
        mod = importlib.import_module("esolangs.compilers.jaune")
        assert "lw   s2, 0(s1)" in mod.comp("#")
        assert "sw   zero, 0(s1)" in mod.comp("%")

    def test_switch_controls(self) -> None:
        mod = importlib.import_module("esolangs.compilers.jaune")
        assert ".switch" in mod.comp("v?")
        assert "call switch" in mod.comp("v@")

    def test_register_arithmetic(self) -> None:
        """A bare + or - operates on the register via s7."""
        mod = importlib.import_module("esolangs.compilers.jaune")
        assert "add  t0, t0, s7" in mod.comp("+")
        assert "sub  t0, t0, s7" in mod.comp("-")

    def test_chained_arithmetic(self) -> None:
        """Consecutive digit+ sequences accumulate in count."""
        mod = importlib.import_module("esolangs.compilers.jaune")
        assert "lw   t0, 0(s1)" in mod.comp("1+2+3+")

    def test_switch_table_generation(self) -> None:
        """A label plus a conditional jump generates the switch table."""
        mod = importlib.import_module("esolangs.compilers.jaune")
        output = mod.comp("5:v?")
        assert ".switch" in output
        assert "j .label" in output

    def test_multiply(self) -> None:
        """& multiplies via a subroutine when counted, else adds edi."""
        mod = importlib.import_module("esolangs.compilers.jaune")
        assert "call mult" in mod.comp("&&")
        assert "add  t0, t0, s2" in mod.comp("&")

    def test_conditional_sequence(self) -> None:
        """Consecutive ?/! jumps are condensed in prep."""
        mod = importlib.import_module("esolangs.compilers.jaune")
        output = mod.comp("1?2!")
        assert "bnez t0" in output
        assert "beqz t0" in output

    def test_conditional_sequence_variants(self) -> None:
        """!-first and ?-only sequences take the other prep branches."""
        mod = importlib.import_module("esolangs.compilers.jaune")
        assert "beqz t0" in mod.comp("1!2?")
        assert "bnez t0" in mod.comp("1?2?")

    def test_multi_label_switch(self) -> None:
        """Multiple labels produce a richer .switch dispatch table."""
        mod = importlib.import_module("esolangs.compilers.jaune")
        output = mod.comp("1:v2:v?")
        assert ".switch" in output
        assert "beq  s7, t0" in output
        assert "beq  s7, t0" in output

    def test_subroutine_dispatch_table(self) -> None:
        """Multiple $ subroutines with @ calls generate a dispatch table."""
        mod = importlib.import_module("esolangs.compilers.jaune")
        output = mod.comp("5$v@7$v@")
        assert "switch:" in output
        assert "beq  s7, t0" in output

    def test_subroutine_label(self) -> None:
        mod = importlib.import_module("esolangs.compilers.jaune")
        assert "sub" in mod.comp("5$")


class TestUnsquare:
    def test_register_commands(self) -> None:
        mod = importlib.import_module("esolangs.compilers.unsquare")
        assert "call zero" in mod.comp("O")
        assert "call one" in mod.comp("I")
        assert "call down" in mod.comp("A")
        assert "call up" in mod.comp("P")
        assert "call swap" in mod.comp("S")

    def test_io(self) -> None:
        mod = importlib.import_module("esolangs.compilers.unsquare")
        assert "call output" in mod.comp("o")
        assert "call input" in mod.comp("i")

    def test_arithmetic_and_shift(self) -> None:
        mod = importlib.import_module("esolangs.compilers.unsquare")
        assert "addi s2, s2" in mod.comp("+")
        assert "addi s2, s2, -2" in mod.comp("-")
        assert "slli s2, s2" in mod.comp("x")

    def test_loops(self) -> None:
        mod = importlib.import_module("esolangs.compilers.unsquare")
        output = mod.comp("O>I<")
        assert ".T1" in output
        assert ".B1" in output

    def test_zero_one_with_address(self) -> None:
        mod = importlib.import_module("esolangs.compilers.unsquare")
        assert "li   s2" in mod.comp("OA")
        assert "li   s2" in mod.comp("IA")

    def test_prep_optimization(self) -> None:
        """OA/I-A sequences with a following loop are optimized in prep."""
        mod = importlib.import_module("esolangs.compilers.unsquare")
        assert ".T1" in mod.comp("OAI>")
        assert "slli s2, s2" in mod.comp("OAIx")

    def test_counted_register(self) -> None:
        """Repeated O/I/A commands emit a count and repeated-call loop."""
        mod = importlib.import_module("esolangs.compilers.unsquare")
        assert "li   s3, 2" in mod.comp("OO")
        assert "addi s3, s3, -1" in mod.comp("OO")
        assert "addi s3, s3, -1" in mod.comp("AA")

    def test_address_arithmetic(self) -> None:
        """OA followed by +/-/x adjusts the stored value in count."""
        mod = importlib.import_module("esolangs.compilers.unsquare")
        assert "li   s2" in mod.comp("OA+")
        assert "li   s2" in mod.comp("OA-")
        assert "li   s2" in mod.comp("OAx")

    def test_nested_loop_scan(self) -> None:
        """Nested > in the OI-A scan increments the match counter."""
        mod = importlib.import_module("esolangs.compilers.unsquare")
        mod.comp("OA>>I<<<")  # must not crash


class TestSuffolkComp:
    def test_compiles_various_programs(self) -> None:
        mod = importlib.import_module("esolangs.compilers.suffolk")
        for program in ["!<.", "!!", ">", ">!<", "."]:
            output = mod.comp(program, 1)
            assert ".global _start" in output
            assert output

    def test_counted_left(self) -> None:
        """Repeated < commands emit a count via s5."""
        mod = importlib.import_module("esolangs.compilers.suffolk")
        assert "li   s5" in mod.comp("<<<<", 1)


class TestBFPDA:
    def test_push_flip_pop(self) -> None:
        mod = importlib.import_module("esolangs.compilers.bf_pda")
        output = mod.comp("<@>")
        assert "sb   zero, 0(s1)" in output  # push 0
        assert "xori t0, t0, 1" in output  # flip top
        assert "addi s1, s1, 1" in output  # pop

    def test_output_emits_syscall(self) -> None:
        mod = importlib.import_module("esolangs.compilers.bf_pda")
        assert "ecall" in mod.comp(".")


class TestAddSubJump:
    def test_compiles_to_assembly(self) -> None:
        mod = importlib.import_module("esolangs.compilers.addsubjump")
        output = mod.comp("-1 4 -8 -7 65")
        assert ".global _start" in output
        assert "read_cell:" in output
        assert "write_cell:" in output

    def test_initial_memory_embedded_as_dwords(self) -> None:
        mod = importlib.import_module("esolangs.compilers.addsubjump")
        output = mod.comp("-1 4 -8 -7 65")
        assert ".dword" in output
        assert "65" in output

    def test_comments_and_blank_lines_ignored(self) -> None:
        mod = importlib.import_module("esolangs.compilers.addsubjump")
        base = mod.comp("-1 4 -8 -7 65")
        commented = mod.comp("# a comment\n\n-1 4 -8 -7 65 # trailing\n")
        assert base == commented

    def test_empty_program(self) -> None:
        mod = importlib.import_module("esolangs.compilers.addsubjump")
        output = mod.comp("")
        assert ".global _start" in output

    def test_malformed_token_raises(self) -> None:
        mod = importlib.import_module("esolangs.compilers.addsubjump")
        with pytest.raises(ValueError, match="malformed memory token"):
            mod.comp("12 -6 x -7")

    def test_random_int_input_does_not_crash(self) -> None:
        import random

        mod = importlib.import_module("esolangs.compilers.addsubjump")
        random.seed(3)
        for _ in range(30):
            n = random.randint(1, 40)
            code = " ".join(str(random.randint(-9, 200)) for _ in range(n))
            mod.comp(code)  # must not raise

    def test_program_at_buffer_size_is_not_padded(self) -> None:
        """A program already filling the cell buffer skips the zero padding.

        Short programs are padded out to the fixed ``_CELLS`` buffer (65536);
        one that is already that long takes the other side of the guard, and
        the halt boundary ``s3`` still reports its own length.
        """
        mod = importlib.import_module("esolangs.compilers.addsubjump")
        output = mod.comp(" ".join(["0"] * 65536))
        assert "li   s3, 65536" in output

    def test_program_over_buffer_size_keeps_its_length(self) -> None:
        """Past the buffer the boundary follows the program, not ``_CELLS``."""
        mod = importlib.import_module("esolangs.compilers.addsubjump")
        output = mod.comp(" ".join(["0"] * 65600))
        assert "li   s3, 65600" in output


class TestSBleq:
    def test_compiles_to_assembly(self) -> None:
        mod = importlib.import_module("esolangs.compilers.sbleq")
        output = mod.comp("0 0 2 -1")
        assert ".global _start" in output
        assert "read_cell:" in output
        assert "write_cell:" in output

    def test_initial_memory_embedded_as_dwords(self) -> None:
        mod = importlib.import_module("esolangs.compilers.sbleq")
        output = mod.comp("-3 6 3 0 0 7 65 9")
        assert ".dword" in output
        assert "65" in output

    def test_comments_and_blank_lines_ignored(self) -> None:
        mod = importlib.import_module("esolangs.compilers.sbleq")
        base = mod.comp("0 0 2 -1")
        commented = mod.comp("# a comment\n\n0 0 2 -1 # trailing\n")
        assert base == commented

    def test_empty_program(self) -> None:
        mod = importlib.import_module("esolangs.compilers.sbleq")
        output = mod.comp("")
        assert ".global _start" in output

    def test_malformed_token_raises(self) -> None:
        mod = importlib.import_module("esolangs.compilers.sbleq")
        with pytest.raises(ValueError, match="malformed memory token"):
            mod.comp("0 0 x")

    def test_random_int_input_does_not_crash(self) -> None:
        import random

        mod = importlib.import_module("esolangs.compilers.sbleq")
        random.seed(3)
        for _ in range(30):
            n = random.randint(1, 40)
            code = " ".join(str(random.randint(-3, 200)) for _ in range(n))
            mod.comp(code)  # must not raise

    def test_program_at_buffer_size_is_not_padded(self) -> None:
        """A program already filling the cell buffer skips the zero padding."""
        mod = importlib.import_module("esolangs.compilers.sbleq")
        output = mod.comp(" ".join(["0"] * 65536))
        assert "li   s3, 65536" in output


class TestDecleq:
    def test_compiles_to_assembly(self) -> None:
        mod = importlib.import_module("esolangs.compilers.decleq")
        output = mod.comp("10 10 99")
        assert ".global _start" in output
        assert "read_cell:" in output
        assert "write_cell:" in output

    def test_initial_memory_embedded_as_dwords(self) -> None:
        mod = importlib.import_module("esolangs.compilers.decleq")
        output = mod.comp("-2 10 0 0 0 999 0 0 0 0 65")
        assert ".dword" in output
        assert "65" in output

    def test_comments_and_blank_lines_ignored(self) -> None:
        mod = importlib.import_module("esolangs.compilers.decleq")
        base = mod.comp("10 10 99")
        commented = mod.comp("# a comment\n\n10 10 99 # trailing\n")
        assert base == commented

    def test_empty_program(self) -> None:
        mod = importlib.import_module("esolangs.compilers.decleq")
        output = mod.comp("")
        assert ".global _start" in output

    def test_malformed_token_raises(self) -> None:
        mod = importlib.import_module("esolangs.compilers.decleq")
        with pytest.raises(ValueError, match="malformed memory token"):
            mod.comp("10 10 x")

    def test_random_int_input_does_not_crash(self) -> None:
        import random

        mod = importlib.import_module("esolangs.compilers.decleq")
        random.seed(3)
        for _ in range(30):
            n = random.randint(1, 40)
            code = " ".join(str(random.randint(-2, 200)) for _ in range(n))
            mod.comp(code)  # must not raise

    def test_program_at_buffer_size_is_not_padded(self) -> None:
        """A program already filling the cell buffer skips the zero padding."""
        mod = importlib.import_module("esolangs.compilers.decleq")
        output = mod.comp(" ".join(["0"] * 65536))
        assert "li   s3, 65536" in output


class TestCollatzMultiverse:
    def test_compiles_to_assembly(self) -> None:
        mod = importlib.import_module("esolangs.compilers.collatz_multiverse")
        output = mod.comp("x = negativeOne x + negativeOne, DO PRINT.")
        assert ".global _start" in output
        assert "dispatch:" in output
        assert "collatz_odd:" in output

    def test_parse(self) -> None:
        mod = importlib.import_module("esolangs.compilers.collatz_multiverse")
        assert mod.parse("x = y x + z, DO PRINT.") == [
            ("x", None, "y", None, "z", None, "DO")
        ]
        assert mod.parse("arr[i] = y x + z, NOT PRINT.") == [
            ("arr", "i", "y", None, "z", None, "NOT")
        ]

    def test_blank_lines_ignored(self) -> None:
        mod = importlib.import_module("esolangs.compilers.collatz_multiverse")
        base = mod.comp("x = y x + z, DO PRINT.")
        spaced = mod.comp("\n\nx = y x + z, DO PRINT.\n\n")
        assert base == spaced

    def test_array_gets_its_own_data_block(self) -> None:
        mod = importlib.import_module("esolangs.compilers.collatz_multiverse")
        output = mod.comp("arr[i] = negativeOne x + i, DO PRINT.")
        assert "array_index:" in output
        assert "arr0:" in output

    def test_repeated_array_and_index_allocated_once(self) -> None:
        """A name and index seen again reuse their slots rather than re-adding.

        The allocator walks all three operands of every line; naming the same
        array and the same index in each takes the already-registered side of
        both checks, so ``arr`` gets one data block and ``i`` one scalar.
        """
        mod = importlib.import_module("esolangs.compilers.collatz_multiverse")
        output = mod.comp("arr[i] = arr[i] x + arr[i], DO PRINT.")
        assert output.count("arr0:") == 1
        assert "arr1:" not in output

    def test_line_number_dispatch_table(self) -> None:
        mod = importlib.import_module("esolangs.compilers.collatz_multiverse")
        output = mod.comp(
            "\n".join(
                [
                    "lineNumber = negativeOne x + negativeOne, NOT PRINT.",
                    "x = negativeOne x + one, DO PRINT.",
                ]
            )
        )
        assert "beq  s2, t0, .L1" in output
        assert "beq  s2, t0, .L2" in output

    def test_empty_program(self) -> None:
        mod = importlib.import_module("esolangs.compilers.collatz_multiverse")
        output = mod.comp("")
        assert ".global _start" in output

    def test_malformed_line_raises(self) -> None:
        mod = importlib.import_module("esolangs.compilers.collatz_multiverse")
        with pytest.raises(ValueError, match="malformed line"):
            mod.comp("hello world")

    def test_random_program_does_not_crash(self) -> None:
        import contextlib
        import random

        mod = importlib.import_module("esolangs.compilers.collatz_multiverse")
        names = ["a", "b", "c", "arr", "negativeOne", "input", "lineNumber", "zero"]
        random.seed(3)
        for _ in range(30):
            lines = []
            for _ in range(random.randint(1, 8)):
                v1, v2, v3 = (random.choice(names) for _ in range(3))
                do = random.choice(["DO", "NOT"])
                lines.append(f"{v1} = {v2} x + {v3}, {do} PRINT.")
            # input as a target is documented as malformed; everything else
            # must compile without raising.
            with contextlib.suppress(ValueError):
                mod.comp("\n".join(lines))


class TestRAM0:
    def test_parse(self) -> None:
        mod = importlib.import_module("esolangs.compilers.ram0")
        assert mod.parse("A A 5") == ["A", "A", "5"]
        assert mod.parse("Z A N C L S") == ["Z", "A", "N", "C", "L", "S"]

    def test_dispatch_labels(self) -> None:
        mod = importlib.import_module("esolangs.compilers.ram0")
        output = mod.comp("A A")
        assert ".L0:" in output
        assert ".L1:" in output
        assert ".done:" in output

    def test_goto_jumps(self) -> None:
        mod = importlib.import_module("esolangs.compilers.ram0")
        assert "j .L0" in mod.comp("1")
        assert "j .done" in mod.comp("9 A")

    def test_c_skip(self) -> None:
        mod = importlib.import_module("esolangs.compilers.ram0")
        assert "beqz s1, .done" in mod.comp("C")

    def test_znls_emit(self) -> None:
        """Each RAM0 command maps to its RISC-V instruction sequence."""
        mod = importlib.import_module("esolangs.compilers.ram0")
        output = mod.comp("Z A N L S")
        assert "li   s1, 0" in output  # Z
        assert "mv   s2, s1" in output  # N
        assert "lw   s1, 0(t0)" in output  # L
        assert "sw   s1, 0(t0)" in output  # S


class TestForth:
    def test_digits_and_letters(self) -> None:
        mod = importlib.import_module("esolangs.compilers.forth")
        assert "li   t0, 6" in mod.comp("6")
        assert "li   t0, 10" in mod.comp("A")  # A..F push 10..15

    def test_stack_ops(self) -> None:
        mod = importlib.import_module("esolangs.compilers.forth")
        assert "call dup" in mod.comp(":")
        assert "call complement" in mod.comp("~")
        assert "call print_top" in mod.comp(".")
        assert "call read_line" in mod.comp(",")
        assert "call reverse" in mod.comp("o")
        assert "call rotate3" in mod.comp("c")

    def test_arithmetic_ops(self) -> None:
        mod = importlib.import_module("esolangs.compilers.forth")
        assert "call op_add" in mod.comp("+")
        assert "call op_sub" in mod.comp("-")
        assert "call op_mul" in mod.comp("*")
        assert "call op_div" in mod.comp("/")
        assert "call op_mod" in mod.comp("%")
        assert "call op_swap" in mod.comp("v")

    def test_branch_and_loop_bodies_become_subroutines(self) -> None:
        mod = importlib.import_module("esolangs.compilers.forth")
        branch = mod.comp("1(2.)")
        assert ".scope1:" in branch
        assert "call peek" in branch
        assert "call .scope1" in branch

        loop = mod.comp("1[2.]")
        assert ".scope1:" in loop
        assert "j    .scope2" in loop or ".scope2:" in loop

    def test_store_emits_table_store_and_call_emits_table_call(self) -> None:
        mod = importlib.import_module("esolangs.compilers.forth")
        output = mod.comp("1{2.}1;")
        assert "call table_store" in output
        assert "call table_call" in output

    def test_nested_brackets_get_their_own_matching(self) -> None:
        """A ( inside a [...] body does not close the outer [."""
        mod = importlib.import_module("esolangs.compilers.forth")
        output = mod.comp("1[1(2.)]")
        assert output.count(".scope") >= 4  # loop body, branch body, + labels

    def test_unmatched_bracket_compiles_without_crashing(self) -> None:
        mod = importlib.import_module("esolangs.compilers.forth")
        output = mod.comp("(5")
        assert ".global _start" in output

    def test_empty_program(self) -> None:
        mod = importlib.import_module("esolangs.compilers.forth")
        output = mod.comp("")
        assert ".global _start" in output

    def test_unknown_characters_are_ignored(self) -> None:
        mod = importlib.import_module("esolangs.compilers.forth")
        assert mod.comp("a5.b") == mod.comp("5.")

    def test_software_multiply_and_divide_no_hardware_m_extension(self) -> None:
        """rv64i has no M extension, so mul/div/mod must be software."""
        mod = importlib.import_module("esolangs.compilers.forth")
        output = mod.comp("23+45-*9/8%")
        assert "\tmul" not in output.replace("mul32", "").replace("op_mul", "")
        assert "\tdiv" not in output
        assert "\trem" not in output
        assert "mul32:" in output
        assert "divmod32:" in output

    def test_call_sites_that_make_further_calls_save_ra(self) -> None:
        """Every subroutine containing a nested call must preserve ra, or
        the nested call's own return overwrites the caller's return
        address (this was the compiler's original bug: table_call,
        op_add, and the generated .scopeN bodies all call further
        subroutines and must save/restore ra around that)."""
        mod = importlib.import_module("esolangs.compilers.forth")
        output = mod.comp("1{2.}1;")
        assert "sd   ra, 0(sp)" in output
        assert "ld   ra, 0(sp)" in output


class TestCompilerFuzz:
    """Compilers must not crash on arbitrary (possibly malformed) input."""

    ALPHABET = "><+-.,[]{}_|#@$%^&*;:?!\\/'\"" + "asdfjkl;OIAPoi v" + "0123456789"

    @pytest.mark.parametrize(
        "module",
        [
            "esolangs.compilers.bfstack",
            "esolangs.compilers.home_row",
            "esolangs.compilers.jaune",
            "esolangs.compilers.unsquare",
            "esolangs.compilers.bf_pda",
            "esolangs.compilers.ram0",
            "esolangs.compilers.forth",
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

        mod = importlib.import_module("esolangs.compilers.suffolk")
        random.seed(3)
        for _ in range(30):
            code = "".join(
                random.choice(self.ALPHABET) for _ in range(random.randint(1, 40))
            )
            mod.comp(code, 1)


class TestForbinCompiler:
    """Forbin lowers to a call graph over a runtime frame chain.

    Forbin is excluded from the ``COMPILERS`` sweep above because that
    sweep compiles the literal text ``"Hello"``, which is not a Forbin
    program (every program is a set of brace-delimited functions).
    """

    @staticmethod
    def comp(code: str) -> str:
        mod = importlib.import_module("esolangs.compilers.forbin")
        return mod.comp(code)

    def test_produces_assembly(self) -> None:
        out = self.comp("main { out 0,1,0,0,1,0,0,0; }")
        assert ".global _start" in out

    def test_relaxation_is_disabled(self) -> None:
        """``la`` must not relax to a gp-relative access.

        Nothing initializes ``gp`` under ``-nostdlib``, so a relaxed
        ``la`` yields a garbage arena pointer and every frame lands
        outside mapped memory.
        """
        assert ".option norelax" in self.comp("main { }")

    def test_no_main_is_rejected(self) -> None:
        """A program without ``main`` is rejected, as the interpreter does."""
        with pytest.raises(ValueError, match="no main function"):
            self.comp("helper { out 0,0,0,0,0,0,0,0; }")

    def test_malformed_source_is_rejected(self) -> None:
        """Malformed syntax raises, sharing the interpreter's parser."""
        with pytest.raises(ValueError, match="unterminated block"):
            self.comp("main {")

    def test_each_function_gets_its_own_epilogue(self) -> None:
        """Two functions must not share one ``.ret`` label.

        A shared label is a duplicate-symbol assembler error rather than a
        wrong answer, so it needs its own guard.
        """
        out = self.comp("one { return 1; }\nmain { a = (one 0); }")
        assert ".ret0:" in out
        assert ".ret1:" in out

    def test_recursive_function_compiles(self) -> None:
        """A self-call reaches its own body index without recursing forever."""
        out = self.comp("again { again 0; }\nmain { again 0; }")
        assert ".global _start" in out

    def test_nested_definitions_emit_a_table(self) -> None:
        """A function with nested definitions carries a lookup table.

        The table is what makes a caller's nested definition visible to a
        callee, which is how Forbin's dynamic scoping resolves names.
        """
        out = self.comp("main { helper { out 0,0,0,0,0,0,0,0; } helper 0; }")
        assert ".tbl0:" in out

    def test_function_without_nested_has_no_table(self) -> None:
        out = self.comp("main { out 0,0,0,0,0,0,0,0; }")
        assert ".tbl" not in out

    def test_range_loop_emits_a_counter_loop(self) -> None:
        """A range loop compares its counter against its limit each pass."""
        out = self.comp("main { for i:0..1 { out 0,0,0,0,0,0,0,i; } }")
        assert "bgt  s4, s5" in out

    def test_range_bounds_are_checked_for_bitness(self) -> None:
        """A non-bit bound halts, as the interpreter's _bound does."""
        out = self.comp("main { for i:0..1 { } }")
        assert out.count("bgtu a0, t0, .abort") >= 2

    def test_wildcard_expands_at_compile_time(self) -> None:
        """A wildcard's two fillings are unrolled, not looped at runtime.

        The count is fixed at compile time, so each row is emitted; the
        body therefore appears once per filling.
        """
        one = self.comp("main { for v:(0) { out 0,0,0,0,0,0,0,v; } }")
        two = self.comp("main { for v:(*) { out 0,0,0,0,0,0,0,v; } }")
        assert two.count("call .dispatch") > one.count("call .dispatch")

    def test_wildcard_pair_expands_to_four_rows(self) -> None:
        """``(*,*)`` unrolls to four rows, so the body is emitted four times.

        The fifth dispatch is the entry's call to ``main`` itself.
        """
        out = self.comp("main { for (a,b):((*,*)) { out 0,0,0,0,0,0,a,b; } }")
        assert out.count("call .dispatch") == 4 + 1

    def test_broadcast_assignment_reevaluates_per_target(self) -> None:
        """``a,b = (in 0)`` reads twice, matching _exec_stmt.

        The interpreter calls _eval inside its target loop, so this is two
        reads rather than one value bound twice -- the behaviour the
        boolean generator's eight-name load depends on.
        """
        out = self.comp("main { a,b = (in 0); }")
        assert out.count("li   a0, -2") == 2

    def test_discard_target_consumes_no_read(self) -> None:
        """``_`` is skipped entirely, so it evaluates nothing."""
        out = self.comp("main { _,b = (in 0); }")
        assert out.count("li   a0, -2") == 1

    def test_paired_assignment_pairs_positionally(self) -> None:
        out = self.comp("main { a,b = 1,0; }")
        assert ".global _start" in out

    def test_not_rejects_a_non_bit(self) -> None:
        """``!`` guards its operand, as the interpreter's '! needs a bit'."""
        assert "xori a0, a0, 1" in self.comp("main { a = !0; }")

    def test_return_targets_its_own_function_epilogue(self) -> None:
        """A nested function's return must not jump to main's epilogue."""
        out = self.comp("f { return 1; }\nmain { a = (f 0); return 0; }")
        assert "j    .ret0" in out
        assert "j    .ret1" in out

    def test_prologue_saves_the_loop_registers(self) -> None:
        """s4/s5 are saved per invocation, not only per loop.

        A callee returning from inside its own loop discards that loop's
        stack save, so without this a mid-loop caller gets its counter
        clobbered and loses an iteration.
        """
        out = self.comp("main { for i:0..1 { } }")
        assert "sd   s4, 16(sp)" in out
        assert "ld   s5, 24(sp)" in out

    def test_statement_call_and_builtins_are_reachable(self) -> None:
        out = self.comp("main { out 0,0,0,0,0,0,0,0; a = (in 0); }")
        assert ".do_out:" in out
        assert ".do_in:" in out
        assert ".readline:" in out

    def test_anonymous_function_literal_compiles(self) -> None:
        out = self.comp("main { f = (a@{ return a; }); b = (f 1); }")
        assert ".global _start" in out

    def test_bare_block_literal_compiles(self) -> None:
        out = self.comp("main { x = { return 1; }; }")
        assert ".global _start" in out

    def test_iteration_loop_over_named_values(self) -> None:
        """Each listed value emits the body once, plus the entry's own call."""
        out = self.comp("main { for v:(0,1) { out 0,0,0,0,0,0,0,v; } }")
        assert out.count("call .dispatch") == 2 + 1


class TestContainerCompiler:
    """Container lowers a synchronous rule system to a dataflow round.

    Container is excluded from the ``COMPILERS`` sweep above because that
    sweep compiles the literal text ``"Hello"``, whose first line is a rule
    with no container to attach it to -- which the shared parser rejects.
    """

    @staticmethod
    def comp(code: str) -> str:
        mod = importlib.import_module("esolangs.compilers.container")
        return mod.comp(code)

    def test_produces_assembly(self) -> None:
        out = self.comp("A=1:\n+1 A>=0\nEXIT=1:\n-1 A>=3")
        assert ".global _start" in out

    def test_relaxation_is_disabled(self) -> None:
        """``la`` must not relax to a gp-relative access.

        Nothing initializes ``gp`` under ``-nostdlib``, so a relaxed ``la``
        yields a garbage buffer pointer and every container's store lands
        outside mapped memory.
        """
        assert ".option norelax" in self.comp("A:\nEXIT=1:\n-1 A>=0")

    def test_rule_before_declaration_is_rejected(self) -> None:
        """A rule with no container raises, sharing the interpreter's parser."""
        with pytest.raises(ValueError, match="rule line before any container"):
            self.comp("+1 T>=0")

    def test_undeclared_condition_name_is_rejected(self) -> None:
        """A name that is neither a container nor a literal is rejected.

        ``update`` calls ``val`` on every operand every tick, so such a
        program raises on its first tick; rejecting it at compile time
        matches the interpreter rather than narrowing the accepted class.
        """
        with pytest.raises(ValueError, match="undeclared container"):
            self.comp("A=1:\n+1 ZZ>=0")

    def test_negative_literal_is_accepted(self) -> None:
        """A negative operand parses as a literal, as ``int()`` does."""
        assert ".global _start" in self.comp("A=1:\n+1 A>=-1\nEXIT=1:\n-1 A>=3")

    def test_empty_program_halts_immediately(self) -> None:
        """No containers means ``halted`` before the first tick."""
        out = self.comp("")
        assert "li   a7, 93" in out
        assert ".tick:" not in out

    def test_two_buffers_are_one_symbol(self) -> None:
        """``old`` and ``new`` are halves of one array, so one ``la`` reaches both."""
        out = self.comp("A=1:\nEXIT=1:\n-1 A>=0")
        assert out.count("la   s1, con_cells") == 1
        assert "con_new" not in out

    def test_print_masks_to_seven_bits(self) -> None:
        """The interpreter prints ``OUT % (1 << 7)``, so the mask is 0x7f."""
        out = self.comp("OUT=200:\nPRINT:\n+1 PRINT<=0\nEXIT=1:\n-1 OUT>=0")
        assert "andi a0, a0, 0x7f" in out

    def test_print_needs_both_print_and_out(self) -> None:
        """PRINT without OUT prints nothing, as the interpreter's guard does."""
        assert "call putbyte" not in self.comp("PRINT:\n+1 PRINT<=0")

    def test_reader_without_in_still_consumes(self) -> None:
        """A program declaring ``""`` but no IN reads the byte and drops it.

        The interpreter writes ``new["IN"]`` into a dict with no IN
        container, so the value is discarded on the next tick.
        """
        out = self.comp(":\n+1 T>=0\nT:\n+1 T>=T")
        assert "call readqueue" in out
        assert "sd   a0," not in out

    def test_reader_with_in_stores_the_byte(self) -> None:
        """With IN declared, the read lands in the *new* buffer.

        Storing to ``new`` rather than ``old`` is what reproduces the
        interpreter's clobber: the write happens after IN's own rules have
        already computed a value for this tick.
        """
        out = self.comp(":\n+1 T>=0\nT:\n+1 T>=T\nIN=0:\n+1 T>=0")
        assert "call readqueue\n" in out
        assert "    sd   a0, 16(s2)\n" in out

    def test_exit_fires_on_any_change(self) -> None:
        """EXIT halts when its value *changes*, not on an edge to nonzero."""
        out = self.comp("EXIT=5:\n-1 T>=0\nT:\n+1 T>=T")
        assert "beq  t0, t1, .no_exit" in out

    def test_clamp_is_once_per_container(self) -> None:
        """``max(res, 0)`` wraps the whole rule sum, not each rule."""
        out = self.comp("A=1:\n-1 A>=0\n-1 A>=0\n-1 A>=0\nEXIT=1:\n-1 A>=9")
        assert out.count("bgez s3, .keep_0") == 1

    def test_duplicate_declaration_shares_one_cell(self) -> None:
        """Two containers of one name write the same cell, so the last wins.

        The interpreter builds ``new`` as a dict comprehension keyed by
        name, which is exactly what a second store to one cell reproduces.
        """
        out = self.comp("A=1:\n+1 T>=0\nA=2:\n+1 T>=0\nT:\n+1 T>=T")
        assert out.count("sd   s3, 0(s2)") == 2

    def test_values_are_fixed_width(self) -> None:
        """The 64-bit value domain is the one place totality stops.

        A delta at ``2**63 - 1`` is emitted as-is, which pins where the
        compiled form stops agreeing with the interpreter's unbounded
        integers: a container driven past that wraps negative, and
        ``max(res, 0)`` then destroys it rather than wrapping back.  The
        repo's generators peak at 127, so only hand-written programs can
        reach this.
        """
        out = self.comp(f"A=0:\n+{2**63 - 1} A>=0\nEXIT=1:\n-1 A>=1")
        assert f"li   t2, {2**63 - 1}\n" in out

    def test_far_cells_use_an_indirect_address(self) -> None:
        """Past the 12-bit ``ld``/``sd`` offset, the address is computed.

        The boolean generator needs ``2**n + 2n + 7`` containers, which
        passes 255 at ``n == 8``, so this path is reached by real output
        rather than only by a synthetic program.
        """
        lines = ["T:", "+1 T>=T"]
        for i in range(300):
            lines.append(f"C{i}={i}:")
            lines.append(f"+1 T>={i % 5}")
        out = self.comp("\n".join(lines))
        assert "add  t6, s1, t6" in out


class TestForbinDiscardTarget:
    """``_`` as a binding target, which the compiler emits no bind for.

    Forbin's ``_`` is an ordinary identifier to the lexer, so every place
    that binds a name has to special-case it.  There are three -- a
    multi-target assignment, a range loop's counter, and an iteration row --
    and each drops the store while still evaluating the value, matching the
    interpreter.  The programs are compiled, not assembled, so these need no
    cross-compiler.
    """

    @staticmethod
    def comp(code: str) -> str:
        mod = importlib.import_module("esolangs.compilers.forbin")
        return str(mod.comp(code))

    def test_multi_target_assignment_skips_the_discard(self) -> None:
        """``x,_ = 1,0`` binds ``x`` and drops the second store."""
        out = self.comp("main {\n  x,_ = 1,0;\n}\n")
        assert ".global _start" in out
        # one bind for x, none for the discard: the second value is still
        # evaluated, so the difference is the store, not the expression.
        assert (
            out.count("sd   a0, ")
            == self.comp("main {\n  x,y = 1,0;\n}\n").count("sd   a0, ") - 1
        )

    def test_range_loop_counter_may_be_discarded(self) -> None:
        """``for _:0..1`` runs its body without binding the counter."""
        out = self.comp("main {\n  for _:0..1 {\n    out 0,1,0,0,0,0,0,1;\n  }\n}\n")
        named = self.comp("main {\n  for i:0..1 {\n    out 0,1,0,0,0,0,0,1;\n  }\n}\n")
        assert ".global _start" in out
        assert len(out) < len(named)  # the bind is what the named form adds

    def test_iteration_row_may_discard_a_column(self) -> None:
        """``for (_,x):((0,1))`` binds only the column that is named."""
        out = self.comp(
            "main {\n  for (_,x):((0,1)) {\n    out 0,1,0,0,0,0,0,1;\n  }\n}\n"
        )
        named = self.comp(
            "main {\n  for (w,x):((0,1)) {\n    out 0,1,0,0,0,0,0,1;\n  }\n}\n"
        )
        assert ".global _start" in out
        assert len(out) < len(named)


class TestCVNCCompiler:
    """CV(N)(C) lowers a runtime-built function and two computed gotos.

    Excluded from the ``COMPILERS`` sweep above because that sweep compiles
    the literal text ``"Hello"``, which is not a syllable string -- the
    shared tokenizer rejects it on ``H``.
    """

    @staticmethod
    def comp(code: str) -> str:
        mod = importlib.import_module("esolangs.compilers.cvnc")
        return str(mod.comp(code))

    def test_produces_assembly(self) -> None:
        assert ".global _start" in self.comp("cici")

    def test_relaxation_is_disabled(self) -> None:
        """``la`` must not relax to a gp-relative access.

        Nothing initializes ``gp`` under ``-nostdlib``, so a relaxed ``la``
        yields a garbage table pointer and every computed goto would read
        outside mapped memory.
        """
        assert ".option norelax" in self.comp("cici")

    def test_empty_program_is_rejected(self) -> None:
        """An empty source is malformed, as it is for the interpreter."""
        with pytest.raises(ValueError, match="program is empty"):
            self.comp("")

    def test_non_symbol_is_rejected(self) -> None:
        """A character outside the command set makes the program malformed."""
        with pytest.raises(ValueError, match=r"not a CV\(N\)\(C\) symbol"):
            self.comp("ciZ")

    def test_unsyllabifiable_source_is_rejected(self) -> None:
        """The wiki's own counterexample: a nasal with no vowel of its own."""
        with pytest.raises(ValueError, match="syllable must start with a consonant"):
            self.comp("susŋ")

    def test_unbalanced_loop_is_rejected(self) -> None:
        """A ``ʋ`` with no opener is malformed, from the shared matcher."""
        with pytest.raises(ValueError, match="loop end with no matching start"):
            self.comp("ʋi")

    def test_every_token_is_a_jump_target(self) -> None:
        """``ɹ``/``j`` can land anywhere, so each token gets its own label."""
        out = self.comp("cici")
        assert all(f".t{i}:" in out for i in range(4))

    def test_ring_command_spans_two_offsets(self) -> None:
        """``ɰ̊`` is two codepoints and one command, so both offsets map to it.

        ``ɹ`` counts characters, so landing on the ring must resume at the
        ``ɰ̊`` itself -- there is no command in the middle of one.
        """
        out = self.comp("ɰ̊iʋi")
        table = out.split("cvnc_offsets:\n")[1].split("cvnc_starts:")[0]
        assert table.split()[:4] == [".dword", "0", ".dword", "0"]

    def test_ascii_g_folds_to_the_script_form(self) -> None:
        """The page's Hello, world! spells the multiplication plosive ``g``."""
        assert self.comp("giɡi") == self.comp("ɡiɡi")

    def test_loop_opener_jumps_past_its_end(self) -> None:
        """``ɰ̊`` clears the ``ʋ`` rather than landing on it.

        Landing *on* the loop end would run it and bounce straight back to
        the test that just failed, which is an infinite loop for the very
        case the test escapes.
        """
        out = self.comp("ɰ̊iʋi")
        assert "beqz s1, .t3" in out  # past the ``ʋ`` at token 2

    def test_loop_end_jumps_onto_its_opener(self) -> None:
        """``ʋ`` returns *to* the opener, which re-tests the condition."""
        assert "j    .t0" in self.comp("ɰ̊iʋi")

    def test_decrement_floors_at_zero(self) -> None:
        """The accumulator is unsigned, so ``ə`` cannot go below zero."""
        assert "beqz s1, 1f" in self.comp("cə")

    def test_literal_symbol_carries_a_value(self) -> None:
        """``p``/``k`` append a popped *number*, so an entry is a tagged pair.

        The other seven symbols are fixed, but a popped literal is an
        arbitrary 64-bit value, which is why the array is two words wide.
        """
        out = self.comp("pi")
        assert "call pop_front" in out
        assert f"li   a0, {7}" in out  # the literal tag

    def test_apply_is_a_runtime_evaluator(self) -> None:
        """``u`` parses the array at run time, not at compile time."""
        out = self.comp("cu")
        assert "call apply" in out
        assert "expr:" in out
        assert "term:" in out
        assert "factor:" in out

    def test_division_by_zero_halts(self) -> None:
        """A zero divisor is an invalid *operation*, not a malformed function."""
        assert "beqz a1, .halt" in self.comp("cu")

    def test_reader_is_line_faithful(self) -> None:
        """Both reads take a whole line, matching the interpreter's refill.

        ``s`` goes through ``IO.input_str`` and ``ʒ`` through
        ``IO.input_char``, which reads a line and returns its first
        character -- so a byte reader would diverge on identical stdin.
        """
        assert "call readline" in self.comp("soʒo")

    def test_arithmetic_is_software(self) -> None:
        """``rv64i`` has no multiply or divide, so both are emitted."""
        out = self.comp("cæco")
        assert "mul64:" in out
        assert "divu64:" in out
        assert "isqrt64:" in out
