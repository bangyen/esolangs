"""Verify the transpilers.

The contract is that a brainfuck program and its translation are
interchangeable: the translation runs to identical output through the
target interpreter.  The ASCII-art transpilers are alphabet swaps whose
translation also recovers the source program exactly.  The Circlefuck
transpiler is a real program transformation (its tape is the program
itself), so it targets the class of brainfuck programs whose data pointer
stays within ``[0, size)``; a battery plus a fuzz of bounded, terminating
programs verifies that class.
"""

import importlib
import random

import pytest

import esolangs
from esolangs.exceptions import (
    EsolangError,
    UnsupportedTranspilationError,
)

ascii_art = importlib.import_module("esolangs.interpreters.tape_based.ascii_art")


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


def _filter(program: str) -> str:
    return "".join(c for c in program if c in "+-<>.,[]")


@pytest.mark.parametrize(("program", "stdin"), BATTERY)
def test_transpiled_output_matches_source(program: str, stdin: str) -> None:
    art = esolangs.transpile("brainfuck", "ASCII art", program)
    assert esolangs.run("brainfuck", program, stdin) == esolangs.run(
        "ASCII art", art, stdin
    )


@pytest.mark.parametrize(("program", "pair"), tuple(PINNED.items()))
def test_pinned_outputs(program: str, pair: tuple[str, str]) -> None:
    stdin, expected = pair
    assert esolangs.run("brainfuck", program, stdin) == expected


@pytest.mark.parametrize(("program", "stdin"), BATTERY)
def test_parse_recovers_source(program: str, stdin: str) -> None:
    art = esolangs.transpile("brainfuck", "ASCII art", program)
    assert ascii_art.parse(art) == _filter(program)


@pytest.mark.parametrize(("program", "stdin"), BATTERY)
def test_reverse_transpiler_recovers_source(program: str, stdin: str) -> None:
    """ASCII art -> BF inverts BF -> ASCII art for well-formed art."""
    art = esolangs.transpile("brainfuck", "ASCII art", program)
    assert esolangs.transpile("ASCII art", "brainfuck", art) == _filter(program)


@pytest.mark.parametrize(("program", "stdin"), BATTERY)
def test_reverse_transpiled_output_matches_source(program: str, stdin: str) -> None:
    art = esolangs.transpile("brainfuck", "ASCII art", program)
    bf_program = esolangs.transpile("ASCII art", "brainfuck", art)
    assert esolangs.run("brainfuck", bf_program, stdin) == esolangs.run(
        "ASCII art", art, stdin
    )


def test_reverse_round_trips_art() -> None:
    """Re-encoding recovered art reproduces it byte for byte."""
    for program, _ in BATTERY:
        art = esolangs.transpile("brainfuck", "ASCII art", program)
        assert (
            esolangs.transpile(
                "brainfuck",
                "ASCII art",
                esolangs.transpile("ASCII art", "brainfuck", art),
            )
            == art
        )


def test_reverse_empty_program() -> None:
    assert esolangs.transpile("ASCII art", "brainfuck", "") == ""
    assert esolangs.transpile("brainfuck", "ASCII art", "") == ""


@pytest.mark.parametrize("text", ["Hello, World!", "Hi", "\x00\x01"])
def test_generator_is_transpiled_generator(text: str) -> None:
    """The ASCII-art generator is exactly the BF generator, transpiled."""
    bf_program = esolangs.generate("brainfuck", text)
    art = esolangs.transpile("brainfuck", "ASCII art", bf_program)
    assert esolangs.generate("ASCII art", text) == art
    assert esolangs.run("ASCII art", art) == text


@pytest.mark.parametrize("text", ["Hello, World!", "Hi"])
def test_generator_inverse(text: str) -> None:
    """The reverse transpiler recovers the BF generator's program."""
    art = esolangs.generate("ASCII art", text)
    assert esolangs.transpile("ASCII art", "brainfuck", art) == esolangs.generate(
        "brainfuck", text
    )


