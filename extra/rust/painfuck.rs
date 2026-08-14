//! Painfuck interpreter (Rust cross-check; see README "Extra Implementations").
//!
//! The program file is *not* executed directly: its source text is first
//! translated through a fixed substitution.  Each source character that
//! appears in one of the two cycles `pevkjzwr` and `yuctsobqihald` is
//! replaced by the character `k` steps further along that cycle, where `k`
//! is the number of characters translated so far (a position-dependent
//! Caesar shift per cycle); characters in no cycle are dropped.
//!
//! The translated program runs over a tape of unbounded integers starting as
//! a single 0 cell.  `p`/`s` add 2/subtract 1 from the current cell,
//! `r`/`l` move the pointer two right/one left, `i`/`j` read a number/byte
//! from input, `o`/`u` print the cell as a decimal number/byte,
//! `a`/`b` open/close a while-nonzero loop, `k` squares, `z` zeroes, `h`
//! halves (truncating toward zero), `w`/`q` copy from the right/left
//! neighbor, `c` repeats the next command `7`^run-length times, `y` skips
//! the next command at random, `v` skips the next command when the cell is
//! nonzero, `d` resets the pointer, `t` repeats the previous command
//! `3`^run-length times, and `e` halts.
//!
//! Reads at exhausted input exit with status 3, an unmatched `b` exits with
//! status 3, and `i` parses the whole input line as an integer (exit 3 on a
//! bad or missing line).  `y` is nondeterministic (a random skip), so a
//! single run's output is not reproducible; the generators and differential
//! corpus avoid it.
//!
//! Invocation: `painfuck <program-file>`; program text from `argv[1]`.
//! Input: the program file is `argv[1]`; `i`/`j` read from stdin.

use std::env;
use std::fs;
use std::io::{self, BufRead, Write};
use std::process;

fn translate(code: &str) -> Vec<char> {
    let cycles = ["pevkjzwr", "yuctsobqihald"];
    let mut prog: Vec<char> = Vec::new();
    let mut k = 0usize;
    for ch in code.chars() {
        for cycle in cycles {
            if let Some(p) = cycle.find(ch) {
                let bytes = cycle.as_bytes();
                prog.push(bytes[(p + k) % bytes.len()] as char);
                k += 1;
                break;
            }
        }
    }
    prog
}

fn prompt(out: &mut bool) {
    let mut stdout = io::stdout();
    if *out {
        stdout.write_all(b"\n").unwrap();
    }
    stdout.write_all(b"Input: ").unwrap();
    stdout.flush().unwrap();
    *out = false;
}

fn read_line() -> Option<Vec<u8>> {
    let mut stdin = io::stdin().lock();
    let mut line: Vec<u8> = Vec::new();
    if stdin.read_until(b'\n', &mut line).unwrap_or(0) == 0 {
        return None;
    }
    Some(line)
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let text = fs::read_to_string(&args[1]).expect("invalid file");
    let prog = translate(&text);
    let n = prog.len();

    let mut tape: Vec<i64> = vec![0];
    let mut loop_stack: Vec<usize> = Vec::new();
    let mut ptr = 0usize;
    let mut ind = 0usize;
    let mut rep: i64 = 1;
    let mut out = false;
    let mut stdout = io::stdout();

    while ind < n {
        let mut c = prog[ind];
        ind += 1;

        while rep > 0 {
            rep -= 1;

            match c {
                'p' => tape[ptr] += 2,
                's' => tape[ptr] -= 1,
                'r' => {
                    ptr += 2;
                    while ptr >= tape.len() {
                        tape.push(0);
                    }
                }
                'l' => {
                    ptr = ptr.saturating_sub(1);
                }
                'i' => {
                    prompt(&mut out);
                    match read_line() {
                        Some(line) => {
                            let s = String::from_utf8(line).unwrap();
                            match s.trim().parse::<i64>() {
                                Ok(value) => tape[ptr] = value,
                                Err(_) => process::exit(3),
                            }
                        }
                        None => process::exit(3),
                    }
                }
                'j' => {
                    prompt(&mut out);
                    match read_line() {
                        Some(line) => {
                            if line.is_empty() {
                                process::exit(3);
                            }
                            tape[ptr] = line[0] as i64;
                            // the reference's discard-to-end-of-line loop
                            // leaves the command as '\n', so a repeated `j`
                            // reads once and then no-ops
                            c = '\n';
                        }
                        None => process::exit(3),
                    }
                }
                'o' => {
                    write!(stdout, "{}", tape[ptr]).unwrap();
                    out = true;
                }
                'u' => {
                    stdout.write_all(&[(tape[ptr] & 0xFF) as u8]).unwrap();
                    out = true;
                }
                'a' => {
                    if tape[ptr] != 0 {
                        loop_stack.push(ind - 1);
                    } else {
                        let mut val = 1;
                        while val != 0 && ind < n {
                            let ch = prog[ind];
                            ind += 1;
                            if ch == 'a' {
                                val += 1;
                            } else if ch == 'b' {
                                val -= 1;
                            }
                        }
                    }
                }
                'b' => match loop_stack.pop() {
                    Some(value) => ind = value,
                    None => process::exit(3),
                },
                'k' => tape[ptr] = tape[ptr] * tape[ptr],
                'z' => tape[ptr] = 0,
                'h' => tape[ptr] /= 2,
                'w' => {
                    tape[ptr] = if ptr + 1 < tape.len() {
                        tape[ptr + 1]
                    } else {
                        0
                    };
                }
                'q' => {
                    if ptr > 0 {
                        tape[ptr] = tape[ptr - 1];
                    }
                }
                'c' => {
                    rep = 1;
                    while c == 'c' {
                        c = if ind < n { prog[ind] } else { '\0' };
                        ind += 1;
                        rep *= 7;
                    }
                }
                'y' => {
                    if rand::random::<bool>() && ind < n {
                        c = prog[ind];
                        ind += 1;
                    }
                }
                'e' => process::exit(0),
                'v' => {
                    if tape[ptr] != 0 && ind < n {
                        c = prog[ind];
                        ind += 1;
                    }
                }
                'd' => ptr = 0,
                't' => {
                    let val = ind;
                    rep = 1;
                    let mut found = false;
                    while ind > 0 {
                        ind -= 1;
                        if prog[ind] != 't' {
                            found = true;
                            break;
                        }
                        rep *= 3;
                    }
                    c = if found { prog[ind] } else { '\0' };
                    ind = val;
                }
                _ => {}
            }
        }

        rep += 1;
    }
}

