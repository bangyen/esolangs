//! Basicfuck interpreter (Rust cross-check; see README "Extra Implementations").
//!
//! A source-level language compiled to cells by the interpreter itself.  A
//! `#basicfuck t=.. r=.. o=..` directive sets the tape size, cell range, and
//! overflow behavior (`wrap`/`halt`/`nearest`); `#allocate` names the
//! variables (plain `X` or array `X->n`).  `X += Y` / `X -= Y` add or
//! subtract a constant or another variable, `if`/`while (X) { ... }` branch
//! and loop (with an optional `!` negating the condition), `write <- X`
//! prints X as a byte, `read -> X` stores the next input byte, and `X->n`
//! indexes into an allocated array.  `//` comments are stripped.
//!
//! Malformed programs (a bad directive, identifier, token, syntax, or a tape
//! too small for the allocations) print the C++ reference's message and exit
//! with status 2; a `halt` underflow/overflow, or an array access past its
//! allocation, exits with status 3; `wrap`/`nearest` bound the cell instead.
//! `read` reads the first byte of a line and returns status 3 when the input
//! runs out (nested scopes discard the status, as the C++ reference does).
//!
//! Invocation: `basicfuck <program-file>`; program text from `argv[1]`.
//! Input: the program file is `argv[1]`; `read` reads from stdin.

use regex::Regex;
use std::env;
use std::fs;
use std::io::{self, BufRead, Write};
use std::process;

fn error(message: &str, status: i32) -> ! {
    println!("{message}");
    process::exit(status);
}

fn index(key: &str, var: &[(String, i64)]) -> i64 {
    let mut ind: i64 = 0;
    let mut name = key;
    if let Some(pos) = key.find("->") {
        ind += key[pos + 2..].parse::<i64>().unwrap();
        name = &key[..pos];
    }
    for (vname, size) in var {
        if vname != name {
            ind += size;
        } else {
            return ind;
        }
    }
    error("Identifier is undefined.", 2);
}

fn lexer(program: &str) -> Vec<String> {
    let b = program.as_bytes();
    let n = b.len();
    let mut tokens: Vec<String> = Vec::new();
    let mut i = 0usize;
    while i < n {
        while i < n && (b[i] as char).is_ascii_whitespace() {
            i += 1;
        }
        if i >= n {
            break;
        }
        let c = b[i] as char;
        if c.is_ascii_alphabetic() || c == '_' {
            let mut j = i;
            while j < n && ((b[j] as char).is_ascii_alphanumeric() || b[j] == b'_') {
                j += 1;
            }
            if j + 2 < n && &program[j..j + 2] == "->" && (b[j + 2] as char).is_ascii_digit() {
                let mut k = j + 2;
                while k < n && (b[k] as char).is_ascii_digit() {
                    k += 1;
                }
                tokens.push(program[i..k].to_string());
                i = k;
            } else {
                tokens.push(program[i..j].to_string());
                i = j;
            }
        } else if c.is_ascii_digit() {
            let mut j = i;
            while j < n && (b[j] as char).is_ascii_digit() {
                j += 1;
            }
            tokens.push(program[i..j].to_string());
            i = j;
        } else if "!(){};".contains(c) {
            tokens.push(c.to_string());
            i += 1;
        } else if program[i..].starts_with("+=")
            || program[i..].starts_with("-=")
            || program[i..].starts_with("->")
            || program[i..].starts_with("<-")
        {
            tokens.push(program[i..i + 2].to_string());
            i += 2;
        } else {
            error("Invalid token.", 2);
        }
    }
    tokens
}