def test_empty_program_stays_empty() -> None:
    art = esolangs.transpile("brainfuck", "ASCII art", "")
    assert art == ""
    assert esolangs.run("ASCII art", art) == ""


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
    ],
)
def test_laserfuck_out_of_class_rejected(program: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        esolangs.transpile("Dimensional", "LaserFuck", program)


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
    ("0ox1ix", ""),
    ("0oy1iy", ""),
    ("0oz1iz", ""),
    ("1ix", ""),
    ("0ox0ox1ix", ""),
    ("0ox0oy0ix1iy1ox}", ""),
    ("0ox0oy0oz0iy1iz1oy}", ""),
    ("1ix1ix", ""),
    ("0ox0oz0iz1ix1oz}", ""),
    ("0ox0oy0ox0iy1iy1oy1ix1ox}", ""),
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
    program = "hello there 0ox 1ix ok"
    bf_program = esolangs.transpile("BIO", "brainfuck", program)
    assert (
        esolangs.run("BIO", program) == esolangs.run("brainfuck", bf_program) == "\x01"
    )


def test_bio_unbalanced_loops_rejected() -> None:
    """A stray '}' or an unclosed '0i' is rejected, not crashed on."""
    with pytest.raises(ValueError, match="unmatched"):
        esolangs.transpile("BIO", "brainfuck", "}")
    with pytest.raises(ValueError, match="unclosed"):
        esolangs.transpile("BIO", "brainfuck", "0ix0iy")


def test_bio_register_wrap_is_out_of_class() -> None:
    """A register reaching a nonzero multiple of 256 is outside the class.

    BIO's registers are unbounded, so 256 is truthy for a loop condition;
    brainfuck cells wrap, so the same register reads as 0.
    """
    program = "0ox" * 256 + "0ix1ix1ox}"
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
                parts.append("0o" + "xyz"[r])
                reg[r] += 1
            elif kind == "dec":
                parts.append("1o" + "xyz"[r])
                reg[r] -= 1
            elif kind == "out":
                parts.append("1i" + "xyz"[r])
            else:
                move = "1o" if reg[r] > 0 else "0o" if reg[r] < 0 else ""
                body = move + "xyz"[r]
                if move and rng.random() < 0.5:
                    body += "1i" + "xyz"[rng.randrange(3)]
                parts.append("0i" + "xyz"[r] + body + "}")
                reg[r] = 0
        program = "".join(parts)
        bf_program = esolangs.transpile("BIO", "brainfuck", program)
        assert esolangs.run("BIO", program) == esolangs.run("brainfuck", bf_program)


# (Huf program, stdin) pairs; Huf is straight line, so every program
# terminates and the transpiler's mul-tracking is exact.
HUF_BATTERY = (
    ("#+++>@", ""),
    ("#+++++>@", ""),
    ("#+|+!>@", ""),
    ("#+++|+++!>@", ""),
    ("#+++++|++++!>@", ""),
    ("#+++|+!>@", ""),
    ("#|+!>@", ""),
    ("#+++>@#++>@", ""),
    ("#+++|++!+>@", ""),
    ("#|>@", ""),
    ("#+|++++!>@", ""),
    ("#+++++++|+++!>@", ""),
)


@pytest.mark.parametrize(("program", "stdin"), HUF_BATTERY)
def test_huf_transpiles_to_brainfuck(program: str, stdin: str) -> None:
    bf_program = esolangs.transpile("huf", "brainfuck", program)
    assert esolangs.run("huf", program, stdin) == esolangs.run(
        "brainfuck", bf_program, stdin
    )


@pytest.mark.parametrize("text", ["Hello, World!", "Hi", "123"])
def test_huf_transpiles_generated_program(text: str) -> None:
    """The huf generator's output prints the same text as brainfuck."""
    program = esolangs.generate("huf", text)
    bf_program = esolangs.transpile("huf", "brainfuck", program)
    assert esolangs.run("brainfuck", bf_program) == text


def test_huf_comments_are_ignored() -> None:
    program = "hello #+++>@ world"
    bf_program = esolangs.transpile("huf", "brainfuck", program)
    assert (
        esolangs.run("huf", program) == esolangs.run("brainfuck", bf_program) == "\x03"
    )


def test_huf_fuzz_segments() -> None:
    """Random straight-line segment programs agree.

    The fuzz tracks num/mul so it only emits ops Huf can run: ``!`` is only
    emitted when it keeps ``num`` in ``chr()`` range (Huf's ``>`` crashes on
    a value outside 0-255), and ``!`` with mul == 0 is skipped (it would
    make num negative).
    """
    rng = random.Random(13)
    for _ in range(60):
        parts: list[str] = []
        for _ in range(rng.randint(1, 4)):
            seg = "#"
            num = mul = 0
            for _ in range(rng.randint(1, 8)):
                kind = rng.choice(("inc", "set", "mul", "out"))
                if kind == "inc" or (
                    kind == "mul" and (not mul or num * (mul - 1) > 255)
                ):
                    if mul:
                        seg += "+"
                        mul += 1
                    else:
                        seg += "+"
                        num += 1
                elif kind == "set":
                    seg += "|"
                    mul = 1
                elif kind == "mul":
                    seg += "!"
                    num = num * (mul - 1)
                    mul = 0
                else:  # "out"
                    seg += ">"
                    num = 0
            parts.append(seg + "@")
        program = "".join(parts)
        bf_program = esolangs.transpile("huf", "brainfuck", program)
        assert esolangs.run("huf", program) == esolangs.run("brainfuck", bf_program)


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
    """More than 18 loops (36 markers) cannot be labelled."""
    with pytest.raises(ValueError, match="18 loops"):
        esolangs.transpile("brainfuck", "6-5", "[-]" * 19)


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


# (Decleq program, stdin) pairs; every program keeps its instruction pointer
# inside the original program and terminates.
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
)


