import itertools


def finite_cases():
    cases = []
    for value in (0, 1, 2, 3, 4, 9, 10, 42, 77, 255, 999, 1000, 3999):
        for op in "&V?":
            for expression in (f"'{op}#{value}'", f"#{op}{value}"):
                # Keep output inside the interpreter's declared ordinary Roman range.
                cases.append((f"PLEASE .1 <- {expression}\nDO GIVE UP\nDO GIVE UP", ""))
        cases.append((f"PLEASE READ OUT #{value}\nDO GIVE UP\nDO GIVE UP", ""))
    for a, b in itertools.product((0, 1, 2, 3, 77, 255, 32768, 65535), repeat=2):
        for op in "$~":
            cases.append((f"PLEASE .1 <- '#{a}{op}#{b}'\nDO GIVE UP\nDO GIVE UP", ""))
    for text in (
        "ZERO\n",
        "OH\n",
        "ONE\n",
        "four two\n",
        "NINER\n",
        "SIX FIVE FIVE THREE FIVE\n",
        "SIX FIVE FIVE THREE SIX\n",
        "\n",
        "TEN\n",
        "ONE\r\n",
        "",
    ):
        cases.append(("PLEASE WRITE IN .1\nDO GIVE UP\nDO GIVE UP", text))
    for count in (0, 1, 2, 3, 65535):
        for op in ("FORGET", "RESUME"):
            cases.append(
                (
                    "PLEASE DO (10) NEXT\nDO GIVE UP\nDO GIVE UP\n"
                    f"(10) DO {op} #{count}",
                    "",
                )
            )
    for command in (
        "FORGET #0",
        "WRITE IN .0",
        "WRITE IN .65536",
        "(99) NEXT",
        ".0 <- #1",
        ".65536 <- #1",
    ):
        cases.append((f"PLEASE {command}\nDO GIVE UP\nDO GIVE UP", "ONE\n"))
    cases += [
        ("(1) PLEASE (1) NEXT\nDO GIVE UP\nDO GIVE UP", ""),
        ("PLEASE .1 <- #1\nDO NOT .1 <- #2\nDO READ OUT .1", ""),
        ("PLEASE .1 <- #1\nDON'T .1 <- #2\nDO READ OUT .1", ""),
    ]
    cases += [
        (f"PLEASE READ OUT {operand}\nDO GIVE UP\nDO GIVE UP", "")
        for operand in ("#4000", "#65535", "'#65535$#65535'", "'#0$#32768'")
    ]
    cases.append(
        (
            "PLEASE DO (10) NEXT\nDO READ OUT #1\nDO GIVE UP\n"
            "(10) DO (20) NEXT\nDO READ OUT #2\nPLEASE GIVE UP\n"
            "(20) DO RESUME #2",
            "",
        )
    )
    select = '\'"#0$#1"~"#0$#1"\''
    cases.append(
        ("PLEASE READ OUT " + '"?' + select + '"' + "\nDO GIVE UP\nDO GIVE UP", "")
    )
    return cases
