# NoComment interpreter (RISC-V Linux port; see README "Extra Implementations").
#
# The full wiki language: a byte tape with a movable pointer, plus a byte
# stack.  `i`/`d` increment/decrement the current cell (mod 256), `c` clears
# it, `l`/`r` move the pointer (a static 4096-byte tape whose pointer wraps
# at both ends), `n` pushes the current cell, `f` pops into it, `s`/`b` jump
# forward/backward by the top-of-stack amount when the current cell is
# nonzero (`s` skips X instructions, `b` jumps back X-1), and `o` prints
# the current cell as a byte.  Any other character is a malformed program.
#
# Exit codes follow the cross-check convention: 0 = success, 2 = malformed
# program (unrecognized command), 3 = invalid runtime operation (stack
# underflow or a jump out of range).  The program is read from stdin.
#
# Build: riscv64-elf-gcc -nostdlib -static -march=rv64i -mabi=lp64 -o nocomment-riscv nocomment-riscv.s
#        (or riscv64-linux-gnu-gcc, as in CI)
# Run:   qemu-riscv64 ./nocomment-riscv < program
#
# Registers:
#   s3 = first program byte address (program[i] lives at s3 - i)
#   s4 = instruction index (ind)
#   s5 = program length (n)
#   s6 = tape pointer
#   s7 = stack top index
#
# Syscalls: read = 63, write = 64, exit = 93.

    .text
    .global _start

_start:
    addi s3, sp, -5         # first program byte address
    li   s4, 0              # ind
    li   s5, 0              # n
    li   s6, 0              # ptr
    li   s7, 0              # stack top
    mv   s2, s3             # read pointer

# Read the program from stdin into memory (downward), one byte at a time.
.read:
    li   a7, 63
    li   a0, 0
    mv   a1, s2
    li   a2, 1
    ecall
    addi s2, s2, -1
    li   t0, 1
    blt  a0, t0, .read_done # read returned < 1 (EOF)
    addi s5, s5, 1          # n += 1
    j    .read
.read_done:
    sb   zero, 0(s2)        # NUL below the program

.parse:
    bge  s4, s5, .done      # ind >= n: the program ended
    sub  t0, s3, s4
    lbu  t1, 0(t0)          # t1 = program[ind]
    li   t0, 'i'
    beq  t1, t0, .up
    li   t0, 'd'
    beq  t1, t0, .down
    li   t0, 'c'
    beq  t1, t0, .zero
    li   t0, 'l'
    beq  t1, t0, .left
    li   t0, 'r'
    beq  t1, t0, .right
    li   t0, 'n'
    beq  t1, t0, .on
    li   t0, 'f'
    beq  t1, t0, .off
    li   t0, 's'
    beq  t1, t0, .fore
    li   t0, 'b'
    beq  t1, t0, .back
    li   t0, 'o'
    beq  t1, t0, .output
    # unrecognized command: malformed, exit 2
    li   a0, 2
    li   a7, 93
    ecall

.done:
    li   a0, 0
    li   a7, 93
    ecall

.err3:
    li   a0, 3
    li   a7, 93
    ecall

.up:
    la   t0, tape
    add  t0, t0, s6
    lbu  t1, 0(t0)
    addi t1, t1, 1
    andi t1, t1, 0xFF
    sb   t1, 0(t0)
    j    .next

.down:
    la   t0, tape
    add  t0, t0, s6
    lbu  t1, 0(t0)
    addi t1, t1, -1
    andi t1, t1, 0xFF
    sb   t1, 0(t0)
    j    .next

.zero:
    la   t0, tape
    add  t0, t0, s6
    sb   zero, 0(t0)
    j    .next

.left:
    addi s6, s6, -1
    bge  s6, zero, 1f
    li   s6, 4095           # pointer overflow wraps to the opposite end
1:
    j    .next

.right:
    addi s6, s6, 1
    li   t0, 4096
    blt  s6, t0, 1f
    li   s6, 0              # the tape is a fixed 4096-byte zeroed buffer
1:
    j    .next

.on:
    la   t0, tape
    add  t0, t0, s6
    lbu  t1, 0(t0)
    la   t2, stack
    add  t2, t2, s7
    sb   t1, 0(t2)
    addi s7, s7, 1
    j    .next

.off:
    beqz s7, .err3          # stack underflow: exit 3
    addi s7, s7, -1
    la   t2, stack
    add  t2, t2, s7
    lbu  t1, 0(t2)
    la   t0, tape
    add  t0, t0, s6
    sb   t1, 0(t0)
    j    .next

.fore:                      # s: skip X forward
    la   t0, tape
    add  t0, t0, s6
    lbu  t1, 0(t0)
    beqz t1, .next          # cell zero: no jump
    beqz s7, .next          # empty stack: no jump
    addi t2, s7, -1
    la   t3, stack
    add  t3, t3, t2
    lbu  t1, 0(t3)          # X = top of stack
    add  t2, s4, t1
    addi t2, t2, 1          # target = ind + X + 1
    bge  t2, s5, .err3      # target >= n: exit 3
    add  s4, s4, t1         # ind += X (the loop's +1 lands on target)
    j    .next

.back:                      # b: jump back X-1
    la   t0, tape
    add  t0, t0, s6
    lbu  t1, 0(t0)
    beqz t1, .next
    beqz s7, .next
    addi t2, s7, -1
    la   t3, stack
    add  t3, t3, t2
    lbu  t1, 0(t3)          # X = top of stack
    sub  t2, s4, t1
    addi t2, t2, 1          # target = ind - X + 1
    blt  t2, zero, .err3    # target < 0: exit 3
    bge  t2, s5, .err3      # target >= n: exit 3
    sub  s4, s4, t1         # ind -= X
    j    .next

.output:
    la   t0, tape
    add  t0, t0, s6
    lbu  t1, 0(t0)
    la   t2, outbyte
    sb   t1, 0(t2)
    li   a7, 64
    li   a0, 1
    mv   a1, t2
    li   a2, 1
    ecall
    j    .next

.next:
    addi s4, s4, 1
    j    .parse

    .bss
    .align 2
tape:
    .zero 4096
stack:
    .zero 4096
outbyte:
    .zero 1
