"""Verify the transpilers.

The contract is that a program and its translation are interchangeable:
the translation runs to identical output through the target interpreter.
Every transpiler here is *total* over its source language -- the admission
criteria in ``esolangs.tools.transpilers`` say why partial ones are not
carried -- so each section pairs a pinned battery with a fuzz that has no
rejection skip-arm.
"""

import random

import pytest

import esolangs
from esolangs.exceptions import (
    EsolangError,
    UnsupportedTranspilationError,
)

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


def test_unsupported_pair_raises() -> None:
    with pytest.raises(UnsupportedTranspilationError):
        esolangs.transpile("brainfuck", "Unsquare", "x")
    with pytest.raises(UnsupportedTranspilationError):
        esolangs.transpile("Sophie", "Modulous", "x")
    assert issubclass(UnsupportedTranspilationError, EsolangError)
    assert issubclass(UnsupportedTranspilationError, ValueError)


@pytest.mark.parametrize(
    "pair",
    [
        ("brainfuck", "Circlefuck"),
        ("brainfuck", "6-5"),
        ("Basicfuck", "brainfuck"),
        ("BIO", "brainfuck"),
        ("Dimensional", "LaserFuck"),
        ("Streetcode", "LaserFuck"),
    ],
)
def test_partial_transpilers_are_not_offered(pair: tuple[str, str]) -> None:
    """The six partial transpilers were removed, not merely documented.

    Each rejected programs its source language accepts, or -- for BIO --
    mistranslated them silently.  The admission criteria in
    ``esolangs.tools.transpilers`` set the bar they failed.
    """
    with pytest.raises(UnsupportedTranspilationError):
        esolangs.transpile(pair[0], pair[1], "+")


def test_listed_transpilers_are_known_languages() -> None:
    """Every transpiler source and target is a registered language."""
    from esolangs.tools.transpilers import TRANSPILERS

    known = set(esolangs.list_languages())
    for source, target in TRANSPILERS:
        assert source in known
        assert target in known


# 3D Brainfuck and Painfuck are brainfuck supersets, so every battery
# program must agree byte-for-byte through the target interpreter.  3D
# Brainfuck's ``s`` walks negative where brainfuck clamps ``<``, but the
# translation guards ``<`` at runtime, so nothing is out of class -- the
# program that dips below cell 0 (``>+<<.``) is included.
THREE_D_BATTERY = BATTERY
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
def test_three_d_bf_swaps_right_and_guards_left(program: str) -> None:
    """``>`` is a plain ``n``; ``<`` carries its clamp guard."""
    target = esolangs.transpile("brainfuck", "3D Brainfuck", program)
    assert target == "su+dn" + program.replace(">", "n").replace("<", "su[dnu]d")


@pytest.mark.parametrize("program", ["+", "+[>+<-]>.", ",>,<.>."])
def test_three_d_bf_transpile_drops_comments(program: str) -> None:
    """Non-command characters are dropped, because they are commands here.

    Brainfuck's comment characters include ``n``, ``s``, ``e``, ``w``,
    ``u`` and ``d``, every one of which moves 3D Brainfuck's array
    pointer.  Passing them through mistranslates
    (:func:`test_three_d_bf_comment_characters_are_commands`), so the
    translation emits only the eight brainfuck commands.
    """
    commented = "xx" + program + "yy"
    target = esolangs.transpile("brainfuck", "3D Brainfuck", commented)
    assert target == esolangs.transpile("brainfuck", "3D Brainfuck", program)
    assert "x" not in target
    assert "y" not in target


@pytest.mark.parametrize(
    "program", ["+.n.", "+.hello.", "+.send.", "+n.>.", "xx+++xx.xx"]
)
def test_three_d_bf_comment_characters_are_commands(program: str) -> None:
    """Comment text that reads as array moves must not change the output.

    Each of these silently mistranslated while comments were passed
    through -- ``hello`` and ``send`` move the pointer twice apiece -- so
    they are pinned against the brainfuck reference.
    """
    target = esolangs.transpile("brainfuck", "3D Brainfuck", program)
    assert esolangs.run("brainfuck", program) == esolangs.run("3D Brainfuck", target)


def test_three_d_bf_transpile_empty() -> None:
    """An empty program still carries the guard's sentinel prefix."""
    assert esolangs.transpile("brainfuck", "3D Brainfuck", "") == "su+dn"
    assert esolangs.run("3D Brainfuck", "su+dn") == ""


def test_painfuck_transpile_empty() -> None:
    assert esolangs.transpile("brainfuck", "Painfuck", "") == ""


