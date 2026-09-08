# Language capabilities

Generated from `esolangs/registry.py` by
`scripts/make_languages_doc.py`; do not edit by hand.

## Columns

**Python** means an in-repo interpreter under `esolangs.interpreters`.
**Cross-check** means an implementation in `extra/` that runs as a
standalone program (RISC-V assembly), used to differentially verify
the Python interpreter.  **Boolean** marks the boolean-function
generators.

## Parameterized generators

Parameterized generators embed `{Xi}` input bits in a template. The
harness instantiates and runs one program per input row.

- **The no-input languages** (Back, BIO, NoComment, BF-PDA, Lamfunc,
  Bitdeque, RAM0, Minsky Swap, Eval, ArrowQueue, A Painter Ant, WII2D),
  which have no input command at all.
- **Cod, Minifuck, and %^2^-1**, where embedded input is the supported
  Boolean-generator route. %^2^-1 cannot compute a two-input function
  from runtime input; Cod's edge input would require horizontal routing.

## How %^2^-1 reaches its tables

The generator combines subcube, affine, threshold, band, and fold
constructions. It is exhaustive through four inputs; the fold reaches
sampled generic tables through eleven inputs, and the interleaved
fold reaches generic twelve-input tables.

## The matrix

| Language | Text generator | Python | Cross-check | Boolean | Compiler |
| --- | :---: | :---: | :---: | :---: | :---: |
| %^2^-1 | yes | yes |  | yes |  |
| 123 | yes | yes |  | yes |  |
| 3D Brainfuck | yes | yes |  | yes |  |
| 3x | yes | yes |  | yes |  |
| 6-5 | yes | yes |  | yes |  |
| A Painter Ant |  | yes |  | yes |  |
| AddSubJump | yes | yes |  | yes | yes |
| Algebraic Programming Language |  | yes |  | yes |  |
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
| CV(N)(C) | yes | yes |  | yes | yes |
| Circlefuck | yes | yes |  | yes |  |
| Circuit Diagram |  | yes |  | yes |  |
| Clockwise | yes | yes |  | yes |  |
| Collatz Multiverse | yes | yes |  | yes | yes |
| Container | yes | yes |  | yes | yes |
| Decleq | yes | yes |  | yes | yes |
| Dig | yes | yes |  | yes |  |
| Dimensional | yes | yes |  | yes |  |
| Eval | yes | yes |  | yes |  |
| Factor | yes | yes |  | yes |  |
| Fargo |  | yes |  | yes |  |
| Flowchart |  | yes |  | yes |  |
| Forbin | yes | yes |  | yes | yes |
| Forþ | yes | yes |  | yes | yes |
| Grapheme |  | yes |  | yes |  |
| Home Row | yes | yes |  | yes | yes |
| Inject |  | yes |  | yes |  |
| Jaune |  | yes |  | yes | yes |
| Lamfunc |  | yes |  | yes |  |
| LaserFuck | yes | yes |  | yes |  |
| Minifuck | yes | yes |  | yes |  |
| Minsky Swap |  | yes | yes | yes |  |
| Modulous | yes | yes |  | yes |  |
| MyScript | yes | yes |  | yes | yes |
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
| Super SNUSP | yes | yes |  | yes |  |
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
