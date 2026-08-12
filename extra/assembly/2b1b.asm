; 2 Bits, 1 Byte interpreter (x86-32 Linux assembly cross-check; see README
; "Extra Implementations").
;
; The program is a single byte whose 8 bits form four two-bit instructions,
; executed in sequence with the instruction pointer wrapping: 00 = DON (do
; nothing), 01 = ACT (apply a bitwise operation to the byte), 10 = JMP (jump,
; honoring the wrap), and 11 = END (print the byte as a character and halt).
;
; The program byte is read from stdin (the language has no file-based I/O
; protocol; see the README note).  The ACT instruction here is implemented
; as bit toggles / shift-combines rather than the wiki's 00->11, 01->10,
; 10->00, 11->01 value table.
;
; This is a direct syscall (int 80h) program with no libc; it is built with
; nasm -f elf32 and linked with ld -m elf_i386 by the CI extra-languages job.

global _start
_start:
	mov eax, 3
	xor ebx, ebx
	lea ecx, [esp - 1]
	mov edx, 1
	int 80h

	mov al, [ecx]
	mov bl, 3
	mov cl, 8
.parse:
	call num

	cmp dl, 0
	je .parse
	cmp dl, 1
	je .one
	cmp dl, 2
	je .two

	lea ecx, [esp - 1]
	mov [ecx], al

	mov eax, 4
	mov ebx, 1
	mov edx, 1
	int 80h

	mov eax, 1
	xor ebx, ebx
	int 80h

.one:
	call num
	push bx
	push cx
	call ind
	call num
	cmp dl, 1
	jg .above

	xor al, bl
	jmp .done
.above:
	mov dl, bl
	shl dl, 1
	and dl, bl
	xor al, dl
.done:
	pop cx
	pop bx
	jmp .parse

.two:
	call num
	call ind
	jmp .parse

num:
	sub cl, 2
	and cl, 7
	ror bl, 2

	mov dl, bl
	and dl, al
	shr dl, cl
	ret

ind:
	mov cl, dl
	shl cl, 1
	sub cl, 8
	neg cl

	mov bl, 3
	shl bl, cl
	ret
