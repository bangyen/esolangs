import random

from esolangs.tools.thisthat import (
    _rotate_tree,
    _stream_tree,
    _strip_tree,
    _tree,
    thisthat,
)


def sources(table):
    groups = {}

    def add(source, label):
        groups.setdefault(source, []).append(label)

    for width in (None, 1, 13, 100):
        add(thisthat(table, width), f"public:{width}")
    for prune in (False, True):
        for reorder in (False, True):
            source = _tree(table, prune=prune, reorder=reorder)
            label = f"tree:{prune}:{reorder}"
            add(source, label)
            add(_rotate_tree(source), "rotated:" + label)
    if len(table) <= 8:
        add(_strip_tree(table), "strip")
    if len(table) <= 4:
        add(_stream_tree(table), "stream")
    return groups


def legacy_tables():
    rng = random.Random(6)
    for n in (4, 5, 6):
        for index in range(12):
            yield (
                n,
                f"legacy-random:{index}",
                "".join(rng.choice("01") for _ in range(1 << n)),
            )
    for n in (4, 6, 8):
        rng = random.Random(946 + n)
        yield n, "legacy-narrow", "".join(str(rng.randrange(2)) for _ in range(1 << n))


def tables(n):
    count = 1 << n
    rng = random.Random(177564 + n)
    exceptions = {0, count // 3, count - 1}
    return {
        "zero": "0" * count,
        "one": "1" * count,
        "parity": "".join(str(row.bit_count() % 2) for row in range(count)),
        "sparse": "".join(str(int(row in exceptions)) for row in range(count)),
        "dense": "".join(str(int(row not in exceptions)) for row in range(count)),
        "random": "".join(rng.choice("01") for _ in range(count)),
    }
