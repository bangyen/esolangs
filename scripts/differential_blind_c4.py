r"""Generators and adapters for nine languages checked against clean-room refs.

LaserFuck, Line, Minifuck, Modulous, Packlang, Painfuck, Polynomial, Qoibl
and ROTfuck have no other implementation, so each reference is a "blind"
interpreter written from the wiki text alone (``BLIND/<slug>.py``, the
contract in ``differential.py``).  ``differential.py`` registers ``SPECS``.
Each Spec's ``patches`` bring a copy of the reference (``--patch``) to the
choices ours records where the page is silent; all but Polynomial and Qoibl
have some.  ``env BLIND_STEP_LIMIT=20000`` keeps the references' own limit
under the wall clock.  References (``P`` the patched copy; escape the
inner double quotes in a shell)::

    --ref "python3 P {program}"   # Modulous, Packlang, Painfuck, Polynomial,
                                  # Qoibl, ROTfuck (backward, our default)
    --ref "sh -c 'iconv -f latin1 -t utf-8 "$1" > "$1.u8" &&
           exec python3 P "$1.u8"' sh {program}"           # LaserFuck
    --ref "sh -c 'read n; BLIND_STEP_LIMIT=$n exec python3 P "$1"' sh {program}"
    --ref "sh -c 'python -m esolangs.tools.line.bf_to_line "$(cat "$1")"
           "$1.png" >/dev/null && exec python3 P "$1.png"' sh {program}"

LaserFuck: the harness writes Latin-1 and the reference reads UTF-8 (the
0xFF byte-mode mark).  Minifuck: the reference loops its program
forever where ours halts at the end, so ``ref_stdin`` sends it the number
of commands our single pass ran, and its limit exit means "halted".  Line
has no text form: a program here is brainfuck, rendered by our Line
renderer, and both sides read that PNG (the last template, ``python`` the
repo's with ``PYTHONPATH=src``).
"""

from __future__ import annotations

import dataclasses
import functools
import random
import sys
from collections.abc import Callable
from typing import Any

#: Filled at the end; bound first so that importing this module before
#: ``differential`` (which imports it back) finds a dict, if an empty one.
SPECS: dict[str, Any] = {}


def _harness() -> Any:
    """Return the loaded ``differential`` module (it may be ``__main__``)."""
    for name in ("differential", "__main__"):
        module = sys.modules.get(name)
        if module is not None and hasattr(module, "Spec"):
            return module
    import differential

    return differential


# --- Minifuck ---------------------------------------------------------------


def minifuck_program(rng: random.Random) -> str:
    """Return ``<.[`` strings, often the wiki cat; no comments (see ``_step``)."""
    if rng.random() < 0.2:
        return "<[<.[<." * rng.randint(1, 3)
    return "".join(rng.choice("<<..[[[") for _ in range(rng.randint(1, 24)))


def minifuck_pass_length(program: str, stdin: str) -> int:
    """Return how many commands our single pass executes (comments excluded)."""
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.minifuck import _Machine

    machine, count = _Machine(program, ScriptedIO(stdin)), 0
    while not machine.halted:
        count += program[machine.ind] in "<.["
        try:
            machine.step()
        except EOFError:
            break
    return count


def _pass_outcome(code: int, stdout: bytes, stderr: bytes) -> Any:
    """Map the capped reference: its limit is our halt, its exit 0 an EOF read."""
    harness = _harness()
    status = {124: "halt", 0: "eof"}.get(code, "error")
    return harness.Outcome(status, stdout, f"exit {code}: {stderr[-200:]!r}")


#: Minifuck: the reference clears the window after printing, which only its
#: looping reading needs (the cat would repeat its first letter); ours keeps
#: it, as the page says nothing of clearing.  See the module docstring.
MINIFUCK_PATCHES = (
    (
        "                out.write(bytes([v]))\n"
        "                for k in range(8):\n"
        "                    tape[k] = 0\n",
        "                out.write(bytes([v]))\n",
    ),
)


