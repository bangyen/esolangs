    .text
    .option norelax
    .global _start
_start:
    li   s1, 0
    la   s2, cvnc_deque
    li   s3, 0
    li   s4, 0
    la   s5, cvnc_function
    li   s6, 0
    li   s7, 0
.t0:
    li   s6, 0
.t1:
    addi s1, s1, 1
.t2:
    li   s6, 0
.t3:
    addi s1, s1, 1
.halt:
    li   a0, 0
    li   a7, 93
    ecall
.unwind:
    la   t0, cvnc_sp
    ld   sp, 0(t0)
    j    .invalid
# dispatch(t1 = token index) -- jump to that token's code
dispatch:
    la   t2, cvnc_ntokens
    ld   t2, 0(t2)
    bgeu t1, t2, .halt
    la   t3, cvnc_labels
    slli t4, t1, 3
    add  t3, t3, t4
    ld   t3, 0(t3)
    jr   t3
# push_front(a0) / push_back(a0); pop_front() / pop_back() -> a0
# A circular buffer indexed by (s3 + i) % _DEQUE, so both ends are
# O(1); overflow aborts rather than wrapping onto live entries.
push_front:
    li   t0, 4096
    bgeu s4, t0, .halt
    addi s3, s3, -1
    bgez s3, 1f
    li   s3, 4095
1:
    slli t1, s3, 3
    add  t1, s2, t1
    sd   a0, 0(t1)
    addi s4, s4, 1
    ret
push_back:
    li   t0, 4096
    bgeu s4, t0, .halt
    add  t1, s3, s4
    bltu t1, t0, 1f
    sub  t1, t1, t0
1:
    slli t1, t1, 3
    add  t1, s2, t1
    sd   a0, 0(t1)
    addi s4, s4, 1
    ret
pop_front:
    beqz s4, .halt
    slli t1, s3, 3
    add  t1, s2, t1
    ld   a0, 0(t1)
    addi s3, s3, 1
    li   t0, 4096
    bltu s3, t0, 1f
    li   s3, 0
1:
    addi s4, s4, -1
    ret
pop_back:
    beqz s4, .halt
    add  t1, s3, s4
    addi t1, t1, -1
    li   t0, 4096
    bltu t1, t0, 1f
    sub  t1, t1, t0
1:
    slli t1, t1, 3
    add  t1, s2, t1
    ld   a0, 0(t1)
    addi s4, s4, -1
    ret
# fn_append(tag: a0, value: a1) -- push one function symbol
fn_append:
    li   t0, 4096
    bgeu s6, t0, .halt
    slli t1, s6, 4
    add  t1, s5, t1
    sd   a0, 0(t1)
    sd   a1, 8(t1)
    addi s6, s6, 1
    ret
# mul64(a0, a1) -> a0, unsigned shift-and-add
mul64:
    mv   t0, a0
    li   a0, 0
1:
    beqz a1, 3f
    andi t1, a1, 1
    beqz t1, 2f
    add  a0, a0, t0
2:
    slli t0, t0, 1
    srli a1, a1, 1
    j    1b
3:
    ret
# divu64(a0, a1) -> a0 quotient; a1 == 0 is the caller's problem
divu64:
    li   t0, 0
    li   t1, 0
    li   t2, 63
1:
    slli t1, t1, 1
    srl  t3, a0, t2
    andi t3, t3, 1
    or   t1, t1, t3
    slli t0, t0, 1
    bltu t1, a1, 2f
    sub  t1, t1, a1
    ori  t0, t0, 1
2:
    beqz t2, 3f
    addi t2, t2, -1
    j    1b
3:
    mv   a0, t0
    ret
# isqrt64(a0) -> a0, the restoring bit-at-a-time integer root
isqrt64:
    mv   t0, a0
    li   a0, 0
    li   t1, 1
    slli t1, t1, 62
1:
    bltu t0, t1, 3f
    j    2f
3:
    beqz t1, 4f
    srli t1, t1, 2
    j    1b
2:
    beqz t1, 5f
    add  t2, a0, t1
    bltu t0, t2, 6f
    sub  t0, t0, t2
    srli a0, a0, 1
    add  a0, a0, t1
    j    7f
6:
    srli a0, a0, 1
