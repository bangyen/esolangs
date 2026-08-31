# Language capabilities

What the repository implements for each language. Generated from
`esolangs/registry.py` by `scripts/make_languages_doc.py`; do not edit by
hand.

Python means an in-repo interpreter under `esolangs.interpreters`;
Cross-check means an implementation in `extra/` that runs as a
standalone program (Lean or RISC-V assembly), used to
differentially verify the Python interpreter.  The Boolean
column marks the boolean-function generators; the no-input languages (Back, BIO, NoComment, BF-PDA, Lamfunc, Bitdeque, RAM0, Minsky Swap, Eval, ArrowQueue, A Painter Ant, WII2D) use parameterized generators (the harness substitutes input bits into a template).  Minifuck and %^2^-1 use parameterized generators too, for a different reason: both *have* an input command, but neither can branch on what it reads, so their reading models are walled (the %^2^-1 wall is proved in Lean) and embedding is what reaches the two-input tables.  %^2^-1 goes further: a subcube cascade builds every conjunction or disjunction of literals at any arity, and a composed-affine search adds the tables that are no subcube — 86 of the 256 three-input tables, XOR3 among them (see `docs/limitations.md`).

| Language | Text generator | Python | Cross-check | Boolean | Compiler |
| --- | :---: | :---: | :---: | :---: | :---: |
| %^2^-1 | yes | yes |  | yes |  |
| 123 | yes | yes |  | yes |  |
| 3D Brainfuck | yes | yes |  | yes |  |
| 3x | yes | yes |  | yes |  |
| 6-5 | yes | yes |  | yes |  |
| A Painter Ant |  | yes |  | yes |  |
| AddSubJump | yes | yes |  | yes | yes |
| ArrowQueue |  | yes |  | yes |  |
| BF-PDA |  | yes | yes | yes | yes |
| BFStack | yes | yes |  | yes | yes |
| BIO | yes | yes | yes | yes |  |
| Back |  | yes |  | yes |  |
| Basicfuck | yes | yes |  | yes |  |
| Between | yes | yes |  | yes |  |
| Bitdeque |  | yes |  | yes |  |
| BrainIf | yes | yes |  | yes |  |
| COD |  | yes |  | yes |  |
| CV(N)(C) | yes | yes |  | yes |  |
| Circlefuck | yes | yes |  | yes |  |
| Circuit Diagram |  | yes |  | yes |  |
| Clockwise | yes | yes |  | yes |  |
| Collatz Multiverse | yes | yes |  | yes | yes |
| Container | yes | yes |  | yes |  |
| Decleq | yes | yes |  | yes | yes |
| Dig | yes | yes |  | yes |  |
| Dimensional | yes | yes |  | yes |  |
| Eval | yes | yes |  | yes |  |
| Factor | yes | yes |  | yes |  |
| Fargo |  | yes |  | yes |  |
| Flowchart |  | yes |  | yes |  |
| Forbin | yes | yes |  | yes |  |
| Forþ | yes | yes |  | yes | yes |
| Grapheme |  | yes |  | yes |  |
| Home Row | yes | yes |  | yes | yes |
| Jaune |  | yes |  | yes | yes |
| Lamfunc |  | yes |  | yes |  |
| LaserFuck | yes | yes |  | yes |  |
| Minifuck | yes | yes |  | yes |  |
| Minsky Swap |  | yes | yes | yes |  |
| Modulous | yes | yes |  | yes |  |
| MyScript | yes | yes |  | yes |  |
| Nevermind | yes | yes |  | yes |  |
| NoComment | yes | yes | yes | yes |  |
| Painfuck | yes | yes |  | yes |  |
| Point Break |  | yes |  | yes |  |
| Polynomial | yes | yes |  | yes |  |
| Qoibl | yes | yes |  | yes |  |
| RAM0 |  | yes | yes | yes | yes |
| ROTfuck | yes | yes |  | yes |  |
| S*bleq | yes | yes |  | yes | yes |
| SLOW ACV MAMMALIAN | yes | yes |  | yes |  |
| Sophie | yes | yes |  | yes |  |
| Streetcode | yes | yes |  | yes |  |
| Suffolk | yes | yes |  | yes | yes |
| Suptiftam | yes | yes |  | yes |  |
| Taglate | yes | yes |  | yes |  |
| Unsquare | yes | yes |  | yes | yes |
| WII2D | yes | yes |  | yes |  |
| ZTOALC L | yes | yes |  | yes |  |
| bit~ | yes | yes |  | yes |  |
| brainfuck | yes | yes |  | yes |  |

The `esolangs` command lists the languages with Python support:

```bash
esolangs list
```
