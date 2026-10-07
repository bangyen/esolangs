"""BrainIf, Circlefuck, Circuit Diagram, Clockwise, Container, CV(N)(C), Dig, EGL.

No other implementation exists, so each reference is a clean-room ("blind")
interpreter written from the wiki text alone (see ``differential.py``):
``--ref "env BLIND_STEP_LIMIT=100000 python3 BLIND/<slug>.py {program}"``.
CV(N)(C) is spelled in ASCII here (the harness writes programs as latin-1),
so its reference goes through this file's shim::

    --ref "python3 scripts/differential_blind_c2.py BLIND/cvnc.py {program}"

Container's reference reports EXIT's value on stderr; both sides append it
to the output as ``|exit N``.  ``differential.py`` imports ``SPECS``.
"""

from __future__ import annotations

import dataclasses
import os
import random
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

if __name__ != "__main__":
    # Imported by ``differential.py`` (as ``__main__`` or as a module).
    _h = sys.modules.get("differential") or sys.modules["__main__"]
    Spec, Outcome, blind_outcome = _h.Spec, _h.Outcome, _h.blind_outcome
    run_ours, run_ours_fast = _h.run_ours, _h.run_ours_fast


def _ascii(rng: random.Random, _program: str = "") -> str:
    pool = "abcxyz019 \n\x00\x01\x7f"
    return "".join(rng.choice(pool) for _ in range(rng.choice((0, 3, 8, 12, 12))))


# --- BrainIf ---------------------------------------------------------------


def brainif_program(rng: random.Random) -> str:
    """Guarded lines over small values; gotos in and past range; rare junk.

    One program in a hundred climbs 256 cells of ``if k increment`` to show
    the cell width; ``inc`` (a documented alias of ours) is never written.
    """
    if rng.random() < 0.01:
        return "\n".join(f"if {k} increment" for k in range(256)) + "\nif 0 output"
    size = rng.randint(1, 10)
    lines = []
    for _ in range(size):
        value = rng.choice((0, 0, 0, 1, 1, 2, 3, 97, rng.randint(0, 300)))
        roll = rng.random()
        if roll < 0.05:
            lines.append(rng.choice(("", "  ", "\t")))
        elif roll < 0.07:
            lines.append(
                rng.choice(("if 0", "if x output", "if 0 move up", "if 0 goto 0"))
            )
        else:
            command = rng.choice(
                ["increment"] * 5
                + ["move right", "move left", "input", "output", "output"]
                + [f"goto {rng.randint(1, size + 2)}"] * 2
            )
            lines.append(f"if {value} {command}")
    return "\n".join(lines)


# --- Circlefuck --------------------------------------------------------------

_CF_ESCAPES = (r"\0", r"\n", r"\xFF", r"\x0a", r"\255", r"\256", r"\o377", r"\ ")
_CF_EDGES = (r"\B", r"\b", r"\12a", r"\o8", r"\q", r"\space", "\\")


def circlefuck_program(rng: random.Random) -> str:
    """Return code and data cells, usually with an ``@``; escapes and edges."""
    out = []
    for _ in range(rng.randint(1, 16)):
        roll = rng.random()
        if roll < 0.7:
            out.append(rng.choice("><+-.,[]#{}@" + "+-.>"))
        elif roll < 0.85:
            out.append(rng.choice("a0!* "))
        elif roll < 0.97:
            out.append(rng.choice(_CF_ESCAPES))
        else:
            out.append(rng.choice(_CF_EDGES))
    if rng.random() < 0.8:
        out.insert(rng.randrange(len(out) + 1), "@")
    return "".join(out)


def _escape_split(program: str) -> list[str]:
    return re.findall(r"\\(?:o\d{3}|x\w\w|\d{1,3}|.)?|.", program, re.S)


# --- Circuit Diagram -----------------------------------------------------------