# --- ROTfuck ------------------------------------------------------------------


def rotfuck_program(rng: random.Random) -> str:
    """Return brainfuck-shaped text, which rotation scrambles as it runs."""
    h = _harness()
    if rng.random() < 0.6:
        return str(h.bf_program(rng))
    out = "".join(rng.choice("+-><,.[]") for _ in range(rng.randint(1, 16)))
    if rng.random() < 0.1:
        at = rng.randrange(len(out) + 1)
        out = out[:at] + rng.choice(" x\n") + out[at:]
    return out


#: ROTfuck: ours keeps brainfuck's byte cells and raises at EOF, choices the
#: page leaves open ("Output the Unicode character" fixes no width).
ROTFUCK_PATCHES = (
    ("tape[ptr] = v + 1", "tape[ptr] = (v + 1) % 256"),
    ("tape[ptr] = v - 1", "tape[ptr] = (v - 1) % 256"),
    (
        "tape[ptr] = 0 if r is None else r",
        "tape[ptr] = sys.exit(4) if r is None else r % 256",
    ),
)


def utf8_to_latin1(out: bytes) -> bytes:
    """Re-encode a reference's UTF-8 characters the way ``_bytes`` does ours."""
    return out.decode("utf-8", "surrogateescape").encode("latin-1", "replace")


def converted(
    outcome: Callable[[int, bytes, bytes], Any], convert: Callable[[bytes], bytes]
) -> Callable[[int, bytes, bytes], Any]:
    """Return ``outcome`` with the reference's output in our spelling."""

    def adapted(code: int, stdout: bytes, stderr: bytes) -> Any:
        got = outcome(code, stdout, stderr)
        return dataclasses.replace(got, output=convert(got.output))

    return adapted


# --- Painfuck -----------------------------------------------------------------

#: The encryption's two cycles: each command becomes the next letter along.
_PAIN_CYCLES = ("pevkjzwr", "yuctsobqihald")


def painfuck_encrypt(plain: str) -> str:
    """Return the source that runs ``plain``: command ``k`` encrypted back ``k``."""
    out = []
    for k, char in enumerate(plain):
        cycle = next(c for c in _PAIN_CYCLES if char in c)
        out.append(cycle[(cycle.index(char) - k) % len(cycle)])
    return "".join(out)


def painfuck_decrypt(source: str) -> str:
    """Return the commands ``source`` runs (others are comments)."""
    out: list[str] = []
    for char in source:
        cycle = next((c for c in _PAIN_CYCLES if char in c), None)
        if cycle is not None:
            out.append(cycle[(cycle.index(char) + len(out)) % len(cycle)])
    return "".join(out)


def painfuck_plain(rng: random.Random, depth: int = 0) -> str:
    """Return a decrypted program; ``a...b`` loops count their cell down.

    No ``y`` (a coin flip).  Prefixes ``c``/``t``/``v`` and the edges
    (``l`` at the left end, ``q``/``w`` past it, ``h`` of a negative).
    """
    parts: list[str] = []
    # A loop body stays on its cell, so the ``z`` before ``b`` ends it.
    moves = "" if depth else "rld"
    for _ in range(rng.randint(1, 8 - 2 * depth)):
        roll = rng.random()
        if roll < 0.12 and depth < 2:
            parts.append("a" + painfuck_plain(rng, depth + 1) + "zb")
        elif roll < 0.2:
            parts.append(rng.choice("cvt") + rng.choice("psouh" + moves))
        else:
            parts.append(rng.choice("ppssijoouukzhwqtte" + moves))
    return "".join(parts)


#: Painfuck: ours raises at EOF and prints ``u`` as ``chr(cell & 0xFF)``,
#: choices the page ("Output as character") leaves open.
PAINFUCK_PATCHES = (
    ("put(b[0] if b else 0)", "put(b[0] if b else sys.exit(4))"),
    ("if v < 0 or v > 0x10FFFF:", "v &= 0xFF\n            if v < 0:"),
)


