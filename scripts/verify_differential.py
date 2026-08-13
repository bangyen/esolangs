"""Differential-test the in-package interpreters against their native cross-checks.

The ``extra/`` implementations are not upstream references: they are
cross-checks written in this repository (see README "Extra
Implementations").  They still serve as oracles for the in-package Python
interpreters, so this script runs a *full-surface corpus* — every
instruction plus edge cases, not just generator output — through both the
Python interpreter and the native implementation and asserts they agree.

Languages with both an in-package interpreter and a native cross-check:

* **EXCON** — ``tape_based/excon.py`` vs ``extra/r/excon.r``.  Both are
  deterministic single-pass bit-pool interpreters, so outputs must match
  exactly.
* **LaserFuck** — ``other/laserfuck.py`` vs ``extra/rust/laserfuck.rs``.
  The Rust reference picks a random initial heading, so its output is a
  *set* across runs; the Python interpreter (which accepts a fixed heading)
  must produce a member of that set for each of the four headings.
* **NoComment** — ``tape_based/nocomment.py`` vs
  ``extra/assembly/nocomment.asm``.  Both implement the full wiki language
  (10 commands over a tape and stack).  The assembly is run under unicorn
  via ``x86_elf_runner`` and must agree with the Python interpreter on the
  full corpus; both error on non-commands, stack underflow, and out-of-range
  jumps.

Called from CI's ``extra-languages`` and ``rust`` jobs (which provide
Rscript and cargo) and from ``verify.py`` locally.  References whose
toolchain is missing are skipped, not failed.

Usage:
    PYTHONPATH=src python scripts/verify_differential.py
    PYTHONPATH=src python scripts/verify_differential.py --fuzz 200 --seed 1
"""

import argparse
import io
import random
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parents[1]
EXTRA_R = ROOT / "extra" / "r"
RUST_BIN = ROOT / "extra" / "rust" / "target" / "debug" / "laserfuck"


# -- EXCON corpus: every instruction (: ^ ! <) plus edge cases ------------

EXCON_CORPUS = [
    "",  # empty program: no output
    ":",  # reset
    "^",  # flip one bit (cell 7)
    "^^",  # flip twice (back to zero)
    "^^^^^^^",  # all 8 bits
    "!:",  # print zero byte then reset
    "^!",  # print 1 (pool 10000000 -> 128)
    "^^^^^^^!",  # print 127
    "^^^^^^^^!",  # print 255
    "^^^^^^^^^",  # 9 flips: the 9th hits an invalid < ? no, ^ never faults
    "<",  # pointer below 8 (cell 6) — legal
    "^<^",  # flip cell 7 then cell 6
    ":^<^<^<^<^<^<^<^!",  # flip all 8 cells -> 255
    "^^^^!!!",  # repeat prints
    ":^!^<^!^<^!^<^!^<^!^<^!^<^!^<^!",  # each cell flipped then printed
    "<^<^<^<^<^<^<^!",  # build 11111111 by flipping all, then print
    "^^^<^^^<^^^<^^^<^^^<^^^<^^^<^^^!",  # alternating
]

# A program that moves the pointer 8 times left from cell 7 faults; the
# Python interpreter raises HaltError and the R cross-check stops with an
# error (both now agree).  Excluded from the exact-match corpus and checked
# separately for the exit-code agreement.
EXCON_FAULT = "<" * 8 + "!"


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


