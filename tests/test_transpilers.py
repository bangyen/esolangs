"""Verify the transpilers.

The contract is that a brainfuck program and its translation are
interchangeable: the translation runs to identical output through the
target interpreter.  The ASCII-art transpilers are alphabet swaps whose
translation also recovers the source program exactly.  The CircleFuck
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

ascii_art = importlib.import_module("esolangs.interpreters.tape_based.ascii-art")


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
# [0, size) for the auto-sized bound, so it is in the CircleFuck
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
    art = esolangs.transpile("BF", "ASCII art", program)
    assert esolangs.run("BF", program, stdin) == esolangs.run("ASCII art", art, stdin)


@pytest.mark.parametrize(("program", "pair"), tuple(PINNED.items()))
def test_pinned_outputs(program: str, pair: tuple[str, str]) -> None:
    stdin, expected = pair
    assert esolangs.run("BF", program, stdin) == expected


@pytest.mark.parametrize(("program", "stdin"), BATTERY)
def test_parse_recovers_source(program: str, stdin: str) -> None:
    art = esolangs.transpile("BF", "ASCII art", program)
    assert ascii_art.parse(art) == _filter(program)


@pytest.mark.parametrize(("program", "stdin"), BATTERY)
def test_reverse_transpiler_recovers_source(program: str, stdin: str) -> None:
    """ASCII art -> BF inverts BF -> ASCII art for well-formed art."""
    art = esolangs.transpile("BF", "ASCII art", program)
    assert esolangs.transpile("ASCII art", "BF", art) == _filter(program)


@pytest.mark.parametrize(("program", "stdin"), BATTERY)
def test_reverse_transpiled_output_matches_source(program: str, stdin: str) -> None:
    art = esolangs.transpile("BF", "ASCII art", program)
    bf_program = esolangs.transpile("ASCII art", "BF", art)
    assert esolangs.run("BF", bf_program, stdin) == esolangs.run(
        "ASCII art", art, stdin
    )


def test_reverse_round_trips_art() -> None:
    """Re-encoding recovered art reproduces it byte for byte."""
    for program, _ in BATTERY:
        art = esolangs.transpile("BF", "ASCII art", program)
        assert (
            esolangs.transpile(
                "BF", "ASCII art", esolangs.transpile("ASCII art", "BF", art)
            )
            == art
        )


def test_reverse_empty_program() -> None:
    assert esolangs.transpile("ASCII art", "BF", "") == ""
    assert esolangs.transpile("BF", "ASCII art", "") == ""


@pytest.mark.parametrize("text", ["Hello, World!", "Hi", "\x00\x01"])
def test_generator_is_transpiled_generator(text: str) -> None:
    """The ASCII-art generator is exactly the BF generator, transpiled."""
    bf_program = esolangs.generate("BF", text)
    art = esolangs.transpile("BF", "ASCII art", bf_program)
    assert esolangs.generate("ASCII art", text) == art
    assert esolangs.run("ASCII art", art) == text


@pytest.mark.parametrize("text", ["Hello, World!", "Hi"])
def test_generator_inverse(text: str) -> None:
    """The reverse transpiler recovers the BF generator's program."""
    art = esolangs.generate("ASCII art", text)
    assert esolangs.transpile("ASCII art", "BF", art) == esolangs.generate("BF", text)


def test_empty_program_stays_empty() -> None:
    art = esolangs.transpile("BF", "ASCII art", "")
    assert art == ""
    assert esolangs.run("ASCII art", art) == ""


def test_unsupported_pair_raises() -> None:
    with pytest.raises(UnsupportedTranspilationError):
        esolangs.transpile("BF", "Unsquare", "x")
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
    circlefuck = esolangs.transpile("BF", "CircleFuck", program)
    assert esolangs.run("BF", program, stdin) == esolangs.run(
        "CircleFuck", circlefuck, stdin
    )


@pytest.mark.parametrize(("program", "stdin"), CIRCLEFUCK_BATTERY)
def test_circlefuck_explicit_size(program: str, stdin: str) -> None:
    """An explicit size is a larger-but-still-valid data region."""
    circlefuck = esolangs.transpile("BF", "CircleFuck", program, size=8)
    assert esolangs.run("BF", program, stdin) == esolangs.run(
        "CircleFuck", circlefuck, stdin
    )


@pytest.mark.parametrize("text", ["Hello, World!", "Hi", "123"])
def test_circlefuck_transpiles_generated_program(text: str) -> None:
    """The BF generator's output (single cell) transpiles and prints the text."""
    program = esolangs.generate("BF", text)
    circlefuck = esolangs.transpile("BF", "CircleFuck", program)
    assert esolangs.run("CircleFuck", circlefuck) == text


def test_circlefuck_left_edge_is_out_of_class() -> None:
    """Moving below cell 0 is outside the supported class.

    Brainfuck clamps ``<`` at the left edge; CircleFuck's pointer wraps to
    the end of the program, so the transpiler only guarantees equivalence
    for programs that stay in ``[0, size)``.
    """
    program = ">+<<."  # reads cell 1, then moves below cell 0
    circlefuck = esolangs.transpile("BF", "CircleFuck", program, size=4)
    assert esolangs.run("BF", program) != esolangs.run("CircleFuck", circlefuck)


def test_circlefuck_auto_size_rejects_below_zero() -> None:
    """Programs that dip below cell 0 are rejected rather than mistranslated."""
    with pytest.raises(ValueError, match="below cell 0"):
        esolangs.transpile("BF", "CircleFuck", ">+<<.")


def test_circlefuck_auto_size_rejects_drifting_loop() -> None:
    """Loops that drift the pointer unboundedly cannot be auto-sized."""
    with pytest.raises(ValueError, match="drift"):
        esolangs.transpile("BF", "CircleFuck", "+[>+]")


