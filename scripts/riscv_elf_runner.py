"""Run RISC-V RV64 Linux ELFs under unicorn (an independent CPU emulator).

unicorn is a mature, independent CPU-emulation engine, so this runner
executes the interpreter ports without needing a Linux VM or qemu. It
targets the statically-linked, nostdlib RV64 ELFs the esolangs interpreter
ports produce (see extra/assembly/), implementing the small set of Linux
syscalls they use. It is not a full Linux ABI.

Assembled ELFs are cached on disk under ``$XDG_CACHE_HOME`` (see
``assemble_source``); set ``ESOLANGS_NO_ELF_CACHE`` to compile every time.

API:
    run_elf(binary, stdin=b"") -> (stdout: bytes, exit_code: int)

CLI:
    python riscv_elf_runner.py <elf> < input > output
    (exits with the emulated program's exit code)

Requires: pip install unicorn
"""

import functools
import hashlib
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    from unicorn import UC_ARCH_RISCV, UC_HOOK_INTR, UC_MODE_RISCV64, Uc
    from unicorn.riscv_const import (
        UC_RISCV_REG_A0,
        UC_RISCV_REG_A1,
        UC_RISCV_REG_A2,
        UC_RISCV_REG_A7,
        UC_RISCV_REG_PC,
        UC_RISCV_REG_SP,
    )
except ImportError:
    raise SystemExit("unicorn is not installed; run: pip install unicorn") from None

PAGE = 0x1000

# RISC-V Linux syscall numbers (small subset)
SYS_READ = 63
SYS_WRITE = 64
SYS_OPENAT = 56
SYS_CLOSE = 57
SYS_BRK = 214
SYS_EXIT = 93
SYS_EXIT_GROUP = 94

STACK_TOP = 0x800000
HEAP_BASE = 0x100000
HEAP_SIZE = 0x1000000
STACK_SIZE = 0x2000


CROSS_COMPILERS = ("riscv64-linux-gnu-gcc", "riscv64-elf-gcc")


def _cache_dir() -> Path:
    """Where assembled ELFs are kept between runs."""
    root = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(root) / "esolangs" / "riscv-elf"


@functools.lru_cache(maxsize=1)
def _toolchain_id() -> str:
    """Identify the assembler, so an upgrade cannot be served from cache.

    Keying on the compiler's *output* alone would leave the assembler
    unguarded: the one thing a content key cannot notice is gcc itself
    changing under a byte-identical input.
    """
    for cc in CROSS_COMPILERS:
        if shutil.which(cc):
            rv = subprocess.run([cc, "--version"], capture_output=True, text=True)
            return f"{cc}\0{rv.stdout.splitlines()[0] if rv.stdout else ''}"
    return "none"


def _compile(assembly: str) -> bytes:
    """Compile *assembly* into a statically-linked ELF, without the cache."""
    fd, tmp = tempfile.mkstemp(suffix=".s")
    os.close(fd)
    try:
        with open(tmp, "w") as f:
            f.write(assembly)
        for cc in CROSS_COMPILERS:
            if not shutil.which(cc):
                continue
            binary = tmp + ".elf"
            rv = subprocess.run(
                [
                    cc,
                    "-nostdlib",
                    "-static",
                    "-march=rv64i",
                    "-mabi=lp64",
                    "-o",
                    binary,
                    tmp,
                ],
                capture_output=True,
            )
            if rv.returncode == 0:
                with open(binary, "rb") as f:
                    return f.read()
        raise SystemExit("no RISC-V cross-compiler (riscv64-linux-gnu-gcc) on PATH")
    finally:
        os.unlink(tmp)


def assemble_source(assembly: str) -> bytes:
    """Compile a RISC-V assembly source string into a statically-linked ELF.

    Assembling dominates this module's cost -- across the 121 compiler cases
    in ``verify_riscv_unicorn.COMPILER_CASES``, gcc is 28.2s of the 31s and
    the emulation is 0.1s -- and the same handful of assembly strings is
    re-assembled on every run.  The result is cached on disk, which takes
    that suite from 31s to 0.08s once warm.

    The key is the assembly text itself plus the toolchain's version, so a
    hit means the very bytes gcc produced for this input.  A codegen change
    changes the text, and so the key: the round-trip these ELFs feed exists
    to catch a compiler that emits working-but-wrong code, and a cache that
    could serve a stale binary would silently retire that check.

    ``ESOLANGS_NO_ELF_CACHE`` bypasses it, and a cache that cannot be read
    or written falls through to compiling -- the cache is an optimisation,
    never a correctness dependency.
    """
    if os.environ.get("ESOLANGS_NO_ELF_CACHE"):
        return _compile(assembly)

    digest = hashlib.sha256(f"{_toolchain_id()}\0{assembly}".encode()).hexdigest()
    path = _cache_dir() / digest
    try:
        return path.read_bytes()
    except OSError:
        pass

    binary = _compile(assembly)
    # Write through a unique temp name and rename: pytest-xdist runs these
    # tests across four workers, and a reader must never see a half-written
    # ELF.  os.replace is atomic within a filesystem, so a racing worker
    # either sees the old entry or the complete new one.
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f"{digest}.{os.getpid()}")
        tmp_path.write_bytes(binary)
        os.replace(tmp_path, path)
    except OSError:
        pass  # unwritable cache: the binary is already correct
    return binary


