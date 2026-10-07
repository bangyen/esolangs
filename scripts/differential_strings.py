"""Unlambda, Underload, Thue and ///: generators and reference patches.

The plug-ins ``differential.py`` registers for these four; see its docstring
for the references and how they are built.
"""

from __future__ import annotations

import random
import re
from collections import Counter

import esolangs

#: Unlambda terms that read, test, print, delay, capture and exit.
_UNL_IDIOMS = (
    "``@i``|ii",
    "`@i",
    "``|ii",
    "`.ai",
    "`ri",
    "``?a.yi",
    "``?\n.ni",
    "`d`.xi",
    "``d`.xii",
    "``cii",
    "``ci`.ci",
    "`c``s`k.ci",
    "`e.e",
    "``e.ei",
    "``k.k`.qi",
    "```s.s.ti",
    "`v`.vi",
)
_UNL_ATOMS = ("i", "k", "s", "v", "d", "c", "e", "r", "@", "|", ".a", ".b", "?a")


def unl_term(rng: random.Random, depth: int = 0) -> str:
    """Return one Unlambda term, now and then with whitespace or a comment."""
    roll = rng.random()
    if depth > 4 or roll < 0.3:
        term = rng.choice((*_UNL_ATOMS, f".{rng.choice('x* \n`#.')}"))
    elif roll < 0.5:
        term = rng.choice(_UNL_IDIOMS)
    else:
        term = "`" + unl_term(rng, depth + 1) + unl_term(rng, depth + 1)
    if rng.random() < 0.05:
        term = rng.choice((" ", "\n", "\t", "# note\n")) + term
    return term


def unl_runnable(program: str) -> bool:
    """Whether ``esolangs`` takes ``program`` as source: ``.x`` is a path."""
    return not esolangs._looks_like_a_path(program)  # noqa: SLF001


def unl_program(rng: random.Random) -> str:
    """Return a term; rarely a malformed source (trailing term, cut short)."""
    program = unl_term(rng)
    while not unl_runnable(program):
        program = unl_term(rng)
    if rng.random() < 0.03:
        program = rng.choice(
            (program + "i", program[:-1], program + ".", "`" + program, "")
        )
    if rng.random() < 0.02:
        program += rng.choice(("  \n", "# end", "\n# end\n"))
    return program


#: Underload commands: how many entries each needs, and the depth change.
_UL_OPS = {"~": (2, 0), ":": (1, 1), "!": (1, -1), "*": (2, -1), "a": (1, 0)}
_UL_OPS |= {"S": (1, -1), "a^": (1, 0), ":*": (1, 0), "~^": (2, -1)}


def underload_block(rng: random.Random, depth: int, nest: int = 0) -> tuple[str, int]:
    """Return commands for a stack ``depth`` deep, and the depth after.

    Tracking the depth keeps underflow an edge case; a quoted block is either
    text or code run in place by ``^`` (``(...)^``, ``(...):^``) at a known
    depth, so code built at run time is exercised too.
    """
    parts: list[str] = []
    for _ in range(rng.randint(1, 7 - 2 * nest)):
        roll = rng.random()
        if roll < 0.2 and nest < 3:
            dup = rng.random() < 0.4
            body, after = underload_block(rng, depth + dup, nest + 1)
            parts.append(f"({body})" + (":^" if dup else "^"))
            depth = after
        elif roll < 0.98:
            fits = [op for op, (need, _) in _UL_OPS.items() if need <= depth]
            if roll < 0.4 or (not fits and rng.random() < 0.95):
                text = rng.choice(("", "x", "a b", "\n", "()", "(S)", "S", ":a"))
                parts.append(f"({text})")
                depth += 1
                continue
            op = rng.choice(fits) if fits and rng.random() < 0.98 else "S"
            parts.append(op)
            depth = max(0, depth + _UL_OPS[op][1])
        else:
            parts.append(rng.choice((" ", "\n", "\t", "x")))
    return "".join(parts), depth


