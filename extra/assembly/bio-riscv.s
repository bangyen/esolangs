# BIO interpreter (RISC-V Linux port; see README "Extra Implementations").
#
# The full wiki language: three registers x/y/z, each addressed by a 2-char
# opcode plus a register letter.  `0o[xyz]` increments, `1o[xyz]` decrements,
# `1i[xyz]` prints the register's low byte, and `0i[xyz]` is a while-loop
# guard: it pushes the current token index when the register is nonzero
# (entering the loop body) and otherwise skips forward to the matching `}`.
# `}` pops the loop stack and jumps back to just before the guard, so the
# guard re-checks the register; popping an empty stack is an invalid
# runtime operation.  Commands are matched by the regex
# ``([01][oOiI][xXyYzZ]|})`` (case-insensitive), so any other text --
# including `;` separators -- is a comment.  The malformed check is lazy,
# matching the Python interpreter's control flow exactly: a `0i[xyz]`
# guard only scans for its matching `}` when its register is zero (the
# skip path), so an unmatched guard that is always entered never raises,
# and a `}` that halts the program (empty loop stack) can fire before a
# later unmatched guard is ever reached.
#
# Exit codes follow the cross-check convention: 0 = success, 2 = malformed
# program (unmatched loop guard), 3 = invalid runtime operation (`}` with an
# empty loop stack).  The program is read from stdin.
#
# Build: riscv64-elf-gcc -nostdlib -static -march=rv64i -mabi=lp64 -o bio-riscv bio-riscv.s
#        (or riscv64-linux-gnu-gcc, as in CI)
# Run:   qemu-riscv64 ./bio-riscv < program
#
# Registers:
#   s0 = program length (n_bytes; program[i] lives at s3 - i)
#   s3 = first program byte address
#   s4 = byte index (tokenizing) / token index (executing)
#   s5 = token count
#   s6 = token types base (0=0o 1=1o 2=1i 3=0i 4=})
#   s7 = token regs base (0=x 1=y 2=z; unused for type 4)
#   s8/s9/s10 = x/y/z registers
#   s11 = loop stack top index
#
# Resource limits: the token table and loop stack are fixed buffers (4096
# entries each), and the runner caps execution at 10M instructions.  A
# program that pushes either past its buffer faults (folded into "did not
# terminate" by the differential), the same class as RAM0's fixed RAM.
#
# Syscalls: read = 63, write = 64, exit = 93.

    .text
    .global _start

_start:
    addi s3, sp, -5         # first program byte address
    li   s0, 0              # n_bytes
    mv   t0, s3             # read pointer

# Read the program from stdin into memory (downward), one byte at a time.
.read:
    li   a7, 63
    li   a0, 0
    mv   a1, t0
    li   a2, 1
    ecall
    addi t0, t0, -1
    li   t1, 1
    blt  a0, t1, .read_done # read returned < 1 (EOF)
    addi s0, s0, 1          # n_bytes += 1
    j    .read
.read_done:
    sb   zero, 0(t0)        # NUL below the program

# Tokenize into (type, reg) pairs, matching the case-insensitive regex
# ``([01][oOiI][xXyYzZ]|})``: two-char command + register, or a bare `}`.
    la   s6, types
    la   s7, regs
    li   s4, 0              # byte index
    li   s5, 0              # token count
.tokenize:
    bge  s4, s0, .tokenize_done
    sub  t1, s3, s4
    lbu  t2, 0(t1)          # program[s4]
    li   t3, '}'
    bne  t2, t3, .tok_try2
    li   t3, 4              # type }
    add  t4, s6, s5
    sb   t3, 0(t4)
    add  t4, s7, s5
    sb   zero, 0(t4)        # reg unused
    addi s4, s4, 1
    addi s5, s5, 1
    j    .tokenize
.tok_try2:
    addi t5, s4, 1
    bge  t5, s0, .tok_skip  # need two more bytes
    call .lower
    li   t3, '0'
    beq  t2, t3, .tok_dig0
    li   t3, '1'
    beq  t2, t3, .tok_dig1
    j    .tok_skip
.tok_dig0:
    li   t4, 0              # base type for '0' family: 0=0o, 3=0i
    j    .tok_op
.tok_dig1:
    li   t4, 1              # base type for '1' family: 1=1o, 2=1i
.tok_op:
    sub  t1, s3, t5
    lbu  t2, 0(t1)          # program[s4+1]
    call .lower
    li   t3, 'o'
    beq  t2, t3, .tok_o
    li   t3, 'i'
    beq  t2, t3, .tok_i
    j    .tok_skip
.tok_o:
    # '0' -> type 0 (0o), '1' -> type 1 (1o)
    j    .tok_have_type
.tok_i:
    # '0' -> type 3 (0i), '1' -> type 2 (1i)
    li   t3, 3
    sub  t4, t3, t4
