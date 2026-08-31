"""Verify the transpilers.

The contract is that a brainfuck program and its translation are
interchangeable: the translation runs to identical output through the
target interpreter.  The Circlefuck
transpiler is a real program transformation (its tape is the program
itself), so it targets the class of brainfuck programs whose data pointer
stays within ``[0, size)``; a battery plus a fuzz of bounded, terminating
programs verifies that class.
"""

import random
import string

import pytest

import esolangs
from esolangs.exceptions import (
    EsolangError,
    UnsupportedTranspilationError,
)
from esolangs.tools.transpilers import _laser_analyze

# (brainfuck program, stdin) pairs; every pair must terminate and agree.
BATTERY = (
    ("+[>+<-]>.", ""),
    ("+++[>++<-]>++.", ""),
    ("+++[>++[>+<-]<-]>+++.", ""),
    (">+<<.", ""),
    (",>,<.>.", "a\nb"),
    (",[.-]", "a"),
    ("+++>+++<.>.", ""),
    ("+++++++++++++++++++++++++++++++++++++++++++++++++.", ""),
    (",", "a"),
    ("", ""),
    ("xx+++xx.xx", ""),
)

# a subset with pinned output, so the battery checks more than self-consistency
PINNED = {
    "+[>+<-]>.>": ("", "\x01"),
    "+++[>++<-]>+++.": ("", "\t"),
    "+++[>++[>+<-]<-]>+++.": ("", "\x03"),
    ">+<<.": ("", "\x00"),
    ",>,<.>.": ("a\nb", "ab"),
    "+++>+++<.>.": ("", "\x03\x03"),
    "+++++++++++++++++++++++++++++++++++++++++++++++++.": ("", "1"),
}

# (brainfuck program, stdin) pairs; each program keeps its pointer in
# [0, size) for the auto-sized bound, so it is in the Circlefuck
# transpiler's supported class.
CIRCLEFUCK_BATTERY = (
    ("++.", ""),
    ("+[>+<-]>.", ""),
    ("+++[>++<-]>+++.", ""),
    (",>,<.>.", "a\nb"),
    (",[.-]", "a"),
    ("++[>++[>+<-]<-]>+++.", ""),
    ("+++++++++++++++++++++++++++++++++++++++++++++++++.", ""),
    (">.<.", ""),
    (">++>+++<.>.<.", ""),
    ("[-]+++++++[-]++++++++++++++++++++++++++++++++++++++++++++++++.", ""),
    ("", ""),
)


def test_unsupported_pair_raises() -> None:
    with pytest.raises(UnsupportedTranspilationError):
        esolangs.transpile("brainfuck", "Unsquare", "x")
    with pytest.raises(UnsupportedTranspilationError):
        esolangs.transpile("Sophie", "Modulous", "x")
    assert issubclass(UnsupportedTranspilationError, EsolangError)
    assert issubclass(UnsupportedTranspilationError, ValueError)


def test_listed_transpilers_are_known_languages() -> None:
    """Every transpiler source and target is a registered language."""
    from esolangs.tools.transpilers import TRANSPILERS

    known = set(esolangs.list_languages())
    for source, target in TRANSPILERS:
        assert source in known
        assert target in known


@pytest.mark.parametrize(("program", "stdin"), CIRCLEFUCK_BATTERY)
def test_circlefuck_transpiled_output_matches_source(program: str, stdin: str) -> None:
    circlefuck = esolangs.transpile("brainfuck", "Circlefuck", program)
    assert esolangs.run("brainfuck", program, stdin) == esolangs.run(
        "Circlefuck", circlefuck, stdin
    )


@pytest.mark.parametrize(("program", "stdin"), CIRCLEFUCK_BATTERY)
def test_circlefuck_explicit_size(program: str, stdin: str) -> None:
    """An explicit size is a larger-but-still-valid data region."""
    circlefuck = esolangs.transpile("brainfuck", "Circlefuck", program, size=8)
    assert esolangs.run("brainfuck", program, stdin) == esolangs.run(
        "Circlefuck", circlefuck, stdin
    )


@pytest.mark.parametrize("text", ["Hello, World!", "Hi", "123"])
def test_circlefuck_transpiles_generated_program(text: str) -> None:
    """The BF generator's output (single cell) transpiles and prints the text."""
    program = esolangs.generate("brainfuck", text)
    circlefuck = esolangs.transpile("brainfuck", "Circlefuck", program)
    assert esolangs.run("Circlefuck", circlefuck) == text


def test_circlefuck_left_edge_is_out_of_class() -> None:
    """Moving below cell 0 is outside the supported class.

    Brainfuck clamps ``<`` at the left edge; Circlefuck's pointer wraps to
    the end of the program, so the transpiler only guarantees equivalence
    for programs that stay in ``[0, size)``.
    """
    program = ">+<<."  # reads cell 1, then moves below cell 0
    circlefuck = esolangs.transpile("brainfuck", "Circlefuck", program, size=4)
    assert esolangs.run("brainfuck", program) != esolangs.run("Circlefuck", circlefuck)


def test_circlefuck_auto_size_rejects_below_zero() -> None:
    """Programs that dip below cell 0 are rejected rather than mistranslated."""
    with pytest.raises(ValueError, match="below cell 0"):
        esolangs.transpile("brainfuck", "Circlefuck", ">+<<.")


def test_circlefuck_auto_size_rejects_drifting_loop() -> None:
    """Loops that drift the pointer unboundedly cannot be auto-sized."""
    with pytest.raises(ValueError, match="drift"):
        esolangs.transpile("brainfuck", "Circlefuck", "+[>+]")


def test_circlefuck_auto_size_rejects_nested_drifting_loop() -> None:
    """Drift detected inside a nested loop is propagated out."""
    with pytest.raises(ValueError, match="drift"):
        esolangs.transpile("brainfuck", "Circlefuck", "++[+[>+]]")


def test_circlefuck_unmatched_bracket_rejected() -> None:
    """Unbalanced brackets are malformed and rejected by both the source
    interpreter and the transpiler."""
    with pytest.raises(ValueError, match="unbalanced brackets"):
        esolangs.transpile("brainfuck", "Circlefuck", "[")


