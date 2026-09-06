    .text
    .global _start
_start:
    addi sp, sp, -100
    mv   s1, sp
    li   s3, 25
.zero_grid:
    sw   zero, 0(s1)
    addi s1, s1, 4
    addi s3, s3, -1
    bnez s3, .zero_grid
    mv   s1, sp
    li   s4, 0
    li   s5, 0

