# Annotated walkthrough: Forþ (a stack language)

`Forþ` keeps a stack of signed 32-bit integers.  A digit `0`-`9` or hex
letter `A`-`F` pushes its value; `+`/`-`/`*`/`/`/`%` replace the top two
values with their arithmetic result (the top goes on the right); `:` copies
the top; `.` prints the top's low byte; `[` loops while the top is nonzero;
and any other character is ignored.

## The program

```
8 8 * 1 + .
```

This computes `8 × 8 + 1 = 65` and prints it, which is the byte for `A`.

## Step by step

| Command | Stack (top on the right) | Why |
| --- | --- | --- |
| `8` | `[8]` | a digit pushes its value. |
| `8` | `[8, 8]` | ditto. |
| `*` | `[64]` | `*` pops `8` and `8` and pushes `8 × 8 = 64`. |
| `1` | `[64, 1]` | a digit pushes 1. |
| `+` | `[65]` | `+` pops `1` and `64` and pushes `64 + 1 = 65`. |
| `.` | `[]` | `.` prints the top's low byte, 65 = `'A'`, and pops it. |

## Why it terminates

The program is straight-line: it has no loop, so it reaches its end and
the interpreter halts.