def test_circlefuck_size_must_be_positive() -> None:
    with pytest.raises(ValueError, match="size must be positive"):
        esolangs.transpile("brainfuck", "Circlefuck", "+.", size=0)


def test_circlefuck_fuzz_bounded_programs() -> None:
    """Random in-class programs (pointer in [0, size), terminating) agree."""
    rng = random.Random(5)
    for _ in range(60):
        size = rng.randint(1, 4)
        parts: list[str] = []
        ptr = 0
        for _ in range(rng.randint(3, 10)):
            kind = rng.choice(("inc", "dec", "print", "zero", "jump"))
            if kind == "jump":
                target = rng.randrange(size)
                if target >= ptr:
                    parts.append(">" * (target - ptr))
                else:
                    parts.append("<" * (ptr - target))
                ptr = target
            elif kind == "inc":
                parts.append("+" * rng.randint(1, 6))
            elif kind == "dec":
                parts.append("-" * rng.randint(1, 6))
            elif kind == "print":
                parts.append(".")
            else:
                parts.append("[-]")
        program = "".join(parts)
        circlefuck = esolangs.transpile("brainfuck", "Circlefuck", program)
        assert esolangs.run("brainfuck", program) == esolangs.run(
            "Circlefuck", circlefuck
        )


# 3D Brainfuck and Painfuck are brainfuck supersets, so the battery programs
# in class must agree byte-for-byte through the target interpreter.  3D
# Brainfuck's ``s`` walks negative where brainfuck clamps ``<``, so the one
# battery program that dips below cell 0 (``>+<<.``) is out of class and is
# tested as a rejection instead.
THREE_D_BATTERY = tuple((p, s) for p, s in BATTERY if p != ">+<<.")
PAINFUCK_BATTERY = BATTERY


@pytest.mark.parametrize(("program", "stdin"), THREE_D_BATTERY)
def test_three_d_bf_transpiled_output_matches_source(program: str, stdin: str) -> None:
    target = esolangs.transpile("brainfuck", "3D Brainfuck", program)
    assert esolangs.run("brainfuck", program, stdin) == esolangs.run(
        "3D Brainfuck", target, stdin
    )


@pytest.mark.parametrize(("program", "stdin"), PAINFUCK_BATTERY)
def test_painfuck_transpiled_output_matches_source(program: str, stdin: str) -> None:
    target = esolangs.transpile("brainfuck", "Painfuck", program)
    assert esolangs.run("brainfuck", program, stdin) == esolangs.run(
        "Painfuck", target, stdin
    )


@pytest.mark.parametrize("program", ["+", "+[>+<-]>.", ",>,<.>."])
def test_three_d_bf_is_a_command_swap(program: str) -> None:
    """The translation swaps >/< for n/s and leaves everything else."""
    target = esolangs.transpile("brainfuck", "3D Brainfuck", program)
    assert target == program.replace(">", "n").replace("<", "s")


@pytest.mark.parametrize("program", ["+", "+[>+<-]>.", ",>,<.>."])
def test_three_d_bf_transpile_preserves_comments(program: str) -> None:
    """Non-command characters pass through unchanged (comments stay comments)."""
    commented = "xx" + program + "yy"
    target = esolangs.transpile("brainfuck", "3D Brainfuck", commented)
    assert target.startswith("xx")
    assert target.endswith("yy")


def test_three_d_bf_transpile_empty() -> None:
    assert esolangs.transpile("brainfuck", "3D Brainfuck", "") == ""


def test_painfuck_transpile_empty() -> None:
    assert esolangs.transpile("brainfuck", "Painfuck", "") == ""


def test_three_d_bf_fuzz_agrees() -> None:
    """Random in-class brainfuck programs agree through 3D Brainfuck.

    In-class = straight-line commands whose pointer never dips below cell 0
    (3D Brainfuck's ``s`` walks negative where brainfuck clamps).
    """
    rng = random.Random(7)
    for _ in range(60):
        parts: list[str] = []
        ptr = 0
        for _ in range(rng.randint(3, 12)):
            kind = rng.choice(("inc", "dec", "print", "right", "left", "zero"))
            if kind == "right":
                parts.append(">" * rng.randint(1, 2))
                ptr += rng.randint(1, 2)
            elif kind == "left":
                if ptr == 0:
                    continue
                back = rng.randint(1, min(2, ptr))
                parts.append("<" * back)
                ptr -= back
            elif kind == "inc":
                parts.append("+" * rng.randint(1, 5))
            elif kind == "dec":
                parts.append("-" * rng.randint(1, 5))
            elif kind == "print":
                parts.append(".")
            else:
                parts.append("[-]")
        program = "".join(parts)
        try:
            target = esolangs.transpile("brainfuck", "3D Brainfuck", program)
        except ValueError:
            continue  # the generated program left cell 0; skip it
        expected = esolangs.run("brainfuck", program)
        assert esolangs.run("3D Brainfuck", target) == expected


def test_painfuck_fuzz_agrees() -> None:
    """Random terminating brainfuck programs agree through Painfuck."""
    rng = random.Random(11)
    for _ in range(60):
        # straight-line programs always terminate (loops can run forever)
        program = "".join(rng.choice("+-<>.,") for _ in range(rng.randint(1, 16)))
        try:
            expected = esolangs.run("brainfuck", program)
        except Exception:
            continue
        target = esolangs.transpile("brainfuck", "Painfuck", program)
        assert esolangs.run("Painfuck", target) == expected


def test_three_d_bf_rejects_below_cell_zero() -> None:
    """Programs that dip below cell 0 are rejected, like Circlefuck's.

    3D Brainfuck's ``s`` walks negative where brainfuck clamps ``<``.
    """
    with pytest.raises(ValueError, match="below cell 0"):
        esolangs.transpile("brainfuck", "3D Brainfuck", ">+<<.")
    with pytest.raises(ValueError, match="below cell 0"):
        esolangs.transpile("brainfuck", "3D Brainfuck", "<")


