"""All192 legacy operator inputs plus explicit continuation/parser/IO cases."""

from dataclasses import dataclass
from itertools import product
from operator import and_, or_, xor


@dataclass(frozen=True)
class Case:
    source: str
    stdin: str = "0\n"
    cap: int = 64
    legacy_answer: int | None = None
    name: str = ""


def cases():
    result = []
    for left, right, (symbol, calculate) in product(
        range(8), range(8), (("&", and_), ("|", or_), ("^", xor))
    ):
        writes = [
            f"% {index:b} {symbol} {left >> index & 1} {right >> index & 1}"
            for index in (2, 0, 1)
        ]
        preset = [f"% {index:b} | 1 0" for index in range(3)]
        result.append(
            Case(
                "\n".join([*preset, *writes, "$"]), legacy_answer=calculate(left, right)
            )
        )
    assert len(result) == 192
    for name, source, stdin in (
        ("low-bit-clear", "% 0 1\n% 0 10\n$", "0"),
        ("nested-zero-return", "% 0 | 0 % 1 1\n$", "0"),
        ("print-zero-return", "% 1 1\n% 0 < $\n$", "0"),
        (
            "shift-left-positive",
            "% 0 [?] +[] +[] +[] +[] [] 0 [] 0 [] 1 [] 0 [] 0 > 1\n$",
            "0",
        ),
        (
            "shift-right-positive",
            "% 0 [?] +[] +[] +[] +[] [] 0 [] 0 [] 1 [] 0 [] 0 < 100\n$",
            "0",
        ),
        ("partial-args", "% 0 | 1 0\n$", "7"),
        ("nested-binds", "g x | x 0\nf y g y\n% 0 f 1\n$", "7"),
        ("callee-return", "g | 1 0\n% 0 : 1 g\n$", "0"),
        ("lazy-false", "again again\n: 0 again\n$", "0"),
        ("lazy-true", "again again\n: 1 again", "0"),
        ("callable-array", "f :g [?] [] :g 0\nf :$\n$", "0"),
        ("return-type-rollback", "arr [] 1\n$\n% 0 arr", "0"),
        ("return-arity-rollback", "make [?] [] :& 0\napply c | c 0\napply make", "0"),
        ("late-incomplete", "$\n% 0", "0"),
        ("validate-before-input", "f 101", "unread"),
        ("empty-token", "$", "  "),
        ("large-invalid-number", "$", "9" * 5000),
        ("numeric-raw-body", "% 0 : 1 1\n$", "0"),
        ("zero-builtin-body", "% 0 1\n: 1 $", "0"),
        ("zero-body-not-run", "% 0 1\n: 0 $", "0"),
        ("dynamic-callable", "id x | x 0\napply :g y g y\n% 0 apply :id 1\n$", "0"),
        ("dynamic-bad-arity", "apply :g y g y\napply :& 1", "0"),
        ("raw-solo", "f :x x\nf :$\n$", "0"),
        ("raw-solo-value", "f :x x\nf 1\n$", "0"),
        ("raw-solo-bad-arity", "f :x x\nf :&", "0"),
        ("bound-zero-callable", "use c | c 0\nsetter % 0 1\nuse :setter\n$", "0"),
        ("bound-plain-call", "apply c : 1 c\napply 1\n$", "0"),
        ("three-args-ordered", "mix a b c | a | b c\n% 0 mix 1 0 1\n$", "0"),
        (
            "forward-arity",
            "f x | g x 0\ng y | y 0\n% 0 f 1\n$",
            "0",
        ),
        ("recursive-arity", "loop n | n loop n\nloop 1", "0"),
        ("invalid-self-arity", "f n f\n$", "unread"),
        ("raw-array-lazy-refusal", "f x : 0 x\nf [] 1", "0"),
        ("array-parameter", "first x [?] x 0\n% 0 first [] 1\n$", "0"),
        ("array-nesting", "[] [] [] 1\n$", "0"),
        ("array-join-order", "% 0 [?] +[] [] 1 [] 0 0\n$", "0"),
        ("array-index-failure", "% 0 [?] [] 1 1", "0"),
        ("array-shift-failure", "% 0 < [] 1", "0"),
        ("number-concat-failure", "% 0 +[] 1 1", "0"),
        ("lazy-arity-positive", ": 0 <", "0"),
        (
            "array-returned-callable",
            "apply c : 1 c\ng % 0 1\napply [?] [] :g 0\n$",
            "0",
        ),
        ("conditional-arg-body", "% 0 : 1 <\n$", "0"),
        ("undefined-body-lazy", ": 0 nowhere", "0"),
        ("undefined-token", "% 0 nowhere 1", "0"),
        ("multiple-top-calls", "% 0 1\n$ $", "0"),
        ("top-literal", "101", "0"),
        ("top-raw", "s $\n:s", "0"),
        ("trailing-colon-name", "f: x | x 0\n% 0 f: 1\n$", "0"),
        ("nonbinary-name", "2 x | x 0\n% 0 2 1\n$", "0"),
        ("comments", "# first\n\u200b% 0 1 # last\n$", "0"),
        ("discard-effect-on-pure-failure", "% [] 0 $", "0"),
        ("invalid-empty-definition", "f", "unread"),
        ("invalid-value-definition", "f x x\n$", "unread"),
        ("invalid-raw-definition", "f :x :x\n$", "unread"),
        ("invalid-short-definition", "f x & x\n$", "unread"),
        ("invalid-two-calls", "g x | x 0\nf y g y g y", "unread"),
        ("unused-undefined-body", "f x & x nowhere\n$", "0"),
        ("shadowed-redefinition-call", "f | 1 0\nf | 0 0\n$", "0"),
        ("empty-program-reads", "", "3 trailing"),
    ):
        result.append(Case(source, stdin, name=name))
    for stdin in (
        "",
        " \t",
        "banana rest",
        "-3 rest",
        "+7 rest",
        "\u0661_\u0660 rest",
        "1_0 rest",
        "1" * 5000 + " rest",
        "\ud800\udfff rest",
    ):
        result.append(Case("% 0 @ 0\n$", stdin, name="constructor-token"))  # noqa: PERF401 -- Exact legacy case order.
    result.append(
        Case(
            "$\n% 100111000100000 1\n% 100111000100000 $\n$",
            "0",
            name="postcommit-decimal-limit",
        )
    )
    result.append(Case("[?] [] 1 " + "1" * 20000, "0", name="pure-diagnostic-limit"))
    result.append(Case("1" * 20000, "0", name="cycle-render-limit"))
    canonical = "a @ 0\nb @ 1\n% 0 & b a\n$\n\n"
    for number in range(4):
        result.append(Case(canonical, str(number), name="canonical-spec"))  # noqa: PERF401 -- Exact legacy case order.
    return result
