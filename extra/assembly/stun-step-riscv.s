# Stun Step interpreter (RISC-V Linux port; see README "Extra Implementations").
#
# A tape language with four commands: `+`/`-` increment/decrement the current
# cell, and `>`/`<` move the pointer right/left only while the current cell
# is nonzero.  Cells are 32-bit words holding nonnegative integers,
# initialized to 1 except the cell the pointer starts on, which is stored as
# 0xFFFFFFFF (-1) so that the +1 output mapping shows 0; `-` on that cell is
# a no-op and `>`/`<` from it do not move.  There is no explicit flow
# control: once the program text is consumed, execution loops back to the
# start unless the current cell's high bit is set, in which case the machine
# halts.  The program is read from stdin; on halting the cells from the
# start position through the rightmost reached are printed as
# space-separated decimal values (an output decision, not a language rule).
#
# Build: riscv64-elf-gcc -nostdlib -static -march=rv64i -mabi=lp64 -o stun-step-riscv stun-step-riscv.s
#        (or riscv64-linux-gnu-gcc, as in CI)
# Run:   qemu-riscv64 ./stun-step-riscv < program
#
# Registers:
#   s2 = program buffer pointer (grows down as the program is read)
#   s3 = scan pointer
#   s4 = cell offset from the tape base (0, -4, -8, ...)
#   s5 = position (1-based)
#   s6 = extent (the rightmost position reached)
#
# Syscalls: read = 63, write = 64, exit = 93.

    .text
    .global _start

_start:
    addi s2, sp, -20          # program buffer starts below the stack top
    li   s4, 0                # cell offset (cell 0)
    li   s5, 1                # position
    li   s6, 1                # extent
    la   t0, tape
    li   t1, -1
    sw   t1, 0(t0)            # cell 0 = 0xFFFFFFFF (-1)

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
    addi s3, sp, -19          # scan from the first program byte

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
    bnez t1, .parse           # anything else is skipped

# End of the program: halt if the current cell's high bit is set, else
# restart from the first byte.
    la   t0, tape
    add  t0, t0, s4
    lw   t1, 0(t0)
    bltz t1, .halt
    addi s3, sp, -19
    j    .parse

# On halting, print (cell + 1) for cells 0..extent-1, space separated.
.halt:
    la   t0, tape
    lw   a0, 0(t0)
    addi a0, a0, 1
    li   t1, -1
    and  a0, a0, t1          # mod 2^32
    call output
    li   s5, 1               # k = 1
.state:
    bge  s5, s6, .final      # k >= extent: done
    call print_space
    la   t0, tape
    slli t1, s5, 2
    sub  t0, t0, t1          # cell -4k
    lw   a0, 0(t0)
    addi a0, a0, 1
    li   t1, -1
    and  a0, a0, t1
    call output
    addi s5, s5, 1
    j    .state
.final:
    li   a0, 0
    li   a7, 93
    ecall

.plus:
    la   t0, tape
    add  t0, t0, s4
    lw   t1, 0(t0)
    addi t1, t1, 1           # wraps mod 2^32 on the store
    sw   t1, 0(t0)
    j    .parse

.minus:
    la   t0, tape
    add  t0, t0, s4
    lw   t1, 0(t0)
    li   t2, -1
    beq  t1, t2, .parse      # cell == -1: no-op
    addi t1, t1, -1
    sw   t1, 0(t0)
    j    .parse

.right:
    la   t0, tape
    add  t0, t0, s4
    lw   t1, 0(t0)
    li   t2, -1
    beq  t1, t2, .parse      # cell == -1: no move
    addi s5, s5, 1           # position += 1
    addi s4, s4, -4          # cell offset -= 4
    blt  s6, s5, .right_ext  # extent < position: extend
    j    .parse
.right_ext:
    mv   s6, s5
    j    .parse

.left:
    bne  s4, s6, .left_check # cell != extent (always true here)
    j    .parse
.left_check:
    la   t0, tape
    add  t0, t0, s4
    lw   t1, 0(t0)
    li   t2, -1
    beq  t1, t2, .parse      # cell == -1: no move
    addi s5, s5, -1          # position -= 1
    addi s4, s4, 4           # cell offset += 4
    j    .parse

# Divide a0 by a1: quotient in a0, remainder in a1 (repeated subtraction).
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
    .zero 4096
