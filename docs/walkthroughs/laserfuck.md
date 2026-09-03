# Annotated walkthrough: LaserFuck (a 2D language)

`LaserFuck` is a grid: a laser starts at `o` and travels in its current
heading.  Cells along the way act as commands — `+`/`-` adjust the current
tape cell, `.` would print it (in this interpreter the whole tape prints
when the laser dies), `\`/`/` are mirrors that reflect the laser, `v`
points it down, and any non-command character is a no-op.  The first grid
cell `\xff` selects byte output mode.  The laser's *initial* heading is
chosen randomly, so a funnel of `|`/`^`/`}` around `o` routes 3 of the 4
possible headings onto the top row moving right (the fourth, down, runs
off the bottom edge before touching the tape).

## The program

```
ÿ}}+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++v
|o^
                                                                    .\
```

The top row sets cell 0 to 65, then a `v` turns the laser down column 68.
It passes over a blank cell and the `.` (a no-op in this interpreter) and
runs off the bottom edge, which kills it. The `\` at row 2, column 69 is
never reached — the beam is one column to its left the whole way down.
Killing the last laser triggers the tape dump, which prints byte 65 as
`A`.

The laser's initial heading is chosen at random, so this program has no
single reproducible trace; the funnel above exists to absorb that, and the
trace below assumes the heading it routes to the top row.

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
| 70 | blank (row 1, col 68) | `[65]` | no-op; the beam keeps heading down. |
| 71 | `.` (row 2, col 68) | `[65]` | no-op in this interpreter; the tape prints only when the laser dies. |
| 72 | off the bottom edge | `[65]` | the laser leaves the grid and dies. |

## Why it terminates

The laser's path is finite — it travels the funnel to the program row, is
turned down by the `v`, and runs off the bottom edge of the grid without
ever reaching the `\` (one column to its right). Leaving the grid deletes
the laser, and when no lasers remain the interpreter prints the tape (byte
65, `'A'`) and halts.
