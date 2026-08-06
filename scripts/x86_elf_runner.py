"""Run x86-32 Linux assembly programs under unicorn (an independent emulator).

Assembles the reference interpreters in extra/assembly/ with nasm and runs
the machine code under unicorn, hooking the classic Linux `int 0x80` syscalls
(read/write/exit) they use. This verifies the actual x86 reference
implementations execute, cross-checking the RISC-V ports and the Python
simulators.

API:
    assemble(path) -> object bytes  (nasm -f elf32)
    run_elf(binary, stdin=b"") -> (stdout: bytes, exit_code: int)

CLI:
    python x86_elf_runner.py <asm-or-elf32> < input > output
    (exits with the emulated program's exit code)

Requires: pip install unicorn; nasm on PATH.
"""

import os
import struct
import subprocess
import sys
import tempfile

try:
    from unicorn import UC_ARCH_X86, UC_HOOK_INTR, UC_MODE_32, Uc
    from unicorn.x86_const import (
        UC_X86_REG_EAX,
        UC_X86_REG_EBX,
        UC_X86_REG_ECX,
        UC_X86_REG_EDX,
        UC_X86_REG_EIP,
        UC_X86_REG_ESP,
    )
except ImportError:
    raise SystemExit("unicorn is not installed; run: pip install unicorn") from None

PAGE = 0x1000

# Classic Linux x86 syscall numbers (the only ones the interpreters use)
SYS_READ = 3
SYS_WRITE = 4
SYS_EXIT = 1

CODE_BASE = 0x10000
STACK_TOP = 0x800000
STACK_SIZE = 0x2000


def assemble(path):
    fd, tmp = tempfile.mkstemp(suffix=".o")
    os.close(fd)
    try:
        subprocess.run(["nasm", "-f", "elf32", "-o", tmp, path], check=True)
        with open(tmp, "rb") as f:
            return f.read()
    finally:
        os.unlink(tmp)


def assemble_source(assembly):
    """Assemble a nasm source string directly, returning the ELF32 object."""
    fd, tmp = tempfile.mkstemp(suffix=".asm")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(assembly)
        return assemble(tmp)
    finally:
        os.unlink(tmp)


def load_text(binary):
    """Return the SHT_PROGBITS (.text) section from a 32-bit ELF object."""
    if binary[:4] != b"\x7fELF" or binary[4] != 1:  # ELFCLASS32
        raise ValueError("expected a 32-bit ELF object")
    e_shoff = struct.unpack_from("<I", binary, 0x20)[0]
    e_shentsize = struct.unpack_from("<H", binary, 0x2E)[0]
    e_shnum = struct.unpack_from("<H", binary, 0x30)[0]
    for i in range(e_shnum):
        off = e_shoff + i * e_shentsize
        if struct.unpack_from("<I", binary, off + 4)[0] == 1:  # SHT_PROGBITS
            sh_offset = struct.unpack_from("<I", binary, off + 16)[0]
            sh_size = struct.unpack_from("<I", binary, off + 20)[0]
            return binary[sh_offset : sh_offset + sh_size]
    raise ValueError("no .text section found")


def run_elf(binary, stdin=b""):
    text = load_text(binary)
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(CODE_BASE, PAGE)
    mu.mem_write(CODE_BASE, text)
    stack_base = (STACK_TOP - STACK_SIZE) & ~(PAGE - 1)
    mu.mem_map(stack_base, STACK_SIZE)
    esp = STACK_TOP - 0x10
    mu.mem_write(esp, b"\0" * 16)
    mu.reg_write(UC_X86_REG_ESP, esp)
    mu.reg_write(UC_X86_REG_EIP, CODE_BASE)

    inp = bytearray(stdin)
    inp_pos = 0
    out = bytearray()
    exit_code = [0]
    halted = [False]

    def on_int(uc, intno, user_data):
        nonlocal inp_pos, out
        if intno != 0x80:
            return
        syscall = uc.reg_read(UC_X86_REG_EAX)
        if syscall == SYS_READ:
            if uc.reg_read(UC_X86_REG_EBX) == 0:
                n = min(uc.reg_read(UC_X86_REG_EDX), len(inp) - inp_pos)
                n = max(n, 0)
                if n:
                    uc.mem_write(
                        uc.reg_read(UC_X86_REG_ECX), bytes(inp[inp_pos : inp_pos + n])
                    )
                    inp_pos += n
            else:
                n = 0
            uc.reg_write(UC_X86_REG_EAX, n)
        elif syscall == SYS_WRITE:
            n = uc.reg_read(UC_X86_REG_EDX)
            if uc.reg_read(UC_X86_REG_EBX) in (1, 2):
                out += uc.mem_read(uc.reg_read(UC_X86_REG_ECX), n)
            uc.reg_write(UC_X86_REG_EAX, n)
        elif syscall == SYS_EXIT:
            exit_code[0] = uc.reg_read(UC_X86_REG_EBX)
            halted[0] = True
            uc.emu_stop()
        # unicorn advances eip past the int instruction before calling the hook

    mu.hook_add(UC_HOOK_INTR, on_int)
    mu.emu_start(CODE_BASE, until=0, count=10000000)
    if not halted[0]:
        raise ValueError("program did not halt")
    return bytes(out), exit_code[0]


def main(argv):
    with open(argv[1], "rb") as f:
        data = f.read()
    binary = data if data[:4] == b"\x7fELF" else assemble(argv[1])
    out, code = run_elf(binary, sys.stdin.buffer.read())
    sys.stdout.buffer.write(out)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv))
