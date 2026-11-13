# Esolang Interpreters

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![CI](https://github.com/bangyen/esolangs/actions/workflows/ci.yml/badge.svg)](https://github.com/bangyen/esolangs/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/esolangs.svg)](https://pypi.org/project/esolangs/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

<!-- PACKAGE-COUNT:START -->

Interpreters and Boolean generators for 117 esoteric languages: 115 text and 2 raster.

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
| Text programs and in-memory raster programs | `pip install esolangs` |
| Load or save PNG programs (image-based languages) | `pip install 'esolangs[image]'` |

Image-based programs built in memory need no extra.

Examples reflect this checkout. Use `pip install .` from the repository to try
unreleased APIs.

## Command line

```bash
esolangs --help
esolangs list
esolangs list --input-shape char_stream --answer-mode output
esolangs list --inputs 8 --details
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
row = program.evaluate([0, 1], limits=esolangs.ExecutionLimits(max_steps=10_000))
assert row.bit == "1"
```

| Call | Does |
|---|---|
| `generate` | Returns a program artifact or input template for a truth table. |
| `encode_inputs` | Builds the stdin for one input row; each language reads input its own way. |
| `run` | Returns output, input consumption, and completion evidence. |
| `read_answer` | Pulls the `0`/`1` answer out of the output. |
| `describe` | Says how a language takes input and where its answer lands. |
| `instantiate` | Fills a template: some languages put inputs in the source, so `generate` returns a template instead. |

Bound a run with:

- `max_steps`: a command count.
- `timeout`: wall time, enforced in a worker on all platforms.
- `max_output`, and `max_memory` on Linux: need `isolated=True`.

`evaluate` handles stdin encoding, template binding, and answer extraction.
The row includes an execution observation and, for termination answers,
a halt or divergence proof. Exhausting a time or step budget raises `ExecutionTimeoutError`; `max_output`, `InterpreterLimitError`.
Generated artifacts expose `.source` and templates expose `.fill(bits)`.
For a custom catalog, use `Language.evaluate(artifact, bits)`.
The [2.0 migration guide](docs/usage.md#compatibility) covers the changed return
types and migrating 1.x source/output callers.

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

Ready-to-run programs for each of the 114
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
first; its length implies `n`, so it isn't passed separately.  114 of the
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
