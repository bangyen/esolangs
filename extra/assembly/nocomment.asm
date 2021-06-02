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
	je .out

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
.out:
	push edx
	mov eax, 4
	mov ebx, 1
	mov edx, 1
	int 80h
	pop edx
	jmp .parse