; NoComment interpreter (x86-32 Linux assembly cross-check; see README "Extra
; Implementations").
;
; A brainfuck-like tape language (bytes, wrapping) with a byte stack.  `i`/`d`
; increment/decrement the current cell, `c` clears it, `l`/`r` move the
; pointer, `n` pushes the current cell, `f` pops into it, `s`/`b` jump
; forward/backward by the top-of-stack amount when the current cell is
; nonzero, and `o` prints the current cell as a byte.  Every character must be
; a command; anything else is an error.
;
; Note: the in-package Python interpreter implements only the `c`/`i`/`o`
; subset (a single cell, no stack or jumps) for its text generator; this
; assembly implements the full wiki command set.  Stack underflow, an
; unrecognized command, or a jump out of range are errors.
;
; Input: the program is read from stdin (the wiki has no input command); the
; tape is not printed.
;
; This is a direct syscall (int 80h) program with no libc; it is built with
; nasm -f elf32 and linked with ld -m elf_i386 by the CI extra-languages job.

global _start
_start:
	lea ecx, [esp - 5]
	xor ebx, ebx
	mov edx, 1
.input:
	mov eax, 3
	int 80h
	dec ecx

	cmp eax, 1
	jl .done
	jmp .input
.done:
	mov byte [ecx], 0
	mov edx, ecx
	mov esi, ecx
	dec ecx
	lea edi, [esp - 4]
.parse:
	dec edi
	cmp byte [edi], 'i'
	je .up
	cmp byte [edi], 'd'
	je .down
	cmp byte [edi], 'c'
	je .zero
	cmp byte [edi], 'l'
	je .left
	cmp byte [edi], 'r'
	je .right
	cmp byte [edi], 'n'
	je .on
	cmp byte [edi], 'f'
	je .off
	cmp byte [edi], 's'
	je .fore
	cmp byte [edi], 'b'
	je .back
	cmp byte [edi], 'o'
	je .output

	cmp byte [edi], 0
	jne .parse
.final:
	mov eax, 1
	xor ebx, ebx
	int 80h

.up:
	inc byte [ecx]
	jmp .parse
.down:
	dec byte [ecx]
	jmp .parse
.zero:
	mov byte [ecx], 0
	jmp .parse
.left:
	add ecx, 2
	cmp ecx, esi
	jl .parse
.right:
	sub ecx, 2
	jmp .parse
.on:
	mov al, [ecx]
	sub edx, 2
	mov [edx], al
	jmp .parse
.off:
	cmp edx, esi
	je .parse
	mov al, [edx]
	add edx, 2
	mov [ecx], al
	jmp .parse
.fore:
	cmp byte [ecx], 0
	je .parse
	movzx eax, byte [edx]
	sub edi, eax
	jmp .parse
.back:
	cmp byte [ecx], 0
	je .parse
	movzx eax, byte [edx]
	add edi, eax
	jmp .parse
.output:
	push edx
	mov eax, 4
	mov ebx, 1
	mov edx, 1
	int 80h
	pop edx
	jmp .parse
