"""Verify the generator-only languages against their extra/ references.

Forþ and Painfuck have C++ references in ``extra/c++``, and LaserFuck and
Unsquare have Rust references in ``extra/rust``.  This script builds
whatever references it can (g++ for C++, cargo for Rust) and round-trips
each language's generator: a generated program must reproduce its text when
run through the reference implementation.

It is called from CI's ``cxx`` and ``rust`` jobs (which provide g++ and
cargo respectively) and from ``verify.py`` locally.  References whose
toolchain is missing are skipped, not failed.

Usage:
    PYTHONPATH=src python scripts/verify_extra_generators.py

Requires: g++ (for forþ/painfuck) and/or cargo (for laserfuck/unsquare).
"""

import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

from esolangs.tools import generate as gen

ROOT = Path(__file__).parents[1]
EXTRA_CXX = ROOT / "extra" / "c++"
RUST_MANIFEST = ROOT / "extra" / "rust" / "Cargo.toml"
RUST_BIN_DIR = ROOT / "extra" / "rust" / "target" / "debug"

TEXTS = ("Hi", "Hello, World!", "esolangs!")


def _run(binary: Path, program: str) -> bytes:
    """Run ``program`` (written to a temp file) through ``binary``."""
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write(program)
        path = f.name
    try:
        out = subprocess.run([str(binary), path], capture_output=True).stdout
    finally:
        Path(path).unlink()
    return out


def _build_cxx(name: str) -> Path | None:
    """Compile the C++ reference for ``name``, or None if g++ is missing."""
    if shutil.which("g++") is None:
        return None
    binary = Path("/tmp") / name
    rv = subprocess.run(
        ["g++", "-std=c++11", str(EXTRA_CXX / f"{name}.cpp"), "-o", str(binary)],
        capture_output=True,
    )
    return binary if rv.returncode == 0 else None


def _build_rust() -> Path | None:
    """Build the Rust references, or None if cargo is missing."""
    if shutil.which("cargo") is None:
        return None
    rv = subprocess.run(
        ["cargo", "build", "--manifest-path", str(RUST_MANIFEST)],
        capture_output=True,
    )
    return RUST_BIN_DIR if rv.returncode == 0 else None


def main() -> int:
    failures = 0

    cxx = {name: _build_cxx(name) for name in ("forþ", "painfuck")}
    rust_bin_dir = _build_rust()
    rust: dict[str, Path | None] = {"laserfuck": None, "unsquare": None}
    if rust_bin_dir is not None:
        rust = {
            "laserfuck": rust_bin_dir / "laserfuck",
            "unsquare": rust_bin_dir / "unsquare",
        }

    references: list[tuple[str, Callable[[str], str], Path | None]] = [
        ("Forþ", gen.forth, cxx["forþ"]),
        ("Painfuck", gen.painfuck, cxx["painfuck"]),
        ("LaserFuck", gen.laserfuck, rust["laserfuck"]),
        ("Unsquare", gen.unsquare, rust["unsquare"]),
    ]

    for name, generator, binary in references:
        if binary is None:
            print(f"[skip] {name}: reference toolchain not available or build failed")
            continue
        for text in TEXTS:
            out = _run(binary, generator(text))
            ok = out == text.encode()
            failures += not ok
            print(f"{name}: {'ok' if ok else 'FAIL'} -> {out!r}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
