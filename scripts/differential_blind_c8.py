r"""Piet and INTERCAL against their reference implementations.

Each reference runs behind a wrapper: ``python3 WRAP {program}``, exit 0
halt, 2 unreadable, 3 error (E-number on stderr), 4 EOF, 124 its bound.

Piet -- Erik Schoenfelder's npiet 1.3f, https://www.bertnase.de/npiet/
    npiet-1.3f.tar.gz (sha256 2ded856062abd73599e85e1e768ce6bc60ba2db22dc7d6a9
    b62763dca04b855a), no GD/PNG; programs are P3 PPM text.  The wrapper runs
    ``npiet -v11 -q -cs 1 -e 10000`` (``-v11``: the spec's white-block
    retrace rule; plain npiet slides forever) and exits 124 on "execution
    steps exceeded", 5 on a ``-ftrapv`` abort (64-bit overflow, a limit)::

        python scripts/differential.py Piet --patch npiet.c
        cc -w -O1 -ftrapv -o npiet npiet.c

INTERCAL -- C-INTERCAL 0.30, intercal_0.30.orig.tar.gz from deb.debian.org
    (sha256 b38b62a61a3cb5b0d3ce9f2d09c97bd74796979d532615073025a7fff6be1715);
    on arm64 macOS ``abcess.h`` must take the stdarg prototypes (``#ifdef
    HAVE_STDARG_H`` -> ``#if 1``) or every binary crashes.  The wrapper
    compiles with ``ick -b -E`` (no E774 bug, no system library), runs the
    binary with a 2 s wall clock (ick counts no steps) and reads the
    ``ICLnnnI`` line, since ick exits with the E-number mod 256 (E000 is
    0).  Falling off the end is a halt, as ours: E633, or E129 in 0.30,
    whose dispatch switch falls into its default arm::

        python scripts/differential.py INTERCAL --patch src/cesspool.c
        ./configure && make && make install
"""

from __future__ import annotations

import random
import sys
from typing import Any


def _harness() -> Any:
    """Return ``differential`` (imported, or run as ``__main__``)."""
    for name in ("differential", "__main__"):
        module = sys.modules.get(name)
        if module is not None and hasattr(module, "Spec"):
            return module
    raise ImportError("import differential_blind_c8 through differential.py")


_d = _harness()
Outcome, Spec = _d.Outcome, _d.Spec

# --- Piet -------------------------------------------------------------------

type _RGB = tuple[int, ...]

_HEX = ("FFC0C0", "FFFFC0", "C0FFC0", "C0FFFF", "C0C0FF", "FFC0FF")
#: The 18 colours as ``_PIET[lightness][hue]``: light, normal, dark.
_PIET = tuple(
    tuple(tuple(int(h[i : i + 2], 16) for i in (0, 2, 4)) for h in row)
    for row in (
        _HEX,
        ("FF0000", "FFFF00", "00FF00", "00FFFF", "0000FF", "FF00FF"),
        ("C00000", "C0C000", "00C000", "00C0C0", "0000C0", "C000C0"),
    )
)
_WHITE, _BLACK = (255, 255, 255), (0, 0, 0)
#: Off-palette colours (both sides read them as white).
_ODD = ((255, 128, 0), (128, 64, 0), (1, 2, 3), (192, 192, 192))


def _colour(hue: int, light: int) -> _RGB:
    return _PIET[light % 3][hue % 6]


def _ppm(grid: list[list[_RGB]]) -> str:
    """Return ``grid`` as P3 PPM text, one pixel a line."""
    head = f"P3\n{len(grid[0])} {len(grid)}\n255"
    return "\n".join([head] + [f"{r} {g} {b}" for row in grid for r, g, b in row])


def _from_ppm(program: str) -> Any:
    """Parse P3 text back into an ``esolangs`` Raster."""
    from esolangs.raster import Raster

    words = program.split()
    width, height = int(words[1]), int(words[2])
    values = list(map(int, words[4:]))
    pixels = [
        (values[i], values[i + 1], values[i + 2]) for i in range(0, len(values), 3)
    ]
    return Raster(
        tuple(tuple(pixels[y * width : (y + 1) * width]) for y in range(height))
    )


