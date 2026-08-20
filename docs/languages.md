# Language capabilities

What the repository implements for each language. Generated from
`esolangs/registry.py` by `scripts/make_languages_doc.py`; do not edit by
hand.

Python means an in-repo interpreter under `esolangs.interpreters`;
Cross-check means an implementation in `extra/` that runs as a
standalone program (Rust, Lean, or RISC-V assembly), used to
differentially verify the Python interpreter.  The Boolean
column marks the boolean-function generators; the no-input languages (Back, BIO, NoComment, BF-PDA, Lamfunc, Bitdeque, RAM0, Minsky Swap, Eval, ArrowQueue, A Painter Ant, Dotlang, WII2D) use parameterized generators (the harness substitutes input bits into a template).

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
| ArrowQueue |  | yes |  | yes |  | boolean |
| BF-PDA |  | yes |  | yes | yes |  |
| BFStack | yes | yes |  | yes | yes | hello |
| BIO | yes | yes |  | yes |  | hello |
| Back |  | yes |  | yes |  |  |
| Basicfuck | yes | yes | yes | yes |  | hello |
| Between | yes | yes |  | yes |  | hello cat truth-machine |
| Bitdeque |  | yes |  | yes |  |  |
| BrainIf | yes | yes |  | yes |  | hello truth-machine |
| Circlefuck | yes | yes |  | yes |  | hello truth-machine |
| Clockwise | yes | yes |  | yes |  | hello |
| Collatz Multiverse | yes | yes |  | yes |  | hello |
| Container | yes | yes |  | yes |  | hello |
| Decleq | yes | yes |  | yes |  | hello |
| Dig | yes | yes |  | yes |  | hello |
| Dimensional | yes | yes |  | yes |  | hello |
| Dotlang | yes | yes |  | yes |  | hello boolean |
| Eval | yes | yes |  | yes |  | hello boolean |
| Factor | yes | yes |  | yes |  | hello truth-machine |
| Forbin | yes | yes |  | yes |  | hello truth-machine |
| Forþ | yes | yes | yes | yes |  | hello |
| Grapheme |  | yes |  | yes |  |  |
| Home Row | yes | yes |  |  | yes | hello |
| Jaune |  | yes |  | yes | yes |  |
| Lamfunc |  | yes |  | yes |  |  |
| LaserFuck | yes | yes | yes | yes |  | hello |
| Minifuck | yes | yes |  |  |  | hello boolean |
| Minsky Swap |  | yes |  | yes |  |  |
| Modulous | yes | yes |  | yes |  | hello cat truth-machine |
| MyScript | yes | yes |  | yes |  | hello |
| Nevermind | yes | yes |  | yes |  | hello cat |
| NoComment | yes | yes | yes | yes |  | hello |
| Painfuck | yes | yes | yes | yes |  | hello |
| Point Break |  | yes |  | yes |  | boolean |
| Polynomial | yes | yes |  | yes |  | hello |
| Qoibl | yes | yes |  | yes |  | hello |
| RAM0 |  | yes |  | yes | yes |  |
| ROTfuck | yes | yes |  | yes |  | hello |
| S*bleq | yes | yes |  | yes |  | hello |
| SLOW ACV MAMMALIAN | yes | yes |  |  |  | hello |
| Sophie | yes | yes |  | yes |  | hello |
| Suffolk | yes | yes |  |  | yes | hello |
| Suptiftam | yes | yes |  | yes |  | hello cat truth-machine |
| Taglate | yes | yes |  | yes |  | hello |
| The Temporary Stack | yes | yes |  |  |  | hello |
| Unsquare | yes | yes | yes | yes | yes | hello |
| WII2D | yes | yes |  | yes |  | hello boolean |
| ZTOALC L | yes | yes |  | yes |  | hello |
| bit~ | yes | yes | yes | yes |  | hello |
| brainfuck | yes | yes |  | yes |  | hello |

The `esolangs` command lists the languages with Python support:

```bash
esolangs list
```
