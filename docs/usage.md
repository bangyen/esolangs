# Using the package

Generate a program, feed it, and judge the result without language-specific
branches. The API reads [`describe`](#describe) metadata instead.

## The round trip

`evaluate` runs a generated program on every row of its input space and
returns the table it actually computes; `verify` compares that to the table
you asked for.

```python
import esolangs

esolangs.evaluate("A Painter Ant", "0110")  # -> '0110'
esolangs.verify("Fargo", "10010110")  # -> True
```

Both cover unusual input shapes, templates, and termination-encoded answers.
For individual stages, use `generate`, `encode_inputs`, `run`, and
`read_answer`.

## Guided XOR example

XOR's table is `0110`: rows `00`, `01`, `10`, and `11` produce `0`, `1`,
`1`, and `0`. A stdin-driven language runs one row like this:

```python
import esolangs

table = "0110"
program = esolangs.generate("brainfuck", table)
stdin = esolangs.encode_inputs("brainfuck", [0, 1])
output = esolangs.run("brainfuck", program, stdin)
assert esolangs.read_answer("brainfuck", output) == "1"
assert esolangs.verify("brainfuck", table)
```

Some languages embed inputs in their source instead:

```python
template = esolangs.generate("Minifuck", table)
program = esolangs.instantiate("Minifuck", template, [1, 0])
output = esolangs.run("Minifuck", program)
assert esolangs.read_answer("Minifuck", output) == "1"
```

Raster languages return an image source:

```python
raster = esolangs.generate("Piet", table)
assert isinstance(raster, esolangs.Raster)
raster.to_png()
assert esolangs.verify("Piet", table)
```

The VM exposes common state without erasing language-specific state:

```python
program = esolangs.generate("brainfuck", table)
stdin = esolangs.encode_inputs("brainfuck", [0, 1])
vm = esolangs.make_vm("brainfuck", program, stdin)
for _ in range(20):
    if vm.halted:
        break
    vm.step()
print(vm.ip, vm.memory, vm.output)
```

The [debugging](#debugging) section covers the interactive interface. Use
`just benchmark brainfuck 0110 --row 1` when changing a generator; its JSON
reports source units, generation time, and deterministic command count.

## Exported callables

<!-- PUBLIC-API:START -->

- `esolangs.check_program` -- return `program` as source, having checked what can be checked here
- `esolangs.check_runnable` -- reject a program that is a path or an unfilled template
- `esolangs.check_stdin` -- refuse `stdin` that cannot be what `language` wants to read
- `esolangs.describe` -- return a structured description of `language`
- `esolangs.encode_inputs` -- return the stdin that feeds `bits` to a `language` program
- `esolangs.evaluate` -- return the truth table a generated `language` program *actually* computes
- `esolangs.generate` -- return a program in `language` computing `truth_table`
- `esolangs.instantiate` -- fill a parameterized generator's template with `bits`
- `esolangs.list_languages` -- return the supported language names, sorted
- `esolangs.make_debugger` -- return a `Debugger` over a fresh `VM` for `language`
- `esolangs.make_vm` -- return a step-and-inspect wrapper around `language`'s interpreter
- `esolangs.read_answer` -- return the answer bit a `language` program's `output` carries
- `esolangs.run` -- execute `program` and return its output
- `esolangs.run_bounded` -- execute a text program cooperatively, returning output only on halt
- `esolangs.run_isolated` -- return output from a subprocess; the deadline includes loading and startup
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

The other 51 that read stdin take one `0`/`1` line per bit -- `'1\n0\n1\n'`.
The remaining 19 embed their inputs and read no stdin: `instantiate` fills them.
The 1 interpreter-only classics have no generator, so there is no generated stdin to feed.
Call `encode_inputs` rather than reading a row off
this table; it is generated from `describe`, and so is the table.

<!-- INPUT-SHAPES:END -->

A shape the checker cannot tell apart from a legitimate one still answers
the wrong row, which is why the encoder is the interface and the table is
only a reference. [`src/esolangs/examples/MANIFEST.md`](../src/esolangs/examples/MANIFEST.md)
lists every example language's input column.

Stdin is checked against the shape and alphabet a language declares:
`esolangs run` warns, `esolangs run --judge` refuses, and
`esolangs.check_stdin(language, stdin, truth_table)` is the same judge from
Python -- given the table it checks the bit *count* too, which catches a
surplus line as well as a missing one.

## Templates

Fourteen languages embed inputs, so `generate` returns a template with one
ordered `$` run per input, exactly as long as its replacement. Fill it with
`esolangs.instantiate(language, template, bits)`; running one unfilled is
refused.  `esolangs list --details` marks them `tmpl` and identifies each
one.

## Reading the answer

Most languages print the answer, six dump their whole final state with it
somewhere inside, and four answer by *terminating* -- they halt for a 0 and
loop forever for a 1. `read_answer` handles the first two; for the third,
bound the run and catch `ExecutionTimeoutError` as the 1.

The `answer_encoding` is `("halts", "diverges")` for those four, in the order
`describe` gives them, so index 0 is the answer 0 and
`encoding.index("diverges")` is the polarity.

## Width

`generate` and the CLI's `--width` bound the columns. Most grids honour it
by laying themselves out rather than being reflowed;
`describe(language)["width_effect"]` says which of the three behaviours you
have, and names the 15 that ignore a width because their newlines are part
of the program.

## Bounded execution

`run_isolated(language, program, stdin, timeout=30)` bounds subprocess startup,
loading and execution on Windows and worker threads. Timeout kills and reaps
the child; errors retain their class and `partial_output`.
`evaluate(..., isolated=True)` and `verify(..., isolated=True)` apply a finite
deadline per row; a timeout remains undecided, including termination answers.

`run_bounded(language, program, stdin, max_steps=100_000, timeout=1)`
returns output on halt and raises `ExecutionTimeoutError` with
`partial_output` when either bound expires. Supply at least one bound.
It steps text languages on Windows and worker threads; deadlines are checked
between steps, so loading and an individual step cannot be interrupted.
Raster languages require `run`.

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

`--tui` highlights the next operation and shows the tape, stack, output,
named state, and watch history. Controls are `hjkl` to move, `t` to toggle a
breakpoint, `c` to continue, `space` to step, `b` to step back, `r` to finish,
and `q` to quit. Use `--stdin`; keyboard commands and program input cannot
share a stream.

Call-stack and 3-D positions cannot identify source text, so they remain
unhighlighted. The header still shows the raw `ip`.

## describe

`describe(language)` returns the record every function above branches on:
`source_kind`, `input_shape`, `input_encoding`, `answer_mode`, `answer_encoding`,
`width_effect`, `parameterized`, `reads_input` and the rest.
`esolangs describe --json <language>` prints it, and `esolangs list
--details` reduces it to a marker column -- `gen`, `tmpl`, `ex`.

## Compatibility

The package is beta. Within a major release, compatibility covers:

- names in `esolangs.__all__`, their documented arguments, and deliberate
  `EsolangError` exceptions;
- CLI command names, exit-status meanings, and JSON field meanings;
- existing `describe()` fields and their value types;
- interpreter semantics for valid programs, including I/O and answers;
- committed examples as executable programs for their recorded tables.

New optional arguments and metadata fields may be added. Human CLI prose,
generated program text, debugger presentation, and private `_` names may
change without deprecation; generated programs retain behaviour, not spelling
or size.

A breaking public change requires a major release. When old and new interfaces
can coexist, the replacement is documented for at least one minor release.
Security and correctness fixes may reject input accepted by mistake.
