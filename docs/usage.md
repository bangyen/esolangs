# Using the package

Every language reads input and reports its answer in its own way. The API
hides this using [`describe`](#describe) metadata.

## Command line

`esolangs --help` lists every command; `esolangs <command> --help` describes one:

| Command | Does |
| --- | --- |
| `generate` | print a program computing a truth table |
| `run` | run a program through its interpreter |
| `debug` | run under the breakpoint/watch VM |
| `encode` | print the stdin that feeds a bit string |
| `read-answer` | print the answer bit a program's output carries |
| `list` | list the languages; `--details` adds the generator, template and example markers; `--state-model` and `--shape` filter by category and construction shape |
| `describe` | how one language reads input and where its answer lands |

`encode` and `read-answer` wrap `run` for one input row:

- LaserFuck:

  ```bash
  esolangs generate LaserFuck 0110 > prog.txt
  esolangs encode LaserFuck 10 | esolangs run LaserFuck prog.txt | esolangs read-answer LaserFuck  # prints 1
  ```
- Modulous:

  ```bash
  esolangs generate Modulous 0110 > modulous.txt
  ```

## Run XOR

A truth table is a binary string of length `2**n`, most-significant input
first. XOR's table is `0110`, ordered by rows `00`, `01`, `10`, `11`.
Run one stdin-driven row:

```python
import esolangs

table = "0110"
program = esolangs.generate("brainfuck", table)
stdin = esolangs.encode_inputs("brainfuck", [0, 1])
output = esolangs.run("brainfuck", program, stdin=stdin)
assert esolangs.read_answer("brainfuck", output) == "1"
```

Two kinds of language need a different call:

- Minifuck embeds inputs in its source:

  ```python
  template = esolangs.generate("Minifuck", table)
  program = esolangs.instantiate("Minifuck", template, [1, 0])
  output = esolangs.run("Minifuck", program)
  assert esolangs.read_answer("Minifuck", output) == "1"
  ```

  `bits[0]` is the most significant input. Template languages are those with
  `describe(name)["parameterized"]` (CLI: `list --template`).

- Piet returns an image source:

  ```python
  raster = esolangs.generate("Piet", table)
  assert isinstance(raster, esolangs.Raster)
  raster.to_png()
  stdin = esolangs.encode_inputs("Piet", [0, 1])
  assert esolangs.read_answer("Piet", esolangs.run("Piet", raster, stdin=stdin)) == "1"
  ```

`generate` returns a `Program`, which is one of:

- a `str` subclass, for text;
- a `Raster`, for images;
- a `CompressedText` (Unary).

`str()` of the last two is a summary, not source. `dump_program` and
`load_program` round-trip all three as text.

## Work with one language

`Language(name)` binds the same functions to one canonical language name:

```python
import esolangs

bf = esolangs.Language("brainfuck")
program = bf.generate("0110", balance=True)
output = bf.run(program, stdin=bf.encode_inputs([0, 1]))
assert bf.read_answer(output) == "1"
info = bf.describe()
```

It also binds `instantiate`; use the package functions across languages.

### Balance and scale

`balance=True` picks the supported layout that fits the smallest on-screen
square: text minimizes max(columns, 2 x rows), since a character cell is
about twice as tall as wide, so a shorter program can beat a squarer one.
Image-based output minimizes max(width, height) in pixels. Ties break by
source length (image-based: pixel area), then width. It excludes `width`.

Image-based generators accept `scale=1` (CLI: `--scale N`), applied after
layout. Rendering more than 2^28 pixels raises `ArgumentError`.

- Line compares forward and reverse input-test orders. It builds O(T) pixels
  for a truth table of length T and detects enlargement. Its committed
  example occupies 177×341 native pixels.
- Piet folds its path with stack-neutral turns. It builds O(T) pixels for a
  truth table of length T and detects enlargement by the largest uniform
  codel grid (codels are its blocks of pixels) anchored at the origin.
  `run(..., scale=N)` or `--scale N` overrides detection; use `scale=1` for
  native images whose blocks also fit a larger grid. Its committed example
  uses 80-pixel codels (480×240).

## Exported callables

<!-- PUBLIC-API:START -->

- `esolangs.describe` -- return a structured description of `language`
- `esolangs.dump_program` -- return version-1 JSON preserving source, choices, and template setters
- `esolangs.encode_inputs` -- return the stdin that feeds `bits` to a `language` program
- `esolangs.generate` -- return a program in `language` computing `truth_table`
- `esolangs.instantiate` -- fill a parameterized generator's template with `bits`
- `esolangs.list_languages` -- return the supported language names, sorted
- `esolangs.load_program` -- restore version-1 JSON as tagged source for the requested language
- `esolangs.read_answer` -- return the answer bit, `"0"` or `"1"`, a program's `output` carries
- `esolangs.run` -- execute `program` and return its output

<!-- PUBLIC-API:END -->

## Feeding a program

Build language-specific stdin with `encode_inputs`:

- Taglate:

  ```python
  esolangs.encode_inputs("Taglate", [1, 0, 1])  # -> '0101'
  ```

<!-- INPUT-SHAPES:START -->

| Language | `input_shape` | Alphabet | stdin for inputs 1, 0, 1 |
| --- | --- | --- | --- |
| 1 + i | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| 3x | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Algebraic Programming Language | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Ascenic | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Befunge | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| CV(N)(C) | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Caballo | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Clockwise | `char_stream_cyclic` | `0`/`1` | `'101'` |
| Collatz Multiverse | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Dig | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Dimensional | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Fargo | `row_index` | `0`/`1` | `'5\n'` |
| Forþ | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Grapheme | `line_per_bit` | `%`/`A` | `'A\n%\nA\n'` |
| Inject | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Interprogck8 | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Line | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Modulous | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Painfuck | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Piet | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Taglate | `char_stream_padded` | `0`/`1` | `'0101'` |
| Thue | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| Unary | `char_stream` | `\x00`/`ÿ` | `'ÿ\x00ÿ'` |
| Vandevelo | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |
| What!? | `line_per_bit` | `0`/`1` | `'1\n0\n1\n'` |

The other 43 that read stdin take one `0`/`1` character per bit -- `'101'`.
The remaining 17 embed their inputs and read no stdin: `instantiate` fills them.
The 3 interpreter-only classics have no generator, so there is no generated stdin to feed.
Use `encode_inputs` to build stdin; it and this table use `describe`.

<!-- INPUT-SHAPES:END -->

[`EXAMPLES.md`](../src/esolangs/languages/EXAMPLES.md) lists each example’s
input row and encoding.

`esolangs run` passes stdin to the interpreter verbatim. It does not check
it against the alphabet above (`ab` reads as two bits in brainfuck). Build
stdin with `encode`, and pipe the output to `read-answer` when you want an
answer bit.

## Templates

Some languages embed their inputs in the program. For these, `generate`
returns a template with one ordered `$` run per input, exactly as long as
its replacement. Fill it with `esolangs.instantiate(language, template, bits)`.
Running an unfilled template is refused. `esolangs list --details` marks
these languages `tmpl`.

## Reading the answer

Languages give their answer in one of three ways (`answer_mode`):

| Mode | The answer is | How to read it |
| --- | --- | --- |
| printed (most languages) | the output | `read_answer` |
| `"dump"` | the final state | `read_answer` |
| `"termination"` (a few) | halt for 0, loop forever for 1 | run with `max_steps` and treat a halt as 0; `read_answer` refuses these |

A timeout on a termination language remains undecided. Their
`answer_encoding` is `("halts", "diverges")`; its index gives the bit.

## Width

`generate` and CLI `--width` bound columns through layout.
`describe(language)["width_effect"]` identifies the three behaviours,
including the languages it does not affect (`"none"`).

## Dialect settings

`describe(language)["dialect_settings"]` lists a language's choices and
defaults. Pass `settings=DialectSettings(expression_syntax="postfix")` to
`generate`, `run` or `make_debugger`. On the CLI, use `--settings JSON` or the repeatable `--set KEY=VALUE`.

A generated program retains its settings. Plain text saved to a file does
not, so `run` needs them again; `--portable` keeps them.

## Bounded execution

Untrusted programs need all three bounds: `isolated=True`, a `timeout` and,
on Linux, `max_memory`. A timeout alone does not bound memory, and a program
can grow faster than any timeout fires. Elsewhere, cap the process yourself.

- Underload's `(x)(~:*~:^):^` doubles a string past a gigabyte in under a second.

### Isolate a run

`run(language, program, stdin=stdin, isolated=True, timeout=30)` bounds subprocess startup, loading and execution on Windows and worker
threads. A timeout kills and reaps the child; errors retain their class and
`partial_output`.

| Bound | Python | CLI | Notes |
| --- | --- | --- | --- |
| Time | `timeout` | `--timeout` | `--isolated` defaults to 30 seconds |
| Memory | `max_memory=BYTES` | `run --isolated --max-memory BYTES` | Linux only, needs `isolated=True`; other platforms refuse it |
| Output | `max_output` | `--max-output` | needs `isolated=True`; counts Unicode characters |

- `max_memory` bounds an isolated worker's virtual address space, including
  Python overhead. Parent source loading is outside the cap. Exhaustion
  raises `InterpreterLimitError`, never a Boolean answer.
- Exceeding `max_output` raises `InterpreterLimitError` with the retained
  prefix in `partial_output`. Zero permits no output; halting at exactly the
  cap succeeds.

```python
try:
    esolangs.run(
        "brainfuck", ",[.]", stdin="y", isolated=True, timeout=3, max_output=12
    )
except esolangs.InterpreterLimitError as exc:
    assert exc.partial_output == "y" * 12
```

On the CLI: `esolangs run --isolated --timeout 3 --max-output 4096 brainfuck program.txt`.
File acquisition, stdin acquisition, and subprocess execution each use that
bound separately.

### Count steps

`run(language, program, stdin=stdin, max_steps=100_000, timeout=1)`
returns output on halt. When either bound expires it raises
`ExecutionTimeoutError` with `partial_output`; its `bound` is `"timeout"` or
`"max_steps"`.

- `max_steps` selects cooperative stepping. It steps all languages on
  Windows and worker threads.
- Deadlines are checked between steps, so loading and an individual step
  cannot be interrupted.
- Text and image-based languages share the VM and debugger.
- `isolated` and `max_steps` are mutually exclusive, and stepping does not
  support `seed`.
- A language whose `describe()["steppable_to_answer"]` is false (A Painter
  Ant) answers only through `run` without `max_steps`; stepped, it never
  halts.

## Debugging

`esolangs debug` runs a program under the breakpoint/watch VM and reports
where it stopped:

```bash
esolangs generate brainfuck 0110 > bf.txt
printf '01' | esolangs debug --steps 20 --watch-cell 0 brainfuck bf.txt
```

| Flag | Does |
| --- | --- |
| `--steps` | bounds the run |
| `--watch-cell` | prints one value per step |
| `--break-at`, `--break-on-cell I=V`, `--break-on-output` | each stops with its condition still true |

From Python, the stepping API lives in `esolangs.debugger`: `VM`,
`Debugger`, `make_vm`, `make_debugger`, `StopReason`, and `STOP_REASONS`.

To step a text program and inspect its state:

```python
program = esolangs.generate("brainfuck", table)
stdin = esolangs.encode_inputs("brainfuck", [0, 1])
from esolangs.debugger import make_vm

vm = make_vm("brainfuck", program, stdin=stdin)
for _ in range(20):
    if vm.halted:
        break
    vm.step()
print(vm.ip, vm.memory, vm.output)
```

`make_debugger(...).run()` returns one of `STOP_REASONS`:
`"halted"`, `"breakpoint"`, `"max_steps"`, or `"timeout"`. Program faults raise
an exception instead; the CLI catches it and prints `stopped: raised`.

Every language steps under the debugger.

| Kind | Calls |
| --- | --- |
| Breakpoints | `break_at(ip)`, `break_on_cell(index, value)`, `break_on_stack(slot, value)`, `break_on_output(text)`, `break_when(predicate)` |
| Watches | `watch_cell(index)`, `watch_stack(slot)`: both return per-step histories |
| Inspect | `ip` (shaped by `ip_shape`), `memory`, `ptr`, `stack`, `views` |

- The CLI has only `--watch-cell`, so a stack language reports the cell as
  never written.
- A cell the machine has not reached reads `None`, so `break_on_cell(i, 0)`
  fires only once the pointer gets there.
- `break_on_output(text)` stops once output contains `text`. After a hit,
  `run` suppresses that breakpoint until its condition becomes false, so
  resuming can progress without clearing it.
- `clear_breakpoints()` removes all breakpoints while preserving the
  machine, output and watches.
- A breakpoint can stop before the halt instruction executes; inspect
  `halted` separately from the stop reason.

```python
from esolangs.debugger import make_debugger

debug = make_debugger("brainfuck", ",[.]", stdin="y")
debug.break_on_output("yy")
assert debug.run(max_steps=100) == "breakpoint"
assert debug.output == "yy"
assert debug.run(max_steps=20) == "max_steps"
assert len(debug.output) > 2
```

## Benchmarking

Measure a generated program and check every input row:

```bash
just benchmark brainfuck 0110 --all-rows
```

The JSON report holds rendered size, generation time, halt steps, expected
and actual answers, and execution status. Wrong or undecided rows fail;
unsupported stepping is distinct from a cap or timeout.

- The row timeout defaults to 30 seconds. `--no-timeout` disables the
  signal guard for Windows or worker threads.
- `just sizes` checks the committed size and step baseline and requires each
  measured row to answer correctly.

## describe

`describe(language)` returns the language’s API metadata.
`esolangs describe --json <language>` prints it; `esolangs list --details`
shows the `gen`, `tmpl`, and `ex` markers. Fields include:

| Field | Meaning |
| --- | --- |
| `source_kind` | `"text"`, or `"raster"` for an image |
| `state_model` | its category: register, tape, stack, grid, queue, program, variables or other |
| `shape` | its generator’s construction growth: tree, reducing or lookup; None without a generator |
| `input_shape`, `input_encoding` | how input is fed; None unless `reads_input` |
| `answer_mode`, `answer_encoding` | where the answer lands (`"output"`, `"dump"` or `"termination"`) and its `(zero, one)` form |
| `width_effect` | what `width` does: `"layout"`, `"wrap"` or `"none"` |
| `parameterized` | `generate` returns a template for `instantiate` |
| `reads_input` | the language reads stdin |
| `random` | the interpreter draws at random, so `run(seed=...)` applies |

There are more fields beyond these.

## Compatibility

The package is beta until 1.0: a 0.x minor release may still break the
surface below, and [CHANGELOG.md](CHANGELOG.md) lists every break.

The public API is `esolangs.__all__` and `esolangs.debugger.__all__`, plus
the documented CLI. Every other module (`esolangs.vm`, `esolangs.registry`,
`esolangs.generation`, `esolangs.runtime`, ...) is internal.

From 1.0, within a major release, compatibility covers:

- public names, their signatures (required arguments positional, optional
  ones keyword-only), and deliberate `EsolangError` exceptions;
- CLI command names, JSON field meanings, and exit statuses: 0 success,
  1 the program broke, 2 the ask was wrong, 70 internal error, 120 stdout
  closed early, 124 the timeout ran out, 130 interrupted;
- existing `describe()` fields and their value types (an absent value is
  `None`; `examples` are paths relative to the package);
- interpreter semantics for valid programs, including I/O and answers;
- committed examples as executable programs for their recorded tables.

New keyword-only arguments and metadata fields may be added. Human CLI prose,
generated program text, debugger presentation, internal modules, and private
`_` names may change without deprecation; generated programs retain
behaviour, not spelling or size.

A breaking public change requires a major release. Coexisting replacements
are documented for at least one minor release.
Security and correctness fixes may reject input accepted by mistake.
