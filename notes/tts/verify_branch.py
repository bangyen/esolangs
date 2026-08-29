"""Confirm the drain comparator is a real, tunable input-dependent branch.

``comparator.py`` shows ``o v49 @ v50`` emits for input '1' and not for '0'.
This checks that the behaviour is the comparator doing what its arithmetic
says -- not a coincidence of two constants -- by sweeping the threshold and
predicting each outcome from ``sum(rest)/2 > front`` in advance.
"""

from probe import go


def predict(front, tail_const, input_byte):
    """Predict whether the drain fires, straight from the interpreter's test."""
    return (input_byte + tail_const) / 2 > front


def main():
    """Sweep the threshold constant and compare prediction to observation."""
    print("front=49, varying the trailing constant:")
    ok = True
    for tail in (48, 49, 50, 51, 52):
        src = f"o v49 @ v{tail}"
        for ch in ("0", "1"):
            text = go(src, ch)[0]
            fired = text != ""
            want = predict(49, tail, ord(ch))
            match = fired == want
            ok = ok and match
            print(f"  v{tail} input={ch!r}: emitted={fired} "
                  f"predicted={want} {'ok' if match else 'MISMATCH'}")
    print(f"\nall predictions match: {ok}")

    print("\nthe gate moves with the threshold, i.e. it is tunable:")
    for tail in (48, 50, 52):
        outs = tuple(go(f"o v49 @ v{tail}", ch)[0] for ch in ("0", "1"))
        print(f"  v49 @ v{tail} -> {outs}")


if __name__ == "__main__":
    main()
