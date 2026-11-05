# scripts/

Development tools. Run them through `just` >= 1.37 (`just help` lists every
recipe; `just --completions zsh` completes them, also bash and fish); each
script's `--help` prints its full docstring. `checks/` holds the gate's own
checks, which `just test` runs for you.

| Recipe | Script | Use it to |
| --- | --- | --- |
| `doctor` | `doctor.py` | name what the setup lacks, with the fix; runs without `just` |
| `test`, `test-quick`, `test-mid`, `test-full`, ... | `verify/gate.py` | run the local gate; `--list` names its steps |
| `new-language`, `check-language`, `bounds`, `finish-language` | `new_language.py` | add and check a language; `bounds` measures worst cases and witnesses |
| `docs`, `examples` | `docs/generate.py` | regenerate generated doc sections and committed examples |
| `benchmark` | `benchmark.py` | measure one generated program: size, steps, answers |
| `sizes` | `checks/check_generator_sizes.py` | hold every generator to its committed size baseline |
| `tracediff` | `tracediff.py` | prove an interpreter refactor changes no step |
| `gendiff` | `gendiff.py` | prove a generator refactor changes no byte |
| `deadcode` | `deadcode.py` | list generator code no test reaches; name a language to scan one |
| `mutants` | `mutants.py` | seed generator mutants; survivors are untested behaviour |
| `refresh-ci-timings` | `ci/shard.py` | merge CI timing artifacts |

Weekly CI retains raw generator timing artifacts for manual comparison.

CI-only: `ci/release.py` (normalize and smoke a release, print its notes),
`ci/shard.py` (test sharding).

Not run directly:

- `verify/`, `docs/` -- the packages behind the commands above.
- `_benchmark_worker.py` -- the subprocess `benchmark.py` supervises.
- `baselines/` -- triaged results `deadcode` and `mutants` compare against:
  `deadcode --update` rewrites its baseline.
