"""Generate docs/languages.md and the README's Implemented Languages list.

Walks the registry and the compiler/example directories to produce the
language capability matrix (docs/languages.md) and the grouped, wiki-linked
language list in the README, so neither page goes stale the way a
hand-maintained list would.
"""

import pathlib

from esolangs.registry import LANGUAGES, RUNNERS

ROOT = pathlib.Path(__file__).parents[1]
EXAMPLES = ROOT / "examples"
HELLO = EXAMPLES / "hello-world"
CAT = EXAMPLES / "cat"
TRUTH = EXAMPLES / "truth-machine"

# Languages with a boolean generator in esolangs.tools.booleans, mapped to
# display names.  Back, BIO, and NoComment's generators are parameterized
# templates (the harness substitutes the input bits) rather than input-reading
# programs.
BOOLEAN = {
    "3x",
    "6-5",
    "ASCII art",
    "Back",
    "Basicfuck",
    "Between",
    "BF",
    "BFStack",
    "BIO",
    "BrainIf",
    "CircleFuck",
    "Clockwise",
    "Container",
    "Dig",
    "Dimensional",
    "Forþ",
    "LaserFuck",
    "Modulous",
    "Nevermind",
    "NoComment",
    "Polynomial",
    "Qoibl",
    "S*bleq",
    "Sophie",
    "Taglate",
    "Unsquare",
}
# Compiler source-file stem -> the language's display name.  A compiler file
# without an entry here fails loudly rather than silently dropping out of
# the docs.
_COMPILER_NAMES = {
    "bfstack": "BFStack",
    "home-row": "Home Row",
    "jaune": "Jaune",
    "suffolk": "Suffolk",
    "unsquare": "Unsquare",
    "bf-pda": "BF-PDA",
    "excon": "EXCON",
    "RAM0": "RAM0",
}

_COMPILER_DIRS = {
    "assembly": (ROOT / "src" / "esolangs" / "compilers" / "assembly", "*.py"),
    "c": (ROOT / "src" / "esolangs" / "compilers" / "c", "*.c"),
}


def _compiler_set(kind: str) -> set[str]:
    """Return the display names of the compilers in the given directory."""
    directory, pattern = _COMPILER_DIRS[kind]
    return {
        _COMPILER_NAMES[path.stem]
        for path in directory.glob(pattern)
        if path.stem != "__init__"
    }


ASSEMBLY_COMPILERS = _compiler_set("assembly")
C_COMPILERS = _compiler_set("c")

# The README's Extra Implementations section: each entry is the extra/
# subdirectory, its source pattern, the file-stem -> display-name map (an
# unknown file fails loudly), and the heading.  The RISC-V 123 port is
# excluded by matching only ``*.asm``.
_EXTRA_DIRS = [
    (
        ROOT / "extra" / "c++",
        "*.cpp",
        {
            "%^2^-1": "%^2^-1",
            "2dFish": "2dFish",
            "basicfuck": "Basicfuck",
            "forþ": "Forþ",
            "kak": "Kak",
            "painfuck": "Painfuck",
            "trash": "Trash",
        },
        "C++ Implementations",
    ),
    (
        ROOT / "extra" / "assembly",
        "*.asm",
        {
            "123": "123",
            "2b1b": "2 Bits, 1 Byte",
            "brainpocalypse": "Brainpocalypse",
            "nocomment": "NoComment",
            "stun-step": "Stun Step",
        },
        "x86 Assembly Implementations",
    ),
    (
        ROOT / "extra" / "lean" / "esolangs",
        "*Main.lean",
        {
            "AlbabetMain": "Albabet",
            "BfpdaMain": "BF-PDA",
            "ExconMain": "EXCON",
            "SeventyFourMain": "Number Seventy-Four",
        },
        "Lean Implementations",
    ),
    (
        ROOT / "extra" / "r",
        "*.r",
        {"excon": "EXCON"},
        "R Implementations",
    ),
    (
        ROOT / "extra" / "ruby",
        "*.rb",
        {
            "3x": "3x",
            "74": "Number Seventy-Four",
            "bit": "bit~",
            "unsquare": "Unsquare",
        },
        "Ruby Implementations",
    ),
    (
        ROOT / "extra" / "rust",
        "*.rs",
        {"laserfuck": "LaserFuck", "unsquare": "Unsquare"},
        "Rust Implementations",
    ),
]