#[cfg(test)]
mod tests {
    use std::io::Write;
    use std::process::{Command, Stdio};
    use std::sync::atomic::{AtomicU64, Ordering};

    fn encode(targets: &str) -> String {
        let cycles = ["pevkjzwr", "yuctsobqihald"];
        let mut out = String::new();
        let mut k = 0usize;
        for tc in targets.chars() {
            for cycle in cycles {
                if let Some(p) = cycle.find(tc) {
                    let bytes = cycle.as_bytes();
                    out.push(bytes[(p + bytes.len() - k % bytes.len()) % bytes.len()] as char);
                    k += 1;
                    break;
                }
            }
        }
        out
    }

    fn run_program(program: &str, stdin: &str) -> (Vec<u8>, i32) {
        static COUNTER: AtomicU64 = AtomicU64::new(0);
        let exe = std::env::current_exe()
            .expect("current exe")
            .parent()
            .unwrap()
            .parent()
            .unwrap()
            .join("painfuck");
        let path = std::env::temp_dir().join(format!(
            "painfuck-test-{}-{}.txt",
            std::process::id(),
            COUNTER.fetch_add(1, Ordering::SeqCst)
        ));
        std::fs::write(&path, program).expect("write program");
        let mut child = Command::new(&exe)
            .arg(&path)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .spawn()
            .expect("failed to spawn");
        child
            .stdin
            .take()
            .unwrap()
            .write_all(stdin.as_bytes())
            .unwrap();
        let out = child.wait_with_output().unwrap();
        std::fs::remove_file(&path).ok();
        (out.stdout, out.status.code().unwrap_or(-1))
    }

    #[test]
    fn translation_is_the_caesar_shift() {
        use super::translate;
        assert_eq!(translate("p"), vec!['p']);
        // 'e' is one step along the first cycle from 'p'
        assert_eq!(translate("pe"), vec!['p', 'v']);
    }

    #[test]
    fn arithmetic_and_byte_print() {
        // p u e : cell 2, print it as a byte, halt
        assert_eq!(run_program(&encode("pue"), ""), (vec![2], 0));
        // p p u e : cell 4
        assert_eq!(run_program(&encode("ppue"), ""), (vec![4], 0));
        // s u e : cell -1, printed as its low byte
        assert_eq!(run_program(&encode("sue"), ""), (vec![0xFF], 0));
    }

    #[test]
    fn square_halve_and_neighbor_copy() {
        // p k u e : square 2 -> 4
        assert_eq!(run_program(&encode("pkue"), ""), (vec![4], 0));
        // p p h u e : 4 halved -> 2
        assert_eq!(run_program(&encode("pphue"), ""), (vec![2], 0));
        // p p w o : w reads the (zero) right neighbor, o prints 0
        assert_eq!(run_program(&encode("ppwo"), ""), (b"0".to_vec(), 0));
    }

    #[test]
    fn reads_a_byte() {
        // p j o : read '5' (53), print it in decimal
        assert_eq!(
            run_program(&encode("pjo"), "5\n"),
            (b"Input: 53".to_vec(), 0)
        );
    }
}
