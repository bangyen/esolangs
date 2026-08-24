# Annotated walkthrough: brainfuck (a tape language)

`brainfuck` keeps a tape of byte cells and a data pointer.  The eight
commands are `>`/`<` (move the pointer right/left), `+`/`-` (increment/
decrement the current cell), `.` (print the current cell as a byte), `,`
(read a byte into the current cell), and `[`/`]` (loop while the current
cell is nonzero — `[` jumps past the matching `]` when the cell is zero,
`]` jumps back when it is nonzero).  Cells start at 0 and wrap at 8 bits.

## The program

```
++++++++[>++++++++<-]>+.
```

This sets cell 0 to 8, runs a loop that adds 8 to cell 1 on each of the
eight passes (so cell 1 ends at `8 × 8 = 64`), then adds one more and
prints cell 1 — the byte 65, which is `'A'`.

## Step by step

The pointer starts at cell 0 and every cell holds 0.

| Command | State after | Why |
| --- | --- | --- |
| `++++++++` | cell 0 = 8 | eight `+`s increment the current cell. |
| `[` | enter the loop | cell 0 is nonzero, so the body runs. |
| `>` | pointer at cell 1 | `>` moves the data pointer right. |
| `++++++++` | cell 1 = 8 | eight `+`s increment the new current cell. |
| `<` | pointer at cell 0 | `<` moves the data pointer back. |
| `-` | cell 0 = 7 | `-` decrements the loop counter. |
| `]` | back to `[` | cell 0 is still nonzero, so the loop repeats. |
| *(passes 2-7)* | cell 1 = 16, 24, 32, 40, 48, 56 | each pass adds 8 to cell 1 and takes 1 off cell 0. |
| `>` `++++++++` `<` `-` | cell 1 = 64, cell 0 = 0 | the eighth and last pass. |
| `]` | exit the loop | cell 0 is now 0, so `]` falls through. |
| `>` | pointer at cell 1 | `>` moves right to the accumulated result. |
| `+` | cell 1 = 65 | one more increment: `8 × 8 + 1 = 65`. |
| `.` | prints `A` | `.` prints the current cell as a byte; 65 is `'A'`. |

Multiplication is the idiom to recognise here: brainfuck has no multiply
command, so `8 × 8` is built as a loop that runs a counter down to zero
while adding a constant to another cell each pass.

## Why it terminates

The loop counter is cell 0, which starts at 8 and is decremented by exactly
one each pass, so the loop runs eight times and then cell 0 hits 0, letting
`]` fall through.  The program then reaches the end of its source and the
interpreter halts.
