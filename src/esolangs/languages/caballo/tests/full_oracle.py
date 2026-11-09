"""Caballo reference: delimiter AST, occurrence paths and explicit continuations.

No production parser, transition, store, snapshot or randomness helper is used.
Sequence occurrences are numbered root-first/left-to-right only when projecting
semantic code references; the evaluator follows AST paths, not compiled IDs.
"""

import random
from collections import Counter
from dataclasses import dataclass
from typing import NamedTuple


def _tree(source):
    contexts = [("root", [[]])]
    for token in source:
        if token.isspace():
            continue
        kind, branches = contexts[-1]
        if token in "([":
            contexts.append((token, [[]]))
        elif token in "+|":
            if kind != "(":
                raise ValueError("branch separator outside sum")
            branches.append([])
        elif token in ")]":
            if kind != {")": "(", "]": "["}[token]:
                raise ValueError("mismatched delimiter")
            contexts.pop()
            node = (
                ("sum", tuple(tuple(branch) for branch in branches))
                if kind == "("
                else ("loop", (tuple(branches[0]),))
            )
            contexts[-1][1][-1].append(node)
        elif token in "pqid0123456789-":
            branches[-1].append(token)
        else:
            raise ValueError("unknown command")
    if len(contexts) != 1:
        raise ValueError("unclosed delimiter")
    return tuple(contexts[0][1][0])


def _sequences(tree):
    sequences, numbers, table = ({}, {}, [])

    def visit(sequence, path):
        number = len(table)
        numbers[path] = number
        sequences[path] = sequence
        table.append(None)
        body = []
        for offset, node in enumerate(sequence):
            if isinstance(node, str):
                body.append(node)
            else:
                kind, branches = node
                children = tuple(
                    (
                        visit(branch, (*path, offset, i))
                        for i, branch in enumerate(branches)
                    )
                )
                body.append((kind, children))
        table[number] = tuple(body)
        return number

    visit(tree, ())
    return (sequences, numbers, tuple(table))


def _canonical(mapping):
    return tuple(
        sorted(((stack, weight) for stack, weight in mapping.items() if weight))
    )


def _combined(left, right):
    total = Counter(left)
    total.update(right)
    return {stack: weight for stack, weight in total.items() if weight}


def _short(stack):
    values = tuple(stack)
    while values and values[-1] == 0:
        values = values[:-1]
    return values


def _operate(command, mapping):
    if command == "0":
        return {}
    if command == "-":
        return {stack: -weight for stack, weight in mapping.items()}
    result = Counter()
    for stack, weight in mapping.items():
        top = stack[0] if stack else 0
        tail = stack[1:]
        if command == "p":
            moved = tail
        elif command == "q":
            moved = (0, *stack)
        elif command in "id":
            changed = top + (1 if command == "i" else -1)
            if changed < 0:
                continue
            moved = (changed, *tail)
        else:
            depth = ord(command) - ord("1")
            moved = [*stack, *[0] * max(0, depth + 1 - len(stack))]
            moved[0], moved[depth] = (moved[depth], moved[0])
        result[_short(moved)] += weight
    return {stack: weight for stack, weight in result.items() if weight}


@dataclass
class _Sequence:
    path: tuple
    position: int = 0


@dataclass
class _Sum:
    paths: tuple
    next_branch: int
    base: dict
    total: dict


@dataclass
class _Repeat:
    path: tuple
    total: dict


class _Rendered(NamedTuple):
    """A terminal effect and its independent draw evidence."""

    output: str
    error: str | None
    bounds: tuple[int, ...]
    draws: tuple[int, ...]


def _initial_values(stdin):
    """Validate naturals under the native documented host integer policy."""
    values = []
    for token in stdin.split():
        if not token or any(char not in "0123456789" for char in token):
            return ("halt", None)
        try:
            values.append(int(token))
        except ValueError:
            return ("syntax", None)
    return (None, values)


