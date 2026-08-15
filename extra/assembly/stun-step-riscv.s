# Stun Step interpreter (RISC-V Linux port; see README "Extra Implementations").
#
# A tape language with four commands: `+`/`-` increment/decrement the current
# cell, and `>`/`<` move the pointer right/left only while the current cell
# is nonzero.  Cells are 64-bit nonnegative integers, initialized to 1 except
# the cell the pointer starts on, which is 0 (values wrap only past 2^64, a
# practical stand-in for the wiki's unbounded integers).  There is no
# explicit flow control: once the program text is consumed, execution loops
# back to the start unless the current cell is 0, in which case the machine
# halts.  Decrementing a 0 cell is undefined per the wiki; it is left at 0.
# The program is read from stdin; on halting the cells from the leftmost
# through the rightmost position reached are printed as space-separated
# decimal values (an output decision, not a language rule).
#
# Build: riscv64-elf-gcc -nostdlib -static -march=rv64i -mabi=lp64 -o stun-step-riscv stun-step-riscv.s
#        (or riscv64-linux-gnu-gcc, as in CI)
# Run:   qemu-riscv64 ./stun-step-riscv < program
#
# Registers:
#   s2 = program buffer pointer (grows down as the program is read)
#   s3 = scan pointer
#   s4 = current cell's byte offset from the tape's middle (tape+2048)
#   s5 = leftmost cell offset reached
#   s6 = rightmost cell offset reached
#
# Syscalls: read = 63, write = 64, exit = 93.

    .text
    .global _start

_start:
    # initialize the tape: every cell 1, the starting cell 0
    la   t0, tape
    li   t1, 512
    li   t2, 1
.init_loop:
    sd   t2, 0(t0)
    addi t0, t0, 8
    addi t1, t1, -1
    bnez t1, .init_loop
    la   t0, tape
    li   t1, 2048
    add  t0, t0, t1
    sd   zero, 0(t0)          # cell 0 = 0
    li   s4, 0                # current cell offset
    li   s5, 0                # leftmost reached
    li   s6, 0                # rightmost reached
    addi s2, sp, -20          # program buffer starts below the stack top

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
    j    .parse

# Compute the address of the cell at byte offset s4 into t0.
cell_addr:
    la   t0, tape
    li   t1, 2048
    add  t0, t0, t1
    add  t0, t0, s4
    ret

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

# End of the program: halt if the current cell is 0, else restart.
    call cell_addr
    ld   t1, 0(t0)
    beqz t1, .halt
    addi s3, sp, -19
    j    .parse

# On halting, print the cells from offset s5 through s6, space separated.
.halt:
    li   s0, 0                # first-value flag
    mv   s1, s5               # k = leftmost offset
.state_loop:
    la   t0, tape
    li   t1, 2048
    add  t0, t0, t1
    add  t0, t0, s1
    ld   a0, 0(t0)
    bnez s0, .state_space
    li   s0, 1
    j    .state_print
.state_space:
    call print_space
.state_print:
    call output
    addi s1, s1, 8
    ble  s1, s6, .state_loop
    li   a0, 0
    li   a7, 93
    ecall

.plus:
    call cell_addr
    ld   t1, 0(t0)
    addi t1, t1, 1
    sd   t1, 0(t0)
    j    .parse

.minus:
    call cell_addr
    ld   t1, 0(t0)
    beqz t1, .parse           # decrementing 0 clamps at 0
    addi t1, t1, -1
    sd   t1, 0(t0)
    j    .parse

.right:
    call cell_addr
    ld   t1, 0(t0)
    beqz t1, .parse
    addi s4, s4, 8
    blt  s6, s4, .right_ext
    j    .parse
.right_ext:
    mv   s6, s4
    j    .parse

.left:
    call cell_addr
    ld   t1, 0(t0)
    beqz t1, .parse
    addi s4, s4, -8
    blt  s4, s5, .left_ext
    j    .parse
.left_ext:
    mv   s5, s4
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
    sd   ra, 24(sp)
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
    addi sp, sp, -24
    sd   ra, 16(sp)
    sd   a0, 8(sp)
    li   t0, ' '
    sb   t0, 0(sp)
    li   a7, 64
    li   a0, 1
    mv   a1, sp
    li   a2, 1
    ecall
    ld   a0, 8(sp)
    ld   ra, 16(sp)
    addi sp, sp, 24
    ret

    .bss
    .align 3
tape:
    .zero 4096
