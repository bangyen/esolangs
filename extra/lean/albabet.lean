import system.io
open io

def file_name : string := "test.txt"


def read_file : io string := do
    f ← fs.read_file file_name,
    return f^.to_string


def main :
    ℕ → string.iterator → char
        → ℕ → ℕ → string
        → io unit
    |    0    i  c  x y s := put_str s
    | (n + 1) i 'a' x y s :=
        main n i.next i.next.curr (x + 1) y s
    | (n + 1) i 'b' x y s :=
        main n i.next i.next.curr (x - 1) y s
    | (n + 1) i 'c' x y s :=
        main n i.next i.next.curr 0 y s
    | (n + 1) i 'd' x y s :=
        main n i.next i.next.curr 0 x s
    | (n + 1) i 'e' x y s :=
        main n i.next i.next.curr x x s
    | (n + 1) i 'f' x y s :=
        main n i.next i.next.curr x 0 s
    | (n + 1) i 'g' x y s :=
        main n i.next i.next.curr (x * y) y s
    | (n + 1) i 'h' x y s :=
        main n i.next i.next.curr (x * x) y s
    | (n + 1) i 'i' x y s :=
        main n i.next i.next.curr x y
        (s ++ to_string (char.of_nat x))
    | (n + 1) i  c  x y s :=
        main n i.next i.next.curr x y s


#eval do
    c ← read_file,
    let i := string.mk_iterator c,
    main (string.length c) i i.curr 0 0 ""