# (Dimensional program, stdin) pairs in the transpiler's supported class: the
# linear-tape bf core with a final single output at most.
LASERFUCK_BATTERY = (
    ("+++", ""),
    ("+++[-]", ""),
    ("+>0+<0++", ""),
    ("+++[>0+++<0-]", ""),
    ("++[>0++<0-]", ""),
    (">0+++<0+++[-]", ""),
    ("+++[>0+++<0-]>0.", ""),
    ("++++++++[>0++++++++<0-]>0.", ""),
    ("=4A.", ""),
    (":A.", ""),
    (",>0+<0-", "ab"),
    (",+,.", "a\nb"),
    ("+->0.", "a"),
    ("", ""),
)


@pytest.mark.parametrize(("program", "stdin"), LASERFUCK_BATTERY)
def test_laserfuck_transpiled_output_matches_source(program: str, stdin: str) -> None:
    laserfuck = esolangs.transpile("Dimensional", "LaserFuck", program)
    assert esolangs.run("Dimensional", program, stdin) == esolangs.run(
        "LaserFuck", laserfuck, stdin
    )


def test_laserfuck_pinned_outputs() -> None:
    """A subset with pinned output, so the battery checks more than self-consistency."""
    pinned = {
        "+++[>0+++<0-]>0.": "\t",
        "++++++++[>0++++++++<0-]>0.": "@",
        "=4A.": "J",
        ":A.": "A",
        "+++.": "\x03",
        "+[>0+[>0+<0-]<0-]>0.": "\x00",  # nested loop emission
        "+*comment*+>0.": "\x00",  # *...* comment skipped
    }
    for program, expected in pinned.items():
        laserfuck = esolangs.transpile("Dimensional", "LaserFuck", program)
        assert esolangs.run("LaserFuck", laserfuck) == expected


def test_laserfuck_grid_is_rectangular_with_start_and_marker() -> None:
    """The output is a grid with the byte-mode marker and a start."""
    laserfuck = esolangs.transpile("Dimensional", "LaserFuck", "+++[>0+<0-]")
    lines = laserfuck.splitlines()
    assert lines[0][0] == "\u00ff"
    assert any("o" in ln for ln in lines)
    assert any(")" in ln for ln in lines)  # a loop test