def underload_program(rng: random.Random) -> str:
    """Return a program, rarely with an unmatched parenthesis or a loop."""
    program = underload_block(rng, 0)[0]
    if rng.random() < 0.03:
        at = rng.randrange(len(program) + 1)
        program = program[:at] + rng.choice("()") + program[at:]
    if rng.random() < 0.01:
        program += "(:^):^"
    return program


def thue_outcomes(program: str, stdin: str, budget: int = 400) -> set[object] | None:
    """Return the outcomes every draw order reaches, or ``None`` past budget.

    An exhaustive search over (state, input lines used, output); a source
    that does not parse is one outcome (it errors whatever the order), and a
    cycle is an outcome of its own (some order never ends).
    """
    from esolangs.interpreters.other.thue import _parse

    try:
        rules, start = _parse(program)
    except ValueError:
        return {"invalid"}
    lines = stdin.split("\n")
    if lines[-1] == "":
        lines.pop()
    seen: dict[tuple[str, int, str], list[tuple[str, int, str]]] = {}
    stack = [(start, 0, "")]
    outcomes: set[object] = set()
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen[node] = edges = []
        if len(seen) > budget:
            return None
        state, used, out = node
        moves = [
            (lhs, rhs, found.start())
            for lhs, rhs in rules
            for found in re.finditer(f"(?={re.escape(lhs)})", state)
        ]
        if not moves:
            outcomes.add(("halt", out))
        for lhs, rhs, at in moves:
            text, emitted, take = rhs, "", 0
            if rhs == ":::":
                if used >= len(lines):
                    outcomes.add(("eof", out))
                    continue
                text, take = lines[used], 1
            elif rhs.startswith("~"):
                text, emitted = "", rhs[1:] or "\n"
            rewritten = state[:at] + text + state[at + len(lhs) :]
            edges.append((rewritten, used + take, out + emitted))
            stack.append(edges[-1])
    # Kahn's algorithm: whatever cannot be peeled off lies on a cycle.
    into = Counter(after for edges in seen.values() for after in edges)
    ready = [node for node in seen if not into[node]]
    while ready:
        for after in seen[ready.pop()]:
            into[after] -= 1
            if not into[after]:
                ready.append(after)
    return outcomes | ({"cycle"} if +into else set())


#: The inputs a Thue program is judged order-free on, and then fed.
THUE_INPUTS = ("", "a\n", "ab\nc\n_\n", "_b")


def thue_confluent(program: str) -> bool:
    """Whether no rewrite order changes the result on any of the inputs."""
    inputs = THUE_INPUTS if ":::" in program else ("",)
    for stdin in inputs:
        found = thue_outcomes(program, stdin)
        if found is None or len(found) != 1 or "cycle" in found:
            return False
    return True


_THUE_SYMBOLS = "abc_"


def _thue_word(rng: random.Random, low: int, high: int) -> str:
    return "".join(rng.choice(_THUE_SYMBOLS) for _ in range(rng.randint(low, high)))


def thue_raw(rng: random.Random) -> str:
    """Return rules over a small alphabet and a state built from them.

    Right sides often hold another rule's left side, so rules chain; edge
    shapes (blank lines, a whitespace left side, a junk line) turn up rarely.
    """
    lefts = [_thue_word(rng, 1, 3) for _ in range(rng.randint(1, 4))]
    rules = []
    for lhs in lefts:
        roll = rng.random()
        rhs = (
            "~" + _thue_word(rng, 0, 3)
            if roll < 0.4
            else ":::"
            if roll < 0.47
            else rng.choice(lefts) + _thue_word(rng, 0, 1)
            if roll < 0.65
            else _thue_word(rng, 0, 3)
        )
        rules.append(f"{lhs}::={rhs}")
    if rng.random() < 0.1:
        rules.insert(rng.randrange(len(rules) + 1), rng.choice(("", "  ")))
    if rng.random() < 0.05:
        rules.append(rng.choice(("  ::=x", "::=x", "a b::=a", "junk")))
    pieces = [*lefts, *lefts, *_THUE_SYMBOLS]
    state = "".join(rng.choice(pieces) for _ in range(rng.randint(0, 5)))
    if rng.random() < 0.1:
        state += "\n" + rng.choice(pieces)
    separator = rng.choice(("::=",) * 8 + ("  ::=  ", "\t::="))
    tail = rng.choice(("", "", "\n"))
    return "\n".join([*rules, separator, state]) + tail


