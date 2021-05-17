import system.io
open io

def file_name : string := "test.txt"
    -- name of the file containing the BF-PDA program
def limit : ℕ := 100
    -- max number of commands

def read_file : io string := do
    f ← fs.read_file file_name,
    return f^.to_string


def main :
    string.iterator → char → bool
        → ℕ → string → io unit
    | i  c  b     0    s := put_str s
    | i  c  ff (n + 1) s :=
        if s.front = 'H' then put_str s
        else do
            let x := i.to_string.mk_iterator,
            main x x.curr tt n s
    | i '0' b  (n + 1) s :=
        main i.next i.next.curr i.has_next n ("0" ++ s)
    | i '1' b  (n + 1) s :=
        main i.next i.next.curr i.has_next n ("1" ++ s) 
    | i 'H' b  (n + 1) s := do
        let x := if s.front = '0' then "H" else "",
        main i.next i.next.curr i.has_next n (x ++ s)
    | i  c  b  (n + 1) s :=
        main i.next i.next.curr i.has_next n s


#eval do
    c ← read_file,
    let i := string.mk_iterator c,
    main i i.curr tt limit ""
