r"""3x, 6-5, A Painter Ant, AddSubJump, APL, Alight, B-tapemark, Back, Bitdeque.

None has another implementation, so each reference is a "blind" interpreter
written from the wiki text alone (``blind_outcome``'s exit codes)::

    python scripts/differential.py 3x \
        --ref "env BLIND_STEP_LIMIT=20000 python3 BLIND/x3.py {program}"

with ``six_five``, ``addsubjump``, ``algebraic_programming_language``,
``alight``, ``b_tapemark``, ``back`` and ``bitdeque`` likewise.  A Painter
Ant never halts: run it as ``BLIND_STEP_LIMIT=K python scripts/...`` with
``--ref "env APA_DUMP=1 python3 BLIND/a_painter_ant.py {program}"``, and
both sides print the state after exactly ``K`` instructions.
``differential.py`` registers ``SPECS``.
"""

from __future__ import annotations

import dataclasses
import os
import random
import re
import sys
from collections.abc import Callable
from typing import Any


def _harness() -> Any:
    """Return ``differential`` (imported, or run as ``__main__``)."""
    for name in ("differential", "__main__"):
        module = sys.modules.get(name)
        if module is not None and hasattr(module, "Spec"):
            return module
    raise ImportError("import differential_blind_c1 through differential.py")


_d = _harness()
Outcome, Spec, blind_outcome = _d.Outcome, _d.Spec, _d.blind_outcome


def _converted(convert: Callable[[bytes], bytes]) -> Callable[[int, bytes, bytes], Any]:
    """Return ``blind_outcome`` with the reference's output in our spelling."""

    def adapted(code: int, stdout: bytes, stderr: bytes) -> Any:
        got = blind_outcome(code, stdout, stderr)
        return dataclasses.replace(got, output=convert(got.output))

    return adapted


def _ascii(rng: random.Random, _program: str) -> str:
    """Return ASCII input, often empty."""
    pool = "abcAZ019 \n\x00\x7f!"
    return "".join(rng.choice(pool) for _ in range(rng.choice((0, 3, 8, 12, 12))))


def _bits(out: bytes) -> bytes:
    r"""``0101\n`` (the blind dumps) as ours spells it, ``0 1 0 1``."""
    return " ".join(out.decode().strip()).encode()


# --- 3x -------------------------------------------------------------------


def x3_program(rng: random.Random, depth: int = 0) -> str:
    """Return 3x code: pushes first, then ops, loops and literals."""
    out = "" if depth else "".join(rng.choice("33?") for _ in range(rng.randint(0, 5)))
    for _ in range(rng.randint(1, 8 - 3 * depth)):
        roll = rng.random()
        if roll < 0.8 or depth >= 2:
            out += rng.choice("3333xx??!!vv^^##")
        elif roll < 0.9:
            out += "(" + x3_program(rng, depth + 1) + ")"
        else:
            out += "[" + rng.choice(("", "a", "hi", "(", "x3!", " ")) + "]"
    if not depth and rng.random() < 0.04:
        at = rng.randrange(len(out) + 1)
        out = out[:at] + rng.choice("()[] ab") + out[at:]
    return out


def x3_input(rng: random.Random, _program: str) -> str:
    """Return integer and fraction tokens, rarely a malformed one."""
    words = ["0", "1", "2", "3", "-1", "7", "1/2", "-3/4", "6/3", "0/5", "+2"]
    if rng.random() < 0.05:
        words += ["1/0", "a", "1.5"]
    return " ".join(rng.choice(words) for _ in range(rng.choice((0, 1, 2, 4, 6))))


# --- 6-5 ------------------------------------------------------------------


