r"""Eval, Factor, Fargo, Flowchart, Forbin, Forþ, Grapheme, Home Row, Inject.

None has another implementation, so each reference is a "blind" interpreter
written from the wiki text alone (``blind_outcome``'s exit codes)::

    python scripts/differential.py Eval --ref "python3 BLIND/eval_lang.py {program}"

with ``factor``, ``fargo``, ``forbin``, ``grapheme`` and ``home_row``
likewise; Flowchart, Forþ and Inject prefix ``env BLIND_STEP_LIMIT=30000``,
``200000`` and ``100000`` so that the reference's own limit comes before the
wall clock.  Flowchart's reference reads and writes Boolfuck bytes, ours
``0``/``1`` characters, so the Spec converts.  ``differential.py`` registers
``SPECS``.
"""

from __future__ import annotations

import dataclasses
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
    raise ImportError("import differential_blind_c3 through differential.py")


_d = _harness()
Spec, blind_outcome = _d.Spec, _d.blind_outcome
_NO_INPUT = lambda _rng, _program: ""  # noqa: E731


# --- Eval -----------------------------------------------------------------

_EVAL_ATOMS = ("0", "0", "0+", "0-", "`", "^", "^", "~", "=", ";", "*", ".", ".")
_EVAL_BODIES = ("0+.", "0.", "^.", "`.", "~", "0=", ";", ".", "0+=~")


def eval_block(rng: random.Random, depth: int = 0) -> str:
    """Return Eval commands: pushes, stack moves, ``?`` skips and literals.

    A literal often holds Eval code that a later ``!`` runs, sometimes with
    a backquote (an embedded ``"``) or opened by ``'``.  ``?`` guards a
    one-character command (a skipped literal is a reading the two sides
    differ on) and ``!`` sometimes evaluates an integer.
    """
    parts: list[str] = [rng.choice(("0", "0+", "`", "")) for _ in range(2)]
    for _ in range(rng.randint(1, 10 - 3 * depth)):
        roll = rng.random()
        if roll < 0.55:
            parts.append(rng.choice(_EVAL_ATOMS))
        elif roll < 0.7:
            parts.append("?" + rng.choice("0.;^~=`*+-"))
        elif roll < 0.72:
            parts.append(rng.choice(("0!", "0+!", "0-!")))
        elif roll < 0.9 and depth < 2:
            body = eval_block(rng, depth + 1).replace('"', "`")
            parts.append(rng.choice("\"'") + body + '"' + rng.choice(("!", ".", ";")))
        else:
            parts.append('"' + rng.choice(("ab", "", "x`y", "0+.")) + '"')
    if rng.random() < 0.05:
        parts.append('"' + rng.choice(_EVAL_BODIES))
    return "".join(parts)


# --- Factor ---------------------------------------------------------------


def _primes(limit: int) -> list[int]:
    """Return the primes below ``limit``."""
    sieve = bytearray([1]) * limit
    sieve[:2] = b"\0\0"
    for n in range(2, int(limit**0.5) + 1):
        if sieve[n]:
            sieve[n * n :: n] = bytearray(len(sieve[n * n :: n]))
    return [n for n in range(limit) if sieve[n]]


_PRIMES = _primes(20_000)
_BF_RESIDUE = {char: index for index, char in enumerate("0><+-.,[]") if index}


def factor_bf(rng: random.Random) -> str:
    """Return a balanced brainfuck program that rarely leaves cell 0 leftward.

    Loops decrement their cell, so most halt; ``,`` is fed enough input.
    """
    out: list[str] = []
    ptr = 0
    for _ in range(rng.randint(1, 14)):
        roll = rng.random()
        if roll < 0.35:
            out.append(rng.choice("+-") * rng.randint(1, 5))
        elif roll < 0.55:
            step = rng.randint(1, 2)
            if (ptr >= step and rng.random() < 0.5) or rng.random() < 0.04:
                out.append("<" * step)
                ptr = max(ptr - step, 0)
            else:
                out.append(">" * step)
                ptr += step
        elif roll < 0.7:
            out.append(".")
        elif roll < 0.8:
            out.append(",")
        else:
            out.append(rng.choice(("[-]", "[->+<]", "[>+<-]", "[-.]", "[.-]")))
    return "".join(out)


