# Architecture

The registry joins the package's generators and interpreters.  Public API and
CLI calls resolve a language name there, then follow the same pipeline:

```text
language name
    │
    ▼
registry.Language ──► boolean generator ──► program or template
    │                                              │
    │                                      instantiate inputs
    ▼                                              │
interpreter module ◄──── source + encoded stdin ◄──┘
    │
    ├── run() ──► raw output ──► read_answer() ──► bit
    └── make_vm() ──► step-and-inspect state
```

`src/esolangs/registry/` is the integration source of truth. Each `Language`
records its names, interpreter, source shape, and optional generator. `resolve`
normalizes spelling; `RUNNERS` selects whole-source or split-line input.

`generate` calls the registered generator. Most return runnable source;
input-embedding languages return a `$`-placeholder template for `instantiate`.
`encode_inputs` handles stdin conventions. Generators live in
`src/esolangs/tools/`.

`run` loads the registered module from `src/esolangs/interpreters/`, constructs
the shared scripted I/O object, and calls its `run(code, io)` entry point.
`make_vm` reaches the same interpreter through its step-capable machine and
exposes common state for the debugger and hang proofs.

Interpreter output is not uniformly a printed `0` or `1`.  `read_answer` uses
the registered example metadata for printed and state-dump answers; `evaluate`
also handles languages whose answer is whether execution terminates.  It runs
every input row through generation, optional instantiation, input encoding,
execution, and extraction.  `verify` compares that observed table with the
requested one.

When adding a language, keep the whole path connected: implement the
interpreter and generator, add their `Language` entry, add example metadata,
and test the generated program by executing every row.  The
[contribution checklist](CONTRIBUTING.md) and `just test` enforce that contract.
