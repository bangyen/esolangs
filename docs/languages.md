# Language capabilities

What the repository implements for each language. Generated from
`esolangs/registry.py` by `scripts/make_languages_doc.py`; do not edit by
hand.

Python means an in-repo interpreter under `esolangs.interpreters`;
Cross-check means an implementation in `extra/` that runs as a
standalone program (Rust, Lean, or RISC-V assembly), used to
differentially verify the Python interpreter.  The Boolean
column marks the boolean-function generators; Back, BIO, and
NoComment's are parameterized (the harness substitutes input bits
into a template) rather than the program reading input.

| Language | Text generator | Python | Cross-check | Boolean | Compiler | Examples |
| --- | :---: | :---: | :---: | :---: | :---: | :---: |
| %^2^-1 | yes | yes | yes |  |  | hello |
| 123 | yes | yes |  |  |  | hello |
| 2dFish | yes | yes | yes |  |  | hello |
| 3D Brainfuck | yes | yes |  | yes |  | hello |
| 3x | yes | yes | yes | yes |  | hello |
| 6-5 | yes | yes |  | yes |  | hello cat |
| A Painter Ant |  | yes |  | yes |  |  |
| ABCDirection |  | yes |  | yes |  |  |
| AddSubJump | yes | yes |  | yes |  | hello |
| Albabet | yes | yes |  |  |  | hello |
| ArrowQueue |  | yes |  |  |  | truth-machine |
| BF-PDA |  | yes |  | yes | yes |  |
| BFStack | yes | yes |  | yes | yes | hello |
| BIO | yes | yes |  | yes |  | hello |
| Back |  | yes |  | yes |  |  |
| Basicfuck | yes | yes | yes | yes |  | hello |
| Between | yes | yes |  | yes |  | hello cat truth-machine |
| Bitdeque |  | yes |  |  |  |  |
| BrainIf | yes | yes |  | yes |  | hello truth-machine |
| Brainpocalypse |  | yes |  |  |  |  |
| Circlefuck | yes | yes |  | yes |  | hello truth-machine |
| Clockwise | yes | yes |  | yes |  | hello |
| Collatz Multiverse | yes | yes |  | yes |  | hello |
| Container | yes | yes |  | yes |  | hello |
| Decleq | yes | yes |  | yes |  | hello |
| Dig | yes | yes |  | yes |  | hello |
| Dimensional | yes | yes |  | yes |  | hello |
| Dotlang | yes | yes |  |  |  | hello |
| EXCON | yes | yes |  |  | yes | hello |
| Eval | yes | yes |  |  |  | hello |
| Factor | yes | yes |  |  |  | hello truth-machine |
| Forbin | yes | yes |  | yes |  | hello truth-machine |
| Forþ | yes | yes | yes | yes |  | hello |
| Grapheme |  | yes |  |  |  |  |
| Home Row | yes | yes |  | yes | yes | hello |
| Jaune |  | yes |  | yes | yes |  |
| Kak |  | yes |  |  |  |  |
| Lamfunc |  | yes |  | yes |  |  |
| LaserFuck | yes | yes | yes | yes |  | hello |
| Lightlang |  | yes |  |  |  |  |
| Minifuck | yes | yes |  | yes |  | hello truth-machine |
| Minsky Swap |  | yes |  |  |  |  |
| Modulous | yes | yes |  | yes |  | hello cat truth-machine |
| Movesum |  | yes |  |  |  |  |
| MyScript | yes | yes |  | yes |  | hello |
| Nevermind | yes | yes |  | yes |  | hello cat |
| NoComment | yes | yes | yes | yes |  | hello |
| Number Seventy-Four |  | yes |  |  |  |  |
| Painfuck | yes | yes | yes | yes |  | hello |
| Polynomial | yes | yes |  | yes |  | hello |
| Qoibl | yes | yes |  | yes |  | hello |
| RAM0 |  | yes |  |  | yes |  |
| ROTfuck | yes | yes |  | yes |  | hello |
| S*bleq | yes | yes |  | yes |  | hello |
| SLOW ACV MAMMALIAN | yes | yes |  |  |  | hello |
| Sophie | yes | yes |  | yes |  | hello |
| Stun Step |  | yes |  |  |  |  |
| Suffolk | yes | yes |  |  | yes | hello |
| Taglate | yes | yes |  | yes |  | hello |
| The Temporary Stack | yes | yes |  |  |  | hello |
| Trash |  | yes |  |  |  |  |
| Unsquare | yes | yes | yes | yes | yes | hello |
| WII2D | yes | yes |  |  |  | hello |
| ZTOALC L | yes | yes |  | yes |  | hello |
| bit~ | yes | yes | yes | yes |  | hello |
| brainfuck | yes | yes |  | yes |  | hello |
| huf | yes | yes |  |  |  | hello |

The `esolangs` command lists the languages with Python support:

```bash
esolangs list
```
