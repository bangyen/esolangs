    .text
    .global _start
_start:
    addi sp, sp, -64
    addi s1, sp, 64
    mv   s2, s1
	li   a0, 0
	li   a7, 93
	ecall
