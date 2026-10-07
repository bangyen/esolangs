# Changelog

Breaking changes are listed first. Before 1.0 a minor release may break the
public API; see [the compatibility policy](docs/usage.md#compatibility).
Releases before 0.10.0 are described on the
[GitHub releases page](https://github.com/bangyen/esolangs/releases).

## 0.10.0

Covers everything since 0.8.0, including 0.9.1, which shipped without notes.

### Breaking changes

The public API is settled ahead of 1.0:

- **Optional arguments are keyword-only** everywhere in `esolangs.__all__`,
  `esolangs.debugger.__all__` and the `Language` methods. Required ones stay
  positional.
  - `generate(language, truth_table, *, width, balance, scale, settings)`
  - `instantiate(language, template, bits, *, width, truth_table, settings)`
  - `encode_inputs(language, bits, *, truth_table)`
  - `run(language, program, *, stdin, timeout, seed, isolated, max_steps,
    scale, max_output, max_memory, settings)`: `stdin` is keyword-only too.
  - `make_vm` / `make_debugger(language, program, *, stdin, scale, settings)`
  - `Debugger.run(*, max_steps, timeout)`
  - `Raster(rows, *, language, settings)`: `rows` is required;
    `Raster.upscaled(scale)` takes a required scale.
- **`run(..., timeout=None)`** is the default. With `isolated=True` it now
  means the 30-second default instead of being refused.
- **`run(..., seed=...)`** must be an `int`; a `str`, `float` or `bool` raises
  `ArgumentError`.
- **`instantiate`** accepts what `generate` returns and raises
  `TemplateError` for a raster, so the documented flow type-checks under
  `mypy --strict`.
- **`ProgramSource` / `InputSource`** use `typing.IO` instead of a private
  protocol.
- **Removed** `InputMismatchWarning` (never emitted) and `complete_vm` from
  `esolangs.debugger.__all__` (still in the internal `esolangs.vm`).
- **`describe()`**: the `interpreter` (an internal module path) and
  `proof_status` fields are gone; `examples` are paths relative to the
  package (`importlib.resources.files("esolangs") / path`); an absent value
  is always `None` (`generator_restrictions` and `answer_pattern` were `""`).
- **Public scope**: `esolangs.__all__`, `esolangs.debugger.__all__` and the
  documented CLI are public; every other module is internal.

Language removed (already absent from 0.9.1):

- **3D Brainfuck**: its specification leaves the core undefined.

Interpreter behaviour that changed to match the specification or the wiki's
examples:

- **Tape-based languages** grow the tape left instead of clamping at cell 0
  (Minifuck still clamps: its tape is right-infinite and the wiki cat opens
  with `<`).
- **Flowchart** does Boolfuck byte I/O; its generated programs read 8 bits an
  input and print an ASCII answer.
- **ROTfuck** rotation is a dialect setting (`backward`|`forward`, default
  `backward`); a jump seeks before rotating.
- **Alight** three-argument `at` is a dialect setting (`list_update`
  `in_place`|`copy`, default `in_place`).
- **Bitdeque** `GOTO N` counts from 1; past the end halts; a taken `GOTO 0`
  raises.
- **RAM0** `goto 0` raises; **Dimensional** rejects a malformed literal before
  running.
- **SLOW ACV MAMMALIAN** `EXCRETE`/`PRONOUNCE` default to the page's modulo 255.
- **INTERCAL** implements INTERCAL-72 plus single-threaded C-INTERCAL;
  `READ OUT` prints zero as a lone overbar; foreign digit words, `COMING FROM`
  gerund labels, and `COME FROM` re-fires.
- **Piet** numeric input accepts only `[+-]digits`; a depth-0 roll pops its
  operands.
- **Sophie** `;` and `:` at end of input read 0.
- **Inject** `readto` keeps blank lines and empties the block at EOF.
- **thisthat** takes newline-separated input sets and the readings the wiki
  examples force.
- **Super SNUSP** without `"` starts rightward on the last line's last
  character.
- **Painfuck** `v` skips on a nonzero cell; a repeated `j` reads each time.
- **6-5**, **3x**, **Collatz Multiverse**, **bit~**, **Forbin**, **Home Row**,
  **Grapheme**, **EGL**, **Fish**, **Thue**, **Befunge**, **Container**,
  **Dig**, **Qoibl**, **Jaune**, **Unlambda** and **Decleq**: smaller semantic
  corrections, each described in the language's docstring.

### Fixes

- All 80 languages were diffed on random programs against an independent
  implementation (a clean-room reimplementation from the esolangs.org page, or
  a reference interpreter such as npiet or C-INTERCAL); the disagreements
  were resolved in favour of the wiki's examples.
- The Line and 3x generators are thread-safe; concurrent use could return a
  corrupt Line program or crash 3x.
- An in-process `MemoryError` raises `InterpreterLimitError`, as isolated
  execution already did.

### Packaging and docs

- The `dev` extra is now a `dev` dependency group (`uv sync --group dev`), so
  it no longer appears in the published metadata.
- Repository-only tooling moved out of the package into `scripts/`; the sdist
  no longer carries a partial test suite.
- The wheel is reproducible; CI smoke-tests it on Python 3.12 and 3.14 on
  Linux, macOS and Windows.
- `Typing :: Typed` classifier.
- `run --help` lists every exit status (0, 1, 2, 70, 120, 124, 130).
- Docs: untrusted programs need `isolated=True`, a `timeout` and, on Linux,
  `max_memory`.