def factor_encode(rng: random.Random, bf: str) -> int:
    """Encode ``bf`` as ascending primes, sometimes with ignored residues."""
    number, index = 1, 0
    for char in bf:
        if rng.random() < 0.05:
            index += rng.randint(0, 3)
        while _PRIMES[index] % 11 != _BF_RESIDUE[char]:
            index += 1
        number *= _PRIMES[index]
        if rng.random() < 0.08:
            # A prime with residue 0, 9 or 10 (11 itself, 31, 43, ...).
            junk = index
            while _PRIMES[junk] % 11 not in (0, 9, 10):
                junk += 1
            number *= _PRIMES[junk]
        if rng.random() < 0.7:
            # Usually the next command may reuse no prime, so step past it;
            # sometimes stay, making a repeated command an exponent.
            index += 1
    return number


def factor_program(rng: random.Random) -> str:
    """Return a Factor number, sometimes split by comments, or an edge text."""
    roll = rng.random()
    if roll < 0.03:
        return rng.choice(("", "abc", "0", "1", "00", "11", "x1y"))
    text = str(factor_encode(rng, factor_bf(rng)))
    if roll < 0.15:
        cut = rng.randrange(len(text) + 1)
        text = text[:cut] + rng.choice((" ", "\n", "# a+b ", "x")) + text[cut:]
    return text


def factor_split(program: str) -> list[str]:
    """Split a Factor number into its small prime factors, for shrinking.

    Dropping a factor drops instructions; deleting digits instead would
    make numbers with huge prime factors, which neither side factors fast.
    """
    digits = "".join(char for char in program if char.isdigit())
    number = int(digits) if digits else 1
    if number == 0:
        return ["0"]
    factors: list[str] = []
    for prime in _PRIMES:
        while number % prime == 0:
            factors.append(str(prime))
            number //= prime
    return [*factors, str(number)] if number > 1 else factors


def factor_join(tokens: list[str]) -> str:
    """Multiply the factors back into one number."""
    number = 1
    for token in tokens:
        number *= int(token)
    return str(number)


def factor_input(rng: random.Random, _program: str) -> str:
    """Return ASCII input, usually long enough to feed every ``,``."""
    pool = "abc019 \n\x00\x01\x7f"
    size = rng.choice((0, 3, 8, 16, 16, 16))
    return "".join(rng.choice(pool) for _ in range(size))


# --- Fargo ----------------------------------------------------------------


class _FargoGen:
    """Typed random Fargo: integer and array expressions, effects apart.

    ``%`` and ``$`` appear only where their return value is discarded (a
    call line, or an argument of a combinator on one), since the spec gives
    them none.  User functions are pure (``fN``) or effects (``eN``).
    """

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.pure: dict[str, int] = {}
        self.zero: list[str] = []
        self.effects: dict[str, int] = {}

    def literal(self) -> str:
        return self.rng.choice(("0", "1", "10", "11", "101", "0", "1", "1000"))

    def int_expr(self, depth: int, params: tuple[str, ...] = ()) -> str:
        rng = self.rng
        roll = rng.random()
        if depth <= 0 or roll < 0.25:
            if params and rng.random() < 0.5:
                return rng.choice(params)
            return self.literal()
        if roll < 0.4:
            return "@ " + self.int_expr(depth - 1, params)
        if roll < 0.55:
            return rng.choice("<>") + " " + self.int_expr(depth - 1, params)
        if roll < 0.75:
            left = self.int_expr(depth - 1, params)
            return f"{rng.choice('&|^')} {left} {self.int_expr(depth - 1, params)}"
        if roll < 0.85:
            return f"[?] {self.arr_expr(depth - 1, params)} {rng.choice('01')}"
        callable_ = sorted(set(self.pure) - {"apply"})
        if roll < 0.92 and callable_:
            name = rng.choice(callable_)
            args = [self.int_expr(depth - 1, params) for _ in range(self.pure[name])]
            return " ".join((name, *args))
        unary = [name for name, arity in self.pure.items() if arity == 1]
        unary += ["<", ">", "@"]
        if roll < 0.96 and unary and "apply" in self.pure:
            arg = self.int_expr(depth - 1, params)
            return f"apply :{rng.choice(unary)} {arg}"
        body = rng.choice([*self.zero, self.literal()])
        return f": {self.int_expr(depth - 1, params)} {body}"

    def arr_expr(self, depth: int, params: tuple[str, ...] = ()) -> str:
        if depth <= 0 or self.rng.random() < 0.6:
            return "[] " + self.int_expr(depth - 1, params)
        left = self.arr_expr(depth - 1, params)
        return f"+[] {left} {self.arr_expr(depth - 1, params)}"

    def effect(self, depth: int, params: tuple[str, ...] = ()) -> str:
        rng = self.rng
        roll = rng.random()
        if roll < 0.35:
            # ``& 1``: the sides differ on writing a y other than 0 or 1.
            value = "& 1 " + self.int_expr(depth, params)
            return f"% {self.int_expr(1, params)} {value}"
        if roll < 0.5:
            return "$"
        if roll < 0.7 and depth > 0:
            left = self.effect(depth - 1, params)
            return f"{rng.choice('&|^')} {left} {self.effect(depth - 1, params)}"
        zero = [name for name, arity in self.effects.items() if not arity]
        if roll < 0.82 and zero:
            return f": {self.int_expr(depth, params)} {rng.choice(zero)}"
        if self.effects:
            name = rng.choice(sorted(self.effects))
            args = [self.int_expr(depth, params) for _ in range(self.effects[name])]
            return " ".join((name, *args))
        return "$"

    def program(self) -> str:
        rng = self.rng
        lines: list[str] = []
        for index in range(rng.randint(0, 4)):
            params = ("a", "b", "c")[: rng.randint(0, 2)]
            if rng.random() < 0.5:
                name = f"f{index}"
                head = self.int_expr(2, params)
                if head.split()[0] in params or head[0] in "01":
                    head = "| " + head + " 0"
                lines.append(" ".join((name, *params, head)))
                self.pure[name] = len(params)
                if not params:
                    self.zero.append(name)
            else:
                name = f"e{index}"
                lines.append(" ".join((name, *params, self.effect(2, params))))
                self.effects[name] = len(params)
        if rng.random() < 0.3:
            # A raw argument, called with the arity of what it is given.
            lines.append("apply :g a g a")
            self.pure["apply"] = 2
        for _ in range(rng.randint(1, 5)):
            lines.append(self.effect(2))
            if rng.random() < 0.5:
                lines.append("$")
        if rng.random() < 0.1:
            lines.insert(rng.randrange(len(lines) + 1), "# a comment $")
        return "\n".join(lines)