.tok_have_type:
    addi t5, s4, 2
    bge  t5, s0, .tok_skip  # need a third byte (the register)
    sub  t1, s3, t5
    lbu  t2, 0(t1)          # program[s4+2]
    call .lower
    li   t3, 'x'
    beq  t2, t3, .tok_regx
    li   t3, 'y'
    beq  t2, t3, .tok_regy
    li   t3, 'z'
    beq  t2, t3, .tok_regz
    j    .tok_skip
.tok_regx:
    li   t6, 0
    j    .tok_emit
.tok_regy:
    li   t6, 1
    j    .tok_emit
.tok_regz:
    li   t6, 2
.tok_emit:
    add  t3, s6, s5
    sb   t4, 0(t3)          # types[count] = type
    add  t3, s7, s5
    sb   t6, 0(t3)          # regs[count] = reg
    addi s4, s4, 3
    addi s5, s5, 1
    j    .tokenize
.tok_skip:
    addi s4, s4, 1
    j    .tokenize
.tokenize_done:

.exec_start:
    li   s8, 0               # x
    li   s9, 0               # y
    li   s10, 0              # z
    li   s11, 0              # loop stack top
    li   s4, 0               # token index

.exec:
    bge  s4, s5, .done       # ind >= count: halted
    add  t0, s6, s4
    lbu  t1, 0(t0)           # type
    add  t0, s7, s4
    lbu  t2, 0(t0)           # reg (0=x,1=y,2=z)
    li   t0, 0
    beq  t1, t0, .cmd_inc
    li   t0, 1
    beq  t1, t0, .cmd_dec
    li   t0, 2
    beq  t1, t0, .cmd_out
    li   t0, 3
    beq  t1, t0, .cmd_open
    j    .cmd_close

.cmd_inc:
    beqz t2, .inc_x
    li   t0, 1
    beq  t2, t0, .inc_y
    addi s10, s10, 1
    j    .next
.inc_x:
    addi s8, s8, 1
    j    .next
.inc_y:
    addi s9, s9, 1
    j    .next

.cmd_dec:
    beqz t2, .dec_x
    li   t0, 1
    beq  t2, t0, .dec_y
    addi s10, s10, -1
    j    .next
.dec_x:
    addi s8, s8, -1
    j    .next
.dec_y:
    addi s9, s9, -1
    j    .next

.cmd_out:
    beqz t2, .out_x
    li   t0, 1
    beq  t2, t0, .out_y
    mv   t0, s10
    j    .out_emit
.out_x:
    mv   t0, s8
    j    .out_emit
.out_y:
    mv   t0, s9
.out_emit:
    andi t0, t0, 0xff
    la   t1, outbyte
    sb   t0, 0(t1)
    li   a7, 64
    li   a0, 1
    mv   a1, t1
    li   a2, 1
    ecall
    j    .next

.cmd_open:
    beqz t2, .open_x
    li   t0, 1
    beq  t2, t0, .open_y
    mv   t0, s10
    j    .open_check
.open_x:
    mv   t0, s8
    j    .open_check
.open_y:
    mv   t0, s9
.open_check:
    beqz t0, .open_skip      # register is zero: skip the loop body
    la   t0, loopstack
    slli t1, s11, 2
    add  t0, t0, t1
    sw   s4, 0(t0)           # push current token index
    addi s11, s11, 1
    j    .next
.open_skip:
    addi s4, s4, 1           # scan forward from ind+1 for the matching }
    li   t0, 1               # depth
.open_scan:
    bge  s4, s5, .err2       # ran off the end with no matching }: malformed
    add  t1, s6, s4
    lbu  t2, 0(t1)
    li   t3, 3
    beq  t2, t3, .open_up
    li   t3, 4
    beq  t2, t3, .open_down
    addi s4, s4, 1
    j    .open_scan
.open_up:
    addi t0, t0, 1
    addi s4, s4, 1
    j    .open_scan
.open_down:
    addi t0, t0, -1
    addi s4, s4, 1
    bnez t0, .open_scan
    j    .exec                # ind is just after the matching }

.cmd_close:
    beqz s11, .err3           # empty loop stack: invalid runtime op
    addi s11, s11, -1
    la   t0, loopstack
    slli t1, s11, 2
    add  t0, t0, t1
    lw   s4, 0(t0)            # ind = popped index - 1 (the guard re-runs)
    addi s4, s4, -1
    j    .next

.next:
    addi s4, s4, 1
    j    .exec

.done:
    li   a0, 0
    li   a7, 93
    ecall

.err2:
    li   a0, 2
    li   a7, 93
    ecall

.err3:
    li   a0, 3
    li   a7, 93
    ecall

# Lowercase the byte in t2 (ASCII 'A'-'Z' -> 'a'-'z'), used by the tokenizer.
.lower:
    li   t3, 'A'
    blt  t2, t3, .lower_ret
    li   t3, 'Z'
    bgt  t2, t3, .lower_ret
    ori  t2, t2, 0x20
.lower_ret:
    ret

    .bss
    .align 2
types:      .zero 4096
regs:       .zero 4096
loopstack:  .zero 16384   # 4096 * 4 bytes
outbyte:    .zero 1
