; 2 Bits, 1 Byte interpreter (x86-32 Linux assembly cross-check; see README
; "Extra Implementations").
;
; Reads a single byte of input and interprets its 8 bits as 4 two-bit
; commands: command 0 advances, command 1 applies a bitwise operation
; (XOR with the addressed bit, or a shift-based combine for the second
; operand), and command 2 reads an indexed bit.  The resulting byte is
; printed and the program halts.
;
; This is a direct syscall (int 80h) program with no libc; it is built with
; nasm -f elf32 and linked with ld -m elf_i386 by the CI extra-languages job.
; The input byte is read from stdin.

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
