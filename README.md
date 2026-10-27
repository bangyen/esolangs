# Esolang Interpreters

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![CI](https://github.com/bangyen/esolangs/actions/workflows/ci.yml/badge.svg)](https://github.com/bangyen/esolangs/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/esolangs.svg)](https://pypi.org/project/esolangs/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

<!-- PACKAGE-COUNT:START -->

Interpreters and Boolean generators for 96 esoteric languages: 94 text and 2 raster.

<!-- PACKAGE-COUNT:END -->

Give it a truth table and a language; it writes a program in that language
that computes the table, and runs it for you.

## Try it

```bash
pip install esolangs
esolangs generate brainfuck 0110 > xor.bf
for i in 00 01 10 11; do printf $i | esolangs run --timeout 5 brainfuck xor.bf; echo " <- $i"; done
# 0 <- 00
# 1 <- 01
# 1 <- 10
# 0 <- 11
```

`0110` is a *truth table*: the outputs for inputs `00, 01, 10, 11`, in that
order. This one is XOR. `generate` wrote a brainfuck program for it, and
`run` fed it one input row at a time.

## Install

| You want | Install |
|---|---|
| Everything except the two below | `pip install esolangs` |
| Polynomial | `pip install 'esolangs[math]'` |
| Load or save PNG programs (image-based languages) | `pip install 'esolangs[image]'` |

Image-based programs built in memory need neither extra.

## Command line

```bash
esolangs --help
esolangs list
esolangs generate Suffolk 0110 > program.txt
printf '01' | esolangs run Suffolk program.txt
```

- `list` shows every language; `list --details` marks which have a
  generator (`gen`), a template (`tmpl`) and committed examples (`ex`).
- Run a program under its own language. Suffolk programs look like
  brainfuck, but brainfuck rejects or misreads them.

## Python

```python
import esolangs

program = esolangs.generate("brainfuck", "0110")
stdin = esolangs.encode_inputs("brainfuck", [0, 1])
output = esolangs.run("brainfuck", program, stdin=stdin, max_steps=10_000)
assert esolangs.read_answer("brainfuck", output) == "1"
```

| Call | Does |
|---|---|
| `generate` | Turns a truth table into a program. |
| `encode_inputs` | Builds the stdin for one input row; each language reads input its own way. |
| `run` | Runs a program. |
| `read_answer` | Pulls the `0`/`1` answer out of the output. |
| `describe` | Says how a language takes input and where its answer lands. |
| `instantiate` | Fills a template: some languages put inputs in the source, so `generate` returns a template instead. |

Bound a run with:

- `max_steps`: a command count.
- `timeout`: wall time. On Windows or in a worker thread, pass
  `isolated=True, timeout=5`.
- `max_output`, and `max_memory` on Linux: need `isolated=True`.

The [usage guide](https://github.com/bangyen/esolangs/blob/main/docs/usage.md)
covers [input](https://github.com/bangyen/esolangs/blob/main/docs/usage.md#feeding-a-program),
templates, answers, debugging and benchmarking.

## Examples

<!-- XOR-EXAMPLE:START -->

`esolangs generate 'bit~' 0110` emits 11 characters computing XOR:

```
))>>~>~<<<(
```

Feeding it the two adjacent input characters prints their XOR.

<!-- XOR-EXAMPLE:END -->


<!-- EXAMPLES:START -->

Ready-to-run programs for each of the 93
languages with a boolean generator live in
each language's [directory](https://github.com/bangyen/esolangs/tree/main/src/esolangs/languages).

<!-- EXAMPLES:END -->

## Languages

Familiar ones include
[brainfuck](https://esolangs.org/wiki/brainfuck),
[Befunge](https://esolangs.org/wiki/Befunge),
[Piet](https://esolangs.org/wiki/Piet),
[INTERCAL](https://esolangs.org/wiki/INTERCAL) and
[Malbolge](https://esolangs.org/wiki/Malbolge).
The [catalog](https://github.com/bangyen/esolangs/blob/main/docs/languages.md)
lists all of them.

<!-- BOOLEAN-COUNT:START -->

The truth table is a binary string of length `2**n`, most-significant input
first; its length implies `n`, so it isn't passed separately.  93 of the
languages have such a generator, some covering only a documented subset of
tables.

<!-- BOOLEAN-COUNT:END -->

[Limitations](https://github.com/bangyen/esolangs/blob/main/docs/limitations.md)
lists those subsets and other known limits; the
[roadmap](https://github.com/bangyen/esolangs/blob/main/docs/roadmap.md)
tracks open work.

## Contributing

See [CONTRIBUTING](https://github.com/bangyen/esolangs/blob/main/docs/CONTRIBUTING.md)
for setup and checks. Licensed GPL v3; see
[LICENSE](https://github.com/bangyen/esolangs/blob/main/LICENSE).
