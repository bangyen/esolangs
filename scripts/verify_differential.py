"""Differential-test the in-package interpreters against their native cross-checks.

The ``extra/`` implementations are not upstream references: they are
cross-checks written in this repository (see README "Extra
Implementations").  They still serve as oracles for the in-package Python
interpreters, so this script runs a *full-surface corpus* — every
instruction plus edge cases, not just generator output — through both the
Python interpreter and the native implementation and asserts they agree.

Languages with both an in-package interpreter and a native cross-check:

* **LaserFuck** — ``other/laserfuck.py`` vs ``extra/rust/laserfuck.rs``.
  The Rust reference picks a random initial heading, so its output is a
  *set* across runs; the Python interpreter (which accepts a fixed heading)
  must produce a member of that set for each of the four headings.
* **NoComment** — ``tape_based/nocomment.py`` vs
  ``extra/assembly/nocomment-riscv.s``.  Both implement the full wiki language
  (10 commands over a tape and stack).  The assembly is run under unicorn
  via ``riscv_elf_runner`` and must agree with the Python interpreter on the
  full corpus; both error on non-commands, stack underflow, and out-of-range
  jumps.
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
* **3x** — ``other/three_x.py`` vs ``extra/rust/three_x.rs``.  Both compute
  over exact rationals; the reference prints its ``Input: `` prompts to
  stdout (stripped before comparing) and both agree on the exit-code
  convention.
* **%^2^-1** — ``register_based/%^2^-1.py`` vs ``extra/rust/pct.rs``.
  Both track the accumulator as a signed magnitude with the 3003 reset; the
  reference prints its ``Input: `` prompts to stdout, which are stripped
  before comparing.
* **2dFish** — ``other/2dfish.py`` vs ``extra/rust/2dfish.rs``.  Both run
  the ragged grid with the reference's trailing-newline phantom row.
* **Painfuck** — ``tape_based/painfuck.py`` vs ``extra/rust/painfuck.rs``.
  Corpus programs are encoded into the source alphabet (the reference
  translates the source before running); the nondeterministic ``y`` is
  excluded.
* **bit~** — ``other/bit_tilde.py`` vs ``extra/rust/bit_tilde.rs``.  Both
  write bytes above 127 as raw bytes; unmatched brackets raise (the former
  Ruby reference hung).

Called from CI's ``assembly`` and ``rust`` jobs (which provide
unicorn+the RISC-V compiler and cargo) and from ``verify.py`` locally.
References whose toolchain is missing are skipped, not failed.

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
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).parents[1]
RUST_BIN_DIR = ROOT / "extra" / "rust" / "target" / "debug"
RUST_BIN = RUST_BIN_DIR / "laserfuck"
UNSQUARE_BIN = RUST_BIN_DIR / "unsquare"
KAK_BIN = RUST_BIN_DIR / "kak"
TRASH_BIN = RUST_BIN_DIR / "trash"
SEVENTY_FOUR_BIN = RUST_BIN_DIR / "seventy_four"
PCT_BIN = RUST_BIN_DIR / "pct"
BIT_TILDE_BIN = RUST_BIN_DIR / "bit_tilde"
FORTH_BIN = RUST_BIN_DIR / "forth"
BASICFUCK_BIN = RUST_BIN_DIR / "basicfuck"
TWO_D_FISH_BIN = RUST_BIN_DIR / "two_d_fish"
PAINFUCK_BIN = RUST_BIN_DIR / "painfuck"
THREE_X_BIN = RUST_BIN_DIR / "three_x"
LEAN_BIN = ROOT / "extra" / "lean" / "esolangs" / ".lake" / "build" / "bin"
ALBABET_BIN = LEAN_BIN / "albabet"
BFPDA_BIN = LEAN_BIN / "bfpda"

# Parallelism for the native-reference runs: each check spawns a subprocess,
# so threads (which just wait on the subprocess) scale well.
_WORKERS = 8


def _run_parallel(fn, tasks):
    """Run ``fn`` over ``tasks`` concurrently, returning results in order."""
    with ThreadPoolExecutor(max_workers=_WORKERS) as executor:
        return list(executor.map(fn, tasks))


def _fuzz_boolean(name, builder, native, python, rng, count):
    """Fuzz ``count`` random truth tables through both implementations.

    ``native(program, stdin)`` runs the reference (None on a timeout) and
    ``python(program, stdin)`` the in-package interpreter.  Returns
    ``(failures, checked)``.
    """
    tasks = []
    for _ in range(count):
        n = rng.randint(1, 4)
        table = "".join(rng.choice("01") for _ in range(2**n))
        program = builder(table, n)
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


def _fuzz_text(name, generator, native, python, rng, count):
    """Fuzz ``count`` random byte texts through both implementations."""
    tasks = []
    for _ in range(count):
        text = "".join(chr(rng.randrange(256)) for _ in range(rng.randint(1, 10)))
        tasks.append((generator(text), text))
    results = _run_parallel(lambda t: native(t[0], b""), tasks)
    failures = checked = 0
    for (program, text), result in zip(tasks, results, strict=True):
        if result is None:
            print(f"{name} {text!r}: reference did not terminate")
            failures += 1
            checked += 1
            continue
        py = python(program, b"")
        checked += 1
        if result != py:
            failures += 1
            print(f"{name} {text!r}: reference {result!r} vs Python {py!r}")
    return failures, checked


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


def _verify_nocomment() -> bool:
    """Compare the Python NoComment interpreter against the assembly cross-check.

    The RISC-V reference is run under unicorn (``riscv_elf_runner``), which
    requires unicorn and a RISC-V cross-compiler; it is skipped when either
    is missing.  Both
    implementations error on non-commands, stack underflow, and out-of-range
    jumps, and must agree on the valid-program corpus.
    """
    if not _asm_refs_ready("nocomment"):
        return True

    failures = 0
    for program in NOCOMMENT_CORPUS:
        ref = _asm_refs("nocomment", program)
        py_out, py_code = _run_nocomment_python(program)
        if ref is None:
            asm_out, asm_code = b"", 1
        else:
            asm_out, asm_code = ref
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
    if not _asm_refs_ready("nocomment"):
        return True

    # The references' tape and stack live in a fixed mapped region below the
    # program buffer; a program that loops (or extends the tape) long enough
    # writes past it and unicorn raises UcError, which the runners fold into
    # None.  That is a resource limit, the same class as the instruction-count
    # cap: a matching Python loop is not a divergence.
    alphabet = "idclrnfsbo"
    failures = checked = loops = 0
    for _ in range(count):
        program = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 30)))
        py = _run_nocomment_python_limited(program, timeout=3)
        asm = _asm_refs("nocomment", program)
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
    ("a5.", b""),  # unknown char with 1 element: exit 3
    ("(5", b""),  # unterminated bracket: exit 3
    ("[", b""),  # unterminated bracket: exit 3
    ("{5", b""),  # unterminated bracket: exit 3
]


def _run_forth_native(
    binary: str, program: str, stdin: bytes
) -> tuple[bytes, int] | None:
    """Run ``program`` through the Rust cross-check; return (stdout, exit code).

    The Rust reference writes its ``Input: `` prompt to stdout, which is stripped (the
    Python side routes the prompt through the IO layer instead).  Returns
    None if the reference does not terminate within the timeout.
    """
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write(program)
        path = f.name
    try:
        proc = subprocess.run(
            [binary, path], capture_output=True, input=stdin, timeout=5
        )
        out = proc.stdout.replace(b"\nInput: ", b"").replace(b"Input: ", b"")
        return out, proc.returncode
    except subprocess.TimeoutExpired:
        return None
    finally:
        Path(path).unlink()


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

    failures = 0
    for program, stdin in FORTH_CORPUS:
        native = _run_forth_native(binary, program, stdin)
        if native is None:
            print(f"Forþ {program!r}: Rust reference did not terminate")
            failures += 1
            continue
        py = _run_forth_python(program, stdin)
        if native != py:
            failures += 1
            print(f"Forþ {program!r}: Rust {native!r} vs Python {py!r}")

    if not failures:
        print(f"Forþ differential: {len(FORTH_CORPUS)} programs match")
    return failures == 0


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
        _BF_U + "a->2\na->0 += 65;\nwrite <- a->0 ;\na->1 += 66;" "\nwrite <- a->1 ;",
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
    """Run ``program`` through the Rust cross-check; return (stdout, exit code).

    The reference prints its ``Input: `` prompts and error messages to
    stdout, which are stripped before comparing.
    """
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write(program)
        path = f.name
    try:
        proc = subprocess.run(
            [binary, path], capture_output=True, input=stdin, timeout=5
        )
        out = proc.stdout.replace(b"\nInput: ", b"").replace(b"Input: ", b"")
        for message in _CPP_ERRORS:
            out = out.replace((message + "\n").encode(), b"")
        return out, proc.returncode
    except subprocess.TimeoutExpired:
        return None
    finally:
        Path(path).unlink()


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

    failures = 0
    for program, stdin in BASICFUCK_CORPUS:
        native = _run_basicfuck_native(binary, program, stdin)
        if native is None:
            print(f"Basicfuck {program.splitlines()[-1]!r}: Rust did not terminate")
            failures += 1
            continue
        py = _run_basicfuck_python(program, stdin)
        if native != py:
            failures += 1
            print(
                f"Basicfuck {program.splitlines()[-1]!r}: "
                f"Rust {native!r} vs Python {py!r}"
            )

    if not failures:
        print(f"Basicfuck differential: {len(BASICFUCK_CORPUS)} programs match")
    return failures == 0


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
    """Run ``program`` through the Rust cross-check; return (stdout, exit code).

    The reference prints its ``Input: `` prompts to stdout, which are
    stripped; invalid operations exit with status 3.
    """
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write(program)
        path = f.name
    try:
        proc = subprocess.run(
            [binary, path], capture_output=True, input=stdin, timeout=5
        )
        out = proc.stdout.replace(b"\nInput: ", b"").replace(b"Input: ", b"")
        return out, proc.returncode
    except subprocess.TimeoutExpired:
        return None
    finally:
        Path(path).unlink()


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

    failures = 0
    for program, stdin in UNSQUARE_CORPUS:
        native = _run_unsquare_native(str(UNSQUARE_BIN), program, stdin)
        if native is None:
            print(f"Unsquare {program!r}: Rust reference did not terminate")
            failures += 1
            continue
        py = _run_unsquare_python(program, stdin)
        if native != py:
            failures += 1
            print(f"Unsquare {program!r}: Rust {native!r} vs Python {py!r}")

    if not failures:
        print(f"Unsquare differential: {len(UNSQUARE_CORPUS)} programs match")
    return failures == 0


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
    """Run ``program`` through the Rust cross-check; return (stdout, exit code).

    The reference prints its ``Input: `` prompts to stdout, which are
    stripped; invalid operations exit with status 3.
    """
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write(program)
        path = f.name
    try:
        proc = subprocess.run(
            [str(THREE_X_BIN), path],
            capture_output=True,
            input=stdin,
            timeout=5,
        )
        out = proc.stdout.replace(b"Input: ", b"")
        return out, proc.returncode
    except subprocess.TimeoutExpired:
        return None
    finally:
        Path(path).unlink()


def _run_three_x_python(program: str, stdin: bytes) -> tuple[bytes, int]:
    """Run ``program`` through the in-package interpreter."""
    from esolangs.exceptions import HaltError
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.other.three_x import run

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

    failures = 0
    for program, stdin in THREE_X_CORPUS:
        native = _run_three_x_native(program, stdin)
        if native is None:
            print(f"3x {program!r}: Rust reference did not terminate")
            failures += 1
            continue
        py = _run_three_x_python(program, stdin)
        if native != py:
            failures += 1
            print(f"3x {program!r}: Rust {native!r} vs Python {py!r}")

    if not failures:
        print(f"3x differential: {len(THREE_X_CORPUS)} programs match")
    return failures == 0


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
    if not PCT_BIN.exists():
        print("[skip] %^2^-1 differential: Rust reference not built")
        return None
    return str(PCT_BIN)


def _run_pct_native(
    binary: str, program: str, stdin: bytes
) -> tuple[bytes, int] | None:
    """Run ``program`` through the Rust cross-check; return (stdout, exit code)."""
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write(program)
        path = f.name
    try:
        proc = subprocess.run(
            [binary, path], capture_output=True, input=stdin, timeout=5
        )
        out = proc.stdout.replace(b"\nInput: ", b"").replace(b"Input: ", b"")
        return out, proc.returncode
    except subprocess.TimeoutExpired:
        return None
    finally:
        Path(path).unlink()


def _run_pct_python(program: str, stdin: bytes) -> tuple[bytes, int]:
    """Run ``program`` through the in-package interpreter."""
    import importlib

    from esolangs.interpreters.io import ScriptedIO

    run = importlib.import_module("esolangs.interpreters.register_based.%^2^-1").run

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

    failures = 0
    for program, stdin in PCT_CORPUS:
        native = _run_pct_native(binary, program, stdin)
        if native is None:
            print(f"%^2^-1 {program!r}: Rust reference did not terminate")
            failures += 1
            continue
        py = _run_pct_python(program, stdin)
        if native != py:
            failures += 1
            print(f"%^2^-1 {program!r}: Rust {native!r} vs Python {py!r}")

    if not failures:
        print(f"%^2^-1 differential: {len(PCT_CORPUS)} programs match")
    return failures == 0


def _fuzz_pct(rng: random.Random, count: int) -> bool:
    """Differentially fuzz %^2^-1 with random byte text.

    The language has no boolean generator, so the text generator's programs
    are fuzzed instead: they are built per byte and always terminate, unlike
    a hand-written ``t`` loop.
    """
    from esolangs.tools.generate import pct_squared_minus_one

    binary = _build_pct()
    if binary is None:
        return True

    failures, checked = _fuzz_text(
        "%^2^-1",
        pct_squared_minus_one,
        lambda program, stdin: _run_pct_native(binary, program, stdin),
        _run_pct_python,
        rng,
        count,
    )
    print(
        f"%^2^-1 fuzz: {checked} programs match"
        if not failures
        else f"%^2^-1 fuzz: {failures} failures of {checked}"
    )
    return failures == 0


# -- 2dFish corpus: every command plus the error categories ---------------

TWO_D_FISH_CORPUS = [
    ("/%o%o@", b"1\n"),  # second read hits EOF: exit 3
    ("/i@", b""),
    ("/ii@", b""),
    ("/d@", b""),
    ("/s@", b""),
    ("/iio@", b""),
    ("/ia@", b""),
    ("/i*a@", b""),
    ("/i(abc)*@", b""),
    ("/i(abc)@", b""),
    ("/i(ab)a@", b""),  # a in string mode prints one captured character
    ("v\ni\n@\n", b""),
    ("v\nii\no\n@\n", b""),
    ("^", b""),
    ("\\", b""),
    ("/i@\n", b""),  # trailing newline phantom-row quirk
    ("/$*@", b"hi\n"),
    ("/%o@", b"42\n"),
    ("/@", b""),
    ("", b""),  # no initial direction
]


def _build_two_d_fish() -> str | None:
    """Return the built 2dFish Rust reference; None if cargo built it not yet."""
    if not TWO_D_FISH_BIN.exists():
        print("[skip] 2dFish differential: Rust reference not built")
        return None
    return str(TWO_D_FISH_BIN)


def _run_two_d_fish_native(
    binary: str, program: str, stdin: bytes
) -> tuple[bytes, int] | None:
    """Run ``program`` through the Rust cross-check; return (stdout, exit code)."""
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write(program)
        path = f.name
    try:
        proc = subprocess.run(
            [binary, path], capture_output=True, input=stdin, timeout=5
        )
        out = proc.stdout.replace(b"\nInput: ", b"").replace(b"Input: ", b"")
        return out, proc.returncode
    except subprocess.TimeoutExpired:
        return None
    finally:
        Path(path).unlink()


def _run_two_d_fish_python(program: str, stdin: bytes) -> tuple[bytes, int]:
    """Run ``program`` through the in-package interpreter."""
    import importlib

    from esolangs.exceptions import HaltError
    from esolangs.interpreters.io import ScriptedIO

    run = importlib.import_module("esolangs.interpreters.other.2dfish").run

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


def _verify_two_d_fish() -> bool:
    """Compare the Python 2dFish interpreter against the Rust cross-check."""
    binary = _build_two_d_fish()
    if binary is None:
        return True

    failures = 0
    for program, stdin in TWO_D_FISH_CORPUS:
        native = _run_two_d_fish_native(binary, program, stdin)
        if native is None:
            print(f"2dFish {program!r}: Rust reference did not terminate")
            failures += 1
            continue
        py = _run_two_d_fish_python(program, stdin)
        if native != py:
            failures += 1
            print(f"2dFish {program!r}: Rust {native!r} vs Python {py!r}")

    if not failures:
        print(f"2dFish differential: {len(TWO_D_FISH_CORPUS)} programs match")
    return failures == 0


def _fuzz_two_d_fish(rng: random.Random, count: int) -> bool:
    """Differentially fuzz 2dFish with random byte text.

    The language has no boolean generator, so the text generator's programs
    are fuzzed instead.
    """
    from esolangs.tools.generate import two_d_fish

    binary = _build_two_d_fish()
    if binary is None:
        return True

    failures, checked = _fuzz_text(
        "2dFish",
        two_d_fish,
        lambda program, stdin: _run_two_d_fish_native(binary, program, stdin),
        _run_two_d_fish_python,
        rng,
        count,
    )
    print(
        f"2dFish fuzz: {checked} programs match"
        if not failures
        else f"2dFish fuzz: {failures} failures of {checked}"
    )
    return failures == 0


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
    """Run ``program`` through the Rust cross-check; return (stdout, exit code)."""
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write(program)
        path = f.name
    try:
        proc = subprocess.run(
            [binary, path], capture_output=True, input=stdin, timeout=5
        )
        out = proc.stdout.replace(b"\nInput: ", b"").replace(b"Input: ", b"")
        return out, proc.returncode
    except subprocess.TimeoutExpired:
        return None
    finally:
        Path(path).unlink()


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

    failures = 0
    for targets, stdin in _PAIN_CORPUS:
        program = _painfuck_encode(targets)
        native = _run_painfuck_native(binary, program, stdin)
        if native is None:
            print(f"Painfuck {targets!r}: Rust reference did not terminate")
            failures += 1
            continue
        py = _run_painfuck_python(program, stdin)
        if native != py:
            failures += 1
            print(f"Painfuck {targets!r}: Rust {native!r} vs Python {py!r}")

    if not failures:
        print(f"Painfuck differential: {len(_PAIN_CORPUS)} programs match")
    return failures == 0


def _fuzz_painfuck(rng: random.Random, count: int) -> bool:
    """Differentially fuzz Painfuck with random byte text.

    The language has no boolean generator, so the text generator's programs
    (which avoid the nondeterministic `y`) are fuzzed instead.
    """
    from esolangs.tools.generate import painfuck

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

# Unmatched brackets raise in both sides (the former Ruby reference hung).
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
    """Run ``program`` through the Rust cross-check; return (stdout, exit code).

    The reference prints its ``Input: `` prompts to stdout, which are
    stripped; invalid operations exit with status 3.
    """
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write(program)
        path = f.name
    try:
        proc = subprocess.run(
            [str(BIT_TILDE_BIN), path],
            capture_output=True,
            input=stdin,
            timeout=5,
        )
        out = proc.stdout.replace(b"\nInput: ", b"").replace(b"Input: ", b"")
        return out, proc.returncode
    except subprocess.TimeoutExpired:
        return None
    finally:
        Path(path).unlink()


def _run_bit_tilde_python(program: str, stdin: bytes) -> tuple[bytes, int]:
    """Run ``program`` through the in-package interpreter."""
    import importlib

    from esolangs.exceptions import HaltError
    from esolangs.interpreters.io import ScriptedIO

    run = importlib.import_module("esolangs.interpreters.other.bit_tilde").run

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

    failures = 0
    for program, stdin in BIT_TILDE_CORPUS:
        native = _run_bit_tilde_native(program, stdin)
        if native is None:
            print(f"bit~ {program!r}: Rust reference did not terminate")
            failures += 1
            continue
        py = _run_bit_tilde_python(program, stdin)
        if native != py:
            failures += 1
            print(f"bit~ {program!r}: Rust {native!r} vs Python {py!r}")

    if not failures:
        print(f"bit~ differential: {len(BIT_TILDE_CORPUS)} programs match")
    return failures == 0


def _fuzz_bit_tilde(rng: random.Random, count: int) -> bool:
    """Differentially fuzz bit~ with random byte text.

    The language has no boolean generator, so the text generator's programs
    are fuzzed instead.
    """
    from esolangs.tools.generate import bit_tilde

    if not BIT_TILDE_BIN.exists():
        print("[skip] bit~ fuzz: Rust reference not built")
        return True

    failures, checked = _fuzz_text(
        "bit~",
        bit_tilde,
        _run_bit_tilde_native,
        _run_bit_tilde_python,
        rng,
        count,
    )
    print(
        f"bit~ fuzz: {checked} programs match"
        if not failures
        else f"bit~ fuzz: {failures} failures of {checked}"
    )
    return failures == 0


# -- The generator-less extra/ interpreters (corpus only) -------------------
#
# Kak, Trash, BF-PDA, Number Seventy-Four, 2 Bits 1 Byte, Brainpocalypse,
# and Stun Step have no generators (narrow output classes), so only the
# fixed corpora are checked; Albabet has a text generator and is fuzzed.

_LEAN_BINARIES = {
    "Albabet": ALBABET_BIN,
    "BF-PDA": BFPDA_BIN,
}


def _build_kak() -> str | None:
    """Return the built Kak Rust reference; None if cargo built it not yet."""
    if not KAK_BIN.exists():
        print("[skip] Kak differential: Rust reference not built")
        return None
    return str(KAK_BIN)


def _build_trash() -> str | None:
    """Return the built Trash Rust reference; None if cargo built it not yet."""
    if not TRASH_BIN.exists():
        print("[skip] Trash differential: Rust reference not built")
        return None
    return str(TRASH_BIN)


def _run_file_ref(
    cmd: list[str], program: str, stdin: bytes = b""
) -> tuple[bytes, int] | None:
    """Run ``program`` (written to a temp file) through a file-based reference."""
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write(program)
        path = f.name
    try:
        proc = subprocess.run([*cmd, path], capture_output=True, input=stdin, timeout=5)
        return proc.stdout, proc.returncode
    except subprocess.TimeoutExpired:
        return None
    finally:
        Path(path).unlink()


def _build_riscv(name: str) -> bytes | None:
    """Assemble the RISC-V port ``extra/assembly/{name}-riscv.s``.

    Returns None if the cross-compiler is missing.
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


