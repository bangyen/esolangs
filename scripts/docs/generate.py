"""Regenerate the committed documentation and the tools export block."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import ast
import builtins
import pathlib
import re
import shlex
import sys
import tomllib
from typing import cast

import esolangs
from esolangs.registry import LANGUAGES, SourceKind, wiki_url
from esolangs.tools import BOOLEAN


def main() -> int:
    """Dispatch one generation command."""
    parser = argparse.ArgumentParser()
    parser.add_argument("target", choices=("docs", "examples"))
    parser.add_argument("args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.target == "docs":
        if args.args:
            parser.error("docs takes no arguments")
        return docs_main()
    if args.target == "examples":
        sys.argv = [sys.argv[0], *args.args]
        from docs.examples import examples_main

        return examples_main()
    raise AssertionError(args.target)


ROOT = pathlib.Path(__file__).resolve().parents[2]
_INTERPRETERS = ROOT / "src" / "esolangs" / "interpreters"
CURATION = ROOT / "tests" / "fixtures" / "curation.toml"


# The README's Implemented Languages section, grouped by interpreter
# category.  The list order is the classification priority (a language is
# filed by its most distinctive data structure): grid (a beam/pointer moving
# on a 2D surface) > stack > queue > tape > register (the imperative
# default) > other.
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
        "other",
        "Other Languages",
        "Languages that don't fit into the above categories.",
    ),
]

_README_START = "<!-- IMPLEMENTED:START -->"
_README_END = "<!-- IMPLEMENTED:END -->"
_EXAMPLES_START = "<!-- EXAMPLES:START -->"
_EXAMPLES_END = "<!-- EXAMPLES:END -->"
_BOOLEAN_COUNT_START = "<!-- BOOLEAN-COUNT:START -->"
_BOOLEAN_COUNT_END = "<!-- BOOLEAN-COUNT:END -->"
_PACKAGE_COUNT_START = "<!-- PACKAGE-COUNT:START -->"
_PACKAGE_COUNT_END = "<!-- PACKAGE-COUNT:END -->"
_SHAPES_START = "<!-- INPUT-SHAPES:START -->"
_SHAPES_END = "<!-- INPUT-SHAPES:END -->"
_API_START = "<!-- PUBLIC-API:START -->"
_API_END = "<!-- PUBLIC-API:END -->"
_XOR_START = "<!-- XOR-EXAMPLE:START -->"
_XOR_END = "<!-- XOR-EXAMPLE:END -->"
_RASTER_START = "<!-- RASTER-SOURCES:START -->"
_RASTER_END = "<!-- RASTER-SOURCES:END -->"
_SIZE_START = "<!-- COLLECTION-SIZE:START -->"
_SIZE_END = "<!-- COLLECTION-SIZE:END -->"
_CENSUS_START = "<!-- CURATION-CENSUS:START -->"
_CENSUS_END = "<!-- CURATION-CENSUS:END -->"

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
    module = cast(str, LANGUAGES[name].interpreter)
    path = module.replace(".", "/")
    if not (_INTERPRETERS / f"{path}.py").is_file():
        path += "/__init__"
    return (
        f"https://github.com/bangyen/esolangs/blob/main/"
        f"src/esolangs/interpreters/{path}.py"
    )


def render_languages_section() -> str:
    """Render the README's Implemented Languages section between the markers.

    Each language with an in-repo interpreter is grouped by the interpreter's
    category, sorted by display name, and linked to both its esolangs wiki
    page and the interpreter's source file on GitHub.  The ``<summary>``
    count is generated too, so it stays in sync.
    """
    count = sum(lang.interpreter is not None for lang in LANGUAGES.values())
    out: list[str] = [
        f"<summary>Show all {count} languages</summary>",
        "",
    ]
    groups: dict[str, list[str]] = {prefix: [] for prefix, _, _ in _README_HEADINGS}
    for name, lang in LANGUAGES.items():
        if lang.interpreter is None:
            continue
        category = lang.interpreter.split(".")[0]
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
    the registry rather than from ``ls examples/`` -- the same rule the rest
    of this script follows.  A separate sync test already pins that every
    generator has its committed file, so the registry is the source that
    cannot drift.
    """
    count = sum(esolangs.describe(name)["boolean_generator"] for name in LANGUAGES)
    return "\n".join(
        [
            f"Ready-to-run programs for each of the {count}",
            "languages with a boolean generator live in",
            "[`examples/`]"
            "(https://github.com/bangyen/esolangs/tree/main/src/esolangs/examples).",
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
    generator_dir = root / "tools"
    for language in LANGUAGES.values():
        if language.boolean is None:
            continue
        source = pathlib.Path(language.boolean.__code__.co_filename).resolve()
        if not source.is_relative_to(generator_dir.resolve()):
            raise ValueError(f"{language.name}'s generator is outside {generator_dir}")
    return "| `src/esolangs/tools/` | generators |"


def _reads_stdin() -> list[str]:
    """Return the languages that take their inputs on stdin, sorted."""
    names = esolangs.list_languages()
    return sorted(name for name in names if esolangs.describe(name)["reads_input"])


def _is_exceptional(name: str) -> bool:
    """Return whether the stdin is anything but adjacent ``0``/``1`` characters."""
    record = esolangs.describe(name)
    shape = record["input_shape"]
    alphabet = tuple(record["input_encoding"])
    return shape != "char_stream" or alphabet != ("0", "1")


def render_input_shapes_section() -> str:
    """Render docs/usage.md's stdin table between the markers.

    Every cell is ``repr(encode_inputs(language, [1, 0, 1]))``, so the table
    is the encoder's own output rather than a description of it.  This
    replaced three hand-written prose copies of the same four exceptions;
    one of them called Fargo's row index a bits-on-one-line input, returned
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
        alphabet = "/".join(f"`{c}`" for c in record["input_encoding"])
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
    import inspect
    import re

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

    The fixture records one route per registry language;
    ``tests/test_interpreter_only_admissions.py`` holds its keys to the
    registry, so the counts here are the registry's too.
    """
    census = tomllib.loads(CURATION.read_text(encoding="utf-8"))
    routes = [entry["route"] for entry in census["languages"].values()]
    return "\n".join(
        [
            f"The {census['checked']} census (`tests/fixtures/curation.toml`)"
            " records each",
            f"language's backlinks and route: {routes.count('fame')} clear the"
            " fame gate,",
            f"{routes.count('first implementation')} are first implementations"
            f" and {routes.count('grandfathered')} are grandfathered.",
        ]
    )


def _splice(text: str, start: str, end: str, body: str) -> str:
    """Replace the marked block in ``text``, keeping the markers themselves."""
    block = start + "\n\n" + body + "\n\n" + end
    return text[: text.index(start)] + block + text[text.index(end) + len(end) :]


def update_usage(root: pathlib.Path = ROOT) -> None:
    """Rewrite the generated tables in docs/usage.md between their markers."""
    path = root / "docs" / "usage.md"
    text = path.read_text()
    text = _splice(text, _SHAPES_START, _SHAPES_END, render_input_shapes_section())
    text = _splice(text, _API_START, _API_END, render_api_section())
    path.write_text(text)


def update_limitations(root: pathlib.Path = ROOT) -> None:
    """Rewrite the generated paragraphs of docs/limitations.md."""
    path = root / "docs" / "limitations.md"
    text = path.read_text()
    for start, end, render in (
        (_RASTER_START, _RASTER_END, render_raster_section),
        (_SIZE_START, _SIZE_END, render_collection_size_section),
        (_CENSUS_START, _CENSUS_END, render_curation_census_section),
    ):
        text = _splice(text, start, end, render())
    path.write_text(text)


def update_contributing(root: pathlib.Path = ROOT) -> None:
    """Validate the registry-derived generator location in contributor docs."""
    path = root / "docs" / "CONTRIBUTING.md"
    if render_contributor_tools_section() not in path.read_text():
        raise ValueError(f"{path} does not name the registry's generator directory")


def update_language_request(root: pathlib.Path = ROOT) -> None:
    """Rewrite the issue template's registry language count."""
    path = root / ".github" / "ISSUE_TEMPLATE" / "language_request.yml"
    text, replacements = re.subn(
        r"(What it adds that the current )\d+( do not —)",
        rf"\g<1>{len(LANGUAGES)}\g<2>",
        path.read_text(),
    )
    if replacements != 1:
        raise ValueError(f"expected one language count in {path}, found {replacements}")
    path.write_text(text)


def update_readme(root: pathlib.Path = ROOT) -> None:
    """Rewrite the generated sections of README.md between their markers."""
    path = root / "README.md"
    text = path.read_text()
    for start, end, render in (
        (
            _PACKAGE_COUNT_START,
            _PACKAGE_COUNT_END,
            render_package_count_section,
        ),
        (_README_START, _README_END, render_languages_section),
        (_EXAMPLES_START, _EXAMPLES_END, render_examples_section),
        (_BOOLEAN_COUNT_START, _BOOLEAN_COUNT_END, render_boolean_count_section),
        (_XOR_START, _XOR_END, render_xor_section),
    ):
        text = _splice(text, start, end, render())
    path.write_text(text)


def docs_main(*, output_root: pathlib.Path = ROOT) -> int:
    """Write every generated documentation section."""
    # Imported here so the module also loads from a test, where this directory
    # is not on ``sys.path`` until now.
    from docs.proof_status import update_docs

    update_exports(output_root)
    print("updated the generated exports of esolangs.tools")
    update_docs(output_root)
    update_readme(output_root)
    print("updated the generated sections of README.md")
    update_usage(output_root)
    print("updated the generated tables of docs/usage.md")
    update_limitations(output_root)
    print("updated the generated paragraphs of docs/limitations.md")
    update_contributing(output_root)
    print("validated the registry facts in docs/CONTRIBUTING.md")
    update_language_request(output_root)
    print("updated the generated facts of the language request template")
    return 0


INIT = "src/esolangs/tools/__init__.py"
START = "# BEGIN GENERATED EXPORTS: python scripts/docs/generate.py docs"
END = "# END GENERATED EXPORTS"


def declared(root: pathlib.Path = ROOT) -> list[tuple[str, str]]:
    """Return ``(module, generator)`` for every module declaring a ``LANGUAGE``."""
    tools = root / "src/esolangs/tools"
    found = []
    for path in [*tools.glob("*.py"), *tools.glob("*/__init__.py")]:
        text = path.read_text(encoding="utf-8")
        start = text.find("\nLANGUAGE = Language(")
        if start < 0:
            continue
        statement = ast.parse(text[start:]).body[0]
        assert isinstance(statement, ast.Assign)
        assert isinstance(statement.value, ast.Call)
        generator = next(
            kw.value.id
            for kw in statement.value.keywords
            if kw.arg == "boolean" and isinstance(kw.value, ast.Name)
        )
        module = path.parent.name if path.name == "__init__.py" else path.stem
        found.append((module, generator))
    return sorted(found)


def render(root: pathlib.Path = ROOT) -> str:
    """Return the import block and ``__all__`` for :data:`declared`."""
    pairs = declared(root)
    imports = "\n".join(
        f"from esolangs.tools.{m} import {g}"
        # A generator named for its language may shadow a builtin (Eval).
        + ("  # noqa: A004 - the language's name" if hasattr(builtins, g) else "")
        for m, g in pairs
    )
    names = sorted(["BOOLEAN", *(g for _, g in pairs)])
    listed = "\n".join(f'    "{name}",' for name in names)
    return f"{imports}\n\n__all__ = [\n{listed}\n]"


def update_exports(
    output_root: pathlib.Path = ROOT, source_root: pathlib.Path = ROOT
) -> None:
    """Rewrite the marked block of ``tools/__init__.py`` under ``output_root``."""
    path = output_root / INIT
    text = path.read_text(encoding="utf-8")
    block = START + "\n" + render(source_root) + "\n" + END
    head, rest = text.split(START, 1)
    path.write_text(head + block + rest.split(END, 1)[1], encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
