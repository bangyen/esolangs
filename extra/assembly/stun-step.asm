global _start
_start:
	lea ecx, [esp - 20]
	xor ebx, ebx
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
	dec dword [ecx]
	lea edx, [esp - 19]
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

	lea edx, [esp - 19]
	cmp dword [ecx], 0
	jge .parse

	mov ecx, eax
.state:
	inc dword [ecx]
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
	xor ebx, ebx
	int 80h

.plus:
	inc dword [ecx]
	jmp .parse
.minus:
	cmp dword [ecx], -1
	je .parse
	dec dword [ecx]
	jmp .parse
.right:
	cmp dword [ecx], -1
	je .parse
	inc esi
	sub ecx, 4
	cmp edi, esi
	jge .parse
	inc edi
	jmp .parse
.left:
	cmp ecx, edi
	je .parse
	cmp dword [ecx], -1
	je .parse
	dec esi
	add ecx, 4
	jmp .parse

output:
	push edi
	mov edi, [ecx]
	mov eax, 10
.max:
	cmp eax, edi
	jg .main
	mov ebx, 10
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
