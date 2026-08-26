"""Rank text generators by emitted size, to find where size is left on the table.

Method: for each generator, emit programs for a fixed corpus and report
characters-per-input-character.  A generator whose ratio is far above its
family's median is a candidate -- but see the caveats printed at the end:
a high ratio is evidence to investigate, never a defect on its own.
"""

import importlib
import statistics

reg = importlib.import_module("esolangs.registry")

CORPUS = [
    ("hello", "Hello, World!"),
    ("lower", "the quick brown fox jumps over the lazy dog"),
    ("repeat", "aaaaaaaaaaaaaaaaaaaa"),
    ("alternate", "abababababababababab"),
    ("ascending", "".join(chr(i) for i in range(48, 68))),
    ("spread", "".join(chr(i) for i in (32, 126, 32, 126, 32, 126))),
    ("digits", "1234567890"),
]

rows = []
for name, gen in sorted(reg.GENERATORS.items()):
    per: dict[str, float | None] = {}
    total_in = total_out = 0
    ok = True
    for label, text in CORPUS:
        try:
            out = gen(text)
        except Exception:
            per[label] = None
            ok = False
            continue
        out = str(out)
        per[label] = len(out) / len(text)
        total_in += len(text)
        total_out += len(out)
    if total_in:
        rows.append((name, total_out / total_in, per, ok))

rows.sort(key=lambda r: -r[1])
ratios = [r[1] for r in rows]
med = statistics.median(ratios)

print(f"{'generator':<26}{'chars/char':>12}{'vs median':>12}   per-case ratios")
print("-" * 100)
for name, ratio, per, ok in rows:
    detail = " ".join(
        f"{lbl}={per[lbl]:.0f}" if per[lbl] is not None else f"{lbl}=X"
        for lbl, _ in CORPUS
    )
    flag = "" if ok else "  (some inputs rejected)"
    print(f"{name:<26}{ratio:>12.1f}{ratio / med:>11.1f}x   {detail}{flag}")

print(f"\nmedian chars/char across {len(rows)} generators: {med:.1f}")
print("""
CAVEATS -- read before acting on any row above:
  * A high ratio is often the LANGUAGE, not the generator.  Polynomial emits
    a giant integer by design; Collatz Multiverse emits English sentences.
  * The right comparison is against sibling generators in the same family
    (tape vs tape, literal vs literal), not against the global median.
  * 'spread' vs 'repeat' is the signal worth reading: a generator whose
    spread ratio is far above its repeat ratio is not exploiting deltas,
    which IS a generator-level choice.
  * Anything flagged here needs the same treatment as bucket 3: measure the
    alternative and verify it RUNS before believing the saving.""")
