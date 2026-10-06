"""Generators and adapters for five languages checked against clean-room refs.

123, BIO, Jaune, NoComment and Sophie have no other implementation, so each
reference is a "blind" interpreter written from the wiki text alone::

    cp blind/<slug>.py ref_<slug>.py
    python scripts/differential.py LANG --patch ref_<slug>.py   # if any
    python scripts/differential.py LANG --ref \
        "env BLIND_STEP_LIMIT=<5 x max_steps> python3 ref_<slug>.py {program}"

Patches bring a reference to a reading our docstrings record as a choice
the page leaves open.  ``differential.py`` registers ``SPECS``.
"""

from __future__ import annotations

import dataclasses
import random
import re
import sys
from typing import Any

_harness = sys.modules.get("differential") or sys.modules["__main__"]
Spec = _harness.Spec


def blind_outcome(code: int, stdout: bytes, stderr: bytes) -> object:
    """Map a blind reference's exit as the harness does, the limit as ``timeout``."""
    got = _harness.blind_outcome(code, stdout, stderr)
    return dataclasses.replace(got, status="timeout") if code == 124 else got


def ascii_input(rng: random.Random, _program: str) -> str:
    """Return ASCII input, now and then empty."""
    pool = "aZ09 \n\x00\x7f"
    return "".join(rng.choice(pool) for _ in range(rng.choice((0, 2, 5, 8))))


def one_two_three_program(rng: random.Random) -> str:
    """Return a ``123`` string, ``1``-heavy at the end so it can halt.

    Some carry the wiki cat or a NOP character.  None is empty: ours
    refuses what the page (and the reference) loop on.
    """
    body = "".join(
        rng.choice("1112223") for _ in range(rng.randint(1, rng.choice((6, 20))))
    )
    if rng.random() < 0.2:
        body = "111212112" + body
    if rng.random() < 0.6:
        body += "1" * rng.randint(1, 4)
    if rng.random() < 0.1:
        k = rng.randint(0, len(body))
        body = body[:k] + rng.choice(" \nx") + body[k:]
    return body


def _bio_block(rng: random.Random, depth: int) -> list[str]:
    """Return BIO commands; a loop decrements its own register most times."""
    out: list[str] = []
    for _ in range(rng.randint(1, 5)):
        reg = rng.choice("xyz")
        roll = rng.random()
        if roll < 0.35:
            out += ["0o" + reg + ";"] * rng.randint(1, 4)
        elif roll < 0.5:
            out.append("1o" + reg + ";")
        elif roll < 0.75:
            out.append("1i" + reg + ";")
        elif depth < 2:
            body = _bio_block(rng, depth + 1)
            if rng.random() < 0.8:
                body.insert(rng.randint(0, len(body)), "1o" + reg + ";")
            out.append("0i" + reg + "{" + "".join(body) + "};")
    return out


def bio_program(rng: random.Random) -> str:
    """Return a BIO program: random case, spacing, now and then a comment."""
    words = _bio_block(rng, 0)
    text = ""
    for word in words:
        if rng.random() < 0.3:
            word = "".join(c.upper() if rng.random() < 0.5 else c for c in word)
        text += word + rng.choice(("", "", " ", "\n", " //c\n"))
    if rng.random() < 0.05:
        k = rng.randint(0, len(text))
        # Not a space: ours refuses one inside a command, the reference not.
        text = text[:k] + rng.choice(("}", ";", "q", "/")) + text[k:]
    return text


#: Our reading of an out-of-byte ``1i``: the value mod 256.
BIO_PATCHES = (
    ("                return 3\n", "                pass\n"),
    ("out.append(v)", "out.append(v % 256)"),
)


def _jaune_number(rng: random.Random) -> str:
    """Return a literal (sometimes signed) or ``v``."""
    if rng.random() < 0.2:
        return "v"
    return rng.choice(("", "", "", "+", "-")) + str(rng.choice((0, 1, 1, 2, 3, 10)))


def _jaune_unit(rng: random.Random, base: int, *, calls: bool) -> str:
    """Return a command run; labels from ``base``, each defined once.

    Each unit has its own labels: ours resolves a label program-wide, the
    reference within the unit, and the page says neither.  Most jumps name
    a defined label.
    """
    defined = rng.sample(range(base, base + 3), rng.randint(0, 3))
    out = [f"{label}:" for label in defined]
    for _ in range(rng.randint(1, 8)):
        roll = rng.random()
        if roll < 0.35:
            out.append(rng.choice("^><#&%"))
        elif roll < 0.7:
            out.append(_jaune_number(rng) + rng.choice("+-"))
        elif roll < 0.9:
            label = rng.choice(defined) if defined and rng.random() < 0.9 else base
            # A read label is main's only: input names labels 0..2.
            read = base == 0 and rng.random() < 0.1
            out.append(f"{'v' if read else label}{rng.choice('?!')}")
        elif calls:
            out.append(rng.choice(("1", "2", "v")) + "@")
    rng.shuffle(out)
    return "".join(out)


