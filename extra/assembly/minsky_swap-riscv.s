# Minsky Swap interpreter (RISC-V Linux port; see README "Extra
# Implementations").
#
# The full wiki language in compact notation: a first line of `+`/`~`/`*`
# commands over two registers reg[0]/reg[1] addressed by a swappable
# pointer, and a second line of space-separated decimal jump targets, one
# per `~` in program order (1-based: target N resumes at command N).  `+`
# increments the pointed-to register, `*` flips the pointer, and `~`
# decrements the pointed-to register if it is nonzero; if it is already
# zero, `~` jumps to its target unless the target is 0 (a lone `~\n0` is a
# no-op fallthrough, matching the Python interpreter's ``if target:``
# guard).  Any other character on the first line is ignored (comment); the
# second line is scanned for digit runs only.  A `~` with no corresponding
# number on the jump line is a malformed program.
#
# Exit codes follow the cross-check convention: 0 = success, 2 = malformed
# program (a `~` with no jump target).  Minsky Swap has no invalid runtime
# operations, so exit 3 is unused.  The program is read from stdin.
#
# Build: riscv64-elf-gcc -nostdlib -static -march=rv64i -mabi=lp64 -o minsky_swap-riscv minsky_swap-riscv.s
#        (or riscv64-linux-gnu-gcc, as in CI)
# Run:   qemu-riscv64 ./minsky_swap-riscv < program
#
# Registers:
#   s0 = program length (n_bytes; program[i] lives at s3 - i)
#   s3 = first program byte address
#   s4 = byte index (tokenizing) / token index (executing)
#   s5 = token count
#   s6 = token types base (0=+ 1=~ 2=*)
#   s7 = token_targets base: 4-byte entries indexed by token index,
#        meaningful only where types[] is 1 (1-based; 0 = "no jump on
#        zero"); a tilde revisited via a jump always reads the same entry
#   s8/s9 = reg[0]/reg[1]
#   s10 = pointer (0 or 1: which of s8/s9 is active)
#   s11 = tilde count seen so far (tokenizing only)
#
# Resource limits: the token and target tables are fixed buffers (4096
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

# Find the first newline (or EOF): the command line is program[0:nl_pos],
# the jump line is program[nl_pos+1:n_bytes] (empty if there is none).
    li   t0, 0               # scan index
.find_nl:
    bge  t0, s0, .nl_found   # no newline: the whole program is the cmd line
    sub  t1, s3, t0
    lbu  t2, 0(t1)
    li   t3, '\n'
    beq  t2, t3, .nl_found
    addi t0, t0, 1
    j    .find_nl
.nl_found:
    mv   s1, t0              # s1 = command-line length (nl_pos)
    addi s2, t0, 1            # s2 = jump-line start (nl_pos + 1)

# Tokenize the command line into (type) entries, matching /[+~*]/, and
# count the tildes seen (their order is what the second pass indexes by).
    la   s6, types
    li   s4, 0                # byte index
    li   s5, 0                # token count
    li   s11, 0                # tilde count
.tokenize:
    bge  s4, s1, .tokenize_done
    sub  t1, s3, s4
    lbu  t2, 0(t1)
    li   t3, '+'
    beq  t2, t3, .tok_plus
    li   t3, '~'
    beq  t2, t3, .tok_tilde
    li   t3, '*'
    beq  t2, t3, .tok_star
    addi s4, s4, 1
    j    .tokenize
.tok_plus:
    li   t3, 0
    j    .tok_emit
.tok_star:
    li   t3, 2
    j    .tok_emit
.tok_tilde:
    li   t3, 1
    addi s11, s11, 1
.tok_emit:
    add  t6, s6, s5
    sb   t3, 0(t6)
    addi s4, s4, 1
    addi s5, s5, 1
    j    .tokenize
.tokenize_done:

# Scan the jump line for digit runs (matching re.findall(r"\d+", line)),
# building an nth_targets[] array indexed by tilde order (the k-th tilde
# tokenized gets the k-th number).  A tilde with no corresponding number
# (s11 > number count) is malformed.
    la   t4, nth_targets
    li   t0, 0                 # numbers found so far
    mv   t1, s2                 # scan index into the jump line
.numscan:
    bge  t1, s0, .numscan_done
    sub  t2, s3, t1
    lbu  t3, 0(t2)
    li   t5, '0'
    blt  t3, t5, .numscan_next
    li   t5, '9'
    bgt  t3, t5, .numscan_next
    # start of a digit run
    li   t6, 0                  # accumulated value
.numscan_digit:
    bge  t1, s0, .numscan_emit
    sub  t2, s3, t1
    lbu  t3, 0(t2)
    li   t5, '0'
    blt  t3, t5, .numscan_emit
    li   t5, '9'
    bgt  t3, t5, .numscan_emit
    addi t3, t3, -48
    slli t5, t6, 3               # value * 8
    slli t2, t6, 1                # value * 2
    add  t6, t5, t2
    add  t6, t6, t3
    addi t1, t1, 1
    j    .numscan_digit
