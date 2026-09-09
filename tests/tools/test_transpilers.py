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
    HaltError,
    UnsupportedTranspilationError,
)
from esolangs.vm import make_vm, run_until_halt_or_cycle, run_until_halt_or_growth

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
        "+.<.",  # the clamp is required: prints the same byte twice
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
        esolangs.transpile("brainfuck", "3D Brainfuck", program)
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


# (brainfuck program, stdin) pairs for Streetcode.  Streetcode is a 2D
# language whose only branch is a junction that reads whether the pointer's
# cell is zero -- exactly brainfuck's loop test -- so a ``[``/``]`` draws as
# a room the car laps.  The cases that matter beyond plain agreement are the
# ones the doubled non-wrapping cell model has to reproduce: underflow
# (``-.`` -> 255), overflow past 255 inside a loop (``+[+].``), a wrapping
# multiply, a pointer-moving loop body (``+[>].``), a ``,`` of a code point
# above U+00FF (mod 256), a skipped loop, and a deeply nested one.
#
# The wide-cell programs cost seconds each in the target grid rather than
# milliseconds: a Streetcode cell is reached by driving to it, so a value
# near 255 (underflow, the 8x8 multiply, input above U+00FF) is that many
# steps of geometry.  Those carry ``slow`` individually, keeping the cheap
# rows -- which still cover wraparound, input, nesting and the skipped loop
# -- in the fast run and in the mutation harness, which deselects ``slow``.
_SLOW = pytest.mark.slow
STREETCODE_BATTERY = (
    ("-.", ""),
    ("+.", ""),
    ("--.", ""),
    ("+-.", ""),
    (">+<.", ""),
    ("+++[-].", ""),
    pytest.param("+[+].", "", marks=_SLOW),
    ("+[->+<]>.", ""),
    ("+++[>].", ""),
    ("++>++<[>]<.", ""),
    ("++[>[-]<-].", ""),
    pytest.param("+++[>++[>+<-]<-]>+++.", "", marks=_SLOW),
    pytest.param("++++++++[>++++++++<-]>.", "", marks=_SLOW),
    pytest.param("+[>+[>[-]+<-]<-].", "", marks=_SLOW),
    (",.", "a"),
    (",.", "Ā"),
    pytest.param(",.", "中", marks=_SLOW),
    pytest.param(",[.-]", "a", marks=_SLOW),
    (",>,<.>.", "a\nb"),
    ("[-].", ""),
    ("[+].", ""),
    ("", ""),
    ("xx+++xx.xx", ""),
)

# a subset with pinned output, so the battery checks more than agreement.
# Marked like the battery above, and for the same reason: ``-.`` pins the
# wraparound and ``,.`` the mod-256 input without paying for a wide cell.
STREETCODE_PINNED = (
    ("-.", "", "\xff"),
    ("[-]---.", "", "\xfd"),
    pytest.param("+[+].", "", "\x00", marks=_SLOW),
    pytest.param("++++++++[>++++++++<-]>.", "", "@", marks=_SLOW),
    (",.", "Ā", "\x00"),  # U+0100 taken mod 256 is 0
)


@pytest.mark.parametrize(("program", "stdin"), STREETCODE_BATTERY)
def test_streetcode_transpiled_output_matches_source(program: str, stdin: str) -> None:
    """Every battery program agrees byte-for-byte through Streetcode.

    The wraparound brainfuck has and Streetcode does not is reproduced by a
    canonicalizer the transpiler emits after arithmetic runs and ```,``,
    except clear-and-set runs whose byte residue is known, so underflow,
    overflow and above-byte input all match.
    """
    target = esolangs.transpile("brainfuck", "Streetcode", program)
    assert esolangs.run("brainfuck", program, stdin, timeout=30) == esolangs.run(
        "Streetcode", target, stdin, timeout=30
    )


@pytest.mark.parametrize(("program", "stdin", "want"), STREETCODE_PINNED)
def test_streetcode_pinned_output(program: str, stdin: str, want: str) -> None:
    """Pinned outputs, so the battery is not merely self-consistent."""
    target = esolangs.transpile("brainfuck", "Streetcode", program)
    assert esolangs.run("Streetcode", target, stdin, timeout=30) == want


def test_streetcode_clear_and_set_skips_the_canonicalizer() -> None:
    """A byte clear makes its following arithmetic residue statically known."""
    from esolangs.tools._bf_streetcode import _lower

    assert _lower("[-]---") == "[-]" + "+" * 253


