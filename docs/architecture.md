# Architecture

The registry connects the API and CLI to generators and interpreters:

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

`src/esolangs/registry/` owns integration. `Language` records names,
interpreter, source shape and optional generator; `resolve` normalizes
spelling, and `RUNNERS` selects whole-source or split-line input.

`generate` calls the registered generator. Most return runnable source;
input-embedding languages return a `$`-placeholder template for `instantiate`.
`encode_inputs` handles stdin conventions. Generators live in
`src/esolangs/tools/`.

`run` loads the registered module from `src/esolangs/interpreters/`, constructs
the shared scripted I/O object, and calls its `run(code, io)` entry point.
`make_vm` exposes the interpreter’s step-capable machine to the debugger
and hang proofs.

Interpreters are grouped by execution model. Each interpreter and generator
owns a module or helper package.
`tests/interpreters/` and `tests/tools/` hold language suites and shared
contract checks. Line and Piet use the same verification and mutation
workflows as text languages. `scripts/` holds verification, mutation, and
documentation tools.

`Language.contract` owns typed Boolean input encodings and answer conventions.
Examples derive those fields from the registry; execution does not need docstrings.
`read_answer` uses the contract for printed and state-dump answers.
`evaluate` also handles termination answers, applying instantiation, input
encoding, execution and extraction to every row.
The private evaluation harness compares a supplied program's observed table with the expected one.

To add a language, implement its interpreter and generator, register its
`Language` and example metadata, and execute every generated input row. Follow
the [contribution checklist](CONTRIBUTING.md) and run `just test`.
