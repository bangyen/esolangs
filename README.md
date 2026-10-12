# Esolang Interpreters

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![CI](https://github.com/bangyen/esolangs/actions/workflows/ci.yml/badge.svg)](https://github.com/bangyen/esolangs/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/esolangs.svg)](https://pypi.org/project/esolangs/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

<!-- PACKAGE-COUNT:START -->

Interpreters and Boolean generators for 83 esoteric languages: 80 text and 3 raster.

<!-- PACKAGE-COUNT:END -->

`generate` builds a truth-table program; `run` executes it on one input row.

## Concepts

The task is uniform across languages: compute a Boolean function from its
*truth table*, then verify the answer by running the generated program.
`generate` turns a table into a program; `encode_inputs` builds the stdin one
input row needs; `run` executes it; `read_answer` returns the `0`/`1` bit.
`describe` reports how a language takes its input and where its answer lands.
Languages that embed their inputs in the source return a template to fill with
`instantiate` instead.

## Quickstart

A table lists outputs for inputs `00, 01, 10, 11` in order, so `0110` is XOR:

```bash
pip install esolangs
esolangs generate brainfuck 0110 > xor.bf
for i in 00 01 10 11; do printf $i | esolangs run --timeout 5 brainfuck xor.bf; echo " <- $i"; done
# 0 <- 00
# 1 <- 01
# 1 <- 10
# 0 <- 11
```

Start with the [CLI](#command-line) or [Python API](#python-api).
The [usage guide](https://github.com/bangyen/esolangs/blob/main/docs/usage.md)
covers inputs, templates, answers, and debugging.
[Limitations](https://github.com/bangyen/esolangs/blob/main/docs/limitations.md)
records contracts; the [roadmap](https://github.com/bangyen/esolangs/blob/main/docs/roadmap.md)
tracks open work.

## Command line

```bash
python -m pip install esolangs

esolangs --help
esolangs list
esolangs generate brainfuck 0110 > bf.txt
printf '01' | esolangs debug --steps 20 --watch-cell 0 brainfuck bf.txt
```

- Suffolk:

  ```bash
  esolangs generate Suffolk 0110 > program.txt
  printf '01' | esolangs run Suffolk program.txt
  ```

- Polynomial needs the optional mathematics extra:
  `pip install 'esolangs[math]'`.

PNG loading and saving need
`pip install 'esolangs[image]'`; in-memory raster programs need neither extra.

## Python API

```python
import esolangs

program = esolangs.generate("brainfuck", "0110")
stdin = esolangs.encode_inputs("brainfuck", [0, 1])
output = esolangs.run("brainfuck", program, stdin=stdin, max_steps=10_000)
assert esolangs.read_answer("brainfuck", output) == "1"
```

Use `max_steps` to bound commands, or `timeout` to bound wall time.
On Windows or worker threads, use `isolated=True, timeout=5`; isolation also
supports `max_output` and Linux-only `max_memory` limits.

- Suffolk source may run as brainfuck with a wrong answer.

Use
[`encode_inputs`](https://github.com/bangyen/esolangs/blob/main/docs/usage.md#feeding-a-program)
to build stdin.

## Examples

<!-- XOR-EXAMPLE:START -->

`esolangs generate Sophie 0110` emits 20 characters computing XOR:

```
;@0{;}{;@0{#1}{#0}},
```

Feeding it the two adjacent input characters prints their XOR.

<!-- XOR-EXAMPLE:END -->


<!-- EXAMPLES:START -->

Ready-to-run programs for each of the 80
languages with a boolean generator live in
each language's [directory](https://github.com/bangyen/esolangs/tree/main/src/esolangs/languages).

<!-- EXAMPLES:END -->

## Implemented languages

Familiar languages include:

- [brainfuck](https://esolangs.org/wiki/brainfuck)
- [Befunge](https://esolangs.org/wiki/Befunge)
- [Piet](https://esolangs.org/wiki/Piet)
- [INTERCAL](https://esolangs.org/wiki/INTERCAL)
- [Malbolge](https://esolangs.org/wiki/Malbolge)

See the [complete language catalog](https://github.com/bangyen/esolangs/blob/main/docs/languages.md).

## Generators

<!-- BOOLEAN-COUNT:START -->

The truth table is a binary string of length `2**n`, most-significant input
first; its length implies `n`, so it isn't passed separately.  80 of the
languages have such a generator, some covering only a documented subset of
tables.

<!-- BOOLEAN-COUNT:END -->

`esolangs list --details` marks generators (`gen`), templates (`tmpl`),
and committed examples (`ex`). See the
[usage guide](https://github.com/bangyen/esolangs/blob/main/docs/usage.md)
for input conventions and benchmarking.

## Contributing

See [contributing](https://github.com/bangyen/esolangs/blob/main/docs/CONTRIBUTING.md)
for setup, verification and the execution path.
The project is GPL v3; see [LICENSE](https://github.com/bangyen/esolangs/blob/main/LICENSE).