fn parse(tokens: &[String], var: &[(String, i64)], name_re: &Regex) -> Vec<i64> {
    let size = tokens.len();
    let mut result: Vec<i64> = Vec::new();
    let mut ind = 0usize;
    let mut pair = 0i64;

    while ind < size {
        let s = &tokens[ind];
        ind += 1;
        if (s == "if" || s == "while") && ind + 4 < size {
            result.push(if s == "if" { -3 } else { -4 });
            if tokens[ind] == "!" {
                result.push(-7);
                ind += 1;
            }
            let mut ok = ind < size && tokens[ind] == "(";
            if ok {
                ind += 1;
                ok = ind < size && name_re.is_match(&tokens[ind]);
                if ok {
                    ind += 1;
                    ok = ind < size && tokens[ind] == ")";
                    if ok {
                        ind += 1;
                        ok = ind < size && tokens[ind] == "{";
                        if ok {
                            ind += 1;
                        }
                    }
                }
            }
            if !ok {
                error("Invalid syntax.", 2);
            }
            pair += 1;
            result.push(index(&tokens[ind - 3], var));
            result.push(-8);
        } else if (s == "write" || s == "read") && ind + 2 < size {
            let arrow = if s == "write" { "<-" } else { "->" };
            let mut ok = ind < size && tokens[ind] == arrow;
            if ok {
                ind += 1;
                ok = ind < size && name_re.is_match(&tokens[ind]);
                if ok {
                    ind += 1;
                    ok = ind < size && tokens[ind] == ";";
                    if ok {
                        ind += 1;
                    }
                }
            }
            if !ok {
                error("Invalid syntax.", 2);
            }
            result.push(if s == "write" { -5 } else { -6 });
            result.push(index(&tokens[ind - 2], var));
        } else if name_re.is_match(s) && ind + 2 < size {
            if !((tokens[ind] == "+=" || tokens[ind] == "-=") && tokens[ind + 2] == ";") {
                error("Invalid syntax.", 2);
            }
            result.push(if tokens[ind] == "+=" { -1 } else { -2 });
            ind += 1;
            let sec = tokens[ind].clone();
            result.push(index(&tokens[ind - 2], var));
            if name_re.is_match(&sec) {
                result.push(index(&tokens[ind], var));
            } else {
                if !sec.bytes().all(|b| b.is_ascii_digit()) {
                    error("Invalid syntax.", 2);
                }
                let mut n = 2 * sec.parse::<i64>().unwrap();
                if n > 0 {
                    n -= 1;
                }
                result.push(-n - 10);
            }
            ind += 2;
        } else if s == "}" {
            result.push(-9);
            pair -= 1;
        } else {
            error("Invalid syntax.", 2);
        }
    }
    if pair != 0 {
        error("Invalid syntax.", 2);
    }
    result
}

fn read_input_line() -> Vec<u8> {
    let mut stdin = io::stdin().lock();
    let mut line: Vec<u8> = Vec::new();
    stdin.read_until(b'\n', &mut line).unwrap();
    line
}

