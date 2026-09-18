# Example programs

Committed examples are exact parameterized-generator output, verified by
`tests/scripts/test_examples.py`. Refresh them with:

```bash
python scripts/generate.py examples
```

Keep command boundaries intact when wrapping to 80 columns. Do not wrap grids,
newline-sensitive programs, or overlong tokens. AddSubJump, Decleq, and
S*bleq use fixed-width cells; BIO uses nesting indentation.

Each `.txt` file is one end-to-end Boolean example for a selected language;
input-reading programs take `0`/`1` lines, while parameterized programs embed
the row's bits.

**Which table does a given file compute?** See
[`MANIFEST.md`](MANIFEST.md), generated alongside the
programs: it gives each file's language, truth table, input row, and
expected output. Without it a program can be run but not judged — none of
these languages has a comment syntax to carry the answer.

Filenames are dash-separated display names, which is not always the name
the CLI takes: `cvnc.txt` is `CV(N)(C)`. The manifest's Language column
gives the name to pass to `esolangs run`, and language lookup is
case-insensitive anyway.
