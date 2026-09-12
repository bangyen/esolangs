"""Generate docs/languages.md, docs/usage.md's tables, and README sections.

Walks the registry to produce the language capability matrix
(docs/languages.md) and the grouped, wiki-linked language list in the
README, so neither page goes stale the way a hand-maintained list would.
Every column derives from the registry or a capability set -- never from
which files happen to sit in examples/.

The two docs/usage.md blocks exist because the facts in them used to be
*prose* policed by regex, in three documents at once.  A rendered table
compared for equality states the same facts without prescribing a sentence
to hold them, which is why the gates could stop matching wording.
"""

import pathlib
import textwrap

import esolangs
from esolangs.registry import LANGUAGES, RUNNERS, parameterized_ids, wiki_url
from esolangs.tools.boolean import BOOLEAN

ROOT = pathlib.Path(__file__).parents[1]
# Extra source files that are support modules, not implementations: they are
# globbed alongside the languages but have no display name (an unknown
# implementation file still fails loudly).
_EXTRA_SUPPORT_MODULES = {"common"}

# Extra-implementation display name -> wiki slug, where the page name
# differs from ``name.replace(" ", "_")`` (URL-encoded characters kept
# literal as in the pre-existing hand-written list).
_EXTRA_WIKI = {
    "Forþ": "For%C3%BE",
    "%^2^-1": "%25%5E2%5E-1",
    "bit~": "Bit~",
}

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
_SHAPES_START = "<!-- INPUT-SHAPES:START -->"
_SHAPES_END = "<!-- INPUT-SHAPES:END -->"
_API_START = "<!-- PUBLIC-API:START -->"
_API_END = "<!-- PUBLIC-API:END -->"

#: The bit vector the stdin table is rendered for.  Three bits, because an
#: odd count is what makes Taglate's padding visible -- at two it encodes
#: like everything else, and Fargo's decimal and binary readings coincide
#: below four.
_SAMPLE_BITS = [1, 0, 1]


def _wiki_name(name: str) -> str:
    """Return the esolangs wiki page title for the displayed language name."""
    return name


def _wiki_link(name: str) -> str:
    """Return the language's wiki URL, built by the registry so the two agree.

    This used to build its own slug, which meant the README and
    ``describe`` each had a copy of the same escaping bug.
    """
    return wiki_url(_wiki_name(name))


def _source_link(name: str) -> str:
    """Return the GitHub URL of the language's Python interpreter."""
    module = RUNNERS[name][0]
    path = module.replace(".", "/")
    return (
        f"https://github.com/bangyen/esolangs/blob/main/"
        f"src/esolangs/interpreters/{path}.py"
    )


def _template_list() -> str:
    """Return the parameterized languages as one wrapped Markdown line.

    Derived from the registry rather than written out.  The hand-kept
    version named fifteen languages and three different subsets appeared in
    three documents; the two it left out (123 and Home Row) emit a `{Xi}`
    slot like the rest.
    """
    ids = parameterized_ids()
    names = sorted(name for name, lang in LANGUAGES.items() if lang.id in ids)
    return textwrap.fill(", ".join(names) + ".", width=72)


def _capabilities(name: str) -> dict[str, bool]:
    lang = LANGUAGES.get(name)
    return {
        "interpreter": lang.interpreter is not None if lang else False,
        "boolean": name in BOOLEAN,
        "template": lang is not None and lang.id in parameterized_ids(),
    }


def render() -> str:
    """Render the languages documentation table as Markdown."""
    lines = [
        "# Language capabilities",
        "",
        "Generated from `src/esolangs/registry.py` by",
        "`scripts/make_languages_doc.py`; do not edit by hand.",
        "",
        "## Columns",
        "",
        "**Python** means an in-repo interpreter under `esolangs.interpreters`.",
        "**Boolean** marks the boolean-function generators.",
        "**Template** marks the parameterized ones -- see below.",
        "",
        "## Parameterized generators",
        "",
        "A parameterized generator embeds the input bits in a template with",
        "one `{Xi}` slot per input, rather than returning a program that",
        "reads them. `esolangs.generate` returns that template; fill it with",
        "`esolangs.instantiate(language, template, bits)`, which is what the",
        "committed `examples/` programs are built by, or from the command",
        "line with `esolangs generate --bits 10 <language> <table>`. Running",
        "one unfilled raises `TemplateError`; filling the slots by hand does",
        "not work, since each language spells a set-input its own way.",
        "",
        f"The {len(parameterized_ids())} of them are marked **Template** in the",
        "matrix below:",
        "",
        _template_list(),
        "",
        "Most have no input command at all. The exceptions are COD, Minifuck,",
        "123, Home Row and %^2^-1, where an embedded input is the supported",
        "Boolean-generator route: %^2^-1 cannot compute a two-input function",
        "from runtime input, and COD's edge input would require horizontal",
        "routing.",
        "",
        "## How %^2^-1 reaches its tables",
        "",
        "The generator combines subcube, affine, threshold, band, and fold",
        "constructions. It is exhaustive through four inputs; the fold reaches",
        "sampled generic tables through eleven inputs, and the interleaved",
        "fold reaches generic twelve- and thirteen-input tables.",
        "",
        "## The matrix",
        "",
        "| Language | Python | Boolean | Template |",
        "| --- | :---: | :---: | :---: |",
    ]
    for name in sorted(LANGUAGES):
        c = _capabilities(name)
        lines.append(
            f"| {name} | {'yes' if c['interpreter'] else ''} | "
            f"{'yes' if c['boolean'] else ''} | "
            f"{'yes' if c['template'] else ''} |"
        )
    lines += ["", "The `esolangs` command lists the languages with Python support:"]
    lines += ["", "```bash", "esolangs list", "```", ""]
    return "\n".join(lines)


