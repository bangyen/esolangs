; Brainpocalypse interpreter (x86-32 Linux assembly cross-check; see README
; "Extra Implementations").
;
; A brainfuck-like tape language (256 cells, wrapping): `+`/`-` increment/
; decrement the current cell, `>`/`<` move the pointer, and `-` on a zero
; cell rewinds the instruction pointer to the start of the program (the
; wiki's flow-control rule).  Cells hold nonnegative integers.
;
; The wiki defines no I/O; this implementation reads the program from stdin
; and prints the whole tape as space-separated decimal values when the input
; is exhausted — an output decision, not a language rule.
;
; This is a direct syscall (int 80h) program with no libc; it is built with
; nasm -f elf32 and linked with ld -m elf_i386 by the CI extra-languages job.

global _start
_start:
	lea ecx, [esp - 16]
	mov ebx, 0
	mov edx, 1
	mov edi, 1
	mov esi, 1
.input:
	mov eax, 3
	int 80h
	dec ecx
	cmp eax, 0
	jg .input

	mov byte [ecx], 0
	sub ecx, 4
	mov eax, ecx
	lea edx, [esp - 15]
.parse:
	dec edx
	cmp byte [edx], '+'
	je .plus
	cmp byte [edx], '-'
	je .minus
	cmp byte [edx], '>'
	je .right
	cmp byte [edx], '<'
	je .left

	cmp byte [edx], 0
	jne .parse

	mov ecx, eax
.state:
	call output
	dec edi
	cmp edi, 0
	je .final

	mov dword [ecx], ' '
	call print
	sub ecx, 4
	jmp .state
.final:
	mov eax, 1
	mov ebx, 0
	int 80h

.plus:
	inc dword [ecx]
	jmp .parse
.minus:
	cmp dword [ecx], 0
	je .goto
	dec dword [ecx]
	jmp .parse
.right:
	sub ecx, 4
	inc esi
	cmp edi, esi
	jge .parse

	inc edi
	jmp .parse
.left:
	cmp ecx, edi
	je .parse

	dec esi
	add ecx, 4
	jmp .parse
.goto:
	lea edx, [esp - 15]
	jmp .parse

output:
	push edi
	mov edi, [ecx]
	mov eax, 10
.max:
	cmp eax, edi
	jg .main
	mov ebx, 10
	xor edx, edx
	mul ebx
	jmp .max
.main:
	mov ebx, 10
	xor edx, edx
	div ebx

	xchg eax, edi
	xor edx, edx
	div edi
	mov [ecx], eax
	mov eax, edx
	xchg eax, edi

	add dword [ecx], '0'
	call print
	sub dword [ecx], '0'

	cmp eax, 1
	jne .main
	pop edi
	ret

print:
	push eax
	mov eax, 4
	mov ebx, 1
	mov edx, 1
	int 80h
	pop eax
	ret
