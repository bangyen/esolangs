"""Generators and adapters for seven languages checked against clean-room refs.

Boolfuck, Bitwise Cyclic Tag, Cyclic tag, FRACTRAN, Unary, HQ9+ and Nope.
against "blind" interpreters written from the wiki text alone::

    python scripts/differential.py LANG --patch blind/<slug>.py   # if any
    python scripts/differential.py LANG --ref \
        "env BLIND_STEP_LIMIT=<5 x max_steps> python3 blind/<slug>.py {program}"

The tag systems' references take the program on line 1 and the data on
stdin and print every deleted bit; ours reads ``program,data`` and prints
the last one, so our side renders the deleted prefix of its queue.
FRACTRAN's reference reads the start value on stdin.
``differential.py`` registers ``SPECS``.
"""

from __future__ import annotations

import random
import sys
from collections.abc import Callable
from typing import Any

_harness = sys.modules.get("differential") or sys.modules["__main__"]
Spec, Outcome, balanced = _harness.Spec, _harness.Outcome, _harness.balanced
_c5 = __import__("differential_blind_c5")
_tarpits = __import__("differential_tarpits")
blind_outcome = _c5.blind_outcome

_Ours = Callable[[str, str, str, int], Any]


def rewritten(build: Callable[[str, str], str], render: Any = None) -> _Ours:
    """Run ours on ``build(program, stdin)`` with no input.

    ``render(machine)`` replaces the output, also on a timeout (the
    references print their output so far).  ``esolangs.run`` must agree
    with the stepping, else the status is a crash.
    """

    def ours(language: str, program: str, stdin: str, max_steps: int) -> Any:
        source = build(program, stdin)
        got = _harness.run_ours(language, source, "", max_steps)
        if got.status != "timeout":
            fast = _harness.run_ours_fast(language, source, "")
            if fast.status != got.status or fast.output != got.output:
                return Outcome("crash:fastpath", b"", f"{got} vs {fast}")
        if render is None or got.status not in ("halt", "timeout"):
            return got
        vm = _harness.make_vm(language, source, "")
        for _ in range(max_steps):
            if vm.halted:
                break
            vm.step()
        return Outcome(got.status, render(vm._machine).encode(), got.detail)  # noqa: SLF001

    return ours


def deleted(machine: Any) -> str:
    """Return the bits a tag system's run has deleted, oldest first."""
    return "".join(machine.data[: machine.read])


def _bits(rng: random.Random, low: int, high: int, ones: float = 0.5) -> str:
    return "".join(
        "1" if rng.random() < ones else "0" for _ in range(rng.randint(low, high))
    )


def bct_program(rng: random.Random) -> str:
    """Return ``0``/``1x`` commands, a wiki example, or a stray symbol."""
    roll = rng.random()
    if roll < 0.05:
        return rng.choice(("00111", "110100", "1011110110100111010110"))
    commands = [rng.choice(("0", "0", "10", "11")) for _ in range(rng.randint(1, 6))]
    program = "".join(commands)
    if rng.random() < 0.2:  # a 1 last, pairing with the first bit
        program += "1"
    if rng.random() < 0.05:
        at = rng.randrange(len(program) + 1)
        program = program[:at] + rng.choice(" 2") + program[at:]
    return program


def tag_data(rng: random.Random, _program: str) -> str:
    """Return the initial data-string, now and then empty."""
    return _bits(rng, 0 if rng.random() < 0.05 else 1, 6, 0.4)


def ct_program(rng: random.Random) -> str:
    """Return comma-separated productions, empty ones included."""
    if rng.random() < 0.05:
        return rng.choice(("011,10,101", "1,0", "010001,100,100100100,,,"))
    return ",".join(
        _bits(rng, 0, 4, 0.3) for _ in range(rng.randint(1, 4))
    ) + rng.choice(("",) * 12 + ("2", " "))


def fractran_program(rng: random.Random) -> str:
    """Return fractions, mostly shrinking ones; integers and zeros now and then."""
    if rng.random() < 0.05:
        return "13/21, 385/13, 1/7, 3/11, 7/2, 1/3"
    tokens = []
    for _ in range(rng.randint(0, 5)):
        roll = rng.random()
        q = rng.choice((1, 2, 3, 5, 6, 7, 9, 10, 15, 21, 30))
        if roll < 0.03:
            tokens.append(rng.choice(("0/3", "3/0", "x")))
        elif roll < 0.06:
            tokens.append(str(rng.randint(1, 4)))
        elif roll < 0.4:  # trades one prime for another, so it halts
            tokens.append(rng.choice(("3/2", "5/3", "7/5", "5/2", "21/10", "15/14")))
        else:
            tokens.append(f"{rng.randint(1, max(1, q - 1))}/{q}")
    return rng.choice((", ", " ", ",")).join(tokens)


def fractran_input(rng: random.Random, _program: str) -> str:
    """Return a positive start: a product of small prime powers, or 1."""
    if rng.random() < 0.02:
        return "0"
    value = 1
    for prime in (2, 3, 5, 7):
        value *= prime ** rng.choice((0, 0, 1, 2, 4))
    return str(value)


_UNARY = "><+-.,[]"


def unary_encode(brainfuck: str) -> str:
    """Return the Unary source of ``brainfuck``: the zero count, in zeros."""
    number = 1
    for command in brainfuck:
        number = 8 * number + _UNARY.index(command)
    return "0" * number