def painfuck_input(rng: random.Random, _program: str) -> str:
    """Return number tokens (``i``) and characters (``j``), often empty."""
    if rng.random() < 0.5:
        return " ".join(str(rng.randint(-5, 300)) for _ in range(rng.randint(0, 3)))
    return "".join(rng.choice("ab09 \n") for _ in range(rng.randint(0, 4)))


# --- Modulous -----------------------------------------------------------------

_MOD_FIXED = (
    "[POP]",
    "[SWP]",
    "[DUP]",
    "[DUP]",
    "[PRT INT]",
    "[PRT INT]",
    "[PRT STR]",
    "[END]",
    "[INP INT]",
    "[INP STR]",
)


def modulous_module(rng: random.Random, here: int, size: int) -> str:
    """Return one module; jumps mostly forward, conditions on small values."""
    roll = rng.random()
    var = f"VAR{rng.randint(1, 4)}"
    small = rng.randint(-2, 3)
    if roll < 0.2:
        return f"[PSH INT {rng.choice((small, 65, 104, 0))}]"
    if roll < 0.25:
        return rng.choice(('[PSH STR "ab"]', '[PSH STR ""]', '[PSH STR "hi!"]'))
    if roll < 0.3:
        return f"[PSH {var}]"
    if roll < 0.38:
        return f"[{rng.choice(('ADD', 'SUB'))} {small}]"
    if roll < 0.44:
        return f"[PRT {var} {rng.choice(('INT', 'STR'))}]"
    if roll < 0.5:
        return f"[{var}{rng.choice('+-')}{abs(small)}]"
    if roll < 0.68:
        back = rng.random() < 0.15 and here > 0
        steps = rng.randint(1, here) if back else rng.randint(1, size - here + 1)
        cond = rng.choice(("", "", f" IF {small}", f" NIF {small}"))
        return f"[JMP {'B' if back else 'F'} {steps}{cond}]"
    if roll < 0.7:
        return "[RST]"
    return rng.choice(_MOD_FIXED)


def modulous_program(rng: random.Random) -> str:
    """Return a few modules, now and then the wiki's (in straight quotes)."""
    if rng.random() < 0.05:
        return '[PSH STR "Hello, World!"][PRT STR][JMP B 1 NIF 0]'
    size = rng.randint(1, 9)
    mods = [modulous_module(rng, here, size) for here in range(size)]
    return rng.choice(("", " ", "\n")).join(mods)


#: Modulous: ours reads an empty stack's top as 0 for ``IF``/``NIF``, and a
#: jump before the start wraps to the end; the page says neither.
MODULOUS_PATCHES = (
    (
        "if not stack:\n                        take = False\n"
        '                    elif cond == "IF":',
        'if cond == "IF":',
    ),
    ("take = stack[-1] == val", "take = (stack or [0])[-1] == val"),
    ("take = stack[-1] != val", "take = (stack or [0])[-1] != val"),
    ('raise RunError("jump before the start of the program")', "nip %= n"),
)


def modulous_input(rng: random.Random, _program: str) -> str:
    """Return lines holding one integer or a short word, often none."""
    lines = [
        str(rng.randint(-3, 99))
        if rng.random() < 0.6
        else rng.choice(("ab", "", "x y"))
        for _ in range(rng.choice((0, 1, 2, 3)))
    ]
    return "".join(line + "\n" for line in lines)


# --- Qoibl --------------------------------------------------------------------


def _qoibl_number(value: int) -> str:
    """Spell ``value`` in binary, ``e`` for 0 and ``y`` for 1."""
    return format(value, "b").translate(str.maketrans("01", "ey"))


