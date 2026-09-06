    .text
    .global _start
_start:
    la   s2, stack_base
    mv   s1, s2
    la   s3, table

    call reverse
    j    .halt

.halt:
    li   a0, 0
    li   a7, 93
    ecall

# push(value: t0) -- push t0 onto the data stack
push:
    addi s1, s1, -8
    sd   t0, 0(s1)
    ret

# pop() -> t0; an empty-stack pop halts the whole program
pop:
    beq  s1, s2, .halt
    ld   t0, 0(s1)
    addi s1, s1, 8
    ret

# peek() -> t0; an empty-stack peek halts the whole program
peek:
    beq  s1, s2, .halt
    ld   t0, 0(s1)
    ret

dup:
    addi sp, sp, -16
    sd   ra, 0(sp)
    call peek
    call push
    ld   ra, 0(sp)
    addi sp, sp, 16
    ret

complement:
    addi sp, sp, -16
    sd   ra, 0(sp)
    call pop
    not  t0, t0
    call wrap32
    call push
    ld   ra, 0(sp)
    addi sp, sp, 16
    ret

# print_top() -- pop and print the low byte
print_top:
    addi sp, sp, -32
    sd   ra, 0(sp)
    call pop
    andi a0, t0, 0xff
    sd   a0, 16(sp)
    li   a7, 64
    li   a0, 1
    addi a1, sp, 16
    li   a2, 1
    ecall
    ld   ra, 0(sp)
    addi sp, sp, 32
    ret


# reverse() -- reverse the whole data stack in place
reverse:
    mv   t3, s1
    mv   t4, s2
    addi t4, t4, -8
1:
    bge  t3, t4, 2f
    ld   t0, 0(t3)
    ld   t1, 0(t4)
    sd   t1, 0(t3)
    sd   t0, 0(t4)
    addi t3, t3, 8
    addi t4, t4, -8
    j    1b
2:
    ret

# rotate3() -> a0 (1 ok, 0 aborted); moves the third-from-top value
# to the top, or reports abort if fewer than three values are on
# the stack.  On abort the caller must unwind its whole current
# scope (see emit_body's abort_to), not just skip this call, so it
# only reports status here and never touches ra/sp/s4 itself.
rotate3:
    mv   t1, s2
    addi t1, t1, -24
    blt  t1, s1, .rotate3_abort
    ld   t0, 16(s1)
    ld   t1, 8(s1)
    ld   t2, 0(s1)
    sd   t1, 16(s1)
    sd   t2, 8(s1)
    sd   t0, 0(s1)
    li   a0, 1
    ret
.rotate3_abort:
    li   a0, 0
    ret

# binary ops -> a0 (1 ok, 0 aborted): pop two (one=second-from-top,
# two=top), push the result; fewer than two values, or a zero
# divisor for div/mod, aborts without pushing.  Like rotate3, only
# status is reported -- the abort itself unwinds the whole calling
# scope at the call site, not just this op.  rv64i has no M
# extension, so mul/div/mod are software (mul32/divmod32 below);
# every result is truncated to a sign-extended 32-bit word, matching
# the interpreter's _wrap32.
op_add:
    addi sp, sp, -16
    sd   ra, 0(sp)
    call binary_operands
    beqz t3, .op_abort
    add  t0, t1, t2
    call wrap32
    call push
    j    .op_ok
op_sub:
    addi sp, sp, -16
    sd   ra, 0(sp)
    call binary_operands
    beqz t3, .op_abort
    sub  t0, t1, t2
    call wrap32
    call push
    j    .op_ok
op_mul:
    addi sp, sp, -16
    sd   ra, 0(sp)
    call binary_operands
    beqz t3, .op_abort
    mv   a0, t1
    mv   a1, t2
    call mul32
    mv   t0, a0
    call push
    j    .op_ok
op_div:
    addi sp, sp, -16
    sd   ra, 0(sp)
    call binary_operands
    beqz t3, .op_abort
    beqz t2, .op_abort
    mv   a0, t1
    mv   a1, t2
    call divmod32
    mv   t0, a0
    call push
    j    .op_ok
