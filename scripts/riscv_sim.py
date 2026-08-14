"""Minimal RISC-V RV64 simulator for the 123 interpreter.

Decodes the standard instruction encodings for the small subset used by
extra/assembly/123-riscv.s and emulates its memory + Linux syscalls, so the
port can be verified without qemu-user.
"""

import struct

MEM = bytearray(2 * 1024 * 1024)
SP = 1000000  # stack pointer base


def sign_extend(val: int, bits: int) -> int:
    """Sign-extend a ``bits``-wide value to a Python int."""
    sign = 1 << (bits - 1)
    return (val & (sign - 1)) - (val & sign)


def disassemble_and_run(binary: bytes, stdin: bytes) -> bytes:
    """Disassemble and run the ELF in ``binary``, returning its output."""
    # find the .text section and entry point from the ELF
    entry = struct.unpack_from("<Q", binary, 0x18)[0]
    text_off = text_addr = text_size = 0
    e_shoff = struct.unpack_from("<Q", binary, 0x28)[0]
    e_shnum = struct.unpack_from("<H", binary, 0x3C)[0]
    e_shentsize = struct.unpack_from("<H", binary, 0x3A)[0]
    for i in range(e_shnum):
        off = e_shoff + i * e_shentsize
        sh_type = struct.unpack_from("<I", binary, off + 4)[0]
        if sh_type == 1:  # SHT_PROGBITS
            sh_addr = struct.unpack_from("<Q", binary, off + 0x10)[0]
            sh_offset = struct.unpack_from("<Q", binary, off + 0x18)[0]
            sh_size = struct.unpack_from("<Q", binary, off + 0x20)[0]
            text_off, text_addr, text_size = sh_offset, sh_addr, sh_size
    mem = MEM
    for i in range(text_size):
        mem[text_addr + i] = binary[text_off + i]

    # registers (x0..x31)
    reg = [0] * 32
    reg[2] = SP  # sp
    pc = entry
    inp = bytearray(stdin)
    inp_pos = 0
    out = bytearray()

    def load(pc: int) -> int:
        return int(struct.unpack_from("<I", mem, pc)[0])

    steps = 0
    while steps < 5000000:
        steps += 1
        ins = load(pc)
        opcode = ins & 0x7F
        rd = (ins >> 7) & 0x1F
        funct3 = (ins >> 12) & 0x7
        rs1 = (ins >> 15) & 0x1F
        rs2 = (ins >> 20) & 0x1F
        if opcode == 0x37:  # lui
            if rd:
                reg[rd] = (ins >> 12) << 12
            pc += 4
        elif opcode == 0x17:  # auipc
            if rd:
                reg[rd] = pc + ((ins >> 12) << 12)
            pc += 4
        elif opcode == 0x13:  # OP-IMM: addi / slli / srli
            if funct3 == 0x1:  # slli
                if rd:
                    reg[rd] = reg[rs1] << ((ins >> 20) & 0x1F)
            elif funct3 == 0x5:  # srli / srai
                if rd:
                    reg[rd] = reg[rs1] >> ((ins >> 20) & 0x1F)
            elif funct3 == 0x6:  # ori
                imm = sign_extend(ins >> 20, 12)
                if rd:
                    reg[rd] = reg[rs1] | imm
            elif funct3 == 0x7:  # andi
                imm = sign_extend(ins >> 20, 12)
                if rd:
                    reg[rd] = reg[rs1] & imm
            else:  # addi
                imm = sign_extend(ins >> 20, 12)
                if rd:
                    reg[rd] = reg[rs1] + imm
            pc += 4
        elif opcode == 0x33:  # R-type
            funct7 = ins >> 25
            imm = (ins >> 20) & 0x1F
            value = 0
            if funct3 == 0 and funct7 == 0:
                value = reg[rs1] + reg[rs2]
            elif funct3 == 0 and funct7 == 0x20:
                value = reg[rs1] - reg[rs2]
            elif funct3 == 0x4:
                value = reg[rs1] ^ reg[rs2]
            elif funct3 == 0x6:
                value = reg[rs1] | reg[rs2]
            elif funct3 == 0x7:
                value = reg[rs1] & reg[rs2]
            elif funct3 == 0x1:
                value = reg[rs1] << imm
            elif funct3 == 0x5 and funct7 == 0:
                value = reg[rs1] >> imm
            elif funct3 == 0x5 and funct7 == 0x20:
                value = reg[rs1] >> imm  # srai (logical, fine here)
            if rd:
                reg[rd] = value
            pc += 4
        elif opcode == 0x03:  # loads: lb / lbu / lw / ld (funct3 0 / 4 / 2 / 3)
            imm = sign_extend(ins >> 20, 12)
            addr = reg[rs1] + imm
            if rd:
                if funct3 == 0:  # lb (sign-extended byte)
                    value = mem[addr]
                    reg[rd] = value - 0x100 if value & 0x80 else value
                elif funct3 == 4:  # lbu
                    reg[rd] = mem[addr]
                elif funct3 == 2:  # lw (sign-extended word)
                    value = int(struct.unpack_from("<i", mem, addr)[0])
                    reg[rd] = value
                elif funct3 == 3:  # ld
                    reg[rd] = int(struct.unpack_from("<q", mem, addr)[0])
            pc += 4
        elif opcode == 0x23:  # stores: sb / sw / sd (funct3 0 / 2 / 3)
            imm = sign_extend((ins >> 25 << 5) | ((ins >> 7) & 0x1F), 12)
            addr = reg[rs1] + imm
            if funct3 == 0:  # sb
                mem[addr] = reg[rs2] & 0xFF
            elif funct3 == 2:  # sw
                struct.pack_into("<I", mem, addr, reg[rs2] & 0xFFFFFFFF)
            elif funct3 == 3:  # sd
                struct.pack_into("<q", mem, addr, reg[rs2])
            pc += 4
        elif opcode == 0x67:  # jalr (ret uses rd = x0)
            imm = sign_extend(ins >> 20, 12)
            target = (reg[rs1] + imm) & ~1
            if rd:
                reg[rd] = pc + 4
            pc = target
        elif opcode == 0x63:  # branches
            imm = (
                ((ins >> 31) & 1) << 12
                | ((ins >> 7) & 1) << 11
                | ((ins >> 25) & 0x3F) << 5
                | ((ins >> 8) & 0xF) << 1
            )
            imm = sign_extend(imm, 13)
            a, b = reg[rs1], reg[rs2]
            ua, ub = a & 0xFFFFFFFFFFFFFFFF, b & 0xFFFFFFFFFFFFFFFF
            taken = {
                0x0: a == b,
                0x1: a != b,
                0x4: a < b,
                0x5: a >= b,
                0x6: ua < ub,
                0x7: ua >= ub,
            }.get(funct3, False)
            pc += imm if taken else 4
        elif opcode == 0x6F:  # jal (j pseudo uses x0)
            imm = (
                ((ins >> 31) & 1) << 20
                | ((ins >> 12) & 0xFF) << 12
                | ((ins >> 20) & 1) << 11
                | ((ins >> 21) & 0x3FF) << 1
            )
            imm = sign_extend(imm, 21)
            if rd:
                reg[rd] = pc + 4
            pc += imm
        elif opcode == 0x73:  # ecall
            a7 = reg[17]
            if a7 == 63:  # read
                n = min(reg[12], len(inp) - inp_pos)
                n = max(n, 0)
                if n:
                    mem[reg[11] : reg[11] + n] = inp[inp_pos : inp_pos + n]
                    inp_pos += n
                reg[10] = n
            elif a7 == 64:  # write
                n = reg[12]
                out += mem[reg[11] : reg[11] + n]
                reg[10] = n
            elif a7 == 93:  # exit
                break
            pc += 4
        else:
            raise ValueError(f"unsupported opcode 0x{opcode:x} at pc {pc:#x}")
    return bytes(out)


if __name__ == "__main__":
    import sys

    from esolangs.tools.generate import _123

    with open(sys.argv[1], "rb") as f:
        binary = f.read()
    text = sys.argv[2]
    program = _123(text)
    out = disassemble_and_run(binary, program.encode())
    print(
        f"input {text!r} -> output {out!r} {'ok' if out == text.encode() else 'FAIL'}"
    )
