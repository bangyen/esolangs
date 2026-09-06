    .option norelax
    .text
    .global _start
_start:
    la   s1, ms_arena
    li   t0, 2228224
    add  s3, s1, t0
    li   s2, 0
    li   t3, 0
    mv   t4, s1
    li   t5, 528
    add  t5, t4, t5
    bgtu t5, s3, .abort
    mv   s1, t5
    sd   t3, 0(t4)
    sd   zero, 8(t4)
    mv   s2, t4
    mv   s6, sp
    mv   t1, s2
    li   t4, 0
.L1:
    beqz t1, .abort
    ld   t2, 8(t1)
    addi t3, t1, 16
    slli t2, t2, 4
    add  t2, t3, t2
.L2:
    beq  t2, t3, .L3
    addi t2, t2, -16
    ld   t5, 0(t2)
    bne  t5, t4, .L2
    ld   a0, 8(t2)
    j    .L4
.L3:
    ld   t1, 0(t1)
    j    .L1
.L4:
    call .autocall
.top_end:
    j    .halt
# invoke(callee: a0, args: a1, argc: a2) -> a0
.invoke:
    addi sp, sp, -32
    sd   ra, 0(sp)
    sd   s2, 8(sp)
    sd   a1, 16(sp)
    andi t0, a0, 7
    li   t1, 5
    bne  t0, t1, .abort
    srli t0, a0, 3
    slli t0, t0, 3
    ld   t2, 8(t0)
    bne  t2, a2, .abort
    ld   t3, 16(t0)
    ld   t0, 0(t0)
    mv   t4, s1
    li   t5, 528
    add  t5, t4, t5
    bgtu t5, s3, .abort
    mv   s1, t5
    sd   t3, 0(t4)
    sd   zero, 8(t4)
    mv   s2, t4
    ld   a1, 16(sp)
    j    .abort
.invoke_ret:
    ld   ra, 0(sp)
    ld   s2, 8(sp)
    addi sp, sp, 32
    ret
.alloc:
    addi a0, a0, 7
    andi a0, a0, -8
    mv   t0, s1
    add  t1, t0, a0
    bgtu t1, s3, .abort
    mv   s1, t1
    mv   a0, t0
    ret
.alloc_closure:
    addi sp, sp, -32
    sd   ra, 0(sp)
    sd   a0, 8(sp)
    sd   a1, 16(sp)
    li   a0, 24
    call .alloc
    ld   t0, 8(sp)
    sd   t0, 0(a0)
    ld   t0, 16(sp)
    sd   t0, 8(a0)
    sd   s2, 16(a0)
    ori  a0, a0, 5
    ld   ra, 0(sp)
    addi sp, sp, 32
    ret
.alloc_str:
    addi sp, sp, -16
    sd   ra, 0(sp)
    sd   a0, 8(sp)
    addi a0, a0, 8
    call .alloc
    ld   t0, 8(sp)
    sd   t0, 0(a0)
    ld   ra, 0(sp)
    addi sp, sp, 16
    ret
.alloc_arr:
    addi sp, sp, -16
    sd   ra, 0(sp)
    sd   a0, 8(sp)
    slli a0, a0, 3
    addi a0, a0, 8
    call .alloc
    ld   t0, 8(sp)
    sd   t0, 0(a0)
    ld   ra, 0(sp)
    addi sp, sp, 16
    ret
# autocall(value: a0) -> a0; call it if it is a nullary closure
.autocall:
    andi t0, a0, 7
    li   t1, 5
    bne  t0, t1, .autocall_ret
    srli t0, a0, 3
    slli t0, t0, 3
    ld   t1, 8(t0)
    bnez t1, .autocall_ret
    addi sp, sp, -16
    sd   ra, 0(sp)
    mv   a1, sp
    li   a2, 0
    call .invoke
    ld   ra, 0(sp)
    addi sp, sp, 16
.autocall_ret:
    ret
.num:
    andi t0, a0, 7
    li   t1, 0
    beq  t0, t1, .num_ok
    li   t1, 1
    bne  t0, t1, .abort
.num_ok:
    srai a0, a0, 3
    ret