def fargo_program(rng: random.Random) -> str:
    """Return a Fargo program; now and then the wiki truth-machine."""
    if rng.random() < 0.03:
        # Without its zero-width spaces: the harness writes Latin-1.
        return "one ^ $ one\n% 0 @ 0\n: @ 0 one\n$"
    return _FargoGen(rng).program()


def fargo_input(rng: random.Random, _program: str) -> str:
    """Return the input number in decimal, sometimes absent."""
    return rng.choice(("", "0", "1", "5", "6", "13", "255", "1024"))


# --- Home Row -------------------------------------------------------------


def home_row_program(rng: random.Random) -> str:
    """Return Home Row commands with ``l`` pairs that mostly count down.

    Edge cases: ``s`` below zero, ``k`` past 255, ``j`` before an ``l`` or
    a non-command, torus wraps, and a stray character between commands.
    """

    def block(depth: int) -> str:
        parts = []
        for _ in range(rng.randint(1, 6)):
            roll = rng.random()
            if roll < 0.3:
                parts.append(rng.choice("as") * rng.randint(1, 5))
            elif roll < 0.5:
                parts.append(rng.choice("df") * rng.randint(1, 6))
            elif roll < 0.62:
                parts.append("k")
            elif roll < 0.75:
                parts.append("j" + rng.choice("asdfk;l "))
            elif roll < 0.85 and depth == 0:
                parts.append("l" + block(1) + "sl")
            elif roll < 0.9:
                parts.append(rng.choice(("a" * 300 + "k", ";", " ", "\n", "g")))
            else:
                parts.append("a" * rng.randint(1, 4) + "lsl")
        return "".join(parts)

    program = block(0)
    if program.count("l") % 2 and rng.random() < 0.9:
        program += "l"
    return program


# --- Grapheme -------------------------------------------------------------

_GR_DIGITS = "ABCDEGIJZ"  # intmode letters (no F); J..Y carry into a digit
_GR_COMMANDS = "ABCDGIJKLMNOPQRSTWYZ"
#: Commands safe to skip: a skip counts letters here, instructions in the
#: reference, so ``U``/``V``/``X`` are followed by two of these.
_GR_PLAIN = "ABCDJKLMNOPRSTY"


def _gr_literal(rng: random.Random) -> str:
    """Return one int, string or function literal."""
    roll = rng.random()
    if roll < 0.5:
        return (
            "F"
            + "".join(rng.choice(_GR_DIGITS) for _ in range(rng.randint(0, 3)))
            + "F"
        )
    if roll < 0.8:
        letters = "ABCDFGHIJKLXYZ"
        return (
            "E" + "".join(rng.choice(letters) for _ in range(rng.randint(0, 4))) + "E"
        )
    body = "".join(
        rng.choice(("FAF", "FBF", "K", "Y", "M", "A", "L", "N", "J", "EAE"))
        for _ in range(rng.randint(0, 3))
    )
    return "H" + body + "H"