def six_five_program(rng: random.Random) -> str:
    """Return 6-5 code: arithmetic, moves, ``7n``/``8n``, ``4``, comments.

    ``A`` only where straight-line tracking puts the cell in 0..255, and
    ``8n`` mostly names a ``4`` that exists (the readings differ on both).
    """
    tokens: list[str] = []
    tape: dict[int, int] = {}
    cell = 0
    for _ in range(rng.randint(1, 20)):
        roll = rng.random()
        if roll < 0.6:
            tok = rng.choice("666655992213AAB4440")
            if tok == "A" and not 0 <= tape.get(cell, 0) <= 255:
                tok = rng.choice("56")
            cell += {"1": 2, "3": -1}.get(tok, 0)
            add = {"5": 5, "6": 6, "9": -6, "2": -5}.get(tok, 0)
            tape[cell] = tape.get(cell, 0) + add
        elif roll < 0.85:
            tok = rng.choice(("7", "8")) + rng.choice("0123456789ABCZ")
        elif roll < 0.93:
            tok = rng.choice((" ", "\n", " C 44 note\n"))
        else:
            tok = rng.choice(("7", "8", "D", "a", "7b", "8c")) * (rng.random() < 0.2)
        tokens.append(tok)
    fours = tokens.count("4")
    for i, tok in enumerate(tokens):
        if tok[:1] == "8" and len(tok) == 2 and rng.random() < 0.95:
            label = (
                "0123456789ABCDEFGHIJ"[rng.randint(1, min(fours, 19))] if fours else ""
            )
            tokens[i] = "8" + label if label else "4"
    return "".join(tokens)


# --- A Painter Ant --------------------------------------------------------


def ant_program(rng: random.Random) -> str:
    """Return a short instruction string, now and then spaced or broken."""
    out = "".join(rng.choice("nNeEsSwWpPpP") for _ in range(rng.randint(1, 12)))
    if rng.random() < 0.1:
        at = rng.randrange(len(out) + 1)
        out = out[:at] + rng.choice((" ", "\n", "\t")) + out[at:]
    if rng.random() < 0.02:
        out += rng.choice("xq1")
    return out


def ant_ours(language: str, program: str, stdin: str, max_steps: int) -> Any:
    """Step ours ``BLIND_STEP_LIMIT`` instructions; print the blind's dump."""
    from esolangs.interpreters.grid_based.a_painter_ant import _Machine
    from esolangs.interpreters.io import ScriptedIO

    del language, max_steps
    limit = int(os.environ.get("BLIND_STEP_LIMIT", "1000000"))
    try:
        machine = _Machine(program, ScriptedIO(stdin))
    except ValueError as exc:
        return Outcome("error", b"", str(exc))
    for _ in range(limit if machine.prog else 0):
        machine.step()
    white = sorted((x, -y) for (x, y), c in machine.grid.items() if c)
    lines = [f"ant {machine.x} {-machine.y}", f"ip {machine.ip}"]
    lines += [f"white {x} {y}" for x, y in sorted(white, key=lambda p: p[::-1])]
    return Outcome("halt", ("\n".join(lines) + "\n").encode())


def ant_outcome(code: int, stdout: bytes, stderr: bytes) -> Any:
    """Map the blind's limit exit, which carries the dump, to a halt."""
    return blind_outcome(0 if code == 124 else code, stdout, stderr)


# --- AddSubJump -----------------------------------------------------------


def asj_program(rng: random.Random) -> str:
    """Return one instruction a line and a ``.data`` line, or assembly."""
    if rng.random() < 0.25:
        return asj_assembly(rng)
    count = rng.randint(1, 5)
    size = 4 * count + rng.randint(1, 4)

    def operand() -> int:
        roll = rng.random()
        if roll < 0.6:
            return rng.randrange(4 * count, size)
        if roll < 0.75:
            return rng.randrange(size)
        return rng.choice((-1, -1, -2, -3, -4, -5, -6, -7, -8, -9))

    cells: list[int] = []
    for here in range(count):
        jump = rng.random()
        c = (
            4 * (here + 1) % (4 * count)
            if jump < 0.3
            else 4 * rng.randrange(count)
            if jump < 0.6
            else rng.choice((-1, -2, -9, 4 * count))
        )
        a, b, d = operand(), operand(), operand()
        # Writing IO under a positive *d prints *b or -*b (a recorded
        # ambiguity), so IO is written on the add branch only.
        cells += [a, b, c, -7 if a == -1 else d]
    data = [rng.choice((0, 1, -1, 2, 65, 72)) for _ in range(size - len(cells))]
    rows = [" ".join(map(str, cells[i : i + 4])) for i in range(0, len(cells), 4)]
    # FUM starts 0 in ours and 1 in the blind's: zero it first (FUM -= FUM).
    rows = [" ".join(map(str, (-9, -9, 4, -6)))] * (rng.random() < 0.9) + rows
    return "\n".join([*rows, ".data " + " ".join(map(str, data))])