.numscan_emit:
    slli t5, t0, 2
    add  t5, t4, t5
    sw   t6, 0(t5)               # nth_targets[numbers found] = value
    addi t0, t0, 1
    j    .numscan
.numscan_next:
    addi t1, t1, 1
    j    .numscan
.numscan_done:
    bge  t0, s11, .targets_ok    # enough numbers for every tilde seen
    li   a0, 2                    # unmatched '~': malformed
    li   a7, 93
    ecall
.targets_ok:

# Re-walk the token array, this time assigning each tilde *token*'s fixed
# target from nth_targets[] in tilde order: a tilde token can be visited
# many times (via jumps), and each visit must use that same token's own
# target, not "the next target in execution order".  s7 = token_targets
# base (4-byte entries, indexed by token index, meaningful only where
# types[] is 1).
    la   s7, token_targets
    la   t4, nth_targets
    li   s4, 0                  # token index
    li   t0, 0                  # tilde-order counter
.merge:
    bge  s4, s5, .merge_done
    add  t1, s6, s4
    lbu  t2, 0(t1)
    li   t3, 1
    bne  t2, t3, .merge_next
    slli t1, t0, 2
    add  t1, t4, t1
    lw   t2, 0(t1)               # nth_targets[tilde-order counter]
    slli t1, s4, 2
    add  t1, s7, t1
    sw   t2, 0(t1)               # token_targets[token index] = target
    addi t0, t0, 1
.merge_next:
    addi s4, s4, 1
    j    .merge
.merge_done:

.exec_start:
    li   s8, 0                # reg[0]
    li   s9, 0                # reg[1]
    li   s10, 0                # pointer
    li   s4, 0                 # token index

.exec:
    bge  s4, s5, .done         # ind >= count: halted
    add  t0, s6, s4
    lbu  t1, 0(t0)              # type
    li   t0, 0
    beq  t1, t0, .cmd_plus
    li   t0, 1
    beq  t1, t0, .cmd_tilde
    j    .cmd_star

.cmd_plus:
    beqz s10, .plus0
    addi s9, s9, 1
    j    .next
.plus0:
    addi s8, s8, 1
    j    .next

.cmd_star:
    xori s10, s10, 1
    j    .next

.cmd_tilde:
    beqz s10, .tilde0
    beqz s9, .tilde_zero
    addi s9, s9, -1
    j    .next
.tilde0:
    beqz s8, .tilde_zero
    addi s8, s8, -1
    j    .next
.tilde_zero:
    slli t3, s4, 2
    add  t6, s7, t3
    lw   t5, 0(t6)               # token_targets[s4] (1-based; 0 = no-op)
    beqz t5, .next               # target 0: fall through, no jump
    addi s4, t5, -2               # ind = target - 2 (the .next +1 lands
    j    .next                    # on 0-based index target - 1)

.next:
    addi s4, s4, 1
    j    .exec

.done:
    la   a1, buf
    mv   a0, s8
    call fmt_dec
    li   t0, ' '
    sb   t0, 0(a1)
    addi a1, a1, 1
    mv   a0, s9
    call fmt_dec
    # no trailing newline: the Python interpreter's dump ends at the last
    # register, and these ports mirror it
    la   t0, buf
    sub  a2, a1, t0
    li   a7, 64
    li   a0, 1
    la   a1, buf
    ecall
    li   a0, 0
    li   a7, 93
    ecall

# Format a0 (unsigned) as decimal into the buffer at a1, advancing a1 past
# the written digits and returning the new a1 (software division: rv64i
# has no M).
fmt_dec:
    addi sp, sp, -32
    sd   ra, 24(sp)
    li   t0, 0
    bnez a0, 1f
    li   t5, 48
    sb   t5, 0(a1)
    addi a1, a1, 1
    ld   ra, 24(sp)
    addi sp, sp, 32
    ret
1:
    li   t1, 10
2:
    call div_u
    addi t5, t5, 48
    add  t6, sp, t0
    sb   t5, 0(t6)
    addi t0, t0, 1
    bnez a0, 2b
3:
    addi t0, t0, -1
    add  t6, sp, t0
    lbu  t5, 0(t6)
    sb   t5, 0(a1)
    addi a1, a1, 1
    bnez t0, 3b
    ld   ra, 24(sp)
    addi sp, sp, 32
    ret

# a0 / t1 -> a0 quotient, t5 remainder (unsigned 64-bit)
div_u:
    mv   t6, a0
    li   a0, 0
    li   t5, 0
    li   t2, 64
1:
    slli t5, t5, 1
    srli t3, t6, 63
    or   t5, t5, t3
    slli t6, t6, 1
    bltu t5, t1, 2f
    sub  t5, t5, t1
    ori  a0, a0, 1
2:
    addi t2, t2, -1
    beqz t2, 3f
    slli a0, a0, 1
    j    1b
3:
    ret

    .bss
    .align 3
types:         .zero 4096
nth_targets:   .zero 16384   # 4096 * 4 bytes
token_targets: .zero 16384   # 4096 * 4 bytes
buf:           .zero 64