.b_add:
    addi sp, sp, -16
    sd   ra, 0(sp)
    sd   a1, 8(sp)
    call .num
    mv   t5, a0
    ld   a0, 8(sp)
    sd   t5, 8(sp)
    call .num
    mv   t6, a0
    ld   t5, 8(sp)
    ld   ra, 0(sp)
    addi sp, sp, 16
    add  a0, t5, t6
    slli a0, a0, 3
    ret
.b_subtract:
    addi sp, sp, -16
    sd   ra, 0(sp)
    sd   a1, 8(sp)
    call .num
    mv   t5, a0
    ld   a0, 8(sp)
    sd   t5, 8(sp)
    call .num
    mv   t6, a0
    ld   t5, 8(sp)
    ld   ra, 0(sp)
    addi sp, sp, 16
    sub  a0, t5, t6
    slli a0, a0, 3
    ret
.b_multiply:
    addi sp, sp, -16
    sd   ra, 0(sp)
    sd   a1, 8(sp)
    call .num
    mv   t5, a0
    ld   a0, 8(sp)
    sd   t5, 8(sp)
    call .num
    mv   t6, a0
    ld   t5, 8(sp)
    ld   ra, 0(sp)
    addi sp, sp, 16
    addi sp, sp, -16
    sd   ra, 0(sp)
    mv   a0, t5
    mv   a1, t6
    call .mulint
    ld   ra, 0(sp)
    addi sp, sp, 16
    slli a0, a0, 3
    ret
.b_divide:
    addi sp, sp, -16
    sd   ra, 0(sp)
    sd   a1, 8(sp)
    call .num
    mv   t5, a0
    ld   a0, 8(sp)
    sd   t5, 8(sp)
    call .num
    mv   t6, a0
    ld   t5, 8(sp)
    ld   ra, 0(sp)
    addi sp, sp, 16
    beqz t6, .abort
    addi sp, sp, -16
    sd   ra, 0(sp)
    mv   a0, t5
    mv   a1, t6
    call .divint
    ld   ra, 0(sp)
    addi sp, sp, 16
    bnez a1, .abort
    slli a0, a0, 3
    ret
.mulint:
    mv   t0, a0
    mv   t1, a1
    li   a0, 0
.mul_loop:
    beqz t1, .mul_done
    andi t3, t1, 1
    beqz t3, .mul_skip
    add  a0, a0, t0
.mul_skip:
    slli t0, t0, 1
    srli t1, t1, 1
    j    .mul_loop
.mul_done:
    ret
.divint:
    li   t6, 0
    li   t4, 0
    bgez a0, .div_a_pos
    sub  a0, zero, a0
    xori t6, t6, 1
    li   t4, 1
.div_a_pos:
    bgez a1, .div_b_pos
    sub  a1, zero, a1
    xori t6, t6, 1
.div_b_pos:
    li   t0, 0
    li   t1, 0
    li   t2, 63
.div_loop:
    slli t1, t1, 1
    srl  t3, a0, t2
    andi t3, t3, 1
    or   t1, t1, t3
    slli t0, t0, 1
    bltu t1, a1, .div_skip
    sub  t1, t1, a1
    ori  t0, t0, 1
.div_skip:
    beqz t2, .div_done
    addi t2, t2, -1
    j    .div_loop
.div_done:
    mv   a0, t0
    mv   a1, t1
    beqz t4, .div_rem_done
    sub  a1, zero, a1
.div_rem_done:
    beqz t6, .div_ret
    sub  a0, zero, a0
.div_ret:
    ret
.b_equals:
    addi sp, sp, -16
    sd   ra, 0(sp)
    andi t0, a0, 7
    andi t1, a1, 7
    li   t2, 3
    bne  t0, t2, .eq_num
    bne  t1, t2, .eq_false
    call .streq
    j    .eq_out
.eq_num:
    call .numeric_pair
    beqz a0, .eq_ident
    bne  t5, t6, .eq_false
    j    .eq_true
.eq_ident:
    ld   ra, 0(sp)
    addi sp, sp, 16
    beq  a1, a2, .eq_ident_true
    andi t0, a1, 7
    li   t1, 4
    beq  t0, t1, .abort
    andi t0, a2, 7
    beq  t0, t1, .abort
    li   a0, 1
    ret
.eq_ident_true:
    li   a0, 9
    ret
.eq_true:
    li   a0, 9
    j    .eq_out
.eq_false:
    li   a0, 1
.eq_out:
    ld   ra, 0(sp)
    addi sp, sp, 16
    ret