def _asm_refs_ready(riscv_name: str) -> bool:
    """Whether the RISC-V reference can be built."""
    return _build_riscv(riscv_name) is not None


def _inprocess_run(
    module: str, program: str, stdin: bytes = b"", encoding: str = "latin1"
) -> bytes | None:
    """Run ``program`` through the in-package interpreter, returning bytes.

    Returns None if the interpreter does not terminate within the timeout.
    """
    import importlib
    import signal

    from esolangs.interpreters.io import ScriptedIO

    run = importlib.import_module(module).run
    io = ScriptedIO(stdin.decode("latin1"))

    class _TimeoutError(Exception):
        pass

    def _alarm(_signum: int, _frame: object) -> None:
        raise _TimeoutError

    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(3)
    try:
        run(program, io)
        return io.getvalue().encode(encoding)
    except Exception:
        return None
    finally:
        signal.alarm(0)


# (name, ready(), native(program, stdin), Python module, corpus)
_SIMPLE_CORPUS = [
    # Kak: one-bit tape; the Rust prints the tape plus a newline
    (
        "Kak",
        lambda: _build_kak() is not None,
        lambda p, s: _run_file_ref([_build_kak()], p, s),
        "esolangs.interpreters.tape_based.kak",
        [("<!", b""), ("!<!", b""), ("<!!<", b""), ("", b"")],
    ),
    # Trash: number program; the Rust prints via println (trailing newline)
    (
        "Trash",
        lambda: _build_trash() is not None,
        lambda p, s: _run_file_ref([_build_trash()], p, s),
        "esolangs.interpreters.other.trash",
        [("t2", b""), ("t5", b""), ("5", b""), ("0", b""), ("tt3", b""), ("1", b"")],
    ),
    # Number Seventy-Four: Rust reference (a faithful pass-boundary port of
    # the former Ruby cross-check; the Lean port has diverged semantics)
    (
        "Number Seventy-Four",
        lambda: SEVENTY_FOUR_BIN.exists(),
        lambda p, s: _run_file_ref([str(SEVENTY_FOUR_BIN)], p, s),
        "esolangs.interpreters.other.seventy_four",
        [("0H", b""), ("1H0H", b""), ("101H0H", b""), ("0", b""), ("1", b"")],
    ),
    # 2 Bits, 1 Byte: single program byte, read from stdin by the references
    (
        "2 Bits, 1 Byte",
        lambda: _asm_refs_ready("2b1b"),
        lambda p, _s: _asm_refs("2b1b", p),
        "esolangs.interpreters.other.two_bits_one_byte",
        [("\xff", b""), ("\x3f", b""), ("\x00", b""), ("A", b"")],
    ),
    # Brainpocalypse: program read from stdin by the references
    (
        "Brainpocalypse",
        lambda: _asm_refs_ready("brainpocalypse"),
        lambda p, _s: _asm_refs("brainpocalypse", p),
        "esolangs.interpreters.tape_based.brainpocalypse",
        [
            ("+", b""),
            ("++-", b""),
            (">+<-", b""),
            ("-", b""),
            ("", b""),
            (">" * 256 + "+>", b""),  # the pointer wraps past cell 255
        ],
    ),
    # Stun Step: program read from stdin by the references
    (
        "Stun Step",
        lambda: _asm_refs_ready("stun-step"),
        lambda p, _s: _asm_refs("stun-step", p),
        "esolangs.interpreters.tape_based.stun_step",
        [("-", b""), ("->", b""), ("<", b""), (">-", b""), (">", b"")],
    ),
]


