"""Differential testing: run random programs through ours and a reference.

Local and manual: not in CI, not in the justfile.  Usage::

    python scripts/differential.py LANG [--ref CMD] [--programs N] [--seed S]
    python scripts/differential.py LANG --patch FILE   # patch a reference source

``CMD`` is a command template; ``{program}`` becomes the path of a file
holding the program, and the reference reads the program's stdin.  Without
``--ref`` the template comes from ``ESOLANGS_REF_<LANG>`` (upper case,
non-alphanumerics as ``_``, e.g. ``ESOLANGS_REF_BEFUNGE``).

Each program runs through our step VM (bounded by ``max_steps``), through
``esolangs.run`` when the VM stopped (the fast path must agree with
stepping), and through the reference (bounded by ``--ref-timeout``).
Outcomes are compared on status (``halt``, ``eof``, ``error``,
``timeout``, ``limit``) and output bytes; a run that hit a bound or a
reference limit only has to agree on the output prefix.  Disagreements are
minimized by delta debugging over the program's tokens and then the input,
and reported grouped by cause.

A patched reference signals EOF with exit status 70, a limit of its own (a
fixed tape) with 72, and any other runtime error with 71 or a signal (e.g.
``-ftrapv``'s abort); see ``_ref_outcome``.

References (each patch is ``--patch``, which asserts every edit applies
exactly once; the edits bring the reference to a convention our docs record
as a choice the spec leaves open -- see ``Spec.patches``):

brainfuck -- Urban Mueller's original interpreter ``bfi.c`` from
    http://aminet.net/dev/lang/brainfuck-2.lha (sha256 7faaf379b18726bd269a
    526bb8c002fd21838797ad830597e591df776f90277b; extract with ``bsdtar``)::

        python scripts/differential.py brainfuck --patch bfi.c
        cc -std=gnu89 -w -O1 -o bfi bfi.c
        export ESOLANGS_REF_BRAINFUCK="$PWD/bfi {program}"

befunge -- Chris Pressey's ``bef`` v2.25, https://github.com/catseye/Befunge-93
    tag rel_2_25 (commit 8fe4065c0415b6f6fa6f699798fa9b64737aadc1),
    ``src/bef.c``.  ``-ftrapv`` turns signed-long overflow (C UB; ours raises
    HaltError) into an abort::

        python scripts/differential.py befunge --patch bef.c
        cc -w -O1 -ftrapv -o bef bef.c
        export ESOLANGS_REF_BEFUNGE="$PWD/bef -q {program}"

subleq -- Oleg Mazonka's ``sqrun.cpp`` (10 Nov 2006 / 19 Jan 2009), linked
    from the wiki: https://web.archive.org/web/20230605054935id_/http://mazon
    ka.com/subleq/sqrun.cpp (the wiki's own subleq.py has no input and
    indexes past memory)::

        python scripts/differential.py subleq --patch sqrun.cpp
        c++ -w -O1 -o sqrun sqrun.cpp
        export ESOLANGS_REF_SUBLEQ="$PWD/sqrun {program}"

deadfish -- the Python port of Jonathan Todd Skinner's original ("Harry eased
    the mess"), section "Python" of https://esolangs.org/wiki/Deadfish/Impleme
    ntations_(M-Z) revision 196998.  Python 2 source; the patch ports it to
    3.  Unbounded integers, unlike the C original's ``unsigned int``.  It
    reads one command per line, so the harness feeds the program that way::

        python scripts/differential.py deadfish --patch deadfish.py
        export ESOLANGS_REF_DEADFISH="python3 $PWD/deadfish.py"

Adding a language: write a program generator (grammar-aware, biased to short
halting programs and the edge cases), an input generator, and register a
``Spec`` in ``SPECS``.  Override ``split``/``join``/``blank`` when deleting
characters breaks the grammar, ``valid`` to reject such candidates, and
``ref_outcome`` when the reference signals errors some other way.
"""