.numeric_pair:
    mv   a2, a1
    mv   a1, a0
    andi t0, a1, 7
    andi t1, a2, 7
    li   t2, 4
    beq  t0, t2, .np_no
    li   t2, 3
    beq  t0, t2, .np_no
    li   t2, 5
    beq  t0, t2, .np_no
    li   t2, 2
    beq  t0, t2, .np_no
    li   t2, 4
    beq  t1, t2, .np_no
    li   t2, 3
    beq  t1, t2, .np_no
    li   t2, 5
    beq  t1, t2, .np_no
    li   t2, 2
    beq  t1, t2, .np_no
    srai t5, a1, 3
    srai t6, a2, 3
    li   a0, 1
    ret
.np_no:
    li   a0, 0
    ret
.streq:
    srli t0, a0, 3
    slli t0, t0, 3
    srli t1, a1, 3
    slli t1, t1, 3
    ld   t2, 0(t0)
    ld   t3, 0(t1)
    bne  t2, t3, .streq_no
    li   t4, 0
.streq_loop:
    beq  t4, t2, .streq_yes
    add  t5, t0, t4
    lbu  t5, 8(t5)
    add  t6, t1, t4
    lbu  t6, 8(t6)
    bne  t5, t6, .streq_no
    addi t4, t4, 1
    j    .streq_loop
.streq_yes:
    li   a0, 9
    ret
.streq_no:
    li   a0, 1
    ret
.b_less:
    addi sp, sp, -16
    sd   ra, 0(sp)
    sd   a1, 8(sp)
    call .num
    mv   t5, a0
    ld   a0, 8(sp)
    sd   t5, 8(sp)
    call .num
    mv   t6, a0
    ld   t5, 8(sp)
    ld   ra, 0(sp)
    addi sp, sp, 16
    blt  t5, t6, .less_yes
    li   a0, 1
    ret
.less_yes:
    li   a0, 9
    ret
.b_not:
    addi sp, sp, -16
    sd   ra, 0(sp)
    call .truthy
    ld   ra, 0(sp)
    addi sp, sp, 16
    bnez a0, .not_no
    li   a0, 9
    ret
.not_no:
    li   a0, 1
    ret
.truthy:
    andi t0, a0, 7
    li   t1, 1
    beq  t0, t1, .truthy_num
    li   t1, 0
    beq  t0, t1, .truthy_num
    li   t1, 3
    beq  t0, t1, .truthy_len
    li   t1, 4
    beq  t0, t1, .truthy_len
    li   a0, 1
    ret
.truthy_num:
    srai a0, a0, 3
    beqz a0, .truthy_no
    li   a0, 1
    ret
.truthy_len:
    srli t0, a0, 3
    slli t0, t0, 3
    ld   a0, 0(t0)
    beqz a0, .truthy_no
    li   a0, 1
    ret
.truthy_no:
    li   a0, 0
    ret
.b_concat:
    addi sp, sp, -32
    sd   ra, 0(sp)
    sd   a1, 8(sp)
    call .to_str
    sd   a0, 16(sp)
    ld   a0, 8(sp)
    call .to_str
    mv   t1, a0
    ld   t0, 16(sp)
    sd   t1, 24(sp)
    ld   t2, 0(t0)
    ld   t3, 0(t1)
    add  a0, t2, t3
    call .alloc_str
    sd   a0, 8(sp)
    ld   t0, 16(sp)
    ld   t2, 0(t0)
    li   t4, 0
.cat_a:
    beq  t4, t2, .cat_a_done
    add  t5, t0, t4
    lbu  t5, 8(t5)
    add  t6, a0, t4
    sb   t5, 8(t6)
    addi t4, t4, 1
    j    .cat_a
.cat_a_done:
    ld   t1, 24(sp)
    ld   t3, 0(t1)
    li   t4, 0
.cat_b:
    beq  t4, t3, .cat_b_done
    add  t5, t1, t4
    lbu  t5, 8(t5)
    add  t6, a0, t2
    add  t6, t6, t4
    sb   t5, 8(t6)
    addi t4, t4, 1
    j    .cat_b
.cat_b_done:
    ori  a0, a0, 3
    ld   ra, 0(sp)
    addi sp, sp, 32
    ret
