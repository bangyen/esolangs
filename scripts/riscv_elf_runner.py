"""Run RISC-V RV64 Linux ELFs under unicorn (an independent CPU emulator).

unicorn is a mature, independent CPU-emulation engine, so this runner
cross-checks the hand-rolled simulator (scripts/riscv_sim.py) without needing
a Linux VM or qemu. It targets the statically-linked, nostdlib RV64 ELFs the
esolangs interpreter ports produce (see extra/assembly/), implementing the
small set of Linux syscalls they use. It is not a full Linux ABI.

API:
    run_elf(binary, stdin=b"") -> (stdout: bytes, exit_code: int)

CLI:
    python riscv_elf_runner.py <elf> < input > output
    (exits with the emulated program's exit code)

Requires: pip install unicorn
"""

import struct
import sys

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


def _align_down(x, a):
    return x & ~(a - 1)


def _align_up(x, a):
    return _align_down(x + a - 1, a)


def load_segments(binary):
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


def run_elf(binary, stdin=b""):
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

    def on_ecall(uc, intno, user_data):
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


def main(argv):
    with open(argv[1], "rb") as f:
        binary = f.read()
    out, code = run_elf(binary, sys.stdin.buffer.read())
    sys.stdout.buffer.write(out)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
