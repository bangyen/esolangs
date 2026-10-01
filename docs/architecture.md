# Architecture

The API and CLI resolve generators and interpreters through the registry:

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
`make_vm` exposes the interpreter’s step-capable machine to the debugger
and hang proofs.

Languages print a bit, dump state, or answer by halting. `read_answer` uses
example metadata for printed and state-dump answers; `evaluate` also handles
termination answers. It runs a supplied program through optional
instantiation, input encoding, execution, and extraction on every row.
CLI `evaluate --table` compares the observed table with the expected one.

To add a language, implement its interpreter and generator, register its
`Language` and example metadata, and execute every generated input row. Follow
the [contribution checklist](CONTRIBUTING.md) and run `just test`.