from __future__ import annotations

import argparse
import os
import random
import re
import shlex
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import esolangs
from esolangs.exceptions import (
    EsolangError,
    InputExhaustedError,
    InterpreterLimitError,
)
from esolangs.vm import make_vm

EOF_STATUS = 70
LIMIT_STATUS = 72


@dataclass(frozen=True)
class Outcome:
    """How one run ended: ``status`` and the output bytes written first."""

    status: str
    output: bytes
    detail: str = ""


def _bytes(text: str) -> bytes:
    """Encode our output as the byte stream a C reference would write."""
    try:
        return text.encode("latin-1")
    except UnicodeEncodeError:
        return text.encode("utf-8")


def _ours_status(exc: BaseException) -> str:
    """Map an exception from our interpreter to a status."""
    if isinstance(exc, InputExhaustedError):
        return "eof"
    if isinstance(exc, InterpreterLimitError):
        return "limit"
    if isinstance(exc, EsolangError):
        return "error"
    return f"crash:{type(exc).__name__}"


def run_ours(language: str, program: str, stdin: str, max_steps: int) -> Outcome:
    """Step our VM up to ``max_steps``; ``timeout`` if it is still running."""
    vm = None
    try:
        vm = make_vm(language, program, stdin)
        for _ in range(max_steps):
            if vm.halted:
                break
            vm.step()
        if not vm.halted:
            return Outcome("timeout", _bytes(vm.output))
        if vm.dumps_on_the_post_halt_step:
            vm.step()
        return Outcome("halt", _bytes(vm.output))
    except Exception as exc:
        output = _bytes(vm.output) if vm is not None else b""
        return Outcome(_ours_status(exc), output, f"{type(exc).__name__}: {exc}")


def run_ours_fast(language: str, program: str, stdin: str) -> Outcome:
    """Run through ``esolangs.run``, the path users take."""
    try:
        return Outcome(
            "halt", _bytes(esolangs.run(language, program, stdin, timeout=20))
        )
    except Exception as exc:
        return Outcome(_ours_status(exc), b"", f"{type(exc).__name__}: {exc}")


def _ref_outcome(code: int, stdout: bytes, stderr: bytes) -> Outcome:
    """Map a patched reference's exit to a status (see the module docstring)."""
    detail = stderr.decode("latin-1")[-200:]
    if code == 0:
        return Outcome("halt", stdout, detail)
    if code == EOF_STATUS:
        return Outcome("eof", stdout, detail)
    if code == LIMIT_STATUS:
        return Outcome("limit", stdout, detail)
    return Outcome("error", stdout, f"exit {code}: {detail}")


def run_ref(
    spec: Spec, template: str, program: str, stdin: str, timeout: float
) -> Outcome:
    """Run the reference on ``program`` through a temporary file."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"prog{spec.suffix}"
        path.write_bytes(program.encode("latin-1"))
        cmd = [arg.replace("{program}", str(path)) for arg in shlex.split(template)]
        data = spec.ref_stdin(program, stdin).encode("utf-8")
        try:
            got = subprocess.run(cmd, input=data, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            out = exc.stdout if isinstance(exc.stdout, bytes) else b""
            return Outcome("timeout", out)
    return spec.ref_outcome(got.returncode, got.stdout, got.stderr)


def compare(ours: Outcome, ref: Outcome) -> str | None:
    """Return the cause of a disagreement, or ``None`` when they agree."""
    if ours.status.startswith("crash"):
        return f"ours crashed ({ours.status[6:]})"
    if {"timeout", "limit"} & {ours.status, ref.status}:
        short, long = sorted((ours.output, ref.output), key=len)
        if not long.startswith(short):
            return "output differs (unbounded run)"
        if ours.status == ref.status or "limit" in (ours.status, ref.status):
            return None
        return f"termination: ours {ours.status}, ref {ref.status}"
    if ours.status != ref.status:
        return f"status: ours {ours.status}, ref {ref.status}"
    if ours.output != ref.output:
        return f"output differs (both {ours.status})"
    return None


@dataclass(frozen=True)
class Spec:
    """One language's plug-in: generators, reference adaptation, shrinking."""

    language: str
    program: Callable[[random.Random], str]
    stdin: Callable[[random.Random, str], str]
    max_steps: int = 100_000
    suffix: str = ".txt"
    #: How the reference receives ``(program, stdin)`` on its stdin.
    ref_stdin: Callable[[str, str], str] = lambda _program, stdin: stdin
    ref_outcome: Callable[[int, bytes, bytes], Outcome] = _ref_outcome
    #: Shrinking: tokens, how to rebuild, and ``blank`` to overwrite rather
    #: than delete (a grid keeps its geometry).  ``valid`` rejects candidates.
    split: Callable[[str], list[str]] = list
    join: Callable[[list[str]], str] = "".join
    blank: str | None = None
    valid: Callable[[str], bool] = lambda _program: True
    #: ``(old, new)`` source edits applied in order by ``--patch``.
    patches: tuple[tuple[str, str], ...] = field(default=())


