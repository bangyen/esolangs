# Architecture

The registry joins the package's generators and interpreters.  Public API and
CLI calls resolve a language name there, then follow the same pipeline:

```text
language name
    │
    ▼
registry.Language ──► boolean generator ──► program or {Xi} template
    │                                              │
    │                                      instantiate inputs
    ▼                                              │
interpreter module ◄──── source + encoded stdin ◄──┘
    │
    ├── run() ──► raw output ──► read_answer() ──► bit
    └── make_vm() ──► step-and-inspect state
```

`src/esolangs/registry.py` is the integration source of truth.  Each
`Language` records the display name, canonical id, interpreter module, source
shape, and optional boolean generator.  `resolve` normalizes caller spelling;
`RUNNERS` supplies the interpreter module and whether its source is passed as
one string or split into lines.

`generate` calls the registered generator with a truth table.  Most generators
return runnable source.  Languages that embed inputs return a `{Xi}` template;
`instantiate` fills one copy per input row.  `encode_inputs` handles the other
languages' stdin conventions.  Generator code lives under
`src/esolangs/tools/boolean/`.

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
