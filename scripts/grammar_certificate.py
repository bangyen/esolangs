"""Check a forbidden-factor DFA by an independent position automaton."""

import re
from collections import deque
from collections.abc import Iterable
from re import _constants as rc  # type: ignore[attr-defined]
from re import _parser  # type: ignore[attr-defined]
from typing import Any


class _LiteralMonitor:
    """Recognize finite factors with failure links, without subset construction."""

    def __init__(self, factors: list[str], alphabet: str) -> None:
        self.rows = [[-1] * len(alphabet)]
        self.bad = [False]
        for factor in factors:
            if not factor or any(char not in alphabet for char in factor):
                raise ValueError("invalid literal factor")
            state = 0
            for char in factor:
                column = alphabet.index(char)
                if self.rows[state][column] == -1:
                    self.rows[state][column] = len(self.rows)
                    self.rows.append([-1] * len(alphabet))
                    self.bad.append(False)
                state = self.rows[state][column]
            self.bad[state] = True
        failure = [0] * len(self.rows)
        todo: deque[int] = deque()
        for column, target in enumerate(self.rows[0]):
            if target == -1:
                self.rows[0][column] = 0
            else:
                todo.append(target)
        while todo:
            state = todo.popleft()
            self.bad[state] |= self.bad[failure[state]]
            for column, target in enumerate(self.rows[state]):
                fallback = self.rows[failure[state]][column]
                if target == -1:
                    self.rows[state][column] = fallback
                else:
                    failure[target] = fallback
                    todo.append(target)


class _RegexMonitor:
    """Recognize regex factors by first/last/follow positions; no epsilon NFA."""

    def __init__(self, pattern: str, alphabet: str) -> None:
        self.follow: list[int] = []
        self.letters = [0] * len(alphabet)
        self.cache: dict[int, tuple[int, ...]] = {}
        try:
            parsed = _parser.parse(pattern, 0)
        except re.error as error:
            raise ValueError(f"invalid regular factor: {error}") from error
        if parsed.state.flags != re.UNICODE:
            raise ValueError("unsupported regex flags")
        self.first, self.last, nullable = self._sequence(parsed, alphabet)
        if nullable:
            raise ValueError("empty regular factor")

    def _sequence(
        self, items: Iterable[tuple[Any, Any]], alphabet: str
    ) -> tuple[int, int, bool]:
        first = last = 0
        nullable = True
        for op, arg in items:
            if op in (rc.LITERAL, rc.IN):
                chars = (
                    [arg]
                    if op == rc.LITERAL
                    else [value for kind, value in arg if kind == rc.LITERAL]
                )
                if op == rc.IN and len(chars) != len(arg):
                    raise ValueError("unsupported character class")
                position = 1 << len(self.follow)
                self.follow.append(0)
                for char in chars:
                    if chr(char) not in alphabet:
                        raise ValueError("regular factor outside alphabet")
                    self.letters[alphabet.index(chr(char))] |= position
                head = tail = position
                empty = False
            elif op == rc.SUBPATTERN:
                if arg[1] or arg[2]:
                    raise ValueError("unsupported regex flags")
                head, tail, empty = self._sequence(arg[-1], alphabet)
            elif op == rc.BRANCH:
                branches = [self._sequence(branch, alphabet) for branch in arg[1]]
                head = tail = 0
                empty = False
                for start, end, epsilon in branches:
                    head |= start
                    tail |= end
                    empty |= epsilon
            elif op == rc.MAX_REPEAT and arg[:2] == (0, rc.MAXREPEAT):
                head, tail, _ = self._sequence(arg[2], alphabet)
                self._connect(tail, head)
                empty = True
            else:
                raise ValueError(f"unsupported regex operator {op}")
            self._connect(last, head)
            if nullable:
                first |= head
            last = tail | last if empty else tail
            nullable &= empty
        return first, last, nullable

    def _connect(self, sources: int, targets: int) -> None:
        while sources:
            bit = sources & -sources
            self.follow[bit.bit_length() - 1] |= targets
            sources ^= bit

    def transitions(self, state: int) -> tuple[int, ...]:
        """Return live positions or -1 on the first completed factor."""
        if state not in self.cache:
            positions = self.first
            remaining = state
            while remaining:
                bit = remaining & -remaining
                positions |= self.follow[bit.bit_length() - 1]
                remaining ^= bit
            targets = [positions & letters for letters in self.letters]
            self.cache[state] = tuple(
                -1 if target & self.last else target for target in targets
            )
        return self.cache[state]


def check_grammar(
    rows: list[list[int]],
    alphabet: str,
    factors: list[str],
    regexes: list[str],
    *,
    state_cap: int = 150_000,
) -> int:
    """Prove prefix-language equivalence by exhausting the reachable product.

    This checks the supplied grammar, not the semantic soundness of its rules.
    A budget exhaustion is an error, never a partial acceptance certificate.
    """
    if (
        type(state_cap) is not int
        or state_cap < 1
        or not alphabet
        or len(set(alphabet)) != len(alphabet)
        or not rows
        or any(
            len(row) != len(alphabet)
            or any(
                type(target) is not int or not -1 <= target < len(rows)
                for target in row
            )
            for row in rows
        )
    ):
        raise ValueError("invalid grammar DFA")
    literals = _LiteralMonitor(factors, alphabet)
    monitors = [_RegexMonitor(pattern, alphabet) for pattern in regexes]
    initial = (0, 0, (0,) * len(monitors))
    witnesses = {initial: ""}
    todo = deque([initial])
    while todo:
        state, literal, positions = todo.popleft()
        witness = witnesses[state, literal, positions]
        transitions = [
            monitor.transitions(active)
            for monitor, active in zip(monitors, positions, strict=True)
        ]
        for column, char in enumerate(alphabet):
            target = rows[state][column]
            next_literal = literals.rows[literal][column]
            next_positions = tuple(row[column] for row in transitions)
            rejected = literals.bad[next_literal] or -1 in next_positions
            if (target == -1) != rejected:
                raise ValueError(f"grammar mismatch on {witness + char!r}")
            if rejected:
                continue
            key = (target, next_literal, next_positions)
            if key not in witnesses:
                if len(witnesses) >= state_cap:
                    raise ValueError("grammar product budget exceeded")
                witnesses[key] = witness + char
                todo.append(key)
    return len(witnesses)