def _cd_block(rng: random.Random) -> list[str]:
    """One small circuit: a chain, a gate, two levels, a source or a split."""
    gate = rng.choice("aAoOxX")
    kind = rng.randrange(7)
    wide = rng.choice(("-", "-", "-2-"))
    if kind == 0:
        return [wide + ".~." * rng.randint(0, 2) + "-:"]
    if kind == 1:
        return ["-.", f"  {gate}.-:", "-."]
    if kind == 2:
        return ["-.~.", f"    {gate}.-:", "-.-."]
    if kind == 3:
        second = rng.choice("aAoOxX")
        return ["-.", f"  {gate}.-.", f"-.    {second}.-:", "-----."]
    if kind == 4:
        return [rng.choice(")(") + rng.choice(("-2-", "-", "-3-")) + ".~.-:"]
    if kind == 5:
        return ["    .-:", "-2-<", "    .-:"]
    return ["-.", "  >-2-:", "-."]


def circuit_program(rng: random.Random) -> str:
    """Stack one to three blocks; now and then overwrite a cell."""
    rows: list[str] = []
    for _ in range(rng.randint(1, 3)):
        rows += _cd_block(rng)
    if rng.random() < 0.15:
        at = rng.randrange(len(rows))
        line = rows[at]
        col = rng.randrange(len(line) + 1)
        rows[at] = line[:col] + rng.choice("-|/\\.=~ a:") + line[col + 1 :]
    return "\n".join(rows)


def circuit_input(rng: random.Random, _program: str) -> str:
    """Bits, usually more than the program reads, sometimes too few."""
    return "".join(rng.choice("01") for _ in range(rng.choice((2, 12, 12, 12))))


# --- Clockwise -------------------------------------------------------------------


def clockwise_program(rng: random.Random) -> str:
    """Return a ring of R corners round random cells, or a random grid."""
    cells = "+-;;.S  ?!"
    width, height = rng.randint(2, 6), rng.randint(2, 4)
    if rng.random() < 0.15:
        return "\n".join(
            "".join(rng.choice(cells + "R") for _ in range(width))
            for _ in range(height)
        )
    grid = [[rng.choice(cells[:7]) for _ in range(width)] for _ in range(height)]
    for row, col in ((0, width - 1), (height - 1, width - 1), (height - 1, 0)):
        grid[row][col] = "R"
    if rng.random() < 0.2:
        grid[rng.randrange(height)][rng.randrange(width)] = rng.choice("?!R")
    return "\n".join("".join(row).rstrip() for row in grid)


# --- Container -----------------------------------------------------------------

_NAMES = ("A", "B", "PRINT", "OUT", "", "IN")


def container_program(rng: random.Random) -> str:
    """Return containers over A, B and the special ones; EXIT fires on A.

    Every referenced name is declared, save rarely an undeclared ``Z``.
    """
    names = list(_NAMES[: rng.randint(2, 6)])

    def operand() -> str:
        return rng.choice(names + ["Z"] * (rng.random() < 0.03))

    lines = []
    for name in names:
        lines.append(
            name + (f"={rng.randint(0, 3)}" if rng.random() < 0.3 else "") + ":"
        )
        for _ in range(rng.randint(0, 3)):
            delta = rng.choice(("+1", "-1", "+3", "-2", "+72", "+0", "5"))
            right = rng.choice((operand(), str(rng.randint(0, 4))))
            op = rng.choice((">=", ">=", "<=")) if right.isdigit() else ">="
            if rng.random() < 0.03:  # edges: ``A<=B``, spaces, a second head
                op = rng.choice(("<=", " >= ", ">=1\nA:\n +1 A"))
            lines.append(f" {delta} {operand()}{op}{right}")
    lines += ["EXIT:", f" +{rng.randint(1, 3)} A>={rng.randint(1, 6)}"]
    if "A" in names and rng.random() < 0.9:
        at = lines.index("A:") if "A:" in lines else 0
        lines.insert(at + 1, " +1 A>=0")
    return "\n".join(lines)


