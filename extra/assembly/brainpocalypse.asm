; Brainpocalypse interpreter (x86-32 Linux assembly cross-check; see README
; "Extra Implementations").
;
; A tape language where cells hold integers: `+`/`-` increment/decrement the
; current cell, `>`/`<` move the pointer, and `-` on a zero cell restarts the
; program from the beginning (the `.goto` path rewinds to the start of the
; parsed input).  When the input is exhausted the whole tape is printed as
; space-separated decimal values.
;
; This is a direct syscall (int 80h) program with no libc; it is built with
; nasm -f elf32 and linked with ld -m elf_i386 by the CI extra-languages job.
; The program is read from stdin.

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
