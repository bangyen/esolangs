"""BIO source wrapping and balancing."""

from __future__ import annotations

import re

from esolangs.generation.token_balance import balanced_token_width
from esolangs.generation.wrap import _RUN, _join_tokens, balance_score

# ``[01][oi][xyz]`` plus ``;`` or ``{``, or ``};``, or the separating
# space.  Varying width is why neither a character wrap nor a fixed stride
# will do.
_BIO_COMMAND = r"[01][oOiI][xXyYzZ](?:\{|;)|\};| "


def _bio(program: str, width: int) -> str:
    """Wrap BIO, indenting a nested program by its loop depth.

    The separating space attaches to the following command.  ``0i?`` opens a
    level and ``}`` closes, so a program two or more levels deep is indented
    by depth (the boolean generator nests one loop per row).
    """
    merged = _bio_tokens(program)
    if merged is None:
        return program
    if _bio_depth(merged) >= 2:
        return _bio_indented(merged, width)
    wrapped = _join_tokens(merged, width, separator="")
    # The newline replaces the trailing separator.
    return "\n".join(line.rstrip(" ") for line in wrapped.split("\n"))


def _bio_tokens(program: str) -> list[str] | None:
    """Return BIO commands with their trailing separators, if they tile source."""
    tokens = re.findall(f"{_RUN}|{_BIO_COMMAND}", program)
    if "".join(tokens) != program:
        return None
    merged: list[str] = []
    for token in tokens:
        if token.isspace() and merged:
            merged[-1] += token
        else:
            merged.append(token)
    return merged


def _bio_opens(token: str) -> bool:
    """Whether ``token`` opens a BIO loop: the ``0i?`` triple *with* its ``{``."""
    return token[:2].lower() == "0i" and "{" in token


def _bio_closes(token: str) -> bool:
    """Whether ``token`` closes a BIO loop."""
    return token.startswith("}")


def _bio_depth(tokens: list[str]) -> int:
    """Return the deepest loop nesting ``tokens`` reaches."""
    depth = best = 0
    for token in tokens:
        if _bio_opens(token):
            depth += 1
            best = max(best, depth)
        elif _bio_closes(token):
            depth = max(0, depth - 1)
    return best


def _bio_indented(tokens: list[str], width: int) -> str:
    """Lay BIO out one loop level to a line, indented by depth.

    The run between an open and a close (the ``0oy`` ramp) packs to the
    remaining width; the indent stops growing once a run would have less
    than a quarter of the width.
    """
    lines: list[str] = []
    cap = max(0, (width - width // 4) // 2)
    for depth, run in _bio_runs(tokens):
        pad = " " * (2 * min(depth, cap))
        room = max(width - len(pad), width // 4)
        for line in _join_tokens(run, room, separator="").split("\n"):
            lines.append((pad + line).rstrip(" "))
    return "\n".join(lines)


def _bio_runs(tokens: list[str]) -> list[tuple[int, list[str]]]:
    """Return structural straight runs with their loop depth."""
    groups: list[tuple[int, list[str]]] = []
    depth = 0
    run: list[str] = []

    def flush(at: int) -> None:
        """Retain a nonempty run without sharing its mutable buffer."""
        if run:
            groups.append((at, run.copy()))
            run.clear()

    for token in tokens:
        if _bio_opens(token):
            run.append(token)
            flush(depth)
            depth += 1
        elif _bio_closes(token):
            flush(depth)
            depth = max(0, depth - 1)
            run.append(token)
            flush(depth)
        else:
            run.append(token)
    flush(depth)
    return groups


def _balance_bio(program: str) -> str:
    """Balance shallow token fits or nested padding-cap and run-fit regimes."""
    tokens = _bio_tokens(program)
    if tokens is None:
        return program
    if _bio_depth(tokens) < 2:
        width = balanced_token_width(tokens, rstrip_rows=True)
        return min(program, _bio(program, width), key=balance_score)
    groups = _bio_runs(tokens)
    full_spans = [2 * depth + len("".join(run).rstrip(" ")) for depth, run in groups]
    widest = max(full_spans)
    if widest <= len(groups):
        # Every layout has at least one row per structural run and no row
        # wider than its fully indented run. Attaining both bounds is optimal.
        target = min(
            depth
            for (depth, _run), span in zip(groups, full_spans, strict=True)
            if span == widest
        )
        cap_widths = []
        for residue in range(8):
            fixed = (residue - residue // 4) // 2
            remainder = residue - 2 * fixed
            quotient = max(0, -((residue - 1) // 8), -((fixed - target) // 3))
            for depth, run in groups:
                if len(run) > 1:
                    length = sum(map(len, run))
                    # For w=8q+r, room=max(2q+r-2f, 8q+r-2depth).
                    quotient = max(
                        quotient,
                        min(
                            -((remainder - length) // 2),
                            -((residue - 2 * depth - length) // 8),
                        ),
                    )
            cap_widths.append(8 * quotient + residue)
        width = min(cap_widths, key=lambda value: ((value - value // 4) // 2, value))
        return min(program, _bio_indented(tokens, width), key=balance_score)

    depth_limit = max(depth for depth, _run in groups)
    fits: list[tuple[int, set[int]]] = []
    for depth, run in groups:
        lengths = list(map(len, run))
        if len(set(lengths)) == 1:
            spans = set(range(lengths[0], sum(lengths) + 1, lengths[0]))
        else:
            prefix = [0]
            for length in lengths:
                prefix.append(prefix[-1] + length)
            spans = {
                end - start
                for at, start in enumerate(prefix[:-1])
                for end in prefix[at + 1 :]
            }
        fits.append((depth, spans))
    widths = set()
    for cap in range(depth_limit + 1):
        lower = max(1, 2 * cap + 2 * cap // 3)
        stop = (
            2 * (cap + 1) + 2 * (cap + 1) // 3 - 1
            if cap < depth_limit
            else max(lower, max(2 * depth + max(spans) for depth, spans in fits))
        )
        widths.add(lower)
        for depth, spans in fits:
            pad = 2 * min(depth, cap)
            widths.update(pad + span for span in spans if lower < pad + span <= stop)
    # Padding is fixed within each cap interval; only whole run fits can
    # change its source. Beyond the last fit, the layout is constant.
    candidates = [_bio_indented(tokens, width) for width in sorted(widths)]
    return min(program, *candidates, key=balance_score)
