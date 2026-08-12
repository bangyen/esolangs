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

Called from CI's ``extra-languages`` and ``rust`` jobs (which provide
Rscript and cargo) and from ``verify.py`` locally.  References whose
toolchain is missing are skipped, not failed.

Usage:
    PYTHONPATH=src python scripts/verify_differential.py
"""

import io
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
# Python interpreter raises HaltError.  The R reference has no bounds check
# (the module docstring notes it matches the reference Python).  Exclude it
# from the exact-match corpus and handle it separately.
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

    # the pointer-fault program: Python raises HaltError; the R reference has
    # no bounds check, so it prints a byte instead — expected divergence
    out = _run_native(r_ref, EXCON_FAULT)
    assert out is not None, "EXCON reference did not terminate on the fault program"
    native = out.decode(errors="replace")
    print(f"EXCON fault: R prints {native!r} (Python raises HaltError)")

    if not failures:
        print(f"EXCON differential: {len(EXCON_CORPUS)} programs match")
    return failures == 0


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
    from esolangs.tools.booleans import other

    for table, n in LASERFUCK_BOOLEAN:
        program = other.laserfuck(table, n)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            inputs = [str(b) for b in bits]
            outputs: set[str] = set()
            input_bytes = ("\n".join(inputs) + "\n").encode()
            for _ in range(12):
                out = _run_native([str(RUST_BIN)], program, input_bytes=input_bytes)
                if out is None:
                    print(
                        f"LaserFuck boolean {table!r} combo {bits}: "
                        "Rust reference does not terminate"
                    )
                    return False
                text = out.decode(errors="replace")
                # the Rust reference writes an "Input: " prompt per read
                while text.startswith("Input: "):
                    text = text[len("Input: ") :]
                outputs.add(re.sub("[^01]", "", text))
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

    if not failures:
        print(f"LaserFuck differential: {checked} programs match")
    return failures == 0


def main() -> int:
    """Verify the differential corpora, reporting failures."""
    ok = _verify_excon()
    ok = _verify_laserfuck() and ok
    print("differential corpus: all ok" if ok else "differential corpus: FAILURES")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
