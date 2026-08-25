# BIO interpreter (RISC-V Linux port; see README "Extra Implementations").
#
# The full wiki language: three registers x/y/z, each addressed by a 2-char
# opcode plus a register letter.  The wiki writes a loop as
# `0i{ do something };` and says every command is ended by a `;`, so
# neither mark is free-standing punctuation -- a command is a triple *with*
# its terminator, and a loop guard is a triple carrying the `{` that opens
# its body:
#
#   `0o[xyz];`  increment          `1o[xyz];`  decrement
#   `1i[xyz];`  print low byte     `0i[xyz]{`  while-loop guard
#   `};`        close the innermost loop
#
# A guard pushes the current token index when its register is nonzero
# (entering the body) and otherwise skips forward to the matching `};`.
# The close pops the loop stack and jumps back to just before the guard, so
# the guard re-checks the register.  Matching is case-insensitive, and `//`
# runs to the end of its line as a comment.
#
# The whole program is checked when it loads: every byte outside a comment
# must belong to a command, and the braces must balance.  So a triple
# missing its `;`, a guard missing its `{`, a `};` with no loop to close,
# and a guard with no close are all rejected eagerly, before any output --
# which is what makes the loop stack impossible to pop empty at run time.
#
# Exit codes follow the cross-check convention: 0 = success, 2 = malformed
# program.  Every rejection is that one category; there is no invalid
# *runtime* operation left to reach.  The program is read from stdin.
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

# Tokenize into (type, reg) pairs.  A command is `[01][oi][xyz]` followed by
# `;` (or `{`, which makes a `0i` guard), or the two bytes `};`.  Whitespace
# separates commands and `//` runs to end of line; anything else is a load
# error, so the scanner rejects where it used to skip.
    la   s6, types
    la   s7, regs
    li   s4, 0              # byte index
    li   s5, 0              # token count
.tokenize:
    bge  s4, s0, .tokenize_done
    sub  t1, s3, s4
    lbu  t2, 0(t1)          # program[s4]
    # whitespace between commands
    li   t3, ' '
    beq  t2, t3, .tok_space
    li   t3, '\t'
    beq  t2, t3, .tok_space
    li   t3, '\n'
    beq  t2, t3, .tok_space
    li   t3, '\r'
    beq  t2, t3, .tok_space
    # `//` comment: run to the end of the line
    li   t3, '/'
    beq  t2, t3, .tok_comment
    li   t3, '}'
    bne  t2, t3, .tok_try2
    # `}` must be followed by its `;`
    addi t5, s4, 1
    bge  t5, s0, .err2
    sub  t1, s3, t5
    lbu  t2, 0(t1)
    li   t3, ';'
    bne  t2, t3, .err2
    li   t3, 4              # type };
    add  t4, s6, s5
    sb   t3, 0(t4)
    add  t4, s7, s5
    sb   zero, 0(t4)        # reg unused
    addi s4, s4, 2
    addi s5, s5, 1
    j    .tokenize
.tok_space:
    addi s4, s4, 1
    j    .tokenize
.tok_comment:
    # need a second '/' to open a comment; a lone '/' is a load error
    addi t5, s4, 1
    bge  t5, s0, .err2
    sub  t1, s3, t5
    lbu  t2, 0(t1)
    li   t3, '/'
    bne  t2, t3, .err2
    addi s4, s4, 2
.tok_comment_scan:
    bge  s4, s0, .tokenize_done
    sub  t1, s3, s4
    lbu  t2, 0(t1)
    li   t3, '\n'
    beq  t2, t3, .tokenize   # the newline itself is whitespace
    addi s4, s4, 1
    j    .tok_comment_scan
.tok_try2:
    addi t5, s4, 1
    bge  t5, s0, .err2      # need two more bytes
    call .lower
    li   t3, '0'
    beq  t2, t3, .tok_dig0
    li   t3, '1'
    beq  t2, t3, .tok_dig1
    j    .err2
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
    j    .err2
.tok_o:
    # '0' -> type 0 (0o), '1' -> type 1 (1o)
    j    .tok_have_type
.tok_i:
    # '0' -> type 3 (0i), '1' -> type 2 (1i)
    li   t3, 3
    sub  t4, t3, t4
.tok_have_type:
    addi t5, s4, 2
    bge  t5, s0, .err2      # need a third byte (the register)
    sub  t1, s3, t5
    lbu  t2, 0(t1)          # program[s4+2]
    call .lower
    li   t3, 'x'
    beq  t2, t3, .tok_regx
    li   t3, 'y'
    beq  t2, t3, .tok_regy
    li   t3, 'z'
    beq  t2, t3, .tok_regz
    j    .err2
.tok_regx:
    li   t6, 0
    j    .tok_emit
.tok_regy:
    li   t6, 1
    j    .tok_emit
.tok_regz:
    li   t6, 2
.tok_emit:
    # The fourth byte is the command's terminator: `{` for a loop guard
    # (type 3), `;` for every other command.  Anything else -- a missing
    # terminator, or a `{` on a non-guard -- is a load error.
    addi t5, s4, 3
    bge  t5, s0, .err2
    sub  t1, s3, t5
    lbu  t2, 0(t1)          # program[s4+3]
    li   t3, 3
    beq  t4, t3, .tok_want_brace
    li   t3, ';'
    bne  t2, t3, .err2
    j    .tok_store
.tok_want_brace:
    li   t3, '{'
    bne  t2, t3, .err2
.tok_store:
    add  t3, s6, s5
    sb   t4, 0(t3)          # types[count] = type
    add  t3, s7, s5
    sb   t6, 0(t3)          # regs[count] = reg
    addi s4, s4, 4
    addi s5, s5, 1
    j    .tokenize
.tokenize_done:

# Balance the braces before executing, so a `};` always has a loop to close
# and a guard always has a close to skip to.
    li   t0, 0              # depth
    li   t1, 0              # token index
.balance:
    bge  t1, s5, .balance_done
    add  t2, s6, t1
    lbu  t3, 0(t2)
    li   t4, 3
    beq  t3, t4, .balance_up
    li   t4, 4
    beq  t3, t4, .balance_down
    j    .balance_next
.balance_up:
    addi t0, t0, 1
    j    .balance_next
.balance_down:
    beqz t0, .err2          # `};` with no loop to close
    addi t0, t0, -1
.balance_next:
    addi t1, t1, 1
    j    .balance
.balance_done:
    bnez t0, .err2          # a guard with no matching `};`

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
    # The balance pass proved a matching `};` exists, so this never runs off
    # the end; the bound is kept as a guard against a corrupt token table.
    bge  s4, s5, .err2
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
    # The balance pass proved every `};` has a loop, so the stack is never
    # empty here; the check is kept as a guard against a corrupt table.
    beqz s11, .err2
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