def _verify_simple_corpus() -> bool:
    """Differentially check the generator-less extra/ interpreters."""
    failures = 0
    for name, ready, native, module, corpus in _SIMPLE_CORPUS:
        if not ready():
            print(f"[skip] {name} differential: reference toolchain not available")
            continue
        checked = 0
        for program, stdin in corpus:
            ref = native(program, stdin)
            py = _inprocess_run(module, program, stdin)
            if ref is None and py is None:
                continue  # both loop forever: consistent
            if ref is None or py is None:
                failures += 1
                print(
                    f"{name} {program!r}: termination mismatch "
                    f"(reference {'loops' if ref is None else 'halts'}, "
                    f"Python {'loops' if py is None else 'halts'})"
                )
                continue
            ref_out = ref[0].rstrip(b"\n")
            checked += 1
            if ref_out != py.rstrip(b"\n") or ref[1] != 0:
                failures += 1
                print(f"{name} {program!r}: ref={(ref_out, ref[1])!r} py={py!r}")
        if checked:
            print(f"{name} differential: {checked} programs match")
    return failures == 0


def _verify_lean(name: str, binary: Path, module: str, corpus: list[str]) -> bool:
    """Differentially check a Lean-referenced interpreter."""
    failures = 0
    if not binary.exists():
        print(f"[skip] {name} differential: Lean binary not built")
        return True
    checked = 0
    for program in corpus:
        ref = _run_file_ref([str(binary)], program)
        if ref is None:
            print(f"{name} {program!r}: reference did not terminate")
            failures += 1
            continue
        py = _inprocess_run(module, program)
        checked += 1
        if py is None:
            # the interpreter raised (an invalid operation): the reference
            # must also exit with status 3
            if ref[1] != 3:
                failures += 1
                print(f"{name} {program!r}: ref={ref!r} py=error")
        elif ref != (py, 0):
            failures += 1
            print(f"{name} {program!r}: ref={ref!r} py={(py, 0)!r}")
    if checked:
        print(f"{name} differential: {checked} programs match")
    return failures == 0