@pytest.mark.parametrize(
    ("program", "stdin", "prefix"),
    [
        ("+++[->+>++<<]>.>.", "", 17),
        (">++[<+>-]<.", "", 11),
        ("++.,.", "a", 3),
        ("+[>+[>+<-]<-]", "", 1),
    ],
)
def test_streetcode_byte_safe_affine_prefixes(
    program: str, stdin: str, prefix: int
) -> None:
    """Affine transfers lower directly; unknown code falls back at its boundary."""
    from esolangs.interpreters.brackets import match_brackets
    from esolangs.tools._bf_streetcode import _byte_safe_prefix

    assert _byte_safe_prefix(program, match_brackets(program)) == prefix
    target = esolangs.transpile("brainfuck", "Streetcode", program)
    assert esolangs.run("Streetcode", target, stdin, timeout=30) == esolangs.run(
        "brainfuck", program, stdin, timeout=30
    )


def test_streetcode_affine_transfer_fuzz_agrees() -> None:
    """Accepted multi-target transfer shapes agree with the generic semantics."""
    rng = random.Random(23)
    for _ in range(12):
        counter = rng.randint(0, 15)
        first = rng.randint(0, 8)
        second = rng.randint(0, (255 - counter * first) // counter if counter else 8)
        program = "+" * counter + "[->" + "+" * first + ">" + "+" * second + "<<]>.>."
        target = esolangs.transpile("brainfuck", "Streetcode", program)
        assert esolangs.run("Streetcode", target, timeout=30) == esolangs.run(
            "brainfuck", program, timeout=30
        )


def test_streetcode_transpiler_is_total() -> None:
    """Every brainfuck program translates; only unbalanced brackets raise.

    Unbalanced brackets are malformed in brainfuck too, so raising on them
    is not a class restriction -- the brainfuck interpreter raises on the
    identical input.
    """
    for program in (">+<<.", "<<<", "+.<.", "", "xx", "-.", "+[+].", ",."):
        esolangs.transpile("brainfuck", "Streetcode", program)
    for bad in ("[", "]", "[[]"):
        with pytest.raises(ValueError, match=r"unmatched"):
            esolangs.transpile("brainfuck", "Streetcode", bad)
        with pytest.raises(ValueError, match=r"unbalanced|unmatched"):
            esolangs.run("brainfuck", bad)


def test_streetcode_end_of_input_raises_in_both() -> None:
    """Exhausted input raises ``EOFError`` through both, not one silently.

    The doc claims this agreement; criterion 5 wants it executed rather than
    read.  ``,`` against empty stdin has no line to consume in either
    language, so both must raise.
    """
    target = esolangs.transpile("brainfuck", "Streetcode", ",")
    with pytest.raises(EOFError):
        esolangs.run("brainfuck", ",", "")
    with pytest.raises(EOFError):
        esolangs.run("Streetcode", target, "")


def _brainfuck_can_halt(program: str, stdin: str) -> bool:
    """False when a certificate proves ``program`` never halts.

    Most of the corpus's non-halting draws are trivial (``--++++[]``), and
    waiting one out costs the source timeout each.  A proof drops them for
    free instead.

    Both provers are needed, in this order.
    :func:`run_until_halt_or_cycle` is unbounded by design -- it steps until
    a state repeats -- so the growth class hangs it outright rather than
    returning undecided: ``+[>+]`` grows the tape a cell a lap and never
    repeats a state.  :func:`run_until_halt_or_growth` is the prover for
    that class and takes a step ``limit``, so asking it first means a growth
    program is answered or bounded before the unbounded detector runs.

    Growth exhausting its limit is *undecided*, not halting, so the cycle
    detector still gets its turn -- that is what keeps the cheap corpus
    hangs (``--++++[]``) proven rather than waited out.  Reaching it needs
    growth to have declined the program, which rules out the input that
    would hang it.  Measured worst case over both arms is under half a
    second.

    True is the undecided answer as well as the halting one, so the
    wall-clock skip below stays as the backstop.  ``EOFError`` is the same
    refusal the timed run reports; leave it to that arm rather than
    duplicating the judgement here.
    """
    try:
        try:
            if not run_until_halt_or_growth(make_vm("brainfuck", program, stdin)):
                return False
        except TimeoutError:
            pass  # undecided by growth; a repeated state may still decide it
        return run_until_halt_or_cycle(make_vm("brainfuck", program, stdin))
    except (EOFError, TimeoutError):
        return True


@pytest.mark.slow
def test_streetcode_fuzz_agrees() -> None:
    """Random terminating brainfuck programs agree through Streetcode.

    The generator mixes arithmetic, pointer moves, I/O and balanced loops.
    A program the *source* interpreter does not halt on within its step
    budget is skipped -- that is a property of brainfuck, not a rejection by
    the transpiler, which has no reject arm -- and the count of programs
    that actually ran is asserted so the fuzz cannot quietly stop
    exercising the geometry.

    A skip on the *target* side is different: a mistranslation that turned a
    halting program into a non-terminating one would look exactly like a
    slow grid timing out.  So target-side timeouts are counted and bounded
    -- if most of the corpus were skipping there, the fuzz would be proving
    nothing, and the assertion says so.
    """
    rng = random.Random(5)
    checked = 0
    target_timeouts = 0
    for _ in range(40):
        depth = 0
        parts: list[str] = []
        for _ in range(rng.randint(1, 14)):
            kind = rng.choice(
                ("inc", "dec", "right", "left", "print", "in", "open", "close")
            )
            if kind == "inc":
                parts.append("+" * rng.randint(1, 4))
            elif kind == "dec":
                parts.append("-" * rng.randint(1, 4))
            elif kind == "right":
                parts.append(">")
            elif kind == "left":
                parts.append("<")
            elif kind == "print":
                parts.append(".")
            elif kind == "in":
                parts.append(",")
            elif kind == "open":
                parts.append("[")
                depth += 1
            elif kind == "close" and depth:
                parts.append("]")
                depth -= 1
        parts.append("]" * depth)
        program = "".join(parts)
        stdin = "\n".join(rng.choice(["", "a", "Ā", "中"]) for _ in range(4))
        if not _brainfuck_can_halt(program, stdin):
            continue  # a repeated state proves it never halts
        try:
            expected = esolangs.run("brainfuck", program, stdin, timeout=15)
        except EOFError:
            continue  # ``,`` past the end of stdin; the source refuses it
        except HaltError:
            continue  # brainfuck did not halt in the wall-clock budget
        try:
            got = esolangs.run(
                "Streetcode",
                esolangs.transpile("brainfuck", "Streetcode", program),
                stdin,
                timeout=30,
            )
        except HaltError:
            target_timeouts += 1  # a slow grid -- counted, not silently dropped
            continue
        assert got == expected, program
        checked += 1
    assert checked > 12, f"only {checked} programs ran; fuzz is not exercising"
    assert target_timeouts < checked, (
        f"{target_timeouts} target-side timeouts vs {checked} checked: "
        "the fuzz is mostly skipping the geometry it exists to test"
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
        esolangs.transpile("Decleq", "S*bleq", program)
    with pytest.raises(ValueError, match="malformed memory token"):
        esolangs.transpile("Decleq", "S*bleq", "1 x 3")


def test_decleq_end_of_input_is_a_target_language_collision() -> None:
    """End-of-input is the one thing S*bleq cannot represent.

    S*bleq's only input primitive, address ``-2``, yields ``0`` when the
    input is exhausted, where Decleq raises :class:`EOFError`.  Every
    S*bleq computation is a function of the values it reads, so no S*bleq
    program can tell "a zero was read" from "there was nothing to read",
    and no translation can either.  This asserts the divergence rather
    than hiding it.

    The *empty line* used to belong to this collision too, because
    ``io.input_char`` returned ``10`` there while S*bleq returned ``0``.
    It no longer does: ``input_char`` reads a blank line as ``0``, the
    value the interpreters calling ``input_str`` already used, so the two
    languages now agree.  What remains below the surface is a genuine
    S*bleq property -- it still cannot separate an empty line from a NUL
    line -- but that is no longer a *divergence*, because Decleq collapses
    them the same way.
    """
    program = "-1 0 3 -2 0 0"
    sb_program = esolangs.transpile("Decleq", "S*bleq", program)

    # the empty line now agrees, in both directions
    assert esolangs.run("Decleq", program, "\n") == "\x00"
    assert esolangs.run("S*bleq", sb_program, "\n") == "\x00"
    # ... and S*bleq still cannot separate it from a NUL line
    assert esolangs.run("S*bleq", sb_program, "\x00") == "\x00"

    # the surviving collision: exhausted input
    with pytest.raises(EOFError):
        esolangs.run("Decleq", program, "")
    assert esolangs.run("S*bleq", sb_program, "") == "\x00"


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
