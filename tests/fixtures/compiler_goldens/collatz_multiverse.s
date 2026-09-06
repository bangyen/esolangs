    .text
    .global _start
_start:
    la   gp, __global_pointer$
    la   s4, scalars
    li   t0, 32
    add  t1, s4, t0
1:
    bge  s4, t1, 2f
    sd   zero, 0(s4)
    addi s4, s4, 8
    j    1b
2:
    la   s4, scalars
    li   t0, -1
    sd   t0, 0(s4)
    li   a0, 1
    j    dispatch
.L1:
	li   s2, 1
	ld   t0, 16(s4)
	ld   t1, 24(s4)
	ld   t2, 8(s4)
	beqz t2, .odd1
	andi t3, t2, 1
	bnez t3, .odd1
	srai t2, t2, 1
	j    .done1
.odd1:
	mv   a0, t0
	mv   a1, t1
	call collatz_odd
	mv   t2, a0
.done1:
	sd   t2, 8(s4)
	mv   a0, t2
	call write_byte
	j    .halt
.halt:
	li   a0, 0
	li   a7, 93
	ecall

# dispatch: jump to .L{a0}, or .halt if a0 is outside 1..n
dispatch:
	mv   s2, a0
	li   t0, 1
	beq  s2, t0, .L1
	j    .halt

# array_index(idx: a0) -> a0, wrapped into 0.._ARRAY_SIZE-1
# (_ARRAY_SIZE is a power of two, so a bitmask is the wrapped modulo
# even for negative idx, without needing the M extension's rem)
array_index:
	andi a0, a0, 255
	ret

# collatz_odd(a: a0, b: a1) -> a0 = t2 * a0 + a1 (t2 = current value)
collatz_odd:
	mv   t4, t2
	mv   t5, a0
	li   t6, 0
	bgez t4, 1f
	sub  t4, x0, t4
	xori t6, t6, 1
1:
	bgez t5, 2f
	sub  t5, x0, t5
	xori t6, t6, 1
2:
	li   a0, 0
3:
	beqz t5, 4f
	andi t3, t5, 1
	beqz t3, 5f
	add  a0, a0, t4
5:
	slli t4, t4, 1
	srli t5, t5, 1
	j    3b
4:
	beqz t6, 6f
	sub  a0, x0, a0
6:
	add  a0, a0, a1
	ret

# write_byte(value: a0)
write_byte:
	addi sp, sp, -16
	sd   ra, 8(sp)
	andi t0, a0, 0xff
	sb   t0, 0(sp)
	li   a7, 64
	li   a0, 1
	mv   a1, sp
	li   a2, 1
	ecall
	ld   ra, 8(sp)
	addi sp, sp, 16
	ret

# mul_small(a0, a1) -> a0 = a0 * a1 (unsigned, small multiplier)
mul_small:
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
	ret

    .data
    .align 3
scalars:
    .space 32
