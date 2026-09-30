"""Rebuild the finite-state Brainfuck behaviour-count certificate."""

import itertools
from functools import lru_cache
from re import _constants as rc
from re import _parser

ALPHABET = ".,-+<>[]"
BOUND = (70347, 10000)


def local_patterns():
    patterns = {
        "+-",
        "-+",
        "><",
        "+[-]",
        "-[-]",
        "+,",
        "-,",
        "[-],",
        "][",
        "[+]",
        "[++]",
        "[+++]",
        "[++++]",
        "[].",
    }
    ds = [""]
    for n in range(1, 7):
        for cs in itertools.product("+-<>.", repeat=n):
            word = "".join(cs)
            p = d = 0
            good = True
            for c in word:
                p += (c == ">") - (c == "<")
                if p < 0:
                    good = False
                    break
                if p == 0:
                    d += (c == "+") - (c == "-")
            if good and p == d == 0:
                ds.append(word)
                patterns.add("]" + word + "[")
                patterns.add("[" + word + "]")
                patterns.add("[]" + word)
    # A finite subset suffices; longer divergence prefixes are regular below.
    for s in ds:
        for t in ds:
            if len(s) + len(t) <= 6:
                patterns.add("[" + s + "[" + t + "]")
    for letters, limit, ys in [("+-<>", 6, ".,+-"), ("+-<>.,", 5, "+-")]:
        for n in range(limit + 1):
            for cs in itertools.product(letters, repeat=n):
                p = 1
                good = True
                for c in cs:
                    p += (c == ">") - (c == "<")
                    if p < 1:
                        good = False
                        break
                if not good or p != 1:
                    continue
                e = ">" + "".join(cs) + "<"
                for y in ys:
                    patterns.add(e + y)
                patterns.add("[-]" + e)
    for n in range(5):
        for cs in itertools.product("+-<>.,", repeat=n):
            p = 0
            for c in cs:
                p += (c == ">") - (c == "<")
                if p < 0:
                    break
            else:
                patterns.add(">" + "".join(cs) + "<>")
    return patterns


def _stationary(letters):
    return r"(?:[" + letters + r"]|\[" + "[" + letters + r"]*\])*"


def _confined(letters):
    body = "[" + letters + "]*"
    return "(?:[" + letters + r"]|\[" + body + r"\]|>" + body + "<)*"


def regular_patterns():
    # Stationary loops and right excursions return without changing the
    # tested cell. A read can cross only a terminating, silent excursion.
    w0, w1 = _stationary(r"+\-."), _stationary(r"+\-.,")
    rf, io, ni = (_confined(chars) for chars in (r"+\-.", r"+\-.,", r"+\-"))
    halting = r"(?:[+\-]|\[-\]|>[+\-]*<)*"
    loop = r"\[[+\-.,]*\]"
    patterns = [
        r">\[\]<" + w0 + ">",
        r"\[]>" + rf + "<",
        r"\[-\]>" + io + "<",
        r">\[-\]<" + w1 + ">",
        ">" + ni + r"<[.+\-]",
        ">" + halting + "<,",
        ">" + io + r"<[+\-]",
        r"\[[+\-]*\[-\][+\-]*\]",
        loop + ">" + halting + "<",
        ">" + loop + r"<[+\-]*>",
    ]
    # These balanced bodies have arbitrary length and nesting depth <= 1.
    body = r"(?:[+\-<>.,]|\[[+\-<>.,]*\])*"
    readfree = r"(?:[+\-<>.]|\[[+\-<>.]*\])*"
    preserve_rf = r"(?:\.|>" + rf + "<)*"
    preserve_io = r"(?:\.|>" + io + "<)*"
    patterns += [
        r"\[" + readfree + r"\[" + readfree + r"\]\.*[+\-]\.*\]",
        ">" + io + "<>",
        r"\]" + preserve_io + r"\[",
        r"\[" + preserve_rf + r"\[\]",
        r"\[\." + body + r"\]\.",
    ]
    return patterns


