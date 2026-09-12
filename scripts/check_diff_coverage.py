r"""Require every file this branch *touches* to be fully covered."""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# The gate only speaks for the.
# (`source = ["src/esolangs"]`).
# coverage record to check, so.
MEASURED = "src/esolangs/"


def _added_lines(base: str) -> dict[str, set[int]] | None:
    r"""Map each changed file to the line numbers this branch added."""
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
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("@@") and current is not None:
            # "@@ -old,count +new,count @@".
            # are what the branch is adding.
            # length 0 and contributes.
            span = line.split("+")[1].split("@@")[0].strip()
            start, _, count = span.partition(",")
            length = int(count) if count else 1
            if length:
                added.setdefault(current, set()).update(
                    range(int(start), int(start) + length)
                )
    return added


def _rev(*args: str) -> str | None:
    r"""Return the single revision *args* resolves to, or ``None``."""
    got = subprocess.run(
        ["git", *args], capture_output=True, text=True, cwd=ROOT, check=False
    )
    return got.stdout.strip() if got.returncode == 0 and got.stdout.strip() else None


def _diff_base() -> str | None:
    r"""Return the ref to diff against, or ``None`` if there is not one."""
    bases = [
        base
        for ref in ("origin/main", "main")
        if (base := _rev("merge-base", ref, "HEAD")) is not None
    ]
    if bases:
        # `--is-ancestor` orders the.
        # the other is further along.
        # tighter base.
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


def _coverage_json(data_file: Path) -> dict[str, dict[str, Any]] | None:
    r"""Return coverage's per-file executed/missing lines, or ``None``."""
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
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    if got.returncode != 0:
        return None
    # `coverage json -o -` writes.
    # unreadable data file, say).
    # rather than assumed to start.
    start = got.stdout.find("{")
    if start < 0:
        return None
    try:
        return dict(json.loads(got.stdout[start:])["files"])
    except (ValueError, KeyError):
        return None


def main() -> int:
    r"""Check every file this branch touched against the recorded coverage."""
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
            "the suite ran a subset (e.g. -m 'not slow'), so an uncovered line "
            "may simply be covered by a test that did not run: report, do not fail"
        ),
    )
    args = parser.parse_args()

    base = _diff_base()
    if base is None:
        print("skip: no diff base (shallow clone or detached HEAD)")
        return 0

    added = _added_lines(base)
    if added is None:
        print("skip: could not read the branch diff")
        return 0

    targets = {f for f in added if f.startswith(MEASURED)}
    if not targets:
        print(f"skip: branch touched no files under {MEASURED}")
        return 0

    files = _coverage_json(Path(args.data_file))
    if files is None:
        print(f"skip: no usable coverage data at {args.data_file}")
        return 0

    gaps: list[tuple[str, list[int]]] = []
    arc_gaps: list[tuple[str, list[tuple[int, int]]]] = []
    unmeasured: list[str] = []
    checked = 0
    arcs_checked = 0
    # Branch data is optional: a.
    # records no arcs at all, and a.
    # block every such run.
    branch_data = False
    for path in sorted(targets):
        record = files.get(path)
        if record is None:
            # Coverage records a file only.
            # module that no test imports.
            # exists to catch, so it is.
            unmeasured.append(path)
            continue
        # Whole-file: every statement.
        # ones this branch's hunks.
        missing = sorted(record["missing_lines"])
        checked += len(record["executed_lines"]) + len(record["missing_lines"])
        if missing:
            gaps.append((path, missing))

        # An arc is `[from, to]`.
        # leaving the function, which.
        # line number.
        summary = record.get("summary", {})
        if summary.get("num_branches") is None:
            continue
        branch_data = True
        arcs_checked += len(record.get("executed_branches") or ())
        untaken = sorted(
            (arc[0], arc[1]) for arc in record.get("missing_branches") or ()
        )
        arcs_checked += len(untaken)
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

    if args.partial:
        print(
            "\nnot failing: the suite ran a subset, so these may be covered by "
            "tests that did not run.  Re-check with the full suite:\n"
            "  uv run pytest --cov --cov-branch && "
            "uv run python scripts/check_diff_coverage.py"
        )
        return 0
    print(
        "\nEvery file this branch touches must be fully covered.  Add tests for "
        "the lines above, or mark genuinely unreachable ones `# pragma: no cover` "
        "with a comment saying why."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