def asj_assembly(rng: random.Random) -> str:
    """Return assembly: labels, sugar, ``?``, ``.data``, comments, a macro."""
    lines = ["FUM FUM ? @1"] * (rng.random() < 0.9)  # FUM -= FUM, as below
    if rng.random() < 0.3:
        lines[:0] = ["def OUT A {", "  IO A", "}"]
    for _ in range(rng.randint(1, 4)):
        a = rng.choice(("IO", "X", "Y", "FUM", "X"))
        b = rng.choice(("X", "Y", "@1", "@n1", "NF", "ZF", "IO", "Y+1"))
        line = rng.choice(
            (
                f"{a} {b}",
                f"{a} {b} ?",
                f"ASJ {a} {b} ? @1",
                f"{a} {b} -1 @0",
                f"OUT {b}" if lines and lines[0].startswith("def") else f"{a} {b}",
            )
        )
        if rng.random() < 0.2:
            line += rng.choice((" # c", " // c", " /* c */"))
        lines.append(line)
    lines.append("IO X -1")
    lines.append(f"X: .data {rng.choice((65, 0, -3, 66))} Y: {rng.randint(-2, 70)} 7")
    return "\n".join(lines)


# --- Algebraic Programming Language ---------------------------------------


def apl_expr(rng: random.Random, depth: int = 0, names: str = "abc") -> str:
    """Return an expression over numbers, variables, operators and calls."""
    roll = rng.random()
    if depth >= 3 or roll < 0.35:
        atoms: list[str] = ["0", "1", "2", "3", "7", "10", "0.5", "2.5", *names]
        return rng.choice(atoms)
    if roll < 0.75:
        op = rng.choice(("+", "-", "*", "/", "%", "**", "&", "|", "+", "*", " - "))
        left = apl_expr(rng, depth + 1, names)
        if op == "**":  # a small literal exponent, so values stay small
            return f"{left}**{rng.choice(('2', '3', '0.5', '-1', '0'))}"
        return f"{left}{op}{apl_expr(rng, depth + 1, names)}"
    if roll < 0.82:
        return f"({apl_expr(rng, depth + 1, names)})"
    if roll < 0.88:
        return f"-{apl_expr(rng, depth + 1, names)}"
    if roll < 0.94:
        return f"{names[:1]}{names[-1:]}" if names else "2"
    return rng.choice(("F(", "G(")) + apl_expr(rng, depth + 1, names) + ")"


def apl_program(rng: random.Random) -> str:
    """Return definitions, assignments and executed lines."""
    lines = []
    if rng.random() < 0.6:
        lines.append(f"F(x) = {apl_expr(rng, 1, 'x')}")
    if rng.random() < 0.4:
        lines.append(
            rng.choice(
                (
                    "G(y) = {\ny + 1\n$(y * 2)\n}",
                    "G(y) = {\ny & $0\n$1\n}",
                    "G(y) = y ~ 3",
                    "G(y) = y@@",
                )
            )
        )
        lines[:0] = ["a ~ b = (a + b) / 2", "a@ = a * 2"]
    bound = ""
    for _ in range(rng.randint(1, 4)):
        # An assignment's right side names only bound variables: whether
        # it reads the others is a recorded ambiguity.
        assign = rng.random() < 0.3
        expr = apl_expr(rng, 0, bound if assign else "abc")
        if "F(" in expr and not any(x.startswith("F(") for x in lines):
            expr = expr.replace("F(", "(")
        if "G(" in expr and not any(x.startswith("G(") for x in lines):
            expr = expr.replace("G(", "(")
        if assign:
            name = rng.choice("abc")
            lines.append(f"{name} = {expr}")
        else:
            lines.append(expr)
            name = "".join(c for c in "abc" if c in expr)
        bound = "".join(sorted(set(bound + name)))
    return "\n".join(lines) + "\n"  # one line may look like a path


