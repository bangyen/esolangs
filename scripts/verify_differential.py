"""Differential-test the in-package interpreters against their native cross-checks.

The ``extra/`` implementations are not upstream references: they are
cross-checks written in this repository (see README "Extra
Implementations").  They still serve as oracles for the in-package Python
interpreters, so this script runs a *full-surface corpus* — every
instruction plus edge cases, not just generator output — through both the
Python interpreter and the native implementation and asserts they agree.

Languages with both an in-package interpreter and a native cross-check:

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
  written ``0i[xyz]{ ... };``, every command ended by ``;``, and ``//``
  comments).  The assembly is run under unicorn via ``riscv_elf_runner``
  and must agree with the Python interpreter on the full corpus; both
  check the whole program when it loads, so every rejection is "malformed"
  (exit 2) and is raised before any output.
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

Called from CI's ``assembly`` job (which provides unicorn and the RISC-V
compiler) and from ``verify.py`` locally.  References whose toolchain is
missing are skipped, not failed.

Usage:
    PYTHONPATH=src python scripts/verify_differential.py
    PYTHONPATH=src python scripts/verify_differential.py --fuzz 200 --seed 1
"""

import argparse
import contextlib
import io
import pathlib
import random
import shutil
import signal
import subprocess
import sys
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, TypeVar

ROOT = Path(__file__).parents[1]

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

# Every command over three registers x/y/z.  A command is a triple ended by
# its `;`: `0o[xyz];` increments, `1o[xyz];` decrements, `1i[xyz];` prints
# the register's low byte, `0i[xyz]{` is a while-loop guard carrying the
# brace that opens its body, and `};` closes the innermost loop.  Matching
# is case-insensitive, `//` runs to end of line as a comment, and anything
# else is a load error.
#
# Errors are one category: the whole program is checked when it loads --
# the commands, their terminators, and the brace balance -- so every
# rejection is "malformed" (exit 2) and is raised eagerly, before any
# output.  There is no invalid *runtime* operation (exit 3) left to reach,
# since a `};` can only run once parsing has proved it has a loop to close.
# Programs must terminate (a loop whose body never changes its guard
# register loops forever).
BIO_CORPUS = [
    "",  # empty program: no output
    "   \n\t  ",  # whitespace only: no output
    "0ox; //increment\n1ix; //print\n",  # `//` comments are stripped
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
    # error categories -- all malformed (exit 2), all raised at load
    "};",  # bare close with no loop to close
    "0ox;};",  # close with no open loop, after valid output
    "0iy{0ox;",  # guard with no matching close
    "0ix{0iy{};",  # unmatched outer guard
    ";x1Ox{{}0Iy",  # not commands at all
    "0ox;invalid;1ix;",  # stray text is rejected, not treated as a comment
    "0ox1ix;",  # a triple missing its `;` is not a command
    "0ox;0ix1ox;};",  # a guard missing its `{` is not a command
    "0ox;{1ix;",  # a `{` not carried by a guard
    "0ox;/ 1ix;",  # a lone `/` is not the start of a comment
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
    program.  BIO checks its whole program when it loads -- the commands,
    their terminators, and the brace balance -- so every rejection is that
    one category and there is no invalid *runtime* operation (exit 3) left
    to reach: a ``};`` can only run once parsing has proved it has a loop
    to close.
    """
    from esolangs.interpreters.register_based.bio import run

    buffer, sink = _capture_io()

    try:
        run(program, sink)
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
        # ``/`` and a newline are in the alphabet so the fuzz reaches the
        # comment scanner (and a lone ``/``, which is a load error) as well
        # as the command and brace paths.
        _random_program("01OoIiXxYyZz{};/ \n", 40),
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


_LANGUAGES: tuple[tuple[str, str, str], ...] = (
    (
        "nocomment",
        "interpreters/tape_based/nocomment.py",
        "extra/assembly/nocomment-riscv.s",
    ),
    ("bfpda", "interpreters/stack_based/bf_pda.py", "extra/assembly/bfpda-riscv.s"),
    ("ram0", "interpreters/register_based/ram0.py", "extra/assembly/ram0-riscv.s"),
    ("bio", "interpreters/register_based/bio.py", "extra/assembly/bio-riscv.s"),
    (
        "minsky_swap",
        "interpreters/register_based/minsky_swap.py",
        "extra/assembly/minsky_swap-riscv.s",
    ),
)


def _scoped_languages() -> tuple[set[str] | None, str]:
    """Return the languages worth cross-checking, and why that set was chosen.

    ``None`` means "run them all" -- the answer was unclear, or something
    shared moved -- so an unreadable diff never silently drops the corpus.
    """
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from _scope import changed_files, widens_to_everything

    changed = changed_files()
    reason = widens_to_everything(changed)
    if reason is not None:
        return None, reason
    picked = {
        name
        for name, py, native in _LANGUAGES
        if any(f.endswith(py) or f.endswith(native) for f in changed)
    }
    return picked, f"{len(picked)} cross-checked language(s) changed"


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
    parser.add_argument(
        "--scope",
        action="store_true",
        help="only cross-check languages this branch touched (full run when "
        "the diff is unreadable or shared machinery moved)",
    )
    args = parser.parse_args()

    verifiers = {
        "nocomment": _verify_nocomment,
        "bfpda": _verify_bfpda,
        "ram0": _verify_ram0,
        "bio": _verify_bio,
        "minsky_swap": _verify_minsky_swap,
    }

    selected = set(verifiers)
    if args.scope:
        picked, why = _scoped_languages()
        selected = set(verifiers) if picked is None else picked
        scope_note = "all" if picked is None else (", ".join(sorted(picked)) or "none")
        print(f"differential scope: {scope_note} ({why})")
        if not selected:
            print("differential corpus: all ok")
            return 0

    ok = True
    for name, verify in verifiers.items():
        if name in selected:
            ok = verify() and ok

    if args.fuzz:
        rng = random.Random(args.seed)
        fuzzers = {
            "nocomment": _fuzz_nocomment,
            "bfpda": _fuzz_bfpda,
            "ram0": _fuzz_ram0,
            "bio": _fuzz_bio,
            "minsky_swap": _fuzz_minsky_swap,
        }
        for name, fuzz in fuzzers.items():
            if name in selected:
                ok = fuzz(rng, args.fuzz) and ok
    print("differential corpus: all ok" if ok else "differential corpus: FAILURES")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
