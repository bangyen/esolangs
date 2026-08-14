# Brainpocalypse interpreter (RISC-V Linux port; see README "Extra
# Implementations").
#
# A brainfuck-like tape language (256 cells, wrapping): `+`/`-` increment/
# decrement the current cell, `>`/`<` move the pointer (wrapping past the
# ends), and `-` on a zero cell rewinds the instruction pointer to the start
# of the program (the wiki's flow-control rule).  Cells hold nonnegative
# integers (unbounded, so they never wrap), and every other character is a
# comment.  The program is read from stdin; when it ends, the whole tape
# from cell 0 through the rightmost cell reached is printed as
# space-separated decimal values (an output decision, not a language rule).
#
# Build: riscv64-elf-gcc -nostdlib -static -march=rv64i -mabi=lp64 -o brainpocalypse-riscv brainpocalypse-riscv.s
#        (or riscv64-linux-gnu-gcc, as in CI)
# Run:   qemu-riscv64 ./brainpocalypse-riscv < program
#
# Registers:
#   s2 = program buffer pointer (grows down as the program is read)
#   s3 = parse pointer
#   s4 = tape pointer index (0..255)
#   s5 = rightmost cell reached
#
# Syscalls: read = 63, write = 64, exit = 93.

    .text
    .global _start

_start:
    addi s2, sp, -16          # program buffer starts below the stack top
    li   s4, 0                # tape pointer index
    li   s5, 0                # rightmost cell reached

# Read the program from stdin into memory (downward), one byte at a time.
.read:
    li   a7, 63
    li   a0, 0
    mv   a1, s2
    li   a2, 1
    ecall
    addi s2, s2, -1
    li   t0, 1
    blt  a0, t0, .read_done   # read returned < 1 (EOF)
    j    .read
.read_done:
    sb   zero, 0(s2)          # NUL below the program (the end marker)
    addi s3, sp, -15          # parse from the first program byte

.parse:
    addi s3, s3, -1
    lbu  t1, 0(s3)
    li   t0, '+'
    beq  t1, t0, .plus
    li   t0, '-'
    beq  t1, t0, .minus
    li   t0, '>'
    beq  t1, t0, .right
    li   t0, '<'
    beq  t1, t0, .left
    bnez t1, .parse           # anything else is a comment

# Program ended: print cells 0..right as space-separated decimals.
    li   s4, 0
.state:
    la   t0, tape
    slli t1, s4, 2
    add  t0, t0, t1
    lw   a0, 0(t0)
    call output
    beq  s4, s5, .final
    call print_space
    addi s4, s4, 1
    j    .state
.final:
    li   a0, 0
    li   a7, 93
    ecall

.plus:
    la   t0, tape
    slli t1, s4, 2
    add  t0, t0, t1
    lw   t2, 0(t0)
    addi t2, t2, 1
    sw   t2, 0(t0)
    j    .parse

.minus:
    la   t0, tape
    slli t1, s4, 2
    add  t0, t0, t1
    lw   t2, 0(t0)
    bnez t2, .minus_dec
    addi s3, sp, -15          # cell is zero: rewind to the start
    j    .parse
.minus_dec:
    addi t2, t2, -1
    sw   t2, 0(t0)
    j    .parse

.right:
    addi s4, s4, 1
    li   t0, 256
    bne  s4, t0, .right_keep
    li   s4, 0                # wrap past cell 255
    j    .parse
.right_keep:
    blt  s5, s4, .right_set
    j    .parse
.right_set:
    mv   s5, s4
    j    .parse

.left:
    bnez s4, .left_keep
    li   s4, 255              # wrap before cell 0
    j    .parse
.left_keep:
    addi s4, s4, -1
    j    .parse

# Divide a0 by a1: quotient in a0, remainder in a1 (repeated subtraction;
# rv64i has no div instruction).
divmod:
    li   t0, 0
.div_loop:
    bltu a0, a1, .div_done
    sub  a0, a0, a1
    addi t0, t0, 1
    j    .div_loop
.div_done:
    mv   a1, a0
    mv   a0, t0
    ret

# Print the decimal representation of a0 (no leading zeros).
output:
    addi sp, sp, -48
    sd   ra, 24(sp)           # save area is sp+24..47, above the digit buffer
    sd   s0, 32(sp)
    sd   s1, 40(sp)
    addi s0, sp, 24           # digit buffer end (grows down below the saves)
    li   s1, 0                # digit count
.out_digits:
    li   a1, 10
    call divmod               # a0 = a0/10, a1 = a0%10
    addi s0, s0, -1
    addi t2, a1, 48           # '0'
    sb   t2, 0(s0)
    addi s1, s1, 1
    bnez a0, .out_digits
    li   a7, 64
    li   a0, 1
    mv   a1, s0
    mv   a2, s1
    ecall
    ld   ra, 24(sp)
    ld   s0, 32(sp)
    ld   s1, 40(sp)
    addi sp, sp, 48
    ret

print_space:
    addi sp, sp, -16
    sd   ra, 8(sp)
    li   t0, ' '
    sb   t0, 0(sp)
    li   a7, 64
    li   a0, 1
    mv   a1, sp
    li   a2, 1
    ecall
    ld   ra, 8(sp)
    addi sp, sp, 16
    ret

    .bss
    .align 2
tape:
    .zero 1024                # 256 dwords
