    .text
    .global _start
_start:
    li   s4, 1
    li   s3, 0
    addi s1, sp, -12
    addi s2, s1, -4
    li   s5, 1
.main:

	addi s4, s4, -1
	bgt  s4, zero, .main
	li   a0, 0
	li   a7, 93
	ecall