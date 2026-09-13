# Using the package

Generate a program, feed it, judge what comes back -- in a language the
caller knows nothing about. Every decision below reads a
[`describe`](#describe) field rather than a language name, so nothing here
needs a per-language branch.

## The round trip

`evaluate` runs a generated program on every row of its input space and
returns the table it actually computes; `verify` compares that to the table
you asked for.

```python
import esolangs

esolangs.evaluate("A Painter Ant", "0110")  # -> '0110'
esolangs.verify("Fargo", "10010110")  # -> True
```

Both work for all 65 -- the four odd input shapes, the seventeen template
languages and the three that answer by diverging included. If you need the
steps rather than the result, they are `generate`, `encode_inputs`, `run`,
`read_answer`, below.

## Exported callables

<!-- PUBLIC-API:START -->

- `esolangs.check_program` -- return `program` as source, having checked what can be checked here
- `esolangs.check_stdin` -- refuse `stdin` that cannot be what `language` wants to read
- `esolangs.describe` -- return a structured description of `language`
- `esolangs.encode_inputs` -- return the stdin that feeds `bits` to a `language` program
- `esolangs.evaluate` -- return the truth table a generated `language` program *actually* computes
- `esolangs.generate` -- return a program in `language` computing `truth_table`
- `esolangs.instantiate` -- fill a parameterized generator's `{Xi}` slots with `bits`
- `esolangs.list_languages` -- return the supported language names, sorted
- `esolangs.make_debugger` -- return a `Debugger` over a fresh `VM` for `language`
- `esolangs.make_vm` -- return a step-and-inspect wrapper around `language`'s interpreter
- `esolangs.read_answer` -- return the answer bit a `language` program's `output` carries
- `esolangs.run` -- execute `program` and return its output
- `esolangs.spec` -- return the interpreter's own description of `language`
- `esolangs.verify` -- whether a generated `language` program really computes `truth_table`

<!-- PUBLIC-API:END -->

`generate` takes a truth table -- `0110` is XOR -- and returns a program
computing it. The table is a binary string of length `2**n`,
most-significant input first, so its length implies `n`.

## Feeding a program

**How a language reads its input bits is not universal.** Let
`encode_inputs` build the stdin rather than assembling it by hand:

```python
esolangs.encode_inputs("Taglate", [1, 0, 1])  # -> '0\n1\n0\n1\n'
```

<!-- INPUT-SHAPES:START -->

| Language | `input_shape` | Alphabet | stdin for inputs 1, 0, 1 |
| --- | --- | --- | --- |
| Clockwise | `one_line` | `0`/`1` | `'101'` |
| Fargo | `row_index` | `0`/`1` | `'5\n'` |
| Grapheme | `line_per_bit` | `%`/`A` | `'A\n%\nA\n'` |
| Taglate | `line_per_bit_padded` | `0`/`1` | `'0\n1\n0\n1\n'` |

The other 40 that read stdin take one `0`/`1` line per bit -- `'1\n0\n1\n'`.
The remaining 16 read no stdin at all: their inputs are
embedded by `instantiate`.  Call `encode_inputs` rather than reading a row off
this table; it is generated from `describe`, and so is the table.

<!-- INPUT-SHAPES:END -->

A shape the checker cannot tell apart from a legitimate one still answers
the wrong row, which is why the encoder is the interface and the table is
only a reference. `examples/boolean/MANIFEST.md` lists every language's
input column.

Stdin is checked against the shape and alphabet a language declares:
`esolangs run` warns, `esolangs run --judge` refuses, and
`esolangs.check_stdin(language, stdin, truth_table)` is the same judge from
Python -- given the table it checks the bit *count* too, which catches a
surplus line as well as a missing one.

## Templates

Seventeen languages embed the inputs in the program rather than reading
them, so `generate` returns a template with a `{Xi}` slot per input. Fill
it with `esolangs.instantiate(language, template, bits)`; running one
unfilled is refused. `esolangs list --details` marks them `tmpl` and
identifies each one.

## Reading the answer

Most languages print the answer, six dump their whole final state with it
somewhere inside, and three answer by *terminating* -- they halt for a 0 and
loop forever for a 1. `read_answer` handles the first two; for the third,
bound the run and catch `ExecutionTimeoutError` as the 1.

`TERMINATION_OUTCOMES` is `("halts", "diverges")`: the `answer_encoding` of
those three, in the order `describe` gives them, so index 0 is the answer 0
and `encoding.index("diverges")` is the polarity.

## Width

`generate` and the CLI's `--width` bound the columns. Most grids honour it
by laying themselves out rather than being reflowed;
`describe(language)["width_effect"]` says which of the three behaviours you
have, and names the 22 that ignore a width because their newlines are part
of the program.

## Debugging

`esolangs debug` runs a program under the breakpoint/watch VM and reports
where it stopped. `--steps` bounds the run, `--watch-cell` prints one value
per step, and `--break-at`, `--break-on-cell I=V` and `--break-on-output`
each stop with their condition still true.

```bash
esolangs generate brainfuck 0110 > bf.txt
printf '0\n1\n' | esolangs debug --steps 20 --watch-cell 0 brainfuck bf.txt
```

`STOP_REASONS` is `("halted", "breakpoint", "max_steps", "timeout")` -- what
`make_debugger(...).run()` returns. A program that *faults* raises out of
`run` instead, so it has no reason of its own; the CLI catches that and
prints a fifth word, `stopped: raised`, which is why that line ranges over
more than this tuple.

`--tui` steps the program on screen instead, highlighting the op about to
run and showing the tape, stack, output and the language's own named state
beside it, with `--watch-cell`'s history as a row that grows as you step
and shortens as you go back. `hjkl` move a selector so a breakpoint can be
set where the run has not reached yet; `t` marks under it and `c` continues
to the next one. Feed such a run with `--stdin`, since the keys and the
program cannot share one stream. A language whose position is not a place
in the source -- a call stack, a 3-D point -- is left unhighlighted rather
than marked in the wrong place; the header always shows the raw `ip`.

## describe

`describe(language)` returns the record every function above branches on:
`input_shape`, `input_encoding`, `answer_mode`, `answer_encoding`,
`width_effect`, `parameterized`, `reads_input` and the rest.
`esolangs describe --json <language>` prints it, and `esolangs list
--details` reduces it to a marker column -- `gen`, `tmpl`, `ex`.
