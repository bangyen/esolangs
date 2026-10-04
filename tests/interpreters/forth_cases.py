import itertools


def finite_cases():
    cases = []

    for prefix in ("", "0", "1", "12", "123", "F0~"):
        for size in range(3):
            for suffix in itertools.product(":~+-*/%voc.", repeat=size):
                cases.append((prefix + "".join(suffix), ""))
    for bit in range(16):
        for body in ("5.", "0/", "12c", "1(2.)", "0[.]", "2{A.}2;", "X3."):
            cases.extend(
                ((f"{bit:X}({body})F.", ""), (f"{bit:X}{{{body}}}{bit:X};F.", ""))
            )
    for n in range(9):
        cases.append((f"{n:X}[:1-]A.", ""))
    for text in ("0\n1\n", "Ā\n", "\n", "abc\n"):
        cases.extend((program, text) for program in (",", ",o", ",.", ",,..", ",0o[.]"))
    cases.extend(
        [
            ("65.", ""),
            ("A.", ""),
            ("5:..", ""),
            ("23+.", ""),
            ("95-.", ""),
            ("28*.", ""),
            ("84/.", ""),
            ("85%.", ""),
            ("0~.", ""),
            ("09/~.", ""),
            ("65v..", ""),
            ("123o...", ""),
            ("123c...", ""),
            ("1(F4*5+.)", ""),
            ("0(F4*5+.)", ""),
            ("0F7*0+F4*C+[.]", ""),
            ("0[[.]]", ""),
            ("1{65.}1;", ""),
            ("1{F4*5+.}1;", ""),
            (",..", "hi"),
            (",68*-.", "0"),
            (",.", "Ā"),
            ("F1+:*.", ""),
            ("a5.", ""),
            ("65a.", ""),
            ("0G.", ""),
            ("X5.", ""),
            ("1;", ""),
            ("1(5:).", ""),
            ("1((5.))", ""),
            ("1{3[:1-]A.}1;", ""),
            ("1{/}1;", ""),
            ("9:*:*:*:*", ""),
            ("2:*:*:*:*88*8*8*8**", ""),
            ("1;", ""),
            ("3[:1-]", ""),
            ("65.", ""),
            ("1{/}1;", ""),
            (",", "hi"),
        ]
    )
    for text in (
        "\r\n",
        "a\r\nb\n",
        "a\rb",
        "a\u0085b",
        "a\u2028b",
        "a\v\fb",
        "\n\n",
        "Ā\r\n",
    ):
        cases.extend((source, text) for source in (",", ",.", ",o", ",0o[.]", ",,"))
    return list(dict.fromkeys(cases))