def grapheme_program(rng: random.Random) -> str:
    """Return literals interleaved with commands, mostly with enough operands.

    Edge cases: skips (``U``/``V``/``X``) before literals, ``Z`` loops that
    drain the stack, ``J``/``N`` conversions, string arithmetic, ``G`` on a
    string, ``D`` of an unset name, an unterminated literal at the end.
    """
    parts = [_gr_literal(rng) for _ in range(rng.randint(2, 5))]
    for _ in range(rng.randint(1, 10)):
        roll = rng.random()
        if roll < 0.4:
            parts.append(_gr_literal(rng))
        elif roll < 0.85:
            parts.append(rng.choice(_GR_COMMANDS) + "KY" * (rng.random() < 0.3))
        elif roll < 0.92:
            parts.append(rng.choice(("HMHZ", "HKYMHZ", "EAKYEG")))
        elif roll < 0.97:
            skip = rng.choice(("U", "X", "FBFFZFV", "FAFFZFV", "FZFFZFV", "FBFFAFV"))
            parts.append(skip + "".join(rng.choice(_GR_PLAIN) for _ in range(2)))
        else:
            parts.append(rng.choice(("W", "WJ", "WY", "KY", "Y")))
    if rng.random() < 0.03:
        parts.append(rng.choice("EFH") + "AB")
    return "".join(parts)


def grapheme_closed(program: str) -> bool:
    """Whether every literal closes (shrinking must not open one)."""
    mode = ""
    for char in program:
        if mode:
            mode = "" if char == mode else mode
        elif char in "EFH":
            mode = char
    return not mode


def grapheme_input(rng: random.Random, _program: str) -> str:
    """Return lines of letters or digits, often enough for every ``W``."""
    words = ("A", "AB", "FAF", "Z", "1", "0", "", "HELLO")
    count = rng.choice((0, 1, 2, 4, 8))
    return "".join(rng.choice(words) + "\n" for _ in range(count))


# --- Inject ---------------------------------------------------------------

_INJ_LABELS = ("a", "b", "c", "0")
_INJ_DATA = ("x", "y", "0", "1", "xy", "hello", "", "a;")
_INJ_REGEX = ("x", "y", ".", "x|y", "(x)", "x+", "l+", "x*", "y?", ".*", "^", "$")
_INJ_REPL = ("", "z", "x", "0", "1", "a/b", "q;")
#: Off: no known-divergent shapes (empty matches, blank input lines, EOF,
#: written-in labels, loops), to look for causes they would mask.
_INJ_EDGES = True


def _inj_command(
    rng: random.Random, labels: tuple[str, ...], *, looped: bool = False
) -> str:
    """Return one Inject command line over ``labels``.

    In a loop body only regexes that cannot match empty, so a block never
    grows without bound.
    """
    name = rng.choice(labels)
    roll = rng.random()
    if roll < 0.3:
        return f"send {name}"
    if roll < 0.45:
        return f"readto {name}"
    if roll < 0.7:
        regex = rng.choice(_INJ_REGEX[:7] if looped or not _INJ_EDGES else _INJ_REGEX)
        repl = _INJ_REPL[: 5 if looped else 7 if _INJ_EDGES else 6]
        return f"inject {name}={regex}/{rng.choice(repl)}"
    if roll < 0.8:
        return f"skipif {name}"
    if roll < 0.9:
        return f"skipq {name} {rng.choice(labels)}"
    return "skip"


def inject_program(rng: random.Random) -> str:
    """Return top-level commands, an optional loop block, then data blocks.

    The loop (``loop; ... skipif X ... loop;``) re-runs while a block is
    non-empty; its body often empties or rewrites that block.  Edge cases:
    ``skip`` before a block, overlapping blocks, empty blocks, rewrites of
    the block holding the pointer, regexes that match empty strings.
    """
    labels = _INJ_LABELS[: rng.randint(1, 4)]
    lines = [_inj_command(rng, labels) for _ in range(rng.randint(1, 4))]
    if _INJ_EDGES and rng.random() < 0.4:
        body = [
            _inj_command(rng, labels, looped=True) for _ in range(rng.randint(1, 3))
        ]
        name = rng.choice(labels)
        body.insert(rng.randrange(len(body) + 1), f"inject {name}=.*/")
        body.append(f"skipif {name}")
        lines += ["loop;", *body, "loop;"]
    if rng.random() < 0.5:
        lines.append("skip")
    blocks = [
        [
            f"{name};",
            *rng.sample(_INJ_DATA if _INJ_EDGES else _INJ_DATA[:6], rng.randint(0, 2)),
            f"{name};",
        ]
        for name in labels
    ]
    if len(blocks) >= 2 and rng.random() < 0.2:
        # Overlap: the first block's end moves inside the second.
        first, second = blocks[0], blocks[1]
        blocks[0] = first[:-1]
        blocks[1] = [second[0], first[-1], *second[1:]]
    for block in blocks:
        lines += block
    return "\n".join(lines)


