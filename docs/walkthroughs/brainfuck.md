# Annotated walkthrough: brainfuck (a tape language)

`brainfuck` keeps a tape of byte cells and a data pointer.  The eight
commands are `>`/`<` (move the pointer right/left), `+`/`-` (increment/
decrement the current cell), `.` (print the current cell as a byte), `,`
(read a byte into the current cell), and `[`/`]` (loop while the current
cell is nonzero — `[` jumps past the matching `]` when the cell is zero,
`]` jumps back when it is nonzero).  Cells start at 0 and wrap at 8 bits.

## The program

```
+++[>++<-]>.
```

This sets cell 0 to 3, runs a loop that adds 2 to cell 1 each pass (so
cell 1 ends at 6), and prints cell 1.

## Step by step

The pointer starts at cell 0 and every cell holds 0.

| Command | State after | Why |
| --- | --- | --- |
| `+` | cell 0 = 1 | `+` increments the current cell. |
| `+` | cell 0 = 2 | ditto. |
| `+` | cell 0 = 3 | ditto. |
| `[` | cell 0 = 3, enter the loop | cell 0 is nonzero, so the body runs. |
| `>` | pointer at cell 1 | `>` moves the data pointer right. |
| `++` | cell 1 = 2 | two `+`s increment the new current cell. |
| `<` | pointer at cell 0 | `<` moves the data pointer back. |
| `-` | cell 0 = 2 | `-` decrements the current cell. |
| `]` | back to `[` | cell 0 is still nonzero, so the loop repeats. |
| `>` `++` `<` `-` | cell 1 = 4, cell 0 = 1 | second pass, same as above. |
| `]` | back to `[` | cell 0 = 1, still nonzero. |
| `>` `++` `<` `-` | cell 1 = 6, cell 0 = 0 | third pass. |
| `]` | exit the loop | cell 0 is now 0, so `]` falls through. |
| `>` | pointer at cell 1 | `>` moves right to the accumulated result. |
| `.` | prints byte 6 | `.` prints the current cell; byte 6 is the
  "acknowledge" control character. |

## Why it terminates

The loop counter is cell 0, which starts at 3 and is decremented by
exactly one each pass, so the loop runs three times and then cell 0 hits 0,
letting `]` fall through.  The program then reaches the end of its source
and the interpreter halts.
