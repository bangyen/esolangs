//! Number Seventy-Four interpreter (Rust cross-check; see README "Extra
//! Implementations").
//!
//! A one-bit tape language.  `0`/`1` push their bit onto the front of the
//! output string, and `H` writes an `H` only if the output already starts
//! with `0` (the first character written, which the last push determines).
//! The program is scanned in repeated passes: once the output starts with
//! `H` the program prints it and halts, otherwise it restarts from the
//! beginning of the program.  Any other character is ignored, and there is
//! no input command.
//!
//! This port matches the pass-boundary semantics of the Python reference
//! (and the former Ruby cross-check): the halting check is made only at a
//! pass boundary, so a program that makes the output start with `H`
//! mid-pass and then pushes a `0`/`1` afterwards never halts, and a program
//! whose output never starts with `H` restarts forever.  A program with no
//! `0`/`1`/`H` commands at all halts with no output instead of looping.
//! (The Lean interpreter in `extra/lean` diverges: it checks for the leading
//! `H` before every command rather than at pass boundaries and stops after a
//! fixed 100-command limit, so it cannot serve as this oracle.)
//!
//! Invocation: `seventy_four <program-file>`; program text from `argv[1]`.
//! Input: the program file is `argv[1]`; the language has no input command.

use std::env;
use std::fs;

fn run(text: String) {
    if !text.chars().any(|c| c == '0' || c == '1' || c == 'H') {
        return;
    }
    let mut data = String::new();
    loop {
        for c in text.chars() {
            match c {
                '0' => data.insert(0, '0'),
                '1' => data.insert(0, '1'),
                'H' => {
                    if data.starts_with('0') {
                        data.insert(0, 'H');
                    }
                }
                _ => {}
            }
        }
        if data.starts_with('H') {
            break;
        }
    }
    print!("{data}");
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let text = fs::read_to_string(&args[1]).expect("invalid file");
    run(text);
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
            .join("seventy_four");
        let path = std::env::temp_dir().join(format!(
            "seventy_four-test-{}-{}.txt",
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
    fn halts_on_leading_h_at_pass_boundary() {
        // 0 then H: the pass ends with data = "H0", which starts with H
        assert_eq!(run_program("0H"), "H0");
    }

    #[test]
    fn leading_h_requires_a_leading_zero() {
        // 1H0H: the first H sees a leading 1, the second a leading 0
        assert_eq!(run_program("1H0H"), "H01");
    }

    #[test]
    fn bits_prepend_before_the_h() {
        assert_eq!(run_program("101H0H"), "H0101");
    }

    #[test]
    fn no_command_program_prints_nothing() {
        assert_eq!(run_program(""), "");
    }
}
