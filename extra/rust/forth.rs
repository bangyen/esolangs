//! Forþ interpreter (Rust cross-check; see README "Extra Implementations").
//!
//! A stack-based language with a dispatch table of named functions.  Digits
//! 0-9 and letters A-F push their value, `:` duplicates the top, `+`/`-`/`*`
//! `/`/`%` do arithmetic (the top goes on the right), `~` pushes the bitwise
//! complement of the top, `.` prints the top as a byte, `,` reads a line of
//! input pushing each byte, `(`/`[` branch or loop while the top is nonzero,
//! `{` stores a scope under the number atop the stack, `;` calls the stored
//! scope, `o` reverses the stack, `c` rotates the top three, and `v` swaps
//! the top two.  Any other character is ignored.
//!
//! Arithmetic wraps to signed 32-bit integers, and `/`/`%` truncate toward
//! zero (C++11 semantics).  An empty-stack pop exits with status 3 (the whole
//! program), while the other invalid operations (a binary operator with fewer
//! than two values, `c` with fewer than three, a division by zero, or an
//! unterminated bracket) abort only the innermost scope, mirroring the Python
//! interpreter's discarded error codes.  `,` reads a whole line and exits with
//! status 3 when the input runs out.
//!
//! Invocation: `forth <program-file>`; program text from `argv[1]`.
//! Input: the program file is `argv[1]`; `,` reads from stdin.

use std::collections::HashMap;
use std::env;
use std::fs;
use std::io::{self, BufRead, Write};
use std::process;

fn top(stack: &[i32]) -> i32 {
    match stack.last() {
        Some(value) => *value,
        None => process::exit(3),
    }
}

fn pop(stack: &mut Vec<i32>) -> i32 {
    let value = top(stack);
    stack.pop();
    value
}

fn read_input_line() -> Vec<u8> {
    let mut stdin = io::stdin().lock();
    let mut line: Vec<u8> = Vec::new();
    if stdin.read_until(b'\n', &mut line).unwrap_or(0) == 0 {
        process::exit(3);
    }
    line
}

fn run(
    code: &[char],
    stack: &mut Vec<i32>,
    table: &mut HashMap<i32, String>,
    out: &mut bool,
) -> i32 {
    let n = code.len();
    let mut k = 0usize;
    let mut stdout = io::stdout();

    while k < n {
        let c = code[k];
        k += 1;
        if c.is_ascii_digit() {
            stack.push(c as i32 - 48);
        } else if c.is_ascii_uppercase() && c <= 'F' {
            stack.push(c as i32 - 55);
        } else if c == ':' {
            let value = top(stack);
            stack.push(value);
        } else if c == '~' {
            let value = pop(stack);
            stack.push(!value);
        } else if c == '.' {
            stdout.write_all(&[(pop(stack) & 0xFF) as u8]).unwrap();
            *out = true;
        } else if c == ',' {
            if *out {
                stdout.write_all(b"\n").unwrap();
            }
            *out = false;
            stdout.write_all(b"Input: ").unwrap();
            stdout.flush().unwrap();

            let mut line = read_input_line();
            if line.last() == Some(&b'\n') {
                line.pop();
            }
            for byte in line {
                stack.push(byte as i32);
            }
        } else if c == ';' {
            let scope = table.get(&pop(stack)).cloned().unwrap_or_default();
            let scope_chars: Vec<char> = scope.chars().collect();
            run(&scope_chars, stack, table, out);
        } else if c == 'o' {
            stack.reverse();
        } else if c == 'c' {
            if stack.len() < 3 {
                return 3;
            }
            let value = stack.remove(stack.len() - 3);
            stack.push(value);
        } else if c == '(' || c == '[' || c == '{' {
            let add = c;
            let sub = match c {
                '(' => ')',
                '[' => ']',
                _ => '}',
            };
            let start = k - 1;
            let mut depth = 1i64;
            loop {
                if k >= n {
                    return 3;
                }
                let inner = code[k];
                k += 1;
                if inner == add {
                    depth += 1;
                } else if inner == sub {
                    depth -= 1;
                }
                if depth == 0 {
                    break;
                }
            }
            let scope: String = code[start + 1..k - 1].iter().collect();
            let scope_chars: Vec<char> = code[start + 1..k - 1].to_vec();
            if add == '(' {
                if top(stack) != 0 {
                    run(&scope_chars, stack, table, out);
                }
            } else if add == '[' {
                while top(stack) != 0 {
                    run(&scope_chars, stack, table, out);
                }
            } else {
                let key = top(stack);
                table.insert(key, scope);
            }
        } else if matches!(c, '+' | '-' | '*' | '/' | '%' | 'v') {
            if stack.len() < 2 {
                return 3;
            }
            let two = pop(stack);
            let one = pop(stack);
            if c == '+' {
                stack.push(one.wrapping_add(two));
            } else if c == '-' {
                stack.push(one.wrapping_sub(two));
            } else if c == '*' {
                stack.push(one.wrapping_mul(two));
            } else if c == '/' {
                if two == 0 {
                    return 3;
                }
                stack.push(one.wrapping_div(two));
            } else if c == '%' {
                if two == 0 {
                    return 3;
                }
                stack.push(one.wrapping_rem(two));
            } else {
                stack.push(two);
                stack.push(one);
            }
        }
    }
    0
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let text = fs::read_to_string(&args[1]).expect("invalid file");
    let code: Vec<char> = text.chars().collect();
    let mut stack: Vec<i32> = Vec::new();
    let mut table: HashMap<i32, String> = HashMap::new();
    let mut out = false;
    let status = run(&code, &mut stack, &mut table, &mut out);
    if status != 0 {
        process::exit(status);
    }
}