.to_str:
    addi sp, sp, -16
    sd   ra, 0(sp)
    andi t0, a0, 7
    li   t1, 3
    beq  t0, t1, .to_str_same
    li   t1, 1
    beq  t0, t1, .to_str_bool
    li   t1, 0
    beq  t0, t1, .to_str_int
    li   t1, 2
    beq  t0, t1, .to_str_none
    j    .abort
.to_str_same:
    srli a0, a0, 3
    slli a0, a0, 3
    j    .to_str_ret
.to_str_bool:
    srai t0, a0, 3
    beqz t0, .to_str_no
    la   a0, .lit_yes
    j    .to_str_ret
.to_str_no:
    la   a0, .lit_no
    j    .to_str_ret
.to_str_none:
    la   a0, .lit_none
    j    .to_str_ret
.to_str_int:
    srai a0, a0, 3
    call .int_str
.to_str_ret:
    ld   ra, 0(sp)
    addi sp, sp, 16
    ret
.int_str:
    addi sp, sp, -48
    sd   ra, 0(sp)
    li   t0, 0
    bgez a0, .int_pos
    li   t0, 1
    sub  a0, zero, a0
.int_pos:
    sd   t0, 8(sp)
    sd   a0, 16(sp)
    li   t1, 1
    mv   t2, a0
.int_count:
    li   t3, 10
    bltu t2, t3, .int_counted
    mv   a0, t2
    li   a1, 10
    sd   t1, 24(sp)
    call .divint
    ld   t1, 24(sp)
    mv   t2, a0
    addi t1, t1, 1
    j    .int_count
.int_counted:
    ld   t0, 8(sp)
    add  a0, t1, t0
    sd   t1, 24(sp)
    call .alloc_str
    sd   a0, 32(sp)
    ld   t0, 8(sp)
    beqz t0, .int_nosign
    li   t1, 45
    sb   t1, 8(a0)
.int_nosign:
    ld   t1, 24(sp)
    ld   t2, 16(sp)
    ld   t0, 8(sp)
    add  t1, t1, t0
.int_digits:
    addi t1, t1, -1
    sd   t1, 40(sp)
    mv   a0, t2
    li   a1, 10
    call .divint
    ld   t1, 40(sp)
    ld   a2, 32(sp)
    addi a1, a1, 48
    add  t3, a2, t1
    sb   a1, 8(t3)
    mv   t2, a0
    ld   t0, 8(sp)
    ble  t1, t0, .int_done
    j    .int_digits
.int_done:
    ld   a0, 32(sp)
    ld   ra, 0(sp)
    addi sp, sp, 48
    ret
.b_arrlen:
    andi t0, a0, 7
    li   t1, 4
    bne  t0, t1, .abort
    srli t0, a0, 3
    slli t0, t0, 3
    ld   a0, 0(t0)
    slli a0, a0, 3
    ret
.b_itemat:
    andi t0, a0, 7
    li   t1, 4
    bne  t0, t1, .abort
    srli t0, a0, 3
    slli t0, t0, 3
    mv   a0, a1
    andi t1, a0, 7
    li   t2, 0
    beq  t1, t2, .item_ok
    li   t2, 1
    bne  t1, t2, .abort
.item_ok:
    srai a0, a0, 3
    bltz a0, .abort
    ld   t1, 0(t0)
    bge  a0, t1, .abort
    slli a0, a0, 3
    add  t0, t0, a0
    ld   a0, 8(t0)
    ret
.b_say:
    addi sp, sp, -16
    sd   ra, 0(sp)
    call .to_str
    ld   a2, 0(a0)
    addi a1, a0, 8
    li   a7, 64
    li   a0, 1
    ecall
    ld   ra, 0(sp)
    addi sp, sp, 16
    li   a0, 2
    ret
# every HaltError site lands here; the interpreter unwinds the
# whole run, and the other compilers exit 0 on a halt
.abort:
.halt:
    li   a0, 0
    li   a7, 93
    ecall
    .section .rodata
    .align 3
    .align 3
.lit_yes:
    .dword 3
    .byte 121
    .byte 101
    .byte 115
    .align 3
.lit_no:
    .dword 2
    .byte 110
    .byte 111
    .align 3
.lit_none:
    .dword 4
    .byte 78
    .byte 111
    .byte 110
    .byte 101
    .bss
    .align 3
ms_arena:
    .space 2228224
