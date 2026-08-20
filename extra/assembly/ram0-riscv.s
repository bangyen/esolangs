# RAM0 interpreter (RISC-V Linux port; see README "Extra Implementations").
#
# The full wiki language: two registers (z, n) plus unbounded RAM, with
# seven token forms: `Z` zeroes z, `A` increments z, `N` copies z into n,
# `L` loads z := ram[z], `S` stores ram[n] := z, `C` skips the next token
# when z == 0, and a digit string ``[1-9]``\ d* is an unconditional goto to
# token ``d - 1`` (running off either end of the token list halts).  Any
# other character is a comment.  On halting the full state is dumped exactly
# once, in RAM0's insertion-order ``z:``/``n:``/``ram:`` format.
#
# Exit codes follow the cross-check convention; RAM0 has no error categories,
# so a run always exits 0 after the dump.  The program is read from stdin.
#
# Build: riscv64-elf-gcc -nostdlib -static -march=rv64i -mabi=lp64 -o ram0-riscv ram0-riscv.s
#        (or riscv64-linux-gnu-gcc, as in CI)
# Run:   qemu-riscv64 ./ram0-riscv < program
#
# Registers:
#   s0 = program length (n_bytes; program[i] lives at s3 - i)
#   s1 = z, s2 = n
#   s3 = first program byte address
#   s4 = token index, s5 = token count
#   s6 = token types base, s7 = token values base
#   s8 = RAM base, s9 = set-flags base, s10 = insertion-order base,
#   s11 = insertion-order length
#
# Resource limits: RAM and the token table are fixed buffers (4096 cells and
# 4096 tokens), and the runner caps execution at 10M instructions.  A program
# that pushes a register or address past the buffers faults (folded into
# "did not terminate" by the differential), the same class as NoComment's
# fixed tape/stack.
#
# Syscalls: read = 63, write = 64, exit = 93.

    .text
    .global _start

_start:
    addi s3, sp, -5         # first program byte address
    li   s0, 0              # n_bytes
    li   s1, 0              # z
    li   s2, 0              # n
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

# Tokenize into (type, value) pairs, matching re.findall(r"([ZANCLS]|[1-9]\d*)").
# Digit-run values are saturated at 0x7FFFFFFF: any value that big is far past
# the token count, so its goto is out of range and dumps, as Python's huge
# int does.
    la   s6, types
    la   s7, values
    li   s4, 0              # byte index
    li   s5, 0              # token count
.tokenize:
    bge  s4, s0, .tokenize_done
    sub  t1, s3, s4
    lbu  t2, 0(t1)          # t2 = program[s4]
    li   t3, 'Z'
    beq  t2, t3, .tok_z
    li   t3, 'A'
    beq  t2, t3, .tok_a
    li   t3, 'N'
    beq  t2, t3, .tok_n
    li   t3, 'C'
    beq  t2, t3, .tok_c
    li   t3, 'L'
    beq  t2, t3, .tok_l
    li   t3, 'S'
    beq  t2, t3, .tok_s
    li   t3, '1'
    blt  t2, t3, .tok_skip  # < '1' (incl. '0'): not a token, per [1-9]\d*
    li   t3, '9'
    bgt  t2, t3, .tok_skip  # > '9'
    j    .tok_digit
.tok_z:
    li   t3, 0
    j    .tok_emit
.tok_a:
    li   t3, 1
    j    .tok_emit
.tok_n:
    li   t3, 2
    j    .tok_emit
.tok_c:
    li   t3, 3
    j    .tok_emit
.tok_l:
    li   t3, 4
    j    .tok_emit
.tok_s:
    li   t3, 5
.tok_emit:
    add  t4, s6, s5
    sb   t3, 0(t4)          # types[count] = 0..5
    addi s4, s4, 1
    addi s5, s5, 1
    j    .tokenize
.tok_digit:
    li   t4, 0              # value
.tok_digit_loop:
    sub  t1, s3, s4
    lbu  t2, 0(t1)
    li   t3, '0'
    blt  t2, t3, .tok_digit_end
    li   t3, '9'
    bgt  t2, t3, .tok_digit_end
    addi t2, t2, -48        # digit 0-9
    slli t5, t4, 3          # value * 8
    slli t6, t4, 1          # value * 2
    add  t4, t5, t6         # value * 10
    add  t4, t4, t2
    li   t3, 0x7FFFFFFF
    bltu t4, t3, 1f         # saturate past any real token count
    mv   t4, t3
1:
    addi s4, s4, 1
    j    .tok_digit_loop
.tok_digit_end:
    slli t3, s5, 3
    add  t3, s7, t3
    sd   t4, 0(t3)          # values[count] = value (8-byte entries)
    li   t3, 6
    add  t4, s6, s5
    sb   t3, 0(t4)          # types[count] = 6
    addi s5, s5, 1
    j    .tokenize
.tok_skip:
    addi s4, s4, 1
    j    .tokenize
.tokenize_done:

# Execution:  the state machine (registers, RAM, and the token cursor).
    la   s8, ram
    la   s9, setflags
    la   s10, order
    li   s11, 0             # order length
    li   s4, 0              # ind