op_mod:
    addi sp, sp, -16
    sd   ra, 0(sp)
    call binary_operands
    beqz t3, .op_abort
    beqz t2, .op_abort
    mv   a0, t1
    mv   a1, t2
    call divmod32
    mv   t0, a1
    call push
    j    .op_ok
op_swap:
    addi sp, sp, -16
    sd   ra, 0(sp)
    call binary_operands
    beqz t3, .op_abort
    mv   t0, t2
    call push
    mv   t0, t1
    call push
.op_ok:
    ld   ra, 0(sp)
    addi sp, sp, 16
    li   a0, 1
    ret
.op_abort:
    ld   ra, 0(sp)
    addi sp, sp, 16
    li   a0, 0
    ret

# binary_operands() -> t1 (one), t2 (two), t3 (1 if both present else 0)
binary_operands:
    mv   t4, s2
    addi t4, t4, -16
    blt  t4, s1, .no_operands
    addi sp, sp, -16
    sd   ra, 0(sp)
    call pop
    mv   t2, t0
    call pop
    mv   t1, t0
    ld   ra, 0(sp)
    addi sp, sp, 16
    li   t3, 1
    ret
.no_operands:
    li   t3, 0
    ret

# wrap32() -- truncate t0 to a signed 32-bit value, sign-extended
# back to 64 bits (matching the interpreter's _wrap32)
wrap32:
    slli t0, t0, 32
    srai t0, t0, 32
    ret

# mul32(a0, a1) -> a0 = (a0 * a1), wrapped to signed 32-bit
# (rv64i has no M extension; shift-and-add is sign-agnostic on
# two's-complement operands as long as the result is truncated)
mul32:
    addi sp, sp, -16
    sd   ra, 0(sp)
    mv   t4, a0
    mv   t5, a1
    li   a0, 0
1:
    beqz t5, 2f
    andi t6, t5, 1
    beqz t6, 3f
    add  a0, a0, t4
3:
    slli t4, t4, 1
    srli t5, t5, 1
    j    1b
2:
    mv   t0, a0
    call wrap32
    mv   a0, t0
    ld   ra, 0(sp)
    addi sp, sp, 16
    ret

# divmod32(a0, a1) -> a0 = quotient, a1 = remainder, truncating
# toward zero (matching the interpreter's _trunc_div/_trunc_mod);
# a1 (divisor) must be nonzero -- checked by the caller
divmod32:
    li   t4, 0
    mv   t5, a0
    bgez a0, 1f
    sub  a0, x0, a0
    xori t4, t4, 1
1:
    bgez a1, 2f
    sub  a1, x0, a1
    xori t4, t4, 1
2:
    li   t0, 0
3:
    bltu a0, a1, 4f
    sub  a0, a0, a1
    addi t0, t0, 1
    j    3b
4:
    beqz t4, 5f
    sub  t0, x0, t0
5:
    bgez t5, 6f
    sub  a0, x0, a0
6:
    mv   a1, a0
    mv   a0, t0
    ret

# table_store(key: a0, addr: a1) -- append (key, addr) to the table
table_store:
    sd   a0, 0(s3)
    sd   a1, 8(s3)
    addi s3, s3, 16
    ret

# table_call(key: a0) -- scan the table backward for the most recent
# entry with this key and call it; a key with no entry is a no-op
# (the interpreter's table.get(key, "") is an empty scope)
table_call:
    la   t0, table
    mv   t1, s3
1:
    beq  t1, t0, 2f
    addi t1, t1, -16
    ld   t2, 0(t1)
    bne  t2, a0, 1b
    ld   t3, 8(t1)
    addi sp, sp, -16
    sd   ra, 0(sp)
    jalr ra, t3, 0
    ld   ra, 0(sp)
    addi sp, sp, 16
2:
    ret

    .bss
    .align 3
table:
    .space 65536
stack:
    .space 524288
stack_base:
