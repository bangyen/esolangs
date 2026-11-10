"""The old27 prefixes and five existing literal/lifecycle witnesses."""

from .full_oracle import _OPS

HELLO = (
    "(=<`#9]~6ZY327Uv4-QsqpMn&+Ij\"'E%e{Ab~w=_:]Kw%o44Uqp0/"
    "Q?xNvL:`H%c#DD2^WV>gY;dts76qKJImZkj"
)
CAT = '(=BA#9"=<;:3y7x54-21q/p-,+*)"!h%B0/.\n~P<\n<:(8&\n66#"!~}|{zyxwvu\ngJ%'


def cases():
    corpus = [chr((op - 33) % 94 + 33) + "P" for op in _OPS]
    for code in [*corpus, HELLO, CAT, " ", "?", "é"]:
        for stdin in ("", "Hi!"):
            yield code, stdin, 128
    yield "ubO", "Ā", 128
    for stdin in ("", "A", "Z"):
        yield "ubO", stdin, 128
    yield "Q", "", 128
    yield "", "", 128
