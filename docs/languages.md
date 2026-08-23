# Language capabilities

What the repository implements for each language. Generated from
`esolangs/registry.py` by `scripts/make_languages_doc.py`; do not edit by
hand.

Python means an in-repo interpreter under `esolangs.interpreters`;
Cross-check means an implementation in `extra/` that runs as a
standalone program (Rust, Lean, or RISC-V assembly), used to
differentially verify the Python interpreter.  The Boolean
column marks the boolean-function generators; the no-input languages (Back, BIO, NoComment, BF-PDA, Lamfunc, Bitdeque, RAM0, Minsky Swap, Eval, ArrowQueue, A Painter Ant, WII2D) use parameterized generators (the harness substitutes input bits into a template).

| Language | Text generator | Python | Cross-check | Boolean | Compiler | Examples |
| --- | :---: | :---: | :---: | :---: | :---: | :---: |
| %^2^-1 | yes | yes | yes |  |  | hello |
| 123 | yes | yes |  |  |  | hello |
| 3D Brainfuck | yes | yes |  | yes |  | hello boolean |
| 3x | yes | yes | yes | yes |  | hello |
| 6-5 | yes | yes |  | yes |  | hello cat boolean |
| A Painter Ant |  | yes |  | yes |  |  |
| ABCDirection |  | yes |  | yes |  |  |
| AddSubJump | yes | yes |  | yes | yes | hello boolean |
| ArrowQueue |  | yes |  | yes |  | boolean |
| BF-PDA |  | yes | yes | yes | yes |  |
| BFStack | yes | yes |  | yes | yes | hello boolean |
| BIO | yes | yes | yes | yes |  | hello boolean |
| Back |  | yes |  | yes |  |  |
| Basicfuck | yes | yes | yes | yes |  | hello boolean |
| Between | yes | yes |  | yes |  | hello cat truth-machine boolean |
| Bitdeque |  | yes |  | yes |  | boolean |
| BrainIf | yes | yes |  | yes |  | hello truth-machine boolean |
| COD |  | yes |  | yes |  | boolean |
| Circlefuck | yes | yes |  | yes |  | hello truth-machine boolean |
| Clockwise | yes | yes |  | yes |  | hello |
| Collatz Multiverse | yes | yes |  | yes | yes | hello boolean |
| Container | yes | yes |  | yes |  | hello boolean |
| Decleq | yes | yes |  | yes | yes | hello boolean |
| Dig | yes | yes |  | yes |  | hello boolean |
| Dimensional | yes | yes |  | yes |  | hello boolean |
| Eval | yes | yes |  | yes |  | hello boolean |
| Factor | yes | yes |  | yes |  | hello truth-machine boolean |
| Flowchart |  | yes |  |  |  | boolean |
| Forbin | yes | yes |  | yes |  | hello truth-machine boolean |
| Forþ | yes | yes | yes | yes | yes | hello |
| Grapheme |  | yes |  | yes |  |  |
| Home Row | yes | yes |  | yes | yes | hello boolean |
| Jaune |  | yes |  | yes | yes |  |
| Lamfunc |  | yes |  | yes |  | boolean |
| LaserFuck | yes | yes | yes | yes |  | hello |
| Minifuck | yes | yes |  |  |  | hello boolean |
| Minsky Swap |  | yes | yes | yes |  |  |
| Modulous | yes | yes |  | yes |  | hello cat truth-machine boolean |
| MyScript | yes | yes |  | yes |  | hello boolean |
| Nevermind | yes | yes |  | yes |  | hello cat boolean |
| NoComment | yes | yes | yes | yes |  | hello boolean |
| Painfuck | yes | yes | yes | yes |  | hello boolean |
| Point Break |  | yes |  | yes |  | boolean |
| Polynomial | yes | yes |  | yes |  | hello boolean |
| Qoibl | yes | yes |  | yes |  | hello boolean |
| RAM0 |  | yes | yes | yes | yes |  |
| ROTfuck | yes | yes |  | yes |  | hello boolean |
| S*bleq | yes | yes |  | yes | yes | hello boolean |
| SLOW ACV MAMMALIAN | yes | yes |  |  |  | hello |
| Sophie | yes | yes |  | yes |  | hello boolean |
| Streetcode | yes | yes |  | yes |  | hello boolean |
| Suffolk | yes | yes |  | yes | yes | hello boolean |
| Suptiftam | yes | yes |  | yes |  | hello cat truth-machine boolean |
| Taglate | yes | yes |  | yes |  | hello |
| Unsquare | yes | yes | yes | yes | yes | hello |
| WII2D | yes | yes |  | yes |  | hello boolean |
| ZTOALC L | yes | yes |  | yes |  | hello |
| bit~ | yes | yes | yes | yes |  | hello boolean |
| brainfuck | yes | yes |  | yes |  | hello boolean |

The `esolangs` command lists the languages with Python support:

```bash
esolangs list
```