def apl_input(rng: random.Random, _program: str) -> str:
    """Return number tokens for the variables an executed line reads."""
    words = ["0", "1", "2", "3", "-1", "5", "1.5", "10"]
    return " ".join(rng.choice(words) for _ in range(rng.choice((0, 2, 3, 6, 6))))


def apl_float(out: bytes) -> bytes:
    """APL: ours prints integral floats without ``.0`` and ``-0.0`` as ``0``."""
    return re.sub(rb"(?m)^-0$", b"0", re.sub(rb"(?m)^(-?\d+)\.0$", rb"\1", out))


# --- Alight ---------------------------------------------------------------


_ALIGHT_ATOMS = ("1", "2", "65", "'a", "0.5", "nil", "eof", "left", "right")


def alight_expr(rng: random.Random, names: list[str]) -> str:
    """Return an atom, one binary operation, or a call or literal.

    One operator at most: ours applies operators left to right, the blind
    by precedence (a recorded ambiguity).
    """
    atom = rng.choice([*_ALIGHT_ATOMS, *names, *names])
    other = rng.choice([*_ALIGHT_ATOMS, *names])
    roll = rng.random()
    if roll < 0.35:
        return atom
    if roll < 0.75:
        return f"{atom}{rng.choice('+-*/=<>&|^')}{other}"
    return rng.choice(
        (
            f"trunc{{{atom}}}",
            f"sign{{{atom}}}",
            f"!{atom}",
            "len{l}",
            "at{l, 0.5}",
            "at{l, 1.5, 66}",
            '"hi"',
            "[1, 2]",
        )
    )


def alight_program(rng: random.Random) -> str:
    """Return a one-row program: declare, compute, output, skip, end."""
    names = ["a", "c"]
    cmds = ["begin", "var a", "var c", "var l", 'set l "AB"', "set a 66", "set c 2"]
    for _ in range(rng.randint(1, 8)):
        roll = rng.random()
        if roll < 0.35:
            cmds.append(f"set {rng.choice(names)} {alight_expr(rng, names)}")
        elif roll < 0.55:
            cmds.append(f"out {rng.choice(names)}")
        elif roll < 0.65:
            cmds.append("inp c")
        elif roll < 0.8:
            other = rng.choice([*_ALIGHT_ATOMS, *names])
            cmds.append(f"skip {rng.choice(names)} {rng.choice('=<>')} {other}")
        elif roll < 0.85:
            cmds.append(rng.choice(("", "wait 0", "set l at{l, 0.5, a}", "set l l+l")))
        elif roll < 0.9:
            cmds.append("end")
        else:
            cmds.append(rng.choice(("out x", "set l len{l, 2}", "x x")))
    cmds.append("end")
    return ";".join(cmds)


# --- B-tapemark -----------------------------------------------------------


def btm_program(rng: random.Random) -> str:
    """Return a small grid with one start symbol, mirrors and commands."""
    rows = [
        "".join(rng.choice("   \\/+-*|?%!AB09") for _ in range(rng.randint(1, 7)))
        for _ in range(rng.randint(1, 4))
    ]
    row = rng.randrange(len(rows))
    col = rng.randrange(len(rows[row]) + 1)
    rows[row] = rows[row][:col] + rng.choice("><v^>>") + rows[row][col + 1 :]
    if rng.random() < 0.85:  # a frame of halts, so most runs end
        width = max(map(len, rows))
        rows = (
            ["!" * (width + 2)] + [f"!{r:{width}}!" for r in rows] + ["!" * (width + 2)]
        )
    if rng.random() < 0.1:
        rows.append('"note" !')
    if rng.random() < 0.03:
        rows.append(rng.choice(("a", ">", '"')))
    return "\n".join(rows)