def thue_program(rng: random.Random) -> str:
    """Return a program whose result no rewrite order changes.

    Thue picks rewrites at random (ours draws, the reference too), so only
    order-independent programs are comparable: draw until one is, on every
    input in ``THUE_INPUTS`` (the inputs it is then fed).
    """
    while True:
        program = thue_raw(rng)
        if thue_confluent(program):
            return program


def slashes_field(rng: random.Random) -> str:
    """Return a pattern or replacement, with escaped slashes and backslashes."""
    out = []
    for _ in range(rng.randint(0, 4)):
        roll = rng.random()
        out.append(
            rng.choice("ab")
            if roll < 0.75
            else rng.choice(("\\/", "\\\\", "\\a", "c", " "))
        )
    return "".join(out)


def slashes_program(rng: random.Random) -> str:
    """Return text and ``/p/r/`` rules, edge shapes now and then.

    Most patterns are nonempty and absent from their replacement, so most
    runs halt; an empty pattern, a pattern its replacement regrows, a cut
    rule and a trailing backslash still turn up.
    """
    parts = []
    for _ in range(rng.randint(1, 6)):
        roll = rng.random()
        if roll < 0.45:
            pattern = slashes_field(rng) or rng.choice("ab")
            if rng.random() < 0.03:
                pattern = ""
            replacement = slashes_field(rng)
            if pattern and pattern in replacement and rng.random() < 0.8:
                replacement = ""
            parts.append(f"/{pattern}/{replacement}/")
        elif roll < 0.9:
            parts.append(
                "".join(rng.choice("aabbc\n") for _ in range(rng.randint(1, 8)))
            )
        else:
            parts.append(rng.choice(("\\/", "\\\\", "\\a", "\\\n")))
    if rng.random() < 0.05:
        parts.append(rng.choice(("/a", "/a/b", "\\", "/a\\/")))
    return "".join(parts)


UNLAMBDA_PATCHES = (
    # Reference bug: `e` parsed as `c` (in c/ and c-refcnt/ alike).
    (
        "  else if ( ch == 'e' || ch == 'E' )\n    {\n"
        "      struct function_s *fun = new_function ();\n"
        "      struct expression_s *expr = new_expression ();\n\n"
        "      fun->t = FUNCTION_C;",
        "  else if ( ch == 'e' || ch == 'E' )\n    {\n"
        "      struct function_s *fun = new_function ();\n"
        "      struct expression_s *expr = new_expression ();\n\n"
        "      fun->t = FUNCTION_E;",
    ),
    # Ours rejects a source with more after its one expression
    # (the reference ignores the rest).
    (
        "int\nmain (int argc, char *argv[])",
        "static int\ntrailing (FILE *f)\n{\n  int ch;\n"
        "  while ( (ch = getc (f)) != EOF )\n"
        "    if ( ch == '#' )\n"
        "      while ( ch != '\\n' && ch != EOF ) ch = getc (f);\n"
        "    else if ( ch != ' ' && ch != '\\n' && ch != '\\r'"
        " && ch != '\\t' )\n      return 1;\n  return 0;\n}\n\n"
        "int\nmain (int argc, char *argv[])",
    ),
    (
        "      expr = parse (f);\n      fclose (f);",
        "      expr = parse (f);\n      if ( trailing (f) )\n"
        "        exit (1);\n      fclose (f);",
    ),
)