def _run_nocomment_python(program: str) -> tuple[bytes, int]:
    """Run the Python NoComment interpreter; return (output, exit code).

    Exit codes follow the cross-check convention: 0 = success, 2 = malformed
    program (ValueError), 3 = invalid operation (HaltError).
    """
    from esolangs.exceptions import HaltError
    from esolangs.interpreters.io import IO
    from esolangs.interpreters.tape_based.nocomment import run

    buffer = io.BytesIO()

    class _IO(IO):
        def print_char(self, char: str) -> None:
            buffer.write(char.encode("latin1"))

    try:
        run(program, _IO())
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
    None if the program did not terminate within ``timeout`` seconds (the
    fuzzer's analog of the assembly's instruction-count cap).  The alarm is
    only meaningful on POSIX; the interpreter is skipped (None) elsewhere.
    """
    import signal

    if not hasattr(signal, "SIGALRM"):
        return None

    class _TimeoutError(Exception):
        pass

    def _alarm(_signum: int, _frame: object) -> None:
        raise _TimeoutError

    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(int(timeout))
    try:
        return _run_nocomment_python(program)
    except _TimeoutError:
        return None
    finally:
        signal.alarm(0)


def _assemble_nocomment() -> bytes | None:
    """Assemble the NoComment cross-check; None if the toolchain is missing."""
    if shutil.which("nasm") is None:
        print("[skip] NoComment differential: nasm not found")
        return None
    try:
        import x86_elf_runner as r
    except SystemExit:
        print("[skip] NoComment differential: unicorn not installed")
        return None

    asm = (ROOT / "extra" / "assembly" / "nocomment.asm").read_text()
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write(asm)
        path = f.name
    try:
        return r.assemble(path)
    finally:
        Path(path).unlink()


def _verify_nocomment() -> bool:
    """Compare the Python NoComment interpreter against the assembly cross-check.

    The assembly is run under unicorn (``x86_elf_runner``), which requires
    unicorn and nasm; it is skipped when either is missing.  Both
    implementations error on non-commands, stack underflow, and out-of-range
    jumps, and must agree on the valid-program corpus.
    """
    binary = _assemble_nocomment()
    if binary is None:
        return True
    import x86_elf_runner as r

    failures = 0
    for program in NOCOMMENT_CORPUS:
        try:
            asm_out, asm_code = r.run_elf(binary, stdin=program.encode())
        except ValueError:
            asm_out, asm_code = b"", 1
        py_out, py_code = _run_nocomment_python(program)
        if (asm_out, asm_code) != (py_out, py_code):
            failures += 1
            print(
                f"NoComment {program!r}: asm={(asm_out, asm_code)} "
                f"py={(py_out, py_code)}"
            )

    if not failures:
        print(f"NoComment differential: {len(NOCOMMENT_CORPUS)} programs match")
    return failures == 0


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


def _run_excon_python(program: str) -> str:
    from esolangs.interpreters.io import IO
    from esolangs.interpreters.tape_based.excon import run

    buffer = io.StringIO()

    class _IO(IO):
        def print_char(self, char: str) -> None:
            buffer.write(char)

    run(program, _IO())
    return buffer.getvalue()


def _verify_excon() -> bool:
    """Compare the Python EXCON interpreter against the R cross-check.

    R's stdout cannot carry a NUL byte (``intToUtf8(0)`` writes nothing),
    while Python's ``chr(0)`` writes one, so NULs are stripped from both
    sides before comparing: the corpus then checks the non-zero byte
    semantics that R is able to express.
    """
    if shutil.which("Rscript") is None:
        print("[skip] EXCON differential: Rscript not found")
        return True

    failures = 0
    r_ref = ["Rscript", str(EXTRA_R / "excon.r")]

    def strip_nul(text: str) -> str:
        return text.replace("\x00", "")

    for program in EXCON_CORPUS:
        out = _run_native(r_ref, program)
        assert out is not None, f"EXCON reference did not terminate on {program!r}"
        native = strip_nul(out.decode(errors="replace"))
        py = strip_nul(_run_excon_python(program))
        if native != py:
            failures += 1
            print(f"EXCON {program!r}: python {py!r} vs R {native!r}")

    # the pointer-fault program: both implementations must fault
    py_fault = _run_excon_fault()
    r = _run_native_code(r_ref, EXCON_FAULT)
    assert r is not None, "EXCON reference did not terminate on the fault program"
    r_fault = (r[0].decode(errors="replace"), r[1])
    if py_fault != r_fault:
        failures += 1
        print(f"EXCON fault: python {py_fault!r} vs R {r_fault!r}")

    if not failures:
        print(f"EXCON differential: {len(EXCON_CORPUS)} programs match")
    return failures == 0


def _run_excon_python_code(program: str) -> tuple[str, int]:
    """Run the Python EXCON interpreter; return (output, exit_code).

    The off-pool fault is an invalid operation, exit code 3 (the cross-check
    convention for HaltError).
    """
    from esolangs.exceptions import HaltError
    from esolangs.interpreters.io import IO
    from esolangs.interpreters.tape_based.excon import run

    buffer = io.StringIO()

    class _IO(IO):
        def print_char(self, char: str) -> None:
            buffer.write(char)

    try:
        run(program, _IO())
    except HaltError:
        return buffer.getvalue(), 3
    return buffer.getvalue(), 0


def _run_excon_fault() -> tuple[str, int]:
    """Run the pointer-fault program; return (output, exit_code)."""
    return _run_excon_python_code(EXCON_FAULT)


def _run_laserfuck_python(
    program: str, heading: int, inputs: list[str] | None = None
) -> str:
    from esolangs.interpreters.io import IO
    from esolangs.interpreters.other.laserfuck import run

    buffer = io.StringIO()
    reads = list(inputs if inputs is not None else ["1"])

    class _IO(IO):
        def print_char(self, char: str) -> None:
            buffer.write(char)

        def print_num(self, num: int) -> None:
            buffer.write(str(num))

        def print_line(self, text: str = "") -> None:
            buffer.write(text + "\n")

        def input_str(self, prompt: str = "Input: ") -> str:  # noqa: ARG002
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
    from esolangs.tools.booleans import other

    program = other.laserfuck(table, n)
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
        for _ in range(30):
            out = _run_native([str(RUST_BIN)], program, input_bytes=b"1\n")
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
# * EXCON: straight-line over ``:^<!`` — the only way to fault is the
#   off-pool pointer, which both implementations agree is exit 3.
# * NoComment: ``idclrnfsbo`` — ``b``/``s`` jump by a peeked stack value, so
#   a random program may loop; both implementations bound the run (the
#   assembly via its instruction-count cap, Python via SIGALRM), and a
#   program that loops on one side but halts on the other is a failure.
# * LaserFuck: random truth tables through the boolean generator, which
#   produces terminating decision-tree grids (a random grid would hang the
#   reference, so raw grids are not fuzzable).


def _fuzz_excon(rng: random.Random, count: int) -> bool:
    """Differentially fuzz EXCON with random programs."""
    if shutil.which("Rscript") is None:
        print("[skip] EXCON fuzz: Rscript not found")
        return True

    r_ref = ["Rscript", str(EXTRA_R / "excon.r")]
    alphabet = ":^<!"
    failures = checked = 0
    for _ in range(count):
        program = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 40)))
        native = _run_native_code(r_ref, program)
        assert native is not None, f"EXCON reference did not terminate on {program!r}"
        native_out = native[0].decode(errors="replace").replace("\x00", "")
        native_code = native[1]
        py_out, py_code = _run_excon_python_code(program)
        checked += 1
        if (native_out, native_code) != (py_out.replace("\x00", ""), py_code):
            failures += 1
            print(
                f"EXCON fuzz {program!r}: python "
                f"{(py_out.replace(chr(0), ''), py_code)!r} "
                f"vs R {(native_out, native_code)!r}"
            )

    print(
        f"EXCON fuzz: {checked} programs match"
        if not failures
        else f"EXCON fuzz: {failures} failures of {checked}"
    )
    return failures == 0


def _fuzz_nocomment(rng: random.Random, count: int) -> bool:
    """Differentially fuzz NoComment with random programs.

    A random ``b``/``s`` program may loop forever.  The assembly raises
    ValueError when it exhausts its instruction-count cap, and Python times
    out under SIGALRM; ``None`` means "did not terminate" on that side.  A
    program that halts on one side but loops on the other is a divergence
    (and the reason a seeded fuzzer is worth having).
    """
    binary = _assemble_nocomment()
    if binary is None:
        return True
    import x86_elf_runner as r

    # The assembly's tape and stack live in a fixed mapped region below the
    # program buffer; a program that loops (or extends the tape) long enough
    # writes past it and unicorn raises UcError.  That is a resource limit,
    # the same class as the instruction-count cap's ValueError: both mean the
    # assembly did not halt cleanly, and a matching Python loop is not a
    # divergence.
    from unicorn import UcError

    alphabet = "idclrnfsbo"
    failures = checked = loops = 0
    for _ in range(count):
        program = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 30)))
        py = _run_nocomment_python_limited(program, timeout=3)
        try:
            asm = r.run_elf(binary, stdin=program.encode())
        except (ValueError, UcError):
            asm = None
        if py is None and asm is None:
            loops += 1
            continue
        if py is None and asm is not None:
            # Python's 3s budget is a heuristic; the assembly is far faster,
            # so confirm a genuinely-looping program with a longer budget
            # before calling the termination mismatch a divergence.
            py = _run_nocomment_python_limited(program, timeout=30)
        if py is None or asm is None:
            failures += 1
            print(
                f"NoComment fuzz {program!r}: termination mismatch "
                f"(python {'loops' if py is None else 'halts'}, "
                f"asm {'loops' if asm is None else 'halts'})"
            )
            continue
        checked += 1
        if py != asm:
            failures += 1
            print(f"NoComment fuzz {program!r}: asm={asm!r} py={py!r}")

    print(
        f"NoComment fuzz: {checked} programs match, {loops} consistent loops"
        if not failures
        else f"NoComment fuzz: {failures} failures of {checked} (plus {loops} loops)"
    )
    return failures == 0


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

    ok = _verify_excon()
    ok = _verify_laserfuck() and ok
    ok = _verify_nocomment() and ok
    if args.fuzz:
        rng = random.Random(args.seed)
        ok = _fuzz_excon(rng, args.fuzz) and ok
        ok = _fuzz_nocomment(rng, args.fuzz) and ok
        # LaserFuck fuzz is far slower per iteration (each truth table needs
        # 12 Rust runs per input combination), so it gets a tenth of the
        # budget.
        ok = _fuzz_laserfuck(rng, max(1, args.fuzz // 10)) and ok
    print("differential corpus: all ok" if ok else "differential corpus: FAILURES")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
