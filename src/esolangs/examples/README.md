# Example programs

Committed examples use `balance=True`, verified by
`tests/scripts/test_examples.py`. Refresh them with:

```bash
python scripts/generate.py examples
```

Each `.txt` or `.png` file is a Boolean example. [`MANIFEST.md`](MANIFEST.md) lists its
language, truth table, input row, format, and expected output. Use
`esolangs.encode_inputs(language, bits)` for stdin; parameterized programs
embed their inputs.

Filenames are dash-separated display names: `cvnc.txt` means `CV(N)(C)`.
Use the manifest’s Language column with `esolangs run`; lookup is
case-insensitive.
