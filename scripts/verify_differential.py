"""Differential-test the in-package interpreters against their native cross-checks.

The ``extra/`` implementations are not upstream references: they are
cross-checks written in this repository (see README "Extra
Implementations").  They still serve as oracles for the in-package Python
interpreters, so this script runs a *full-surface corpus* — every
instruction plus edge cases, not just generator output — through both the
Python interpreter and the native implementation and asserts they agree.

Languages with both an in-package interpreter and a native cross-check:

* **LaserFuck** — ``grid_based/laserfuck.py`` vs ``extra/rust/laserfuck.rs``.
  The Rust reference picks a random initial heading, so its output is a
  *set* across runs; the Python interpreter (which accepts a fixed heading)
  must produce a member of that set for each of the four headings.
* **NoComment** — ``tape_based/nocomment.py`` vs
  ``extra/assembly/nocomment-riscv.s``.  Both implement the full wiki language
  (10 commands over a tape and stack).  The assembly is run under unicorn
  via ``riscv_elf_runner`` and must agree with the Python interpreter on the
  full corpus; both error on non-commands, stack underflow, and out-of-range
  jumps.
* **BF-PDA** — ``stack_based/bf_pda.py`` vs
  ``extra/assembly/bfpda-riscv.s``.  Both implement the full wiki language
  (6 commands over a bit stack whose top is the current cell, with comments).
  The assembly is run under unicorn via ``riscv_elf_runner`` and must agree
  with the Python interpreter on the full corpus; both error on empty
  programs and unbalanced brackets as malformed (exit 2).
* **RAM0** — ``register_based/ram0.py`` vs
  ``extra/assembly/ram0-riscv.s``.  Both implement the full wiki language
  (7 tokens over two registers and RAM, with digit gotos and comments).  The
  assembly is run under unicorn via ``riscv_elf_runner`` and must agree with
  the Python interpreter on the full corpus and the insertion-order state
  dump.
* **BIO** — ``register_based/bio.py`` vs ``extra/assembly/bio-riscv.s``.
  Both implement the full wiki language (3 registers x/y/z, while loops
  guarded by ``0i[xyz]``/``}``, with comments).  The assembly is run under
  unicorn via ``riscv_elf_runner`` and must agree with the Python
  interpreter on the full corpus; both error lazily, matching the Python
  control flow exactly (a loop guard only raises when its skip path scans
  off the end of the program, so a ``}`` that halts first, exit 3, can
  pre-empt a later unmatched guard, exit 2).
* **Minsky Swap** — ``register_based/minsky_swap.py`` vs
  ``extra/assembly/minsky_swap-riscv.s``.  Both implement the compact
  notation (a `+`/`~`/`*` command line plus a jump-target line, one number
  per `~` in program order).  Each `~` token keeps its own fixed target
  across every visit, even when a jump revisits it -- the reference builds
  a token-indexed target table rather than consuming targets in execution
  order, matching the Python interpreter's ``self.targets[self.ind]``
  lookup.  The assembly is run under unicorn via ``riscv_elf_runner`` and
  must agree with the Python interpreter on the full corpus; both error on
  a `~` with no corresponding jump-line number (exit 2).
* **Forþ** — ``stack_based/forth.py`` vs ``extra/rust/forth.rs``.  The Rust
  reference writes its ``Input: `` prompt to stdout (the Python side routes
  it through the IO layer), which is stripped before comparing; both agree
  on the exit-code convention (3 = invalid operation).
* **Basicfuck** — ``tape_based/basicfuck.py`` vs ``extra/rust/basicfuck.rs``.
  Both parse the same source-level dialect; the reference prints its
  ``Input: `` prompts and error messages to stdout, which are stripped
  before comparing, and both agree on the exit-code convention (2 =
  malformed, 3 = invalid operation).
* **Unsquare** — ``stack_based/unsquare.py`` vs
  ``extra/rust/unsquare.rs``.  The Rust reference prints its ``Input: ``
  prompts to stdout, which are stripped before comparing; both agree on the
  exit-code convention (3 = invalid operation) and write characters above
  127 as UTF-8, so the Python output is encoded the same way.
* **3x** — ``stack_based/three_x.py`` vs ``extra/rust/three_x.rs``.  Both compute
  over exact rationals; the reference prints its ``Input: `` prompts to
  stdout (stripped before comparing) and both agree on the exit-code
  convention.
* **%^2^-1** — ``register_based/pct_squared_minus_one.py`` vs ``extra/rust/
  ``pct_squared_minus_one.rs``.
  Both track the accumulator as a signed magnitude with the 3003 reset; the
  reference prints its ``Input: `` prompts to stdout, which are stripped
  before comparing.
* **Painfuck** — ``tape_based/painfuck.py`` vs ``extra/rust/painfuck.rs``.
  Corpus programs are encoded into the source alphabet (the reference
  translates the source before running); the nondeterministic ``y`` is
  excluded.
* **bit~** — ``tape_based/bit_tilde.py`` vs ``extra/rust/bit_tilde.rs``.  Both
  write bytes above 127 as raw bytes; unmatched brackets raise (the former
  Ruby port hung).

Called from CI's ``assembly`` and ``rust`` jobs (which provide
unicorn+the RISC-V compiler and cargo) and from ``verify.py`` locally.
References whose toolchain is missing are skipped, not failed.

Usage:
    PYTHONPATH=src python scripts/verify_differential.py
    PYTHONPATH=src python scripts/verify_differential.py --fuzz 200 --seed 1
"""

import argparse
import contextlib
import functools
import io
import random
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, TypeVar

ROOT = Path(__file__).parents[1]
RUST_BIN_DIR = ROOT / "extra" / "rust" / "target" / "debug"
RUST_BIN = RUST_BIN_DIR / "laserfuck"
UNSQUARE_BIN = RUST_BIN_DIR / "unsquare"
PCT_SQUARED_MINUS_ONE_BIN = RUST_BIN_DIR / "pct_squared_minus_one"
BIT_TILDE_BIN = RUST_BIN_DIR / "bit_tilde"
FORTH_BIN = RUST_BIN_DIR / "forth"
BASICFUCK_BIN = RUST_BIN_DIR / "basicfuck"
PAINFUCK_BIN = RUST_BIN_DIR / "painfuck"
THREE_X_BIN = RUST_BIN_DIR / "three_x"

# Parallelism for the native-reference runs: each check spawns a subprocess,
# so threads (which just wait on the subprocess) scale well.
_WORKERS = 8


_T = TypeVar("_T")
_R = TypeVar("_R")


def _run_parallel(fn: Callable[[_T], _R], tasks: Sequence[_T]) -> list[_R]:
    """Run ``fn`` over ``tasks`` concurrently, returning results in order."""
    with ThreadPoolExecutor(max_workers=_WORKERS) as executor:
        return list(executor.map(fn, tasks))


