"""Generate docs/languages.md: the language capability matrix.

Walks the registry and the compiler/example directories to produce a
markdown table of what this repository implements for each language, so the
page never goes stale the way a hand-maintained list would.
"""

import pathlib

from esolangs.registry import LANGUAGES

ROOT = pathlib.Path(__file__).parents[1]
EXAMPLES = ROOT / "examples"
HELLO = EXAMPLES / "hello-world"
CAT = EXAMPLES / "cat"
TRUTH = EXAMPLES / "truth-machine"

# Languages with a boolean generator in esolangs.tools.booleans, mapped to
# display names.
BOOLEAN = {
    "3x",
    "6-5",
    "ASCII art",
    "Basicfuck",
    "BF",
    "BFStack",
    "BrainIf",
    "CircleFuck",
    "Clockwise",
    "Container",
    "Dig",
    "Dimensional",
    "Forþ",
    "Modulous",
    "Nevermind",
    "Polynomial",
    "Qoibl",
    "Sophie",
    "Taglate",
}
ASSEMBLY_COMPILERS = {"BFStack", "Home Row", "Jaune", "Suffolk", "Unsquare"}
C_COMPILERS = {"BF-PDA", "BFStack", "EXCON", "RAM0"}


def _file_name(name: str) -> str:
    return name.lower().replace(" ", "-")


def _capabilities(name: str) -> dict[str, bool]:
    lang = LANGUAGES.get(name)
    hello = (HELLO / f"{_file_name(name)}.txt").exists()
    return {
        "generator": lang.generator is not None if lang else False,
        "interpreter": lang.interpreter is not None if lang else False,
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
        "| Language | Text generator | Interpreter | Boolean | Compiler | Examples |",
        "| --- | :---: | :---: | :---: | :---: | :---: |",
    ]
    for name in sorted(set(LANGUAGES) | C_COMPILERS):
        c = _capabilities(name)
        examples = " ".join(k for k in ("hello", "cat", "truth-machine") if c[k])
        lines.append(
            f"| {name} | {'yes' if c['generator'] else ''} | "
            f"{'yes' if c['interpreter'] else ''} | {'yes' if c['boolean'] else ''} | "
            f"{'yes' if c['compiler'] else ''} | {examples} |"
        )
    lines += ["", "The `esolangs` command lists the same languages:"]
    lines += ["", "```bash", "esolangs list", "```", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    out = ROOT / "docs" / "languages.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(render())
    print(f"wrote {out} ({len(set(LANGUAGES) | C_COMPILERS)} languages)")
