import itertools


def finite_cases():
    commands = [
        "ADD 3",
        "SUB -2",
        "PSH INT -9",
        'PSH STR "INT"',
        'PSH STR "a[]λ"',
        "PSH VAR1",
        "PSH VAR9",
        "PSH FOO",
        "POP",
        "SWP",
        "DUP",
        "PRT",
        "PRT INT",
        "PRT STR",
        "PRT VAR1 INT",
        "PRT VAR1 STR",
        "PRT VAR9",
        "END",
        "RST",
        "JMP F 2",
        "JMP B 2",
        "JMP F -1",
        "JMP B -2",
        "JMP F 2 IF 0",
        "JMP B 1 NIF 1",
        "RND 1",
        "RND 3",
        "RND 0",
        "VAR1+3",
        "VAR2--2",
        "VAR3+-2",
        "VAR4++2",
        "VAR1-+2",
        "VAR9-1",
        "",
        "INP INT",
        "INP STR",
        "TYPO",
    ]
    cases = []
    for stack, command, draw in itertools.product(
        [(), (0,), (1,), (-1,), (65, 66), (0, 1, -2)], commands, [0, 2]
    ):
        source = "".join(f"[PSH INT {value}]" for value in stack) + f"[{command}][END]"
        cases.append((source, "7\nλ", 20, draw))
    for source, text in [
        ("[INP INT][PRT INT][INP STR][PRT STR]", "12 rest\n"),
        ("[INP STR][PRT][PRT]", "A\n"),
        ("[INP INT]", "bad"),
        ("[INP INT]", "   "),
        ("[INP STR]", ""),
        ('[PSH STR "INT"][PRT][PRT][PRT]', ""),
        ('[PSH STR "A" ][PRT]', ""),
        ('[PSH STR "[]"\n][PRT][PRT]', ""),
    ]:
        cases.append((source, text, 100, 0))
    return cases