@pytest.mark.parametrize(
    ("program", "match"),
    [
        ("+>1-", "only dimension 0"),  # non-zero dimension
        ("+>~1-", "only dimension 0"),  # negative dimension
        ("+>+", "bare '>'/'<'"),  # bare move (dimension = current value)
        ("<0+", "below cell 0"),
        ("[<0]", "below cell 0"),  # below cell 0 inside a loop
        (".+", "must be the last"),  # output not last
        ("+[.-]", "inside a loop"),  # output inside a loop
        ("[>0-]", "drift"),  # drifting loop
        ("++[+[>0]]", "drift"),  # drifting nested loop
        ("$2", "out of the supported class"),  # axis selection
        ("{0", "out of the supported class"),  # axis-coordinate loop
        ("?0", "out of the supported class"),  # coordinate read
        ("!0", "out of the supported class"),  # coordinate clear
        ("d", "out of the supported class"),  # decimal read
        ("x", "out of the supported class"),  # hex read
        ("[", "unbalanced brackets"),
        ("]", "unbalanced brackets"),  # stray close
        ("=", "must be followed by two hex digits"),  # truncated literal
        ("=4", "must be followed by two hex digits"),
        ("=zz", "must be followed by two hex digits"),  # non-hex literal
        (":", "must be followed by a character"),  # truncated char literal
    ],
)
def test_laserfuck_out_of_class_rejected(program: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        esolangs.transpile("Dimensional", "LaserFuck", program)


@pytest.mark.parametrize("op", ["+", "-", ">", "><", ".", ",", "[]"])
def test_laserfuck_analyze_advances_on_every_command(op: str) -> None:
    """Every command steps the walk, so none of them can spin forever.

    ``_laser_analyze`` dispatches per command and advances an index by hand;
    a command handled by no arm never steps that index and hangs the walk
    rather than failing, so each one is pinned here.
    """
    assert _laser_analyze(list(op))[0] >= 0


def test_laserfuck_fuzz_bounded_programs() -> None:
    """Random in-class, guaranteed-terminating programs agree."""
    rng = random.Random(9)

    def gen() -> str:
        cells: dict[int, int] = {}
        ptr = 0
        ops: list[str] = []
        for _ in range(rng.randint(3, 8)):
            r = rng.random()
            v = cells.get(ptr, 0)
            if r < 0.3 and v < 8:
                ops.append("+")
                cells[ptr] = v + 1
            elif r < 0.45 and v > 0:
                ops.append("-")
                cells[ptr] = v - 1
            elif r < 0.6:
                ops.append("[-]")  # clear loop: terminates on a nonnegative cell
                cells[ptr] = 0
            elif r < 0.75:
                ptr += 1
                ops.append(">0")
                cells.setdefault(ptr, 0)
            elif r < 0.9 and ptr > 0:
                ptr -= 1
                ops.append("<0")
        if rng.random() < 0.5:
            ops.append(".")
        return "".join(ops)

    for _ in range(60):
        program = gen()
        stdin = "".join(rng.choice("ab") for _ in range(rng.randint(1, 2)))
        expected = esolangs.run("Dimensional", program, stdin)
        laserfuck = esolangs.transpile("Dimensional", "LaserFuck", program)
        assert esolangs.run("LaserFuck", laserfuck, stdin) == expected


# (BFStack program, stdin) pairs; every program pushes before it reads the
# stack and terminates.
BFSTACK_BATTERY = (
    (">.", ""),
    (">+.", ""),
    (">+++.", ""),
    (">++[>+<-].", ""),
    (">++[>+<-]>.<.", ""),
    (">[-].", ""),
    (">+[>+<-].", ""),
    (">>+<>.", ""),
    (",.", "Z"),
    (">,.", "a"),
    (">>,<>.", "p\nq"),
    (">", ""),
)


@pytest.mark.parametrize(("program", "stdin"), BFSTACK_BATTERY)
def test_bfstack_transpiles_to_brainfuck(program: str, stdin: str) -> None:
    bf_program = esolangs.transpile("BFStack", "brainfuck", program)
    assert esolangs.run("BFStack", program, stdin) == esolangs.run(
        "brainfuck", bf_program, stdin
    )


@pytest.mark.parametrize("text", ["Hello, World!", "Hi", "123"])
def test_bfstack_transpiles_generated_program(text: str) -> None:
    """The BFStack generator's output prints the same text as brainfuck."""
    program = esolangs.generate("BFStack", text)
    bf_program = esolangs.transpile("BFStack", "brainfuck", program)
    assert esolangs.run("brainfuck", bf_program) == text


def test_bfstack_fuzz_stack_programs() -> None:
    """Random well-formed stack programs (tracked depth, safe loops) agree."""
    rng = random.Random(7)
    for _ in range(60):
        parts: list[str] = [">"]
        depth = 1
        for _ in range(rng.randint(3, 10)):
            kind = rng.choice(("push", "pop", "inc", "dec", "print", "zero"))
            if kind == "push":
                parts.append(">")
                depth += 1
            elif kind == "pop" and depth > 1:
                parts.append("<")
                depth -= 1
            elif kind == "inc":
                parts.append("+" * rng.randint(1, 6))
            elif kind == "dec":
                parts.append("-" * rng.randint(1, 6))
            elif kind == "print":
                parts.append(".")
            else:
                parts.append("[-]")
        program = "".join(parts)
        bf_program = esolangs.transpile("BFStack", "brainfuck", program)
        assert esolangs.run("BFStack", program) == esolangs.run("brainfuck", bf_program)


# (BIO program, stdin) pairs; every program terminates and its registers
# stay inside [0, 255], so it is in the transpiler's supported class.
BIO_BATTERY = (
    ("0ox;1ix;", ""),
    ("0oy;1iy;", ""),
    ("0oz;1iz;", ""),
    ("1ix;", ""),
    ("0ox;0ox;1ix;", ""),
    ("0ox;0oy;0ix{1iy;1ox;};", ""),
    ("0ox;0oy;0oz;0iy{1iz;1oy;};", ""),
    ("1ix;1ix;", ""),
    ("0ox;0oz;0iz{1ix;1oz;};", ""),
    ("0ox;0oy;0ox;0iy{1iy;1oy;1ix;1ox;};", ""),
)


@pytest.mark.parametrize(("program", "stdin"), BIO_BATTERY)
def test_bio_transpiles_to_brainfuck(program: str, stdin: str) -> None:
    bf_program = esolangs.transpile("BIO", "brainfuck", program)
    assert esolangs.run("BIO", program, stdin) == esolangs.run(
        "brainfuck", bf_program, stdin
    )


@pytest.mark.parametrize("text", ["Hello, World!", "Hi", "123"])
def test_bio_transpiles_generated_program(text: str) -> None:
    """The BIO generator's output prints the same text as brainfuck."""
    program = esolangs.generate("BIO", text)
    bf_program = esolangs.transpile("BIO", "brainfuck", program)
    assert esolangs.run("brainfuck", bf_program) == text


def test_bio_comments_are_ignored() -> None:
    """A ``//`` comment runs to the end of its line and is dropped."""
    program = "0ox; //hello there\n1ix; //ok"
    bf_program = esolangs.transpile("BIO", "brainfuck", program)
    assert (
        esolangs.run("BIO", program) == esolangs.run("brainfuck", bf_program) == "\x01"
    )


def test_bio_unbalanced_loops_rejected() -> None:
    """A stray '}' or an unclosed '0i{' is rejected, not crashed on."""
    with pytest.raises(ValueError, match="closes no loop"):
        esolangs.transpile("BIO", "brainfuck", "};")
    with pytest.raises(ValueError, match="unmatched"):
        esolangs.transpile("BIO", "brainfuck", "0ix{0iy{")


def test_bio_loop_without_its_brace_is_rejected() -> None:
    """``0i?`` is only a command with the ``{`` that opens its body.

    The wiki writes the loop as ``0i{ do something };``, so a bare ``0ix``
    is not a command at all -- and rejecting it is what stops a program
    that meant to loop from quietly running as something else.
    """
    with pytest.raises(ValueError, match="not a command"):
        esolangs.transpile("BIO", "brainfuck", "0ox;0ix1ox;};")


def test_bio_register_wrap_is_out_of_class() -> None:
    """A register reaching a nonzero multiple of 256 is outside the class.

    BIO's registers are unbounded, so 256 is truthy for a loop condition;
    brainfuck cells wrap, so the same register reads as 0.
    """
    program = "0ox;" * 256 + "0ix{1ix;1ox;};"
    bf_program = esolangs.transpile("BIO", "brainfuck", program)
    assert esolangs.run("BIO", program) != esolangs.run("brainfuck", bf_program)


def test_bio_fuzz_register_programs() -> None:
    """Random programs (tracked registers, terminating loops) agree."""
    rng = random.Random(11)
    for _ in range(60):
        parts: list[str] = []
        reg = [0, 0, 0]
        for _ in range(rng.randint(3, 10)):
            r = rng.randrange(3)
            kind = rng.choice(("inc", "dec", "out", "loop"))
            if kind == "inc":
                parts.append("0o" + "xyz"[r] + ";")
                reg[r] += 1
            elif kind == "dec":
                parts.append("1o" + "xyz"[r] + ";")
                reg[r] -= 1
            elif kind == "out":
                parts.append("1i" + "xyz"[r] + ";")
            else:
                move = "1o" if reg[r] > 0 else "0o" if reg[r] < 0 else ""
                body = move + "xyz"[r] + ";" if move else ""
                if move and rng.random() < 0.5:
                    body += "1i" + "xyz"[rng.randrange(3)] + ";"
                parts.append("0i" + "xyz"[r] + "{" + body + "};")
                reg[r] = 0
        program = "".join(parts)
        bf_program = esolangs.transpile("BIO", "brainfuck", program)
        assert esolangs.run("BIO", program) == esolangs.run("brainfuck", bf_program)


# (brainfuck program, stdin) pairs; every program terminates.
SIX_FIVE_BATTERY = (
    ("+[>+<-]>.", ""),
    ("+++[>++<-]>++.", ""),
    ("+++[>++[>+<-]<-]>+++.", ""),
    (">+<<.", ""),
    (",>,<.>.", "a\nb"),
    (",[.-]", "a"),
    ("+++>+++<.>.", ""),
    ("+++++++++++++++++++++++++++++++++++++++++++++++++.", ""),
    (",", "a"),
    ("", ""),
    ("xx+++xx.xx", ""),
)


@pytest.mark.parametrize(("program", "stdin"), SIX_FIVE_BATTERY)
def test_six_five_transpiled_output_matches_source(program: str, stdin: str) -> None:
    six_five = esolangs.transpile("brainfuck", "6-5", program)
    assert esolangs.run("brainfuck", program, stdin) == esolangs.run(
        "6-5", six_five, stdin
    )


def test_six_five_transpiles_generated_program() -> None:
    """The BF generator's output (single cell) transpiles and prints the text."""
    text = "Hello, World!"
    program = esolangs.generate("brainfuck", text)
    six_five = esolangs.transpile("brainfuck", "6-5", program)
    assert esolangs.run("6-5", six_five) == text


def test_six_five_loop_cap() -> None:
    """More than 17 loops cannot be labelled within the spec's alphabet.

    The bound is derived from the operand alphabet (digits then ``A``..``Z``,
    so 35 is the highest named marker), not hardcoded: an 18th loop would
    need marker 36, which the spec names no character for.
    """
    from esolangs.tools.transpilers import _SIX_FIVE_MAX_LABEL

    cap = _SIX_FIVE_MAX_LABEL // 2
    with pytest.raises(ValueError, match=f"{cap} loops"):
        esolangs.transpile("brainfuck", "6-5", "[-]" * (cap + 1))


def test_six_five_transpile_stays_in_the_spec_alphabet() -> None:
    """Every 7n/8n operand emitted is a digit or an uppercase letter.

    At the cap the transpiler used to emit ``8[`` -- operand 36 -- which only
    worked through the interpreter's undefined decode.
    """
    from esolangs.interpreters.tape_based.six_five import _tokens
    from esolangs.tools.transpilers import _SIX_FIVE_MAX_LABEL

    code = esolangs.transpile("brainfuck", "6-5", "[-]" * (_SIX_FIVE_MAX_LABEL // 2))
    operands = [t[1] for t in _tokens(code) if t[0] in "78" and len(t) > 1]
    assert operands, "expected the transpile to emit 7n/8n tokens"
    assert all(c.isdigit() or c in string.ascii_uppercase for c in operands)


def test_six_five_label_rejects_values_outside_the_alphabet() -> None:
    """The label helper refuses what the operand alphabet cannot spell.

    The transpiler stops at the cap before ever asking for one of these, so
    this guard is reached only by calling the helper directly -- which is
    the point: it is what keeps a future caller from emitting an operand the
    spec does not name.
    """
    from esolangs.tools.transpilers import _SIX_FIVE_MAX_LABEL, _six_five_label

    # The two ends of the valid range still spell.
    assert _six_five_label(0) == "0"
    assert _six_five_label(_SIX_FIVE_MAX_LABEL) == "Z"

    for bad in (-1, _SIX_FIVE_MAX_LABEL + 1):
        # ``match`` is a substring search, so the equality below is what
        # actually pins the message.
        with pytest.raises(ValueError, match="no operand character") as caught:
            _six_five_label(bad)
        assert str(caught.value) == f"6-5 has no operand character for {bad}"


def test_six_five_unbalanced_brackets_rejected() -> None:
    with pytest.raises(ValueError, match="unbalanced"):
        esolangs.transpile("brainfuck", "6-5", "+[")


# (Basicfuck program, stdin) pairs; each uses an 8-bit wrapping tape and
# keeps every cell in [0, 255] while it runs (the transpiler's supported
# class).
# The 8-bit wrapping tape header shared by the battery programs.
_BF = "#basicfuck t=unbounded r=0~255 o=wrap\n#allocate "
_HDR2 = _BF + "a, b\n"
_HDR3 = _BF + "a, b, c\n"
_HDRARR = _BF + "a->3\n"

BASICFUCK_BATTERY = (
    (_BF + "a\na += 65;\nwrite <- a ;", ""),
    (
        "#basicfuck t=3 r=0~255 o=wrap\n#allocate a, b\na += 5;\nb += a;\nwrite <- b ;",
        "",
    ),
    (_BF + "a\nread -> a ;\nwrite <- a ;", "X\n"),
    (_BF + "a\na += 1;\nif (a) { write <- a ; }", ""),
    (_BF + "a\na += 0;\nif (a) { write <- a ; }", ""),
    (_BF + "a\na += 0;\nif !(a) { a += 65; }\nwrite <- a ;", ""),
    (_BF + "a\na += 5;\nwhile (a) { a -= 1; }\nwrite <- a ;", ""),
    (_BF + "a\na += 5;\nwhile !(a) { a -= 1; }\nwrite <- a ;", ""),
    (_HDR3 + "a += 1;\nif (a) { b += 2; if (b) { c += 3; } }\nwrite <- c ;", ""),
    (_HDR2 + "a += 7;\nb += 2;\nb += a;\nwrite <- b ;", ""),
    (_HDRARR + "a->0 += 72;\na->1 += 105;\nwrite <- a->0 ;\nwrite <- a->1 ;", ""),
    (_BF + "a\nread -> a ;\na -= 32;\nwrite <- a ;", "h\n"),
    (_HDR2 + "a += 4;\nwhile (a) { a -= 1; b += 2; }\nwrite <- b ;", ""),
    (_HDR2 + "a += 3;\nwhile (a) { b += a; a -= 1; }\nwrite <- b ;", ""),
)


@pytest.mark.parametrize(("program", "stdin"), BASICFUCK_BATTERY)
def test_basicfuck_transpiles_to_brainfuck(program: str, stdin: str) -> None:
    bf_program = esolangs.transpile("Basicfuck", "brainfuck", program)
    assert esolangs.run("Basicfuck", program, stdin) == esolangs.run(
        "brainfuck", bf_program, stdin
    )


def test_basicfuck_requires_byte_tape() -> None:
    """Non-8-bit tapes are rejected rather than silently mistranslated."""
    with pytest.raises(ValueError, match="r=0~255"):
        esolangs.transpile(
            "Basicfuck", "brainfuck", "#basicfuck t=1 r=0~1023 o=wrap\n#allocate a\n"
        )


_HEADER = "#basicfuck t=1 r=0~255 o=wrap\n#allocate a\n"

# malformed Basicfuck programs, each rejected by the parser rather than
# mistranslated
_BASICFUCK_MALFORMED = {
    "missing-allocate": "#basicfuck t=1 r=0~255 o=wrap",
    "bad-directive": "hello\n#allocate a",
    "if-without-paren": _HEADER + "if a { a += 1; }",
    "if-missing-paren": _HEADER + "if (a { a += 1; }",
    "if-missing-brace": _HEADER + "if (a) }",
    "if-unterminated": _HEADER + "if (a) { a += 1; x }",
    "if-unterminated-eof": _HEADER + "if (a) { a += 1;",
    "write-missing-arrow": _HEADER + "write a;",
    "write-missing-semicolon": _HEADER + "write <- a b;",
    "assign-bad-op": _HEADER + "a 5;",
    "assign-missing-semicolon": _HEADER + "a += 1 b;",
    "constant-out-of-range": _HEADER + "a += 300;",
}


@pytest.mark.parametrize("program", _BASICFUCK_MALFORMED.values())
def test_basicfuck_malformed_programs_rejected(program: str) -> None:
    with pytest.raises(
        ValueError,
        match=(
            r"(needs a directive|Missing/Invalid|Invalid syntax|"
            r"Invalid token|constants within)"
        ),
    ):
        esolangs.transpile("Basicfuck", "brainfuck", program)


def test_basicfuck_fuzz_in_bounds_programs() -> None:
    """Random in-bounds programs (cells stay in 0..255) agree."""
    rng = random.Random(11)
    for _ in range(60):
        a = rng.randint(1, 5)
        stmts = [f"a += {a};"]
        for _ in range(rng.randint(1, 3)):
            kind = rng.choice(("inc", "dec-safe", "loop", "ifadd"))
            if kind == "inc":
                k = rng.randint(1, 5)
                a += k
                stmts.append(f"a += {k};")
            elif kind == "dec-safe" and a > 0:
                k = rng.randint(1, min(a, 3))
                a -= k
                stmts.append(f"a -= {k};")
            elif kind == "loop":
                stmts.append("while (a) { a -= 1; b += 1; }")
                a = 0
            else:
                stmts.append("if (a) { b += 1; }")
        stmts.append("b += a;")
        stmts.append("write <- b ;")
        program = "#basicfuck t=unbounded r=0~255 o=wrap\n#allocate a, b\n" + "\n".join(
            stmts
        )
        bf_program = esolangs.transpile("Basicfuck", "brainfuck", program)
        assert esolangs.run("Basicfuck", program) == esolangs.run(
            "brainfuck", bf_program
        )


# (Decleq program, stdin) pairs.  The transpiler emits a Decleq emulator,
# so nothing about a program's shape puts it out of class: self-modifying
# code, computed jumps, lengths and targets that are not multiples of
# three, and negative operands all translate.  The pairs avoid *empty*
# input lines, which S*bleq cannot represent (see
# ``test_decleq_empty_input_line_is_a_target_language_collision``).
DECLEQ_BATTERY = (
    ("1 1 3 -2 1 0", ""),
    ("9 12 3 -2 12 0 -7 0 -1 5 0 0", ""),
    ("9 12 3 -2 12 0 -7 0 -1 1 0 0", ""),
    ("9 12 6 -2 12 0 -7 0 -1 0 0 0", ""),
    ("9 12 3 -2 12 0 -7 0 -1 -3 0 0", ""),
    ("2 21 3 -2 21 0 21 21 9 -2 21 0 21 21 15 -2 21 0 -7 0 -1", ""),
    ("-1 0 3 -2 0 0", "A"),
    ("-1 0 3 -2 0 0", "\x00"),
    ("-1 0 3 -2 0 0 -1 1 9 -2 1 0", "B\nC\n"),
    ("", ""),
    # Classes the earlier static translation rejected outright.
    ("2 10 3 255 10 6 -10 16 9 -2 10 0 -2 10 0 -2 16 0", ""),  # self-modifying
    ("1 1 4 0 0 0 -2 0 0", ""),  # jump target not a multiple of three
    ("1 1 3 -2", ""),  # length not a multiple of three
    ("5 -2 3", ""),  # negative non-special b
    ("-7 0 3 -2 0 0", ""),  # negative non-special a, which reads as zero
    ("-2 -3 3", ""),  # output through a negative address
)


@pytest.mark.parametrize(("program", "stdin"), DECLEQ_BATTERY)
def test_decleq_transpiles_to_sbleq(program: str, stdin: str) -> None:
    sb_program = esolangs.transpile("Decleq", "S*bleq", program)
    assert esolangs.run("Decleq", program, stdin) == esolangs.run(
        "S*bleq", sb_program, stdin
    )


def test_decleq_self_modifying_code_is_translated() -> None:
    """A write re-read as an operand translates; the emulator dispatches it.

    This program overwrites the operand of a later instruction, which no
    static per-instruction rewrite can express -- a computed target may
    land in the middle of a translated block.  The emulator has no blocks
    to land in the middle of.
    """
    program = "2 10 3 255 10 6 -10 16 9 -2 10 0 -2 10 0 -2 16 0"
    sb_program = esolangs.transpile("Decleq", "S*bleq", program)
    assert esolangs.run("S*bleq", sb_program) == esolangs.run("Decleq", program)


def test_decleq_non_triple_length_is_translated() -> None:
    """Decleq reads a missing ``b``/``c`` as zero, so any length is legal."""
    sb_program = esolangs.transpile("Decleq", "S*bleq", "1 1 3 -2")
    assert esolangs.run("S*bleq", sb_program) == esolangs.run("Decleq", "1 1 3 -2")


def test_decleq_unaligned_jump_target_is_translated() -> None:
    """A target that is not a multiple of three lands mid-instruction."""
    program = "1 1 4 0 0 0 -2 0 0"
    sb_program = esolangs.transpile("Decleq", "S*bleq", program)
    assert esolangs.run("S*bleq", sb_program) == esolangs.run("Decleq", program)


def test_decleq_negative_b_indexes_from_the_end() -> None:
    """A negative non-special ``b`` writes through Python's negative index."""
    program = "5 -2 3"
    sb_program = esolangs.transpile("Decleq", "S*bleq", program)
    assert esolangs.run("S*bleq", sb_program) == esolangs.run("Decleq", program)


def test_decleq_transpiler_is_total() -> None:
    """No integer list is rejected: the rewrite raises only on non-integers."""
    for program in (
        "",
        "0",
        "-1",
        "1 2",
        "5 -2 3",
        "1 1 4 0 0 0",
        "-99 -99 -99",
        "2 10 3 255 10 6 -10 16 9 -2 10 0 -2 10 0 -2 16 0",
    ):
        assert esolangs.transpile("Decleq", "S*bleq", program)
    with pytest.raises(ValueError, match="malformed memory token"):
        esolangs.transpile("Decleq", "S*bleq", "1 x 3")


def test_decleq_empty_input_line_is_a_target_language_collision() -> None:
    """An empty input line is the one thing S*bleq cannot represent.

    Decleq's reader turns an empty line into ``10`` (the newline that ended
    it) and a ``"\x00"`` line into ``0``.  S*bleq's only input primitive,
    address ``-2``, yields ``0`` for *both* -- two inputs reaching one
    value.  Every S*bleq computation is a function of the values it reads,
    so no S*bleq program can separate them and no translation can either;
    the same collision sends end-of-input to ``0`` where Decleq raises
    ``EOFError``.  This asserts the divergence rather than hiding it.
    """
    program = "-1 0 3 -2 0 0"
    sb_program = esolangs.transpile("Decleq", "S*bleq", program)
    assert esolangs.run("Decleq", program, "\n") == "\n"
    assert esolangs.run("S*bleq", sb_program, "\n") == "\x00"
    # the collision: a NUL line is what S*bleq reports for both
    assert esolangs.run("S*bleq", sb_program, "\x00") == "\x00"


def test_decleq_fuzz_unrestricted_programs() -> None:
    """Random programs of any shape agree with the Decleq interpreter."""
    rng = random.Random(19)
    vals = [0, 1, 2, 3, 5, 9, -1, -2, -3, -7, 42, 127, 255, -255, 6, 12, 15, 4, 10]
    checked = 0
    for _ in range(120):
        cells = [rng.choice(vals) for _ in range(rng.randint(0, 12))]
        program = " ".join(map(str, cells))
        try:
            expected = esolangs.run("Decleq", program)
        except (EsolangError, EOFError, IndexError):
            continue  # the reference interpreter errors; no behaviour to match
        sb_program = esolangs.transpile("Decleq", "S*bleq", program)
        assert esolangs.run("S*bleq", sb_program) == expected
        checked += 1
    assert checked > 40, f"only {checked} programs terminated; fuzz is not exercising"


def test_decleq_fuzz_countdowns() -> None:
    """Random countdowns (the canonical ``x x next`` idiom) agree."""
    rng = random.Random(23)
    checked = 0
    for _ in range(40):
        x = rng.randint(0, 25)
        program = f"{x} {x} 3 -2 {x} 0"
        try:
            expected = esolangs.run("Decleq", program)
        except (EsolangError, EOFError, IndexError):
            continue
        sb_program = esolangs.transpile("Decleq", "S*bleq", program)
        assert esolangs.run("S*bleq", sb_program) == expected
        checked += 1
    assert checked > 10, f"only {checked} countdowns terminated"


def test_laser_emit_steps_past_a_stray_loop_close() -> None:
    """A ``]`` reaching the walk directly costs no cell.

    The ``[`` arm consumes its matching close while laying out the loop, so
    a ``]`` the walk sees itself has already been accounted for -- it is
    stepped over rather than given a square of its own.  Emitting ``]+``
    therefore lays out exactly the one cell that ``+`` needs.
    """
    from esolangs.tools.transpilers import _laser_emit, _LaserGrid

    grid = _LaserGrid()
    next_col, _bottom = _laser_emit(grid, list("]+"), 4, 0)

    plain = _LaserGrid()
    assert _laser_emit(plain, list("+"), 4, 0) == (next_col, _bottom)


def _street_corridor(body: str) -> str:
    """Draw ``body`` as a single two-wide east-west street.

    Streetcode's streets are two characters wide and must be walled all
    round, so the shortest program that is just a run of commands is a
    blank lane above the code lane, boxed.  Every accepted program in this
    module is one of these: a drive with nothing for the tape to steer.
    """
    inner = len(body)
    return "\n".join(
        [
            "+" + "-" * inner + "+",
            "|" + " " * inner + "|",
            "|" + body + "|",
            "+" + "-" * inner + "+",
        ]
    )


# The counting loop from ``tests/interpreters/test_streetcode.py``: nine
# laps of an island, printing 'H'.  It is the *designed* Streetcode loop,
# and it is out of the transpiler's class -- see the rejection test.
STREET_COUNTING_LOOP = "\n".join(
    [
        "+------------+",
        "|            |",
        "|C^        O;|",
        "+--+  ++  +--+",
        "   |      |",
        "   | ^_~ =|",
        "   | ^++= |",
        "   |^^++^U|",
        "   |^^^^^=|",
        "   |^^^^^^|",
        "   +------+",
    ]
)

# A ring whose only junction is where the car enters it.  The car still
# never returns to that junction *as a drive state*, which is the wall.
STREET_RING = "\n".join(
    [
        "+---------+",
        "|         |",
        "|C^^^   O;|",
        "+--+  +--+",
        "   |  |",
        "   |~ |",
        "   |  |",
        "   +--+",
    ]
)

# (command run, stdin) pairs; each is drawn as a corridor and must agree.
STREETCODE_BATTERY = (
    ("C^^^O;", ""),
    ("C" + "^" * 65 + "O;", ""),
    ("C^^=^^O;", ""),
    ("C^^=^^~O;", ""),
    ("C=^^^_^O;", ""),
    ("CIO;", "A\n"),
    ("CI^O;", "A\n"),
    ("CIO;", "\n"),
)


@pytest.mark.parametrize(("body", "stdin"), STREETCODE_BATTERY)
def test_streetcode_transpiled_output_matches_source(body: str, stdin: str) -> None:
    program = _street_corridor(body)
    laserfuck = esolangs.transpile("Streetcode", "LaserFuck", program)
    assert esolangs.run("Streetcode", program, stdin) == esolangs.run(
        "LaserFuck", laserfuck, stdin
    )


def test_streetcode_pinned_outputs() -> None:
    """A subset with pinned output, so the battery checks more than agreement."""
    pinned = {
        "C" + "^" * 65 + "O;": "A",
        "C^^^O;": "\x03",
        "C^^=^^O;": "\x02",
    }
    for body, expected in pinned.items():
        laserfuck = esolangs.transpile(
            "Streetcode", "LaserFuck", _street_corridor(body)
        )
        assert esolangs.run("LaserFuck", laserfuck) == expected


def test_streetcode_grid_is_rectangular_with_start_and_marker() -> None:
    """The output is a LaserFuck grid with the byte-mode marker and a start."""
    laserfuck = esolangs.transpile("Streetcode", "LaserFuck", _street_corridor("C^^O;"))
    lines = laserfuck.splitlines()
    assert lines[0][0] == "\u00ff"
    assert any("o" in line for line in lines)


@pytest.mark.parametrize(
    "program",
    [
        pytest.param(STREET_COUNTING_LOOP, id="counting-loop"),
        pytest.param(STREET_RING, id="ring"),
        pytest.param(esolangs.generate("Streetcode", "A"), id="text-generator"),
    ],
)
def test_streetcode_drawn_control_flow_is_rejected(program: str) -> None:
    """A tape-steered square is refused, not mistranslated.

    All three drawings run correctly on Streetcode; none has a brainfuck
    loop image, because the car never returns to the junction that steers
    it as the same drive state.  ``match`` is a substring search, so the
    message is also asserted whole.
    """
    with pytest.raises(ValueError, match="the car steers on the tape") as caught:
        esolangs.transpile("Streetcode", "LaserFuck", program)
    assert "drawn control flow is out of the supported class" in str(caught.value)


def test_streetcode_boolean_generator_is_out_of_class() -> None:
    """The boolean generator draws decision trees, which are out of class."""
    from esolangs.tools import boolean

    with pytest.raises(ValueError, match="the car steers on the tape"):
        esolangs.transpile("Streetcode", "LaserFuck", boolean.streetcode("0001"))


def test_streetcode_multiple_outputs_are_rejected() -> None:
    """LaserFuck prints its tape once, so only a single final ``O`` is in class."""
    with pytest.raises(ValueError, match="must be the last command"):
        esolangs.transpile("Streetcode", "LaserFuck", _street_corridor("C^O^O;"))


# A ring road two lanes wide around a solid island, with no ';' anywhere:
# the car laps it forever.  Nothing on it steers, so this is the one
# rejection that reaches the walk's cycle guard rather than its junction
# check.
STREET_DONUT = "\n".join(
    [
        "+------+",
        "|C     |",
        "|      |",
        "|  --  |",
        "|  --  |",
        "|      |",
        "|      |",
        "+------+",
    ]
)


def test_streetcode_endless_ring_is_rejected() -> None:
    """A ring with nothing to stop the car has nothing to translate.

    The interpreter validates that the car can always drive *out* of a
    square, not that it ever stops, so a program that never halts reaches
    the transpiler intact and the walk has to notice the repeat itself.
    """
    with pytest.raises(ValueError, match="nothing to stop it") as caught:
        esolangs.transpile("Streetcode", "LaserFuck", STREET_DONUT)
    assert "the program does not halt" in str(caught.value)


# ~4.4s per parameter: the cost is generating the Streetcode text program
# and transpiling it, not the class assertion, so every parameter pays it
# and the marker goes on the whole family.
@pytest.mark.slow
@pytest.mark.parametrize("text", ["A", "x", "Z", "0"])
def test_streetcode_unwrapped_text_generator_is_in_class(text: str) -> None:
    """The text generator's own output transpiles, so long as it is not folded.

    The generator draws a single straight street with no branching, which
    is exactly the supported class -- but only at a width that keeps it on
    one row.  The default folds the line into a boustrophedon, and the fold
    is a ring the car steers around, so the wrapped form is rejected.
    """
    program = esolangs.generate("Streetcode", text, 100_000)
    laserfuck = esolangs.transpile("Streetcode", "LaserFuck", program)
    assert esolangs.run("LaserFuck", laserfuck) == esolangs.run("Streetcode", program)


def test_streetcode_wrapped_text_generator_is_rejected() -> None:
    """The default (folded) form of the same program is out of class."""
    with pytest.raises(ValueError, match="the car steers on the tape"):
        esolangs.transpile(
            "Streetcode", "LaserFuck", esolangs.generate("Streetcode", "A")
        )


# 2.2s, and the same generator build as the family above.
@pytest.mark.slow
def test_streetcode_multi_character_text_hits_the_output_convention() -> None:
    """Longer texts are refused by the target, not by the control-flow wall.

    A LaserFuck program prints its tape once when the last laser dies, so
    it carries a single ``O``; the generator emits one per character.
    """
    program = esolangs.generate("Streetcode", "hi", 100_000)
    with pytest.raises(ValueError, match="must be the last command"):
        esolangs.transpile("Streetcode", "LaserFuck", program)
