"""Regenerate the committed documentation and the tools export block."""

import sys
from pathlib import Path

# scripts/ holds the sibling `verify`, `docs`, and `ci` packages.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import ast
import builtins
import inspect
import pathlib
import re
import shlex

import esolangs
from docs.catalogue import load as _catalogue_load
from docs.curation import dates as _curation_dates
from docs.curation import rows as _curation_rows
from docs.proof_status import splice, update_docs
from docs.writing import write_if_changed as _write_if_changed
from esolangs.languages.generators import BOOLEAN
from esolangs.registry import LANGUAGES, SourceKind, wiki_url
from esolangs.registry._language import Shape


def main() -> int:
    """Dispatch one generation command."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "target",
        choices=("docs", "examples"),
        help="docs: the generated README and docs sections; examples: the "
        "committed example programs",
    )
    parser.add_argument(
        "args", nargs=argparse.REMAINDER, help="passed to examples (see its --help)"
    )
    args = parser.parse_args()
    if args.target == "docs":
        if args.args:
            parser.error("docs takes no arguments")
        return docs_main()
    if args.target == "examples":
        from docs.examples import examples_main

        return examples_main(args.args)
    raise AssertionError(args.target)


ROOT = pathlib.Path(__file__).resolve().parents[2]


# The README's Implemented Languages section, grouped by interpreter
# category.  The list order is the classification priority (a language is
# filed by its most distinctive data structure): grid (a beam/pointer moving
# on a 2D surface) > stack > queue > tape > register (the imperative
# default) > program > variables > other.
_README_HEADINGS = [
    (
        "grid_based",
        "Grid-based Languages",
        "Languages that move a pointer or beam across a 2D grid.",
    ),
    (
        "stack_based",
        "Stack-based Languages",
        "Languages that use a stack for data manipulation.",
    ),
    (
        "queue_based",
        "Queue-based Languages",
        "Languages whose primary data structure is a queue or deque.",
    ),
    (
        "tape_based",
        "Tape-based Languages",
        "Languages that operate on a tape (similar to Turing machines).",
    ),
    (
        "register_based",
        "Register-based Languages",
        "Languages that use registers to store and manipulate data.",
    ),
    (
        "program_based",
        "Self-modifying Languages",
        "Languages whose data is the program itself, rewritten as it runs.",
    ),
    (
        "variable_based",
        "Variable-based Languages",
        "Languages that store data in named variables the program declares.",
    ),
    (
        "other",
        "Other Languages",
        "Languages that don't fit into the above categories.",
    ),
]

# language-owners: ["Fargo", "Taglate"]
#: The bit vector the stdin table is rendered for.  Three bits, because an
#: odd count is what makes Taglate's padding visible -- at two it encodes
#: like everything else, and Fargo's decimal and binary readings coincide
#: below four.
_SAMPLE_BITS = [1, 0, 1]


def render_package_count_section() -> str:
    """Render the total and source-shape counts in the README lead."""
    text_count = sum(lang.source_kind is SourceKind.TEXT for lang in LANGUAGES.values())
    return (
        f"Interpreters and Boolean generators for {len(LANGUAGES)} esoteric "
        f"languages: {text_count} text and "
        f"{len(LANGUAGES) - text_count} raster."
    )


def _source_link(name: str) -> str:
    """Return the GitHub URL of the language's Python interpreter."""
    canonical = ROOT / "src/esolangs/languages" / LANGUAGES[name].id / "interpreter"
    for source in (canonical.with_suffix(".py"), canonical / "__init__.py"):
        if source.is_file():
            relative = source.relative_to(ROOT).as_posix()
            return f"https://github.com/bangyen/esolangs/blob/main/{relative}"
    raise FileNotFoundError(f"no canonical interpreter for {name}")


