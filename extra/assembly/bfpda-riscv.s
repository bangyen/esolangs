# BF-PDA interpreter (RISC-V Linux port; see README "Extra Implementations").
#
# The full wiki language: a stack of bits whose top is the current cell.
# `@` flips the top bit (auto-pushing a fresh 1 on an empty stack), `.`
# prints the top bit as '0'/'1' (0 on an empty stack), `<` pushes a zero,
# `>` pops the top bit (a no-op on an empty stack), and `[`/`]` are
# brainfuck-style while loops (`[` skips to its matching `]` when the top
# bit is 0, `]` jumps back when it is 1).  Any other character is a comment;
# a run ends when the instruction pointer reaches the end of the program.
#
# Exit codes follow the cross-check convention: 0 = success, 2 = malformed
# program (empty, or unbalanced brackets), 3 = invalid runtime operation
# (unused by BF-PDA).  The program is read from stdin.
#
# Build: riscv64-elf-gcc -nostdlib -static -march=rv64i -mabi=lp64 -o bfpda-riscv bfpda-riscv.s
#        (or riscv64-linux-gnu-gcc, as in CI)
# Run:   qemu-riscv64 ./bfpda-riscv < program
#
# Registers:
#   s3 = first program byte address (program[i] lives at s3 - i)
#   s4 = instruction index (ip)
#   s5 = program length (n)
#   s7 = stack top index (the bit stack, empty when 0)
#
# Syscalls: read = 63, write = 64, exit = 93.

    .text
    .global _start

_start:
    addi s3, sp, -5         # first program byte address
    li   s4, 0              # ip
    li   s5, 0              # n
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

    beqz s5, .err2          # empty program: malformed, exit 2

# Eager bracket validation (the Python interpreter's): a `]` below depth 0,
# or a nonzero depth at the end, is a malformed program (exit 2).
    li   t2, 0              # depth
    li   s4, 0
.validate:
    bge  s4, s5, .validate_done
    sub  t0, s3, s4
    lbu  t1, 0(t0)
    li   t0, '['
    beq  t1, t0, .v_open
    li   t0, ']'
    beq  t1, t0, .v_close
    addi s4, s4, 1
    j    .validate
.v_open:
    addi t2, t2, 1
    addi s4, s4, 1
    j    .validate
.v_close:
    addi t2, t2, -1
    blt  t2, zero, .err2
    addi s4, s4, 1
    j    .validate
.validate_done:
    bnez t2, .err2
    li   s4, 0              # reset ip for the run

.parse:
    bge  s4, s5, .done      # ip >= n: the program ended
    sub  t0, s3, s4
    lbu  t1, 0(t0)          # t1 = program[ip]
    li   t0, '@'
    beq  t1, t0, .flip
    li   t0, '.'
    beq  t1, t0, .output
    li   t0, '<'
    beq  t1, t0, .push0
    li   t0, '>'
    beq  t1, t0, .pop
    li   t0, '['
    beq  t1, t0, .open
    li   t0, ']'
    beq  t1, t0, .close
    j    .next              # any other character is a comment

.done:
    li   a0, 0
    li   a7, 93
    ecall

.err2:
    li   a0, 2
    li   a7, 93
    ecall

.flip:                      # @: flip the top bit
    beqz s7, .flip_empty    # empty stack: auto-push a fresh 1
    la   t0, stack
    addi t1, s7, -1
    add  t0, t0, t1
    lbu  t2, 0(t0)
    xori t2, t2, 1
    sb   t2, 0(t0)
    j    .next
.flip_empty:
    la   t0, stack
    li   t2, 1
    sb   t2, 0(t0)
    li   s7, 1
    j    .next

.push0:                     # <: push a zero
    la   t0, stack
    add  t0, t0, s7
    sb   zero, 0(t0)
    addi s7, s7, 1
    j    .next

.pop:                       # >: pop the top bit (no-op on an empty stack)
    beqz s7, .next
    addi s7, s7, -1
    j    .next

.output:                    # .: print the top bit as '0'/'1' (0 if empty)
    la   t0, stack
    addi t1, s7, -1
    bltz t1, 1f
    add  t0, t0, t1
    lbu  t2, 0(t0)
    j    2f
1:
    li   t2, 0
2:
    addi t2, t2, 48
    la   t0, outbyte
    sb   t2, 0(t0)
    li   a7, 64
    li   a0, 1
    mv   a1, t0
    li   a2, 1
    ecall
    j    .next

.open:                      # [: enter when the top is 1, else skip the body
    la   t0, stack
    addi t1, s7, -1
    bltz t1, .open_skip      # empty stack reads 0 -> skip
    add  t0, t0, t1
    lbu  t2, 0(t0)
    beqz t2, .open_skip
    j    .next              # top 1: enter the loop body
.open_skip:
    addi s4, s4, 1          # scan forward from ip+1
    li   t2, 1              # depth
.open_scan:
    bge  s4, s5, .err2      # defensive: validated programs never run off
    sub  t0, s3, s4
    lbu  t1, 0(t0)
    li   t0, '['
    beq  t1, t0, .open_up
    li   t0, ']'
    beq  t1, t0, .open_down
    addi s4, s4, 1
    j    .open_scan
.open_up:
    addi t2, t2, 1
    addi s4, s4, 1
    j    .open_scan
.open_down:
    addi t2, t2, -1
    addi s4, s4, 1
    bnez t2, .open_scan
    j    .parse             # ip is just after the matching ]

.close:                     # ]: jump back when the top is 1, else continue
    la   t0, stack
    addi t1, s7, -1
    bltz t1, .next          # empty stack reads 0 -> continue
    add  t0, t0, t1
    lbu  t2, 0(t0)
    beqz t2, .next          # top 0 -> continue
    addi s4, s4, -1         # scan backward from ip-1
    li   t2, 1              # depth
.close_scan:
    bltz s4, .err2          # defensive: validated programs never run off
    sub  t0, s3, s4
    lbu  t1, 0(t0)
    li   t0, ']'
    beq  t1, t0, .close_up
    li   t0, '['
    beq  t1, t0, .close_down
    addi s4, s4, -1
    j    .close_scan
.close_up:
    addi t2, t2, 1
    addi s4, s4, -1
    j    .close_scan
.close_down:
    addi t2, t2, -1
    addi s4, s4, -1
    beqz t2, .close_hit
    j    .close_scan
.close_hit:
    addi s4, s4, 1          # ip is just after the matching [
    j    .parse

.next:
    addi s4, s4, 1
    j    .parse

    .bss
    .align 2
stack:
    .zero 4096
outbyte:
    .zero 1
