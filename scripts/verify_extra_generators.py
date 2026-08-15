"""Verify the generator-only languages against their extra/ references.

Every generator with a native reference now round-trips through Rust:
Forþ, Basicfuck, 2dFish, Painfuck, LaserFuck, Unsquare, %^2^-1, bit~, and
3x all have references in ``extra/rust``.  This script builds whatever
references it can (cargo for Rust) and round-trips each language's
generator: a generated program must reproduce its text when run through the
reference implementation.  Dimensional moved to its in-package v3.0
interpreter (``esolangs.interpreters.tape_based.dimensional``) and is
verified by unit tests instead.

It is called from CI's ``rust`` job and from ``verify.py`` locally.
References whose toolchain is missing are skipped, not failed.

Usage:
    PYTHONPATH=src python scripts/verify_extra_generators.py

Requires: cargo (for the Rust references).
"""

import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from esolangs.tools import boolean
from esolangs.tools import generate as gen
from esolangs.tools.booleans import other as other_bools

ROOT = Path(__file__).parents[1]
RUST_MANIFEST = ROOT / "extra" / "rust" / "Cargo.toml"
RUST_BIN_DIR = ROOT / "extra" / "rust" / "target" / "debug"

TEXTS = ("Hi", "Hello, World!", "esolangs!")

# The round-trips and truth-table checks each spawn a reference subprocess,
# so threads (which just wait on the subprocess) scale well.
_WORKERS = 8


def _run_parallel(fn: Callable[..., bytes | None], tasks: Sequence) -> list:
    """Run ``fn`` over ``tasks`` concurrently, returning results in order."""
    with ThreadPoolExecutor(max_workers=_WORKERS) as executor:
        return list(executor.map(fn, tasks))


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


def _build_rust() -> bool:
    """Build the Rust references, reporting whether they are runnable."""
    if shutil.which("cargo") is None:
        return False
    rv = subprocess.run(
        ["cargo", "build", "--manifest-path", str(RUST_MANIFEST)],
        capture_output=True,
    )
    return rv.returncode == 0


def main() -> int:
    """Verify the extra generators round-trip, reporting failures."""
    failures = 0

    rust_bins = (
        "laserfuck",
        "unsquare",
        "pct_squared_minus_one",
        "bit_tilde",
        "forth",
        "basicfuck",
        "two_d_fish",
        "painfuck",
        "three_x",
    )
    rust = dict.fromkeys(rust_bins)
    if _build_rust():
        rust = {name: [str(RUST_BIN_DIR / name)] for name in rust_bins}

    references: list[tuple[str, Callable[[str], str], list[str] | None]] = [
        ("Forþ", gen.forth, rust["forth"]),
        ("Basicfuck", gen.basicfuck, rust["basicfuck"]),
        ("2dFish", gen.two_d_fish, rust["two_d_fish"]),
        ("Painfuck", gen.painfuck, rust["painfuck"]),
        ("LaserFuck", gen.laserfuck, rust["laserfuck"]),
        ("Unsquare", gen.unsquare, rust["unsquare"]),
        ("%^2^-1", gen.pct_squared_minus_one, rust["pct_squared_minus_one"]),
        ("bit~", gen.bit_tilde, rust["bit_tilde"]),
        ("3x", gen.three_x, rust["three_x"]),
    ]

    text_tasks = []
    for name, generator, cmd in references:
        if cmd is None:
            print(f"[skip] {name}: reference toolchain not available or build failed")
            continue
        for text in TEXTS:
            text_tasks.append((name, cmd, generator(text), text))
    for (name, _cmd, _program, text), out in zip(
        text_tasks,
        _run_parallel(lambda t: _run(t[1], t[2]), text_tasks),
        strict=True,
    ):
        ok = out == text.encode()
        failures += not ok
        print(f"{name}: {'ok' if ok else 'FAIL'} -> {out!r}")

    # Boolean generators: 3x computes truth tables via a variable decision
    # tree (Rust), Forþ via a function-dispatch tree (Rust), Basicfuck via an
    # if/if-not decision tree (Rust), and Unsquare via an accumulator decision
    # tree (Rust).  Dimensional and Container are verified against their
    # in-package interpreters instead.
    boolean_refs: list[tuple[str, Callable[[str, int], str], list[str] | None]] = [
        ("3x", boolean.three_x, rust["three_x"]),
        ("Forþ", boolean.forth, rust["forth"]),
        ("Basicfuck", boolean.basicfuck, rust["basicfuck"]),
        ("Unsquare", boolean.unsquare, rust["unsquare"]),
    ]
    tables = {
        1: ("00", "01", "10", "11"),
        2: ("0001", "0110", "1110"),
        3: ("00000001", "11111110"),
        4: ("1111111100000000", "0000000011111111"),
    }
    bool_tasks = []
    for name, builder, cmd in boolean_refs:
        if cmd is None:
            print(f"[skip] {name} boolean: reference toolchain not available")
            continue
        for n, group in tables.items():
            for table in group:
                program = builder(table, n)
                for combo in range(2**n):
                    bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                    inputs = "\n".join(map(str, bits)) + "\n"
                    bool_tasks.append(
                        (name, cmd, program, inputs, table, n, bits, combo)
                    )
    for (name, _cmd, _program, _inputs, table, n, bits, combo), out in zip(
        bool_tasks,
        _run_parallel(lambda t: _run_boolean(t[1], t[2], t[3]), bool_tasks),
        strict=True,
    ):
        ok = out == table[combo].encode()
        failures += not ok
        if not ok:
            print(f"{name} boolean {table!r} n={n} combo {bits}: FAIL -> {out!r}")
    for name, _, _ in boolean_refs:
        print(f"{name} boolean: verified tables for n = 1..4")

    # 3x constants: the closed-form _const must push its value on a clean
    # stack for a wide range of n (the tables above only reach names <= 6).
    three_x_cmd = rust["three_x"]
    if three_x_cmd is not None:
        const_programs = [
            other_bools._const(n) + "!"  # noqa: SLF001 - boolean-constant helper
            for n in range(256)
        ]
        for n, out in zip(
            range(256),
            _run_parallel(lambda prog: _run(three_x_cmd, prog), const_programs),
            strict=True,
        ):
            ok = out.decode().strip() == str(n)
            failures += not ok
            if not ok:
                print(f"3x const {n}: FAIL -> {out!r}")
        print("3x const: verified closed-form encodings for n = 0..255")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