# Display names of the languages with a native implementation in extra/
# (C++, Rust, Ruby, R, Lean, or x86 assembly).  These interpreters run as
# standalone programs rather than through the Python package.
NATIVE = {name for _, _, names, _ in _EXTRA_DIRS for name in names.values()}

# Extra-implementation display name -> wiki slug, where the page name
# differs from ``name.replace(" ", "_")`` (URL-encoded characters kept
# literal as in the pre-existing hand-written list).
_EXTRA_WIKI = {
    "Forþ": "For%C3%BE",
    "%^2^-1": "%25%5E2%5E-1",
    "bit~": "Bit~",
    "Number Seventy-Four": "Number_Seventy-Four",
    "Stun Step": "Stun_Step",
}

# The README's Implemented Languages section, grouped by interpreter
# category in this order, with its one-line descriptions.
_README_HEADINGS = [
    (
        "register_based",
        "Register-based Languages",
        "Languages that use registers to store and manipulate data.",
    ),
    (
        "tape_based",
        "Tape-based Languages",
        "Languages that operate on a tape (similar to Turing machines).",
    ),
    (
        "stack_based",
        "Stack-based Languages",
        "Languages that use a stack for data manipulation.",
    ),
    (
        "other",
        "Other Languages",
        "Languages that don't fit into the above categories.",
    ),
]

# Registry display name -> esolangs wiki page title, where the wiki names
# the page differently from the registry's shorthand.
_WIKI_PAGES = {
    "BF": "brainfuck",
    "BitDeque": "Bitdeque",
    "CircleFuck": "Circlefuck",
    "MAMMALIAN": "SLOW ACV MAMMALIAN",
    "Temporary": "The Temporary Stack",
    "ZTOALC": "ZTOALC L",
}

_README_START = "<!-- IMPLEMENTED:START -->"
_README_END = "<!-- IMPLEMENTED:END -->"
_COMPILERS_START = "<!-- COMPILERS:START -->"
_COMPILERS_END = "<!-- COMPILERS:END -->"
_EXTRA_START = "<!-- EXTRA:START -->"
_EXTRA_END = "<!-- EXTRA:END -->"


def _wiki_name(name: str) -> str:
    """Return the esolangs wiki page title for the displayed language name."""
    return _WIKI_PAGES.get(name, name)


def _wiki_slug(name: str) -> str:
    return _wiki_name(name).replace(" ", "_")


def _file_name(name: str) -> str:
    return name.lower().replace(" ", "-")


def _capabilities(name: str) -> dict[str, bool]:
    lang = LANGUAGES.get(name)
    hello = (HELLO / f"{_file_name(name)}.txt").exists()
    return {
        "generator": lang.generator is not None if lang else False,
        "interpreter": lang.interpreter is not None if lang else False,
        "native": name in NATIVE,
        "boolean": name in BOOLEAN,
        "compiler": name in ASSEMBLY_COMPILERS or name in C_COMPILERS,
        "hello": hello,
        "cat": (CAT / f"{_file_name(name)}.txt").exists(),
        "truth-machine": (TRUTH / f"{_file_name(name)}.txt").exists(),
    }


