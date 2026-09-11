# Language capabilities

Generated from `esolangs/registry.py` by
`scripts/make_languages_doc.py`; do not edit by hand.

## Columns

**Python** means an in-repo interpreter under `esolangs.interpreters`.
**Boolean** marks the boolean-function generators.

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
fold reaches generic twelve- and thirteen-input tables.

## The matrix

| Language | Python | Boolean |
| --- | :---: | :---: |
| %^2^-1 | yes | yes |
| 123 | yes | yes |
| 3D Brainfuck | yes | yes |
| 3x | yes | yes |
| 6-5 | yes | yes |
| A Painter Ant | yes | yes |
| AddSubJump | yes | yes |
| Algebraic Programming Language | yes | yes |
| Alight | yes | yes |
| ArrowQueue | yes | yes |
| BF-PDA | yes | yes |
| BFStack | yes | yes |
| BIO | yes | yes |
| Back | yes | yes |
| Basicfuck | yes | yes |
| Between | yes | yes |
| Bitdeque | yes | yes |
| BrainIf | yes | yes |
| COD | yes | yes |
| CV(N)(C) | yes | yes |
| Circlefuck | yes | yes |
| Circuit Diagram | yes | yes |
| Clockwise | yes | yes |
| Collatz Multiverse | yes | yes |
| Container | yes | yes |
| DINAC | yes | yes |
| Decleq | yes | yes |
| Dig | yes | yes |
| Dimensional | yes | yes |
| Eval | yes | yes |
| Factor | yes | yes |
| Fargo | yes | yes |
| Flowchart | yes | yes |
| Forbin | yes | yes |
| Forþ | yes | yes |
| Grapheme | yes | yes |
| Home Row | yes | yes |
| Inject | yes | yes |
| Interprogck8 | yes | yes |
| Jaune | yes | yes |
| Lamfunc | yes | yes |
| LaserFuck | yes | yes |
| Minifuck | yes | yes |
| Minsky Swap | yes | yes |
| Modulous | yes | yes |
| MyScript | yes | yes |
| Nevermind | yes | yes |
| NoComment | yes | yes |
| Packlang | yes | yes |
| Painfuck | yes | yes |
| Point Break | yes | yes |
| Polynomial | yes | yes |
| Qoibl | yes | yes |
| RAM0 | yes | yes |
| ROTfuck | yes | yes |
| S*bleq | yes | yes |
| SLOW ACV MAMMALIAN | yes | yes |
| Sophie | yes | yes |
| Streetcode | yes | yes |
| Suffolk | yes | yes |
| Super SNUSP | yes | yes |
| Suptiftam | yes | yes |
| Taglate | yes | yes |
| Unsquare | yes | yes |
| WII2D | yes | yes |
| ZTOALC L | yes | yes |
| bit~ | yes | yes |
| brainfuck | yes | yes |
| function x(y) | yes | yes |

The `esolangs` command lists the languages with Python support:

```bash
esolangs list
```