# --- Back -----------------------------------------------------------------


def back_program(rng: random.Random) -> str:
    """Return a small grid with a ``*`` or two."""
    rows = [
        "".join(rng.choice("\\/<>-+  -<>") for _ in range(rng.randint(1, 6)))
        for _ in range(rng.randint(1, 4))
    ]
    for _ in range(rng.randint(1, 2)):
        row = rng.randrange(len(rows))
        col = rng.randrange(len(rows[row]))
        rows[row] = rows[row][:col] + "*" + rows[row][col + 1 :]
    return "\n".join(rows) + rng.choice(("", "", "\n"))


# --- Bitdeque -------------------------------------------------------------


def bitdeque_program(rng: random.Random) -> str:
    """Return commands; ``GOTO`` targets mostly in range, now and then 0."""
    count = rng.randint(1, 14)
    words = []
    for _ in range(count):
        word = rng.choice(
            ("PUSH", "PUSH", "INJECT", "EJECT", "POP", "INVERT", "INVERT", "GOTO")
        )
        if word == "GOTO":
            word += f" {rng.randint(1, count + 1)}"
        words.append(word)
    return rng.choice((" ", "\n")).join(words)


def bitdeque_ours(language: str, program: str, stdin: str, max_steps: int) -> Any:
    """Run ours with ``GOTO n`` as ``GOTO n-1``.

    Its targets are 0-based and the blind's 1-based (a recorded ambiguity).
    """
    shifted = re.sub(r"GOTO (\d+)", lambda m: f"GOTO {max(int(m[1]) - 1, 0)}", program)
    return _d.run_ours(language, shifted, stdin, max_steps)


def _blind_spec(
    language: str, program: Callable[[random.Random], str], **kw: Any
) -> Any:
    """Return a Spec with the blind defaults: no input, ``blind_outcome``."""
    kw.setdefault("stdin", lambda _rng, _program: "")
    kw.setdefault("ref_outcome", blind_outcome)
    kw.setdefault("max_steps", 20_000)
    return Spec(language, program, **kw)


SPECS = {
    "3x": _blind_spec(
        "3x",
        x3_program,
        stdin=x3_input,
        ref_outcome=_converted(lambda out: out.replace(b"\n", b"")),
    ),
    "6-5": _blind_spec("6-5", six_five_program, stdin=_ascii),
    "A Painter Ant": _blind_spec(
        "A Painter Ant", ant_program, ref_outcome=ant_outcome, ours=ant_ours
    ),
    "AddSubJump": _blind_spec(
        "AddSubJump",
        asj_program,
        stdin=_ascii,
        split=str.splitlines,
        join="\n".join,
    ),
    "Algebraic Programming Language": _blind_spec(
        "Algebraic Programming Language",
        apl_program,
        stdin=apl_input,
        ref_outcome=_converted(apl_float),
        split=str.splitlines,
        join=lambda lines: "\n".join(lines) + "\n",
    ),
    "Alight": _blind_spec(
        "Alight",
        alight_program,
        stdin=_ascii,
        split=lambda p: p.split(";"),
        join=";".join,
    ),
    "B-tapemark": _blind_spec(
        "B-tapemark", btm_program, stdin=_ascii, join="".join, blank=" "
    ),
    "Back": _blind_spec("Back", back_program, ref_outcome=_converted(_bits), blank=" "),
    "Bitdeque": _blind_spec(
        "Bitdeque",
        bitdeque_program,
        ref_outcome=_converted(_bits),
        ours=bitdeque_ours,
        split=lambda p: re.findall(r"GOTO \d+|\S+", p),
        join=" ".join,
    ),
}
