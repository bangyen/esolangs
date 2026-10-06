# Using the package

The API handles language I/O conventions using [`describe`](#describe) metadata.

## Command line

`esolangs --help` lists every command; `esolangs <command> --help` describes one:

| Command | Does |
| --- | --- |
| `generate` | print a program computing a truth table |
| `run` | run a program through its interpreter |
| `debug` | run under the breakpoint/watch VM, or `--tui` to step interactively |
| `suggest` | preview unambiguous command-spelling fixes; runs and edits nothing |
| `encode` | print the stdin that feeds a bit string |
| `read-answer` | print the answer bit a program's output carries |
| `list` | list the languages; `--details` adds the generator, template and example markers |
| `describe` | how one language reads input and where its answer lands |

`encode` and `read-answer` wrap `run` for one input row:

```bash
esolangs generate LaserFuck 0110 > prog.txt
esolangs encode LaserFuck 10 | esolangs run LaserFuck prog.txt | esolangs read-answer LaserFuck -> 1
esolangs generate Modulous 0110 > modulous.txt
esolangs suggest Modulous modulous.txt
```

## Work with one language

`Language(name)` binds the same functions to one canonical language name:

```python
bf = esolangs.Language("brainfuck")
program = bf.generate("0110", balance=True)
output = bf.run(program, bf.encode_inputs([0, 1]))
assert bf.read_answer(output) == "1"
info = bf.describe()
```

It also binds `instantiate`; use the package functions across languages.
`balance=True` minimizes the rendered width/height difference across supported
layouts, breaking ties by source length (raster pixel area), then width.
It excludes `width`. Line compares forward and reverse input-test orders;
Piet folds its path with stack-neutral turns. Both construct O(T) pixels
for a truth table of length T.
Raster generators accept `scale=1` (CLI: `--scale N`), applied after layout.
Both interpreters detect enlargement. Piet chooses the largest uniform codel
grid anchored at the image origin; `run(..., scale=N)` or `--scale N`
overrides detection. Use `scale=1` for native images whose blocks also fit a
larger grid. The committed Piet example uses 80-pixel codels (960×560),
comparable in area to native Line (680×800).

## Run XOR

Truth tables are binary strings of length `2**n`, most-significant input
first. XOR's table is `0110`, ordered by rows `00`, `01`, `10`, `11`.
Run one stdin-driven row:

```python
import esolangs

table = "0110"
program = esolangs.generate("brainfuck", table)
stdin = esolangs.encode_inputs("brainfuck", [0, 1])
output = esolangs.run("brainfuck", program, stdin)
assert esolangs.read_answer("brainfuck", output) == "1"
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
stdin = esolangs.encode_inputs("Piet", [0, 1])
assert esolangs.read_answer("Piet", esolangs.run("Piet", raster, stdin)) == "1"
```

To step through a text program and inspect its state:

```python
program = esolangs.generate("brainfuck", table)
stdin = esolangs.encode_inputs("brainfuck", [0, 1])
from esolangs.debugger import make_vm

vm = make_vm("brainfuck", program, stdin)
for _ in range(20):
    if vm.halted:
        break
    vm.step()
print(vm.ip, vm.memory, vm.output)
```

The [debugging](#debugging) section covers the interactive interface.

## Benchmarking

Measure a generated program and check every input row:

```bash
just benchmark brainfuck 0110 --all-rows
```

JSON reports rendered size, generation time, halt steps, expected and actual
answers, and execution status. Wrong or undecided rows fail; unsupported
stepping is distinct from a cap or timeout. The row timeout defaults to 30 seconds;
`--no-timeout` disables the signal guard for Windows or worker threads.
`just sizes` checks the committed size and step baseline and requires each
measured row to answer correctly.

## Exported callables

<!-- PUBLIC-API:START -->

- `esolangs.describe` -- return a structured description of `language`
- `esolangs.dump_program` -- return version-1 JSON preserving source, choices, and template setters
- `esolangs.encode_inputs` -- return the stdin that feeds `bits` to a `language` program
- `esolangs.generate` -- return a program in `language` computing `truth_table`
- `esolangs.instantiate` -- fill a parameterized generator's template with `bits`
- `esolangs.list_languages` -- return the supported language names, sorted
- `esolangs.load_program` -- restore version-1 JSON as tagged source for the requested language
- `esolangs.read_answer` -- return the answer bit a `language` program's `output` carries
- `esolangs.run` -- execute `program` and return its output

<!-- PUBLIC-API:END -->

## Feeding a program

Build language-specific stdin with `encode_inputs`:

```python
esolangs.encode_inputs("Taglate", [1, 0, 1])  # -> '0101'
```

<!-- INPUT-SHAPES:START -->

| Language | `input_shape` | Alphabet | stdin for inputs 1, 0, 1 |
| --- | --- | --- | --- |
| 3x | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Algebraic Programming Language | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Befunge | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| CV(N)(C) | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Clockwise | `char_stream_cyclic` | `0`/`1` | `'101'` |
| Collatz Multiverse | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Dig | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Dimensional | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Fargo | `row_index` | `0`/`1` | `'5\n'` |
| Forþ | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Grapheme | `line_per_bit` | `%`/`A` | `'A\n%\nA\n'` |
| Inject | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Jaune | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Line | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Modulous | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Painfuck | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Piet | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Taglate | `char_stream_padded` | `0`/`1` | `'0101'` |
| Thue | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Vandevelo | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |

The other 35 that read stdin take one `0`/`1` character per bit -- `'101'`.
The remaining 21 embed their inputs and read no stdin: `instantiate` fills them.
The 4 interpreter-only classics have no generator, so there is no generated stdin to feed.
Use `encode_inputs` to build stdin; it and this table use `describe`.

<!-- INPUT-SHAPES:END -->

[`MANIFEST.md`](../src/esolangs/examples/MANIFEST.md) lists each example’s
input row and encoding.

`esolangs run` warns about invalid stdin through the interpreter; pipe its
output to `read-answer` when an answer bit is wanted.

## Templates

For languages that embed inputs, `generate` returns a template with one
ordered `$` run per input, exactly as long as its replacement. Fill it with
`esolangs.instantiate(language, template, bits)`; running one unfilled is
refused. `esolangs list --details` marks them `tmpl`.

## Reading the answer

Most languages print the answer; six dump their final state, and four answer
by termination: halt for 0, loop forever for 1. `read_answer` handles printed
and state-dump answers and refuses termination answers: run those with
`max_steps` and treat a halt as 0. A timeout remains undecided.

Their `answer_encoding` is `("halts", "diverges")`; its index gives the bit.

## Width

`generate` and CLI `--width` bound columns through layout;
`describe(language)["width_effect"]` identifies the three behaviours,
including the 15 languages that ignore width because newlines are semantic.

## Bounded execution

`run(language, program, stdin, isolated=True, timeout=30)` bounds subprocess startup,
loading and execution on Windows and worker threads. Timeout kills and reaps
the child; errors retain their class and `partial_output`.
`max_memory=BYTES` bounds a Linux isolated worker's virtual address space,
including Python overhead. `run` requires `isolated=True`; CLI
`run --isolated --max-memory BYTES` bounds the worker. Other platforms refuse the
option. Parent source loading is outside the cap; exhaustion raises
`InterpreterLimitError`, never a Boolean answer.

`run(language, program, stdin, max_steps=100_000, timeout=1)`
returns output on halt and raises `ExecutionTimeoutError` with
`partial_output` when either bound expires. `max_steps` selects cooperative stepping.
It steps all languages on Windows and worker threads; deadlines are checked
between steps, so loading and an individual step cannot be interrupted.
Text and raster languages share the VM and debugger. `isolated` and `max_steps` are mutually
exclusive, and stepping does not support `seed`.

With `isolated=True`, `max_output` caps output in Unicode characters. Exceeding
the cap raises `InterpreterLimitError` with the retained prefix in `partial_output`.
Zero permits no output; halting at exactly the cap succeeds.

```python
try:
    esolangs.run("brainfuck", ",[.]", "y", isolated=True, timeout=3, max_output=12)
except esolangs.InterpreterLimitError as exc:
    assert exc.partial_output == "y" * 12
```

## Debugging

The Python stepping API lives in `esolangs.debugger`: `VM`, `Debugger`,
`make_vm`, `make_debugger`, `StopReason`, and `STOP_REASONS`.

`esolangs debug` runs a program under the breakpoint/watch VM and reports
where it stopped. `--steps` bounds the run, `--watch-cell` prints one value
per step, and `--break-at`, `--break-on-cell I=V` and `--break-on-output`
each stop with their condition still true.

```bash
esolangs generate brainfuck 0110 > bf.txt
printf '01' | esolangs debug --steps 20 --watch-cell 0 brainfuck bf.txt
```

`make_debugger(...).run()` returns one of `STOP_REASONS`:
`"halted"`, `"breakpoint"`, `"max_steps"`, or `"timeout"`. Program faults raise
an exception instead; the CLI catches it and prints `stopped: raised`.

`break_on_output(text)` stops once output contains `text`. After a hit, `run`
suppresses that breakpoint until its condition becomes false, so resuming can
progress without clearing it. `clear_breakpoints()` removes all breakpoints
while preserving the machine, output and watches. A breakpoint can stop before
the halt instruction executes; inspect `halted` separately from the stop reason.

```python
from esolangs.debugger import make_debugger

debug = make_debugger("brainfuck", ",[.]", "y")
debug.break_on_output("yy")
assert debug.run(max_steps=100) == "breakpoint"
assert debug.output == "yy"
assert debug.run(max_steps=20) == "max_steps"
assert len(debug.output) > 2
```

`--tui` highlights the next operation and shows the tape, stack, output,
named state, and watch history. Controls are `hjkl` to move (a leading
count walks further, `g` prompts for a place, `G` returns to the run), `t`
to toggle a breakpoint, `c` to continue, `space` to step, `b` to step back,
`r` to finish, `R` to restart on new stdin, `w`/`W` to add and drop a
watched cell, `p` to play with `+`/`-` setting the speed, and `q` to quit.
The cell the last step changed flashes. Use `--stdin`; keyboard commands
and program input cannot share a stream.

Call-stack and 3-D positions show raw `ip` without source highlighting.

## describe

`describe(language)` returns the language’s API metadata:
`source_kind`, `input_shape`, `input_encoding`, `answer_mode`, `answer_encoding`,
`width_effect`, `parameterized`, `reads_input` and the rest.
`esolangs describe --json <language>` prints it; `esolangs list --details`
shows the `gen`, `tmpl`, and `ex` markers.

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

A breaking public change requires a major release. Coexisting replacements
are documented for at least one minor release.
Security and correctness fixes may reject input accepted by mistake.

CLI portable execution: `esolangs run --isolated --timeout 3 --max-output 4096 brainfuck program.txt`.
`--isolated` defaults to 30 seconds; `--max-output` requires it. File acquisition,
stdin acquisition, and subprocess execution each use that bound separately.
