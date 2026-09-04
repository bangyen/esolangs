# Annotated walkthrough: LaserFuck (a 2D language)

`LaserFuck` is a grid: a laser starts at `o` and travels in its current
heading (full semantics in the interpreter docstring). This example uses
just `+` (increment the current tape cell), `v`/`\` (turn the laser down /
reflect it), and `.`, which in this interpreter is a no-op — the whole tape
prints only when the laser dies. The laser's *initial* heading is chosen
randomly, so a funnel of `|`/`^`/`}` around `o` routes 3 of the 4 possible
headings onto the top row moving right (the fourth, down, runs off the
bottom edge before touching the tape).

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

The laser's path is finite: it runs off the grid edge, and the interpreter
halts once no lasers remain.
