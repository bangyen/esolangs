# Annotated walkthrough: AddSubJump (an OISC)

`AddSubJump` is a one-instruction-set computer: its only instruction is
`ASJ a b c d`, meaning "if the cell `*d` is positive then `*a -= *b`, else
`*a += *b`; then go to `*c`".  The source is a flat list of integers that
serves as both the program and its own memory: the instruction at address
`ip` is the four cells `memory[ip]..memory[ip+3]`.  A few addresses are
special: `-1` is I/O (writing to it prints a byte), `-6`/`-7`/`-8` are the
constants `1`/`0`/`-1`, and jumping to any special address halts the
program.

## The program

```
-1 4 -8 -7 65
```

This prints the byte held in cell 4 (the literal `65`, which is `'A'`) and
then halts.

## Step by step

Memory is `[-1, 4, -8, -7, 65]` at addresses `0..4`, and `ip` starts at 0.

| Cell | Contents | Meaning |
| --- | --- | --- |
| 0 | `-1` | `a`: write to `-1`, which prints. |
| 1 | `4` | `b`: read cell 4 (the `65`). |
| 2 | `-8` | `c`: the jump target; `-8` reads as the constant `-1`. |
| 3 | `-7` | `d`: `*d`; `-7` reads as the constant `0`. |
| 4 | `65` | data: the byte that gets printed. |

The interpreter executes the single instruction at address 0:

1. `a` is `-1`, the I/O port, so the interpreter skips add/subtract
   entirely and writes `*b = *(4) = 65` straight through.  Writing to `-1`
   prints the value being written, so the byte `65` (`'A'`) is output.
2. Go to `*c = *(-8) = -1`.  Address `-1` is special, so the program halts.

## Why it terminates

The jump target resolves to a special address (`-1`), which the interpreter
treats as the halt condition — the program does not fall off into
uninitialised memory or loop back.
