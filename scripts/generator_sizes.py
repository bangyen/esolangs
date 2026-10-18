"""Load and store generator size baselines from package ``language.toml``.

Each boolean generator's committed size/step baseline lives in its own
package's ``[generator_sizes]`` section, one inline table per benchmark
table; this module is the dataset's one aggregator and its one writer.
A package with no file or no section contributes nothing (an interpreter-
only language, or one the sweep has not recorded yet).

TOML has no null, and the baseline needs two: a language that cannot be
stepped records ``commands = null``, and individual rows can be null
inside an otherwise steppable record.  A fragment omits a null
``commands`` outright and lists null rows by index in
``commands_by_row_nulls``; aggregation reconstructs the exact JSON-era
record shape, nulls included.
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from docs.fragments import AggregateKey, aggregate

if TYPE_CHECKING:
    from esolangs.registry import Language

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ROOT / "src" / "esolangs" / "languages"
FRAGMENT = "language.toml"
SECTION = "generator_sizes"
_HEADER = (
    "# Language-owned data, one section per dataset; aggregators read\n"
    "# only their own section and skip this file when it is absent.\n\n"
)
_FIELDS = frozenset(
    {"source_units", "commands", "commands_by_row", "commands_by_row_nulls"}
)


def _section(path: Path) -> dict[str, Any] | None:
    """Return ``path``'s generator_sizes section, or None when it has none."""
    table = tomllib.loads(path.read_text(encoding="utf-8")).get(SECTION)
    if table is None:
        return None
    if not isinstance(table, dict):
        raise ValueError(f"{path}: [{SECTION}] must be a table")
    return table


def _count(path: Path, table: str, key: str, value: object) -> int:
    """Return ``value`` after checking it is a nonnegative int, not a bool."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{path}: [{SECTION}] {table!r} {key} must be a count")
    return value


def _validate_row(path: Path, table: str, row: object) -> dict[str, Any]:
    """Return the JSON-shaped record for one benchmark table's fragment row."""
    if not isinstance(row, dict):
        raise ValueError(f"{path}: [{SECTION}] {table!r} must be a table")
    unknown = set(row) - _FIELDS
    if unknown:
        raise ValueError(f"{path}: [{SECTION}] {table!r} keys {sorted(unknown)}")
    if "source_units" not in row:
        raise ValueError(f"{path}: [{SECTION}] {table!r} needs source_units")
    units = _count(path, table, "source_units", row["source_units"])
    if units == 0:
        raise ValueError(f"{path}: [{SECTION}] {table!r} source_units must be > 0")
    record: dict[str, Any] = {
        "source_units": units,
        "commands": (
            _count(path, table, "commands", row["commands"])
            if "commands" in row
            else None
        ),
    }
    if "commands_by_row" in row or "commands_by_row_nulls" in row:
        by_row: dict[str, Any] = {}
        stored = row.get("commands_by_row", {})
        if not isinstance(stored, dict):
            raise ValueError(f"{path}: [{SECTION}] {table!r} commands_by_row")
        for key, value in stored.items():
            if not key.isdigit():
                raise ValueError(f"{path}: [{SECTION}] {table!r} row {key!r}")
            by_row[key] = _count(path, table, f"row {key}", value)
        nulls = row.get("commands_by_row_nulls", [])
        if not isinstance(nulls, list):
            raise ValueError(f"{path}: [{SECTION}] {table!r} null rows")
        seen: set[int] = set()
        for index in nulls:
            _count(path, table, "null row", index)
            if index in seen or str(index) in by_row:
                raise ValueError(f"{path}: [{SECTION}] {table!r} null row {index}")
            seen.add(index)
            by_row[str(index)] = None
        record["commands_by_row"] = by_row
    return record


def _validate_section(path: Path, section: dict[str, Any]) -> dict[str, Any]:
    """Return every record in one package's section, keyed by table bits."""
    records: dict[str, Any] = {}
    for table, row in section.items():
        if not table or set(table) - {"0", "1"}:
            raise ValueError(f"{path}: [{SECTION}] key {table!r} is not a table")
        records[table] = _validate_row(path, table, row)
    return records


def _aggregate_fragments(
    packages: Path, languages: Iterable[Language]
) -> dict[str, dict[str, Any]]:
    """Merge every package's generator_sizes section, keyed by language name.

    ``languages`` is the registry, in registry order; discovery follows
    it, never a second list.  A section in an unregistered package, an
    unknown key, or a value of the wrong type raises ``ValueError``, as
    does a repeated language.
    """
    rows: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()
    for lang in languages:
        if lang.id in seen:
            raise ValueError(f"duplicate language id: {lang.id}")
        seen.add(lang.id)
        path = packages / lang.id / FRAGMENT
        if not path.is_file():
            continue
        section = _section(path)
        if section is not None:
            if lang.name in rows:
                raise ValueError(f"duplicate language name: {lang.name}")
            rows[lang.name] = _validate_section(path, section)
    if packages.is_dir():
        for path in packages.glob(f"*/{FRAGMENT}"):
            if path.parent.name not in seen and _section(path) is not None:
                raise ValueError(f"{path}: [{SECTION}] in an unregistered package")
    return rows