def _fuzz_boolean(
    name: str,
    builder: Callable[[str], str],
    native: Callable[[str, bytes], _R | None],
    python: Callable[[str, bytes], _R | None],
    rng: random.Random,
    count: int,
) -> tuple[int, int]:
    """Fuzz ``count`` random truth tables through both implementations.

    ``native(program, stdin)`` runs the reference (None on a timeout) and
    ``python(program, stdin)`` the in-package interpreter.  Returns
    ``(failures, checked)``.
    """
    tasks = []
    for _ in range(count):
        n = rng.randint(1, 4)
        table = "".join(rng.choice("01") for _ in range(2**n))
        program = builder(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            stdin = ("\n".join(map(str, bits)) + "\n").encode()
            tasks.append((program, stdin, table, bits))
    results = _run_parallel(lambda t: native(t[0], t[1]), tasks)
    failures = checked = 0
    for (program, stdin, table, bits), result in zip(tasks, results, strict=True):
        if result is None:
            print(f"{name} boolean {table!r}: reference did not terminate")
            failures += 1
            checked += 1
            continue
        py = python(program, stdin)
        checked += 1
        if result != py:
            failures += 1
            print(
                f"{name} boolean {table!r} combo {bits}: "
                f"reference {result!r} vs Python {py!r}"
            )
    return failures, checked


def _fuzz_text(
    name: str,
    generator: Callable[[str], str],
    native: Callable[[str, bytes], _R | None],
    python: Callable[[str, bytes], _R | None],
    rng: random.Random,
    count: int,
) -> tuple[int, int]:
    """Fuzz ``count`` random byte texts through both implementations.

    Either side may report ``None`` for "did not terminate" (the native
    side via a subprocess timeout, the Python side via state-cycle
    detection where the interpreter is step-capable, on languages whose
    Python runner has one).  A text generator's programs are expected to
    always halt, so both sides agreeing they loop is not itself a failure
    (mirrors ``_run_nocomment_python_limited``'s fuzzer) — only one side
    halting while the other loops is a real divergence.
    """
    tasks = []
    for _ in range(count):
        text = "".join(chr(rng.randrange(256)) for _ in range(rng.randint(1, 10)))
        tasks.append((generator(text), text))
    results = _run_parallel(lambda t: native(t[0], b""), tasks)
    failures = checked = 0
    for (program, text), result in zip(tasks, results, strict=True):
        checked += 1
        py = python(program, b"")
        if result is None and py is None:
            continue  # agreement: both sides prove the program loops
        if result is None or py is None:
            failures += 1
            print(
                f"{name} {text!r}: termination mismatch "
                f"(reference {'looped' if result is None else 'halted'}, "
                f"Python {'looped' if py is None else 'halted'})"
            )
            continue
        if result != py:
            failures += 1
            print(f"{name} {text!r}: reference {result!r} vs Python {py!r}")
    return failures, checked


def _verify_asm(
    name: str,
    riscv_name: str,
    corpus: Sequence[Any],
    run_python: Callable[..., tuple[bytes, int]],
) -> bool:
    """Compare a Python interpreter against its RISC-V cross-check on ``corpus``.

    ``name`` is the display label, ``riscv_name`` the reference key passed to
    :func:`_asm_refs`, and ``run_python(program)`` the in-package interpreter
    returning ``(output, exit_code)``.  The reference is run under unicorn,
    which needs unicorn and a RISC-V cross-compiler; a missing toolchain is
    skipped (reported as success), not failed.  A reference that faults is
    folded into ``(b"", 1)`` so a divergence still prints rather than passing
    silently.
    """
    if not _asm_refs_ready(riscv_name):
        return True

    failures = 0
    for program in corpus:
        ref = _asm_refs(riscv_name, program)
        py_out, py_code = run_python(program)
        if ref is None:
            asm_out, asm_code = b"", 1
        else:
            asm_out, asm_code = ref
        if (asm_out, asm_code) != (py_out, py_code):
            failures += 1
            print(
                f"{name} {program!r}: asm={(asm_out, asm_code)} py={(py_out, py_code)}"
            )

    if not failures:
        print(f"{name} differential: {len(corpus)} programs match")
    return failures == 0


def _fuzz_asm(
    name: str,
    riscv_name: str,
    gen_program: Callable[[random.Random], str],
    run_limited: Callable[..., Any],
    rng: random.Random,
    count: int,
) -> bool:
    """Differentially fuzz one assembly-backed language with random programs.

    ``gen_program(rng)`` draws a program and ``run_limited(program, timeout)``
    runs the Python interpreter under a wall-clock budget, returning None for
    "did not terminate".  The reference reports the same way when it exhausts
    its instruction-count cap or writes past a fixed buffer, so both sides
    looping is agreement, not a failure; one side halting while the other
    loops is a divergence.  A Python-only timeout is re-checked with a longer
    budget first, since the 3s budget is a heuristic and the assembly is far
    faster.
    """
    if not _asm_refs_ready(riscv_name):
        return True

    failures = checked = loops = 0
    for _ in range(count):
        program = gen_program(rng)
        py = run_limited(program, timeout=3)
        asm = _asm_refs(riscv_name, program)
        if py is None and asm is None:
            loops += 1
            continue
        if py is None and asm is not None:
            py = run_limited(program, timeout=30)
        if py is None or asm is None:
            failures += 1
            print(
                f"{name} fuzz {program!r}: termination mismatch "
                f"(python {'loops' if py is None else 'halts'}, "
                f"asm {'loops' if asm is None else 'halts'})"
            )
            continue
        checked += 1
        if py != asm:
            failures += 1
            print(f"{name} fuzz {program!r}: asm={asm!r} py={py!r}")

    print(
        f"{name} fuzz: {checked} programs match, {loops} consistent loops"
        if not failures
        else f"{name} fuzz: {failures} failures of {checked} (plus {loops} loops)"
    )
    return failures == 0


def _verify_rust(
    name: str,
    corpus: Sequence[Any],
    run_native: Callable[..., Any],
    run_python: Callable[..., Any],
    prepare: Callable[[Any], Any] | None = None,
    label: Callable[[Any], str] | None = None,
) -> bool:
    """Compare a Python interpreter against its Rust cross-check on ``corpus``.

    Each corpus entry is a ``(program, stdin)`` pair.  ``prepare(program)``
    maps the entry's first element to what the interpreters actually run
    (Painfuck encodes into its source alphabet), and ``label(program)`` picks
    what a divergence prints (Basicfuck names a program by its last line);
    both default to the entry itself.  ``run_native`` returning None means the
    reference did not terminate, which is a failure -- unlike the assembly
    fuzzers, these corpora are all expected to halt.  The caller is
    responsible for skipping when the Rust binary is not built.
    """
    prepare = prepare or (lambda program: program)
    label = label or (lambda program: program)

    failures = 0
    for entry, stdin in corpus:
        program = prepare(entry)
        native = run_native(program, stdin)
        if native is None:
            print(f"{name} {label(entry)!r}: Rust reference did not terminate")
            failures += 1
            continue
        py = run_python(program, stdin)
        if native != py:
            failures += 1
            print(f"{name} {label(entry)!r}: Rust {native!r} vs Python {py!r}")

    if not failures:
        print(f"{name} differential: {len(corpus)} programs match")
    return failures == 0


def _random_program(alphabet: str, max_len: int) -> Callable[[random.Random], str]:
    """Return a generator drawing a random ``alphabet`` program up to ``max_len``.

    The draws are ordered length-then-characters to match the per-language
    fuzzers this replaces, so a given seed produces the same corpus as before.
    """

    def gen(rng: random.Random) -> str:
        return "".join(rng.choice(alphabet) for _ in range(rng.randint(0, max_len)))

    return gen


# Error messages the Basicfuck reference prints to stdout before exiting;
# stripped so only the program's own output is compared.
_CPP_ERRORS = (
    "Identifier is undefined.",
    "Invalid token.",
    "Invalid syntax.",
    "Invalid identifier.",
    "Missing/Invalid directives.",
    "Missing/Invalid identifiers.",
    "Missing overflow directive.",
    "Invalid overflow directive.",
    "Insufficient memory.",
    "Underflow error.",
    "Overflow error.",
)


def _build_forth() -> str | None:
    """Return the built Forþ Rust reference; None if cargo built it not yet."""
    if not FORTH_BIN.exists():
        print("[skip] Forþ differential: Rust reference not built")
        return None
    return str(FORTH_BIN)


def _build_basicfuck() -> str | None:
    """Return the built Basicfuck Rust reference; None if cargo built it not yet."""
    if not BASICFUCK_BIN.exists():
        print("[skip] Basicfuck differential: Rust reference not built")
        return None
    return str(BASICFUCK_BIN)


# -- LaserFuck corpus: mirrors, conditionals, tape ops, direction -------

# Raw snippets test individual cells; they must terminate under the funnel
# for every heading (the Rust reference has no step limit and hangs on
# non-terminating grids).  `{` and `|` point the beam back into the funnel's
# row-0 orbit (the `}` at (0,1) reflects it), so they cannot be hosted on the
# standard funnel and are omitted here; the boolean generator programs below
# exercise the full decision-tree machinery instead.
LASERFUCK_CORPUS = [
    # + and die
    "\u00ff}}o+x",
    # - makes -1, excluded from output
    "\u00ff}}o-x",
    # > moves the pointer, + writes a second cell
    "\u00ff}}o>+x",
    # < at the left edge inserts a cell
    "\u00ff}}o<x",
    # directional cells steer the beam into x
    "\u00ff}}o^x",
    "\u00ff}}ovx",
    "\u00ff}}o}x",
    # mirrors
    "\u00ff}}o\\x",
    "\u00ff}}o/x",
    "\u00ff}}o_x",
    # # skips the next command
    "\u00ff}}o#+x",
    # input then print via byte mode
    "\u00ff}}o,x",
    # read, normalize with '-', reflect on nonzero
    "\u00ff}},------------------------------------------------#v)x",
]

# `(`/`)` reflect on a nonzero cell; the boolean generator programs below
# exercise them on the real decision tree, and the raw snippets above cannot
# host them without heading-dependent orbits.

# The boolean generator produces terminating programs that exercise the full
# decision-tree machinery (the '#','v',')','\\' node, pointer moves, leaves).
LASERFUCK_BOOLEAN = [
    ("10", 1),
    ("0110", 2),
    ("11111110", 3),
]


# -- BF-PDA corpus: the full 6-command wiki language ----------------------

# Every command over a bit stack (top = current cell).  `@` flips the top,
# `.` prints it as '0'/'1', `<` pushes a zero, `>` pops, and `[`/`]` are
# brainfuck-style while loops; any other character is a comment.  An empty
# stack reads as a zero.  Programs must terminate (a `]` back-jumping to a
# repeating point loops forever).
BFPDA_CORPUS = [
    "@",  # empty stack: @ auto-pushes a fresh 1
    ".",  # empty stack: prints '0'
    "<.",  # push 0, print '0'
    "<@.",  # push 0, flip, print '1'
    "<@@.",  # push 0, flip twice, print '0'
    ">@.",  # pop empty (no-op), push 1, print '1'
    "<>@.",  # push 0, pop, push 1, print '1'
    "<.>@.",  # "01"
    "<@>@.",  # push-flip, pop, push, print -> "1"
    "[]",  # `[` on an empty stack skips the body
    "[@].",  # skipped body, then print '0'
    "<@[>].",  # loop runs once (pops the guard), print '0'
    "abc.",  # comments, then print '0'
    "@..",  # "11"
    "<@<@[.>]",  # loop prints each bit -> "11"
    # error categories: an empty program and unbalanced brackets are both
    # malformed (exit 2) in the Python interpreter and the assembly
    "",  # empty program: malformed, exit 2
    "[",  # unbalanced '[': malformed, exit 2
    "]",  # unbalanced ']': malformed, exit 2
    "<@[",  # unbalanced '[': malformed, exit 2
    "@]",  # unbalanced ']': malformed, exit 2
    "][",  # ']' below depth 0: malformed, exit 2
]


# -- RAM0 corpus: the full 7-token wiki language --------------------------

# Every token over two registers (z, n) plus unbounded RAM.  `Z` zeroes z,
# `A` increments z, `N` copies z into n, `L` loads z := ram[z], `S` stores
# ram[n] := z, `C` skips the next token when z == 0, and a digit string
# ``[1-9]``\ d* is an unconditional goto to token ``d - 1`` (running off
# either end halts).  Any other character is a comment, including a lone
# ``0``.  RAM0 has no error categories: every run dumps the final state and
# exits 0.  Programs must terminate (a goto back to a repeating point loops
# forever).
RAM0_CORPUS = [
    "",  # empty program: dumps the zero state
    "Z",  # zero z
    "A",  # increment z
    "N",  # copy z into n
    "L",  # load from ram[0] (uninitialized -> 0)
    "S",  # store ram[0] = 0
    "A A A",  # z: 3
    "A A A Z",  # Z resets z
    "A A A N",  # n: 3
    "A C A",  # C does not skip when z is nonzero
    "C A",  # C skips the next token when z is zero
    "A A N A A A S",  # store 5 at address 2
    "A A N A A A S A A L",  # L from an uninitialized address returns 0
    "A A N A A A S A A A A A N L",  # L loads the stored value into z
    "A N A S A A N A A S",  # two cells, insertion order
    "A N A S A A N A S",  # overwrite keeps the first insertion position
    "A 3 A A",  # goto to token 3
    "A 999 A",  # goto past the end dumps
    "A A 0 A",  # lone '0' is a comment, not a token
    "A A 12 A",  # multi-digit goto past the end dumps
    "A /* comment */ A",  # comments are ignored
    "A A N S",  # store 2 at address 2
    "A A A A A N A A A S A A A A A N L",  # load from an uninitialized address
    "A N S A A N S A A A N S A A A A N S A A A A A N S",  # insertion order
]


# -- BIO corpus: the full 3-register wiki language -------------------------

# Every command over three registers x/y/z.  `0o[xyz]` increments, `1o[xyz]`
# decrements, `1i[xyz]` prints the register's low byte, `0i[xyz]` is a
# while-loop guard, and `}` closes the innermost loop; matching is
# case-insensitive and any other text (including `;` separators) is a
# comment.  Error categories: a loop guard that is skipped (register zero)
# and never finds its matching `}` is malformed (exit 2, raised lazily on
# the skip scan, not eagerly); a `}` with no open loop is an invalid
# runtime operation (exit 3).  Programs must terminate (a loop whose body
# never changes its guard register loops forever).
BIO_CORPUS = [
    "",  # empty program: no output
    "   \n\t  ",  # whitespace only: no output
    "0ox;invalid;1ix;",  # non-command text is a comment
    "0ox;1ix;",  # increment then output x
    "0oy;0oy;0oy;1iy;",  # increment y three times
    "0oz;1iz;",  # increment then output z
    "1ox;1ix;",  # decrement from zero wraps to 0xff
    "0ox;1ox;1ix;",  # net zero
    "0OX;1IX;",  # uppercase commands
    "0ox;0ix{0oy;1ox;};1iy;",  # loop runs once
    "0ix{0oy;};1iy;",  # loop skipped when register is zero
    "0ix{};1ix;",  # empty loop body, skipped
    "0ox;0ix{0oy;0iy{0oz;1oy;};1ox;};1iz;",  # nested loops
    "0ox;0ox;0ix{1ix;1ox;};",  # loop with output inside
    "0ox;" * 5 + "0ix{1ox;" + "0oy;" * 5 + "};1iy;",  # 5*5 = 25
    "0ox;" * 66 + "1ix;",  # 66 = 'B'
    "0ox;" * 300 + "1ix;",  # wraps mod 256
    "0ox;0oy;0oz;1ix;1iy;1iz;",  # registers are independent
    # error categories
    "}",  # bare close: invalid runtime op, exit 3
    "0ox;}",  # close with no open loop: exit 3
    "0iy{0ox;",  # unmatched guard, skipped: malformed, exit 2
    "0ix{0iy{};",  # unmatched outer guard, skipped: malformed, exit 2
    ";x1Ox{{}0Iy",  # a halting `}` pre-empts a later unmatched guard: exit 3
]


# -- Minsky Swap corpus: the full compact-notation wiki language ----------

# A command line of `+`/`~`/`*` plus a jump-target line, one number per `~`
# in program order (1-based: target N resumes at command N; 0 means "no
# jump on zero", a `~` fallthrough).  `+` increments the pointed-to
# register, `*` flips the pointer, `~` decrements the pointed-to register
# if nonzero, else looks up its own fixed target (a revisited tilde always
# uses the same entry, regardless of execution order).  Any other
# character on the command line is ignored; the jump line is scanned for
# digit runs only.  Error category: a `~` with no corresponding number on
# the jump line is malformed (exit 2).  Programs must terminate (a jump
# back to a repeating point loops forever).
MINSKY_SWAP_CORPUS = [
    "",  # empty program: dumps "0 0"
    "+",  # increment reg[0]
    "++",  # reg[0] = 2
    "*+",  # swap, then increment reg[1]
    "+*+",  # reg[0] = 1, swap, reg[1] = 1
    "+~\n1",  # decrement reg[0] to 0
    "~+\n2",  # zero register jumps past the +, landing back on it
    "~+~\n2 1",  # two tildes, two targets
    "  +  \n  ",  # whitespace around commands and an empty jump line
    "+++~\n1",  # counting loop
    "+*+*+",  # register-swapping sequence
    "++~+~\n2 1",  # conditional jump based on register value
    "++*++*+++",  # reg[0] = 5, reg[1] = 2
    "~\n999",  # target far past the program end halts immediately
    "~+~+~\n3 2 1",  # multiple tildes with distinct targets
    "+++*+++",  # reg[0] = 3, reg[1] = 3
    "+++*+++*~+~\n2 1",  # register copy pattern
    "~\n0",  # target 0 is a fallthrough, not a jump
    "~\n12 34",  # multi-digit jump targets
    "~*+*~\n3 1",  # a tilde revisited via a jump keeps its own fixed target
    "~~\n1",  # unmatched second tilde: malformed, exit 2
    "~\n",  # tilde with an empty jump line: malformed, exit 2
]


# -- NoComment corpus: the full 10-command wiki language ------------------

# Every command over a byte tape and stack.  `s`/`b` jump by a peeked stack
# value when the current cell is nonzero; programs using them must terminate
# (a back-jump to a repeating point loops forever).
NOCOMMENT_CORPUS = [
    "",  # empty program
    "o",  # print cell 0 (NUL)
    "io",  # chr(1)
    "i" * 255 + "o",  # wraps to 255
    "do",  # -1 wraps to 255
    "c" + "i" * 65 + "o",  # 'A'
    "c" + "i" * 65 + "r" + "o",  # r to cell 1 (NUL)
    "c" + "i" * 65 + "r" + "i" * 70 + "o",  # cell 1 = 70 'F'
    "c" + "i" * 65 + "l" + "o",  # l at cell 0 is a no-op
    "c" + "i" * 65 + "r" + "l" + "o",  # back to cell 0
    "c" + "i" * 65 + "n" + "f" + "o",  # push then pop
    "c" + "i" * 65 + "n" + "r" + "f" + "o",  # push, r, pop into cell 1
    "c" + "i" * 65 + "n" + "n" + "f" + "f" + "o",  # two pushes, two pops
    "c" + "i" * 65 + "n" + "r" + "c" + "f" + "o",  # pop overwrites cell 1
    "cii" + "n" + "s" + "ii" + "o",  # s skips 2
    "ci" + "n" + "s" + "i" + "o",  # s skips 1
    "ciii" + "n" + "s" + "iii" + "o",  # s skips 3
    "c" + "i" * 3 + "n" + "r" + "i" + "o",  # cell 1 = 1
    "c" + "i" + "n" + "s" + "n" + "f" + "o",  # s then push/pop
    # error categories: a non-command is malformed (exit 2); stack underflow
    # and out-of-range jumps are invalid operations (exit 3) in both
    "xyz",  # non-command: malformed, exit 2
    "f",  # stack underflow: invalid op, exit 3
    "c" + "i" * 10 + "n" + "s" + "o",  # s out of range: invalid op, exit 3
    "c" + "i" * 10 + "n" + "b" + "o",  # b out of range: invalid op, exit 3
    "c" + "n" + "b" + "o",  # b with cell 0 does not jump
]


class _TimeoutError(Exception):
    """Raised by the SIGALRM handler when a limited run overruns its budget."""


@contextlib.contextmanager
def _alarm_budget(timeout: float) -> Iterator[None]:
    """Raise :class:`_TimeoutError` in this thread after ``timeout`` seconds.

    The wall-clock backstop for the unbounded-growth class of runaway
    program -- one that keeps pushing a stack or incrementing a register
    never revisits a state, so cycle detection alone never fires.  Callers
    gate on ``hasattr(signal, "SIGALRM")`` first; this is POSIX-only.
    """

    def _alarm(_signum: int, _frame: object) -> None:
        raise _TimeoutError

    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(int(timeout))
    try:
        yield
    finally:
        signal.alarm(0)


def _capture_io(*, dump_str: bool = False) -> tuple[io.BytesIO, Any]:
    """Build an ``IO`` that appends everything printed to a byte buffer.

    Returns ``(buffer, io_instance)``.  ``dump_str`` picks which half of the
    IO surface the interpreter actually drives: the tape and stack languages
    emit one character at a time (``print_char``), the register languages
    emit their state dump as a string (``print_str``).  Both encode latin1,
    so a byte written by the interpreter is the byte the assembly wrote.
    """
    from esolangs.interpreters.io import IO

    buffer = io.BytesIO()

    class _IO(IO):
        if dump_str:

            def print_str(self, s: str) -> None:
                buffer.write(s.encode("latin1"))

        else:

            def print_char(self, char: str) -> None:
                buffer.write(char.encode("latin1"))

    return buffer, _IO()


def _run_nocomment_python(program: str) -> tuple[bytes, int]:
    """Run the Python NoComment interpreter; return (output, exit code).

    Exit codes follow the cross-check convention: 0 = success, 2 = malformed
    program (ValueError), 3 = invalid operation (HaltError).
    """
    from esolangs.exceptions import HaltError
    from esolangs.interpreters.tape_based.nocomment import run

    buffer, sink = _capture_io()

    try:
        run(program, sink)
    except HaltError:
        return buffer.getvalue(), 3
    except ValueError:
        return buffer.getvalue(), 2
    return buffer.getvalue(), 0


def _run_nocomment_python_limited(
    program: str, timeout: float
) -> tuple[bytes, int] | None:
    """Run the Python NoComment interpreter with a wall-clock budget.

    Returns ``(output, exit_code)`` like :func:`_run_nocomment_python`, or
    None if the program did not terminate (the fuzzer's analog of the
    assembly's instruction-count cap).  The interpreter is step-capable, so
    the run is bounded by state-cycle detection
    (:func:`esolangs.vm.run_until_halt_or_cycle`): a repeated snapshot
    proves a loop and is reported as non-termination immediately.  The alarm
    stays as the backstop for the unbounded-growth class (a loop that keeps
    pushing the stack never revisits a state), and is only meaningful on
    POSIX; the interpreter is skipped (None) elsewhere.
    """
    import signal

    if not hasattr(signal, "SIGALRM"):
        return None

    from esolangs.exceptions import HaltError
    from esolangs.interpreters.tape_based.nocomment import _Machine
    from esolangs.vm import run_until_halt_or_cycle

    buffer, sink = _capture_io()

    try:
        with _alarm_budget(timeout):
            machine = _Machine(program, sink)
            if not run_until_halt_or_cycle(machine):
                return None
            return buffer.getvalue(), 0
    except _TimeoutError:
        return None
    except HaltError:
        return buffer.getvalue(), 3
    except ValueError:
        return buffer.getvalue(), 2


def _verify_nocomment() -> bool:
    """Compare the Python NoComment interpreter against the assembly cross-check.

    The RISC-V reference is run under unicorn (``riscv_elf_runner``), which
    requires unicorn and a RISC-V cross-compiler; it is skipped when either
    is missing.  Both
    implementations error on non-commands, stack underflow, and out-of-range
    jumps, and must agree on the valid-program corpus.
    """
    return _verify_asm(
        "NoComment", "nocomment", NOCOMMENT_CORPUS, _run_nocomment_python
    )


def _run_bfpda_python(program: str) -> tuple[bytes, int]:
    """Run the Python BF-PDA interpreter; return (output, exit code).

    Exit codes follow the cross-check convention: 0 = success, 2 = malformed
    program (ValueError: empty or unbalanced brackets).  BF-PDA has no
    invalid runtime operations, so exit 3 is unused.
    """
    from esolangs.exceptions import HaltError
    from esolangs.interpreters.stack_based.bf_pda import run

    buffer, sink = _capture_io()

    try:
        run(program, sink)
    except HaltError:
        return buffer.getvalue(), 3
    except ValueError:
        return buffer.getvalue(), 2
    return buffer.getvalue(), 0


def _run_bfpda_python_limited(program: str, timeout: float) -> tuple[bytes, int] | None:
    """Run the Python BF-PDA interpreter with a wall-clock budget.

    Returns ``(output, exit_code)`` like :func:`_run_bfpda_python`, or None
    if the program did not terminate (the fuzzer's analog of the assembly's
    instruction-count cap).  The interpreter is step-capable, so the run is
    bounded by state-cycle detection
    (:func:`esolangs.vm.run_until_halt_or_cycle`): a repeated snapshot
    proves a loop and is reported as non-termination immediately.  The alarm
    stays as the backstop for the unbounded-growth class (a loop that keeps
    pushing the stack never revisits a state), and is only meaningful on
    POSIX; the interpreter is skipped (None) elsewhere.
    """
    import signal

    if not hasattr(signal, "SIGALRM"):
        return None

    from esolangs.exceptions import HaltError
    from esolangs.interpreters.stack_based.bf_pda import _Machine
    from esolangs.vm import run_until_halt_or_cycle

    buffer, sink = _capture_io()

    try:
        with _alarm_budget(timeout):
            machine = _Machine(program, sink)
            if not run_until_halt_or_cycle(machine):
                return None
            return buffer.getvalue(), 0
    except _TimeoutError:
        return None
    except HaltError:
        return buffer.getvalue(), 3
    except ValueError:
        return buffer.getvalue(), 2


def _verify_bfpda() -> bool:
    """Compare the Python BF-PDA interpreter against the assembly cross-check.

    The RISC-V reference is run under unicorn (``riscv_elf_runner``), which
    requires unicorn and a RISC-V cross-compiler; it is skipped when either
    is missing.  Both implementations error on empty programs and unbalanced
    brackets, and must agree on the valid-program corpus.
    """
    return _verify_asm("BF-PDA", "bfpda", BFPDA_CORPUS, _run_bfpda_python)


def _run_ram0_python(program: str) -> tuple[bytes, int]:
    """Run the Python RAM0 interpreter; return (output, exit code).

    RAM0 has no error categories, so the exit code is always 0; the state
    dump is printed once, on the step that halts the machine.
    """
    from esolangs.interpreters.register_based.ram0 import run

    buffer, sink = _capture_io(dump_str=True)

    run(program, sink)
    return buffer.getvalue(), 0


def _run_ram0_python_limited(program: str, timeout: float) -> tuple[bytes, int] | None:
    """Run the Python RAM0 interpreter with a wall-clock budget.

    Returns ``(output, exit_code)`` like :func:`_run_ram0_python`, or None
    if the program did not terminate (the fuzzer's analog of the assembly's
    instruction-count cap).  The interpreter is step-capable, so the run is
    bounded by state-cycle detection
    (:func:`esolangs.vm.run_until_halt_or_cycle`): a repeated snapshot
    proves a loop and is reported as non-termination immediately.  The alarm
    stays as the backstop for the unbounded-growth class (a loop that keeps
    incrementing a register never revisits a state), and is only meaningful
    on POSIX; the interpreter is skipped (None) elsewhere.
    """
    import signal

    if not hasattr(signal, "SIGALRM"):
        return None

    from esolangs.interpreters.register_based.ram0 import _Machine
    from esolangs.vm import run_until_halt_or_cycle

    buffer, sink = _capture_io(dump_str=True)

    try:
        with _alarm_budget(timeout):
            machine = _Machine(program, sink)
            if not run_until_halt_or_cycle(machine):
                return None
            machine.step()  # the dump happens on the step after halting
            return buffer.getvalue(), 0
    except _TimeoutError:
        return None


def _verify_ram0() -> bool:
    """Compare the Python RAM0 interpreter against the assembly cross-check.

    The RISC-V reference is run under unicorn (``riscv_elf_runner``), which
    requires unicorn and a RISC-V cross-compiler; it is skipped when either
    is missing.  Both implementations tokenize the same way, dump the same
    insertion-order state, and must agree on the valid-program corpus.
    """
    return _verify_asm("RAM0", "ram0", RAM0_CORPUS, _run_ram0_python)


def _run_bio_python(program: str) -> tuple[bytes, int]:
    """Run the Python BIO interpreter; return (output, exit code).

    Exit codes follow the cross-check convention: 0 = success, 2 = malformed
    program (ValueError: a skipped loop guard never finds its matching
    `}`), 3 = invalid runtime operation (HaltError: `}` with an empty loop
    stack).
    """
    from esolangs.exceptions import HaltError
    from esolangs.interpreters.register_based.bio import run

    buffer, sink = _capture_io()

    try:
        run(program, sink)
    except HaltError:
        return buffer.getvalue(), 3
    except ValueError:
        return buffer.getvalue(), 2
    return buffer.getvalue(), 0


def _run_bio_python_limited(program: str, timeout: float) -> tuple[bytes, int] | None:
    """Run the Python BIO interpreter with a wall-clock budget.

    Returns ``(output, exit_code)`` like :func:`_run_bio_python`, or None if
    the program did not terminate (the fuzzer's analog of the assembly's
    instruction-count cap).  The interpreter is step-capable, so the run is
    bounded by state-cycle detection
    (:func:`esolangs.vm.run_until_halt_or_cycle`): a repeated snapshot
    proves a loop and is reported as non-termination immediately.  The alarm
    stays as the backstop for the unbounded-growth class (a loop that keeps
    incrementing a register never revisits a state), and is only meaningful
    on POSIX; the interpreter is skipped (None) elsewhere.
    """
    import signal

    if not hasattr(signal, "SIGALRM"):
        return None

    from esolangs.exceptions import HaltError
    from esolangs.interpreters.register_based.bio import _Machine
    from esolangs.vm import run_until_halt_or_cycle

    buffer, sink = _capture_io()

    try:
        with _alarm_budget(timeout):
            machine = _Machine(program, sink)
            if not run_until_halt_or_cycle(machine):
                return None
            return buffer.getvalue(), 0
    except _TimeoutError:
        return None
    except HaltError:
        return buffer.getvalue(), 3
    except ValueError:
        return buffer.getvalue(), 2


def _verify_bio() -> bool:
    """Compare the Python BIO interpreter against the assembly cross-check.

    The RISC-V reference is run under unicorn (``riscv_elf_runner``), which
    requires unicorn and a RISC-V cross-compiler; it is skipped when either
    is missing.  Both implementations tokenize the same way and error
    lazily on the same control-flow path, and must agree on the
    valid-program and error-category corpus.
    """
    return _verify_asm("BIO", "bio", BIO_CORPUS, _run_bio_python)


def _run_minsky_swap_python(program: str) -> tuple[bytes, int]:
    """Run the Python Minsky Swap interpreter; return (output, exit code).

    Exit codes follow the cross-check convention: 0 = success, 2 =
    malformed program (ValueError: a `~` with no jump-line target).  Minsky
    Swap has no invalid runtime operations, so exit 3 is unused.
    """
    from esolangs.interpreters.register_based.minsky_swap import run

    buffer, sink = _capture_io(dump_str=True)

    try:
        run(program, sink)
    except ValueError:
        return buffer.getvalue(), 2
    return buffer.getvalue(), 0


def _run_minsky_swap_python_limited(
    program: str, timeout: float
) -> tuple[bytes, int] | None:
    """Run the Python Minsky Swap interpreter with a wall-clock budget.

    Returns ``(output, exit_code)`` like :func:`_run_minsky_swap_python`, or
    None if the program did not terminate (the fuzzer's analog of the
    assembly's instruction-count cap).  The interpreter is step-capable, so
    the run is bounded by state-cycle detection
    (:func:`esolangs.vm.run_until_halt_or_cycle`): a repeated snapshot
    proves a loop and is reported as non-termination immediately.  The alarm
    stays as the backstop for the unbounded-growth class (a loop that keeps
    incrementing a register never revisits a state), and is only meaningful
    on POSIX; the interpreter is skipped (None) elsewhere.
    """
    import signal

    if not hasattr(signal, "SIGALRM"):
        return None

    from esolangs.interpreters.register_based.minsky_swap import _Machine
    from esolangs.vm import run_until_halt_or_cycle

    buffer, sink = _capture_io(dump_str=True)

    try:
        with _alarm_budget(timeout):
            machine = _Machine(program, sink)
            if not run_until_halt_or_cycle(machine):
                return None
            machine.step()  # the dump happens on the step after halting
            return buffer.getvalue(), 0
    except _TimeoutError:
        return None
    except ValueError:
        return buffer.getvalue(), 2


def _verify_minsky_swap() -> bool:
    """Compare the Python Minsky Swap interpreter against the assembly cross-check.

    The RISC-V reference is run under unicorn (``riscv_elf_runner``), which
    requires unicorn and a RISC-V cross-compiler; it is skipped when either
    is missing.  Both implementations parse the compact notation the same
    way and give each `~` a fixed target independent of execution order,
    and must agree on the valid-program and error-category corpus.
    """
    return _verify_asm(
        "Minsky Swap",
        "minsky_swap",
        MINSKY_SWAP_CORPUS,
        _run_minsky_swap_python,
    )


def _run_native(
    cmd: list[str],
    program: str,
    timeout: float = 5,
    input_bytes: bytes | None = None,
) -> bytes | None:
    """Run ``program`` (written to a temp file) through ``cmd``.

    Returns None if the reference does not terminate within ``timeout``
    seconds (the Rust reference has no step limit and hangs on
    non-terminating grids).
    """
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write(program)
        path = f.name
    try:
        out = subprocess.run(
            [*cmd, path],
            capture_output=True,
            timeout=timeout,
            input=input_bytes,
        ).stdout
    except subprocess.TimeoutExpired:
        return None
    finally:
        Path(path).unlink()
    return out


def _run_native_code(
    cmd: list[str], program: str, timeout: float = 5
) -> tuple[bytes, int] | None:
    """Run ``program`` through ``cmd``, returning ``(stdout, exit_code)``."""
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write(program)
        path = f.name
    try:
        proc = subprocess.run([*cmd, path], capture_output=True, timeout=timeout)
        return proc.stdout, proc.returncode
    except subprocess.TimeoutExpired:
        return None
    finally:
        Path(path).unlink()


def _run_laserfuck_python(
    program: str, heading: int, inputs: list[str] | None = None
) -> str:
    from esolangs.interpreters.grid_based.laserfuck import run
    from esolangs.interpreters.io import IO

    buffer = io.StringIO()
    reads = list(inputs if inputs is not None else ["1"])

    class _IO(IO):
        def print_char(self, char: str) -> None:
            buffer.write(char)

        def print_num(self, num: int) -> None:
            buffer.write(str(num))

        def print_str(self, text: str) -> None:
            buffer.write(text)

        def input_str(self, _prompt: str = "Input: ") -> str:
            return reads.pop(0) if reads else "1"

    def _alarm(_signum: int, _frame: object) -> None:
        raise TimeoutError

    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(5)
    try:
        run(program.splitlines(), _IO(), heading=heading)
    finally:
        signal.alarm(0)
    return buffer.getvalue()


def _check_laserfuck_boolean(table: str, n: int, runs: int = 12) -> tuple[int, int]:
    """Differentially check a LaserFuck boolean program for one truth table.

    Returns ``(checked, failures)``: one ``checked`` per input combination,
    with ``failures`` counting the combos whose output did not match, plus
    any Python heading that hung.  ``runs`` is how many times the Rust
    reference samples the output set; the mirror funnel normalizes every
    heading, so the set is effectively a singleton and a couple of runs are
    enough to catch a divergence.
    """
    from esolangs.tools.boolean import other

    program = other.laserfuck(table)
    checked = 0
    failures = 0
    for combo in range(2**n):
        bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
        inputs = [str(b) for b in bits]
        outputs: set[str] = set()
        input_bytes = ("\n".join(inputs) + "\n").encode()
        for _ in range(runs):
            out = _run_native([str(RUST_BIN)], program, input_bytes=input_bytes)
            if out is None:
                print(
                    f"LaserFuck boolean {table!r} combo {bits}: "
                    "Rust reference does not terminate"
                )
                failures += 1
                checked += 1
                break
            text = out.decode(errors="replace")
            # the Rust reference writes an "Input: " prompt per read
            while text.startswith("Input: "):
                text = text[len("Input: ") :]
            outputs.add(re.sub("[^01]", "", text))
        else:
            checked += 1
            for heading in range(4):
                try:
                    py = _run_laserfuck_python(program, heading, inputs)
                except TimeoutError:
                    failures += 1
                    print(
                        f"LaserFuck boolean {table!r} combo {bits} heading {heading}: "
                        "Python hangs"
                    )
                    continue
                py = re.sub("[^01]", "", py)
                if py not in outputs:
                    failures += 1
                    print(
                        f"LaserFuck boolean {table!r} combo {bits} heading {heading}: "
                        f"python {py!r} not in rust set {sorted(map(repr, outputs))}"
                    )
    return checked, failures


def _verify_laserfuck() -> bool:
    """Compare the Python LaserFuck interpreter against the Rust cross-check.

    The Rust reference picks a random initial heading, so its output is a
    set across runs; the Python interpreter (which accepts a fixed heading)
    must produce a member of that set for each of the four headings.  A
    corpus program that never terminates in the reference is skipped.
    """
    if shutil.which("cargo") is None or not RUST_BIN.exists():
        print("[skip] LaserFuck differential: Rust reference not built")
        return True

    failures = 0
    checked = 0

    def check(program: str) -> None:
        nonlocal failures, checked
        outputs: set[str] = set()
        for out in _run_parallel(
            lambda _: _run_native([str(RUST_BIN)], program, input_bytes=b"1\n"),
            range(30),
        ):
            if out is None:
                print(f"LaserFuck {program!r}: Rust reference does not terminate")
                return
            text = out.decode(errors="replace")
            while text.startswith("Input: "):
                text = text[len("Input: ") :]
            outputs.add(text)
        checked += 1
        for heading in range(4):
            try:
                py = _run_laserfuck_python(program, heading)
            except TimeoutError:
                failures += 1
                print(f"LaserFuck {program!r} heading {heading}: Python hangs")
                continue
            if py not in outputs:
                failures += 1
                print(
                    f"LaserFuck {program!r} heading {heading}: "
                    f"python {py!r} not in rust set {sorted(map(repr, outputs))}"
                )

    for program in LASERFUCK_CORPUS:
        check(program)

    # boolean generator programs: read real inputs, exercise the tree
    for table, n in LASERFUCK_BOOLEAN:
        c, f = _check_laserfuck_boolean(table, n)
        checked += c
        failures += f

    if not failures:
        print(f"LaserFuck differential: {checked} programs match")
    return failures == 0


# -- seeded differential fuzzing ------------------------------------------
#
# The corpora above are fixed: they only catch divergences that were thought
# of.  The fuzzers draw random programs from each language's alphabet with a
# seeded RNG, so the same seed always explores the same programs.  They
# compare not only output but also the error category (exit code) and, for
# NoComment, the termination verdict itself: a program that halts in one
# implementation and loops in the other is exactly the class of divergence
# the fixed corpora missed.
#
# Generators keep the fuzz surface terminating by construction:
#
# * NoComment: ``idclrnfsbo`` — ``b``/``s`` jump by a peeked stack value, so
#   a random program may loop; both implementations bound the run (the
#   assembly via its instruction-count cap, Python via SIGALRM), and a
#   program that loops on one side but halts on the other is a failure.
# * LaserFuck: random truth tables through the boolean generator, which
#   produces terminating decision-tree grids (a random grid would hang the
#   reference, so raw grids are not fuzzable).


def _fuzz_nocomment(rng: random.Random, count: int) -> bool:
    """Differentially fuzz NoComment with random programs.

    A random ``b``/``s`` program may loop forever.  The assembly references
    raise or fault when they exhaust their instruction-count cap, and Python
    times out under SIGALRM; ``None`` means "did not terminate" on that side.
    A program that halts on one side but loops on the other is a divergence
    (and the reason a seeded fuzzer is worth having).
    """
    return _fuzz_asm(
        "NoComment",
        "nocomment",
        _random_program("idclrnfsbo", 30),
        _run_nocomment_python_limited,
        rng,
        count,
    )


def _fuzz_bfpda(rng: random.Random, count: int) -> bool:
    """Differentially fuzz BF-PDA with random programs.

    A random ``[``/``]`` program may loop forever (e.g. ``<@[]``): the
    assembly references raise or fault when they exhaust their
    instruction-count cap (or write past the fixed stack buffer), and Python
    times out under SIGALRM; ``None`` means "did not terminate" on that side.
    A program that halts on one side but loops on the other is a divergence.
    """
    return _fuzz_asm(
        "BF-PDA",
        "bfpda",
        _random_program("@.<>[]", 30),
        _run_bfpda_python_limited,
        rng,
        count,
    )


def _fuzz_ram0(rng: random.Random, count: int) -> bool:
    """Differentially fuzz RAM0 with random programs.

    A random digit-goto may loop forever (e.g. ``1``): the assembly
    references raise or fault when they exhaust their instruction-count cap
    (or write past the fixed RAM buffer), and Python times out under SIGALRM
    (or proves a state cycle); ``None`` means "did not terminate" on that
    side.  A program that halts on one side but loops on the other is a
    divergence.
    """
    return _fuzz_asm(
        "RAM0",
        "ram0",
        _random_program("ZANCLS123456789", 30),
        _run_ram0_python_limited,
        rng,
        count,
    )


def _fuzz_bio(rng: random.Random, count: int) -> bool:
    """Differentially fuzz BIO with random programs.

    A random loop whose body never flips its guard register may loop
    forever (e.g. ``0ox;0ix{0ix;}``): the assembly reference raises or
    faults when it exhausts its instruction-count cap (or writes past a
    fixed buffer), and Python times out under SIGALRM (or proves a state
    cycle); ``None`` means "did not terminate" on that side.  A program
    that halts on one side but loops on the other is a divergence.
    """
    return _fuzz_asm(
        "BIO",
        "bio",
        _random_program("01OoIiXxYyZz{}; ", 40),
        _run_bio_python_limited,
        rng,
        count,
    )


def _gen_minsky_swap_program(rng: random.Random) -> str:
    """Draw a random command line plus a (usually matching) jump-target line.

    Jump targets are drawn independently of the command length, so most
    programs are well-formed (each `~` gets a number) but some are
    deliberately over- or under-provided to exercise the malformed-program
    path (a `~` with no target) alongside ordinary execution.
    """
    cmd_len = rng.randint(0, 25)
    cmds = "".join(rng.choice("+~*") for _ in range(cmd_len))
    tilde_count = cmds.count("~")
    num_count = max(0, tilde_count + rng.choice([-1, 0, 0, 0, 1]))
    nums = " ".join(str(rng.randint(0, cmd_len + 2)) for _ in range(num_count))
    if rng.random() < 0.9:
        return cmds + "\n" + nums
    return cmds  # no jump line at all


def _fuzz_minsky_swap(rng: random.Random, count: int) -> bool:
    r"""Differentially fuzz Minsky Swap with random programs.

    A random `~` whose target lands on a repeating point may loop forever
    (e.g. ``~\n1``): the assembly reference raises or faults when it
    exhausts its instruction-count cap (or writes past a fixed buffer), and
    Python times out under SIGALRM (or proves a state cycle); ``None``
    means "did not terminate" on that side.  A program that halts on one
    side but loops on the other is a divergence.
    """
    return _fuzz_asm(
        "Minsky Swap",
        "minsky_swap",
        _gen_minsky_swap_program,
        _run_minsky_swap_python_limited,
        rng,
        count,
    )


# -- Forþ corpus: every command plus the error categories ------------------

# (program, input).  Programs that `,` always provide enough input, since
# Python's EOFError has no Rust equivalent.
FORTH_CORPUS = [
    (",,", b"hi\n"),  # second read hits EOF: exit 3
    ("", b""),  # empty program
    ("5", b""),  # nothing printed
    ("65.", b""),  # digits push and . prints
    ("A.", b""),  # hex letters push
    ("5:..", b""),  # duplicate
    ("23+.", b""),  # addition
    ("95-.", b""),  # subtraction
    ("28*.", b""),  # multiplication
    ("84/.", b""),  # division
    ("85%.", b""),  # remainder
    ("0~.", b""),  # complement
    ("09/~.", b""),  # truncating division over negatives
    ("65v..", b""),  # swap
    ("123o...", b""),  # reverse
    ("123c...", b""),  # rotate top 3
    ("1(F4*5+.)", b""),  # branch on nonzero
    ("0(F4*5+.)", b""),  # branch on zero
    ("0F7*0+F4*C+[.]", b""),  # [.] loop over the 0 seed
    ("1{65.}1;", b""),  # store and call
    ("1{/}1;", b""),  # nested underflow is discarded (exit 0)
    ("1{.};", b""),  # nested empty pop is fatal (exit 3)
    (",..", b"hi"),  # read pushes the rightmost byte on top
    (",68*-.", b"0"),  # read and normalize a bit
    ("12c", b""),  # c with 2 elements: exit 3
    ("50/", b""),  # division by zero: exit 3
    ("50%", b""),  # modulo by zero: exit 3
    ("9/", b""),  # binary op with 1 element: exit 3
    ("a5.", b""),  # unknown char is ignored: prints 5
    ("(5", b""),  # unterminated bracket: exit 3
    ("[", b""),  # unterminated bracket: exit 3
    ("{5", b""),  # unterminated bracket: exit 3
]


def _run_rust_native(
    binary: str,
    program: str,
    stdin: bytes,
    *,
    strip_leading_newline: bool = True,
    strip_errors: bool = False,
) -> tuple[bytes, int] | None:
    """Run ``program`` through a Rust cross-check; return (stdout, exit code).

    Every reference prints an ``Input: `` prompt that the Python side routes
    through the IO layer instead, so it is stripped before comparing;
    ``strip_leading_newline`` also drops the newline the prompt follows,
    which 3x does not emit.  ``strip_errors`` additionally removes the C++
    runtime's error messages, which only Basicfuck's reference writes to
    stdout.  Returns None if the reference does not terminate within the
    timeout -- the Rust references have no step limit.
    """
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write(program)
        path = f.name
    try:
        proc = subprocess.run(
            [binary, path], capture_output=True, input=stdin, timeout=5
        )
    except subprocess.TimeoutExpired:
        return None
    finally:
        Path(path).unlink()

    out = proc.stdout
    if strip_leading_newline:
        out = out.replace(b"\nInput: ", b"")
    out = out.replace(b"Input: ", b"")
    if strip_errors:
        for message in _CPP_ERRORS:
            out = out.replace((message + "\n").encode(), b"")
    return out, proc.returncode


def _run_forth_native(
    binary: str, program: str, stdin: bytes
) -> tuple[bytes, int] | None:
    """Run ``program`` through the Forþ Rust cross-check."""
    return _run_rust_native(binary, program, stdin)


def _run_forth_python(program: str, stdin: bytes) -> tuple[bytes, int]:
    """Run ``program`` through the in-package interpreter."""
    from esolangs.exceptions import HaltError
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.stack_based.forth import run

    io = ScriptedIO(stdin.decode("latin1"))
    try:
        run(program, io)
    except HaltError:
        return io.getvalue().encode("latin1"), 3
    except EOFError:
        return io.getvalue().encode("latin1"), 3
    return io.getvalue().encode("latin1"), 0


def _verify_forth() -> bool:
    """Compare the Python Forþ interpreter against the Rust cross-check."""
    binary = _build_forth()
    if binary is None:
        return True

    return _verify_rust(
        "Forþ",
        FORTH_CORPUS,
        lambda program, stdin: _run_forth_native(binary, program, stdin),
        _run_forth_python,
    )


def _fuzz_forth(rng: random.Random, count: int) -> bool:
    """Differentially fuzz Forþ with random truth tables.

    The boolean generator emits terminating decision-tree programs that read
    one bit per line and print the matching entry.  Random instruction
    programs would frequently hang the Rust reference, which has no loop
    bound, so they are not fuzzed.
    """
    from esolangs.tools import boolean

    binary = _build_forth()
    if binary is None:
        return True

    failures, checked = _fuzz_boolean(
        "Forþ",
        boolean.forth,
        lambda program, stdin: _run_forth_native(binary, program, stdin),
        _run_forth_python,
        rng,
        count,
    )
    print(
        f"Forþ fuzz: {checked} checks match"
        if not failures
        else f"Forþ fuzz: {failures} failures of {checked}"
    )
    return failures == 0


# -- Basicfuck corpus: every construct plus the error categories -----------

# (program, input).  Programs that read always provide enough input, since
# Python's EOFError has no Rust equivalent (the reference stores -1 at EOF).
_BF_N = "#basicfuck t=1 r=0~255 o=nearest\n#allocate a\n"
_BF_W = "#basicfuck t=1 r=0~255 o=wrap\n#allocate a\n"
_BF_H = "#basicfuck t=1 r=0~255 o=halt\n#allocate a\n"
_BF_U = "#basicfuck t=unbounded r=0~255 o=wrap\n#allocate "

BASICFUCK_CORPUS = [
    (_BF_U + "a\nread -> a ;\nread -> a ;", b"X\n"),  # EOF
    (_BF_N + "a += 65;\nwrite <- a ;", b""),
    (_BF_W + "a += 65;\nwrite <- a ;", b""),
    (_BF_N + "a += 5;\nwrite <- a ;", b""),
    (_BF_H + "a += 256;", b""),
    (_BF_H + "a -= 1;", b""),
    (_BF_W + "a += 256;\nwrite <- a ;", b""),
    (_BF_W + "a -= 1;\nwrite <- a ;", b""),
    (_BF_N + "a += 300;\nwrite <- a ;", b""),
    (_BF_N + "a -= 300;\nwrite <- a ;", b""),
    (_BF_U + "a, b\na += 5;\nb += a;\nwrite <- b ;", b""),
    (_BF_U + "a\nread -> a ;\nwrite <- a ;", b"X\n"),
    (_BF_U + "a\nread -> a ;\na -= 48 ;\nwrite <- a ;", b"0\n"),
    (_BF_U + "a\na += 1;\nif (a) { write <- a ; }", b""),
    (_BF_U + "a\na += 0;\nif (a) { write <- a ; }", b""),
    (_BF_U + "a\na += 0;\nif !(a) { write <- a ; }", b""),
    (_BF_U + "a\na += 5;\nwhile (a) { a -= 1; }\nwrite <- a ;", b""),
    (
        _BF_U + "a->2\na->0 += 65;\nwrite <- a->0 ;\na->1 += 66;\nwrite <- a->1 ;",
        b"",
    ),
    (_BF_U + "a\nread -> a ;\nwrite <- a ;\nread -> a ;\nwrite <- a ;", b"hi\nx\n"),
    (_BF_N + "a += 65; // comment\nwrite <- a ;", b""),
    # malformed programs (exit 2)
    ("not a directive\n#allocate a\n", b""),
    ("#basicfuck t=1 r=0~255 o=nearest\nbad alloc\n", b""),
    (_BF_N + "z += 1;", b""),
    (_BF_N + "a += ;", b""),
    (_BF_N + "if (a) { write <- a ;", b""),
    ("#basicfuck t=1 r=0~255 o=nearest\n#allocate a, b\n", b""),
    ("#basicfuck t=1 r=0~255 o=nearest\n#allocate write\n", b""),
    (_BF_N + "a += 1 @ 2;", b""),
    ("#basicfuck t=1 r=0~255\n#allocate a\n", b""),
]


def _run_basicfuck_native(
    binary: str, program: str, stdin: bytes
) -> tuple[bytes, int] | None:
    """Run ``program`` through the Basicfuck Rust cross-check."""
    return _run_rust_native(binary, program, stdin, strip_errors=True)


def _run_basicfuck_python(program: str, stdin: bytes) -> tuple[bytes, int]:
    """Run ``program`` through the in-package interpreter."""
    from esolangs.exceptions import HaltError
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.basicfuck import run

    io = ScriptedIO(stdin.decode("latin1"))
    try:
        run(program, io)
    except HaltError:
        return io.getvalue().encode("latin1"), 3
    except EOFError:
        return io.getvalue().encode("latin1"), 3
    except ValueError:
        return io.getvalue().encode("latin1"), 2
    return io.getvalue().encode("latin1"), 0


def _verify_basicfuck() -> bool:
    """Compare the Python Basicfuck interpreter against the Rust cross-check."""
    binary = _build_basicfuck()
    if binary is None:
        return True

    return _verify_rust(
        "Basicfuck",
        BASICFUCK_CORPUS,
        lambda program, stdin: _run_basicfuck_native(binary, program, stdin),
        _run_basicfuck_python,
        label=lambda program: program.splitlines()[-1],
    )


def _fuzz_basicfuck(rng: random.Random, count: int) -> bool:
    """Differentially fuzz Basicfuck with random truth tables.

    The boolean generator emits terminating decision-tree programs (reads,
    normalization, and nested if/if! dispatch); random source programs would
    frequently hang the Rust reference, which has no loop bound, so they are
    not fuzzed.
    """
    from esolangs.tools import boolean

    binary = _build_basicfuck()
    if binary is None:
        return True

    failures, checked = _fuzz_boolean(
        "Basicfuck",
        boolean.basicfuck,
        lambda program, stdin: _run_basicfuck_native(binary, program, stdin),
        _run_basicfuck_python,
        rng,
        count,
    )
    print(
        f"Basicfuck fuzz: {checked} checks match"
        if not failures
        else f"Basicfuck fuzz: {failures} failures of {checked}"
    )
    return failures == 0


# -- Unsquare corpus: every command plus the error categories -------------

# (program, input).  Programs that read always provide enough input, since
# the references exit on exhausted input.  Characters above 127 are written
# as UTF-8 by all three implementations.
UNSQUARE_CORPUS = [
    ("ii", b"X\n"),  # second read hits EOF: exit 3
    ("Io", b""),  # push 1 and print it
    ("Oo", b""),  # push 0 and print it
    ("Ooo", b""),  # o does not pop
    ("I+Po", b""),  # acc 2
    ("++Po", b""),  # acc 4
    ("-Po", b""),  # -2 prints as a decimal value
    ("xxPo", b""),  # doubling from 0
    ("+" * 32 + "Po", b""),  # '@'
    ("+" * 200 + "Po", b""),  # 200 -> 'è' (UTF-8, 2 bytes)
    ("+" * 256 + "Po", b""),  # 256 -> 'Ā' (UTF-8, 2 bytes)
    ("OISo", b""),  # swap
    ("IPPP", b""),  # pushes without printing
    ("IOA", b""),  # pop into acc
    ("OAIA", b""),  # O, A, I, A
    ("iPo", b"7\n"),  # read, then push acc (0)
    ("iPo", b"hi\n"),  # read pushes only the first character
    ("O>I<", b""),  # > skips when acc is 0
    ("I>I<", b""),  # > skips when acc is 1
    ("++>Po-<", b""),  # countdown loop: prints 4 then 2
    ("iA>PoiA<", b"h\n\x00\n"),  # cat until a 0 byte
    # invalid operations (exit 3)
    ("A", b""),  # empty-stack pop
    ("o", b""),  # o on an empty stack
    ("S", b""),  # swap with fewer than two
    ("<", b""),  # unmatched <
    ("I<", b""),  # < with acc 0/1 and no pending >
    (">", b""),  # > with no matching <
]


def _run_unsquare_native(
    binary: str, program: str, stdin: bytes
) -> tuple[bytes, int] | None:
    """Run ``program`` through the Unsquare Rust cross-check."""
    return _run_rust_native(binary, program, stdin)


def _run_unsquare_python(program: str, stdin: bytes) -> tuple[bytes, int]:
    """Run ``program`` through the in-package interpreter.

    The output is encoded as UTF-8 to match the references, which write
    characters above 127 as UTF-8 rather than bytes.
    """
    from esolangs.exceptions import HaltError
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.stack_based.unsquare import run

    io = ScriptedIO(stdin.decode("utf-8"))
    try:
        run(program, io)
    except HaltError:
        return io.getvalue().encode("utf-8"), 3
    except EOFError:
        return io.getvalue().encode("utf-8"), 3
    return io.getvalue().encode("utf-8"), 0


def _verify_unsquare() -> bool:
    """Compare the Python Unsquare interpreter against the Rust cross-check."""
    if not UNSQUARE_BIN.exists():
        print("[skip] Unsquare differential: Rust reference not built")
        return True

    return _verify_rust(
        "Unsquare",
        UNSQUARE_CORPUS,
        lambda program, stdin: _run_unsquare_native(str(UNSQUARE_BIN), program, stdin),
        _run_unsquare_python,
    )


def _fuzz_unsquare(rng: random.Random, count: int) -> bool:
    """Differentially fuzz Unsquare with random truth tables.

    The boolean generator emits terminating decision-tree programs; random
    instruction programs would frequently loop, and the Rust reference has
    no loop bound, so they are not fuzzed.
    """
    from esolangs.tools import boolean

    if not UNSQUARE_BIN.exists():
        print("[skip] Unsquare fuzz: Rust reference not built")
        return True

    failures, checked = _fuzz_boolean(
        "Unsquare",
        boolean.unsquare,
        lambda program, stdin: _run_unsquare_native(str(UNSQUARE_BIN), program, stdin),
        _run_unsquare_python,
        rng,
        count,
    )
    print(
        f"Unsquare fuzz: {checked} checks match"
        if not failures
        else f"Unsquare fuzz: {failures} failures of {checked}"
    )
    return failures == 0


# -- 3x corpus: every command plus the error categories --------------------

# (program, input).  Programs that read always provide enough input, since
# the reference crashes on exhausted input.
THREE_X_CORPUS = [
    ("??", b"5\n"),  # second read hits EOF: exit 3
    ("333x!", b""),  # 0
    ("3333x3x!", b""),  # 1
    ("3!", b""),  # 3
    ("3333333x3xx!", b""),  # (1-3)/3 = -2/3 as a fraction
    ("[Hi]", b""),  # literal
    ("[Hello, World!]", b""),  # literal with command characters
    ("[A]333x!", b""),  # literal skips past the bracket
    ("333x3#!", b""),  # swap
    ("3333xv3^!", b""),  # store and recall
    ("3^!", b""),  # unassigned variable defaults to 3
    ("33?x!", b"6\n"),  # read: (6-3)/3 = 1
    ("?3v3^!", b"1/3\n"),  # fraction input
    ("3333x3x(33x)!", b""),  # loop runs while the top is nonzero
    ("333x(3)!", b""),  # loop skips when the top is zero
    # invalid operations (exit 3)
    ("x", b""),  # x with too few items
    ("!", b""),  # pop an empty stack
    ("#", b""),  # swap with too few items
    ("(", b""),  # ( on an empty stack
    (")", b""),  # ) on an empty stack
    ("333x33x!", b""),  # division by zero
    ("333x(", b""),  # unmatched (
    ("33)", b""),  # ) with no pending (
]


def _run_three_x_native(program: str, stdin: bytes) -> tuple[bytes, int] | None:
    """Run ``program`` through the 3x Rust cross-check."""
    return _run_rust_native(
        str(THREE_X_BIN), program, stdin, strip_leading_newline=False
    )


def _run_three_x_python(program: str, stdin: bytes) -> tuple[bytes, int]:
    """Run ``program`` through the in-package interpreter."""
    from esolangs.exceptions import HaltError
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.stack_based.three_x import run

    io = ScriptedIO(stdin.decode("utf-8"))
    try:
        run(program, io)
    except HaltError:
        return io.getvalue().encode("utf-8"), 3
    except EOFError:
        return io.getvalue().encode("utf-8"), 3
    return io.getvalue().encode("utf-8"), 0


def _verify_three_x() -> bool:
    """Compare the Python 3x interpreter against the Rust cross-check."""
    if not THREE_X_BIN.exists():
        print("[skip] 3x differential: Rust reference not built")
        return True

    return _verify_rust(
        "3x",
        THREE_X_CORPUS,
        _run_three_x_native,
        _run_three_x_python,
    )


def _fuzz_three_x(rng: random.Random, count: int) -> bool:
    """Differentially fuzz 3x with random truth tables.

    The boolean generator emits terminating decision-tree programs (reads,
    variable stores, and guarded loops); random programs would frequently
    loop, so they are not fuzzed.
    """
    from esolangs.tools import boolean

    if not THREE_X_BIN.exists():
        print("[skip] 3x fuzz: Rust reference not built")
        return True

    failures, checked = _fuzz_boolean(
        "3x",
        boolean.three_x,
        _run_three_x_native,
        _run_three_x_python,
        rng,
        count,
    )
    print(
        f"3x fuzz: {checked} checks match"
        if not failures
        else f"3x fuzz: {failures} failures of {checked}"
    )
    return failures == 0


# -- %^2^-1 corpus: every command plus the error categories ----------------

# (program, input).  Programs that read always provide enough input, since
# Python's EOFError has no Rust equivalent (the reference stores -1).
PCT_CORPUS = [
    ("nn", b"X\n"),  # second read hits EOF: exit 3
    ("'e", b""),  # reset then print 0
    ("'ipe", b""),  # -3, p -> 3
    ("'ipse", b""),  # the fixed three-op path for byte 1
    ("'mse", b""),  # 0, *2, -2 -> -2 as a byte
    ("'ie", b""),  # -3 as a byte
    ("'l", b""),  # print the magnitude as a number
    ("'sl", b""),  # negative magnitude
    ("'me'l", b""),  # byte then number
    ("'m" * 12 + "l", b""),  # the 3003 reset fires before the l
    ("'te", b""),  # t with a zero magnitude does not rewind
    ("ne", b"X\n"),  # read a byte and print it
    ("nl", b"A\n"),  # read and print the value
    ("nt", b"A\n\x00\n"),  # t rewinds until a 0 byte is read
    ("n'ne", b"ab\ncd\n"),  # read, reset, read, print
    ("'e" * 5, b""),  # repeated prints
]


def _build_pct() -> str | None:
    """Return the built %^2^-1 Rust reference; None if cargo built it not yet."""
    if not PCT_SQUARED_MINUS_ONE_BIN.exists():
        print("[skip] %^2^-1 differential: Rust reference not built")
        return None
    return str(PCT_SQUARED_MINUS_ONE_BIN)


def _run_pct_native(
    binary: str, program: str, stdin: bytes
) -> tuple[bytes, int] | None:
    """Run ``program`` through the %^2^-1 Rust cross-check."""
    return _run_rust_native(binary, program, stdin)


def _run_pct_python(program: str, stdin: bytes) -> tuple[bytes, int]:
    """Run ``program`` through the in-package interpreter."""
    import importlib

    from esolangs.interpreters.io import ScriptedIO

    run = importlib.import_module(
        "esolangs.interpreters.register_based.pct_squared_minus_one"
    ).run

    io = ScriptedIO(stdin.decode("latin1"))
    try:
        run(program, io)
    except EOFError:
        return io.getvalue().encode("latin1"), 3
    return io.getvalue().encode("latin1"), 0


def _verify_pct() -> bool:
    """Compare the Python %^2^-1 interpreter against the Rust cross-check."""
    binary = _build_pct()
    if binary is None:
        return True

    return _verify_rust(
        "%^2^-1",
        PCT_CORPUS,
        lambda program, stdin: _run_pct_native(binary, program, stdin),
        _run_pct_python,
    )


# -- Painfuck corpus: every command plus the error categories --------------

# Programs are written in the source alphabet via _painfuck_encode, whose
# translation exercises the listed commands.  The nondeterministic `y` is
# excluded (both the generator and this corpus avoid it).
_PAIN_CYCLES = ("pevkjzwr", "yuctsobqihald")


def _painfuck_encode(targets: str) -> str:
    """Source text whose translation is exactly ``targets``."""
    out: list[str] = []
    k = 0
    for tc in targets:
        for cycle in _PAIN_CYCLES:
            if tc in cycle:
                out.append(cycle[(cycle.index(tc) - k) % len(cycle)])
                k += 1
                break
    return "".join(out)


_PAIN_CORPUS = [
    ("jj", b"X\n"),  # second read hits EOF: exit 3
    ("pue", b""),
    ("ppue", b""),
    ("sue", b""),
    ("pzue", b""),
    ("pkue", b""),
    ("ppkue", b""),
    ("phue", b""),
    ("pphue", b""),
    ("ppwo", b""),
    ("ppwqo", b""),
    ("prppdpue", b""),
    ("ppo", b""),
    ("ppuo", b""),
    ("pjo", b"5\n"),
    ("pjo", b"65\n"),
    ("jiu", b"7\n9\n"),
    ("jiu", b"255\n1\n"),
    ("ip", b"42\n"),
    ("ip", b"12x\n"),  # unparseable i input: exit 3 on both sides
    ("ppas b ue".replace(" ", ""), b""),
    ("pcsu", b""),
    ("pcue", b""),
    ("ptpue", b""),
    ("pve", b""),
    ("pvu", b""),
    ("pe", b""),
    ("b", b""),  # loop close with an empty stack: the reference segfaults
]


def _build_painfuck() -> str | None:
    """Return the built Painfuck Rust reference; None if cargo built it not yet."""
    if not PAINFUCK_BIN.exists():
        print("[skip] Painfuck differential: Rust reference not built")
        return None
    return str(PAINFUCK_BIN)


def _run_painfuck_native(
    binary: str, program: str, stdin: bytes
) -> tuple[bytes, int] | None:
    """Run ``program`` through the Painfuck Rust cross-check."""
    return _run_rust_native(binary, program, stdin)


def _run_painfuck_python(program: str, stdin: bytes) -> tuple[bytes, int]:
    """Run ``program`` through the in-package interpreter."""
    import importlib

    from esolangs.exceptions import HaltError
    from esolangs.interpreters.io import ScriptedIO

    run = importlib.import_module("esolangs.interpreters.tape_based.painfuck").run

    io = ScriptedIO(stdin.decode("latin1"))
    try:
        run(program, io)
    except HaltError:
        return io.getvalue().encode("latin1"), 3
    except EOFError:
        return io.getvalue().encode("latin1"), 3
    return io.getvalue().encode("latin1"), 0


def _verify_painfuck() -> bool:
    """Compare the Python Painfuck interpreter against the Rust cross-check."""
    binary = _build_painfuck()
    if binary is None:
        return True

    return _verify_rust(
        "Painfuck",
        _PAIN_CORPUS,
        lambda program, stdin: _run_painfuck_native(binary, program, stdin),
        _run_painfuck_python,
        prepare=_painfuck_encode,
    )


def _fuzz_painfuck(rng: random.Random, count: int) -> bool:
    """Differentially fuzz Painfuck with random byte text.

    The language has no boolean generator, so the text generator's programs
    (which avoid the nondeterministic `y`) are fuzzed instead.
    """
    from esolangs.tools.text import painfuck

    binary = _build_painfuck()
    if binary is None:
        return True

    failures, checked = _fuzz_text(
        "Painfuck",
        painfuck,
        lambda program, stdin: _run_painfuck_native(binary, program, stdin),
        _run_painfuck_python,
        rng,
        count,
    )
    print(
        f"Painfuck fuzz: {checked} programs match"
        if not failures
        else f"Painfuck fuzz: {failures} failures of {checked}"
    )
    return failures == 0


# -- bit~ corpus: every command plus the error categories ------------------

# Unmatched brackets raise in both sides (the former Ruby port hung).
BIT_TILDE_CORPUS = [
    ("))", b"a\n"),  # second read hits EOF: exit 3
    ("~(", b""),
    ("~>~(", b""),
    ("~>~>~(", b""),
    ("~<(", b""),
    (">(", b""),
    (")((", b"a\n"),
    ("))(((", b"ab\ncd\n"),
    ("~)(", b"a\n"),
    ("~)(", b"\xff\n"),
    ("~)(", b"\x80\n"),
    ("{~}", b""),
    ("~{~}", b""),
    ("}~", b""),
    ("{~}~(", b""),
    ("~{~}(", b""),
    ("{>~}(~", b""),
    (")", b"a\n"),
    ("~~~~", b""),
]


def _run_bit_tilde_native(program: str, stdin: bytes) -> tuple[bytes, int] | None:
    """Run ``program`` through the bit~ Rust cross-check."""
    return _run_rust_native(str(BIT_TILDE_BIN), program, stdin)


def _run_bit_tilde_python(program: str, stdin: bytes) -> tuple[bytes, int]:
    """Run ``program`` through the in-package interpreter."""
    import importlib

    from esolangs.exceptions import HaltError
    from esolangs.interpreters.io import ScriptedIO

    run = importlib.import_module("esolangs.interpreters.tape_based.bit_tilde").run

    io = ScriptedIO(stdin.decode("latin1"))
    try:
        run(program, io)
    except HaltError:
        return io.getvalue().encode("latin1"), 3
    except EOFError:
        return io.getvalue().encode("latin1"), 3
    except ValueError:
        return io.getvalue().encode("latin1"), 2
    return io.getvalue().encode("latin1"), 0


def _verify_bit_tilde() -> bool:
    """Compare the Python bit~ interpreter against the Rust cross-check."""
    if not BIT_TILDE_BIN.exists():
        print("[skip] bit~ differential: Rust reference not built")
        return True

    return _verify_rust(
        "bit~",
        BIT_TILDE_CORPUS,
        _run_bit_tilde_native,
        _run_bit_tilde_python,
    )


# -- RISC-V reference helpers ----------------------------------------------
#
# Assemble and run the RISC-V port of an interpreter under unicorn as an
# independent reference for the generator-based differential fuzzers.


@functools.cache
def _build_riscv(name: str) -> bytes | None:
    """Assemble the RISC-V port ``extra/assembly/{name}-riscv.s``.

    Returns None if the cross-compiler is missing.  Cached: the ELF is
    deterministic for a given source, and the differential fuzzers call this
    once per program, so without caching the nocomment fuzz would re-run the
    cross-compiler for every case.
    """
    asm = ROOT / "extra" / "assembly" / f"{name}-riscv.s"
    if not asm.exists():
        return None
    for cc in ("riscv64-linux-gnu-gcc", "riscv64-elf-gcc"):
        if shutil.which(cc) is None:
            continue
        binary = Path("/tmp") / f"verify-{name}-riscv"
        rv = subprocess.run(
            [
                cc,
                "-nostdlib",
                "-static",
                "-march=rv64i",
                "-mabi=lp64",
                str(asm),
                "-o",
                str(binary),
            ],
            capture_output=True,
        )
        if rv.returncode == 0 and binary.exists():
            return binary.read_bytes()
    return None


def _run_riscv_elf(binary: bytes, program: str) -> tuple[bytes, int] | None:
    """Run ``program`` (as the stdin stream) through a RISC-V reference ELF."""
    import importlib

    try:
        riscv_elf_runner = importlib.import_module("riscv_elf_runner")
    except SystemExit:
        return None
    try:
        out, code = riscv_elf_runner.run_elf(binary, program.encode("latin1"))
    except ValueError:
        return None
    except Exception:
        return None  # the reference faulted (e.g. walked off its tape)
    return out, code


def _asm_refs(riscv_name: str, program: str) -> tuple[bytes, int] | None:
    """Run ``program`` through the RISC-V reference ``{name}-riscv.s``.

    Returns ``(out, code)``, or None when the reference does not terminate
    cleanly (it looped or faulted).
    """
    riscv = _build_riscv(riscv_name)
    if riscv is None:
        return None
    return _run_riscv_elf(riscv, program)


def _riscv_runner_available() -> bool:
    """Whether the unicorn-backed RISC-V ELF runner can be imported."""
    import importlib

    try:
        importlib.import_module("riscv_elf_runner")
    except (ImportError, SystemExit):
        return False
    return True


def _asm_refs_ready(riscv_name: str) -> bool:
    """Whether the RISC-V reference can be built *and* executed.

    Both halves matter: the cross-compiler assembles the ELF, and unicorn
    (via ``riscv_elf_runner``) executes it.  Checking only the compiler let
    a machine with a cross-compiler but no unicorn pass the gate and then
    read every reference run as an empty ``(b"", 1)`` result, reporting the
    whole corpus as divergent.  The toolchain being absent is a skip, not a
    failure.
    """
    return _build_riscv(riscv_name) is not None and _riscv_runner_available()


def _fuzz_laserfuck(rng: random.Random, count: int) -> bool:
    """Differentially fuzz LaserFuck with random truth tables.

    Raw random grids mostly hang the Rust reference (it has no step limit),
    so the fuzzer instead draws random truth tables and runs them through the
    boolean generator, which emits terminating decision-tree grids that
    exercise the same mirror/conditional machinery.
    """
    if shutil.which("cargo") is None or not RUST_BIN.exists():
        print("[skip] LaserFuck fuzz: Rust reference not built")
        return True

    failures = checked = 0
    for _ in range(count):
        n = rng.randint(2, 3)
        table = "".join(rng.choice("01") for _ in range(2**n))
        # 4 runs: the funnel makes the output heading-independent, and the
        # fuzzer draws many tables, so each needs to stay cheap
        c, f = _check_laserfuck_boolean(table, n, runs=4)
        checked += c
        failures += f

    print(
        f"LaserFuck fuzz: {checked} checks match"
        if not failures
        else f"LaserFuck fuzz: {failures} failures of {checked}"
    )
    return failures == 0


def main() -> int:
    """Verify the differential corpora, optionally fuzzing random programs."""
    parser = argparse.ArgumentParser(
        description="Differential-test the in-package interpreters against "
        "their native cross-checks."
    )
    parser.add_argument(
        "--fuzz",
        type=int,
        default=0,
        metavar="N",
        help="also fuzz N random programs per language with a seeded RNG "
        "(default: 0, corpus only)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="seeded RNG for the fuzzers (default: 0)",
    )
    args = parser.parse_args()

    ok = _verify_laserfuck()
    ok = _verify_nocomment() and ok
    ok = _verify_bfpda() and ok
    ok = _verify_ram0() and ok
    ok = _verify_bio() and ok
    ok = _verify_minsky_swap() and ok
    ok = _verify_forth() and ok
    ok = _verify_basicfuck() and ok
    ok = _verify_unsquare() and ok
    ok = _verify_three_x() and ok
    ok = _verify_pct() and ok
    ok = _verify_painfuck() and ok
    ok = _verify_bit_tilde() and ok
    if args.fuzz:
        rng = random.Random(args.seed)
        ok = _fuzz_nocomment(rng, args.fuzz) and ok
        ok = _fuzz_bfpda(rng, args.fuzz) and ok
        ok = _fuzz_ram0(rng, args.fuzz) and ok
        ok = _fuzz_bio(rng, args.fuzz) and ok
        ok = _fuzz_minsky_swap(rng, args.fuzz) and ok
        ok = _fuzz_forth(rng, args.fuzz) and ok
        ok = _fuzz_basicfuck(rng, args.fuzz) and ok
        ok = _fuzz_unsquare(rng, args.fuzz) and ok
        ok = _fuzz_three_x(rng, args.fuzz) and ok
        ok = _fuzz_painfuck(rng, args.fuzz) and ok
        # LaserFuck fuzz is far slower per iteration (each truth table needs
        # 12 Rust runs per input combination), so it gets a tenth of the
        # budget.
        ok = _fuzz_laserfuck(rng, max(1, args.fuzz // 10)) and ok
    print("differential corpus: all ok" if ok else "differential corpus: FAILURES")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
