# Compatibility

The package is beta. Minor releases may add languages and metadata fields, but
the following interfaces remain compatible within a major release:

- names exported by `esolangs.__all__`, their documented arguments, and
  deliberate exceptions derived from `EsolangError`;
- CLI command names, exit status meanings, and JSON field meanings;
- existing `describe()` fields and their value types;
- interpreter semantics for valid programs, including input and answer
  conventions;
- committed examples as executable programs for their recorded tables.

New optional arguments and JSON or `describe()` fields may be added. Human
CLI prose, generated program text, debugger presentation, and private names
beginning with `_` may change without deprecation. Generated programs remain
behaviorally equivalent; their exact spelling and size are not API.

A breaking public change requires a major release. A replacement is documented
for at least one minor release before removal when both interfaces can coexist.
Security and correctness fixes may reject input previously accepted by mistake.