def qoibl_expression(rng: random.Random, *, atom: bool = False) -> str:
    """Return an atom or one binary operation of two atoms.

    No chains: ours splits at the first ``yr`` (else ``ry``) and the
    reference goes left to right, a choice the page leaves open.
    """
    roll = rng.random()
    if roll < 0.4 or (atom and roll < 0.75):
        return _qoibl_number(rng.choice((0, 1, 2, 3, 5, 72, 104, 255)))
    if roll < 0.75:
        return f"qe {_qoibl_number(rng.randint(0, 3))} qe"
    if roll < 0.8 or atom:
        return "et"
    marker = rng.choice(("ry", "yr"))
    op = rng.choice(("ee", "ey", "ye", "yy"))
    left, right = qoibl_expression(rng, atom=True), qoibl_expression(rng, atom=True)
    return f"{left} {marker} {op} {marker} {right}"


def qoibl_statement(rng: random.Random) -> str:
    """Return a print, a store, or a countdown loop over cells 0..3.

    A loop body is one statement (ours reads "rr x rr y rr" literally, the
    reference takes a run of them): a countdown, or prints until a newline.
    """
    roll = rng.random()
    if roll < 0.35:
        return f"tt {qoibl_expression(rng)} tt"
    cell = _qoibl_number(rng.randint(0, 3))
    if roll < 0.43:
        dec = f"we {cell} we qe {cell} qe ry ey ry y we"
        return f"rr qe {cell} qe yr ey yr e rr {dec} rr"
    if roll < 0.5:
        return f"rr et yr yy yr yey rr tt {qoibl_expression(rng)} tt rr"
    index = rng.choice((0, 1, 2, 3, 3, 256)) if rng.random() < 0.95 else 300
    return f"we {_qoibl_number(index)} we {qoibl_expression(rng)} we"


def qoibl_program(rng: random.Random) -> str:
    """Return statements one per line, now and then the wiki's adder.

    Not its truth-machine: ``rr`` runs inside one statement, so ours cannot
    bound a loop that never ends (``1`` to the truth-machine).
    """
    if rng.random() < 0.03:
        return (
            "we e we yyeeee we\nwe y we et ry ey ry qe e qe we\n"
            "we ye we et ry ey ry qe e qe we\nwe y we qe y qe ry ee ry qe ye qe we\n"
            "we y we qe y qe ry ee ry qe e qe we\ntt qe y qe tt"
        )
    return "\n".join(qoibl_statement(rng) for _ in range(rng.randint(1, 5)))


# --- Packlang -----------------------------------------------------------------

#: Variables every generated package declares, by name and type.
_PACK_VARS = (
    ("Integer", "n"),
    ("Char", "c"),
    ("Integer(0, 3, 3, 0)", "b"),
    ("Array(Char, 3)", "a"),
)


#: Packlang: ours makes a plain ``Integer`` a wrapping byte and prints
#: ``charPut(v)`` as ``v % 256``; the page fixes neither range.
PACKLANG_PATCHES = (
    ('    elif k == "Char":\n        v %= 256', "    else:\n        v %= 256"),
    (
        "                if isinstance(v, list) or not 0 <= v <= 0x10FFFF:",
        "                v = v % 256 if isinstance(v, int) else v\n"
        "                if isinstance(v, list):",
    ),
)


def packlang_expression(rng: random.Random, depth: int = 0) -> str:
    """Return a literal, a variable, an element, ``!e``, ``e ^ e`` or a call.

    Literals avoid all-0/1 digit strings, which the readings split on.
    """
    roll = rng.random()
    if roll < 0.3 or depth >= 2:
        return str(rng.choice((2, 3, 5, 48, 65, 72, 97, 104, 255, 256, 300)))
    if roll < 0.55:
        return rng.choice(("n", "c", "b", "a(2)", "a(length)"))
    if roll < 0.7:
        return f"!({packlang_expression(rng, depth + 1)})"
    if roll < 0.9:
        left = packlang_expression(rng, depth + 1)
        return f"{left} ^ {packlang_expression(rng, depth + 1)}"
    return f"same({packlang_expression(rng, 2)}, {packlang_expression(rng, 2)})"