@pytest.mark.parametrize(("program", "stdin"), DECLEQ_BATTERY)
def test_decleq_transpiles_to_sbleq(program: str, stdin: str) -> None:
    sb_program = esolangs.transpile("Decleq", "S*bleq", program)
    assert esolangs.run("Decleq", program, stdin) == esolangs.run(
        "S*bleq", sb_program, stdin
    )


def test_decleq_self_modifying_code_is_out_of_class() -> None:
    """A write that is re-read as an operand is rejected, not mistranslated."""
    program = "2 10 3 255 10 6 -10 16 9 -2 10 0 -2 10 0 -2 16 0"
    with pytest.raises(ValueError, match="self-modifying"):
        esolangs.transpile("Decleq", "S*bleq", program)


def test_decleq_non_triple_length_rejected() -> None:
    with pytest.raises(ValueError, match="multiple of three"):
        esolangs.transpile("Decleq", "S*bleq", "1 2")


def test_decleq_bad_jump_target_rejected() -> None:
    with pytest.raises(ValueError, match="multiples of three"):
        esolangs.transpile("Decleq", "S*bleq", "1 1 4 -2 1 0")


def test_decleq_negative_non_special_b_rejected() -> None:
    """A negative ``b`` other than the I/O specials has no S*bleq mapping."""
    with pytest.raises(ValueError, match="negative non-special b"):
        esolangs.transpile("Decleq", "S*bleq", "5 -2 3")


def test_decleq_fuzz_in_class_programs() -> None:
    """Random in-class programs (write targets outside the code) agree."""
    rng = random.Random(19)
    vals = [0, 1, 2, 3, 5, 9, 42, 127, 200, 255, -2, -3, -5, -10]
    for _ in range(200):
        k = rng.randint(1, 4)
        cells = []
        for i in range(k):
            cells.extend([rng.choice(vals), rng.randint(3 * k, 30), (i + 1) * 3])
        for i in range(k):
            cells.extend([-2, cells[i * 3 + 1], 0])
        cells.extend([-7, 0, -1])  # halt, so the pointer never runs off the end
        program = " ".join(map(str, cells))
        try:
            expected = esolangs.run("Decleq", program)
        except (EsolangError, EOFError):
            continue  # out of the terminating class; the transpiler halts early
        try:
            sb_program = esolangs.transpile("Decleq", "S*bleq", program)
        except ValueError:
            continue  # writes into reachable operands; self-modifying code
        assert esolangs.run("S*bleq", sb_program) == expected


def test_decleq_fuzz_countdowns() -> None:
    """Random countdowns (the canonical ``x x next`` idiom) agree."""
    rng = random.Random(23)
    for _ in range(80):
        x = rng.randint(0, 25)
        program = f"{x} {x} 3 -2 {x} 0"
        try:
            expected = esolangs.run("Decleq", program)
        except (EsolangError, EOFError):
            continue  # counters inside the code extend memory; out of class
        try:
            sb_program = esolangs.transpile("Decleq", "S*bleq", program)
        except ValueError:
            continue  # a counter cell doubled as a re-read operand
        assert esolangs.run("S*bleq", sb_program) == expected