def unary_program(rng: random.Random) -> str:
    """Return a Unary program of at most six commands; cats and bad counts.

    Seven commands would already be 4M zeros.  The cat's stated count
    56623 and its listing's 55623 (``,.,>]``, unmatched) both appear.
    """
    roll = rng.random()
    if roll < 0.03:
        return "0" * rng.choice((56623, 55623))
    if roll < 0.08:
        return "0" * rng.choice((2, 3, 7, 16, 100))  # incomplete triples
    while len(code := _harness.bf_program(rng)) > 6:
        pass
    source = unary_encode(code)
    if rng.random() < 0.05:
        at = rng.randrange(len(source) + 1)
        source = source[:at] + rng.choice("\n x") + source[at:]
    return source


def unary_split(program: str) -> list[str]:
    """Shrink over the decoded commands, or the source when it does not decode."""
    from esolangs.interpreters.tape_based.unary import decode

    try:
        return list(decode(program))
    except ValueError:
        return [program]


def unary_join(tokens: list[str]) -> str:
    """Re-encode decoded commands; pass an undecodable source through."""
    if all(len(t) == 1 and t in _UNARY for t in tokens):
        return unary_encode("".join(tokens))
    return "".join(tokens)


#: ``<`` at cell 0 grows the tape (the repo's brainfuck-family decision).
UNARY_PATCHES = (
    (
        '            if ptr == 0:\n                return out, "left"\n'
        "            ptr -= 1",
        "            if ptr == 0:\n                tape.insert(0, 0)\n"
        "            else:\n                ptr -= 1",
    ),
)

#: Ours prints "Hello, world!" (the linked page's title) and our lyrics,
#: store verse included; both are readings of a spec giving no text.
HQ9_PATCHES = (
    ('out.append("hello, world\\n")', 'out.append("Hello, world!\\n")'),
    (
        "def song():",
        "def song():\n"
        "    def b(k):\n"
        '        return "%d bottle%s" % (k, "" if k == 1 else "s") if k '
        'else "no more bottles"\n'
        "    verses = []\n"
        "    for k in range(99, -1, -1):\n"
        '        act = ("Take one down and pass it around, " + b(k - 1) if k\n'
        '               else "Go to the store and buy some more, 99 bottles")\n'
        '        verses.append("%s of beer on the wall, %s of beer.\\n%s of '
        'beer on the wall.\\n"\n'
        "                      % (b(k).capitalize(), b(k), act))\n"
        '    return "\\n".join(verses)\n\n\ndef _blind_song():',
    ),
)


def hq9_program(rng: random.Random) -> str:
    """Return a short program over the commands, lower case and others."""
    pool = "HQ++hq x\n" + ("9" if rng.random() < 0.1 else "")
    return "".join(rng.choice(pool) for _ in range(rng.randint(1, 8)))


def nope_program(rng: random.Random) -> str:
    """Return any short text but a path, which ``esolangs.run`` refuses."""
    from esolangs import _looks_like_a_path

    while _looks_like_a_path(
        text := "".join(rng.choice("Nope. x\n+[") for _ in range(rng.randint(0, 6)))
    ):
        pass
    return text


def _no_input(_rng: random.Random, _program: str) -> str:
    return ""


def _drop_newline(code: int, stdout: bytes, stderr: bytes) -> Any:
    """FRACTRAN's reference ends its value with a newline; ours does not."""
    got = blind_outcome(code, stdout, stderr)
    return Outcome(got.status, got.output.removesuffix(b"\n"), got.detail)


SPECS: dict[str, Any] = {
    "Boolfuck": Spec(
        "Boolfuck",
        _tarpits.bf_like(_harness.bf_program, {"-": "+", ".": ";"}),
        _harness.ascii_input,
        max_steps=20_000,
        ref_outcome=blind_outcome,
        valid=balanced,
    ),
    "Bitwise Cyclic Tag": Spec(
        "Bitwise Cyclic Tag",
        bct_program,
        tag_data,
        max_steps=5_000,
        ref_outcome=blind_outcome,
        ours=rewritten(lambda program, data: f"{program},{data}", deleted),
    ),
    "Cyclic tag": Spec(
        "Cyclic tag",
        ct_program,
        tag_data,
        max_steps=5_000,
        ref_outcome=blind_outcome,
        ours=rewritten(
            lambda program, data: f"{program.replace(',', ';')},{data}", deleted
        ),
    ),
    "FRACTRAN": Spec(
        "FRACTRAN",
        fractran_program,
        fractran_input,
        max_steps=5_000,
        ref_outcome=_drop_newline,
        ours=rewritten(lambda program, start: f"{start} {program}"),
        split=lambda program: program.split(" "),
        join=" ".join,
    ),
    "Unary": Spec(
        "Unary",
        unary_program,
        _harness.ascii_input,
        max_steps=20_000,
        ref_outcome=blind_outcome,
        split=unary_split,
        join=unary_join,
        patches=UNARY_PATCHES,
    ),
    "HQ9+": Spec(
        "HQ9+", hq9_program, _no_input, ref_outcome=blind_outcome, patches=HQ9_PATCHES
    ),
    "Nope.": Spec("Nope.", nope_program, _no_input, ref_outcome=blind_outcome),
}
