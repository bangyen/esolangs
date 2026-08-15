//! %^2^-1 interpreter (Rust cross-check; see README "Extra Implementations").
//!
//! A single accumulator always of the form 10^x (x is the "magnitude"):
//! `s`/`i` subtract 2/3 from the magnitude (divide by 100/1000), `m` doubles
//! it (square), `p` negates it (reciprocate), `'` zeroes it (set to 1),
//! `l`/`e` print it (decimal / as a byte), `n` reads one byte of input, and
//! `t` rewinds to the start of the program when the magnitude is nonzero.
//! The magnitude is reset to zero whenever it exceeds 3003 (before each
//! command).
//!
//! The accumulator is stored as its magnitude (the exponent x) rather than as
//! the 10^x value, which is the workaround the wiki suggests for avoiding
//! huge numbers; the command semantics match the wiki exactly.  `e` prints
//! the low byte as a raw byte (values above 127 are written as single
//! bytes), `l` prints the signed magnitude, `n` exits with status 3 when the
//! input runs out (the cross-check convention; the Python interpreter raises
//! `EOFError` instead), and `t` on a nonzero magnitude loops the program
//! forever (the only loop).
//!
//! Invocation: `pct <program-file>`; program text from `argv[1]`.
//! Input: the program file is `argv[1]`; `n` reads from stdin.

use std::env;
use std::fs;
use std::io::{self, Read, Write};
use std::process;

fn main() {
    let args: Vec<String> = env::args().collect();
    let text = fs::read_to_string(&args[1]).expect("invalid file");
    let chars: Vec<char> = text.chars().collect();
    let n = chars.len();

    let mut acc: i64 = 0;
    let mut out = false;
    let mut ind = 0usize;
    let mut stdin = io::stdin().lock();
    let mut stdout = io::stdout();

    while ind < n {
        if acc > 3003 {
            acc = 0;
        }
        match chars[ind] {
            's' => acc -= 2,
            'i' => acc -= 3,
            'm' => acc *= 2,
            'p' => acc *= -1,
            'l' => {
                write!(stdout, "{}", acc).unwrap();
                out = true;
            }
            'e' => {
                stdout.write_all(&[(acc & 0xFF) as u8]).unwrap();
                out = true;
            }
            'n' => {
                if out {
                    stdout.write_all(b"\n").unwrap();
                }
                stdout.write_all(b"Input: ").unwrap();
                out = false;

                let mut byte = [0u8; 1];
                if stdin.read(&mut byte).unwrap_or(0) == 0 {
                    process::exit(3);
                }
                acc = byte[0] as i64;
                let mut rest = [0u8; 1];
                while stdin.read(&mut rest).unwrap_or(0) > 0 && rest[0] != b'\n' {}
            }
            '\'' => acc = 0,
            't' => {
                if acc != 0 {
                    ind = 0;
                    continue;
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
            .join("pct");
        let path = std::env::temp_dir().join(format!(
            "pct-test-{}-{}.txt",
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
    fn prints_bytes_as_raw_bytes() {
        // 'ipe: reset, -3, +3 -> byte 3
        assert_eq!(run_program("'ipe", ""), vec![3]);
        // 'mse: 0, 0, -2 -> low byte 0xFE
        assert_eq!(run_program("'mse", ""), vec![0xFE]);
        // 'me'l: byte 0 then the magnitude "0"
        assert_eq!(run_program("'me'l", ""), vec![0x00, b'0']);
    }

    #[test]
    fn prints_the_signed_magnitude() {
        assert_eq!(run_program("'l", ""), b"0".to_vec());
        assert_eq!(run_program("'sl", ""), b"-2".to_vec());
    }

    #[test]
    fn reads_a_byte_and_drains_the_line() {
        // ne: read 'X', print it as a byte (prompt precedes the read)
        assert_eq!(run_program("ne", "X\n"), b"Input: X".to_vec());
        // nl: read 'A', print its value
        assert_eq!(run_program("nl", "A\n"), b"Input: 65".to_vec());
    }

    #[test]
    fn t_rewinds_until_a_zero_byte_is_read() {
        // nt: read 'A' (rewind), read 0x00 (stop); two prompts, no output
        assert_eq!(run_program("nt", "A\n\x00\n"), b"Input: Input: ".to_vec());
    }
}