def _container_ref(code: int, stdout: bytes, stderr: bytes) -> object:
    got = blind_outcome(code, stdout, stderr)
    found = re.search(rb"exit value (-?\d+)", stderr)
    if got.status != "halt" or not found:
        return got
    return dataclasses.replace(got, output=stdout + b"|exit " + found.group(1))


def _container_ours(language: str, program: str, stdin: str, steps: int) -> object:
    from esolangs.vm import make_vm

    got = run_ours(language, program, stdin, steps)
    if got.status != "halt":
        return got
    vm = make_vm(language, program, stdin=stdin)
    while not vm.halted:
        vm.step()
    code = vm._machine.exit_code  # type: ignore[attr-defined]  # noqa: SLF001
    return dataclasses.replace(got, output=got.output + f"|exit {code}".encode())


# --- CV(N)(C), spelled in ASCII ---------------------------------------------

#: IPA symbols outside latin-1, as the ASCII letters the generator writes.
CVNC_IPA = dict(zip("TZGQXRWVENY^", "θʒɡʔʡɹɰʋəŋɲ\u030a", strict=True))
_CVNC_TO_IPA = str.maketrans(CVNC_IPA)


def cvnc_program(rng: random.Random, depth: int = 0) -> str:
    """Return CV(N)(C) syllables (ASCII spelling) with nested loops.

    One in ten starts with an edge: a function that goes negative or divides
    by zero, or a ``ɹ`` whose target differs if ``ɰ̊`` counts twice.
    """
    if depth == 0 and rng.random() < 0.1:
        edge = rng.choice(("dEtEdEtEdETiTuTE", "dEqEdETu", "W^EVEdidiRETE", "dEtimu"))
        return edge + cvnc_program(rng, 1)
    out = []
    for _ in range(rng.randint(1, 6 - 2 * depth)):
        if depth < 2 and rng.random() < 0.15:
            opener = rng.choice(("W^", "W^", "W"))
            body = cvnc_program(rng, depth + 1)
            out.append(f"{opener}{rng.choice('iE')}{body}V{rng.choice('iEoo')}")
            continue
        onset = rng.choice(
            "TfsZpkdbtGqQXc" + "fTdbtcg" * 2 + "Rj" * (rng.random() < 0.2)
        )
        syllable = onset + rng.choice("iiiEEæou")
        if rng.random() < 0.35:
            syllable += rng.choice("mnmnNY")
        if rng.random() < 0.15:
            syllable += rng.choice("Tfdb")
        out.append(syllable)
    program = "".join(out)
    if depth == 0 and re.search("[WRj]", program):
        # A repeated square (vowel or function product) outgrows all bounds.
        program = program.translate(str.maketrans("æGg", "obb"))
    if depth == 0 and rng.random() < 0.05:
        at = rng.randrange(len(program) + 1)
        program = program[:at] + rng.choice("aN V") + program[at:]
    return program


def _cvnc_input(rng: random.Random, _program: str) -> str:
    return rng.choice(("", "3", "0", "12 5", "a", "ab\n", "7\n9\n", "2 x"))


def _cvnc_ours(language: str, program: str, stdin: str, steps: int) -> object:
    ipa = program.translate(_CVNC_TO_IPA)
    got = run_ours(language, ipa, stdin, steps)
    if got.status != "timeout":
        fast = run_ours_fast(language, ipa, stdin)
        if fast.status != got.status or (
            fast.status == "halt" and fast.output != got.output
        ):
            return Outcome("crash:fastpath", b"", f"{got} vs {fast}")
    return got


# --- Dig -------------------------------------------------------------------------


def dig_program(rng: random.Random) -> str:
    """Return a right-going row of ``$``-dug work runs, digits beneath.

    Rarely a turn ``#`` (with or without a digit beside it), a missing ``@``
    or a cell overwritten with anything.
    """
    top, below = [">"], [" "]
    for _ in range(rng.randint(1, 4)):
        # A digit right of ``$`` would be its count (up, right, down, left).
        work = [rng.choice("HeZ:.=~;")] + [
            rng.choice("HeZ7:" + ":::" + "%+-*/" + ";;" + "=~" + "0.!q ")
            for _ in range(rng.randint(0, 4))
        ]
        top += ["$", *work]
        below += [str(len(work)), *(rng.choice("0123  ") for _ in work)]
        if rng.random() < 0.1:
            top.append(rng.choice("#'^<"))
            below.append(rng.choice("01 "))
    if rng.random() < 0.95:
        top.append("@")
    if rng.random() < 0.1:
        top[rng.randrange(1, len(top))] = rng.choice("#$@'^<>:12")
    return "".join(top) + "\n" + "".join(below).rstrip()


