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


def test_circlefuck_unmatched_bracket_tolerated() -> None:
    """An unmatched bracket halts on both interpreters, so it is in class."""
    program = "["
    circlefuck = esolangs.transpile("BF", "CircleFuck", program)
    assert esolangs.run("BF", program) == esolangs.run("CircleFuck", circlefuck) == ""


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