#: Aggregates by (packages, registry, fragment fingerprint): repeat
#: loads within a process reuse the first parse instead of re-reading
#: every fragment -- the writer's own rewrites included, since an edit
#: changes the fingerprint.
_AGGREGATES: dict[AggregateKey, dict[str, dict[str, Any]]] = {}


def aggregate_fragments(
    packages: Path, languages: Iterable[Language]
) -> dict[str, dict[str, Any]]:
    """Merge the generator_sizes sections, cached per process.

    See :func:`_aggregate_fragments` for the merge rules and
    :mod:`docs.fragments` for the caching discipline.
    """
    return aggregate(_AGGREGATES, packages, languages, _aggregate_fragments)


def _render_row(record: Mapping[str, Any]) -> str:
    """Return one record as a TOML inline table, nulls encoded as omissions."""
    parts = []
    if record.get("commands") is not None:
        parts.append(f"commands = {record['commands']}")
    if "commands_by_row" in record:
        by_row = record["commands_by_row"]
        stored = {k: v for k, v in by_row.items() if v is not None}
        inner = ", ".join(f'"{key}" = {stored[key]}' for key in sorted(stored, key=int))
        rendered_rows = f"{{ {inner} }}" if inner else "{}"
        parts.append(f"commands_by_row = {rendered_rows}")
        nulls = sorted(int(k) for k, v in by_row.items() if v is None)
        if nulls:
            parts.append(f"commands_by_row_nulls = {nulls}")
    parts.append(f"source_units = {record['source_units']}")
    return "{ " + ", ".join(parts) + " }"


def render_section(records: Mapping[str, Any]) -> str:
    """Return the ``[generator_sizes]`` block for one package's records."""
    lines = [f"[{SECTION}]"]
    for table in sorted(records):
        lines.append(f'"{table}" = {_render_row(records[table])}')
    return "\n".join(lines) + "\n"


def _section_span(lines: list[str]) -> tuple[int, int] | None:
    """Return the [start, end) line span of the section, blanks included."""
    start = next(
        (i for i, line in enumerate(lines) if line.strip() == f"[{SECTION}]"),
        None,
    )
    if start is None:
        return None
    end = start + 1
    while end < len(lines) and not lines[end].startswith("["):
        end += 1
    return start, end


def _replace_section(text: str, rendered: str | None) -> str:
    """Return ``text`` with its generator_sizes section swapped or dropped.

    Only the section's own span changes; everything else is byte-preserved,
    and the result is parsed back to prove no sibling section moved.  A
    section reaching end of file leaves the file ending in exactly one
    newline, so a second write over the same records changes nothing.
    """
    before = tomllib.loads(text) if text.strip() else {}
    lines = text.split("\n")
    span = _section_span(lines)
    block = rendered.rstrip("\n").split("\n") if rendered is not None else []
    if span is None:
        if not block:
            return text
        body = lines[:-1] if lines and lines[-1] == "" else lines
        merged = body + ([""] if body and body[-1] != "" else []) + block + [""]
    else:
        start, end = span
        if any(line.startswith("#") for line in lines[start + 1 : end]):
            raise ValueError(f"comment inside the [{SECTION}] span; move it out")
        tail = lines[end:]
        if all(line == "" for line in tail):
            head = lines[:start]
            while head and head[-1] == "":
                head.pop()
            merged = head + ([""] if head and block else []) + block + [""]
        else:
            merged = lines[:start] + block + ([""] if block else []) + tail
    result = "\n".join(merged)
    after = tomllib.loads(result)
    for key in set(before) | set(after):
        if key != SECTION and before.get(key) != after.get(key):
            raise ValueError(f"section surgery disturbed [{key}]")
    return result


def write_fragments(
    packages: Path,
    languages: Iterable[Language],
    records: Mapping[str, Mapping[str, Any]],
) -> bool:
    """Write each language's records into its package fragment.

    Returns True when any file changed.  A language with no records loses
    its section; a measured name outside the registry raises, since the
    sweep only ever measures registered languages.
    """
    by_name = {lang.name: lang for lang in languages}
    unknown = set(records) - set(by_name)
    if unknown:
        raise ValueError(f"measured languages not in the registry: {sorted(unknown)}")
    changed = False
    for lang in by_name.values():
        path = packages / lang.id / FRAGMENT
        rows = records.get(lang.name)
        rendered = render_section(rows) if rows else None
        if not path.is_file():
            if rendered is None:
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_HEADER + rendered, encoding="utf-8")
            changed = True
            continue
        text = path.read_text(encoding="utf-8")
        new_text = _replace_section(text, rendered)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            changed = True
    return changed