def _dig_input(rng: random.Random, _program: str) -> str:
    return rng.choice(("", "5\n", "1\n2\n", "ab\n", "3 4 5", "-2\n"))


# --- EGL ---------------------------------------------------------------------


def egl_program(rng: random.Random) -> str:
    """Return ``W,H:`` and commands that mostly keep the pointer in the grid.

    One program in ten moves freely (and reads ``x``); loop bodies only
    count, print, or step right and back.
    """
    width, height = rng.randint(1, 4), rng.randint(1, 4)
    row = col = 0
    free = rng.random() < 0.1
    out = []
    for _ in range(rng.randint(1, 10)):
        char = rng.choice("><^v" * 2 + "_|%" + "++-" * 2 + "==#(" + "x" * free)
        moved = {
            ">": (row, col + 1),
            "<": (row, col - 1),
            "^": (row - 1, col),
            "v": (row + 1, col),
            "_": (-row % height, col),
            "|": (row, -col % width),
            "%": (-row % height, -col % width),
        }.get(char, (row, col))
        if not free and not (0 <= moved[0] < height and 0 <= moved[1] < width):
            continue
        row, col = moved
        if char == "(":
            step = ">+<" if col + 1 < width else "="
            body = (rng.choice(("=", "+", "-", step)) for _ in range(rng.randint(1, 3)))
            char = "+(" + "".join(body) + "-)"
        out.append(char)
    return f"{width},{height}:" + "".join(out) + "=" * (rng.random() < 0.5)


# --- Specs -----------------------------------------------------------------------

_LINES = {"split": lambda program: program.split("\n"), "join": "\n".join}

SPECS: dict[str, Any] = {}
if __name__ != "__main__":
    SPECS = {
        "BrainIf": Spec(
            "BrainIf", brainif_program, _ascii, ref_outcome=blind_outcome, **_LINES
        ),
        "Circlefuck": Spec(
            "Circlefuck",
            circlefuck_program,
            _ascii,
            ref_outcome=blind_outcome,
            split=_escape_split,
        ),
        "Circuit Diagram": Spec(
            "Circuit Diagram",
            circuit_program,
            circuit_input,
            max_steps=2_000,
            ref_outcome=blind_outcome,
            blank=" ",
        ),
        "Clockwise": Spec(
            "Clockwise", clockwise_program, _ascii, ref_outcome=blind_outcome, blank=" "
        ),
        "Container": Spec(
            "Container",
            container_program,
            _ascii,
            max_steps=5_000,
            ref_outcome=_container_ref,
            ours=_container_ours,
            **_LINES,
        ),
        "CV(N)(C)": Spec(
            "CV(N)(C)",
            cvnc_program,
            _cvnc_input,
            max_steps=5_000,
            ref_outcome=blind_outcome,
            ours=_cvnc_ours,
        ),
        "Dig": Spec(
            "Dig", dig_program, _dig_input, ref_outcome=blind_outcome, blank=" "
        ),
        "EGL": Spec("EGL", egl_program, _ascii, ref_outcome=blind_outcome),
    }


if __name__ == "__main__":
    # CV(N)(C) reference shim: ``REFERENCE PROGRAM``, the program in ASCII.
    text = Path(sys.argv[2]).read_text("latin-1").translate(_CVNC_TO_IPA)
    with tempfile.NamedTemporaryFile(
        "w", suffix=".cvnc", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(text)
    os.execvp(sys.executable, [sys.executable, sys.argv[1], handle.name])