def render() -> str:
    """Render the languages documentation table as Markdown."""
    lines = [
        "# Language capabilities",
        "",
        "What the repository implements for each language. Generated from",
        "`esolangs/registry.py` by `scripts/make_languages_doc.py`; do not edit by",
        "hand.",
        "",
        "Python means an in-repo interpreter under `esolangs.interpreters`;",
        "Native means an implementation in `extra/` that runs as a standalone",
        "program (C++, Rust, Ruby, R, Lean, or x86 assembly).  The Boolean",
        "column marks the boolean-function generators; Back, BIO, and",
        "NoComment's are parameterized (the harness substitutes input bits",
        "into a template) rather than the program reading input.",
        "",
        "| Language | Text generator | Python | Native | Boolean | Compiler | Examples |",  # noqa: E501
        "| --- | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for name in sorted(set(LANGUAGES) | C_COMPILERS | NATIVE):
        c = _capabilities(name)
        examples = " ".join(k for k in ("hello", "cat", "truth-machine") if c[k])
        lines.append(
            f"| {name} | {'yes' if c['generator'] else ''} | "
            f"{'yes' if c['interpreter'] else ''} | "
            f"{'yes' if c['native'] else ''} | "
            f"{'yes' if c['boolean'] else ''} | "
            f"{'yes' if c['compiler'] else ''} | {examples} |"
        )
    lines += ["", "The `esolangs` command lists the languages with Python support:"]
    lines += ["", "```bash", "esolangs list", "```", ""]
    return "\n".join(lines)


def render_languages_section() -> str:
    """Render the README's Implemented Languages section between the markers.

    Each language with an in-repo interpreter is grouped by the interpreter's
    category, sorted by display name, and linked to its esolangs wiki page.
    """
    groups: dict[str, list[str]] = {prefix: [] for prefix, _, _ in _README_HEADINGS}
    for name, (module, _, _) in RUNNERS.items():
        groups[module.split(".")[0]].append(name)

    out: list[str] = []
    for prefix, heading, description in _README_HEADINGS:
        out.append(f"### {heading}")
        out.append("")
        out.append(description)
        out.append("")
        for name in sorted(groups[prefix]):
            out.append(
                f"- [{_wiki_name(name)}](https://esolangs.org/wiki/{_wiki_slug(name)})"
            )
        out.append("")
    return "\n".join(out).rstrip()


def render_compilers_section() -> str:
    """Render the README's Compilers section between the markers."""
    out: list[str] = []
    for kind, heading in (("assembly", "x86 Assembly Compilers"), ("c", "C Compilers")):
        out.append(f"### {heading}")
        out.append("")
        for name in sorted(_compiler_set(kind)):
            out.append(
                f"- [{name}](https://esolangs.org/wiki/{name.replace(' ', '_')})"
            )
        out.append("")
    return "\n".join(out).rstrip()


def render_extra_section() -> str:
    """Render the README's Extra Implementations lists between the markers."""
    out: list[str] = []
    for directory, pattern, names, heading in _EXTRA_DIRS:
        out.append(f"### {heading}")
        out.append("")
        for name in sorted(
            {names[path.stem] for path in directory.glob(pattern)}, key=str.lower
        ):
            slug = _EXTRA_WIKI.get(name, name.replace(" ", "_"))
            out.append(f"- [{name}](https://esolangs.org/wiki/{slug})")
        out.append("")
    return "\n".join(out).rstrip()


def update_readme() -> None:
    """Rewrite the generated sections of README.md between their markers."""
    path = ROOT / "README.md"
    text = path.read_text()
    for start, end, render in (
        (_README_START, _README_END, render_languages_section),
        (_COMPILERS_START, _COMPILERS_END, render_compilers_section),
        (_EXTRA_START, _EXTRA_END, render_extra_section),
    ):
        block = start + "\n\n" + render() + "\n\n" + end
        text = text[: text.index(start)] + block + text[text.index(end) + len(end) :]
    path.write_text(text)


if __name__ == "__main__":
    out = ROOT / "docs" / "languages.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(render())
    print(f"wrote {out} ({len(set(LANGUAGES) | C_COMPILERS | NATIVE)} languages)")
    update_readme()
    print("updated the generated sections of README.md")
