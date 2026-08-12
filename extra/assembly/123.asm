; 123 interpreter (x86-32 Linux assembly cross-check; see README "Extra
; Implementations").
;
; A bit-tape language: `1` flips the current bit and moves the pointer left
; (wrapping from -4 back to 0), `2` reads a character into bits 0-7 when the
; pointer is at -3 or writes bits 0-7 as a character when at -2 (otherwise it
; moves the pointer right), and `3` is a jump symbol: when the current bit is
; TRUE the pointer skips back to the previous `3` (or the start), when FALSE
; it skips forward to the next `3` (or the end).  Bits start at FALSE and the
; program terminates only when the end is reached with the pointer below 0.
;
; Note: the program bytes are stored in a downward-growing buffer, so the
; instruction pointer `edx` walks DOWN through the source and `inc edx` moves
; BACK toward the start; the `3` branches match the wiki (back on TRUE,
; forward on FALSE).
;
; Invocation: `123 < stdin`; the program is read from stdin.
; Input/output: the program is read from stdin; `2` at -3 reads a byte and `2`
; at -2 writes one, in little-endian bit order per the wiki note.
;
; This is a direct syscall (int 80h) program with no libc; it is built with
; nasm -f elf32 and linked with ld -m elf_i386 by the CI extra-languages job.

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