7:
    srli t1, t1, 2
    j    2b
4:
5:
    ret
# apply() -- s1 = function(s1), or unchanged if it does not parse
apply:
    addi sp, sp, -16
    sd   ra, 0(sp)
    sd   s7, 8(sp)
    la   t0, cvnc_sp
    sd   sp, 0(t0)
    li   s7, 0
    beqz s6, .invalid
    call expr
    bne  s7, s6, .invalid
    mv   s1, a0
    ld   ra, 0(sp)
    ld   s7, 8(sp)
    addi sp, sp, 16
    ret
.invalid:
    ld   ra, 0(sp)
    ld   s7, 8(sp)
    addi sp, sp, 16
    ret
# peek() -> a0 = tag at s7, or -1 past the end
peek:
    li   a0, -1
    bgeu s7, s6, 1f
    slli t0, s7, 4
    add  t0, s5, t0
    ld   a0, 0(t0)
1:
    ret
# expr() -> a0; a sum of terms, left to right
expr:
    addi sp, sp, -32
    sd   ra, 0(sp)
    call term
    sd   a0, 8(sp)
1:
    call peek
    li   t0, 1
    beq  a0, t0, 2f
    li   t0, 2
    bne  a0, t0, 4f
2:
    sd   a0, 16(sp)
    addi s7, s7, 1
    call term
    ld   t1, 8(sp)
    ld   t2, 16(sp)
    li   t0, 1
    bne  t2, t0, 3f
    add  t1, t1, a0
    sd   t1, 8(sp)
    j    1b
3:
    bltu t1, a0, 5f
    sub  t1, t1, a0
    sd   t1, 8(sp)
    j    1b
5:
    sd   zero, 8(sp)
    j    1b
4:
    ld   a0, 8(sp)
    ld   ra, 0(sp)
    addi sp, sp, 32
    ret
# term() -> a0; a product of factors, left to right
term:
    addi sp, sp, -32
    sd   ra, 0(sp)
    call factor
    sd   a0, 8(sp)
1:
    call peek
    li   t0, 3
    beq  a0, t0, 2f
    li   t0, 4
    bne  a0, t0, 4f
2:
    sd   a0, 16(sp)
    addi s7, s7, 1
    call factor
    ld   t2, 16(sp)
    mv   a1, a0
    ld   a0, 8(sp)
    li   t0, 3
    bne  t2, t0, 3f
    call mul64
    sd   a0, 8(sp)
    j    1b
3:
    beqz a1, .halt
    call divu64
    sd   a0, 8(sp)
    j    1b
4:
    ld   a0, 8(sp)
    ld   ra, 0(sp)
    addi sp, sp, 32
    ret
# factor() -> a0; `a`, a literal, or a parenthesized expression
factor:
    addi sp, sp, -16
    sd   ra, 0(sp)
    call peek
    li   t0, 0
    bne  a0, t0, 1f
    addi s7, s7, 1
    mv   a0, s1
    j    9f
1:
    li   t0, 7
    bne  a0, t0, 2f
    slli t0, s7, 4
    add  t0, s5, t0
    ld   a0, 8(t0)
    addi s7, s7, 1
    j    9f
2:
    li   t0, 5
    bne  a0, t0, 8f
    addi s7, s7, 1
    call expr
    sd   a0, 8(sp)
    call peek
    li   t0, 6
    bne  a0, t0, 8f
    addi s7, s7, 1
    ld   a0, 8(sp)
    j    9f
8:
    ld   ra, 0(sp)
    addi sp, sp, 16
    j    .unwind
9:
    ld   ra, 0(sp)
    addi sp, sp, 16
    ret
    .data
    .align 3
cvnc_ntokens:
    .dword 4
cvnc_noffsets:
    .dword 4
cvnc_nstarts:
    .dword 2
cvnc_labels:
    .dword .t0
    .dword .t1
    .dword .t2
    .dword .t3
cvnc_offsets:
    .dword 0
    .dword 1
    .dword 2
    .dword 3
cvnc_starts:
    .dword 0
    .dword 2
    .align 3
cvnc_deque:
    .zero 32768
cvnc_function:
    .zero 65536
cvnc_line:
    .zero 64
cvnc_digits:
    .zero 32
cvnc_sp:
    .zero 8
