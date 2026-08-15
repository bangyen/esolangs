//! Trash interpreter (Rust cross-check; see README "Extra Implementations").
//!
//! The program is a number: the leading `t` characters count how many prime
//! steps to take, and the remaining characters hold the starting value.  If
//! the starting value is prime, the program prints the value advanced by that
//! many primes; otherwise it prints 0.  A program with no digits is malformed
//! (status 1, the reference's EXIT_FAILURE).
//!
//! Matches the C++ reference except that 2 is treated as prime: only `t`
//! characters before the first digit contribute to the step count and other
//! characters there are ignored; only the leading digits after the first
//! digit form the starting value, so trailing characters do not affect the
//! result; and the primality test is trial division up to the square root.
//!
//! Invocation: `trash <program-file>`; program text from `argv[1]`.
//! Input: the program file is `argv[1]`; the language has no input command.

use std::env;
use std::fs;
use std::process;

fn is_prime(n: i64) -> bool {
    if n < 2 {
        return false;
    }
    let root = (n as f64).sqrt() as i64;
    let mut k = 2;
    while k <= root {
        if n % k == 0 {
            return false;
        }
        k += 1;
    }
    true
}

fn run(text: Vec<char>) -> i32 {
    let mut num = 0;
    let mut digit_pos = None;
    for (idx, &c) in text.iter().enumerate() {
        if c == 't' {
            num += 1;
        } else if c.is_ascii_digit() {
            digit_pos = Some(idx);
            break;
        }
    }
    let digits: String = match digit_pos {
        Some(pos) => text[pos..]
            .iter()
            .take_while(|c| c.is_ascii_digit())
            .collect(),
        None => return 1,
    };
    let val: i64 = match digits.parse() {
        Ok(value) => value,
        Err(_) => return 1,
    };
    if num > 0 {
        if is_prime(val) {
            let mut v = val;
            for _ in 0..num {
                v += 1;
                while !is_prime(v) {
                    v += 1;
                }
            }
            println!("{v}");
        } else {
            println!("0");
        }
    }
    0
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let text = fs::read_to_string(&args[1])
        .expect("invalid file")
        .chars()
        .collect();
    process::exit(run(text));
}

#[cfg(test)]
mod tests {
    use std::io::Write;
    use std::process::{Command, Stdio};
    use std::sync::atomic::{AtomicU64, Ordering};

    fn run_program(program: &str) -> String {
        static COUNTER: AtomicU64 = AtomicU64::new(0);
        let exe = std::env::current_exe()
            .expect("current exe")
            .parent()
            .unwrap()
            .parent()
            .unwrap()
            .join("trash");
        let path = std::env::temp_dir().join(format!(
            "trash-test-{}-{}.txt",
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
        child.stdin.take().unwrap().write_all(b"").unwrap();
        let out = child.wait_with_output().unwrap();
        std::fs::remove_file(&path).ok();
        String::from_utf8(out.stdout).expect("non-utf8 output")
    }

    #[test]
    fn advances_through_primes() {
        assert_eq!(run_program("t3"), "5\n");
        assert_eq!(run_program("tt3"), "7\n");
        assert_eq!(run_program("t5"), "7\n");
    }

    #[test]
    fn non_prime_start_prints_zero() {
        assert_eq!(run_program("t4"), "0\n");
        assert_eq!(run_program("t9"), "0\n");
    }

    #[test]
    fn two_is_prime() {
        // 2 is prime per the port, so it advances rather than printing 0
        assert_eq!(run_program("t2"), "3\n");
    }

    #[test]
    fn no_leading_t_prints_nothing() {
        assert_eq!(run_program("5"), "");
        assert_eq!(run_program("0"), "");
    }
}
