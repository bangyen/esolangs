"""Generators and adapters for eight languages checked against clean-room refs.

Smallfuck, Minsky Swap, Collatz Multiverse, ArrowQueue, the six S*bleq
variants, BF-PDA, BFStack and bit~ have no other implementation, so each
reference is a "blind" interpreter written from the wiki text alone:
``--ref "python3 blind/<slug>.py {program}"`` (Smallfuck adds
``env SMALLFUCK_TAPE_LEN=1``, the S*bleq variants ``env BLIND_VARIANT=<name>``,
Collatz Multiverse ``env BLIND_STEP_LIMIT=100000`` so that its own limit,
whose output is converted, comes before the wall clock's, whose is not).
``differential.py`` registers the Specs.
"""

from __future__ import annotations

import dataclasses
import random
from collections.abc import Callable
from typing import Any


def converted(
    outcome: Callable[[int, bytes, bytes], Any], convert: Callable[[bytes], bytes]
) -> Callable[[int, bytes, bytes], Any]:
    """Return ``outcome`` with the reference's output in our spelling."""

    def adapted(code: int, stdout: bytes, stderr: bytes) -> Any:
        got = outcome(code, stdout, stderr)
        return dataclasses.replace(got, output=convert(got.output))

    return adapted


def sbleq_variant(
    store: str, *, indirect: bool, harness: tuple[Any, Any, Any]
) -> Callable[[str, str, str, int], Any]:
    """Run an S*bleq variant, which the registry does not name.

    ``harness`` is ``(Outcome, _bytes, _ours_status)`` from the harness.
    """
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.sbleq import _Machine

    outcome, encode, status_of = harness

    def ours(_language: str, program: str, stdin: str, max_steps: int) -> Any:
        io = ScriptedIO(stdin)
        try:
            machine = _Machine(program, io, store, indirect=indirect)
            for _ in range(max_steps):
                if machine.halted:
                    return outcome("halt", encode(io.getvalue()))
                machine.step()
            return outcome("timeout", encode(io.getvalue()))
        except ValueError as exc:
            return outcome("error", encode(io.getvalue()), str(exc))
        except Exception as exc:
            return outcome(status_of(exc), b"", f"{type(exc).__name__}: {exc}")

    return ours


def bf_like(
    generate: Callable[[random.Random], str], table: dict[str, str]
) -> Callable[[random.Random], str]:
    """Return ``generate`` (brainfuck) spelled in another alphabet."""
    trans = str.maketrans(table)
    return lambda rng: generate(rng).translate(trans) or table["+"]


def minsky_program(rng: random.Random) -> str:
    """Return a code line and a jump line: targets in range, past it, or 0.

    Now and then a stray character, a comma, or a jump number too many or
    too few.
    """
    code = "".join(rng.choice("++~~*") for _ in range(rng.randint(1, 10)))
    size = len(code)
    jumps = [
        rng.choice((rng.randint(1, size),) * 4 + (size + 1, size + 3, 0))
        for _ in range(code.count("~") + (rng.random() < 0.05))
    ]
    if jumps and rng.random() < 0.03:
        jumps.pop()
    if rng.random() < 0.03:
        at = rng.randrange(size + 1)
        code = code[:at] + rng.choice(" x") + code[at:]
    return code + "\n" + rng.choice((" ", " ", ",")).join(map(str, jumps))


_CM_NAMES = ("a", "b", "c", "negativeOne", "lineNumber", "input", "arr")
_CM_INDEXED = ("arr[a]", "arr[b]", "arr[negativeOne]", "arr[input]", "b[c]")


def collatz_program(rng: random.Random) -> str:
    """Return lines ``v = v x + v, DO|NOT PRINT.``; rarely a malformed one."""

    def operand(pool: tuple[str, ...] = _CM_NAMES) -> str:
        return rng.choice(pool * 3 + _CM_INDEXED)

    lines = [
        f"{operand(_CM_NAMES[:5])} = {operand()} x + {operand()}, "
        f"{rng.choice(('DO', 'NOT'))} PRINT."
        for _ in range(rng.randint(1, 6))
    ]
    if rng.random() < 0.03:
        lines.insert(
            rng.randrange(len(lines)), rng.choice(("a = 3 x + 1, DO PRINT.", ""))
        )
    return "\n".join(lines)


def collatz_input(rng: random.Random, _program: str) -> str:
    """Return integer tokens our ``input`` reads (the reference reads bytes)."""
    return " ".join(str(rng.randint(0, 127)) for _ in range(rng.choice((0, 2, 4, 8))))


def arrowqueue_program(rng: random.Random) -> str:
    """Return a small ragged grid of turns, enqueues, dequeues and blanks."""
    rows = [
        "".join(rng.choice("**~~+  x") for _ in range(rng.randint(0, 8)))
        for _ in range(rng.randint(1, 5))
    ]
    return rng.choice("~~* +") + "\n".join(rows)


def sbleq_program(rng: random.Random) -> str:
    """Return triples over a data region, usually ending in a halting triple.

    Cell ``h`` (after the code) holds -1, so ``c = h`` halts on a jump; the
    cell after it holds its own address, a zero source for direct and
    indirect variants alike.  Operands are data cells, any cell, or the
    special -1/-2/-3; data holds addresses, code starts, specials and bytes.
    """
    count = rng.randint(1, 5)
    halt = 3 * count
    size = halt + rng.randint(3, 7)

    def operand() -> int:
        roll = rng.random()
        return (
            rng.randrange(halt, size)
            if roll < 0.75
            else rng.randrange(size)
            if roll < 0.88
            else rng.choice((-1, -2, -3))
        )

    cells = []
    for _ in range(count - (rng.random() < 0.8)):
        jump = rng.random()
        c = halt if jump < 0.4 else rng.randrange(halt, size) if jump < 0.97 else -1
        cells += [operand(), operand(), c]
    if len(cells) < halt:
        cells += [halt + 1, halt + 1, halt]
    cells += [-1, halt + 1]
    cells += [
        rng.choice((3 * rng.randrange(count), rng.randrange(size), -2, -3, 65, 1))
        for _ in range(size - len(cells))
    ]
    return " ".join(map(str, cells))


def ascii_input_long(rng: random.Random, _program: str) -> str:
    """Return ASCII input, mostly long enough that EOF is rare."""
    pool = "abcxyz019 \n\x00\x01\x7f"
    return "".join(rng.choice(pool) for _ in range(rng.choice((0, 8, 12, 12))))


#: ``store`` and ``indirect`` per variant; base S*bleq runs through the VM.
SBLEQ_VARIANTS = {
    "S*bleq": ("a", False),
    "S*bl*q": ("ab", False),
    "Subl*q": ("b", False),
    "S**bleq": ("a", True),
    "Subl**q": ("b", True),
    "S**bl**q": ("ab", True),
}


def strip_newline(out: bytes) -> bytes:
    """Minsky Swap: the reference ends its register dump with a newline."""
    return out.removesuffix(b"\n")


def utf8_to_latin1(out: bytes) -> bytes:
    """Collatz Multiverse: the reference writes chr(value) as UTF-8."""
    return out.decode("utf-8", "replace").encode("latin-1", "replace")


def headings(out: bytes) -> bytes:
    """ArrowQueue: the reference's ``RDLU`` letters as our heading numbers."""
    return " ".join(str("RDLU".index(c)) for c in out.decode().strip()).encode()


def tape(machine: object) -> str:
    """Smallfuck: the final tape as the reference prints it."""
    return "".join(map(str, machine.tape)) + "\n"  # type: ignore[attr-defined]