def test_three_d_bf_fuzz_agrees() -> None:
    """Random brainfuck programs agree through 3D Brainfuck.

    Nothing is out of class now that ``<`` is guarded, so the generator is
    free to walk left past cell 0 and lean on brainfuck's clamp.
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
                # deliberately unbounded: dipping below cell 0 is in class
                parts.append("<" * rng.randint(1, 3))
            elif kind == "inc":
                parts.append("+" * rng.randint(1, 5))
            elif kind == "dec":
                parts.append("-" * rng.randint(1, 5))
            elif kind == "print":
                parts.append(".")
            else:
                parts.append("[-]")
        program = "".join(parts)
        target = esolangs.transpile("brainfuck", "3D Brainfuck", program)
        expected = esolangs.run("brainfuck", program)
        assert esolangs.run("3D Brainfuck", target) == expected


def test_painfuck_fuzz_agrees() -> None:
    """Random terminating brainfuck programs agree through Painfuck.

    The skip arm catches only :class:`EOFError` -- a ``,`` drawn against
    the empty stdin, which the *source* interpreter refuses -- so it can
    never swallow a rejection by the transpiler itself.  Two thirds of the
    draws contain such a ``,``, so the run count is asserted rather than
    assumed: an unasserted skip arm is what lets a fuzz quietly stop
    exercising the thing it names.
    """
    rng = random.Random(11)
    checked = 0
    for _ in range(60):
        # straight-line programs always terminate (loops can run forever)
        program = "".join(rng.choice("+-<>.,") for _ in range(rng.randint(1, 16)))
        try:
            expected = esolangs.run("brainfuck", program)
        except EOFError:
            continue  # ``,`` with no stdin; the source interpreter refuses
        target = esolangs.transpile("brainfuck", "Painfuck", program)
        assert esolangs.run("Painfuck", target) == expected
        checked += 1
    assert checked > 15, f"only {checked} programs ran; fuzz is not exercising"


@pytest.mark.parametrize(
    "program",
    [
        ">+<<.",  # walks past the left edge
        "<",  # a bare left move on the empty tape
        "+.<.",  # the clamp is load-bearing: prints the same byte twice
        "+.<<<<<<.",  # a deep dip still lands on cell 0
        "++>+[<-].",  # the drift a static scan misses: the loop repeats
        "++[>+<-]<<.>.",  # guards nested inside the program's own loop
        "+++[<->-]<.",  # a guard whose loop runs every lap
    ],
)
def test_three_d_bf_clamps_at_cell_zero(program: str) -> None:
    """Brainfuck's clamp is emulated, so dipping left is in class.

    ``<`` compiles to a runtime guard rather than a bare ``s``.  These
    programs were previously rejected or -- for ``++>+[<-].``, whose dip
    only happens on the loop's later laps -- silently mistranslated into a
    program that never halts.
    """
    target = esolangs.transpile("brainfuck", "3D Brainfuck", program)
    assert esolangs.run("brainfuck", program) == esolangs.run("3D Brainfuck", target)


def test_three_d_bf_transpiler_is_total() -> None:
    """Every brainfuck program translates, none is rejected.

    Unbalanced brackets are carried through rather than caught here, which
    is what brainfuck itself does: both interpreters raise on them at run
    time, so the translation preserves that too.
    """
    for program in (">+<<.", "<<<", "+.<.", "", "xx", "++>+[<-].", "["):
        assert esolangs.transpile("brainfuck", "3D Brainfuck", program)
    for bad in ("[", "]", "[[]"):
        target = esolangs.transpile("brainfuck", "3D Brainfuck", bad)
        with pytest.raises(ValueError, match="unmatched"):
            esolangs.run("3D Brainfuck", target)
        with pytest.raises(ValueError, match=r"unbalanced|unmatched"):
            esolangs.run("brainfuck", bad)


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
    """Random programs of any shape agree with the Decleq interpreter.

    Decleq has no per-run instruction cap of its own (removed in favour of
    esolangs.run's uniform timeout), and an arbitrary cell draw can easily
    build a self-decrementing loop that never halts -- exactly the growth
    class the cycle detector cannot prove either.  ``timeout`` is what
    turns that into a fast HaltError the except clause below already
    catches, instead of a hang.

    **The timeout is the whole cost of this test.**  Twelve of the 120
    draws never halt, and each one waits out the full timeout; the other
    108 either halt or error immediately.  So the wall time is essentially
    twelve timeouts, and lowering it scales the test linearly -- 1.0s cost
    12.2s, 0.05s costs 0.8s -- while ``checked`` stays at 69 throughout,
    because a non-halting program is not recovered by *any* timeout.  The
    margin is not tight: the slowest program that does halt takes 0.343ms,
    so 0.05s still leaves ~145x headroom for a slower machine.
    """
    rng = random.Random(19)
    vals = [0, 1, 2, 3, 5, 9, -1, -2, -3, -7, 42, 127, 255, -255, 6, 12, 15, 4, 10]
    checked = 0
    for _ in range(120):
        cells = [rng.choice(vals) for _ in range(rng.randint(0, 12))]
        program = " ".join(map(str, cells))
        try:
            expected = esolangs.run("Decleq", program, timeout=0.05)
        except (EsolangError, EOFError, IndexError):
            continue  # the reference interpreter errors; no behaviour to match
        sb_program = esolangs.transpile("Decleq", "S*bleq", program)
        assert esolangs.run("S*bleq", sb_program) == expected
        checked += 1
    assert checked > 40, f"only {checked} programs terminated; fuzz is not exercising"


def test_decleq_fuzz_countdowns() -> None:
    """Random countdowns (the canonical ``x x next`` idiom) agree.

    The shape always halts by construction, but ``timeout`` is cheap
    insurance against the same class the unrestricted-programs test
    guards against, and keeps the two calling conventions matched -- at
    the same 0.05s, which these programs clear by three orders of
    magnitude.
    """
    rng = random.Random(23)
    checked = 0
    for _ in range(40):
        x = rng.randint(0, 25)
        program = f"{x} {x} 3 -2 {x} 0"
        try:
            expected = esolangs.run("Decleq", program, timeout=0.05)
        except (EsolangError, EOFError, IndexError):
            continue
        sb_program = esolangs.transpile("Decleq", "S*bleq", program)
        assert esolangs.run("S*bleq", sb_program) == expected
        checked += 1
    assert checked > 10, f"only {checked} countdowns terminated"


def test_assembler_rejects_a_duplicate_label() -> None:
    """A label may be attached to only one instruction.

    ``mark`` records where a label lands so later jumps can resolve it, so a
    second use would silently move an existing jump's target rather than
    add one.  The assemblers are internal, but the guard is what keeps a
    macro that mints its own labels from colliding with a hand-written one.
    """
    from esolangs.tools.transpilers import _SbleqAsm

    asm = _SbleqAsm()
    asm.mark("loop")
    with pytest.raises(ValueError, match="duplicate label loop"):
        asm.mark("loop")
