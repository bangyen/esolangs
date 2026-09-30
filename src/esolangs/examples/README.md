# Example programs

Committed examples match generator output, verified by
`tests/scripts/test_examples.py`. Refresh them with:

```bash
python scripts/generate.py examples
```

Keep command boundaries intact when wrapping to 80 columns. Do not wrap grids,
newline-sensitive programs, or overlong tokens. AddSubJump, Decleq, and
S*bleq use fixed-width cells; BIO uses nesting indentation.

Each `.txt` file is a Boolean example. The generated
[`MANIFEST.md`](MANIFEST.md) lists its language, truth table, input row,
input format, and expected output. Use `esolangs.encode_inputs(language, bits)`
for stdin; parameterized programs embed their inputs.

Filenames are dash-separated display names, which is not always the name
the CLI takes: `cvnc.txt` is `CV(N)(C)`. The manifest's Language column
gives the name to pass to `esolangs run`. Lookup is case-insensitive.
