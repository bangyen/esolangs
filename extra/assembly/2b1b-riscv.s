# 2 Bits, 1 Byte interpreter (RISC-V Linux port; see README "Extra
# Implementations").
#
# The program is a single byte whose 8 bits form four 2-bit instructions,
# executed in sequence with the instruction pointer wrapping: 00 = DON (do
# nothing), 01 = ACT (apply a bitwise operation to the byte), 10 = JMP (jump,
# honoring the wrap), and 11 = END (print the byte as a character and halt).
# The byte operated on is the program byte itself, so ACT changes the program
# as it runs.  ACT follows the wiki's disassembly example: two 2-bit operands
# X and Y select a bit pair and an operation (Y <= 1 XORs in the whole pair,
# Y >= 2 XORs in only the pair's high bit).
#
# The program byte is read from stdin.  An empty program halts with no
# output; programs that never reach an END loop forever, exactly as the
# reference does.
#
# Build: riscv64-elf-gcc -nostdlib -static -march=rv64i -mabi=lp64 -o 2b1b-riscv 2b1b-riscv.s
#        (or riscv64-linux-gnu-gcc, as in CI)
# Run:   qemu-riscv64 ./2b1b-riscv < program
#
# Registers:
#   s0 = the program byte being operated on
#   s1 = cl, the field position within the byte (8, 6, 4, 2, wrapping)
#   s2 = bl, the rotating 2-bit mask
#   s3/s4 = saved (cl, bl) for ACT's operand-resume
#
# Syscalls: read = 63, write = 64, exit = 93.

    .text
    .global _start

_start:
    li   a7, 63
    li   a0, 0
    addi a1, sp, -1
    li   a2, 1
    ecall
    beqz a0, .empty        # no byte read: halt with no output
    lbu  s0, -1(sp)        # byte = the first program byte
    li   s1, 8             # cl
    li   s2, 3             # bl = 0b11

.parse:
    call read_field
    beqz a0, .parse        # DON
    li   t0, 1
    beq  a0, t0, .act
    li   t0, 2
    beq  a0, t0, .jmp
    # END: print the byte as a character and halt
    addi sp, sp, -16
    sb   s0, 0(sp)
    li   a7, 64
    li   a0, 1
    mv   a1, sp
    li   a2, 1
    ecall
    li   a0, 0
    li   a7, 93
    ecall

.empty:
    li   a0, 0
    li   a7, 93
    ecall

.act:
    call read_field        # operand field (X)
    mv   s3, s1            # saved cl
    mv   s4, s2            # saved bl
    call seek              # state = seek(X)
    call read_field        # toggle field (Y)
    li   t0, 1
    blt  t0, a0, .act_above  # Y > 1
    xor  s0, s0, s2        # byte ^= bl
    j    .act_done
.act_above:
    slli t0, s2, 1         # (bl << 1) & bl
    and  t0, t0, s2
    andi t0, t0, 0xFF
    xor  s0, s0, t0
.act_done:
    mv   s1, s3            # restore the saved state
    mv   s2, s4
    j    .parse

.jmp:
    call read_field        # operand field (X)
    call seek              # state = seek(X)
    j    .parse

# Read the next 2-bit field: cl = (cl-2) & 7, bl = ror2(bl),
# returns (bl & byte) >> cl in a0.
read_field:
    addi sp, sp, -16
    sd   ra, 8(sp)
    addi s1, s1, -2
    andi s1, s1, 7
    srli t0, s2, 2         # ror2(bl)
    slli t1, s2, 6
    or   t0, t0, t1
    andi s2, t0, 0xFF
    and  t0, s2, s0        # bl & byte
    mv   a0, t0
    call shift_right       # a0 = a0 >> cl (cl is even, 0..8)
    ld   ra, 8(sp)
    addi sp, sp, 16
    ret

# Set the reader state to read ``field`` next: cl = 8 - 2*field,
# bl = (3 << cl) & 0xFF.
seek:
    addi sp, sp, -16
    sd   ra, 8(sp)
    slli t0, a0, 1         # 2*field
    li   t1, 8
    sub  s1, t1, t0        # cl = 8 - 2*field
    li   a0, 3
    call shift_left        # 3 << cl
    andi s2, a0, 0xFF      # bl
    ld   ra, 8(sp)
    addi sp, sp, 16
    ret

# Software variable shift right by s1 (even, 0..8): rv64i has no register
# shift amount, so shift by 2 in s1/2 steps.
shift_right:
    mv   t0, a0
    li   t1, 0
.sr_loop:
    beq  t1, s1, .sr_done
    srli t0, t0, 2
    addi t1, t1, 2
    j    .sr_loop
.sr_done:
    mv   a0, t0
    ret

# Software variable shift left by s1 (even, 0..8).
shift_left:
    mv   t0, a0
    li   t1, 0
.sl_loop:
    beq  t1, s1, .sl_done
    slli t0, t0, 2
    addi t1, t1, 2
    j    .sl_loop
.sl_done:
    mv   a0, t0
    ret