def render_languages_section() -> str:
    """Render the README's Implemented Languages section between the markers.

    Each language with an in-repo interpreter is grouped by the interpreter's
    category, sorted by display name, and linked to both its esolangs wiki
    page and the interpreter's source file on GitHub.
    """
    out: list[str] = []
    groups: dict[str, list[str]] = {prefix: [] for prefix, _, _ in _README_HEADINGS}
    for name, lang in LANGUAGES.items():
        if lang.interpreter is None:
            continue
        category = lang.category
        if category not in groups:
            raise ValueError(
                f"{name}'s interpreter category {category!r} has no README "
                "heading; add one to _README_HEADINGS in scripts/docs/generate.py"
            )
        groups[category].append(name)

    for prefix, heading, description in _README_HEADINGS:
        out.append(f"### {heading}")
        out.append("")
        out.append(description)
        out.append("")
        # Separate README and describe slugs once duplicated the same escaping
        # bug; use the registry's URL builder for both.
        for name in sorted(groups[prefix]):
            tier = (
                "" if LANGUAGES[name].boolean is not None else " *(interpreter-only)*"
            )
            out.append(
                f"- [{name}]({wiki_url(name)}) ([code]({_source_link(name)})){tier}"
            )
        out.append("")
    return "\n".join(out).rstrip()


def render_examples_section() -> str:
    """Render the README's Examples paragraph between the markers.

    The count is the number of registered boolean generators, taken from
    the registry rather than from a directory listing -- the same rule the rest
    of this script follows.  A separate sync test already pins that every
    generator has its committed file, so the registry is the source that
    cannot drift.
    """
    count = sum(esolangs.describe(name)["boolean_generator"] for name in LANGUAGES)
    return "\n".join(
        [
            f"Ready-to-run programs for each of the {count}",
            "languages with a boolean generator live in",
            "each language's [directory]"
            "(https://github.com/bangyen/esolangs/tree/main/src/esolangs/languages).",
        ]
    )


def render_boolean_count_section() -> str:
    """Render the README's boolean-generator count between the markers."""
    return "\n".join(
        [
            "The truth table is a binary string of length `2**n`,"
            " most-significant input",
            f"first; its length implies `n`, so it isn't passed separately."
            f"  {len(BOOLEAN)} of the",
            "languages have such a generator, some covering only a"
            " documented subset of",
            "tables.",
        ]
    )


def render_contributor_tools_section() -> str:
    """Render the generator directory after checking it against the registry."""
    root = ROOT / "src" / "esolangs"
    for language in LANGUAGES.values():
        if language.boolean is None:
            continue
        source = pathlib.Path(language.boolean.__code__.co_filename).resolve()
        colocated = root / "languages" / language.id / "generator"
        if not (
            source.is_relative_to(colocated.resolve())
            or source == colocated.with_suffix(".py").resolve()
        ):
            raise ValueError(f"{language.name}'s generator is outside {colocated}")
    return "| `src/esolangs/generation/` | shared generator helpers |"


def _reads_stdin() -> list[str]:
    """Return the languages that take their inputs on stdin, sorted."""
    names = esolangs.list_languages()
    return sorted(name for name in names if esolangs.describe(name)["reads_input"])


def _is_exceptional(name: str) -> bool:
    """Return whether the stdin is anything but adjacent ``0``/``1`` characters."""
    record = esolangs.describe(name)
    shape = record["input_shape"]
    alphabet = tuple(record["input_encoding"] or ())
    return shape != "char_stream" or alphabet != ("0", "1")


