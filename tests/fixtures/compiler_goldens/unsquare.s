.text
    .global _start
_start:
    addi s1, sp, -4
    li   s2, 0
    li   s3, 1

	call output

	li   a0, 0
	li   a7, 93
	ecall

output:
	li   a7, 64
	li   a0, 1
	mv   a1, s1
	li   a2, 1
	ecall
	ret