def _finish_output(current, random_source, ticket, writer_prefix):
    """Choose the terminal positive stack and render one optional effect."""
    output, error, bounds, draws = ("", None, [], [])
    positive = [(stack, weight) for stack, weight in _canonical(current) if weight > 0]
    if positive:
        chosen = positive[0][0]
        if len(positive) > 1:
            bound = sum((weight for stack, weight in positive))
            chosen_ticket = random_source.randrange(bound) if ticket is None else ticket
            assert 0 <= chosen_ticket < bound
            bounds.append(bound)
            draws.append(chosen_ticket)
            remaining = chosen_ticket
            for stack, weight in positive:
                if remaining < weight:
                    chosen = stack
                    break
                remaining -= weight
        try:
            rendered = "[" + ",".join(str(value) for value in chosen) + "]"
        except ValueError:
            error = "syntax"
        else:
            if writer_prefix is None:
                output += rendered
            else:
                output += rendered[:writer_prefix]
                error = "writer"
    return _Rendered(output, error, tuple(bounds), tuple(draws))


def _full_model(
    source,
    stdin,
    *,
    cap=256,
    ticket=None,
    seed=0,
    writer_prefix=None,
    idle_after_failure=0,
):
    """Return raw error, trace, constructor IO and exact immutable program view.

    Standard rows retain observed's five fields. State adds draw bounds and
    successful/failed read counts after the native state/done fields. A controlled
    writer failure commits done before retaining its prefix; idles stay faulted.
    """
    try:
        tree = _tree(source)
    except ValueError:
        return ("syntax", [(None, False, "", 0, 0)], (0, 0, 0), None)
    sequences, numbers, program = _sequences(tree)
    consumed, reads, past_end = (len(stdin), 1, 0)
    error, values = _initial_values(stdin)
    if error:
        return (
            error,
            [(None, False, "", consumed, consumed)],
            (consumed, reads, past_end),
            program,
        )
    current = {_short(values): 1}
    work = [_Sequence(())]
    done, output, bounds, draws = (False, "", [], [])
    random_source = random.Random(seed)

    def frames():
        captured = []
        for frame in work:
            if isinstance(frame, _Sequence):
                captured.append(("seq", numbers[frame.path], frame.position))
            elif isinstance(frame, _Sum):
                captured.append(
                    (
                        "sum",
                        tuple(numbers[path] for path in frame.paths),
                        frame.next_branch,
                        _canonical(frame.base),
                        _canonical(frame.total),
                    )
                )
            else:
                captured.append(("loop", numbers[frame.path], _canonical(frame.total)))
        return tuple(captured)

    def row():
        state = (
            frames(),
            _canonical(current),
            done,
            tuple(bounds),
            tuple(draws),
            reads,
            past_end,
        )
        return (state, done, output, consumed, consumed)

    trace = [row()]
    error = None
    for _ in range(cap):
        if done:
            break
        active = work[-1]
        assert isinstance(active, _Sequence)
        sequence = sequences[active.path]
        if active.position < len(sequence):
            offset = active.position
            node = sequence[offset]
            active.position += 1
            if current:
                if isinstance(node, str):
                    current = _operate(node, current)
                else:
                    kind, children = node
                    paths = tuple(
                        (*active.path, offset, i) for i in range(len(children))
                    )
                    if kind == "sum":
                        work.append(_Sum(paths, 1, dict(current), {}))
                    else:
                        work.append(_Repeat(paths[0], dict(current)))
                    work.append(_Sequence(paths[0]))
        else:
            work.pop()
            if not work:
                done = True
                rendered = _finish_output(current, random_source, ticket, writer_prefix)
                bounds.extend(rendered.bounds)
                draws.extend(rendered.draws)
                output += rendered.output
                error = rendered.error
            else:
                group = work[-1]
                total = _combined(group.total, current)
                if isinstance(group, _Sum):
                    if group.next_branch == len(group.paths):
                        work.pop()
                        current = total
                    else:
                        selected = group.paths[group.next_branch]
                        group.next_branch += 1
                        group.total = total
                        current = dict(group.base)
                        work.append(_Sequence(selected))
                elif not current:
                    work.pop()
                    current = total
                else:
                    group.total = total
                    work.append(_Sequence(group.path))
        trace.append(row())
        if error:
            trace.extend(row() for _ in range(idle_after_failure))
            break
    if done and (not error):
        trace.extend(row() for _ in range(3))
    return (error, trace, (consumed, reads, past_end), program)


def _full_parts(row):
    return (*row[0][:3], row[-1])
