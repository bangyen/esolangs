# Example programs

Committed examples are exact parameterized-generator output, verified by
`tests/scripts/test_examples.py`. Refresh them with:

```bash
python scripts/write_examples.py
```

Keep command boundaries intact when wrapping to 80 columns. Do not wrap grids,
newline-sensitive programs, or overlong tokens. AddSubJump, Decleq, and
S*bleq use fixed-width cells; BIO uses nesting indentation.

`boolean/` contains one end-to-end Boolean example per selected language;
input-reading programs take `0`/`1` lines, while parameterized programs embed
the row's bits.