def packlang_statement(rng: random.Random, depth: int = 0) -> str:
    """Return one statement; loops count ``n`` down so that most halt."""
    roll = rng.random()
    target = rng.choice(("n", "c", "b", "a(1)", "a"))
    if roll < 0.35:
        op = rng.choice(("INIT", "INCR", "INCR", "DECR"))
        return f"{op} {'a(0)' if op != 'INIT' and target == 'a' else target};"
    if roll < 0.55:
        return f"charPut({packlang_expression(rng)});"
    if roll < 0.62:
        return f"charGet({target if target != 'a' else 'c'});"
    if roll < 0.7:
        return f"{packlang_expression(rng)};"
    if depth >= 1:
        return "INCR c;"
    body = " ".join(packlang_statement(rng, 1) for _ in range(rng.randint(1, 3)))
    if roll < 0.85:
        return f"If {packlang_expression(rng)} Then {{ {body} }}"
    return f"While n Do {{ DECR n; {body} }}"


def packlang_program(rng: random.Random) -> str:
    """Return a dependency and a package whose ``main`` runs statements."""
    decls = " ".join(f"{kind} {name};" for kind, name in _PACK_VARS)
    count = rng.randint(1, 6)
    body = "\n    ".join(packlang_statement(rng) for _ in range(count))
    return (
        "Dependency {\n  Integer same : Integer x, Integer y {\n    !(x ^ y);\n"
        f"  }}\n}} dep;\nPackage : IO, dep {{\n  {decls}\n  Integer main {{\n"
        f"    INCR n; INCR n;\n    {body}\n    0;\n  }}\n}} p;\n"
    )


# --- LaserFuck ----------------------------------------------------------------

#: The start: whichever way the laser is drawn to go, ``v`` and ``}`` send
#: it right along row 2 from column 2, so a run is deterministic.
_LASER_FUNNEL = (" v", "vov", "}}}")

#: LaserFuck: ours prints the cells a command wrote (the reference: every
#: cell the pointer reached), raises at EOF, and puts its line breaks
#: between numbers; the page says "used cells" and "with line breaks".
LASERFUCK_PATCHES = (
    (
        "vals = [tape.get(i, 0) for i in range(lo, hi + 1)]",
        "vals = [tape[i] for i in sorted(tape)]",
    ),
    (
        "else:\n                    tape[ptr] = 0",
        "else:\n                    sys.exit(4)",
    ),
    ("''.join('%d\\n' % v for v in vals)", "'\\n'.join('%d' % v for v in vals)"),
)


def laserfuck_program(rng: random.Random) -> str:
    """Return a rectangular grid behind the funnel, sometimes in byte mode.

    One ``o`` and no ``*`` (both draw), rows padded alike (ours pads a
    ragged row with spaces, the reference ends it).
    """
    width = rng.randint(3, 12)
    cells = "++++--<>>,,xx/\\_|(){}^v#    "
    rows = [
        "".join(rng.choice(cells) for _ in range(width))
        for _ in range(rng.randint(0, 3))
    ]
    first = "\u00ff" + _LASER_FUNNEL[0][1:] if rng.random() < 0.3 else _LASER_FUNNEL[0]
    lines = [first, *_LASER_FUNNEL[1:]]
    lines[2] += "".join(rng.choice(cells) for _ in range(width))
    full = max(map(len, lines + rows))
    return "\n".join(line.ljust(full) for line in lines + rows)


def laserfuck_join(tokens: list[str]) -> str:
    """Rebuild a shrunk grid with its rows padded to one width again."""
    rows = "".join(tokens).split("\n")
    full = max(map(len, rows))
    return "\n".join(row.ljust(full) for row in rows)


