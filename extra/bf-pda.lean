import system.io
open io

def file_name : string := "test.txt"
    -- name of the file containing the BF-PDA program
def limit : ℕ := 100
    -- max number of commands

def read_file : io string := do
    f ← fs.read_file file_name,
    return f^.to_string


def list.pop (l : list ℕ) := l.reverse.tail.reverse
def list.top (l : list ℕ) := l.reverse.head


def list.flip (l : list ℕ) :=
    l.pop ++ [(l.top + 1) % 2]


def find :
    string.iterator → string.iterator → char → bool
        → ℤ → ℕ → string.iterator
    | i j c b 0    n    :=
        if b then j else j.next.next
    | i j c b z    0    := i.next
    | i j c b z (n + 1) := do
        let x := if b then j.next else j.prev,
        let k := if c = '[' then z + 1
            else if c = ']' then z - 1
            else z,
        find i x x.curr b k n


def main :
    string.iterator → char → ℕ → list ℕ
        → string → io unit
    | i  c     0    l s := put_str s
    | i '@' (m + 1) l s :=
        main i.next i.next.curr m l.flip s
    | i '.' (m + 1) l s :=
        main i.next i.next.curr m l
        (s ++ (char.of_nat (48 + l.top)).to_string)
    | i '<' (m + 1) l s :=
        main i.next i.next.curr m (l ++ [0]) s
    | i '>' (m + 1) l s :=
        main i.next i.next.curr m l.pop s
    | i '[' (m + 1) l s := do
        let j := i.next,
        let x := if l.top = 0 then
            find i j j.curr tt 1 i.to_string.length
            else j,
        main x x.curr m l s
    | i ']' (m + 1) l s := do
        let j := i.prev,
        let x := if l.top = 1 then
            find i j j.curr ff (0 - 1) i.to_string.length
            else i.next,
        main x x.curr m l s
    | i  c  (m + 1) l s := do
        main i.next i.next.curr m l s


#eval do
    c ← read_file,
    let i := string.mk_iterator c,
    main i i.curr limit [] ""