def inject_closed(program: str) -> bool:
    """Whether every label line occurs exactly twice (shrinking keeps pairs)."""
    lines = [line for line in program.split("\n") if line.endswith(";")]
    return all(lines.count(line) == 2 for line in lines)


def inject_input(rng: random.Random, _program: str) -> str:
    """Return a few input lines, sometimes blank, sometimes too few."""
    if not _INJ_EDGES:
        return "".join(rng.choice(("x", "y", "0", "hello")) + "\n" for _ in range(9))
    words = ("x", "y", "0", "1", "hello", "", "xy")
    return "".join(rng.choice(words) + "\n" for _ in range(rng.choice((0, 1, 2, 3, 5))))


# --- Forþ -----------------------------------------------------------------

_FORTH_ATOMS = "0123456789ABCDEF" + "::+-*/%~" * 2 + "......,ocvv"


def _forth_block(rng: random.Random, depth: int) -> str:
    """Return Forþ commands: atoms, ``(...)`` ifs, ``[...1-]`` countdowns."""
    parts: list[str] = []
    for _ in range(rng.randint(1, 10 - 3 * depth)):
        roll = rng.random()
        if roll < 0.75 or depth >= 2:
            parts.append(rng.choice(_FORTH_ATOMS))
        elif roll < 0.87:
            parts.append("(" + _forth_block(rng, depth + 1) + ")")
        else:
            parts.append("[" + _forth_block(rng, depth + 1) + "1-]")
    return "".join(parts)


def forth_program(rng: random.Random) -> str:
    """Return a Forþ program over a deep stack, sometimes storing a scope.

    Ten pushes first keep most binary operators and ``c`` fed; a scope is
    stored under a digit (``{`` peeks, so the key stays) and called by ``;``.
    """
    head = "".join(rng.choice("123456789ABCDEF") for _ in range(10))
    body = _forth_block(rng, 0)
    if rng.random() < 0.3:
        key = rng.choice("123")
        body = f"{key}{{{_forth_block(rng, 1)}}}{body}{key};"
    if rng.random() < 0.05:
        body += rng.choice(("FF*:*:*:*.", "0-1.", "0/", "7~.", "1;"))
    # The newline keeps ``esolangs.run`` from taking ``A.3`` for a path.
    return head + body + "\n"


def forth_input(rng: random.Random, _program: str) -> str:
    """Return a few ASCII lines, enough that ``,`` rarely meets EOF."""
    lines = ["".join(rng.choice("ab09 ") for _ in range(rng.randint(0, 3)))]
    return "\n".join(lines * rng.randint(3, 6)) + "\n"


def forth_balanced(program: str) -> bool:
    """Whether all three bracket kinds nest properly."""
    stack: list[str] = []
    for char in program:
        if char in "([{":
            stack.append({"(": ")", "[": "]", "{": "}"}[char])
        elif char in ")]}" and (not stack or stack.pop() != char):
            return False
    return not stack


# --- Forbin ---------------------------------------------------------------

_FB_VARS = ("x", "y", "z")