def render_input_shapes_section() -> str:
    """Render docs/usage.md's stdin table between the markers.

    Every cell is ``repr(encode_inputs(language, [1, 0, 1]))``, so the table
    is the encoder's own output rather than a description of it.  This
    replaced three hand-written prose copies of the same four exceptions;
    one of them called an integer row index a bits-on-one-line input, returned
    0 where the answer was 1, and was believed because it read plausibly.
    """
    reading = _reads_stdin()
    odd = [name for name in reading if _is_exceptional(name)]
    rows = [
        "| Language | `input_shape` | Alphabet | stdin for inputs 1, 0, 1 |",
        "| --- | --- | --- | --- |",
    ]
    for name in odd:
        record = esolangs.describe(name)
        alphabet = "/".join(
            f"`{c if c.isprintable() else repr(c)[1:-1]}`"
            for c in record["input_encoding"] or ()
        )
        stdin = repr(esolangs.encode_inputs(name, _SAMPLE_BITS))
        rows.append(f"| {name} | `{record['input_shape']}` | {alphabet} | `{stdin}` |")
    default = repr(esolangs.encode_inputs("brainfuck", _SAMPLE_BITS))
    embedded = sum(1 for name in LANGUAGES if esolangs.describe(name)["parameterized"])
    classics = sum(
        1 for name in LANGUAGES if esolangs.describe(name)["boolean_generator"] is False
    )
    rows.extend(
        [
            "",
            f"The other {len(reading) - len(odd)} that read stdin take one"
            f" `0`/`1` character per bit -- `{default}`.",
            f"The remaining {embedded} embed their inputs and read no stdin:"
            " `instantiate` fills them.",
            *(
                [
                    f"The {classics} interpreter-only classics have no"
                    " generator, so there is no generated stdin to feed."
                ]
                if classics
                else []
            ),
            "Use `encode_inputs` to build stdin; it and this table use `describe`.",
        ]
    )
    return "\n".join(rows)


def render_api_section() -> str:
    """Render docs/usage.md's exported-callable list between the markers.

    ``esolangs.__all__`` filtered to functions, one per line with the first
    line of its docstring.  The gate that used to demand all of these in a
    single README sentence is what produced a thirteen-name run-on; this
    list carries the same guarantee and no sentence.
    """
    lines = []
    for name in esolangs.__all__:
        member = getattr(esolangs, name)
        if not inspect.isfunction(member):
            continue
        summary = (inspect.getdoc(member) or "").split("\n")[0].rstrip(".")
        # The docstrings are reStructuredText; a role marker and a double
        # backtick both render as literal text in Markdown.
        summary = re.sub(r":\w+:`~?([^`]+)`", r"`\1`", summary)
        summary = summary.replace("``", "`")
        lines.append(f"- `esolangs.{name}` -- {summary[0].lower()}{summary[1:]}")
    return "\n".join(lines)


def xor_language() -> str:
    """Return the language whose XOR program the README shows first.

    The shortest XOR among the languages reading their inputs as adjacent
    characters, so it is short enough to read and never a removed language.
    """
    readers = [
        name
        for name in LANGUAGES
        if (facts := esolangs.describe(name))["boolean_generator"]
        and not facts["parameterized"]
        and not facts["random"]
        and facts["answer_mode"] == "output"
        and facts["input_shape"] == "char_stream"
        and facts["source_kind"] == "text"
    ]
    return min(readers, key=lambda name: len(str(esolangs.generate(name, "0110"))))


def render_xor_section() -> str:
    """Render the README's first example: a generated XOR, and its length."""
    language = xor_language()
    program = str(esolangs.generate(language, "0110"))
    return "\n".join(
        [
            f"`esolangs generate {shlex.quote(language)} 0110` emits"
            f" {len(program)} characters computing XOR:",
            "",
            "```",
            program,
            "```",
            "",
            "Feeding it the two adjacent input characters prints their XOR.",
        ]
    )


def _join(names: list[str]) -> str:
    """Return ``names`` as an English list: ``A``, ``A and B``, ``A, B and C``."""
    if len(names) < 2:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def render_raster_section() -> str:
    """Render docs/limitations.md's raster-source paragraph from the registry."""
    raster = [
        name
        for name, lang in LANGUAGES.items()
        if lang.source_kind is SourceKind.RASTER
    ]
    verb = "carries" if len(raster) == 1 else "carry"
    return "\n".join(
        [
            f"{_join(raster)} {verb} a raster source: `generate` returns an",
            "`esolangs.raster.Raster`, `run` takes it or a PNG path through the shared",
            'codec, and `describe` reports `source_kind="raster"`.',
        ]
    )


def render_collection_size_section() -> str:
    """Render docs/limitations.md's collection size from the registry."""
    return f"The collection has {len(LANGUAGES)} languages."


