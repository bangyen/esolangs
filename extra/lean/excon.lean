import system.io
open io

def file_name : string := "test.txt"
    -- name of the file containing the EXCON program


def read_file : io string := do
    f ← fs.read_file file_name,
    return f^.to_string


def empty_list := list.repeat 0 8


def gets : list ℕ → ℕ → ℕ :=
    λ l n, option.get_or_else (list.nth l n) 0


def flips : list ℕ → ℕ → list ℕ :=
    λ l n, list.update_nth l n (((gets l n) + 1) % 2)


def to_s : list ℕ → ℕ → ℕ → string
    | l    0    m := to_string (char.of_nat m)
    | l (n + 1) m :=
        to_s l n (m + (pow 2 (6 - n)) * (gets l (n + 1)))


def main :
    ℕ → string.iterator → char
        → list ℕ → ℕ → string
        → io unit
    |    0    i  c  l n s := put_str s
    | (m + 1) i ':' l n s :=
        main m i.next i.next.curr empty_list 7 s
    | (m + 1) i '^' l n s :=
        main m i.next i.next.curr (flips l n) n s
    | (m + 1) i '!' l n s :=
        main m i.next i.next.curr l n (s ++ to_s l 7 0)
    | (m + 1) i '<' l n s :=
        main m i.next i.next.curr l ((n - 1) % 8) s
    | (m + 1) i  c  l n s :=
        main m i.next i.next.curr l n s


#eval do
    c ← read_file,
    let i := string.mk_iterator c,
    main (string.length c) i i.curr empty_list 7 ""
