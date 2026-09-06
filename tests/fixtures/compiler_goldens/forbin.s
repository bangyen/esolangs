    .option norelax
    .text
    .global _start
_start:
    la   s1, forbin_arena
    li   t0, 274432
    add  s3, s1, t0
    li   s2, 0
    addi sp, sp, -16
    sd   zero, 0(sp)
    li   a0, 3
    mv   a1, sp
    li   a2, 1
    call .dispatch
    j    .halt
# dispatch(callee: a0, args: a1, argc: a2) -> a0
.dispatch:
    addi sp, sp, -32
    sd   ra, 0(sp)
    sd   s2, 8(sp)
    li   t0, -2
    beq  a0, t0, .do_in
    li   t0, -4
    beq  a0, t0, .do_out
    andi t0, a0, 1
    beqz t0, .abort
    srli t0, a0, 1
    addi t0, t0, -1
    bltz t0, .abort
    mv   t3, s1
    li   t4, 536
    add  t4, t3, t4
    bgtu t4, s3, .abort
    mv   s1, t4
    sd   s2, 0(t3)
    sd   zero, 8(t3)
    sd   zero, 16(t3)
    mv   s2, t3
    li   t1, 0
    beq  t0, t1, .body0
    j    .abort
.body0:
    call .fn0
    j    .dispatch_ret
.dispatch_ret:
    ld   ra, 0(sp)
    ld   s2, 8(sp)
    addi sp, sp, 32
    ret
.do_in:
    la   t0, forbin_bitcount
    ld   t1, 0(t0)
    bnez t1, .have_bits
    call .readline
    la   t3, forbin_bitbuf
    sd   a0, 0(t3)
    li   t1, 8
.have_bits:
    addi t1, t1, -1
    la   t0, forbin_bitcount
    sd   t1, 0(t0)
    la   t3, forbin_bitbuf
    ld   t2, 0(t3)
    srl  a0, t2, t1
    andi a0, a0, 1
    j    .dispatch_ret
.readline:
    addi sp, sp, -32
    sd   ra, 0(sp)
    sd   s4, 8(sp)
    li   a7, 63
    li   a0, 0
    addi a1, sp, 16
    li   a2, 1
    ecall
    blez a0, .halt
    lbu  s4, 16(sp)
    li   t0, 10
    beq  s4, t0, .readline_done
.readline_skip:
    li   a7, 63
    li   a0, 0
    addi a1, sp, 16
    li   a2, 1
    ecall
    blez a0, .readline_done
    lbu  t1, 16(sp)
    li   t0, 10
    bne  t1, t0, .readline_skip
.readline_done:
    mv   a0, s4
    ld   ra, 0(sp)
    ld   s4, 8(sp)
    addi sp, sp, 32
    ret
.do_out:
    li   t0, 8
    bne  a2, t0, .abort
    li   t1, 0
    li   t2, 0
.out_loop:
    li   t3, 8
    beq  t2, t3, .out_done
    li   t4, 7
    sub  t4, t4, t2
    slli t4, t4, 4
    add  t4, a1, t4
    ld   t5, 0(t4)
    li   t6, 1
    bgtu t5, t6, .abort
    slli t1, t1, 1
    add  t1, t1, t5
    addi t2, t2, 1
    j    .out_loop
.out_done:
    addi sp, sp, -16
    sb   t1, 0(sp)
    li   a7, 64
    li   a0, 1
    mv   a1, sp
    li   a2, 1
    ecall
    addi sp, sp, 16
    li   a0, 0
    j    .dispatch_ret
# every HaltError site lands here; the interpreter unwinds the
# whole run, and the other compilers exit 0 on a halt
.abort:
.halt:
    li   a0, 0
    li   a7, 93
    ecall
# function main (index 0)
.fn0:
    addi sp, sp, -48
    sd   ra, 0(sp)
    sd   s6, 8(sp)
    sd   s4, 16(sp)
    sd   s5, 24(sp)
    mv   s6, sp
    mv   t1, s2
    li   t4, 0
.L1:
    beqz t1, .L7
    ld   t2, 16(t1)
    addi t3, t1, 24
    slli t2, t2, 4
    add  t2, t3, t2
.L2:
    beq  t2, t3, .L3
    addi t2, t2, -16
    ld   t5, 0(t2)
    bne  t5, t4, .L2
    ld   a0, 8(t2)
    j    .L6
.L3:
    ld   t2, 8(t1)
    beqz t2, .L5
.L4:
    ld   t5, 0(t2)
    bltz t5, .L5
    addi t2, t2, 16
    bne  t5, t4, .L4
    ld   a0, -8(t2)
    j    .L6
.L5:
    ld   t1, 0(t1)
    j    .L1
.L7:
    li   a0, -4
.L6:
    addi sp, sp, -16
    sd   a0, 0(sp)
    li   a0, 0
    addi sp, sp, -16
    sd   a0, 0(sp)
    li   a0, 1
    addi sp, sp, -16
    sd   a0, 0(sp)
    li   a0, 0
    addi sp, sp, -16
    sd   a0, 0(sp)
    li   a0, 0
    addi sp, sp, -16
    sd   a0, 0(sp)
    li   a0, 1
    addi sp, sp, -16
    sd   a0, 0(sp)
    li   a0, 0
    addi sp, sp, -16
    sd   a0, 0(sp)
    li   a0, 0
    addi sp, sp, -16
    sd   a0, 0(sp)
    li   a0, 0
    addi sp, sp, -16
    sd   a0, 0(sp)
    ld   a0, 128(sp)
    mv   a1, sp
    li   a2, 8
    call .dispatch
    addi sp, sp, 144
    li   a0, 0
.ret0:
    mv   sp, s6
    ld   ra, 0(sp)
    ld   s6, 8(sp)
    ld   s4, 16(sp)
    ld   s5, 24(sp)
    addi sp, sp, 48
    ret
    .bss
    .align 3
forbin_bitbuf:
    .space 8
forbin_bitcount:
    .space 8
forbin_arena:
    .space 274432