@dataclass
class Case:
    """A program and input whose runs disagree, with the cause."""

    program: str
    stdin: str
    cause: str
    ours: Outcome
    ref: Outcome


class Runner:
    """Run one language's programs through both sides and compare."""

    def __init__(self, spec: Spec, template: str, timeout: float) -> None:
        """Bind a spec to a reference command and its time bound."""
        self.spec, self.template, self.timeout = spec, template, timeout
        #: ``ours/ref`` status pairs seen, to show what a campaign exercised.
        self.tally: Counter[str] = Counter()

    def check(self, program: str, stdin: str) -> Case | None:
        """Return the disagreement on this program, if any."""
        spec = self.spec
        ours = run_ours(spec.language, program, stdin, spec.max_steps)
        ref = run_ref(spec, self.template, program, stdin, self.timeout)
        # A bound is not a verdict: give the side that stopped short more room.
        if ours.status == "timeout" and ref.status not in ("timeout", "limit"):
            ours = run_ours(spec.language, program, stdin, spec.max_steps * 5)
        if ref.status == "timeout" and ours.status != "timeout":
            ref = run_ref(spec, self.template, program, stdin, self.timeout * 5)
        self.tally[f"{ours.status}/{ref.status}"] += 1
        if ours.status != "timeout":
            fast = run_ours_fast(spec.language, program, stdin)
            if fast.status != ours.status or (
                fast.status == "halt" and fast.output != ours.output
            ):
                return Case(program, stdin, "ours: run() vs stepping", ours, fast)
        cause = compare(ours, ref)
        return None if cause is None else Case(program, stdin, cause, ours, ref)

    def minimize(self, case: Case, budget: int = 300) -> Case:
        """Shrink the program, then the input, keeping the same cause."""
        spec, best = self.spec, case
        calls = [budget]

        def still(program: str, stdin: str) -> Case | None:
            if calls[0] <= 0 or not program or not spec.valid(program):
                return None
            calls[0] -= 1
            got = self.check(program, stdin)
            return got if got is not None and got.cause == case.cause else None

        tokens = spec.split(case.program)
        blank = spec.blank
        removable = [
            i for i, t in enumerate(tokens) if blank is None or t not in "\n" + blank
        ]
        fixed = set(range(len(tokens))) - set(removable)

        def build(active: Sequence[int]) -> str:
            chosen = fixed | set(active)
            if blank is None:
                return spec.join([t for i, t in enumerate(tokens) if i in chosen])
            return spec.join(
                [t if i in chosen else blank for i, t in enumerate(tokens)]
            )

        kept = ddmin(
            removable, lambda active: still(build(active), best.stdin) is not None
        )
        best = still(build(kept), best.stdin) or best
        size = len(best.stdin)
        while size:
            size //= 2
            got = still(best.program, best.stdin[:size])
            if got is not None:
                best = got
        return best