# --- Polynomial ---------------------------------------------------------------

_PRIMES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29)


def polynomial_source(code: list[tuple[int, ...]]) -> str:
    """Encode instructions, the ``k``-th with the ``k``-th prime ``p``.

    ``(v,)`` is the zero ``p**v``; ``(a, b)`` is ``a + p**b i`` and its conjugate.
    """
    coeffs = [1]  # highest degree first
    for prime, instr in zip(_PRIMES, code):  # noqa: B905 - code is shorter
        if len(instr) == 1:
            factor = [1, -(prime ** instr[0])]
        else:
            a, b = instr
            factor = [1, -2 * a, a * a + prime ** (2 * b)]
        out = [0] * (len(coeffs) + len(factor) - 1)
        for i, x in enumerate(coeffs):
            for j, y in enumerate(factor):
                out[i + j] += x * y
        coeffs = out
    degree = len(coeffs) - 1
    terms: list[str] = []
    for i, c in enumerate(coeffs):
        power = degree - i
        if c == 0:
            continue
        mono = "" if power == 0 else "x" if power == 1 else f"x^{power}"
        size = str(abs(c)) if abs(c) != 1 or not mono else ""
        sign = "-" if c < 0 else "+"
        terms.append(
            f"{sign} {size}{mono}" if terms else f"{'-' if c < 0 else ''}{size}{mono}"
        )
    return "f(x) = " + " ".join(terms)


def polynomial_code(rng: random.Random) -> list[tuple[int, ...]]:
    """Return up to eight instructions, every block closed by its own kind.

    Ours closes any opener with either closer and rejects an unmatched one
    only when it runs, the reference statically: a choice the page leaves.
    """
    code: list[tuple[int, ...]] = []
    opened: list[int] = []
    for _ in range(rng.randint(1, 4)):
        roll = rng.random()
        if roll < 0.2 and opened:
            code.append((2 if opened.pop() < 5 else 6,))
        elif roll < 0.35:
            opener = rng.choice((1, 3, 4, 5, 7, 8))
            opened.append(opener)
            code.append((opener,))
        elif roll < 0.55:
            code.append((0, rng.choice((1, 1, 2))))
        else:
            code.append((rng.choice((-3, -1, 1, 2, 5)), rng.randint(1, 6)))
    while opened:
        code.append((2 if opened.pop() < 5 else 6,))
    return code


# --- Line ---------------------------------------------------------------------

#: Line: ours raises at EOF and prints numbers with no separator (the page
#: says only "print the current cell as a number").
LINE_PATCHES = (
    (
        "else:\n                        tape[ptr] = 0",
        "else:\n                        sys.exit(4)",
    ),
    ("out.write(b'%d\\n' % cur)", "out.write(b'%d' % cur)"),
)


@functools.lru_cache(maxsize=64)
def line_png(program: str) -> bytes | None:
    """Return our rendering of brainfuck ``program``, or None if undrawable."""
    import tempfile
    from pathlib import Path

    from esolangs.tools.line.bf_to_line import bf_to_line
    from esolangs.tools.line.render import render

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "prog.png"
        try:
            render(bf_to_line(program)).save(str(path))
        except ValueError:
            return None
        return path.read_bytes()


def line_drawable(program: str) -> bool:
    """Whether our renderer can draw ``program``."""
    return line_png(program) is not None


def line_program(rng: random.Random) -> str:
    """Return brainfuck our renderer can draw, so both sides read one PNG."""
    h = _harness()
    while True:
        program = str(h.bf_program(rng))
        if line_drawable(program):
            return program


def line_input(rng: random.Random, _program: str) -> str:
    """Return small naturals, often too few, to hit EOF.

    Cells are unbounded, so a negative one would never count down to 0.
    """
    count = rng.choice((0, 1, 2, 3, 5))
    return " ".join(str(rng.randint(0, 6)) for _ in range(count))


