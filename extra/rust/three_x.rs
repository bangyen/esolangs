//! 3x interpreter (Rust cross-check; see README "Extra Implementations").
//!
//! A stack-based language over exact rationals.  `3` pushes the rational 3,
//! `x` replaces the top three items `a, b, c` (c on top) with `(c-b)/a`,
//! `?` reads a rational from input, `!` pops and prints the top (as an
//! integer when whole, otherwise as a fraction), `v` stores the top under a
//! popped key, `^` pushes the value of a popped key (3 if unassigned), `#`
//! swaps the top two, `(`/`)` loop while the top is nonzero, and `[` prints
//! the literal up to the next `]` and skips past it.
//!
//! An empty-stack pop, a swap or `x` with too few items, a `(`/`)` on an
//! empty stack, an unmatched `(`, a `)` with no pending `(`, or a division
//! by zero exit with status 3; `?` exits with status 3 when the input runs
//! out and status 2 on input that is not an integer or a fraction (matching
//! the Ruby `Rational` parser, which rejects decimals).  `[` with no closing
//! `]` prints nothing.
//!
//! Invocation: `three_x <program-file>`; program text from `argv[1]`.
//! Input: the program file is `argv[1]`; `?` reads from stdin.

use std::collections::HashMap;
use std::env;
use std::fs;
use std::io::{self, BufRead, Write};
use std::process;

#[derive(Clone, Copy, PartialEq, Eq, Hash)]
struct Rat {
    num: i64,
    den: i64,
}

fn gcd(mut a: i64, mut b: i64) -> i64 {
    a = a.abs();
    b = b.abs();
    while b != 0 {
        let t = b;
        b = a % b;
        a = t;
    }
    a
}

fn rat(num: i64, den: i64) -> Rat {
    let g = gcd(num, den);
    let mut n = num / g;
    let mut d = den / g;
    if d < 0 {
        n = -n;
        d = -d;
    }
    Rat { num: n, den: d }
}

impl Rat {
    fn sub(self, other: Rat) -> Rat {
        rat(
            self.num * other.den - other.num * self.den,
            self.den * other.den,
        )
    }
    fn div(self, other: Rat) -> Rat {
        rat(self.num * other.den, self.den * other.num)
    }
    fn is_zero(self) -> bool {
        self.num == 0
    }
}

fn pop(stack: &mut Vec<Rat>) -> Rat {
    match stack.pop() {
        Some(value) => value,
        None => process::exit(3),
    }
}

fn parse_rat(line: &[u8]) -> Option<Rat> {
    let s = std::str::from_utf8(line).ok()?.trim();
    fn is_int(t: &str) -> bool {
        let t = t
            .strip_prefix('+')
            .or_else(|| t.strip_prefix('-'))
            .unwrap_or(t);
        !t.is_empty() && t.bytes().all(|b| b.is_ascii_digit())
    }
    if let Some(slash) = s.find('/') {
        let num = &s[..slash];
        let den = &s[slash + 1..];
        if !is_int(num) || !is_int(den) {
            return None;
        }
        let n: i64 = num.parse().ok()?;
        let d: i64 = den.parse().ok()?;
        if d == 0 {
            return None;
        }
        Some(rat(n, d))
    } else {
        if !is_int(s) {
            return None;
        }
        Some(Rat {
            num: s.parse().ok()?,
            den: 1,
        })
    }
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
    let code: Vec<char> = fs::read_to_string(&args[1])
        .expect("invalid file")
        .chars()
        .collect();
    let n = code.len();

    let mut stack: Vec<Rat> = Vec::new();
    let mut jumps: Vec<usize> = Vec::new();
    let mut variables: HashMap<Rat, Rat> = HashMap::new();
    let mut ind = 0usize;
    let mut stdout = io::stdout();

    while ind < n {
        let c = code[ind];
        match c {
            '3' => stack.push(Rat { num: 3, den: 1 }),
            'x' => {
                let c = pop(&mut stack);
                let b = pop(&mut stack);
                let a = pop(&mut stack);
                if a.is_zero() {
                    process::exit(3);
                }
                stack.push(c.sub(b).div(a));
            }
            '?' => {
                stdout.write_all(b"Input: ").unwrap();
                stdout.flush().unwrap();
                match read_line() {
                    Some(line) => match parse_rat(&line) {
                        Some(value) => stack.push(value),
                        None => process::exit(2),
                    },
                    None => process::exit(3),
                }
            }
            '!' => {
                let value = pop(&mut stack);
                if value.den == 1 {
                    write!(stdout, "{}", value.num).unwrap();
                } else {
                    write!(stdout, "{}/{}", value.num, value.den).unwrap();
                }
            }
            'v' => {
                let value = pop(&mut stack);
                let key = pop(&mut stack);
                variables.insert(key, value);
            }
            '^' => {
                let key = pop(&mut stack);
                stack.push(*variables.get(&key).unwrap_or(&Rat { num: 3, den: 1 }));
            }
            '#' => {
                let x = pop(&mut stack);
                let y = pop(&mut stack);
                stack.push(x);
                stack.push(y);
            }
            '(' => {
                if stack.is_empty() {
                    process::exit(3);
                }
                if stack[stack.len() - 1].is_zero() {
                    let mut num = 1;
                    while num > 0 {
                        ind += 1;
                        if ind >= n {
                            process::exit(3);
                        }
                        let inner = code[ind];
                        if inner == '(' {
                            num += 1;
                        } else if inner == ')' {
                            num -= 1;
                        }
                    }
                } else {
                    jumps.push(ind);
                }
            }
            ')' => {
                if stack.is_empty() {
                    process::exit(3);
                }
                if !stack[stack.len() - 1].is_zero() {
                    match jumps.last() {
                        Some(&value) => ind = value,
                        None => process::exit(3),
                    }
                } else if !jumps.is_empty() {
                    jumps.pop();
                }
            }
            '[' => {
                let mut close = None;
                for (i, &ch) in code.iter().enumerate().skip(ind + 1) {
                    if ch == ']' {
                        close = Some(i);
                        break;
                    }
                }
                if let Some(close) = close {
                    let text: String = code[ind + 1..close].iter().collect();
                    stdout.write_all(text.as_bytes()).unwrap();
                    ind = close;
                }
            }
            _ => {}
        }
        ind += 1;
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
            .join("three_x");
        let path = std::env::temp_dir().join(format!(
            "three-x-test-{}-{}.txt",
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
    fn pushes_and_arithmetic() {
        assert_eq!(run_program("3!", ""), (b"3".to_vec(), 0));
        // (3-3)/3 = 0, then (3-0)/3 = 1
        assert_eq!(run_program("3333x3x!", ""), (b"1".to_vec(), 0));
        // 3,3,3 x -> 0, 3 # -> swap, print 0
        assert_eq!(run_program("333x3#!", ""), (b"0".to_vec(), 0));
    }

    #[test]
    fn literal_print() {
        assert_eq!(run_program("[Hi]", ""), (b"Hi".to_vec(), 0));
    }

    #[test]
    fn reads_rationals() {
        assert_eq!(run_program("?!", "5\n"), (b"Input: 5".to_vec(), 0));
        assert_eq!(run_program("?!", "1/3\n"), (b"Input: 1/3".to_vec(), 0));
    }

    #[test]
    fn variables_and_swap() {
        // ? 3 v 3 ^ ! : store 3 under 1/3, recall 3 (default) under 3
        assert_eq!(run_program("?3v3^!", "1/3\n"), (b"Input: 3".to_vec(), 0));
    }
}