fn execute(prog: &[i64], tape: &mut Vec<i64>, mode: char, bot: i64, top: i64) -> i32 {
    let size = prog.len();
    let mut ptr = 0usize;
    let mut out = false;
    let mut stdout = io::stdout();

    while ptr < size {
        let op = prog[ptr];
        ptr += 1;
        if op > -3 {
            let mut num = prog[ptr + 1];
            if num < 0 {
                num += 10;
                if num % 2 != 0 {
                    num = (num - 1) / -2;
                } else {
                    num /= 2;
                }
            } else {
                let idx = num as usize;
                if idx >= tape.len() {
                    process::exit(3);
                }
                num = tape[idx];
            }
            if op == -2 {
                num = -num;
            }
            let dst = prog[ptr] as usize;
            if dst >= tape.len() {
                process::exit(3);
            }
            let mut value = tape[dst] + num;
            if value < bot {
                if mode == 'h' {
                    error("Underflow error.", 3);
                }
                value = if mode == 'w' { top } else { bot };
            }
            if value > top {
                if mode == 'h' {
                    error("Overflow error.", 3);
                }
                value = if mode == 'w' { bot } else { top };
            }
            tape[dst] = value;
            ptr += 2;
        } else if op > -5 {
            let mut neg = false;
            if prog[ptr] == -7 {
                neg = true;
                ptr += 1;
            }
            ptr += 1;
            let mut end = ptr;
            ptr += 1;
            let mut pair = 1;
            while pair != 0 {
                end += 1;
                if prog[end] == -8 {
                    pair += 1;
                } else if prog[end] == -9 {
                    pair -= 1;
                }
            }
            let body = &prog[ptr..end];
            let cond_idx = prog[ptr - 2] as usize;
            if cond_idx >= tape.len() {
                process::exit(3);
            }
            let mut cond = (tape[cond_idx] != 0) ^ neg;
            if op == -3 {
                if cond {
                    execute(body, tape, mode, bot, top);
                }
            } else {
                while cond {
                    execute(body, tape, mode, bot, top);
                    let idx = prog[ptr - 2] as usize;
                    if idx >= tape.len() {
                        process::exit(3);
                    }
                    cond = (tape[idx] != 0) ^ neg;
                }
            }
            ptr = end + 1;
        } else if op == -5 {
            let idx = prog[ptr] as usize;
            if idx >= tape.len() {
                process::exit(3);
            }
            stdout.write_all(&[(tape[idx] & 0xFF) as u8]).unwrap();
            out = true;
            ptr += 1;
        } else {
            let idx = prog[ptr] as usize;
            if idx >= tape.len() {
                process::exit(3);
            }
            if out {
                stdout.write_all(b"\n").unwrap();
            }
            stdout.write_all(b"Input: ").unwrap();
            stdout.flush().unwrap();
            let line = read_input_line();
            if line.is_empty() {
                return 3;
            }
            tape[idx] = line[0] as i64;
            out = false;
            ptr += 1;
        }
    }
    0
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let text = fs::read_to_string(&args[1]).expect("invalid file");

    let directive_re =
        Regex::new(r"#basicfuck t=(\d+|unbounded) r=(\d*)~(\d*)( o=(wrap|halt|nearest))?\s*$")
            .unwrap();
    let allocate_re = Regex::new(r"#allocate(?:\s*[_a-zA-Z]\w*(?:->\d+)?,?)*\s*$").unwrap();
    let ident_re = Regex::new(r"(?s)(\s*([_a-zA-Z]\w*)(?:->(\d+))?,?)(.*)").unwrap();
    let assign_re = Regex::new(r"[_a-zA-Z]\w*(?:->\d+)?\s*[+-]=\s*[_a-zA-Z]\w*(?:->\d+)?").unwrap();
    let name_re = Regex::new(r"^[_a-zA-Z]\w*(?:->\d+)?$").unwrap();
    let comments_re = Regex::new(r"//[^\n]*").unwrap();

    let lines: Vec<&str> = text.split('\n').collect();
    let directive = lines[0];
    let allocate = if lines.len() > 1 { lines[1] } else { "" };
    let mut body = if lines.len() > 2 {
        lines[2..].join("\n")
    } else {
        String::new()
    };

    let caps = match directive_re.captures(directive) {
        Some(caps) => caps,
        None => error("Missing/Invalid directives.", 2),
    };
    let mut lim: i64 = if caps.get(1).unwrap().as_str() == "unbounded" {
        -1
    } else {
        caps.get(1).unwrap().as_str().parse().unwrap()
    };
    let bot_specified = !caps.get(2).unwrap().as_str().is_empty();
    let top_specified = !caps.get(3).unwrap().as_str().is_empty();
    let mode_count = (bot_specified as i64) + (top_specified as i64);
    if mode_count != 0 && caps.get(4).is_none() {
        error("Missing overflow directive.", 2);
    }
    let mode = match caps.get(5) {
        Some(m) => {
            if mode_count != 2 && m.as_str() == "wrap" {
                error("Invalid overflow directive.", 2);
            }
            m.as_str().chars().next().unwrap()
        }
        None => '\0',
    };
    let bot: i64 = if bot_specified {
        caps.get(2).unwrap().as_str().parse().unwrap()
    } else {
        i64::MIN
    };
    let top: i64 = if top_specified {
        caps.get(3).unwrap().as_str().parse().unwrap()
    } else {
        i64::MAX
    };

    if !allocate_re.is_match(allocate) {
        error("Missing/Invalid identifiers.", 2);
    }
    let mut var: Vec<(String, i64)> = Vec::new();
    let mut tape: Vec<i64> = Vec::new();
    let mut rest = &allocate["#allocate".len()..];
    while let Some(m) = ident_re.captures(rest) {
        let name = m.get(2).unwrap().as_str().to_string();
        let size: i64 = match m.get(3) {
            Some(g) if !g.as_str().is_empty() => g.as_str().parse().unwrap(),
            _ => 1,
        };
        let start = tape.len();
        tape.resize(start + size as usize, 0);
        if name == "if" || name == "while" || name == "write" || name == "read" {
            error("Invalid identifier.", 2);
        }
        var.push((name, size));
        rest = m.get(4).unwrap().as_str();
        if rest.trim().is_empty() {
            break;
        }
    }

    body = comments_re.replace_all(&body, "").to_string();
    if assign_re.is_match(&body) && lim != -1 {
        lim -= 1;
    }
    if lim != -1 && lim < tape.len() as i64 {
        error("Insufficient memory.", 2);
    }

    let words = lexer(&body);
    let ops = parse(&words, &var, &name_re);
    let status = execute(&ops, &mut tape, mode, bot, top);
    if status != 0 {
        process::exit(status);
    }
}