#[cfg(test)]
mod tests {
    use std::io::Write;
    use std::process::{Command, Stdio};
    use std::sync::atomic::{AtomicU64, Ordering};

    fn run_program(program: &str, stdin: &str) -> (Vec<u8>, i32) {
        static COUNTER: AtomicU64 = AtomicU64::new(0);
        let exe = std::env::current_exe()
            .expect("current exe")
            .parent()
            .unwrap()
            .parent()
            .unwrap()
            .join("forth");
        let path = std::env::temp_dir().join(format!(
            "forth-test-{}-{}.txt",
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
    fn digits_arithmetic_and_print() {
        assert_eq!(run_program("65.", ""), (vec![5], 0));
        assert_eq!(run_program("23+.", ""), (vec![5], 0));
        assert_eq!(run_program("95-.", ""), (vec![4], 0));
        assert_eq!(run_program("85%.", ""), (vec![3], 0));
    }

    #[test]
    fn complement_and_division() {
        // 0~. prints the low byte of -1
        assert_eq!(run_program("0~.", ""), (vec![0xFF], 0));
        // 09/~. : 0/9 = 0, then ~0 = -1, printed as its low byte
        assert_eq!(run_program("09/~.", ""), (vec![0xFF], 0));
    }

    #[test]
    fn loop_branch_and_rotate() {
        // [.] prints the stack's byte values from the top down
        assert_eq!(run_program("0F7*0+F4*C+[.]", ""), (b"Hi".to_vec(), 0));
        // (F4*5+.) runs only when the top is nonzero
        assert_eq!(run_program("1(F4*5+.)", ""), (b"A".to_vec(), 0));
        assert_eq!(run_program("0(F4*5+.)", ""), (vec![], 0));
        // 123c... : rotate the top three
        assert_eq!(run_program("123c...", ""), (vec![1, 3, 2], 0));
    }

    #[test]
    fn reads_a_line() {
        // ,.. : read "hi", then print the two bytes (top first); the prompt
        // precedes the read
        assert_eq!(run_program(",..", "hi"), (b"Input: ih".to_vec(), 0));
        // ,68*-. : read a byte and normalize 0
        assert_eq!(run_program(",68*-.", "0"), (b"Input: \0".to_vec(), 0));
    }

    #[test]
    fn invalid_operations_exit_3() {
        assert_eq!(run_program("50/", "").1, 3); // division by zero
        assert_eq!(run_program("12c", "").1, 3); // c with two elements
        assert_eq!(run_program("a5.", ""), (vec![5], 0)); // unknown char ignored
        assert_eq!(run_program("(5", "").1, 3); // unterminated bracket
    }
}