def render_curation_census_section() -> str:
    """Render docs/limitations.md's census counts from the curation fixture.

    The fixture records backlinks per registry language, and the route
    follows: fame at 60, else first implementation;
    ``tests/api/test_interpreter_only_admissions.py`` holds its keys to the
    registry, so the counts here are the registry's too.
    """
    census = _curation_rows()
    # A new language is scaffolded ``unassessed`` (finish flags it); counting
    # it here raised KeyError inside check-language's docs step instead.
    fame = [e["backlinks"] >= 60 for e in census.values() if "backlinks" in e]
    pending = len(census) - len(fame)
    checked = _curation_dates()["checked"]
    lines = [
        f"The {checked} census (`snapshot.json`) records each",
        f"language's backlinks and route: {fame.count(True)} clear the fame gate",
        f"and {fame.count(False)} are first implementations.",
    ]
    if pending:
        lines.append(f"{pending} more await their backlink count.")
    return "\n".join(lines)


def render_sharing_counts_section() -> str:
    """Render docs/limitations.md's sharing counts from the catalogue.

    ``test_boolean_sharing_catalogue.py`` measures every tree generator outside
    ``[sharing.exempt]``, so the remainder is that count.
    """
    sharing = _catalogue_load()["sharing"]
    tree = sum(
        lang.boolean is not None and lang.shape is Shape.TREE
        for lang in LANGUAGES.values()
    )
    local, exempt = len(sharing["local"]), len(sharing["exempt"])
    return "\n".join(
        [
            "A test (`tests/generators/test_boolean_sharing_catalogue.py`) checks"
            f" that {tree - exempt}",
            f"of {tree} tree-shaped generators build parity or a repeated-block"
            " table at most",
            f"0.90x its dense or distinct-block twin ({local} by a local helper);"
            f" {exempt} are",
            "exempt with a reason. One shrinking probe does not establish"
            " complete sharing.",
        ]
    )


def update_usage(root: pathlib.Path = ROOT) -> bool:
    """Rewrite the generated tables in docs/usage.md between their markers."""
    path = root / "docs" / "usage.md"
    text = path.read_text()
    text = splice(text, "INPUT-SHAPES", render_input_shapes_section())
    text = splice(text, "PUBLIC-API", render_api_section())
    return _write_if_changed(path, text)


def update_limitations(root: pathlib.Path = ROOT) -> bool:
    """Rewrite the generated paragraphs of docs/limitations.md."""
    path = root / "docs" / "limitations.md"
    text = path.read_text()
    for name, render in (
        ("RASTER-SOURCES", render_raster_section),
        ("COLLECTION-SIZE", render_collection_size_section),
        ("CURATION-CENSUS", render_curation_census_section),
        ("SHARING-COUNTS", render_sharing_counts_section),
    ):
        text = splice(text, name, render())
    return _write_if_changed(path, text)


def update_contributing(root: pathlib.Path = ROOT) -> None:
    """Validate the registry-derived generator location in contributor docs."""
    path = root / "docs" / "CONTRIBUTING.md"
    if render_contributor_tools_section() not in path.read_text():
        raise ValueError(f"{path} does not name the registry's generator directory")


def update_language_request(root: pathlib.Path = ROOT) -> bool:
    """Rewrite the issue template's registry language count."""
    path = root / ".github" / "ISSUE_TEMPLATE" / "language_request.yml"
    text, replacements = re.subn(
        r"(What it adds that the current )\d+( do not —)",
        rf"\g<1>{len(LANGUAGES)}\g<2>",
        path.read_text(),
    )
    if replacements != 1:
        raise ValueError(f"expected one language count in {path}, found {replacements}")
    return _write_if_changed(path, text)


def update_readme(root: pathlib.Path = ROOT) -> bool:
    """Rewrite the generated sections of README.md between their markers."""
    path = root / "README.md"
    text = path.read_text()
    for name, render in (
        ("PACKAGE-COUNT", render_package_count_section),
        ("EXAMPLES", render_examples_section),
        ("BOOLEAN-COUNT", render_boolean_count_section),
        ("XOR-EXAMPLE", render_xor_section),
    ):
        text = splice(text, name, render())
    changed = _write_if_changed(path, text)
    catalog = root / "docs" / "languages.md"
    catalog_text = splice(
        catalog.read_text(), "IMPLEMENTED", render_languages_section()
    )
    return _write_if_changed(catalog, catalog_text) or changed


