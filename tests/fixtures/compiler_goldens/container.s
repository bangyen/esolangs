    .text
    .option norelax
    .global _start
_start:
    la   s1, con_cells
    li   t0, 16
    add  s2, s1, t0
.tick:
    ld   s3, 0(s1)
    ld   t0, 0(s1)
    li   t1, 0
    blt  t0, t1, .skip_0_0
    li   t2, 1
    add  s3, s3, t2
.skip_0_0:
    bgez s3, .keep_0
    li   s3, 0
.keep_0:
    sd   s3, 0(s2)
    ld   s3, 8(s1)
    ld   t0, 0(s1)
    li   t1, 3
    blt  t0, t1, .skip_1_0
    li   t2, -1
    add  s3, s3, t2
.skip_1_0:
    bgez s3, .keep_1
    li   s3, 0
.keep_1:
    sd   s3, 8(s2)
    ld   t0, 8(s1)
    ld   t1, 8(s2)
    beq  t0, t1, .no_exit
    mv   a0, t1
    li   a7, 93
    ecall
.no_exit:
    ld   t0, 0(s2)
    sd   t0, 0(s1)
    ld   t0, 8(s2)
    sd   t0, 8(s1)
    j    .tick
# EXIT is the only halt a Container program has; EOF on input
# lands here, matching the interpreter's unwinding EOFError
.halt:
    li   a0, 0
    li   a7, 93
    ecall
    .data
    .align 3
con_cells:
    .dword 1
    .dword 1
    .dword 1
    .dword 1
