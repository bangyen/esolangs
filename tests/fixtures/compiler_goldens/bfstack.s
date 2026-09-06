    .text
    .global _start
_start:
    addi s1, sp, -6
    li   s2, 1
    addi s3, sp, -1


	li   a0, 0
	li   a7, 93
	ecall