class _Forbin:
    """One Forbin program under construction: helpers ``h0..``, then ``main``.

    Every variable is set before use, helpers read only their parameters
    and call only earlier helpers (no recursion), and ``out`` always gets
    eight bits, so most programs halt and avoid the error readings.
    """

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.helpers: list[int] = []  # each helper's arity

    def value(self, names: tuple[str, ...], depth: int = 0) -> str:
        """Return a bit-valued expression over ``names``."""
        rng = self.rng
        roll = rng.random()
        if roll < 0.3 or depth > 1:
            return rng.choice(("0", "1", *names) if names else ("0", "1"))
        if roll < 0.5:
            return "!" + self.value(names, depth + 1)
        if roll < 0.65:
            return "(in 0)"
        if roll < 0.8 and self.helpers:
            k = rng.randrange(len(self.helpers))
            args = [self.value(names, depth + 1) for _ in range(rng.randint(1, 3))]
            return f"(h{k} {', '.join(args)})"
        if roll < 0.9:
            body = self.value(("a", *names), depth + 1)
            return f"(ap (a @ {{return {body};}}), {self.value(names, depth + 1)})"
        return self.value(names, depth + 1)

    def block(self, names: tuple[str, ...], depth: int, *, in_fn: bool) -> str:
        """Return statements; ``names`` are the variables already set."""
        rng = self.rng
        out: list[str] = []

        def v() -> str:
            return self.value(names)

        def bare() -> str:
            # List items are literals: the reference reads ``(`` as a tuple,
            # and it evaluates a variable item per iteration, ours up front.
            return rng.choice("01")

        for _ in range(rng.randint(1, 5 - depth)):
            roll = rng.random()
            if roll < 0.2:
                bits = ", ".join(v() for _ in range(8))
                out.append(f"out {bits};")
            elif roll < 0.35 and names:
                targets = rng.sample(names, rng.randint(1, len(names)))
                if len(targets) > 1 and rng.random() < 0.5:
                    rhs = ", ".join(v() for _ in targets)
                else:
                    rhs = v()
                out.append(f"{', '.join(targets)} = {rhs};")
            elif roll < 0.5 and depth < 2 and names:
                var = rng.choice((*names, "_"))
                inner = self.block(names, depth + 1, in_fn=in_fn)
                # A start opening with ``(`` reads as a list on both sides.
                start = v()
                start = "!!" + start if start[0] == "(" else start
                out.append(f"for {var}:{start}..{v()} {{{inner}}}")
            elif roll < 0.6 and depth < 2 and len(names) >= 2:
                pair = "(" + ", ".join(rng.sample(names, 2)) + ")"
                spec = rng.choice(
                    ("(*, *)", "((1, *))", "((0, *), (1, 1))", f"(({bare()}, *))")
                )
                inner = self.block(names, depth + 1, in_fn=in_fn)
                out.append(f"for {pair}:{spec} {{{inner}}}")
            elif roll < 0.7 and depth < 2 and names:
                items = ", ".join(rng.choice(("0", "1", "*", bare())) for _ in range(3))
                inner = self.block(names, depth + 1, in_fn=in_fn)
                out.append(f"for {rng.choice(names)}:({items}) {{{inner}}}")
            elif roll < 0.78 and self.helpers:
                k = rng.randrange(len(self.helpers))
                args = ", ".join(v() for _ in range(rng.randint(1, 3)))
                out.append(f"h{k} {args};")
            elif roll < 0.84 and depth < 2:
                out.append("{" + self.block(names, depth + 1, in_fn=in_fn) + "} 0;")
            elif roll < 0.9 and in_fn:
                out.append(f"return {v()};")
            elif names:
                out.append(f"{rng.choice(names)} = {v()};")
        return ("\n" if depth == 0 else " ").join(out)

    def program(self) -> str:
        """Return helpers and a ``main`` that first sets every variable."""
        rng = self.rng
        lines = ["ap f, b { return (f b); }"]
        for k in range(rng.randint(0, 2)):
            params = tuple(f"p{i}" for i in range(rng.randint(1, 3)))
            body = self.block(params, 0, in_fn=True)
            lines.append(f"h{k} {', '.join(params)} {{ {body} }}")
            self.helpers.append(len(params))
        init = f"{', '.join(_FB_VARS)} = {rng.choice('01')};"
        if rng.random() < 0.05:  # the readings the notes list as open
            init += rng.choice(
                ("out 0,1;", "return;", "for w:(0) {}", "x, y = 0, 1, 1;", "q;")
            )
        lines.append(f"main {{\n{init}\n{self.block(_FB_VARS, 0, in_fn=True)}\n}}")
        return "\n".join(lines)


def forbin_program(rng: random.Random) -> str:
    """Return a Forbin program (see :class:`_Forbin`)."""
    return _Forbin(rng).program()


def forbin_input(rng: random.Random, _program: str) -> str:
    """Return enough ASCII bytes that ``in`` rarely meets EOF."""
    return "".join(rng.choice("abcxyz019 \n\x01") for _ in range(rng.randint(40, 60)))


# --- Flowchart --------------------------------------------------------------

