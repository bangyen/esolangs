# Contributing

Add stable, deterministic languages verifiable through the repo's I/O model.
Each needs a generator or documented impossibility; record rejections
in [limitations](limitations.md). See [architecture](architecture.md) for the
execution path.

## Development

```bash
just install-dev
source .venv/bin/activate        # or prefix each command with `uv run`
just test-quick
```

Run `just test` before committing; use `just test-full` for release-scale
changes (`test-full` includes slow tests; weekly probes run separately with
`just test-py`, or in scheduled CI). Regenerate committed examples with
`python scripts/generate.py examples`.

CI checks the wheel on Linux, macOS and Windows: packaged examples, CLI I/O,
Line/Piet PNG execution, and installation with and without the mathematics extra.

## What makes a candidate worth adding

A new language must add an uncovered construction, branch mechanism,
answer convention, or input interface:

- **Construction shape** -- decision tree (the default), minterm sum
  (`bfstack`, `vandevelo`), ANF/XOR-of-products (`fargo`, and `super_snusp`
  below five inputs), grid walk (`laserfuck`, `a_painter_ant`, `streetcode`).
- **Branch mechanism** -- explicit conditional, value-testable jump, skip
  guard, implicit comparator, pointer displacement (`123`).
- **Answer convention** -- print 0/1, landing colour (`a_painter_ant`),
  position-encoded (`minifuck`),
  termination as the answer (`123`, ArrowQueue, Crement, Vandevelo).
- **Input interface** -- read-and-route, bit-addressable index (`fargo`),
  parameterized embed.

These are generator tests. A language whose specification precludes a
generator qualifies only through the fame threshold under Curation in
[limitations](limitations.md). Such languages are interpreter-only, marked
`int` by `esolangs list --details`; Deadfish, HQ9+, Nope. and Unary qualify.
Curation also defines removal independently of admission.

## Layout

| Path | Holds |
| --- | --- |
| `src/esolangs/interpreters/` | interpreter modules and `run(code, io)` |
| `src/esolangs/tools/` | generators |
| `src/esolangs/registry/` | the source of truth for public integration |
| `tests/` | interpreter and generator coverage |

## Interpreter conventions

Start from `src/esolangs/interpreters/_template.py`. Every interpreter:

- Exposes `run(code, io)` with required `IO`; uses `io` for all I/O.
  Most grids receive lines via registry `split=True`; A Painter Ant,
  B-tapemark and EGL receive whole source.
- Raises `ValueError` for a malformed program and `HaltError` for an
  invalid runtime operation, and terminates by construction: the fuzz
  suites feed random and empty programs.
- Guards an input line before indexing it (`if val:`); an empty line is
  legal, and running out raises `EOFError` either way.
- Exposes `_Machine.step()`, `halted` and a complete `snapshot()`, including
  the input cursor. Tests look up that exact name; `dimensional.py` was
  silently skipped when it named something else.
- Writes the language as a pure transition (`_advance`) over an immutable
  state, with `step` as the shell doing the I/O; a store that cannot be
  threaded cheaply returns effects instead (`grapheme.py`).
- Follows explicit specification rules. Examples resolve omissions only when
  consistent with those rules; internal consistency alone does not establish
  author intent. Records contradictions rather than silently repairing them.
  Documents and tests any intentional deviation.
- Documents spec-gap decisions in its docstring (`suffolk.py`); never defines
  away invalid operations.
- Provides a `__main__` block calling `run(data, IO())`.

`tests/test_interpreter_conventions.py` checks the module docstring names
the language and mentions `EOF`, `HaltError` or `ValueError` wherever the
interpreter reads input or raises them.

## What makes a generator optimization worth shipping

A generator size optimization must meet all of these requirements:

- **5% or more** off the total emitted size over all 256 three-input tables,
  measured against its parent. ArrowQueue's 2.1% rotation gain was reverted.
  A gain that grows with the table, such as sharing repeated subtrees
  (`scripts/screens/sharing.py`: 14.5% of nodes repeat at three inputs, a
  third at five), may clear it instead on 200 seeded random five-input
  tables; the no-growth rule then holds on that sample too.
- **No table grows**: checked exhaustively through three inputs, so keep the
  old build as a candidate when the new one is not uniformly shorter.
- **Every table executes**: exhaustively through three inputs and sampled at
  four to six. Pin the n=3 total before and after; update `just sizes` when its
  baseline moves.
- **The Boolean-generator conventions** in `docs/limitations.md`: reads and
  template runs in input order, one uniform `(zero, one)` fill pair, at most
  four named reorder candidates, no search, O(T) size and generation
  (`tests/proofs/deep/linearity.py`).
- **No interpreter leniency**: truncated keywords or missing operands do not
  count as shorter programs.

Execution-time optimizations require 5% fewer commands summed over every row
of the three-input tables (`scripts/screens/steps.py`), with no table slower
or larger. Choose candidates by size, breaking ties by steps.

Use `scripts/screens/` to bound the upside first.

## Checklist

1. Run `just new-language "Name" --category tape_based` (using the matching
   category), then replace the placeholder semantics and test.
2. Register the language and any generator in `registry/_table.py`.
3. Add end-to-end tests, and execute the generated programs.
4. Record generator evidence with `just benchmark "Name" TABLE`; compare
   `source_units` and `commands`, not wall-clock time.
5. Regenerate docs, then run `just test`; `just test-full` for release-scale
   changes.
