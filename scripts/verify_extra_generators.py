"""Verify the generator-only languages against their extra/ references.

Forþ, Painfuck, Dimensional, 2dFish, %^2^-1, and Basicfuck have C++
references in ``extra/c++``, LaserFuck and Unsquare have Rust references in
``extra/rust``, EXCON has an R reference in ``extra/r``, and Unsquare, bit~,
and 3x have Ruby references in ``extra/ruby``.  This script builds whatever
references it can (g++ for C++, cargo for Rust) and round-trips each
language's generator: a generated program must reproduce its text when run
through the reference implementation.

It is called from CI's ``cxx``, ``rust``, and ``extra-languages`` jobs (which
provide g++, cargo, and R/Ruby respectively) and from ``verify.py`` locally.
References whose toolchain is missing are skipped, not failed.

Usage:
    PYTHONPATH=src python scripts/verify_extra_generators.py

Requires: g++ (for the C++ references), cargo (for laserfuck/unsquare),
Rscript (for EXCON), and/or ruby (for unsquare, bit~, and 3x).
"""

import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path

from esolangs.tools import boolean
from esolangs.tools import generate as gen
from esolangs.tools.booleans import other as other_bools

ROOT = Path(__file__).parents[1]
EXTRA_CXX = ROOT / "extra" / "c++"
EXTRA_R = ROOT / "extra" / "r"
EXTRA_RUBY = ROOT / "extra" / "ruby"
RUST_MANIFEST = ROOT / "extra" / "rust" / "Cargo.toml"
RUST_BIN_DIR = ROOT / "extra" / "rust" / "target" / "debug"

TEXTS = ("Hi", "Hello, World!", "esolangs!")


def _run(cmd: Sequence[str], program: str) -> bytes:
    """Run ``program`` (written to a temp file) through ``cmd``."""
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write(program)
        path = f.name
    try:
        out = subprocess.run([*cmd, path], capture_output=True).stdout
    finally:
        Path(path).unlink()
    return out


def _run_boolean(cmd: Sequence[str], program: str, inputs: str) -> bytes:
    """Run ``program`` through ``cmd`` with ``inputs`` on stdin.

    3x prints an ``Input: `` prompt before each read, so the output is
    filtered to the digits the program itself printed.
    """
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write(program)
        path = f.name
    try:
        out = subprocess.run(
            [*cmd, path], input=inputs, capture_output=True, text=True
        ).stdout
    finally:
        Path(path).unlink()
    return "".join(ch for ch in out if ch in "01").encode()


def _build_cxx(name: str) -> list[str] | None:
    """Compile the C++ reference for ``name``, or None if g++ is missing."""
    if shutil.which("g++") is None:
        return None
    binary = Path("/tmp") / f"verify-{name}"
    rv = subprocess.run(
        ["g++", "-std=c++11", str(EXTRA_CXX / f"{name}.cpp"), "-o", str(binary)],
        capture_output=True,
    )
    return [str(binary)] if rv.returncode == 0 else None


def _build_rust() -> bool:
    """Build the Rust references, reporting whether they are runnable."""
    if shutil.which("cargo") is None:
        return False
    rv = subprocess.run(
        ["cargo", "build", "--manifest-path", str(RUST_MANIFEST)],
        capture_output=True,
    )
    return rv.returncode == 0


def _r_reference() -> list[str] | None:
    """Return the R command prefix for EXCON, or None if Rscript is missing."""
    if shutil.which("Rscript") is None:
        return None
    return ["Rscript", str(EXTRA_R / "excon.r")]


def _ruby_reference(name: str) -> list[str] | None:
    """Return the Ruby command prefix for ``name``, or None if ruby is missing."""
    if shutil.which("ruby") is None:
        return None
    return ["ruby", str(EXTRA_RUBY / name)]


def main() -> int:
    """Verify the extra generators round-trip, reporting failures."""
    failures = 0

    cxx_names = ("forþ", "painfuck", "dimensional", "2dFish", "%^2^-1", "basicfuck")
    cxx = {name: _build_cxx(name) for name in cxx_names}
    rust = dict.fromkeys(("laserfuck", "unsquare"))
    if _build_rust():
        rust = {
            "laserfuck": [str(RUST_BIN_DIR / "laserfuck")],
            "unsquare": [str(RUST_BIN_DIR / "unsquare")],
        }

    references: list[tuple[str, Callable[[str], str], list[str] | None]] = [
        ("Forþ", gen.forth, cxx["forþ"]),
        ("Painfuck", gen.painfuck, cxx["painfuck"]),
        ("Dimensional", gen.dimensional, cxx["dimensional"]),
        ("2dFish", gen.two_d_fish, cxx["2dFish"]),
        ("%^2^-1", gen.pct_squared_minus_one, cxx["%^2^-1"]),
        ("Basicfuck", gen.basicfuck, cxx["basicfuck"]),
        ("LaserFuck", gen.laserfuck, rust["laserfuck"]),
        ("Unsquare", gen.unsquare, rust["unsquare"]),
        ("Unsquare", gen.unsquare, _ruby_reference("unsquare.rb")),
        ("bit~", gen.bit_tilde, _ruby_reference("bit.rb")),
        ("3x", gen.three_x, _ruby_reference("3x.rb")),
        ("EXCON", gen.excon, _r_reference()),
    ]

    for name, generator, cmd in references:
        if cmd is None:
            print(f"[skip] {name}: reference toolchain not available or build failed")
            continue
        for text in TEXTS:
            out = _run(cmd, generator(text))
            ok = out == text.encode()
            failures += not ok
            print(f"{name}: {'ok' if ok else 'FAIL'} -> {out!r}")

    # Boolean generators: 3x computes truth tables for n = 1..3 via a
    # variable decision tree, verified against the Ruby reference.
    boolean_refs: list[tuple[str, Callable[[str, int], str], list[str] | None]] = [
        ("3x", boolean.three_x, _ruby_reference("3x.rb")),
    ]
    tables = {
        1: ("00", "01", "10", "11"),
        2: ("0001", "0110", "1110"),
        3: ("00000001", "11111110"),
        4: ("1111111100000000", "0000000011111111"),
    }
    for name, builder, cmd in boolean_refs:
        if cmd is None:
            print(f"[skip] {name} boolean: reference toolchain not available")
            continue
        for n, group in tables.items():
            for table in group:
                program = builder(table, n)
                for combo in range(2**n):
                    bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                    out = _run_boolean(cmd, program, "\n".join(map(str, bits)) + "\n")
                    ok = out == table[combo].encode()
                    failures += not ok
                    if not ok:
                        print(
                            f"{name} boolean {table!r} n={n} combo {bits}: "
                            f"FAIL -> {out!r}"
                        )
        print(f"{name} boolean: verified tables for n = 1..4")

    # 3x constants: the closed-form _const must push its value on a clean
    # stack for a wide range of n (the tables above only reach names <= 6).
    three_x_cmd = _ruby_reference("3x.rb")
    if three_x_cmd is not None:
        for n in range(256):
            program = other_bools._const(n) + "!"  # noqa: SLF001
            with tempfile.NamedTemporaryFile("w", delete=False) as f:
                f.write(program)
                path = f.name
            try:
                got = subprocess.run(
                    [*three_x_cmd, path], capture_output=True
                ).stdout.decode()
            finally:
                Path(path).unlink()
            ok = got.strip() == str(n)
            failures += not ok
            if not ok:
                print(f"3x const {n}: FAIL -> {got!r}")
        print("3x const: verified closed-form encodings for n = 0..255")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