_N, _E, _S, _W = "NESW"
_GLYPHS = {
    frozenset("EW"): "─",
    frozenset("NS"): "│",
    frozenset("ES"): "┌",
    frozenset("SW"): "┐",
    frozenset("NE"): "└",
    frozenset("NW"): "┘",
    frozenset("EWS"): "┬",
    frozenset("EWN"): "┴",
    frozenset("NSE"): "├",
    frozenset("NSW"): "┤",
    frozenset("NESW"): "┼",
}
#: Node spellings, weighted; ``( )`` is placed separately (forks multiply).
_FC_NODES = (
    ["(( ))"] * 5
    + ["< >"] * 5
    + ["\\ \\"] * 5
    + ["[ ]", "{ ]", "[ }", "{ }", "/ /", "/ /"]
    + ["\\[ ]/", "/[ ]\\", "\\{ }/", "/{ }\\", "< ]", "[ >"]
)


def flowchart_program(rng: random.Random) -> str:
    """Return a Flowchart grid: nodes and junctions on a lattice of slots.

    Slot ``(r, c)`` spans row ``2r``, columns ``6c..6c+4``, centred on
    ``6c+2``; edges join neighbouring slots through column ``6c+5`` or row
    ``2r+1``.  A junction slot draws the glyph whose arms are exactly its
    edges, so no path dead-ends; every node is joined to something.
    """
    rows, cols = rng.randint(1, 4), rng.randint(2, 6)
    kind: dict[tuple[int, int], str] = {}
    for r in range(rows):
        for c in range(cols):
            roll = rng.random()
            if roll < 0.6:
                kind[(r, c)] = rng.choice(_FC_NODES)
            elif roll < 0.85:
                kind[(r, c)] = "path"
    arms: dict[tuple[int, int], set[str]] = {slot: set() for slot in kind}
    for r, c in kind:
        if (r, c + 1) in kind and rng.random() < 0.7:
            arms[(r, c)].add(_E)
            arms[(r, c + 1)].add(_W)
        if (r + 1, c) in kind and rng.random() < 0.5:
            arms[(r, c)].add(_S)
            arms[(r + 1, c)].add(_N)
    step = {_N: (-1, 0, _S), _S: (1, 0, _N), _E: (0, 1, _W), _W: (0, -1, _E)}
    stubs = [slot for slot in kind if kind[slot] == "path" and len(arms[slot]) < 2]
    while stubs:  # prune junctions that would dead-end, and their edges
        r, c = slot = stubs.pop()
        if slot not in kind:
            continue
        for arm in arms.pop(slot):
            dr, dc, back = step[arm]
            other = (r + dr, c + dc)
            arms[other].discard(back)
            if kind[other] == "path" and len(arms[other]) < 2:
                stubs.append(other)
        del kind[slot]
    kind = {slot: node for slot, node in kind.items() if arms[slot]}
    for slot in kind:  # a leaf is mostly an end, else it is a dead end
        if len(arms[slot]) == 1 and rng.random() < 0.75:
            kind[slot] = "(( ))"
    # A fork with three or more paths re-entered in a loop doubles the
    # pointers every lap; at most two paths, it splits only at the start.
    linked = [slot for slot in kind if kind[slot] != "path" and len(arms[slot]) <= 2]
    if not linked:
        return utf8_as_latin1("( )─(( ))")
    for slot in rng.sample(linked, min(len(linked), rng.choice((1, 1, 1, 2)))):
        kind[slot] = "( )"
    grid = [[" "] * (6 * cols) for _ in range(2 * rows)]
    for (r, c), node in kind.items():
        here, row = arms[(r, c)], grid[2 * r]
        if _E in here:
            row[6 * c + 5] = "─"
        if _S in here:
            grid[2 * r + 1][6 * c + 2] = "│"
        text = _GLYPHS[frozenset(here)] if node == "path" else node
        left = 6 * c + 2 - len(text) // 2
        if _W in here:
            row[6 * c : left] = "─" * (left - 6 * c)
        if _E in here:
            row[left + len(text) : 6 * c + 5] = "─" * (6 * c + 5 - left - len(text))
        row[left : left + len(text)] = text
    return utf8_as_latin1("\n".join("".join(line).rstrip() for line in grid))


def utf8_as_latin1(text: str) -> str:
    """Spell ``text``'s UTF-8 bytes as Latin-1 characters.

    The harness writes a program to the reference in Latin-1, and the box
    drawing needs UTF-8; ``Spec.ours`` undoes this before running ours.
    """
    return text.encode("utf-8").decode("latin-1")


def latin1_as_utf8(text: str) -> str:
    """Undo :func:`utf8_as_latin1`."""
    return text.encode("latin-1").decode("utf-8")


def flowchart_split(program: str) -> list[str]:
    """One token per character of the decoded grid (whole UTF-8 sequences)."""
    return [utf8_as_latin1(char) for char in latin1_as_utf8(program)]


