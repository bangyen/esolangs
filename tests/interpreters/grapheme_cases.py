import itertools


def finite_cases():
    values = ["FZF", "FAF", "FBF", "EE", "EAE", "EABE", "HH", "HTH"]
    cases = []
    for count in range(3):
        for prefix in itertools.product(values, repeat=count):
            for op in "ABCDIJKL MNOPQRSTUVXY".replace(" ", ""):
                cases.append(("".join(prefix) + op, ""))
    for source in [
        "E",
        "F",
        "H",
        "EABC",
        "FABC",
        "HABC",
        "EHELLOWORLDEY",
        "EAEGI",
        "HTHI",
        "FZFT",
        "FAFXTY",
        "FZFXTY",
        "FAFUY",
        "FZFUY",
        "EAEHMYHZ",
        "FAFFZFBN",
    ]:
        cases.append((source, ""))
    for text in ["", "0\n", "Ā\n", "\n", "a\r\nb", "a\u2028b"]:
        for source in ["W", "WY", "WJ", "WKY", "WNY", "WM"]:
            cases.append((source, text))
    cases.extend(
        [
            ("EHLLOWORLDEY", ""),
            ("EAY", ""),
            ("FAFFBFAY", ""),
            ("FFY", ""),
            ("FAFHYHIE", ""),
            ("HEABHIY", ""),
            ("HFABHIY", ""),
            ("EHABEGNY", ""),
            ("FAFFBFBY", ""),
            ("FAFFBFSY", ""),
            ("FCFFBFRY", ""),
            ("EAEEAEAY", ""),
            ("FAFKYY", ""),
            ("FAFFBFLYY", ""),
            ("EABEECDEPYY", ""),
            ("EAEM", ""),
            ("FAFTY", ""),
            ("FFTY", ""),
            ("EAEOY", ""),
            ("FAFNY", ""),
            ("EAJEJY", ""),
            ("HABHNY", ""),
            ("EAEKKCDY", ""),
            ("FAFEYEG", ""),
            ("FAFHYHIE", ""),
            ("FAFHYHZ", ""),
            ("FAFKHYHZ", ""),
            ("FAFHYHQ", ""),
            ("FAFKKQY", ""),
            ("FAFKKVY", ""),
            ("FAFKZY", ""),
            ("FAFFFUKY", ""),
            ("FFFAFUKY", ""),
            ("FAFFFXKY", ""),
            ("FFFAFXYK", ""),
            ("FAFFFUY", ""),
            ("FBFFAFUY", ""),
            ("FAFFBFFCFXYKY", ""),
            ("FAFFBFHXYKHI", ""),
            ("WKY", "hi"),
            ("FAFJJY", ""),
            ("HABHJY", ""),
            ("EFAEJY", ""),
            ("EAENY", ""),
            ("FFNY", ""),
            ("EAETY", ""),
            ("EETY", ""),
            ("HABHTY", ""),
            ("HHTY", ""),
            ("FAFIY", ""),
            ("FFFFVY", ""),
            ("F", ""),
            ("H", ""),
            ("FBFFFTFFVMY", ""),
            ("FAFFBFFCFFDFHKMMYHZ", ""),
            ("FAFFBFHYHI", ""),
            ("FAFY", ""),
            ("W", "hi"),
        ]
    )
    for key in ("HH", "HTH", "HABH"):
        for value in values:
            cases.extend(
                (
                    (value + key + "C" + key + "D", ""),
                    (value + key + "CFAF" + key + "C" + key + "DY", ""),
                )
            )
        cases.append((key + "D", ""))
    return list(dict.fromkeys(cases))