def test_circlefuck_auto_size_rejects_nested_drifting_loop() -> None:
    """Drift detected inside a nested loop is propagated out."""
    with pytest.raises(ValueError, match="drift"):
        esolangs.transpile("BF", "CircleFuck", "++[+[>+]]")


def test_circlefuck_unmatched_bracket_rejected() -> None:
    """Unbalanced brackets are malformed and rejected by both the source
    interpreter and the transpiler."""
    with pytest.raises(ValueError, match="unbalanced brackets"):
        esolangs.transpile("BF", "CircleFuck", "[")


def test_circlefuck_size_must_be_positive() -> None:
    with pytest.raises(ValueError, match="size must be positive"):
        esolangs.transpile("BF", "CircleFuck", "+.", size=0)


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
        circlefuck = esolangs.transpile("BF", "CircleFuck", program)
        assert esolangs.run("BF", program) == esolangs.run("CircleFuck", circlefuck)


@pytest.mark.parametrize("text", ["Hello, World!", "Hi", "123", "\x00\x01"])
def test_nocomment_transpiles_to_brainfuck(text: str) -> None:
    """NoComment programs print the same text through the BF interpreter."""
    program = esolangs.generate("NoComment", text)
    bf_program = esolangs.transpile("NoComment", "BF", program)
    assert esolangs.run("NoComment", program) == esolangs.run("BF", bf_program) == text


def test_nocomment_comments_are_dropped() -> None:
    program = "xyz " + "c" + "i" * 72 + "o" + " qwerty"
    bf_program = esolangs.transpile("NoComment", "BF", program)
    assert esolangs.run("BF", bf_program) == "H"


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
    bf_program = esolangs.transpile("BFStack", "BF", program)
    assert esolangs.run("BFStack", program, stdin) == esolangs.run(
        "BF", bf_program, stdin
    )


@pytest.mark.parametrize("text", ["Hello, World!", "Hi", "123"])
def test_bfstack_transpiles_generated_program(text: str) -> None:
    """The BFStack generator's output prints the same text as brainfuck."""
    program = esolangs.generate("BFStack", text)
    bf_program = esolangs.transpile("BFStack", "BF", program)
    assert esolangs.run("BF", bf_program) == text


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
        bf_program = esolangs.transpile("BFStack", "BF", program)
        assert esolangs.run("BFStack", program) == esolangs.run("BF", bf_program)


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
    bf_program = esolangs.transpile("BIO", "BF", program)
    assert esolangs.run("BIO", program, stdin) == esolangs.run("BF", bf_program, stdin)


@pytest.mark.parametrize("text", ["Hello, World!", "Hi", "123"])
def test_bio_transpiles_generated_program(text: str) -> None:
    """The BIO generator's output prints the same text as brainfuck."""
    program = esolangs.generate("BIO", text)
    bf_program = esolangs.transpile("BIO", "BF", program)
    assert esolangs.run("BF", bf_program) == text


def test_bio_comments_are_ignored() -> None:
    program = "hello there 0ox 1ix ok"
    bf_program = esolangs.transpile("BIO", "BF", program)
    assert esolangs.run("BIO", program) == esolangs.run("BF", bf_program) == "\x01"


def test_bio_register_wrap_is_out_of_class() -> None:
    """A register reaching a nonzero multiple of 256 is outside the class.

    BIO's registers are unbounded, so 256 is truthy for a loop condition;
    brainfuck cells wrap, so the same register reads as 0.
    """
    program = "0ox" * 256 + "0ix1ix1ox}"
    bf_program = esolangs.transpile("BIO", "BF", program)
    assert esolangs.run("BIO", program) != esolangs.run("BF", bf_program)


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
        bf_program = esolangs.transpile("BIO", "BF", program)
        assert esolangs.run("BIO", program) == esolangs.run("BF", bf_program)


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
    bf_program = esolangs.transpile("huf", "BF", program)
    assert esolangs.run("huf", program, stdin) == esolangs.run("BF", bf_program, stdin)


@pytest.mark.parametrize("text", ["Hello, World!", "Hi", "123"])
def test_huf_transpiles_generated_program(text: str) -> None:
    """The huf generator's output prints the same text as brainfuck."""
    program = esolangs.generate("huf", text)
    bf_program = esolangs.transpile("huf", "BF", program)
    assert esolangs.run("BF", bf_program) == text


def test_huf_comments_are_ignored() -> None:
    program = "hello #+++>@ world"
    bf_program = esolangs.transpile("huf", "BF", program)
    assert esolangs.run("huf", program) == esolangs.run("BF", bf_program) == "\x03"


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
        bf_program = esolangs.transpile("huf", "BF", program)
        assert esolangs.run("huf", program) == esolangs.run("BF", bf_program)


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
    six_five = esolangs.transpile("BF", "6-5", program)
    assert esolangs.run("BF", program, stdin) == esolangs.run("6-5", six_five, stdin)


def test_six_five_transpiles_generated_program() -> None:
    """The BF generator's output (single cell) transpiles and prints the text."""
    text = "Hello, World!"
    program = esolangs.generate("BF", text)
    six_five = esolangs.transpile("BF", "6-5", program)
    assert esolangs.run("6-5", six_five) == text


def test_six_five_loop_cap() -> None:
    """More than 18 loops (36 markers) cannot be labelled."""
    with pytest.raises(ValueError, match="18 loops"):
        esolangs.transpile("BF", "6-5", "[-]" * 19)


def test_six_five_unbalanced_brackets_rejected() -> None:
    with pytest.raises(ValueError, match="unbalanced"):
        esolangs.transpile("BF", "6-5", "+[")
