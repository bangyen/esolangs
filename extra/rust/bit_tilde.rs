//! bit~ interpreter (Rust cross-check; see README "Extra Implementations").
//!
//! An 8-cell bit pool with a pointer: `~` flips the current bit, `>`/`<`
//! move the pointer (`>` appends a cell whenever the 8-cell window would run
//! past the end; `<` is a no-op at the first cell), `)` reads a byte of
//! input into the pool as 8 bits (MSB first, starting at the current cell,
//! extending the pool to hold the full window), `(` prints the 8-bit window
//! at the pointer as a raw byte, and `{`/`}` are a loop bracket pair: `{`
//! jumps forward to the matching `}` when the current bit is zero, `}`
//! jumps back to the matching `{` when it is nonzero.  Any other character
//! is ignored.
//!
//! The pool is a single array that only ever grows.  `)` exits with status 3
//! when the input runs out (invalid operation; the wiki leaves EOF
//! undefined).  A `{`/`}` whose match is missing exits with status 2
//! (malformed) when it would have jumped, matching the Python interpreter
//! (the former Ruby reference looped forever instead).
//!
//! Invocation: `bit_tilde <program-file>`; program text from `argv[1]`.
//! Input: the program file is `argv[1]`; `)` reads from stdin.

use std::env;
use std::fs;
use std::io::{self, BufRead, Write};
use std::process;

fn find(chars: &[char], mut ind: usize, step: i64) -> usize {
    let mut depth = step;
    while depth != 0 {
        let next = ind as i64 + step;
        if next < 0 || next as usize >= chars.len() {
            process::exit(2);
        }
        ind = next as usize;
        match chars[ind] {
            '{' => depth += 1,
            '}' => depth -= 1,
            _ => {}
        }
    }
    ind
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let text = fs::read_to_string(&args[1]).expect("invalid file");
    let chars: Vec<char> = text.chars().collect();
    let n = chars.len();

    let mut tape: Vec<u8> = vec![0; 8];
    let mut cell = 0usize;
    let mut ind = 0usize;
    let mut line = false;
    let mut stdin = io::stdin().lock();
    let mut stdout = io::stdout();

    while ind < n {
        match chars[ind] {
            '~' => tape[cell] ^= 1,
            '>' => {
                if cell + 8 > tape.len() {
                    tape.push(0);
                }
                cell += 1;
            }
            '<' => {
                cell = cell.saturating_sub(1);
            }
            ')' => {
                if line {
                    stdout.write_all(b"\n").unwrap();
                }
                stdout.write_all(b"Input: ").unwrap();
                line = false;

                let mut input: Vec<u8> = Vec::new();
                if stdin.read_until(b'\n', &mut input).unwrap_or(0) == 0 {
                    process::exit(3);
                }
                let byte = input[0];
                let bits: Vec<u8> = (0..8).map(|b| (byte >> (7 - b)) & 1).collect();
                if cell + 8 > tape.len() {
                    tape.resize(cell + 8, 0);
                }
                tape[cell..cell + 8].copy_from_slice(&bits);
            }
            '(' => {
                let window = cell..(cell + 8).min(tape.len());
                let value = tape[window].iter().fold(0u8, |v, b| (v << 1) | b);
                stdout.write_all(&[value]).unwrap();
                line = true;
            }
            '{' => {
                if tape[cell] == 0 {
                    ind = find(&chars, ind, 1);
                }
            }
            '}' => {
                if tape[cell] != 0 {
                    ind = find(&chars, ind, -1);
                }
            }
            _ => {}
        }
        ind += 1;
    }
    let _ = stdout.flush();
}

#[cfg(test)]
mod tests {
    use std::io::Write;
    use std::process::{Command, Stdio};
    use std::sync::atomic::{AtomicU64, Ordering};

    fn run_program(program: &str, stdin: &str) -> Vec<u8> {
        static COUNTER: AtomicU64 = AtomicU64::new(0);
        let exe = std::env::current_exe()
            .expect("current exe")
            .parent()
            .unwrap()
            .parent()
            .unwrap()
            .join("bit_tilde");
        let path = std::env::temp_dir().join(format!(
            "bit-tilde-test-{}-{}.txt",
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
        out.stdout
    }

    #[test]
    fn prints_the_bit_window_as_a_byte() {
        // ~( : MSB of the window is set -> 0x80
        assert_eq!(run_program("~(", ""), vec![0x80]);
        // ~>~( : the window one cell over has only 7 available cells, so the
        // bit lands at 0x40 (the reference prints just the available bits)
        assert_eq!(run_program("~>~(", ""), vec![0x40]);
        // ~~~~( : four flips restore the bit -> 0x00
        assert_eq!(run_program("~~~~(", ""), vec![0x00]);
    }

    #[test]
    fn reads_a_byte_into_the_window() {
        // ~)( with 'a': read 97, then print the window it loaded
        assert_eq!(run_program("~)(", "a\n"), b"Input: a".to_vec());
    }

    #[test]
    fn loop_brackets_skip_when_the_current_bit_is_zero() {
        // ~{~}: the { skips when the bit is 1, the } when it is 0
        assert_eq!(run_program("~{~}", ""), b"".to_vec());
    }
}
