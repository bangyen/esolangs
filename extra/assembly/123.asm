global _start
_start:
	lea ecx, [esp - 1]
	xor ebx, ebx
	xor edi, edi
	mov esi, 128
	mov edx, 1
.input:
	mov eax, 3
	int 80h

	cmp eax, 1
	jl .done
	cmp byte [ecx], '|'
	je .done

	dec ecx
	jmp .input
.done:
	mov byte [ecx], '|'
	sub ecx, 4
	mov edx, esp
.parse:
	dec edx
	cmp byte [edx], '1'
	je .left
	cmp byte [edx], '2'
	je .right
	cmp byte [edx], '3'
	je .jump

	cmp byte [edx], '|'
	jne .parse
	cmp esi, 128
	jg .final

	mov edx, esp
	jmp .parse
.final:
	mov eax, 1
	mov ebx, 0
	int 80h

.left:
	xor edi, esi
	cmp esi, 1024
	jl .shift
	mov esi, 64
.shift:
	shl esi, 1
	jmp .parse

.right:
	cmp esi, 1024
	je .read
	cmp esi, 512
	je .write

	shr esi, 1
	jmp .parse
.read:
	push edx
	mov eax, 3
	xor ebx, ebx
	mov edx, 1
	int 80h
	pop edx

	mov edi, [ecx]
	mov esi, 128
	jmp .parse
.write:
	mov [ecx], edi
	push edx
	mov eax, 4
	mov ebx, 1
	mov edx, 1
	int 80h
	pop edx

	mov esi, 128
	jmp .parse

.jump:
	cmp esi, 128
	jg .parse

	mov eax, edi
	and eax, esi

	cmp eax, 0
	je .false
.true:
	inc edx
	cmp edx, esp
	je .parse
	cmp byte [edx], '3'
	je .parse
	jmp .true
.false:
	dec edx
	cmp byte [edx], '|'
	je .parse
	cmp byte [edx], '3'
	je .parse
	jmp .false
