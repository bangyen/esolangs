"""Generate docs/usage.md's tables and README sections from the registry.

The two docs/usage.md blocks exist because the facts in them used to be
*prose* policed by regex, in three documents at once.  A rendered table
compared for equality states the same facts without prescribing a sentence
to hold them, which is why the gates could stop matching wording.
"""

import pathlib
import re
from typing import cast

import esolangs
from esolangs.registry import LANGUAGES, RUNNERS, wiki_url
from esolangs.tools import BOOLEAN

ROOT = pathlib.Path(__file__).parents[3]


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
_TUI_START = "<!-- TUI-FRAME:START -->"
_TUI_END = "<!-- TUI-FRAME:END -->"

#: The frame the README shows.  Flowchart because the pane is worth seeing:
#: it is a grid language, so the screenshot shows the 2D program pane and a
#: tuple ``ip``, neither of which a tape language exercises.  ``replay``
#: derives the frame from nothing, so this is a coordinate, not a recording.
_TUI_LANGUAGE = "Flowchart"
_TUI_TABLE = "0110"
_TUI_BITS = [0, 1]
_TUI_STEP = 14
_TUI_HEIGHT = 20
_TUI_WIDTH = 74

_ANSI = re.compile(r"\x1b\[[0-9;]*m")

#: The bit vector the stdin table is rendered for.  Three bits, because an
#: odd count is what makes Taglate's padding visible -- at two it encodes
#: like everything else, and Fargo's decimal and binary readings coincide
#: below four.
_SAMPLE_BITS = [1, 0, 1]


def _wiki_name(name: str) -> str:
    """Return the esolangs wiki page title for the displayed language name."""
    return name


def render_package_count_section() -> str:
    """Render the total and source-shape counts in the README lead."""
    return (
        f"Interpreters and Boolean generators for {len(LANGUAGES)} esoteric "
        f"languages: {len(RUNNERS)} text and "
        f"{len(LANGUAGES) - len(RUNNERS)} raster."
    )


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


def render_languages_section() -> str:
    """Render the README's Implemented Languages section between the markers.

    Each language with an in-repo interpreter is grouped by the interpreter's
    category, sorted by display name, and linked to both its esolangs wiki
    page and the interpreter's source file on GitHub.  The ``<summary>``
    count is generated too, so it stays in sync.
    """
    out: list[str] = [
        f"<summary>Show all {len(RUNNERS)} languages</summary>",
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
            tier = (
                "" if LANGUAGES[name].boolean is not None else " *(interpreter-only)*"
            )
            out.append(
                f"- [{_wiki_name(name)}]({_wiki_link(name)})"
                f" ([code]({_source_link(name)})){tier}"
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
            "Ready-to-run programs are committed under"
            " [`examples/`]"
            "(https://github.com/bangyen/esolangs/tree/main/src/esolangs/examples):",
            f"`examples/` holds a truth-table program for each of the {len(BOOLEAN)}",
            "languages with a boolean generator.  It regenerates via",
            "`scripts/generate.py examples`.",
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
            "text languages have such a generator, some covering only a"
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
    embedded = sum(1 for name in LANGUAGES if esolangs.describe(name)["parameterized"])
    classics = sum(
        1 for name in LANGUAGES if esolangs.describe(name)["boolean_generator"] is False
    )
    rows.extend(
        [
            "",
            f"The other {len(reading) - len(odd)} that read stdin take one"
            f" `0`/`1` line per bit -- `{default}`.",
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
            "Call `encode_inputs` rather than reading a row off",
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
        lines.append(f"- `esolangs.{name}` -- {summary[0].lower()}{summary[1:]}")
    return "\n".join(lines)


def render_tui_section() -> str:
    """Render the README's TUI screen between the markers.

    A real frame, not a mock-up: ``tui.replay`` reconstructs the state
    ``_TUI_STEP`` commands into a fresh run and ``tui.render`` draws it.  So
    the block is the screen, and a layout change fails the sync test rather
    than leaving a stale picture on the front page -- which is the whole
    reason this is text and not a recording.

    Two departures from the live screen, both forced by the page.  Colour is
    dropped, so the reverse-video cell marking the op about to run does not
    survive; the header's ``ip`` names it instead, which is the same fallback
    an ``opaque`` language gets.  And every line is right-stripped, because
    ``trailing-whitespace`` runs on README.md and would otherwise strip the
    grid's padding back out from under the committed block.
    """
    from esolangs import tui

    program = esolangs.generate(_TUI_LANGUAGE, _TUI_TABLE)
    program = cast(str, program)
    stdin = esolangs.encode_inputs(_TUI_LANGUAGE, _TUI_BITS)
    frame = tui.replay(_TUI_LANGUAGE, program, stdin, _TUI_STEP)
    screen = tui.render(frame, height=_TUI_HEIGHT, width=_TUI_WIDTH)
    drawn = "\n".join(line.rstrip() for line in _ANSI.sub("", screen).splitlines())
    return "\n".join(
        [
            f"`--tui` steps it on screen instead.  This is a real frame --"
            f" {_TUI_LANGUAGE} at",
            f"step {_TUI_STEP}, redrawn by `tui.render` every time this file"
            f" is generated:",
            "",
            "```",
            drawn,
            "```",
            "",
            "The live screen reverse-videos the cell at that `ip`; colour"
            " does not survive",
            "the page."
            "  [usage](https://github.com/bangyen/esolangs/blob/main/docs/usage.md#debugging)"
            " names every key.",
        ]
    )


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


def update_contributing() -> None:
    """Validate the registry-derived generator location in contributor docs."""
    path = ROOT / "docs" / "CONTRIBUTING.md"
    if render_contributor_tools_section() not in path.read_text():
        raise ValueError(f"{path} does not name the registry's generator directory")


def update_language_request() -> None:
    """Rewrite the issue template's registry language count."""
    path = ROOT / ".github" / "ISSUE_TEMPLATE" / "language_request.yml"
    text, replacements = re.subn(
        r"(What it adds that the current )\d+( do not —)",
        rf"\g<1>{len(LANGUAGES)}\g<2>",
        path.read_text(),
    )
    if replacements != 1:
        raise ValueError(f"expected one language count in {path}, found {replacements}")
    path.write_text(text)


def update_readme() -> None:
    """Rewrite the generated sections of README.md between their markers."""
    path = ROOT / "README.md"
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
        (_TUI_START, _TUI_END, render_tui_section),
    ):
        text = _splice(text, start, end, render())
    path.write_text(text)


def main() -> int:
    """Write every generated documentation section."""
    update_readme()
    print("updated the generated sections of README.md")
    update_usage()
    print("updated the generated tables of docs/usage.md")
    update_contributing()
    print("validated the registry facts in docs/CONTRIBUTING.md")
    update_language_request()
    print("updated the generated facts of the language request template")
    return 0