def flowchart_input(rng: random.Random, _program: str) -> str:
    """Return bits, eight per ASCII byte, least significant first."""
    data = [rng.randrange(128) for _ in range(rng.choice((0, 1, 2, 4)))]
    return "".join(str(byte >> k & 1) for byte in data for k in range(8))


def pack_bits(bits: str, *, pad: bool) -> bytes:
    """Pack ``0``/``1`` characters into bytes, least significant bit first."""
    if pad and len(bits) % 8:
        bits += "0" * (8 - len(bits) % 8)
    return bytes(int(bits[i : i + 8][::-1], 2) for i in range(0, len(bits) // 8 * 8, 8))


def flowchart_ours(d: Any) -> Callable[[str, str, str, int], Any]:
    """Return a ``Spec.ours`` that packs our ``0``/``1`` output into bytes.

    Ours writes each bit as a character; the reference follows Boolfuck,
    padding a partial byte only at a normal halt.
    """

    def ours(language: str, program: str, stdin: str, max_steps: int) -> Any:
        program = latin1_as_utf8(program)
        got = d.run_ours(language, program, stdin, max_steps)
        if got.status != "timeout":
            fast = d.run_ours_fast(language, program, stdin)
            if fast.status != got.status or (
                got.status == "halt" and fast.output != got.output
            ):
                return d.Outcome("crash:fastpath", b"", f"{got} vs {fast}")
        bits = got.output.decode()
        return dataclasses.replace(
            got, output=pack_bits(bits, pad=got.status == "halt")
        )

    return ours


def flowchart_stdin(_program: str, bits: str) -> str:
    """Our input bits as the bytes the reference reads."""
    return pack_bits(bits, pad=False).decode("ascii")


# --- shared ---------------------------------------------------------------


def as_ours(encode: Callable[[str], bytes]) -> Callable[[bytes], bytes]:
    """Re-encode a reference's UTF-8 output the way the harness encodes ours."""
    return lambda out: encode(out.decode("utf-8", "surrogatepass"))


def converted(
    outcome: Callable[[int, bytes, bytes], Any], convert: Callable[[bytes], bytes]
) -> Callable[[int, bytes, bytes], Any]:
    """Return ``outcome`` with the reference's output converted."""

    def adapted(code: int, stdout: bytes, stderr: bytes) -> Any:
        got = outcome(code, stdout, stderr)
        return dataclasses.replace(got, output=convert(got.output))

    return adapted


def _lines(program: str) -> list[str]:
    return program.split("\n")


SPECS: dict[str, Any] = {
    "Eval": Spec(
        "Eval",
        eval_block,
        lambda _rng, _program: "",
        max_steps=20_000,
        ref_outcome=blind_outcome,
    ),
    "Factor": Spec(
        "Factor",
        factor_program,
        factor_input,
        max_steps=20_000,
        ref_outcome=blind_outcome,
        split=factor_split,
        join=factor_join,
    ),
    "Fargo": Spec(
        "Fargo",
        fargo_program,
        fargo_input,
        max_steps=20_000,
        ref_outcome=blind_outcome,
        split=_lines,
        join="\n".join,
    ),
    "Grapheme": Spec(
        "Grapheme",
        grapheme_program,
        grapheme_input,
        max_steps=20_000,
        ref_outcome=blind_outcome,
        valid=grapheme_closed,
    ),
    "Inject": Spec(
        "Inject",
        inject_program,
        inject_input,
        max_steps=5_000,
        ref_outcome=blind_outcome,
        split=lambda program: program.split("\n"),
        join="\n".join,
        valid=inject_closed,
    ),
    "Home Row": Spec(
        "Home Row",
        home_row_program,
        _NO_INPUT,
        max_steps=20_000,
        ref_outcome=blind_outcome,
    ),
    "Forþ": Spec(
        "Forþ",
        forth_program,
        forth_input,
        max_steps=20_000,
        ref_outcome=converted(blind_outcome, as_ours(_d._bytes)),  # noqa: SLF001
        valid=forth_balanced,
    ),
    "Forbin": Spec(
        "Forbin",
        forbin_program,
        forbin_input,
        max_steps=20_000,
        ref_outcome=blind_outcome,
        split=re.compile(r"\w+|\S").findall,
        join=" ".join,
    ),
    "Flowchart": Spec(
        "Flowchart",
        flowchart_program,
        flowchart_input,
        max_steps=3_000,
        ref_stdin=flowchart_stdin,
        ref_outcome=blind_outcome,
        join=_d.befunge_join,
        blank=" ",
        split=flowchart_split,
        ours=flowchart_ours(_d),
    ),
}