UNDERLOAD_PATCHES = (
    # Glue: run the page's own `step` under node, from a file.
    (
        "// Released to the public domain.",
        "var fs=require('fs'), els={prog:{value:fs.readFileSync("
        "process.argv[2],'latin1')},stack:{value:''},op:{value:''},"
        "startrun:{style:{}},stoprun:{style:{}}};\n"
        "var document={getElementById:function(k){return els[k];}};",
    ),
    (
        "if(c=='S') o.value+=pop(s);",
        "if(c=='S') fs.writeSync(1,Buffer.from(pop(s),'latin1'));",
    ),
    (
        "  alert(s);",
        "  process.exit(s=='Program terminated normally.'?0:71);",
    ),
    ("function abortrun()", "for(;;) step(0);\nfunction abortrun()"),
    # Ours skips whitespace between commands (the page: an error).
    (
        "else if(c=='<')",
        "else if(c==' '||c=='\\n'||c=='\\t'||c=='\\r');\n  else if(c=='<')",
    ),
)


THUE_PATCHES = (
    # Room: the original caps rules at 63 bytes, 63 matches, 16K.
    ("char\tlhs[64];\n\t char\trhs[64];", "char lhs[256], rhs[256];"),
    ("rulebase[128]", "rulebase[1024]"),
    ("*target[64],", "*target[1<<16],"),
    ("tempstr[64];", "tempstr[4096];"),
    ("rnum[64];", "rnum[1<<16];"),
    ("dataspace = malloc(16384);", "dataspace = malloc(1<<20);"),
    ("tempspace = malloc(16384);", "tempspace = malloc(1<<20);"),
    ("static\tchar\t buffer[256];", "static char buffer[4096];"),
    (
        "\t\t if (target[k] != NULL)\n",
        "\t\t if (j > 65000) exit (72);\n\t\t if (target[k] != NULL)\n",
    ),
    (
        '\t sprintf (tempspace, "%s%s%s"',
        "\t if (strlen (dataspace) + strlen (c) + 4096 > (1<<20))"
        " exit (72);\n"
        '\t sprintf (tempspace, "%s%s%s"',
    ),
    # Reference bug: the last line loses its final character when
    # the file does not end in a newline.
    (
        " buffer[strlen (buffer) - 1] = '\\0';",
        " if (buffer[strlen (buffer) - 1] == '\\n')"
        " buffer[strlen (buffer) - 1] = '\\0';",
    ),
    # Ours raises at end of input (the reference reuses a stale
    # buffer) and takes a last line with no newline whole.
    (
        "\t\t\tfgets (tempstr, sizeof (tempstr), stdin);\n"
        "                        tempstr[strlen (tempstr) - 1] = '\\0';",
        "\t\t\tif (!fgets (tempstr, sizeof (tempstr), stdin))"
        " exit (70);\n"
        "                        if (tempstr[strlen (tempstr) - 1]"
        " == '\\n') tempstr[strlen (tempstr) - 1] = '\\0';",
    ),
    # Vogel's output convention: no newline, except for `~` alone.
    (
        "puts (&rulebase[temp].rhs[1]);",
        "if (rulebase[temp].rhs[1]) fputs (&rulebase[temp].rhs[1],"
        " stdout); else putchar ('\\n');",
    ),
    # The state keeps the newlines between its lines.
    ("int\truleidx = 0,", "int\tstatelines = 0, ruleidx = 0,"),
    (
        "strcat (dataspace, line);",
        '{ if (statelines++) strcat (dataspace, "\\n"); strcat (dataspace, line); }',
    ),
    # Ours refuses a rule line with no `::=` (a blank one is
    # skipped) and an empty left side; the separator needs
    # whitespace on both sides, else a whitespace left side is a
    # rule (the original ends the rules at any of these).
    (
        '\t\t\tfprintf (stderr, "Malformed production: \\"%s\\"!\\n", line);',
        "\t\t\t{ for (tmp=line;*tmp;tmp++) if (!isspace (*tmp)) exit (71); }",
    ),
    (
        "\t\t else if (c == line)\n\t\t\tstate = 1;\n",
        "",
    ),
    (
        "\t\t\t if (flagstate)\n",
        "\t\t\t for (tmp=c+3;*tmp;tmp++)\n"
        "\t\t\t\tif (!isspace (*tmp))\n"
        "\t\t\t\t\t flagstate = 1;\n"
        "\t\t\t if (flagstate && c == line)\n"
        "\t\t\t\t exit (71);\n"
        "\t\t\t if (flagstate)\n",
    ),
)
