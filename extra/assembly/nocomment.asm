; NoComment interpreter (x86-32 Linux assembly cross-check; see README "Extra
; Implementations").
;
; The full wiki language: a byte tape with a movable pointer, plus a byte
; stack.  `i`/`d` increment/decrement the current cell, `c` clears it,
; `l`/`r` move the pointer (left is a no-op at cell 0, right extends the
; tape), `n` pushes the current cell, `f` pops into it, `s`/`b` jump
; forward/backward by the top-of-stack amount when the current cell is
; nonzero (`s` skips X instructions, `b` jumps back X-1), and `o` prints
; the current cell as a byte.
;
; Per the wiki, errors are an unrecognized command, stack underflow, or a
; jump outside the code; each exits non-zero.  The in-package Python
; interpreter implements the same full language.
;
; Input: the program is read from stdin (the wiki has no input command);
; the tape is not printed.
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
	jne .error
.final:
	mov eax, 1
	xor ebx, ebx
	int 80h

.error:
	; unrecognized command, stack underflow, or a jump out of range: exit
	; non-zero (the wiki requires errors to terminate with a failure status)
	mov eax, 1
	mov ebx, 1
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
	je .error
	mov al, [edx]
	add edx, 2
	mov [ecx], al
	jmp .parse
.fore:
	cmp byte [ecx], 0
	je .parse
	movzx eax, byte [edx]
	sub edi, eax
	; the target (edi, before .parse's dec) must lie in [esi, esp-4]
	lea eax, [esp - 4]
	cmp edi, eax
	jg .error
	cmp edi, esi
	jl .error
	jmp .parse
.back:
	cmp byte [ecx], 0
	je .parse
	movzx eax, byte [edx]
	add edi, eax
	lea eax, [esp - 4]
	cmp edi, eax
	jg .error
	cmp edi, esi
	jl .error
	jmp .parse
.output:
	push edx
	mov eax, 4
	mov ebx, 1
	mov edx, 1
	int 80h
	pop edx
	jmp .parse