_ALBABET_CORPUS = [
    "i",
    "ai",
    "aai",
    "ciai",
    "g",
    "h",
    "bai",
    "dai",
    "e",
    "f",
]
_BFPDA_CORPUS = [
    "<@.",
    "<<@.",
    "<<<@<@>.",
    "<@[@].",
    "<@<@[@]@>.",
    "<@[@][@].",
    "<@[<@>].",
    "<@<@>.",
    # empty-stack operations: both implementations exit 3
    "@",
    ".",
    ">",
    "[",
    "]",
]


def _fuzz_albabet(rng: random.Random, count: int) -> bool:
    """Fuzz the AlbaBet text generator against the Lean reference."""
    from esolangs.tools.generate import albabet

    if not ALBABET_BIN.exists():
        print("[skip] AlbaBet fuzz: Lean binary not built")
        return True

    tasks = []
    for _ in range(count):
        text = "".join(chr(rng.randrange(256)) for _ in range(rng.randint(1, 10)))
        tasks.append((albabet(text), text))
    results = _run_parallel(lambda t: _run_file_ref([str(ALBABET_BIN)], t[0]), tasks)
    failures = checked = 0
    for (program, text), result in zip(tasks, results, strict=True):
        if result is None:
            print(f"AlbaBet {text!r}: reference did not terminate")
            failures += 1
            checked += 1
            continue
        py = _inprocess_run(
            "esolangs.interpreters.other.albabet", program, encoding="utf-8"
        )
        checked += 1
        if result != (py, 0):
            failures += 1
            print(f"AlbaBet {text!r}: ref={result!r} py={(py, 0)!r}")
    print(
        f"AlbaBet fuzz: {checked} programs match"
        if not failures
        else f"AlbaBet fuzz: {failures} failures of {checked}"
    )
    return failures == 0


