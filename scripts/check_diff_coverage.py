"""Require 90% statement and branch coverage in each touched Python file.

The diff selects files. Partial runs judge only added executable statements
and branches, allowing slower bands to cover the rest. Missing measurements
still fail in strict mode; modules never imported always fail.
"""

import argparse
import fnmatch
import json
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# The gate only speaks for the package coverage is configured to measure
# (`source = ["src/esolangs"]`).  A touched file in tests/ or scripts/ has no
# coverage record to check, so it is not evidence of anything either way.
MEASURED = "src/esolangs/"
MIN_COVERAGE = 90


def _omitted() -> list[str]:
    """Return coverage's own ``omit`` patterns from ``pyproject.toml``.

    A file coverage was told to omit (``_template.py``) never gets a record,
    so without this the gate would read it as a module no test imports.
    """
    with (ROOT / "pyproject.toml").open("rb") as fh:
        config = tomllib.load(fh)
    return list(
        config.get("tool", {}).get("coverage", {}).get("run", {}).get("omit", [])
    )


def _added_lines(base: str) -> dict[str, set[int]] | None:
    """Map each changed file to the line numbers this branch added.

    ``-U0`` asks for no context, so every line the hunk reports as added is one
    the branch is answerable for.  Returns ``None`` when the diff cannot be
    read, which the caller must treat as "cannot tell", never as "nothing
    changed".
    """
    got = subprocess.run(
        ["git", "diff", "-U0", base, "--"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    if got.returncode != 0:
        return None

    added: dict[str, set[int]] = {}
    current: str | None = None
    for line in got.stdout.splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else None
            if current is not None:
                # Deleting code still touches the surviving file: whole-file
                # coverage must judge it even when no new lines were added.
                added.setdefault(current, set())
        elif line.startswith("@@") and current is not None:
            # "@@ -old,count +new,count @@" -- the new-side start and length
            # are what the branch is adding.  A hunk that deletes only has
            # length 0 and contributes nothing.
            span = line.split("+")[1].split("@@")[0].strip()
            start, _, count = span.partition(",")
            length = int(count) if count else 1
            if length:
                added.setdefault(current, set()).update(
                    range(int(start), int(start) + length)
                )
    return added


def _rev(*args: str) -> str | None:
    """Return the single revision *args* resolves to, or ``None``."""
    got = subprocess.run(
        ["git", *args], capture_output=True, text=True, cwd=ROOT, check=False
    )
    return got.stdout.strip() if got.returncode == 0 and got.stdout.strip() else None


def _diff_base() -> str | None:
    """Return the ref to diff against, or ``None`` if there is not one.

    The merge-base with main is the branch's own starting point, so diffing
    against it attributes exactly the branch's work and not whatever landed on
    main meanwhile.

    Both spellings of main are consulted, and the *newer* merge-base wins.
    ``origin/main`` alone is wrong whenever local ``main`` is ahead of it --
    commits that are merely unpushed are not this branch's work, but a base
    behind them attributes every line they touched to whoever runs the gate.
    A worktree cut from a stale ``origin/main`` hits this immediately, and the
    symptom is a gate that blames files the branch never opened.

    ``HEAD~1`` is the last resort for a shallow clone or a detached HEAD,
    matching :func:`_scope.changed_files`.
    """
    bases = [
        base
        for ref in ("origin/main", "main")
        if (base := _rev("merge-base", ref, "HEAD")) is not None
    ]
    if bases:
        # `--is-ancestor` orders the two candidates: the one *descended* from
        # the other is further along the branch's history, so it is the
        # tighter base.  Equal bases make either answer the same.
        best = bases[0]
        for other in bases[1:]:
            if _rev("rev-parse", best) != _rev("rev-parse", other) and (
                subprocess.run(
                    ["git", "merge-base", "--is-ancestor", best, other],
                    cwd=ROOT,
                    check=False,
                    capture_output=True,
                ).returncode
                == 0
            ):
                best = other
        return best
    return _rev("rev-parse", "HEAD~1")


def _coverage_json(
    data_file: Path, targets: set[str]
) -> dict[str, dict[str, Any]] | None:
    """Return coverage data for ``targets``, or ``None``.

    Reads through ``coverage json`` rather than the ``.coverage`` SQLite file
    directly: the report applies the ``exclude_lines`` patterns from
    pyproject, so a line the project has deliberately excluded is already gone
    from ``missing_lines`` and cannot fail the gate.
    """
    if not data_file.exists():
        return None
    got = subprocess.run(
        [
            sys.executable,
            "-m",
            "coverage",
            "json",
            "-o",
            "-",
            "--data-file",
            str(data_file),
            "--include",
            ",".join(sorted(targets)),
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    if got.returncode != 0:
        return None
    # `coverage json -o -` writes the document to stdout, but a warning (an
    # unreadable data file, say) lands there too, so the payload is located
    # rather than assumed to start at byte zero.
    start = got.stdout.find("{")
    if start < 0:
        return None
    try:
        return dict(json.loads(got.stdout[start:])["files"])
    except (ValueError, KeyError):
        return None


def main() -> int:
    """Check every file this branch touched against the recorded coverage."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-file",
        default=str(ROOT / ".coverage"),
        help="coverage data file written by the pytest step",
    )
    parser.add_argument(
        "--partial",
        action="store_true",
        help=(
            "the suite ran a subset: require 90 percent coverage of added statements "
            "and branches per file"
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="fail when diff or line/branch coverage evidence is unavailable",
    )
    args = parser.parse_args()
    label = "error" if args.strict else "skip"

    base = _diff_base()
    if base is None:
        print(f"{label}: no diff base (shallow clone or detached HEAD)")
        return int(args.strict)

    added = _added_lines(base)
    if added is None:
        print(f"{label}: could not read the branch diff")
        return int(args.strict)

    omitted = _omitted()
    targets = {
        f
        for f in added
        if f.startswith(MEASURED)
        and f.endswith(".py")
        and not any(fnmatch.fnmatch(f, pattern) for pattern in omitted)
    }
    if not targets:
        print(f"skip: branch touched no files under {MEASURED}")
        return 0

    files = _coverage_json(Path(args.data_file), targets)
    if files is None:
        print(f"{label}: no usable coverage data at {args.data_file}")
        return int(args.strict)

    gaps: list[tuple[str, list[int]]] = []
    arc_gaps: list[tuple[str, list[tuple[int, int]]]] = []
    unmeasured: list[str] = []
    line_totals: dict[str, int] = {}
    branch_totals: dict[str, int] = {}
    checked = 0
    arcs_checked = 0
    # Branch data is optional: a `pytest --cov` run without `--cov-branch`
    # records no arcs at all, and a gate that failed on its absence would
    # block every such run.  Only a file that *has* arc data is judged on it.
    branch_data = False
    for path in sorted(targets):
        record = files.get(path)
        if record is None:
            # Coverage records a file only if it was imported.  A brand-new
            # module that no test imports yet is exactly the gap this gate
            # exists to catch, so it is reported rather than skipped.
            unmeasured.append(path)
            continue
        # Whole-file: every statement coverage knows about, not just the
        # ones this branch's hunks happen to name.
        missing = sorted(record["missing_lines"])
        checked += len(record["executed_lines"]) + len(record["missing_lines"])
        statements = [*record["executed_lines"], *missing]
        line_totals[path] = sum(
            not args.partial or line in added[path] for line in statements
        )
        if missing:
            gaps.append((path, missing))

        # An arc is `[from, to]`.  A negative `to` is coverage's spelling for
        # leaving the function, which is a real untaken exit rather than a
        # line number.
        summary = record.get("summary", {})
        if summary.get("num_branches") is None:
            if args.strict:
                print(f"error: no branch coverage data for {path}")
                return 1
            continue
        branch_data = True
        arcs_checked += len(record.get("executed_branches") or ())
        untaken = sorted(
            (arc[0], arc[1]) for arc in record.get("missing_branches") or ()
        )
        arcs_checked += len(untaken)
        arcs = [*(record.get("executed_branches") or ()), *untaken]
        branch_totals[path] = sum(
            not args.partial or arc[0] in added[path] for arc in arcs
        )
        if untaken:
            arc_gaps.append((path, untaken))

    if not gaps and not arc_gaps and not unmeasured:
        summary = (
            f"touched-file coverage: 100% "
            f"({len(targets)} file(s), {checked} statement(s)"
        )
        summary += f", {arcs_checked} branch(es))" if branch_data else ")"
        print(summary)
        return 0

    if gaps:
        total = sum(len(m) for _, m in gaps)
        print(
            f"touched-file coverage: {total} statement(s) never executed "
            f"in {len(gaps)} touched file(s)"
        )
        for path, missing in gaps:
            spans = ",".join(str(n) for n in missing)
            print(f"  {path}: {spans}")

    if arc_gaps:
        total_arcs = sum(len(a) for _, a in arc_gaps)
        print(f"touched-file branches: {total_arcs} branch(es) never taken")
        for path, untaken in arc_gaps:
            for src, dest in untaken:
                where = "exit" if dest < 0 else f"line {dest}"
                print(f"  {path}: line {src} never continues to {where}")

    if unmeasured:
        print(f"touched but never imported by the suite: {len(unmeasured)} file(s)")
        for path in unmeasured:
            print(f"  {path}")

    blocking_gaps = [
        (path, [line for line in missing if line in added[path]])
        for path, missing in gaps
    ]
    blocking_gaps = [(path, missing) for path, missing in blocking_gaps if missing]
    blocking_arcs = [
        (path, [arc for arc in arcs if arc[0] in added[path]])
        for path, arcs in arc_gaps
    ]
    blocking_arcs = [(path, arcs) for path, arcs in blocking_arcs if arcs]

    line_gaps = blocking_gaps if args.partial else gaps
    branch_gaps = blocking_arcs if args.partial else arc_gaps
    below = any(
        len(missing) * 100 > line_totals[path] * (100 - MIN_COVERAGE)
        for path, missing in line_gaps
    ) or any(
        len(missing) * 100 > branch_totals[path] * (100 - MIN_COVERAGE)
        for path, missing in branch_gaps
    )
    if not below and not unmeasured:
        if (
            args.partial
            and (gaps or arc_gaps)
            and not blocking_gaps
            and not blocking_arcs
        ):
            print("not failing on gaps outside added lines: the suite ran a subset.")
        print(f"coverage meets {MIN_COVERAGE}% minimum per touched file")
        return 0
    if args.partial:
        print(
            f"Added statements and branches require at least {MIN_COVERAGE}% "
            "coverage per file."
        )
    else:
        print(
            f"Every touched file needs at least {MIN_COVERAGE}% "
            "statement and branch coverage."
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