def docs_main(*, output_root: pathlib.Path = ROOT) -> int:
    """Write every generated documentation section."""
    unchanged = 0

    def report(line: str, *, changed: bool) -> None:
        nonlocal unchanged
        if changed:
            print(line)
        else:
            unchanged += 1

    report(
        "updated the generated exports of esolangs.languages",
        changed=update_exports(output_root),
    )
    report(
        "updated the generated tables of docs/proofs/index.md",
        changed=update_docs(output_root),
    )
    report(
        "updated the generated sections of README.md",
        changed=update_readme(output_root),
    )
    report(
        "updated the generated tables of docs/usage.md",
        changed=update_usage(output_root),
    )
    report(
        "updated the generated paragraphs of docs/limitations.md",
        changed=update_limitations(output_root),
    )
    update_contributing(output_root)
    print("validated the registry facts in docs/CONTRIBUTING.md")
    report(
        "updated the generated facts of the language request template",
        changed=update_language_request(output_root),
    )
    if unchanged:
        print(f"{unchanged} generated artifacts already up to date")
    return 0


INIT = "src/esolangs/languages/generators.py"
START = "# BEGIN GENERATED EXPORTS: python scripts/docs/generate.py docs"
END = "# END GENERATED EXPORTS"
#: Ruff's line limit, which the generated import block must respect.
LINE_LIMIT = 88


def declared(root: pathlib.Path = ROOT) -> list[tuple[str, str]]:
    """Return canonical module and function names for declared generators."""
    found = []
    languages = root / "src/esolangs/languages"
    paths = (
        *languages.glob("*/generator.py"),
        *languages.glob("*/generator/__init__.py"),
    )
    for path in sorted(paths):
        text = path.read_text(encoding="utf-8")
        for statement in ast.parse(text).body:
            if not (
                isinstance(statement, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "LANGUAGE"
                    for target in statement.targets
                )
                and isinstance(statement.value, ast.Call)
            ):
                continue
            generator = next(
                kw.value.id
                for kw in statement.value.keywords
                if kw.arg == "boolean" and isinstance(kw.value, ast.Name)
            )
            parts = path.relative_to(root / "src").with_suffix("").parts
            module = ".".join(parts[:-1] if path.name == "__init__.py" else parts)
            found.append((module, generator))
    return sorted(found)


def render(root: pathlib.Path = ROOT) -> str:
    """Return the import block and ``__all__`` for :data:`declared`."""
    pairs = declared(root)
    lines = []
    for m, g in pairs:
        # language-owners: ["Eval"]
        for name, alias in (("LANGUAGE", f"_{g.upper()}_LANGUAGE"), (g, "")):
            comment = (
                "  # noqa: A004 - the language's name"
                if hasattr(builtins, name)
                else ""
            )
            item = f"{name} as {alias}" if alias else name
            line = f"from {m} import {item}"
            if len(line + comment) > LINE_LIMIT:
                lines.append(f"from {m} import (\n    {item},{comment}\n)")
            else:
                lines.append(line + comment)
    imports = "\n".join(lines)
    names = sorted(["BOOLEAN", *(g for _, g in pairs)])
    listed = "\n".join(f'    "{name}",' for name in names)
    declarations = "\n".join(f"    _{g.upper()}_LANGUAGE," for _, g in pairs)
    return f"{imports}\n\n_LANGUAGES = (\n{declarations}\n)\n\n__all__ = [\n{listed}\n]"


def update_exports(
    output_root: pathlib.Path = ROOT, source_root: pathlib.Path = ROOT
) -> bool:
    """Rewrite the marked language export block under ``output_root``."""
    path = output_root / INIT
    text = path.read_text(encoding="utf-8")
    block = START + "\n" + render(source_root) + "\n" + END
    head, rest = text.split(START, 1)
    return _write_if_changed(
        path, head + block + rest.split(END, 1)[1], encoding="utf-8"
    )


if __name__ == "__main__":
    raise SystemExit(main())