def _verify_remaining_extras() -> bool:
    """Differentially check the newly ported extra/ interpreters."""
    ok = _verify_simple_corpus()
    ok = (
        _verify_lean(
            "Albabet",
            ALBABET_BIN,
            "esolangs.interpreters.other.albabet",
            _ALBABET_CORPUS,
        )
        and ok
    )
    return (
        _verify_lean(
            "BF-PDA", BFPDA_BIN, "esolangs.interpreters.tape_based.bfpda", _BFPDA_CORPUS
        )
        and ok
    )


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
    ok = _verify_forth() and ok
    ok = _verify_basicfuck() and ok
    ok = _verify_unsquare() and ok
    ok = _verify_three_x() and ok
    ok = _verify_pct() and ok
    ok = _verify_two_d_fish() and ok
    ok = _verify_painfuck() and ok
    ok = _verify_bit_tilde() and ok
    ok = _verify_remaining_extras() and ok
    if args.fuzz:
        rng = random.Random(args.seed)
        ok = _fuzz_nocomment(rng, args.fuzz) and ok
        ok = _fuzz_forth(rng, args.fuzz) and ok
        ok = _fuzz_basicfuck(rng, args.fuzz) and ok
        ok = _fuzz_unsquare(rng, args.fuzz) and ok
        ok = _fuzz_three_x(rng, args.fuzz) and ok
        ok = _fuzz_pct(rng, args.fuzz) and ok
        ok = _fuzz_two_d_fish(rng, args.fuzz) and ok
        ok = _fuzz_painfuck(rng, args.fuzz) and ok
        ok = _fuzz_bit_tilde(rng, args.fuzz) and ok
        ok = _fuzz_albabet(rng, args.fuzz) and ok
        # LaserFuck fuzz is far slower per iteration (each truth table needs
        # 12 Rust runs per input combination), so it gets a tenth of the
        # budget.
        ok = _fuzz_laserfuck(rng, max(1, args.fuzz // 10)) and ok
    print("differential corpus: all ok" if ok else "differential corpus: FAILURES")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
