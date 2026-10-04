"""Published Alight examples and a command ring."""

CAT_TURN = [
    "                              d",
    "                              n",
    "                              e",
    "begin;var c;inp c;turn c = eof;",
    "           t                  t",
    "           h                  u",
    "           g                  r",
    "           i                  n",
    "           r                   ",
    "                              r",
    "           n                  i",
    "           r                  g",
    "           u                  h",
    "           t                  t",
    "           ;thgir nrut;;;c tuo;",
]

CAT_SKIP = [
    "begin;var c;inp c;skip c = eof;turn right;end",
    "           t                             t",
    "           h                             u",
    "           g                             r",
    "           i                             n",
    "           r                              ",
    "                                         r",
    "           n                             i",
    "           r                             g",
    "           u                             h",
    "           t                             t",
    "           ;thgir nrut;;;;;;;;;;;;;;c tuo;",
]

REVERSED_CAT = [
    (
        "begin;var c;var l;set l [];inp c;;;;;;;;;;;;;;;;;;;skip c = eof;tu"
        "rn right;var x;set x len{l}-0.5;;;;;;;;;;;skip sign{x} > 0;end;tur"
        "n right;"
    ),
    (
        "                          t                                       "
        "        t                      t                                  "
        "       t"
    ),
    (
        "                          h                                       "
        "        u                      h                                  "
        "       u"
    ),
    (
        "                          g                                       "
        "        r                      g                                  "
        "       r"
    ),
    (
        "                          i                                       "
        "        n                      i                                  "
        "       n"
    ),
    (
        "                          r                                       "
        "                               r                                  "
        "        "
    ),
    (
        "                                                                  "
        "        r                                                         "
        "       r"
    ),
    (
        "                          n                                       "
        "        i                      n                                  "
        "       i"
    ),
    (
        "                          r                                       "
        "        g                      r                                  "
        "       g"
    ),
    (
        "                          u                                       "
        "        h                      u                                  "
        "       h"
    ),
    (
        "                          t                                       "
        "        t                      t                                  "
        "       t"
    ),
    (
        "                          ;thgir nrut;}c ,5.0-}l{nel ,l{ta;}1 ,l{n"
        "el l tes;                      ;thgir nrut;1-x x tes;c tuo;}x ,l{t"
        "a c tes;"
    ),
]

LOOP = [
    "begin;turn right;",
    "     t          t",
    "     h          u",
    "     g          r",
    "     i          n",
    "     r",
    "                r",
    "     n          i",
    "     r          g",
    "     u          h",
    "     t          t",
    "     ;thgir nrut;",
]