def jaune_program(rng: random.Random) -> str:
    """Return a main program, ``.``, and up to two subroutines."""
    text = _jaune_unit(rng, 0, calls=True) + "."
    for name in rng.sample((1, 2), rng.randint(0, 2)):
        text += f"{name}$" + _jaune_unit(rng, 3 * name, calls=rng.random() < 0.3) + ";"
    return text


def jaune_input(rng: random.Random, _program: str) -> str:
    """Return integers that name main's labels, now and then a non-number."""
    pool = ("0", "1", "2", "-1", "10", "0", "1")
    tokens = [rng.choice(pool) for _ in range(rng.choice((0, 2, 5, 12)))]
    if tokens and rng.random() < 0.05:
        tokens[-1] = "x"
    return " ".join(tokens)


_JAUNE_TOKEN = re.compile(r"(?:[+-]?\d+|v)[-+:?!$@]|.", re.DOTALL)
_JAUNE_GRAMMAR = re.compile(
    r"(?:[\^><#&%]|(?:[+-]?\d+|v)[-+?!@]|[+-]?\d+:)*\."
    r"(?:\d+\$(?:[\^><#&%]|(?:[+-]?\d+|v)[-+?!@]|[+-]?\d+:)*;)*"
)


def jaune_split(program: str) -> list[str]:
    """Return whole commands, so shrinking never splits a number."""
    return _JAUNE_TOKEN.findall(program)


def jaune_valid(program: str) -> bool:
    """Whether ``program`` is in the page's EBNF (``v:``/``v$`` excluded)."""
    return _JAUNE_GRAMMAR.fullmatch(program) is not None


#: Our readings: ``^`` writes the number with no separator, and a jump to
#: an undefined label errors whether or not it is taken.
JAUNE_PATCHES = (
    ('str(cells.get(ptr, 0)) + "\\n"', "str(cells.get(ptr, 0))"),
    (
        '            if (v != 0) == (op == "?"):\n'
        "                if arg not in labs:\n"
        '                    raise RunError("no label %d" % arg)\n',
        "            if arg not in labs:\n"
        '                raise RunError("no label %d" % arg)\n'
        '            if (v != 0) == (op == "?"):\n',
    ),
)


def nocomment_program(rng: random.Random) -> str:
    """Return a command string: pushes to jump by, cells kept small."""
    body = "".join(
        rng.choice("iiiiddcllrrnnnnfsbbo") for _ in range(rng.randint(1, 25))
    )
    if rng.random() < 0.1:
        k = rng.randint(0, len(body))
        body = body[:k] + rng.choice(" xA") + body[k:]
    return body


#: Our readings: a 4096-cell tape, a jump to one past the end is out of the
#: code space, and a non-command errors when reached (output first).
NOCOMMENT_PATCHES = (
    ("MEM = 30000", "MEM = 4096"),
    ("ip + 1 > n:", "ip + 1 >= n:"),
    (
        "            sys.exit(2)\n",
        "            src = src[:k] + '\\x00' + src[k + 1 :]\n",
    ),
    (
        '        elif c in "sb":',
        '        elif c == "\\x00":\n'
        "            code = 2\n"
        "            break\n"
        '        elif c in "sb":',
    ),
)


def _sophie_const(rng: random.Random) -> str:
    """Return a constant: a character, or ``$`` and digits."""
    if rng.random() < 0.4:
        return "$" + str(rng.choice((0, 0, 1, 48, 49, 65, 300)))
    return rng.choice("0aA1 ,#$")


