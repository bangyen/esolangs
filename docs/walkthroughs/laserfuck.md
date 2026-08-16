# Annotated walkthrough: LaserFuck (a 2D language)

`LaserFuck` is a grid: a laser starts at `o` and travels in its current
heading.  Cells along the way act as commands — `+`/`-` adjust the current
tape cell, `.` would print it (in this interpreter the whole tape prints
when the laser dies), `\`/`/` are mirrors that reflect the laser, `v`
points it down, and any non-command character is a no-op.  The first grid
cell `\xff` selects byte output mode.  The laser's *initial* heading is
chosen randomly, so a funnel of `}`/`^`/`|`/`_` mirrors around `o` sends
most headings onto the top row moving right.

## The program

```
ÿ}}+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++v
|o^
                                                                    .\
```

The top row sets cell 0 to 65, then a `v` turns the laser down into a
mirror that bounces it back left past a `.` — which prints the accumulated
byte.  (The walkthrough assumes the laser starts heading right, which the
funnel routes onto the top row; the run is otherwise non-deterministic
because of the random start heading.)

## Step by step

The tape starts `[0]` and the laser starts at the `o`.  Under the funnel
(starting right, heading 3):

| Step | Laser at | Tape | Why |
| --- | --- | --- | --- |
| 1 | `o` (row 1, col 1) | `[0]` | the laser is born here, heading right. |
| 2 | `^` (row 1, col 2) | `[0]` | `^` points the laser up. |
| 3 | `}` (row 0, col 2) | `[0]` | `}` points it right, onto the program row. |
| 4..68 | the 65 `+`s (row 0) | `[65]` | each `+` increments the current cell. |
| 69 | `v` (row 0, col 68) | `[65]` | `v` points the laser down. |
| 70 | `\` (row 2, col 68) | `[65]` | the mirror reflects down → left. |
| 71 | `.` (row 2, col 67) | `[65]` | prints the cell: byte 65 = `'A'`. |
| 72 | off the left edge | `[65]` | the laser leaves the grid and dies. |

## Why it terminates

The laser's path is finite — it travels the funnel to the program row, is
turned down by the `v`, reflected left by the mirror, and then runs off the
left edge of the grid.  Leaving the grid deletes the laser, and when no
lasers remain the interpreter prints the tape (byte 65, `'A'`) and halts.
