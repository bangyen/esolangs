# 123 interpreter for RISC-V Linux, ported from the x86 123.asm.
# Build: riscv64-linux-gnu-gcc -static -o 123-riscv 123-riscv.s
# Run:   qemu-riscv64 ./123-riscv < program
#
# Registers:
#   s0 = data register (the byte being built/echoed)
#   s1 = bit position, starting at 128
#   s2 = program pointer
#   s3 = memory pointer (the program is stored just below the stack top)
#
# Syscalls: read = 63, write = 64, exit = 93.

    .text
    .global _start

_start:
    addi s3, sp, -1          # buffer starts one byte below the stack top
    li   s0, 0               # data register
    li   s1, 128             # bit position
    li   s2, 1

# Read the program from stdin into memory (downward), until EOF or '|'.
.input:
    li   a7, 63
    li   a0, 0
    mv   a1, s3
    li   a2, 1
    ecall
    li   t4, 1
    blt  a0, t4, .done       # read returned < 1 (EOF)
    lbu  t5, 0(s3)
    li   t4, '|'
    beq  t5, t4, .done       # read the terminator
    addi s3, s3, -1
    j    .input

.done:
    li   t4, '|'
    sb   t4, 0(s3)           # terminator below the program
    addi s3, s3, -4
    addi s2, sp, 0           # parse from the first program byte

.parse:
    addi s2, s2, -1
    lbu  t5, 0(s2)
    li   t4, '1'
    beq  t5, t4, .left
    li   t4, '2'
    beq  t5, t4, .right
    li   t4, '3'
    beq  t5, t4, .jump
    li   t4, '|'
    bne  t5, t4, .parse      # skip anything else (newlines)
    li   t4, 128
    blt  t4, s1, .final      # esi > 128: halt
    addi s2, sp, 0           # else restart the program
    j    .parse

.left:
    xor  s0, s0, s1          # data ^= bit
    li   t4, 1024
    bge  s1, t4, .left_wrap
    slli s1, s1, 1           # bit <<= 1
    j    .parse
.left_wrap:
    li   s1, 64
    slli s1, s1, 1           # bit wraps to 128
    j    .parse

.right:
    li   t4, 1024
    beq  s1, t4, .read       # at 1024: read a byte
    li   t4, 512
    beq  s1, t4, .write      # at 512: write a byte
    srli s1, s1, 1           # bit >>= 1
    j    .parse

.read:
    li   a7, 63
    li   a0, 0
    mv   a1, s3
    li   a2, 1
    ecall
    lbu  s0, 0(s3)           # data = read byte
    li   s1, 128
    j    .parse

.write:
    sb   s0, 0(s3)           # store data
    li   a7, 64
    li   a0, 1
    mv   a1, s3
    li   a2, 1
    ecall
    li   s1, 128
    j    .parse

.jump:
    li   t4, 128
    bgt  s1, t4, .parse      # esi > 128: no jump
    and  t5, s0, s1
    beqz t5, .false
.true:
    addi s2, s2, 1
    beq  s2, sp, .parse      # walked off the top: restart
    lbu  t5, 0(s2)
    li   t4, '3'
    beq  t5, t4, .parse
    j    .true
.false:
    addi s2, s2, -1
    lbu  t5, 0(s2)
    li   t4, '|'
    bne  t5, t4, .false_scan
    li   t4, 128
    blt  t4, s1, .final      # esi > 128: halt
    addi s2, sp, 0           # else restart the program
    j    .parse
.false_scan:
    li   t4, '3'
    beq  t5, t4, .parse
    j    .false

.final:
    li   a0, 0
    li   a7, 93
    ecall