.exec:
    bge  s4, s5, .done      # ind >= count: halted, dump the state
    add  t0, s6, s4
    lbu  t1, 0(t0)          # type
    li   t0, 0
    beq  t1, t0, .cmd_z
    li   t0, 1
    beq  t1, t0, .cmd_a
    li   t0, 2
    beq  t1, t0, .cmd_n
    li   t0, 3
    beq  t1, t0, .cmd_c
    li   t0, 4
    beq  t1, t0, .cmd_l
    li   t0, 5
    beq  t1, t0, .cmd_s
    # type 6: unconditional goto to token (value - 1)
    slli t0, s4, 3
    add  t0, s7, t0
    ld   t1, 0(t0)
    addi s4, t1, -1
    j    .exec
.cmd_z:
    li   s1, 0
    addi s4, s4, 1
    j    .exec
.cmd_a:
    addi s1, s1, 1
    addi s4, s4, 1
    j    .exec
.cmd_n:
    mv   s2, s1
    addi s4, s4, 1
    j    .exec
.cmd_c:
    beqz s1, 1f             # z == 0: skip the next token too
    addi s4, s4, 1
    j    .exec
1:
    addi s4, s4, 2
    j    .exec
.cmd_l:
    li   t0, 4096           # RAM_SIZE
    bgeu s1, t0, 1f         # out of bounds reads 0
    slli t0, s1, 2
    add  t0, s8, t0
    lw   s1, 0(t0)
    j    2f
1:
    li   s1, 0
2:
    addi s4, s4, 1
    j    .exec
.cmd_s:
    li   t0, 4096           # RAM_SIZE
    bgeu s2, t0, 1f         # out of bounds: resource limit, skip the store
    slli t0, s2, 2
    add  t0, s8, t0
    sw   s1, 0(t0)          # ram[n] = z
    add  t0, s9, s2
    lbu  t1, 0(t0)
    bnez t1, 1f             # n already in the insertion order
    li   t1, 1
    sb   t1, 0(t0)          # setflags[n] = 1
    slli t1, s11, 2
    add  t1, s10, t1
    sw   s2, 0(t1)          # order[order_len] = n
    addi s11, s11, 1
1:
    addi s4, s4, 1
    j    .exec

# Dump the final state in the interpreter's format.
.done:
    la   a1, str_z
    call print_str
    mv   a0, s1
    call print_dec
    la   a1, str_nl
    call print_str
    la   a1, str_n
    call print_str
    mv   a0, s2
    call print_dec
    la   a1, str_nl
    call print_str
    beqz s11, .ram_empty
    la   a1, str_ram
    call print_str
    li   s4, 0              # order index
.ram_loop:
    bge  s4, s11, .ram_done
    slli t1, s4, 2
    add  t1, s10, t1
    lw   s0, 0(t1)          # key = order[i] (s0 survives the print calls)
    la   a1, str_sp
    call print_str
    mv   a0, s0
    call print_dec
    la   a1, str_col
    call print_str
    slli t1, s0, 2
    add  t1, s8, t1
    lw   a0, 0(t1)          # ram[key]
    call print_dec
    addi t1, s4, 1
    bge  t1, s11, 1f        # last entry: newline, no comma
    la   a1, str_comma
    j    2f
1:
    la   a1, str_nl
2:
    call print_str
    addi s4, s4, 1
    j    .ram_loop
.ram_done:
    la   a1, str_end
    call print_str
    j    .exit
.ram_empty:
    la   a1, str_ram_empty
    call print_str
.exit:
    li   a0, 0
    li   a7, 93
    ecall

# print the null-terminated string at a1
print_str:
    mv   t3, a1
    mv   t2, a1
1:
    lbu  t4, 0(t2)
    beqz t4, 2f
    addi t2, t2, 1
    j    1b
2:
    sub  a2, t2, t3
    li   a7, 64
    li   a0, 1
    ecall
    ret

# print a0 in decimal (software division by 10: rv64i has no M)
print_dec:
    addi sp, sp, -64
    sd   ra, 56(sp)
    li   t0, 0
    bnez a0, 1f
    li   t5, 48
    sb   t5, 0(sp)
    mv   a1, sp
    li   a2, 1
    li   a7, 64
    li   a0, 1
    ecall
    ld   ra, 56(sp)
    addi sp, sp, 64
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
    add  a1, sp, t0
    li   a2, 1
    li   a7, 64
    li   a0, 1
    ecall
    bnez t0, 3b
    ld   ra, 56(sp)
    addi sp, sp, 64
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

    .section .rodata
str_z:  .asciz "z: "
str_n:  .asciz "n: "
str_nl: .asciz "\n"
str_ram: .asciz "ram: {\n"
str_ram_empty: .asciz "ram: {}\n"
str_sp: .asciz "    "
str_col: .asciz ": "
str_comma: .asciz ",\n"
str_end: .asciz "}\n"

    .bss
    .align 3
types:   .zero 4096
values:  .zero 32768   # 4096 tokens * 8 bytes
ram:     .zero 16384   # 4096 cells * 4 bytes
setflags: .zero 4096
order:   .zero 16384   # 4096 * 4 bytes