#: (hue step, lightness step) per command, and a weight.
_STEPS = (
    ((0, 1), 6),  # push
    ((0, 2), 1),  # pop
    ((1, 0), 2),  # add
    ((1, 1), 3),  # subtract
    ((1, 2), 2),  # multiply
    ((2, 0), 2),  # divide
    ((2, 1), 2),  # mod
    ((2, 2), 1),  # not
    ((3, 0), 1),  # greater
    ((3, 1), 1),  # pointer
    ((3, 2), 1),  # switch
    ((4, 0), 2),  # duplicate
    ((4, 1), 3),  # roll
    ((4, 2), 1),  # in(number)
    ((5, 0), 1),  # in(char)
    ((5, 1), 3),  # out(number)
    ((5, 2), 2),  # out(char)
)
_PUSH, _SUB, _OUT_NUMBER = (0, 1), (1, 1), (5, 1)
#: Commands that take a signed operand: divide, mod, pointer, switch, roll,
#: out(number), out(char).
_SIGNED = ((2, 0), (2, 1), (3, 1), (3, 2), (4, 1), (5, 1), (5, 2))


def _commands(rng: random.Random) -> list[tuple[int, tuple[int, int]]]:
    """Return ``(size of the block exited, command)`` pairs.

    Often an idiom: ``a b - c`` then a signed command, so negative values,
    zero divisors and too-deep or negative rolls come up; the stack is
    printed at the end.
    """
    out: list[tuple[int, tuple[int, int]]] = []
    while len(out) < rng.randint(1, 14):
        if rng.random() < 0.3:
            a, b, c = (rng.randint(1, 7) for _ in range(3))
            out += [(a, _PUSH), (b, _PUSH), (1, _SUB), (c, _PUSH)]
            out.append((1, rng.choice(_SIGNED)))
        else:
            ((step, _),) = rng.choices(_STEPS, [w for _, w in _STEPS])
            out.append((rng.choice((1, 1, 2, 3, 5)), step))
    # Print what is left, so a wrong value cannot hide on the stack.
    return out + [(1, _OUT_NUMBER)] * rng.choice((0, 2, 3, 4))