def _sophie_block(rng: random.Random, depth: int, *, loop: bool) -> str:
    """Return Sophie commands; a loop holds a ``*`` under a condition."""
    out = []
    for _ in range(rng.randint(1, 5)):
        roll = rng.random()
        if roll < 0.3:
            out.append(rng.choice((".", ",", ",", ";", ";", ":")))
        elif roll < 0.5:
            out.append("#" + _sophie_const(rng))
        elif roll < 0.55:
            out.append(rng.choice(("&", "{.,}", "*" if loop else "&")))
        elif depth < 2 and roll < 0.8:
            then = _sophie_block(rng, depth + 1, loop=loop)
            other = "{" + _sophie_block(rng, depth + 1, loop=loop) + "}"
            out.append(
                "@"
                + _sophie_const(rng)
                + "{"
                + then
                + "}"
                + other * (rng.random() < 0.5)
            )
        elif depth < 2:
            body = _sophie_block(rng, depth + 1, loop=True)
            out.append("[;@$0{*}" + body + "]" if rng.random() < 0.6 else f"[{body}*]")
    return "".join(out)


def sophie_program(rng: random.Random) -> str:
    """Return a Sophie program; some are the wiki cat, truth machine or xor."""
    if rng.random() < 0.1:
        return rng.choice(
            (
                "[;@$0{&}{,}]",
                ";@1{[,]}{,&}",
                ":@$0{:@$0{#0,}{#1,}}{:@$0{#1,}{#0,}}&",
            )
        )
    return _sophie_block(rng, 0, loop=False)


def sophie_input(rng: random.Random, _program: str) -> str:
    """Return characters or space-separated numbers."""
    if rng.random() < 0.5:
        return " ".join(rng.choice("0129") for _ in range(rng.choice((0, 2, 4))))
    return ascii_input(rng, _program)


_SOPHIE_TOKEN = re.compile(r"[#@](?:\$\d+|.)|.", re.DOTALL)


def sophie_split(program: str) -> list[str]:
    """Return commands with their constants, so shrinking keeps them whole."""
    return _SOPHIE_TOKEN.findall(program)


def sophie_valid(program: str) -> bool:
    """Whether brackets nest and every ``@c`` opens a block (both refuse else)."""
    tokens, depth = sophie_split(program), []
    for i, token in enumerate(tokens):
        if token[0] == "@" and tokens[i + 1 : i + 2] != ["{"]:
            return False
        if token in "[{":
            depth.append(token)
        elif token in "]}" and (not depth or depth.pop() != "[{"["]}".index(token)]):
            return False
    return not depth


#: Our readings: ``,`` writes a code point as UTF-8 (as ``ours_utf8``
#: encodes ours); ``;`` and ``:`` at EOF raise; ``:`` takes a whitespace
#: token and leaves the accumulator alone unless it is all digits.
SOPHIE_PATCHES = (
    (
        'bytes([a]) if a < 256 else chr(a).encode("utf-8")',
        'chr(a).encode("utf-8")',
    ),
    ("self.acc = 0  # EOF -> 0 (the wiki Cat relies on it)", "raise EOFError"),
    ("return 0  # EOF -> 0, as for ';'", "raise EOFError"),
    (
        "        j = i\n",
        "        k = i\n"
        '        while k < len(d) and d[k] not in b" \\t\\r\\n":\n'
        "            k += 1\n"
        "        self.ip = k\n"
        "        return int(d[i:k]) if d[i:k].isdigit() else None\n",
    ),
    (
        "self.acc = self.read_number()",
        "v = self.read_number()\n"
        "                self.acc = self.acc if v is None else v",
    ),
    (
        "    except RunError as e:",
        "    except EOFError:\n        code = 4\n    except RunError as e:",
    ),
)


def _ours_utf8(*args: Any) -> Any:
    return __import__("differential_blind_c5").ours_utf8(*args)


SPECS: dict[str, Any] = {
    "123": Spec(
        "123",
        one_two_three_program,
        ascii_input,
        max_steps=20_000,
        ref_outcome=blind_outcome,
    ),
    "BIO": Spec(
        "BIO",
        bio_program,
        ascii_input,
        max_steps=20_000,
        ref_outcome=blind_outcome,
        patches=BIO_PATCHES,
    ),
    "Jaune": Spec(
        "Jaune",
        jaune_program,
        jaune_input,
        max_steps=20_000,
        ref_outcome=blind_outcome,
        split=jaune_split,
        valid=jaune_valid,
        patches=JAUNE_PATCHES,
    ),
    "NoComment": Spec(
        "NoComment",
        nocomment_program,
        ascii_input,
        max_steps=20_000,
        ref_outcome=blind_outcome,
        patches=NOCOMMENT_PATCHES,
    ),
    "Sophie": Spec(
        "Sophie",
        sophie_program,
        sophie_input,
        max_steps=20_000,
        ref_outcome=blind_outcome,
        ours=_ours_utf8,
        split=sophie_split,
        valid=sophie_valid,
        patches=SOPHIE_PATCHES,
    ),
}