def ddmin(items: list[int], fails: Callable[[list[int]], bool]) -> list[int]:
    """Zeller's ddmin, complement-only: a 1-minimal sublist that still fails."""
    chunks = 2
    while len(items) >= 2:
        size = -(-len(items) // chunks)
        for start in range(0, len(items), size):
            rest = items[:start] + items[start + size :]
            if fails(rest):
                items, chunks = rest, max(chunks - 1, 2)
                break
        else:
            if chunks >= len(items):
                break
            chunks = min(len(items), chunks * 2)
    return items


def apply_patches(text: str, patches: Sequence[tuple[str, str]]) -> str:
    """Apply each ``(old, new)`` edit, refusing one that does not match once."""
    for old, new in patches:
        if text.count(old) != 1:
            raise SystemExit(f"patch does not apply exactly once: {old[:60]!r}")
        text = text.replace(old, new)
    return text


# --- brainfuck ------------------------------------------------------------

_BF_IDIOMS = ("[-]", "[+]", "[>+<-]", "[>++<-]", "[>-<-]", "[<+>-]")


def bf_block(rng: random.Random, depth: int = 0) -> str:
    """Return a Brainfuck block; inside a loop it returns the pointer home.

    A loop body that ends where it began and decrements its own cell halts
    unless an inner loop resets that cell, so most programs halt.
    """
    parts: list[str] = []
    offset = 0
    for _ in range(rng.randint(1, 8 - 2 * depth)):
        roll = rng.random()
        if roll < 0.3:
            parts.append(rng.choice("+-") * rng.randint(1, 4))
        elif roll < 0.5:
            step = rng.choice((-1, 1)) * rng.randint(1, 3)
            parts.append((">" if step > 0 else "<") * abs(step))
            offset += step
        elif roll < 0.62:
            parts.append(".")
        elif roll < 0.72:
            parts.append(",")
        elif roll < 0.88 and depth < 3:
            parts.append("[" + bf_block(rng, depth + 1) + "-]")
        else:
            parts.append(rng.choice(_BF_IDIOMS))
    if depth:
        parts.append(("<" if offset > 0 else ">") * abs(offset))
    return "".join(parts)


def bf_program(rng: random.Random) -> str:
    """Return a balanced program: mostly structured, sometimes free-form."""
    if rng.random() < 0.85:
        return bf_block(rng)
    out, depth = [], 0
    for _ in range(rng.randint(1, 30)):
        char = rng.choice("+-<>.,[]" if depth else "+-<>.,[")
        depth += {"[": 1, "]": -1}.get(char, 0)
        out.append(char)
    return "".join(out) + "]" * depth


def balanced(program: str) -> bool:
    """Whether every bracket in ``program`` has a partner."""
    depth = 0
    for char in program:
        depth += {"[": 1, "]": -1}.get(char, 0)
        if depth < 0:
            return False
    return depth == 0


def ascii_input(rng: random.Random, _program: str) -> str:
    """Return a short ASCII input; often empty, to hit EOF."""
    pool = "abcxyz019 \n\x00\x01\x7f"
    return "".join(rng.choice(pool) for _ in range(rng.choice((0, 0, 1, 2, 3, 6))))


# --- Befunge-93 -----------------------------------------------------------

_BEF_CELLS = (
    "0123456789" * 3
    + "+-*/%!`"
    + "><^v_|" * 2
    + ":\\$" * 2
    + ".,.,"
    + "#gp&~"
    + '"@@  '
)
#: Edge idioms for a one-line run: a byte above 127 stored and read back,
#: ``g``/``p`` off the grid and at its far corner, zero divisors, signed
#: division, a near-overflow product, and reads.
_BEF_IDIOMS = (
    "99*3*00p00g.",
    "99*3*00p00g,",
    "01-0g.",
    "501-p",
    "98*7+0g.",
    "0/.",
    "0%.",
    "07-2/.",
    "07-2%.",
    "99*:*:*:*:*:*.",
    "&.",
    "~.",
)


def befunge_program(rng: random.Random) -> str:
    """Return a grid within 80x25: a one-line run or a small random grid.

    No ``?``: the two sides draw differently.  A cell at column 79 or row 24
    now and then puts the far edge in play; small grids wrap the torus fast.
    """
    if rng.random() < 0.5:
        line = _BEF_CELLS.translate({ord(c): None for c in "^v|"})
        cells = [rng.choice(line) for _ in range(rng.randint(2, 24))]
        for _ in range(rng.choice((0, 1, 1, 2))):
            cells.insert(rng.randrange(len(cells) + 1), rng.choice(_BEF_IDIOMS))
        if rng.random() < 0.3:
            cells.insert(
                rng.randrange(len(cells)),
                '"' + "".join(rng.choice("ab 0~") for _ in range(3)) + '"',
            )
        rows = ["".join(cells) + "@"]
    else:
        width, height = rng.randint(2, 10), rng.randint(1, 5)
        rows = [
            "".join(rng.choice(_BEF_CELLS + "@@@") for _ in range(width))
            for _ in range(height)
        ]
    if rng.random() < 0.1:
        rows[0] = rows[0].ljust(79) + rng.choice(_BEF_CELLS.strip())
    if rng.random() < 0.1:
        rows += [""] * (24 - len(rows)) + [rng.choice("<>^v.@")]
    return "\n".join(row.rstrip() for row in rows)


def befunge_input(rng: random.Random, _program: str) -> str:
    """Return integer tokens and characters, often empty to hit EOF."""
    tokens = [
        str(rng.randint(-20, 300)) if rng.random() < 0.7 else rng.choice("ab\n")
        for _ in range(rng.choice((0, 0, 1, 2, 4)))
    ]
    return " ".join(tokens)


def befunge_join(tokens: list[str]) -> str:
    """Rebuild a grid, trimming the padding a shrink leaves behind."""
    rows = [row.rstrip() for row in "".join(tokens).split("\n")]
    while len(rows) > 1 and not rows[-1]:
        rows.pop()
    return "\n".join(rows)


# --- Subleq ---------------------------------------------------------------


def subleq_program(rng: random.Random) -> str:
    """Return triples: arithmetic, ``a -1 c`` output and ``-1 b c`` input.

    Jumps go next, anywhere, negative (halt) or past the end (halt);
    operands sometimes point past loaded memory or at -2 (an error), and the
    last triple is sometimes cut short.
    """
    count = rng.randint(1, 6)
    size = 3 * count + rng.randint(0, 5)

    def address() -> int:
        roll = rng.random()
        return (
            rng.randrange(size)
            if roll < 0.9
            else (-2 if roll < 0.92 else size + rng.randint(0, 3))
        )

    cells: list[int] = []
    for pc in range(0, 3 * count, 3):
        roll = rng.random()
        a, b = (
            (-1, address())
            if roll < 0.12
            else (address(), -1)
            if roll < 0.32
            else (address(), address())
        )
        if rng.random() < 0.01:
            a = b = -1
        jump = rng.random()
        c = (
            pc + 3
            if jump < 0.4
            else 3 * rng.randrange(count)
            if jump < 0.65
            else rng.randrange(size)
            if jump < 0.75
            else -rng.randint(1, 3)
            if jump < 0.9
            else size + rng.randint(0, 3)
        )
        cells += [a, b, c]
    cells += [rng.randint(-3, 120) for _ in range(size - len(cells))]
    if rng.random() < 0.05:
        cells = cells[: 3 * (count - 1) + rng.randint(1, 2)]
    return " ".join(map(str, cells))


# --- Deadfish -------------------------------------------------------------


def deadfish_program(rng: random.Random) -> str:
    """Return ``idso`` with rare ``h`` and junk, at most six squarings."""
    out: list[str] = []
    squares = 0
    for _ in range(rng.randint(1, 40)):
        char = rng.choice(
            "iiiiiddds"
            + "oooo"
            + ("h" if rng.random() < 0.05 else "i")
            + ("x " if rng.random() < 0.1 else "i")
        )
        if char == "s":
            squares += 1
            if squares > 6:
                char = "o"
        out.append(char)
    return "".join(out)


SPECS: dict[str, Spec] = {
    "brainfuck": Spec(
        "brainfuck",
        bf_program,
        ascii_input,
        suffix=".b",
        valid=balanced,
        patches=(
            ("#include <stdio.h>", "#include <stdio.h>\n#include <stdlib.h>"),
            # A tape growing both ways: start mid-array, error only far out.
            ("int  p, r, q;", "int  p=1<<19, r, q;"),
            ("char a[5000]", "char a[1<<20]"),
            ("p<0 || p>100", "p<0 || p>=1<<20"),
            # Ours raises at EOF; the original stores getchar()'s EOF (-1).
            ("a[p]=getchar();", "{ int ch=getchar(); if(ch==EOF) exit(70); a[p]=ch; }"),
            ('puts("UNBALANCED BRACKETS"), exit(0)', "exit(71)"),
            ('puts("RANGE ERROR"), exit(0)', "exit(72)"),
            ("chkabort();", ""),
        ),
    ),
    "befunge": Spec(
        "befunge",
        befunge_program,
        befunge_input,
        max_steps=50_000,
        suffix=".bf",
        split=list,
        join=befunge_join,
        blank=" ",
        patches=(
            # Cells are unsigned bytes (ours; C's plain char is signed here).
            ("char pg[LINEWIDTH", "unsigned char pg[LINEWIDTH"),
            ('printf("What do you want %ld/0 to be? ", b);', ";"),
            (
                '                     fscanf (stdin, "%ld", &b);',
                '                     if (fscanf (stdin, "%ld", &b) != 1) exit (71);',
            ),
            # `%` by zero reads its result too (C: undefined behaviour).
            (
                "push (b % a);",
                'if (a == 0) { if (fscanf (stdin, "%ld", &b) != 1) exit (71);'
                " push (b); } else push (b % a);",
            ),
            # `&` at EOF raises (the reference pushes -1); bad token errors.
            (
                '                   fscanf (stdin, "%ld", &b);',
                '                   { int n = fscanf (stdin, "%ld", &b);'
                " if (n != 1) exit (n == EOF ? 70 : 71); }",
            ),
            # `~` at EOF raises (the reference pushes -1).
            (
                "c = fgetc (stdin);\n                   push (c);",
                "{ int ch = fgetc (stdin); if (ch == EOF) exit (70); push (ch); }",
            ),
        ),
    ),
    "subleq": Spec(
        "subleq",
        subleq_program,
        ascii_input,
        max_steps=20_000,
        split=str.split,
        join=" ".join,
        patches=(
            # libc++ exports std::sin, which the global `sin` collides with.
            ("using namespace std;", "using namespace std;\n#define sin in_name"),
            ("vector<int> v;", "vector<long long> v;"),
            (
                "int & operator[](int i);",
                # Reads past memory yield 0 without growing it; growth moves
                # the end, which is where a jump halts.
                "long long & operator[](long long i);\n\tlong long rd(long long i)"
                '{ if( i<0 ) throw "Access violation: ";'
                " return i<(long long)v.size() ? v[i] : 0; }",
            ),
            (
                "int & Mem::operator[](int i)",
                "long long & Mem::operator[](long long i)",
            ),
            ("int ip=0;", "long long ip=0;"),
            ("int a = mem[ip++];", "long long a = mem[ip++];"),
            ("int b = mem[ip++];", "long long b = mem[ip++];"),
            ("int c = mem[ip++];", "long long c = mem[ip++];"),
            (
                'cerr<<"Incomplete instruction\\n"; break;',
                'cerr<<"Incomplete instruction\\n"; return 71;',
            ),
            # `-1 b c` stores the byte and falls through (the reference adds
            # it, branches, and decrements at EOF); `-1 -1 c` is an error.
            ("if( a == iin && b==iout )", "if( false )"),
            (
                "else if( a == iin )",
                'else if( a == iin && (b<0 ? throw "Access violation: " : true) )'
                "{ char ch; if( !cin.get(ch) ) return 70; mem[b] = (unsigned char)ch; }"
                " else if( false )",
            ),
            ("cout<<(unsigned char)(mem[a])", "cout<<(unsigned char)(mem.rd(a))"),
            ("int ma = mem[a];", "long long ma = mem.rd(a);"),
            (
                "cout<<s<<\" ip=\"<<ip<<'\\n';",
                "cerr<<s<<\" ip=\"<<ip<<'\\n'; return 71;",
            ),
        ),
    ),
    "deadfish": Spec(
        "deadfish",
        deadfish_program,
        lambda _rng, _program: "",
        ref_stdin=lambda program, _stdin: "".join(char + "\n" for char in program),
        patches=(
            (
                "    cmd = raw_input('>> ')",
                "    try:\n        cmd = input()\n    except EOFError:\n        break",
            ),
            ("print accumulator", "print(accumulator)"),
            # Ours ignores non-commands (the shell printed a complaint) and
            # honours the optional `h`.
            (
                "    else:\n        print 'Unrecognized command.'",
                "    elif cmd == 'h':\n        break",
            ),
        ),
    ),
}


def _env_name(language: str) -> str:
    return "ESOLANGS_REF_" + re.sub(r"[^A-Z0-9]", "_", language.upper())


def campaign(runner: Runner, programs: int, seed: int) -> list[tuple[Case, int]]:
    """Run ``programs`` random cases; return one minimized case per cause."""
    rng = random.Random(seed)
    groups: dict[str, list[Case]] = {}
    for _ in range(programs):
        program = runner.spec.program(rng)
        case = runner.check(program, runner.spec.stdin(rng, program))
        if case is not None:
            groups.setdefault(case.cause, []).append(case)
    print(f"statuses (ours/ref): {dict(runner.tally.most_common())}")
    found = []
    for cases in groups.values():
        shortest = min(cases[:20], key=lambda c: len(c.program) + len(c.stdin))
        found.append((runner.minimize(shortest), len(cases)))
    return found


def main(argv: Sequence[str] | None = None) -> int:
    """Run a campaign, or patch a reference source with ``--patch``."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("language", choices=sorted(SPECS))
    parser.add_argument("--ref", help="reference command template ({program})")
    parser.add_argument("--programs", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--ref-timeout", type=float, default=1.0)
    parser.add_argument(
        "--patch", type=Path, help="patch this reference source in place"
    )
    args = parser.parse_args(argv)
    spec = SPECS[args.language]
    if args.patch is not None:
        args.patch.write_text(
            apply_patches(args.patch.read_text("latin-1"), spec.patches), "latin-1"
        )
        return 0
    template = args.ref or os.environ.get(_env_name(spec.language))
    if not template:
        parser.error(f"give --ref or set {_env_name(spec.language)}")
    runner = Runner(spec, template, args.ref_timeout)
    found = campaign(runner, args.programs, args.seed)
    print(f"{spec.language}: {args.programs} programs, seed {args.seed}")
    print(f"{len(found)} causes")
    for case, count in found:
        print(f"\n[{count}x] {case.cause}")
        print(f"  program: {case.program!r}\n  stdin:   {case.stdin!r}")
        for side, got in (("ours", case.ours), ("ref", case.ref)):
            print(
                f"  {side:4}:    {got.status} {got.output[:120]!r} {got.detail[:160]}"
            )
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
