# Verification and mutation tooling: measurements and pins

Why `scripts/verify.py` and `scripts/mutate_one.py` are configured the way
they are.  The scripts themselves are authoritative and not restated here;
this file keeps the measurements and version arguments a future change would
otherwise have to re-derive.

## `--cov-branch` is free again on 3.14

`verify.py` asks for `--cov-branch` unconditionally, and the answer has now
flipped twice with the interpreter.

`sys.monitoring` cannot measure branches before 3.14, so asking for arcs
there drops coverage onto the old tracer.  Measured on 3.13 over this suite
(`-n 4`, coverage 7.13.4, the fast selection):

| run | time |
| --- | --- |
| no coverage | 36.5s |
| `--cov` (line, sysmon) | 36.1s |
| `--cov --cov-branch` | 119.3s — 3.3x, the no-sysmon fallback |

3.14's `sys.monitoring` measures branches, so the fallback never happens and
the flag is free again.  Re-measured on 3.14, same suite and flags:

| run | time |
| --- | --- |
| `--cov` (line, sysmon) | 17.81s |
| `--cov --cov-branch` | 17.89s — free |

An older interpreter would silently pay the 3.3x rather than break, so if
this ever feels slow again, check the interpreter before the tests: coverage
says so on stderr with a `no-sysmon` CoverageWarning.

## Why `mutate_one.py` mutates a bundle

Mutating the installed package does not work.  mutmut copies the code into
`mutants/` and runs the suite from there, which fails two ways: naming one
module leaves the other 124 unimportable, and copying all of them means every
module that does trampolined work at *import* time (`registry` building
LANGUAGES, `lamfunc`, ...) fires a trampoline before mutmut has set
`mutmut.config` — "NoneType has no attribute max_stack_depth", once per
module, unfixable one at a time.

So the harness mutates the *bundle* instead.  `scripts/bundle_one.py` already
inlines an interpreter plus its shared modules into one dependency-closed
file whose executable code is byte-identical to the interpreter's (only
docstrings move).  That gives mutmut a single self-contained target, and the
language's own test file — with its imports repointed at the bundle — as the
runner.

## Why mutmut is pinned to 3.7.0

It was pinned to 3.3.1 for a long stretch, against a bug where the trampoline
built its qualname with `mangled_name_from_mutant_name()`, stripping the
class part so that class-method mutants could never be selected and were
silently reported as killed.  3.7.0 does not have it: it carries the class
through the mangled name itself (`mangle_function_name` joins it with a
`CLASS_NAME_SEPARATOR` and `orig_function_and_class_names_from_key` reads it
back), and a run over Minifuck selects and reports all four of its surviving
`_Machine` mutants, which the bug would have hidden.

3.7.0 also drops a class of mutant 3.3.1 emitted: bodies textually identical
to the original.  Bitdeque had one, and it read as a survivor — no test can
kill code that changes nothing — so 3.3.1 scored it 83/84 where 3.7.0 scores
the same suite 83/83.  The higher number is the true one.

When comparing against older notes: mutants are numbered per function in
generation order, so an ID like `__init____mutmut_15` does not refer to the
same edit across the two versions.

## The score floor is 76.7%

Below a set share of mutants killed, a run is treated as broken rather than
reported.  The lowest score this harness has ever legitimately produced is
76.7%, and a suite good enough to be worth mutating does not miss nine
mutants in ten — so a figure down there means they never ran.

## What bounds `verify_no_exception_leaks.py --all`

The step cap is not what makes `--all` expensive.

**Factor is**, and no value of the cap helps: its programs are integers whose
*factorization* is the program, so `make_vm` calls `sympy.factorint` before a
single step runs.  A mutation that alters a digit can turn a factorable
number into a ~120 digit one that is infeasible, and that work is
uninterruptible C — a SIGALRM cannot land on it, since the timer needs a
bytecode boundary.  `Factor prog[69]` (of the seeded corpus) is the specific
run; it wedges a sweep before COD is ever reached.  Bounding it needs a
subprocess with a hard kill, or a digit-length guard on Factor's mutants.

**What the cap costs**, measured on COD, the most expensive language to
*run*.  Five mutants of its example (a dropped or inserted character in the
`~` border) shift the entrance corridor to the tree, so the cod never reaches
open water and loops forever — crossing `+` increments as it goes.  Its value
therefore grows without bound, no state ever repeats, and the cycle detector
cannot decide it: this is the unbounded-growth class, and the programs are
genuinely non-terminating rather than slow.  Those 5 programs x 4 stdins are
20 runs that always reach the cap, and the growing integer makes each step
dearer than the last.

**A smaller cap would not fix the slow languages** — measured, after assuming
otherwise.  Their cost is per-step, not step count: 87 of Painfuck's 376 runs
survive cap 10, and cost ~7ms a step after it, so halving the ceiling only
halves the bill.  Four languages (COD, Factor, Painfuck, Suptiftam) exceed
any cap worth setting, and the subprocess timeout is what actually bounds
them.