def automaton(patterns, regexes):
    # Trie shares the finite prefixes; Thompson states handle regular tails.
    edges = [{}]
    eps = [[]]
    finals = set()

    def state():
        edges.append({})
        eps.append([])
        return len(edges) - 1

    def edge(a, c, b):
        edges[a].setdefault(c, []).append(b)

    for word in sorted(patterns):
        s = 0
        for c in word:
            if c not in edges[s]:
                edge(s, c, state())
            s = edges[s][c][0]
        finals.add(s)

    def compile_seq(items, a, b):
        for index, (op, arg) in enumerate(items):
            t = b if index == len(items) - 1 else state()
            if op == rc.LITERAL:
                edge(a, chr(arg), t)
            elif op == rc.IN:
                for subop, val in arg:
                    assert subop == rc.LITERAL
                    edge(a, chr(val), t)
            elif op == rc.BRANCH:
                for branch in arg[1]:
                    compile_seq(branch, a, t)
            elif op == rc.SUBPATTERN:
                compile_seq(arg[-1], a, t)
            elif op == rc.MAX_REPEAT:
                lo, hi, inner = arg
                assert lo == 0
                assert hi == rc.MAXREPEAT
                u, v = state(), state()
                eps[a].extend((u, t))
                compile_seq(inner, u, v)
                eps[v].extend((u, t))
            else:
                raise ValueError(op)
            a = t
        if not items:
            eps[a].append(b)

    for regex in regexes:
        s, t = state(), state()
        eps[0].append(s)
        compile_seq(_parser.parse(regex, 0), s, t)
        finals.add(t)
    closures = []
    for s in range(len(edges)):
        seen, todo = {s}, [s]
        while todo:
            for t in eps[todo.pop()]:
                if t not in seen:
                    seen.add(t)
                    todo.append(t)
        closures.append(sum(1 << t for t in seen))
    transitions = []
    for s in range(len(edges)):
        transitions.append([0] * len(ALPHABET))
        for i, c in enumerate(ALPHABET):
            for t in edges[s].get(c, []):
                transitions[s][i] |= closures[t]
    bad = sum(1 << s for s in finals)
    initial = closures[0]
    states, indices, rows = [initial], {initial: 0}, []
    for subset in states:
        dest = [initial] * 8
        bits = subset
        while bits:
            bit = bits & -bits
            s = bit.bit_length() - 1
            bits ^= bit
            for c in range(8):
                dest[c] |= transitions[s][c]
        row = []
        for target in dest:
            if target & bad:
                row.append(-1)
            else:
                if target not in indices:
                    indices[target] = len(states)
                    states.append(target)
                row.append(indices[target])
        rows.append(row)
        if len(states) > 150000:
            raise RuntimeError("state budget exceeded")
    return rows


def minimize(rows):
    groups = [0] * len(rows)
    while True:
        keys, new = {}, []
        for row in rows:
            key = tuple(groups[j] if j >= 0 else -1 for j in row)
            if key not in keys:
                keys[key] = len(keys)
            new.append(keys[key])
        if new == groups:
            break
        groups = new
    representatives = {}
    for i, g in enumerate(groups):
        representatives[g] = i
    return [
        [groups[j] if j >= 0 else -1 for j in rows[representatives[g]]]
        for g in range(len(representatives))
    ]


def intersect(a, b):
    states, indices, rows = [(0, 0)], {(0, 0): 0}, []
    for s, t in states:
        row = []
        for u, v in zip(a[s], b[t], strict=True):
            if min(u, v) < 0:
                row.append(-1)
                continue
            pair = u, v
            if pair not in indices:
                indices[pair] = len(states)
                states.append(pair)
            row.append(indices[pair])
        rows.append(row)
        if len(states) > 150000:
            raise RuntimeError("product budget exceeded")
    return minimize(rows)


@lru_cache(maxsize=1)
def certificate():
    """Return the reconstructed DFA and an exactly checked positive vector."""
    rows = minimize(automaton(local_patterns(), []))
    for pattern in regular_patterns():
        rows = intersect(rows, minimize(automaton([], [pattern])))
    vector = [1.0] * len(rows)
    for _ in range(500):
        image = [sum(vector[j] for j in row if j >= 0) for row in rows]
        scale = max(image)
        image = [value / scale for value in image]
        error = max(abs(a - b) for a, b in zip(vector, image, strict=True))
        vector = image
        if error < 1e-13:
            break
    integers = [max(1, round(value * 10**12)) for value in vector]
    check_certificate(rows, integers)
    return rows, integers


def check_certificate(rows, vector):
    """Check M v <= (70347/10000) v using integers only."""
    numerator, denominator = BOUND
    assert len(rows) == len(vector)
    assert all(value > 0 for value in vector)
    for row, value in zip(rows, vector, strict=True):
        assert len(row) == len(ALPHABET)
        assert all(-1 <= target < len(rows) for target in row)
        assert denominator * sum(vector[j] for j in row if j >= 0) <= numerator * value


def accepts(rows, word):
    """Return whether the word avoids every forbidden factor."""
    state = 0
    for char in word:
        state = rows[state][ALPHABET.index(char)]
        if state < 0:
            return False
    return True


if __name__ == "__main__":
    rows, vector = certificate()
    print(f"{len(rows)} DFA states; exact upper certificate {BOUND[0]}/{BOUND[1]}")