def _align_down(x: int, a: int) -> int:
    return x & ~(a - 1)


def _align_up(x: int, a: int) -> int:
    return _align_down(x + a - 1, a)


def load_segments(binary: bytes) -> tuple[int, list[tuple[int, bytearray]]]:
    """Return (entry, [(vaddr, data), ...]) from the ELF's PT_LOAD headers."""
    if binary[:4] != b"\x7fELF" or binary[4] != 2:  # 64-bit little-endian
        raise ValueError("expected a 64-bit ELF")
    entry = struct.unpack_from("<Q", binary, 0x18)[0]
    e_phoff = struct.unpack_from("<Q", binary, 0x20)[0]
    e_phentsize = struct.unpack_from("<H", binary, 0x36)[0]
    e_phnum = struct.unpack_from("<H", binary, 0x38)[0]
    segments = []
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type = struct.unpack_from("<I", binary, off)[0]
        if p_type != 1:  # PT_LOAD
            continue
        p_offset = struct.unpack_from("<Q", binary, off + 0x08)[0]
        p_vaddr = struct.unpack_from("<Q", binary, off + 0x10)[0]
        p_filesz = struct.unpack_from("<Q", binary, off + 0x20)[0]
        p_memsz = struct.unpack_from("<Q", binary, off + 0x28)[0]
        data = bytearray(binary[p_offset : p_offset + p_filesz])
        data += bytearray(p_memsz - len(data))
        segments.append((p_vaddr, data))
    return entry, segments


def run_elf(binary: bytes, stdin: bytes = b"") -> tuple[bytes, int]:
    """Run a RISC-V ELF and return ``(stdout, exit_code)``."""
    entry, segments = load_segments(binary)
    lo = _align_down(min(v for v, _ in segments), PAGE)
    hi = _align_up(max(v + len(d) for v, d in segments), PAGE)
    heap_base = max(HEAP_BASE, hi + 0x10000)
    stack_top = max(STACK_TOP, heap_base + HEAP_SIZE + STACK_SIZE)

    mu = Uc(UC_ARCH_RISCV, UC_MODE_RISCV64)
    mu.mem_map(lo, hi - lo)
    for vaddr, data in segments:
        mu.mem_write(vaddr, bytes(data))
    mu.mem_map(heap_base, HEAP_SIZE)
    mu.mem_map(_align_down(stack_top - STACK_SIZE, PAGE), STACK_SIZE)
    sp = stack_top - 0x10  # room for argc = 0 and a NULL argv terminator
    mu.mem_write(sp, b"\0" * 16)
    mu.reg_write(UC_RISCV_REG_SP, sp)
    mu.reg_write(UC_RISCV_REG_PC, entry)

    inp = bytearray(stdin)
    inp_pos = 0
    out = bytearray()
    exit_code = [0]
    halted = [False]
    heap_cur = [heap_base]

    def on_ecall(uc: Uc, _intno: int, _user_data: Any) -> None:
        nonlocal inp_pos, out
        a7 = uc.reg_read(UC_RISCV_REG_A7)
        if a7 == SYS_READ:
            if uc.reg_read(UC_RISCV_REG_A0) == 0:
                n = min(uc.reg_read(UC_RISCV_REG_A2), len(inp) - inp_pos)
                n = max(n, 0)
                if n:
                    uc.mem_write(
                        uc.reg_read(UC_RISCV_REG_A1), bytes(inp[inp_pos : inp_pos + n])
                    )
                    inp_pos += n
            else:
                n = 0
            uc.reg_write(UC_RISCV_REG_A0, n)
        elif a7 == SYS_WRITE:
            n = uc.reg_read(UC_RISCV_REG_A2)
            if uc.reg_read(UC_RISCV_REG_A0) in (1, 2):
                out += uc.mem_read(uc.reg_read(UC_RISCV_REG_A1), n)
            uc.reg_write(UC_RISCV_REG_A0, n)
        elif a7 in (SYS_EXIT, SYS_EXIT_GROUP):
            exit_code[0] = uc.reg_read(UC_RISCV_REG_A0)
            halted[0] = True
            uc.emu_stop()
        elif a7 == SYS_CLOSE:
            uc.reg_write(UC_RISCV_REG_A0, 0)
        elif a7 == SYS_BRK:
            addr = uc.reg_read(UC_RISCV_REG_A0)
            if addr == 0:
                uc.reg_write(UC_RISCV_REG_A0, heap_cur[0])
            else:
                heap_cur[0] = addr
                uc.reg_write(UC_RISCV_REG_A0, addr)
        elif a7 == SYS_OPENAT:
            uc.reg_write(UC_RISCV_REG_A0, -2)  # ENOENT: no filesystem
        # unicorn advances the pc past the ecall before calling this hook

    mu.hook_add(UC_HOOK_INTR, on_ecall)
    mu.emu_start(entry, until=0, count=10000000)
    if not halted[0]:
        raise ValueError("program did not halt")
    return bytes(out), exit_code[0]


def main(argv: list[str]) -> int:
    """Run the ELF in ``argv[1]`` and print its exit code."""
    with open(argv[1], "rb") as f:
        binary = f.read()
    out, code = run_elf(binary, sys.stdin.buffer.read())
    sys.stdout.buffer.write(out)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