def piet_line(rng: random.Random) -> list[list[_RGB]]:
    """Return a three-row program: a run of commands into a cage that halts.

    Row 1 carries the blocks left to right; a block of ``size`` codels grows
    into rows 0 and 2 (not in its last column, so it still exits along row
    1).  White codels between blocks slide without a command.  The cage is a
    three-codel column whose only neighbours off its extreme codels are black.
    """
    columns: list[list[_RGB]] = []
    hue, light = rng.randrange(6), rng.randrange(3)
    for size, (dh, dl) in _commands(rng):
        width = max(-(-(size + 2) // 3), min(size, rng.choice((1, 2, 3))))
        here = _colour(hue, light)
        block = [[_BLACK, here, _BLACK] for _ in range(width)]
        for slot in rng.sample(range(2 * (width - 1)), size - width):
            block[slot // 2][2 * (slot % 2)] = here
        columns += block
        if rng.random() < 0.1:
            columns.append([_BLACK, rng.choice((_WHITE, *_ODD)), _BLACK])
        hue, light = hue + dh, light + dl
    cage = _colour(hue, light)
    columns.append([cage, cage, cage])
    columns.append([_BLACK, rng.choice((_BLACK, _WHITE)), _BLACK])
    if rng.random() < 0.2:
        x = rng.randrange(len(columns))
        columns[x][rng.choice((0, 2))] = rng.choice((_WHITE, *_ODD))
    return [list(row) for row in zip(*columns, strict=True)]


def piet_grid(rng: random.Random) -> list[list[_RGB]]:
    """Return a small random grid: every colour, white, black, off-palette."""
    width, height = rng.randint(1, 7), rng.randint(1, 5)
    pool = [c for row in _PIET for c in row] + [_WHITE] * 4 + [_BLACK] * 3
    pool += list(_ODD)
    return [[rng.choice(pool) for _ in range(width)] for _ in range(height)]


def piet_program(rng: random.Random) -> str:
    """Return a P3 image: mostly a halting command line, sometimes a grid."""
    return _ppm(piet_line(rng) if rng.random() < 0.75 else piet_grid(rng))


def piet_input(rng: random.Random, _program: str) -> str:
    """Return numbers, often with characters and bad tokens, or nothing.

    A bad token for a numeric read is a recorded gap (ours consumes it,
    npiet's scanf does not), so a fifth of inputs only carry one.
    """
    pool: tuple[str, ...] = ("7", "12", "-3", "0", "+5", "007")
    if rng.random() < 0.2:
        pool += ("x", "1_0", "a", "Z", "-")
    words = [rng.choice(pool) for _ in range(rng.choice((0, 1, 2, 4, 6)))]
    return "".join(word + rng.choice(" \n") for word in words)


def piet_ours(language: str, program: str, stdin: str, max_steps: int) -> Any:
    """Step our VM at codel size 1; UTF-8 output; check the fast path too."""
    import esolangs
    from esolangs.vm import make_vm

    raster, vm, status, detail = _from_ppm(program), None, "timeout", ""
    try:
        vm = make_vm(language, raster, stdin, scale=1)
        machine = vm._machine  # type: ignore[attr-defined]  # noqa: SLF001
        for _ in range(max_steps):
            if vm.halted:
                status = "halt"
                break
            vm.step()
            # npiet's stack is 64-bit; past that ours would square away memory.
            if any(abs(value) >> 62 for value in machine.stack):
                status = "limit"
                break
        else:
            status = "halt" if vm.halted else "timeout"
    except Exception as exc:
        status = _d._ours_status(exc)  # noqa: SLF001
        detail = f"{type(exc).__name__}: {exc}"
    text = vm.output if vm is not None else ""
    if status == "halt":
        try:
            fast = esolangs.run(language, raster, stdin, timeout=20, scale=1)
        except Exception as exc:
            fast = f"{type(exc).__name__}: {exc}"
        if fast != text:
            status, detail = "crash:fastpath", repr(fast)[:160]
    return Outcome(status, text.encode("utf-8", "surrogatepass"), detail)


def piet_outcome(code: int, stdout: bytes, stderr: bytes) -> Any:
    """Exit 5 (npiet's overflow trap) is a limit, its step limit a timeout.

    As ``limit`` the step limit would pass any status of ours that agrees on
    a prefix, hiding a halt of ours inside npiet's budget.
    """
    if code in (5, 124):
        return Outcome("limit" if code == 5 else "timeout", stdout, str(code))
    return _d.blind_outcome(code, stdout, stderr)


#: npiet as written takes choices the spec leaves open differently from
#: ours (recorded in our docstring); these edits bring it to ours.
_PIET_PATCHES = (
    # A division or modulo by zero is ignored (npiet pushes 99999999).
    (
        "\tstack [num_stack - 2] = 99999999;\n\tnum_stack--;\n"
        '\ttprintf ("info: divide failed',
        '\ttprintf ("info: divide failed',
    ),
    (
        "\tstack [num_stack - 2] = 99999999;\n\tnum_stack--;\n"
        '\ttprintf ("info: mod failed',
        '\ttprintf ("info: mod failed',
    ),
    # A failed roll leaves its arguments (npiet pops them); a roll is taken
    # modulo its depth (npiet loops, and depth 0 writes past the stack).
    ("\tnum_stack -= 2;\n\n\tif (depth < 0) {", "\n\tif (depth < 0) {"),
    (
        "} else if (num_stack < depth) {",
        "} else if (num_stack - 2 < depth) {",
    ),
    (
        "\t} else {\n\t  int i;\n\t  /* roll is positive: */",
        "\t} else {\n\t  int i;\n\t  num_stack -= 2;"
        " roll = depth ? roll % depth : 0;\n\t  /* roll is positive: */",
    ),
    # Division floors, as ours (the page says only "integer division"); npiet
    # truncates, and so does its modulo, against the page's floored mod.
    (
        "\tstack [num_stack - 2] = stack [num_stack - 2] / stack [num_stack - 1];",
        "\t{ long a = stack [num_stack - 2], b = stack [num_stack - 1];\n"
        "\t  stack [num_stack - 2] = a / b - (a % b != 0 && (a < 0) != (b < 0)); }",
    ),
    (
        "\tstack [num_stack - 2] = stack [num_stack - 2] % stack [num_stack - 1];",
        "\t{ long b = stack [num_stack - 1], r = stack [num_stack - 2] % b;\n"
        "\t  stack [num_stack - 2] = r != 0 && (r < 0) != (b < 0) ? r + b : r; }",
    ),
    # A negative switch toggles |n| times, as the page says (npiet: never).
    ("\tfor (i = 0; i < val; i++) {", "\tfor (i = 0; i < labs (val); i++) {"),
    # A character is a Unicode code point, written as UTF-8 (npiet writes
    # the low byte); outside Unicode it is not printed, as ours.
    (
        'printf ("%c", (int) (stack [num_stack - 1] & 0xff));',
        "{ long v = stack [num_stack - 1];\n"
        "\t  if (v >= 0 && v < 0x80) putchar ((int) v);\n"
        '\t  else if (v >= 0 && v < 0x800) printf ("%c%c", (int) (0xc0 | v >> 6),'
        " (int) (0x80 | (v & 0x3f)));\n"
        '\t  else if (v >= 0 && v < 0x10000) printf ("%c%c%c", (int) (0xe0 | v >> 12),'
        " (int) (0x80 | (v >> 6 & 0x3f)), (int) (0x80 | (v & 0x3f)));\n"
        '\t  else if (v >= 0 && v < 0x110000) printf ("%c%c%c%c",'
        " (int) (0xf0 | v >> 18),"
        " (int) (0x80 | (v >> 12 & 0x3f)), (int) (0x80 | (v >> 6 & 0x3f)),"
        " (int) (0x80 | (v & 0x3f))); }",
    ),
)


# --- INTERCAL ---------------------------------------------------------------

_CONSTANTS = (0, 1, 2, 3, 4, 5, 7, 9, 13, 255, 256, 3999, 4000, 4321, 65535)
_GERUND_WORDS = (
    "CALCULATING", "NEXTING", "READING OUT", "WRITING IN", "STASHING",
    "RETRIEVING", "IGNORING", "REMEMBERING", "RESUMING", "FORGETTING",
    "COMING FROM",
)  # fmt: skip


def _operand(rng: random.Random, depth: int) -> str:
    """Return an INTERCAL operand: a constant, variable or element."""
    roll = rng.random()
    unary = rng.choice("&V?") if rng.random() < 0.15 else ""
    if roll < 0.4:
        return f"#{unary}{rng.choice(_CONSTANTS)}"
    if roll < 0.7:
        return f".{unary}{rng.randint(1, 3)}"
    if roll < 0.9 or depth:
        return f":{unary}{rng.randint(1, 2)}"
    return f",1 SUB #{rng.randint(1, 3)}"


def _expr(rng: random.Random, depth: int = 0) -> str:
    """Return an expression of depth at most two.

    A binary operand is grouped in sparks or rabbit-ears, alternating with
    depth, sometimes with a unary operator inside.
    """
    if depth >= 2 or rng.random() < 0.45:
        return _operand(rng, depth)
    mark = "'\""[depth % 2]
    sides = []
    for _ in range(2):
        side = _expr(rng, depth + 1)
        if " " in side and "SUB" not in side:
            unary = rng.choice("&V?") if rng.random() < 0.15 else ""
            side = f"{mark}{unary}{side}{mark}"
        sides.append(side)
    return f"{sides[0]} {rng.choice('$~~')} {sides[1]}"


def _statement(rng: random.Random, labels: list[int], subs: list[int]) -> str:
    """Return one command (no prefix)."""
    var = rng.choice((".1", ".2", ".3", ":1", ":2"))
    roll = rng.random()
    if roll < 0.3:
        return f"{var} <- {_expr(rng)}"
    if roll < 0.4:
        # Not an expression: ours takes one (recorded), C-INTERCAL says E000.
        item = f"#{rng.choice(_CONSTANTS)}"
        return "READ OUT " + rng.choice((var, var, item, ",1", ",1 SUB #1"))
    if roll < 0.46:
        return "WRITE IN " + rng.choice((var, var, ",1"))
    if roll < 0.52:
        return f",1 <- #{rng.choice((1, 2, 3, 0))}"
    if roll < 0.56:
        return f",1 SUB #{rng.randint(1, 3)} <- {_expr(rng)}"
    if roll < 0.64:
        word = rng.choice(("STASH", "RETRIEVE", "IGNORE", "REMEMBER"))
        return f"{word} {var}" + (" + ,1" if rng.random() < 0.3 else "")
    if roll < 0.74 and labels:
        word = rng.choice(("ABSTAIN FROM", "REINSTATE", "ABSTAIN #2 FROM"))
        if rng.random() < 0.5:
            return f"{word} ({rng.choice(labels)})"
        return f"{word} " + " + ".join(rng.sample(_GERUND_WORDS, rng.randint(1, 2)))
    if roll < 0.84 and subs:
        return f"({rng.choice(subs)}) NEXT"
    if roll < 0.88:
        return f"{rng.choice(('RESUME', 'FORGET'))} #{rng.choice((0, 1, 1, 2))}"
    if roll < 0.92 and labels:
        return f"COME FROM ({rng.choice(labels)})"
    return f"{var} <- {_expr(rng)}"


def intercal_program(rng: random.Random) -> str:
    """Return a polite program: a main line, GIVE UP, then subroutines.

    Main statements get labels for ABSTAIN, REINSTATE and COME FROM; each
    subroutine ends in RESUME, sometimes too deep.  One in ten misses the
    one-fifth-to-one-third PLEASE ratio.
    """
    labels = rng.sample(range(10, 100), rng.randint(0, 3))
    subs = [100 + 10 * k for k in range(rng.randint(0, 2))]
    main = [_statement(rng, labels, subs) for _ in range(rng.randint(2, 10))]
    body: list[tuple[str, str]] = []
    for index, command in enumerate(main):
        label = labels[index] if index < len(labels) else None
        body.append((f"({label}) " if label else "", command))
    rng.shuffle(body)
    # Print most results, so a wrong value cannot hide in a variable.
    for k in range(len(body) - 1, -1, -1):
        target = body[k][1].split(" <- ")[0]
        if target[0] in ".:" and " " not in target and rng.random() < 0.7:
            body.insert(k + 1, ("", f"READ OUT {target}"))
    if rng.random() < 0.6:
        body.insert(0, ("", f",1 <- #{rng.randint(1, 3)}"))
    if rng.random() < 0.9:
        body.append(("", "GIVE UP"))
    for sub in subs:
        lines = [_statement(rng, [], []) for _ in range(rng.randint(0, 2))]
        lines.append(f"RESUME #{rng.choice((1, 1, 1, 2))}")
        body += [(f"({sub}) " if k == 0 else "", c) for k, c in enumerate(lines)]
    count = len(body)
    polite = rng.randint(-(-count // 5), max(count // 3, -(-count // 5)))
    if rng.random() < 0.1:
        polite = rng.choice((0, count // 2 + 1))
    chosen = set(rng.sample(range(count), min(polite, count)))
    out = []
    for k, (prefix, command) in enumerate(body):
        head = "PLEASE" if k in chosen else "DO"
        if rng.random() < 0.05:
            head += rng.choice((" NOT", "N'T")) if head == "DO" else " DON'T"
        out.append(f"{prefix}{head} {command}")
    return "\n".join(out) + "\n"


_WORDS = ("ZERO", "OH", "ONE", "TWO", "THREE", "FIVE", "SIX", "NINE", "NINER")
_FOREIGN = ("BAT", "BI", "EKA", "DVI", "NULI", "TRES", "NIL", "WALO")


def intercal_input(rng: random.Random, _program: str) -> str:
    """Return lines of digit words, or ASCII text for array input.

    Some words are foreign, lower case or bad, some numbers too big.
    """
    lines = []
    for _ in range(rng.choice((0, 1, 2, 3, 4))):
        roll = rng.random()
        if roll < 0.6:
            line = " ".join(rng.choice(_WORDS) for _ in range(rng.randint(1, 3)))
        elif roll < 0.7:
            line = rng.choice(
                (
                    "SIX FIVE FIVE THREE SIX",
                    "FOUR TWO NINE FOUR NINE SIX SEVEN TWO NINE SIX",
                    "",
                )
            )
        elif roll < 0.8:
            line = " ".join(rng.choice(_FOREIGN) for _ in range(rng.randint(1, 2)))
        elif roll < 0.9:
            line = rng.choice(("one", "TWO  THREE", "FOO", "1"))
        else:
            line = "".join(rng.choice("abcXYZ 09!") for _ in range(rng.randint(1, 5)))
        lines.append(line + "\n")
    return "".join(lines)


def _errcode(outcome: Any) -> Any:
    """Fold an ``E123`` from the detail into an ``error`` status."""
    import dataclasses
    import re

    found = re.search(r"\bE(\d{3})\b", outcome.detail)
    if outcome.status != "error" or found is None:
        return outcome
    return dataclasses.replace(outcome, status=f"error:E{found[1]}")


def intercal_ours(language: str, program: str, stdin: str, max_steps: int) -> Any:
    """``run_ours`` with the E-number in the status; checks the fast path."""
    got = _d.run_ours(language, program, stdin, max_steps)
    if got.status != "timeout":
        fast = _d.run_ours_fast(language, program, stdin)
        if fast.status != got.status or (
            fast.status == "halt" and fast.output != got.output
        ):
            return Outcome("crash:fastpath", got.output, f"{got} vs {fast}")
    return _errcode(got)


def intercal_outcome(code: int, stdout: bytes, stderr: bytes) -> Any:
    """Map the wrapper's exit with its E-number; 124 (wall clock) is a timeout."""
    if code == 124:
        return Outcome("timeout", stdout, "wall clock")
    return _errcode(_d.blind_outcome(code, stdout, stderr))


#: C-INTERCAL runtime edits (``src/cesspool.c``) to conventions our
#: docstring records as choices.
_ICK_PATCHES = (
    # Numeric input at EOF is an EOF (exit 70), not E562.
    (
        "    if (fgets(buf, INTBUFSIZ, ick_cesspoolin) == (char *)NULL)\n"
        "\tick_lose(IE562, ick_lineno, (const char *)NULL);",
        "    if (fgets(buf, INTBUFSIZ, ick_cesspoolin) == (char *)NULL)\n"
        "\t{ (void) fflush(stdout); exit(70); }",
    ),
    # A numeral without overbars is one line.
    (
        '\tbutcher(val, result);\n\t(void) fprintf(ick_cesspoolout,"%s\\n",result);',
        "\tbutcher(val, result);\n"
        "\t{ char *body = strchr(result, '\\n') + 1, *out = result;\n"
        "\t  if (!memchr(result, '_', (size_t) (body - result))) out = body;\n"
        '\t  (void) fprintf(ick_cesspoolout,"%s\\n",out); }',
    ),
    # Array elements start at zero (C-INTERCAL: uninitialised).
    (
        "a->data.tail   = (ick_type16*)malloc(prod * sizeof(ick_type16));",
        "a->data.tail   = (ick_type16*)calloc(prod, sizeof(ick_type16));",
    ),
    (
        "a->data.hybrid = (ick_type32*)malloc(prod * sizeof(ick_type32));",
        "a->data.hybrid = (ick_type32*)calloc(prod, sizeof(ick_type32));",
    ),
    # RETRIEVE restores an array that is undimensioned now.
    (
        "      if (a->rank) {\n\tfree(a->dims);",
        "      if (1) {\n\tif (a->rank) free(a->dims);",
    ),
)

SPECS = {
    "Piet": Spec(
        "Piet",
        piet_program,
        piet_input,
        max_steps=2_000,
        suffix=".ppm",
        ref_outcome=piet_outcome,
        split=lambda program: program.split("\n"),
        join="\n".join,
        blank="255 255 255",
        valid=lambda program: (
            program.startswith("P3\n")
            and len(program.split())
            == 4 + 3 * int(program.split()[1]) * int(program.split()[2])
        ),
        patches=_PIET_PATCHES,
        ours=piet_ours,
    ),
    "INTERCAL": Spec(
        "INTERCAL",
        intercal_program,
        intercal_input,
        max_steps=20_000,
        suffix=".i",
        ref_outcome=intercal_outcome,
        split=lambda program: program.splitlines(keepends=True),
        patches=_ICK_PATCHES,
        ours=intercal_ours,
    ),
}
