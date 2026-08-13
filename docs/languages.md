# Language capabilities

What the repository implements for each language. Generated from
`esolangs/registry.py` by `scripts/make_languages_doc.py`; do not edit by
hand.

Python means an in-repo interpreter under `esolangs.interpreters`;
Native means an implementation in `extra/` that runs as a standalone
program (C++, Rust, Ruby, Lean, or x86 assembly).  The Boolean
column marks the boolean-function generators; Back, BIO, and
NoComment's are parameterized (the harness substitutes input bits
into a template) rather than the program reading input.

| Language | Text generator | Python | Native | Boolean | Compiler | Examples |
| --- | :---: | :---: | :---: | :---: | :---: | :---: |
| %^2^-1 | yes |  | yes |  |  |  |
| 123 | yes |  | yes |  |  |  |
| 2 Bits, 1 Byte |  |  | yes |  |  |  |
| 2dFish | yes |  | yes |  |  |  |
| 3x | yes |  | yes | yes |  |  |
| 6-5 | yes | yes |  | yes |  | hello cat |
| ASCII art | yes | yes |  | yes |  | hello |
| Albabet |  |  | yes |  |  |  |
| ArrowQueue |  | yes |  |  |  |  |
| BF | yes | yes |  | yes |  | hello |
| BF-PDA |  |  | yes |  | yes |  |
| BFStack | yes | yes |  | yes | yes | hello |
| BIO | yes | yes |  | yes |  | hello |
| Back |  | yes |  | yes |  |  |
| Basicfuck | yes |  | yes | yes |  |  |
| Between | yes | yes |  | yes |  | hello cat truth-machine |
| BitDeque |  | yes |  |  |  |  |
| BrainIf | yes | yes |  | yes |  | hello truth-machine |
| Brainpocalypse |  |  | yes |  |  |  |
| CircleFuck | yes | yes |  | yes |  | hello truth-machine |
| Clockwise | yes | yes |  | yes |  | hello |
| Container | yes | yes |  | yes |  | hello |
| DSDLAI |  | yes |  |  |  |  |
| Dig | yes | yes |  | yes |  | hello |
| Dimensional | yes | yes |  | yes |  | hello |
| Dotlang | yes | yes |  |  |  | hello |
| EXCON | yes | yes | yes |  | yes | hello |
| Eval | yes | yes |  |  |  | hello |
| Factor | yes | yes |  |  |  | hello truth-machine |
| Forþ | yes |  | yes | yes |  |  |
| Home Row | yes |  |  |  | yes |  |
| Kak |  |  | yes |  |  |  |
| Keys |  | yes |  |  |  |  |
| LaserFuck | yes | yes | yes | yes |  | hello |
| Lightlang |  | yes |  |  |  |  |
| MAMMALIAN | yes | yes |  |  |  | hello |
| Minifuck | yes | yes |  |  |  | hello |
| Minsky Swap |  | yes |  |  |  |  |
| Modulous | yes | yes |  | yes |  | hello cat truth-machine |
| Movesum |  | yes |  |  |  |  |
| Nevermind | yes | yes |  | yes |  | hello cat |
| NoComment | yes | yes | yes | yes |  | hello |
| Number Seventy-Four |  |  | yes |  |  |  |
| Painfuck | yes |  | yes |  |  |  |
| Polynomial | yes | yes |  | yes |  | hello |
| Qoibl | yes | yes |  | yes |  | hello |
| RAM0 |  | yes |  |  | yes |  |
| S*bleq | yes | yes |  | yes |  | hello |
| Sophie | yes | yes |  | yes |  | hello |
| Stun Step |  |  | yes |  |  |  |
| Suffolk | yes | yes |  |  | yes | hello |
| Taglate | yes | yes |  | yes |  | hello |
| Temporary | yes | yes |  |  |  | hello |
| Trash |  |  | yes |  |  |  |
| Unsquare | yes |  | yes | yes | yes |  |
| WII2D | yes | yes |  |  |  | hello |
| ZTOALC | yes | yes |  |  |  | hello |
| bit~ | yes |  | yes |  |  |  |
| huf | yes | yes |  |  |  | hello |

The `esolangs` command lists the languages with Python support:

```bash
esolangs list
```