#[cfg(test)]
mod tests {
    use std::io::Write;
    use std::process::{Command, Stdio};
    use std::sync::atomic::{AtomicU64, Ordering};

    const BF_N: &str = "#basicfuck t=1 r=0~255 o=nearest\n#allocate a\n";
    const BF_W: &str = "#basicfuck t=1 r=0~255 o=wrap\n#allocate a\n";
    const BF_H: &str = "#basicfuck t=1 r=0~255 o=halt\n#allocate a\n";
    const BF_U: &str = "#basicfuck t=unbounded r=0~255 o=wrap\n#allocate ";

    fn run_program(program: &str, stdin: &str) -> (Vec<u8>, i32) {
        static COUNTER: AtomicU64 = AtomicU64::new(0);
        let exe = std::env::current_exe()
            .expect("current exe")
            .parent()
            .unwrap()
            .parent()
            .unwrap()
            .join("basicfuck");
        let path = std::env::temp_dir().join(format!(
            "basicfuck-test-{}-{}.txt",
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
    fn writes_a_constant() {
        assert_eq!(
            run_program(&format!("{BF_N}a += 65;\nwrite <- a ;"), ""),
            (b"A".to_vec(), 0)
        );
        // wrap: 256 over the top bounds back to the bottom
        assert_eq!(
            run_program(&format!("{BF_W}a += 256;\nwrite <- a ;"), ""),
            (vec![0], 0)
        );
    }

    #[test]
    fn halt_overflow_exits_3() {
        assert_eq!(run_program(&format!("{BF_H}a += 256;"), "").1, 3);
    }

    #[test]
    fn variable_variable_arithmetic() {
        // b += a reads a's value (5)
        let prog = format!("{BF_U}a, b\na += 5;\nb += a;\nwrite <- b ;");
        assert_eq!(run_program(&prog, ""), (vec![5], 0));
    }

    #[test]
    fn reads_and_writes_input() {
        let prog = format!("{BF_U}a\nread -> a ;\nwrite <- a ;");
        assert_eq!(run_program(&prog, "X\n"), (b"Input: X".to_vec(), 0));
        let prog = format!("{BF_U}a\nread -> a ;\na -= 48 ;\nwrite <- a ;");
        assert_eq!(run_program(&prog, "0\n"), (b"Input: \0".to_vec(), 0));
    }

    #[test]
    fn branches_and_loops() {
        let prog = format!("{BF_U}a\na += 1;\nif (a) {{ write <- a ; }}");
        assert_eq!(run_program(&prog, ""), (vec![1], 0));
        let prog = format!("{BF_U}a\na += 0;\nif (a) {{ write <- a ; }}");
        assert_eq!(run_program(&prog, ""), (vec![], 0));
        let prog = format!("{BF_U}a\na += 5;\nwhile (a) {{ a -= 1; }}\nwrite <- a ;");
        assert_eq!(run_program(&prog, ""), (vec![0], 0));
    }

    #[test]
    fn arrays_and_comments() {
        let prog =
            format!("{BF_U}a->2\na->0 += 65;\nwrite <- a->0 ;\na->1 += 66;\nwrite <- a->1 ;");
        assert_eq!(run_program(&prog, ""), (b"AB".to_vec(), 0));
        assert_eq!(
            run_program(&format!("{BF_N}a += 65; // comment\nwrite <- a ;"), ""),
            (b"A".to_vec(), 0)
        );
    }

    #[test]
    fn malformed_programs_exit_2() {
        assert_eq!(run_program("not a directive\n#allocate a\n", "").1, 2);
        assert_eq!(run_program(&format!("{BF_N}z += 1;"), "").1, 2);
    }
}
