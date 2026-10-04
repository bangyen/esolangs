# Example programs

Examples use `balance=True` (`tests/scripts/test_examples.py`). Refresh with:

```bash
python scripts/generate.py examples
```

Each `.txt` or `.png` is a Boolean example. [`MANIFEST.md`](MANIFEST.md) lists
language, table, input row, format and expected output. Use
`esolangs.encode_inputs(language, bits)` for stdin; parameterized programs
embed their inputs.

Filenames use dash-separated display names: `cvnc.txt` means `CV(N)(C)`.
Pass the manifest's Language column to `esolangs run`; lookup ignores case.