def line_ours(language: str, program: str, stdin: str, max_steps: int) -> Any:
    """Run ours on our rendering of ``program`` (stepped, then fast)."""
    import tempfile
    from pathlib import Path

    h = _harness()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "prog.png"
        path.write_bytes(line_png(program) or b"")
        got = h.run_ours(language, path, stdin, max_steps)
        if got.status == "timeout":
            return got
        fast = h.run_ours_fast(language, path, stdin)
    if fast.status != got.status or (
        got.status == "halt" and fast.output != got.output
    ):
        return h.Outcome("crash:fastpath", b"", f"{got} vs {fast}")
    return got


# --- the specs ----------------------------------------------------------------


def _specs() -> dict[str, Any]:
    h = _harness()
    return {
        "minifuck": h.Spec(
            "minifuck",
            minifuck_program,
            h.ascii_input,
            ref_stdin=lambda program, stdin: (
                f"{minifuck_pass_length(program, stdin)}\n{stdin}"
            ),
            ref_outcome=_pass_outcome,
            valid=lambda program: any(c in "<.[" for c in program),
            patches=MINIFUCK_PATCHES,
        ),
        "rotfuck": h.Spec(
            "rotfuck",
            rotfuck_program,
            h.ascii_input,
            ref_outcome=converted(h.blind_outcome, utf8_to_latin1),
            patches=ROTFUCK_PATCHES,
        ),
        "painfuck": h.Spec(
            "painfuck",
            lambda rng: painfuck_encrypt(painfuck_plain(rng)),
            painfuck_input,
            max_steps=20_000,
            ref_outcome=h.blind_outcome,
            patches=PAINFUCK_PATCHES,
            valid=lambda program: h.balanced(
                painfuck_decrypt(program).translate(str.maketrans("ab", "[]"))
            ),
            # Shrink the commands, not the text: one deletion re-keys the rest.
            split=lambda program: list(painfuck_decrypt(program)),
            join=lambda commands: painfuck_encrypt("".join(commands)),
        ),
        "modulous": h.Spec(
            "modulous",
            modulous_program,
            modulous_input,
            max_steps=20_000,
            ref_outcome=h.blind_outcome,
            split=lambda program: h.re.findall(r"\[[^\]]*\]|\s+", program),
            patches=MODULOUS_PATCHES,
        ),
        "qoibl": h.Spec(
            "qoibl",
            qoibl_program,
            h.ascii_input,
            max_steps=20_000,
            ref_outcome=h.blind_outcome,
            split=lambda program: program.split(" "),
            join=" ".join,
        ),
        "packlang": h.Spec(
            "packlang",
            packlang_program,
            h.ascii_input,
            max_steps=20_000,
            ref_outcome=h.blind_outcome,
            split=lambda program: h.re.findall(r"[^;{}]*[;{}]|[^;{}]+", program),
            patches=PACKLANG_PATCHES,
        ),
        "laserfuck": h.Spec(
            "laserfuck",
            laserfuck_program,
            h.ascii_input,
            max_steps=20_000,
            ref_outcome=converted(h.blind_outcome, utf8_to_latin1),
            patches=LASERFUCK_PATCHES,
            join=laserfuck_join,
            blank=" ",
            valid=lambda program: program[:3] in (" v\n", "\u00ffv\n"),
        ),
        "polynomial": h.Spec(
            "polynomial",
            lambda rng: polynomial_source(polynomial_code(rng)),
            h.ascii_input,
            max_steps=20_000,
            ref_outcome=h.blind_outcome,
            split=lambda program: [program],
        ),
        "line": h.Spec(
            "line",
            line_program,
            line_input,
            max_steps=20_000,
            ref_outcome=h.blind_outcome,
            patches=LINE_PATCHES,
            valid=line_drawable,
            ours=line_ours,
        ),
    }


SPECS.update(_specs())