def render_languages_section() -> str:
    """Render the README's Implemented Languages section between the markers.

    Each language with an in-repo interpreter is grouped by the interpreter's
    category, sorted by display name, and linked to both its esolangs wiki
    page and the interpreter's source file on GitHub.  The ``<summary>``
    count and the pointer to the capability matrix are generated too, so they
    stay in sync.
    """
    out: list[str] = [
        f"<summary>Show all {len(RUNNERS)} languages</summary>",
        "",
        "The full capability matrix (generators, boolean support, examples)"
        " is in [`docs/languages.md`](docs/languages.md).",
        "",
    ]
    groups: dict[str, list[str]] = {prefix: [] for prefix, _, _ in _README_HEADINGS}
    for name, (module, _) in RUNNERS.items():
        groups[module.split(".")[0]].append(name)

    for prefix, heading, description in _README_HEADINGS:
        out.append(f"### {heading}")
        out.append("")
        out.append(description)
        out.append("")
        for name in sorted(groups[prefix]):
            out.append(
                f"- [{_wiki_name(name)}]({_wiki_link(name)})"
                f" ([code]({_source_link(name)}))"
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
    return "\n".join(
        [
            "Ready-to-run programs are committed under [`examples/`](examples/):",
            f"`examples/boolean/` holds a truth-table program for each of the"
            f" {len(BOOLEAN)}",
            "languages with a boolean generator.  It regenerates via",
            "`scripts/write_examples.py`.",
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
            "languages have such a generator, some covering only a documented"
            " subset of",
            "tables.",
        ]
    )


def _reads_stdin() -> list[str]:
    """Return the languages that take their inputs on stdin, sorted."""
    names = esolangs.list_languages()
    return sorted(name for name in names if esolangs.describe(name)["reads_input"])


def _is_exceptional(name: str) -> bool:
    """Return whether the stdin is anything but one ``0``/``1`` line per bit."""
    record = esolangs.describe(name)
    shape = record["input_shape"]
    alphabet = tuple(record["input_encoding"])
    return shape != "line_per_bit" or alphabet != ("0", "1")


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
    rows.extend(
        [
            "",
            f"The other {len(reading) - len(odd)} that read stdin take one"
            f" `0`/`1` line per bit -- `{default}`.",
            f"The remaining {len(LANGUAGES) - len(reading)} read no stdin at all:"
            " their inputs are",
            "embedded by `instantiate`.  Call `encode_inputs` rather than"
            " reading a row off",
            "this table; it is generated from `describe`, and so is the table.",
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
        lines.append(f"- `esolangs.{name}` — {summary[0].lower()}{summary[1:]}")
    return "\n".join(lines)


def _splice(text: str, start: str, end: str, body: str) -> str:
    """Replace the marked block in ``text``, keeping the markers themselves."""
    block = start + "\n\n" + body + "\n\n" + end
    return text[: text.index(start)] + block + text[text.index(end) + len(end) :]


def update_usage() -> None:
    """Rewrite the generated tables in docs/usage.md between their markers."""
    path = ROOT / "docs" / "usage.md"
    text = path.read_text()
    text = _splice(text, _SHAPES_START, _SHAPES_END, render_input_shapes_section())
    text = _splice(text, _API_START, _API_END, render_api_section())
    path.write_text(text)


def update_readme() -> None:
    """Rewrite the generated sections of README.md between their markers."""
    path = ROOT / "README.md"
    text = path.read_text()
    for start, end, render in (
        (_README_START, _README_END, render_languages_section),
        (_EXAMPLES_START, _EXAMPLES_END, render_examples_section),
        (_BOOLEAN_COUNT_START, _BOOLEAN_COUNT_END, render_boolean_count_section),
    ):
        text = _splice(text, start, end, render())
    path.write_text(text)


if __name__ == "__main__":
    out = ROOT / "docs" / "languages.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(render())
    count = len(LANGUAGES)
    print(f"wrote {out} ({count} languages)")
    update_readme()
    print("updated the generated sections of README.md")
    update_usage()
    print("updated the generated tables of docs/usage.md")
