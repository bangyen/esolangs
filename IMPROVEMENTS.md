# Repo improvement review

Baseline: 392 tracked files, ~30k LOC src / ~23k LOC tests, 99.9% line
coverage, strict mypy + 17 ruff rule families, pre-commit, bandit,
pip-audit, differential fuzzing against Rust and RISC-V references, Lean
proofs, and CI checks that fail when generated docs go stale.

The generic hygiene is already done. What follows is what the project's
own tooling does *not* catch.

## Done (commits b2bd0f5, 1fea32a, c249587, eaa8def, cd85960, 9720e9c)

Items 1-5 are fixed and committed:

1. **`just lint-python`** now runs `ruff check` + `ruff format --check` +
   `mypy src` instead of black. Passes on a clean tree.
2. **Classifiers** — dropped the false `3.9`; `3.13` is now backed by a CI
   matrix entry (the full 3397-test suite passes there).
3. **Duplicate CI step** — the two identical `verify_riscv_unicorn.py`
   invocations in the `assembly` job are folded into one.
4. **Stray `docs/roadmap.md` diff** — committed (it was correct
   `end-of-file-fixer` output, not the concurrent session's work).
5. **setuptools floor** — raised to `>=77` for PEP 639, `wheel` dropped.
   Verified failing at 68.0.0 and succeeding at 77.0.3.

6. **`scripts/` under strict mypy** — `files = ["src", "scripts"]`, enforced
   by a new step in CI's lint job, in `scripts/verify.py`, and in
   `just lint-python`. 63 errors fixed; three were latent issues, not just
   annotations (an unguarded `end_lineno + 1` in four places, a dead
   pre-talk-format shim, and fuzz callbacks pinned to the wrong payload
   type). Verified by adding an untyped def to `scripts/` and watching the
   gate reject it.

7. **Weekly randomized fuzz job** — `.github/workflows/fuzz.yml` fuzzes 1000
   programs per language on a fresh seed each Monday, with
   `workflow_dispatch` as the repro path. Prints the seed, count, and commit
   up front (all three are needed to replay, since the fuzzers share one
   sequential RNG). A preflight fails the job if any native reference is
   missing, because the fuzzer's own behaviour is to skip and still exit 0.
   Validated by a real dispatch run: all 19 fuzzers ran, none skipped.

10. **Divergence-detection tests now run in CI** — the 10 tests that prove
    the fuzzer can catch a bug had skipped on every run, on all four Python
    versions, forever. Moved into the `assembly` job (which already has the
    RISC-V toolchain) plus a `cargo build`. The step fails on a skip rather
    than reporting green. CI now shows `10 passed, 5 deselected` in 11.4s.
11. **Stale Lean README paths** — `tools/generators/` → `tools/text/`,
    `mammalian` → `slow_acv_mammalian`.

9. **Repo-level GitHub scaffolding** — `.github/dependabot.yml` watches the
   three ecosystems that exist: `pip` at `/` (where the exact `ruff` and
   `mypy` pins live), `github-actions` at `/` (ci.yml and fuzz.yml), and
   `cargo` at `/extra/rust` (the differential fuzzer's reference crate).
   Monthly, grouped, 5 PRs per ecosystem. Plus `ISSUE_TEMPLATE/` with a bug
   report that asks for the language, a minimal program, and the commit, and
   a new-language form that points at `docs/roadmap.md`'s admission criteria
   first.

   One gap this cannot close: **dependabot has no pre-commit ecosystem**, so
   the hook `rev`s in `.pre-commit-config.yaml` still go stale silently and
   need `pre-commit autoupdate` by hand. Since two of those revs (`ruff`
   v0.16.2, `mypy` v2.3.0) must stay in step with the pyproject pins that
   dependabot *does* watch, a dependabot PR bumping either one is the signal
   to run autoupdate. That is recorded in a comment at the top of
   `dependabot.yml` rather than left implicit.

`scripts/verify.py` passes end to end (all steps green).

## Still open



### 8. No release, no tags

`git tag -l` is empty, version has been `0.1.0` throughout, and the name
`esolangs` is unclaimed on PyPI (404). The package builds cleanly today
(`uv build` produces both sdist and wheel), declares `py.typed`, and ships a
console entry point.

If distribution is wanted: fix the build-system floor (#5), tag `v0.1.0`, add a release workflow using PyPI
trusted publishing (OIDC, no token to store), and claim the name. If it is
deliberately git-only, then say so in the README and drop
`Development Status :: 4 - Beta` — right now the metadata reads like a
package meant to be installed from an index.

`SECURITY.md` is still absent, but it only earns its place if #8 ships a
package to an index; a git-only repo does not need one.

## Also checked, nothing found

No TODO/FIXME/HACK markers in tracked source, no assertion-free tests, no
broken relative links in tracked docs, every documented module path resolves,
README and `docs/languages.md` agree with the registry (58 languages), and
the Lean proofs carry no `sorry` or `axiom`.

## Deliberately not suggested

- **New interpreters** — `docs/roadmap.md` already tracks candidates with
  admission criteria; that is the owner's call, not a review finding.
- **More tests** — coverage is 99.9%; the only module below 100% is
  `interpreters/tape_based/one_two_three.py` at 93.8% (4 lines).
- **Splitting `vm.py`** (1,966 lines) — it is 99.1% covered and the size
  alone is not evidence of a maintenance problem.
- **README work** — recently and deliberately curated per the last three
  commits.

## Suggested order

#8 is the only item left, and it is a decision rather than a task: publish
`v0.1.0` to PyPI (tag, trusted-publishing workflow, claim the name), or
declare the repo git-only in the README and drop the
`Development Status :: 4 - Beta` classifier that currently implies otherwise.
Either answer closes it; leaving it open is what keeps the metadata
misleading.
