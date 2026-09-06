    .text
    .global _start
_start:
    li   t0, -2304
    add  sp, sp, t0
    li   s1, 0
    li   s2, 0
    mv   s3, sp
    addi s4, sp, 1024
    li   t0, 2048
    add  s6, sp, t0
    li   s5, 0
    j    .L0
.done:
    la   a1, str_z
    call print_str
    mv   a0, s1
    call print_dec
    la   a1, str_nl
    call print_str
    la   a1, str_n
    call print_str
    mv   a0, s2
    call print_dec
    la   a1, str_nl
    call print_str
    beqz s5, .ram_empty
    la   a1, str_ram
    call print_str
    li   s8, 0
.ram_loop:
    bge  s8, s5, .ram_done
    slli t1, s8, 2
    add  t1, s4, t1
    lw   s7, 0(t1)
    la   a1, str_sp
    call print_str
    mv   a0, s7
    call print_dec
    la   a1, str_col
    call print_str
    slli t1, s7, 2
    add  t1, s3, t1
    lw   a0, 0(t1)
    call print_dec
    addi t1, s8, 1
    blt  t1, s5, .ram_comma
    la   a1, str_nl
    j    .ram_next
.ram_comma:
    la   a1, str_comma
.ram_next:
    call print_str
    addi s8, s8, 1
    j    .ram_loop
.ram_done:
    la   a1, str_end
    call print_str
    j    .exit
.ram_empty:
    la   a1, str_ram_empty
    call print_str
.exit:
    li   a0, 0
    li   a7, 93
    ecall

# print the null-terminated string at a1
print_str:
    mv   t3, a1
    mv   t2, a1
1:
    lbu  t4, 0(t2)
    beqz t4, 2f
    addi t2, t2, 1
    j    1b
2:
    sub  a2, t2, t3
    li   a7, 64
    li   a0, 1
    ecall
    ret

# print a0 in decimal (software division by 10: rv64i has no M)
print_dec:
    addi sp, sp, -64
    sd   ra, 56(sp)
    li   t0, 0
    bnez a0, 1f
    li   t5, 48
    sb   t5, 0(sp)
    mv   a1, sp
    li   a2, 1
    li   a7, 64
    li   a0, 1
    ecall
    ld   ra, 56(sp)
    addi sp, sp, 64
    ret
1:
    li   t1, 10
2:
    call div_u
    addi t5, t5, 48
    add  t6, sp, t0
    sb   t5, 0(t6)
    addi t0, t0, 1
    bnez a0, 2b
3:
    addi t0, t0, -1
    add  a1, sp, t0
    li   a2, 1
    li   a7, 64
    li   a0, 1
    ecall
    bnez t0, 3b
    ld   ra, 56(sp)
    addi sp, sp, 64
    ret

# a0 / t1 -> a0 quotient, t5 remainder (unsigned 64-bit)
div_u:
    mv   t6, a0
    li   a0, 0
    li   t5, 0
    li   t2, 64
1:
    slli t5, t5, 1
    srli t3, t6, 63
    or   t5, t5, t3
    slli t6, t6, 1
    bltu t5, t1, 2f
    sub  t5, t5, t1
    ori  a0, a0, 1
2:
    addi t2, t2, -1
    beqz t2, 3f
    slli a0, a0, 1
    j    1b
3:
    ret

    .section .rodata
str_z:  .asciz "z: "
str_n:  .asciz "n: "
str_nl: .asciz "\n"
str_ram: .asciz "ram: {\n"
str_ram_empty: .asciz "ram: {}"
str_sp: .asciz "    "
str_col: .asciz ": "
str_comma: .asciz ",\n"
str_end: .asciz "}"
