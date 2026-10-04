import itertools


def finite_cases():
    cases = []
    for body in ([], [""], ["x"], ["x", "y"], ["abc", "abbc"]):
        for pattern, replacement in [
            ("x", "q"),
            ("a|b", "Q"),
            ("(a)", "X"),
            ("ab*", "Z"),
            ("ab+", "Z"),
            ("ab?", "Z"),
            (".", "V"),
            ("^", "prefix"),
            ("$", "suffix"),
        ]:
            source = [
                "inject data=" + pattern + "/" + replacement,
                "send data",
                "skip",
                "data;",
                *body,
                "data;",
            ]
            cases.append((source, ""))
    for old in ([], [""], ["old"], ["old", "two"]):
        for text in ("\n", "v\n", "Ā\n", "a\r\n"):
            for earlier in (True, False):
                block = ["data;", *old, "data;"]
                source = (
                    [*block, "readto data", "send data"]
                    if earlier
                    else ["readto data", "send data", "skip", *block]
                )
                cases.append((source, text))
    for left, right in itertools.product(([], [""], ["x"], ["x", "y"]), repeat=2):
        for op in ("skipif a", "skipq a b"):
            cases.append(
                (
                    [
                        "skip",
                        "a;",
                        *left,
                        "a;",
                        "b;",
                        *right,
                        "b;",
                        op,
                        "seen;",
                        "send mark",
                        "seen;",
                        "skip",
                        "mark;",
                        "seen",
                        "mark;",
                    ],
                    "",
                )
            )
    return cases


def edge_cases():
    cases = []
    for command in (
        "send nowhere",
        "skip please",
        "skipq only",
        "inject data",
        "inject data=x",
        "inject data=(/x",
        r"inject data=x/\2",
        r"inject data=x/\g<missing>",
        "readto nowhere",
    ):
        cases.append((command + "\nskip\ndata;\nx\ndata;", "v\n"))
    for closing in range(2, 12):
        cases.append(("a;\nreadto a\n" + "junk\n" * (closing - 2) + "a;", "v\n"))
    for target in ("outer", "inner"):
        for text in ("\n", "v\n"):
            cases.append(
                (
                    f"readto {target}\nouter;\ninner;\nx\ninner;\nouter;\nsend inner",
                    text,
                )
            )
    # Rewrite delimiters without reparsing, then execute both fixed blocks.
    for old, new in (("a", "b"), ("inner", "outer"), ("x", "y")):
        cases.append(
            (
                f"inject store={old};/{new};\nstore;\n{old};\npayload\n"
                f"{old};\nstore;\nsend {old}\nskip",
                "",
            )
        )
    return cases
