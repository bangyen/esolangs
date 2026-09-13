# Documentation

## Start here

| Page | What it answers |
| --- | --- |
| [usage](usage.md) | how to generate, feed and judge a program from Python or the shell |
| [languages](languages.md) | which of the 65 has a generator, a template, an example -- generated from `src/esolangs/registry.py` by `scripts/make_languages_doc.py`, which also fills usage.md's two tables |
| [CONTRIBUTING](CONTRIBUTING.md) | what a new language has to satisfy |

## The three ledgers

They do not overlap: live work, why something cannot be done, and what the
contract is.

| Page | Holds |
| --- | --- |
| [roadmap](roadmap.md) | live work only |
| [walls](walls.md) | falsifiable impossibility claims, each with its structural reason |
| [limitations](limitations.md) | measured contracts, caps, growth laws, and rejected languages |

## Per-generator audits

| Page | Subject |
| --- | --- |
| [wii2d_generator](generators/wii2d_generator.md) | source-size and runtime policy; the embed-convention wall |
| [a_painter_ant_generator](generators/a_painter_ant_generator.md) | construction invariants |
| [a_painter_ant_uniform_proof](generators/a_painter_ant_uniform_proof.md) | the arity proof behind them |
| [arrowqueue_generator](generators/arrowqueue_generator.md) | totality and halting proof |
| [minifuck_generator](generators/minifuck_generator.md) | verified constructions |
| [pct_squared_minus_one_generator](generators/pct_squared_minus_one_generator.md) | six builds |
| [proofs](proofs.md) | the surviving proof certificates, and generator totality |

## Language notes and tooling

| Page | Subject |
| --- | --- |
| [streetcode](streetcode.md) | road and junction rules -- the spec of record |
| [verification_tooling](verification_tooling.md) | `verify.py`, mutation, step scheduling |
| [line_tooling](line_tooling.md) | Line's geometry constraints |
| [SECURITY](SECURITY.md) | what counts as a security report |
