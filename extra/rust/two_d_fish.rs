//! 2dFish interpreter (Rust cross-check; see README "Extra Implementations").
//!
//! A pointer travels a grid of rows; the top-left cell must set its direction
//! (`/` right, `\` left, `v` down, `^` up) and every cell it lands on is
//! executed as a command: `i`/`d`/`s` increment/decrement/square the
//! accumulator, `o` prints it in decimal, `a` prints it as a byte (or, in
//! string mode, the last captured character, which it removes), `$` reads an
//! input line into the string variable, `%` reads an integer into the
//! accumulator, `(`
//! captures the rest of its row up to the first `)` as the string variable
//! and (heading right) skips past it, `*` prints and clears the string
//! variable, and `@` halts.  The direction cell on the current cell also
//! redirects the pointer, so a direction both steers and executes as a
//! no-op.
//!
//! The grid is *ragged*: the pointer is off the grid when it leaves any row,
//! and stepping off the grid exits with status 3.  A `(` with no `)` on its
//! row is a malformed program (status 2), and a program that does not set an
//! initial direction in the top-left cell is malformed too.  The reference's
//! file-reading loop pushes a phantom copy of the last row when the program
//! text ends with a newline; this port reproduces that.  `a` in string mode
//! on an empty string, or exhausted input, exits with status 3; `%` on an
//! unparseable line exits with status 2.
//!
//! Invocation: `two_d_fish <program-file>`; program text from `argv[1]`.
//! Input: the program file is `argv[1]`; `$`/`%` read from stdin.

use std::env;
use std::fs;
use std::io::{self, BufRead, Write};
use std::process;

fn read_rows(code: &str) -> Vec<String> {
    let mut rows: Vec<String> = code.split('\n').map(str::to_string).collect();
    if code.ends_with('\n') {
        rows.pop();
        if let Some(last) = rows.last() {
            rows.push(last.clone());
        }
    }
    rows
}

fn get(grid: &[String], x: i64, y: i64) -> char {
    if y < 0 || x < 0 || y as usize >= grid.len() || x as usize >= grid[y as usize].len() {
        process::exit(3);
    }
    grid[y as usize].as_bytes()[x as usize] as char
}

fn direct(c: char, x: i64, y: i64, d: Option<char>) -> (i64, i64, Option<char>) {
    let mut d = d;
    if c == '/' || c == '\\' || c == 'v' || c == '^' {
        d = Some(c);
    }
    let (mut x, mut y) = (x, y);
    match d {
        Some('/') => x += 1,
        Some('\\') => x -= 1,
        Some('v') => y += 1,
        Some('^') => y -= 1,
        _ => {}
    }
    (x, y, d)
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
    let grid = read_rows(&text);
    if grid.is_empty() {
        process::exit(2);
    }

    let first = if grid[0].is_empty() {
        '\0'
    } else {
        grid[0].as_bytes()[0] as char
    };
    let (mut x, mut y, mut d) = direct(first, 0, 0, None);
    if d.is_none() {
        process::exit(2);
    }

    let mut acc: i64 = 0;
    let mut string = String::new();
    let mut mode = false;
    let mut out = false;
    let mut c = get(&grid, x, y);
    let mut stdout = io::stdout();

    while c != '@' {
        match c {
            'i' => {
                mode = false;
                acc += 1;
            }
            'd' => {
                mode = false;
                acc -= 1;
            }
            's' => {
                mode = false;
                acc *= acc;
            }
            'o' => {
                write!(stdout, "{}", acc).unwrap();
                out = true;
            }
            'a' => {
                if mode {
                    if string.is_empty() {
                        process::exit(3);
                    }
                    let byte = string.as_bytes()[string.len() - 1];
                    stdout.write_all(&[byte]).unwrap();
                    string = string[..string.len() - 1].to_string();
                } else {
                    stdout.write_all(&[(acc & 0xFF) as u8]).unwrap();
                }
                out = true;
            }
            '$' => {
                prompt(&mut out);
                match read_line() {
                    Some(mut line) => {
                        if line.last() == Some(&b'\n') {
                            line.pop();
                        }
                        string = String::from_utf8(line).unwrap();
                    }
                    None => process::exit(3),
                }
            }
            '%' => {
                prompt(&mut out);
                mode = false;
                match read_line() {
                    Some(line) => {
                        let s = String::from_utf8(line).unwrap();
                        match s.trim().parse::<i64>() {
                            Ok(value) => acc = value,
                            Err(_) => process::exit(2),
                        }
                    }
                    None => process::exit(3),
                }
            }
            '(' => {
                string = String::new();
                mode = true;
                let row = &grid[y as usize];
                if !row.as_bytes()[x as usize..].contains(&b')') {
                    process::exit(2);
                }
                let temp = x;
                x += 1;
                while row.as_bytes()[x as usize] as char != ')' {
                    string.push(row.as_bytes()[x as usize] as char);
                    x += 1;
                }
                if d != Some('/') {
                    x = temp;
                }
            }
            '*' => {
                stdout.write_all(string.as_bytes()).unwrap();
                string = String::new();
                out = true;
            }
            _ => {}
        }

        let (nx, ny, nd) = direct(c, x, y, d);
        x = nx;
        y = ny;
        d = nd;
        c = get(&grid, x, y);
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
            .join("two_d_fish");
        let path = std::env::temp_dir().join(format!(
            "2dfish-test-{}-{}.txt",
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
    fn accumulator_and_print() {
        assert_eq!(run_program("/o@", ""), (b"0".to_vec(), 0));
        assert_eq!(run_program("/io@", ""), (b"1".to_vec(), 0));
        assert_eq!(run_program("/iiio@", ""), (b"3".to_vec(), 0));
        // a prints the accumulator as a byte
        assert_eq!(run_program("/ia@", ""), (vec![1], 0));
    }

    #[test]
    fn string_capture_and_print() {
        assert_eq!(run_program("/i(abc)*@", ""), (b"abc".to_vec(), 0));
        // a in string mode prints one captured character
        assert_eq!(run_program("/i(ab)a@", ""), (b"a".to_vec(), 0));
    }

    #[test]
    fn reads_input() {
        assert_eq!(run_program("/$*@", "hi\n"), (b"Input: hi".to_vec(), 0));
        assert_eq!(run_program("/%o@", "42\n"), (b"Input: 42".to_vec(), 0));
    }

    #[test]
    fn vertical_movement_and_phantom_row() {
        // the trailing newline duplicates the last row, but v halts at @
        assert_eq!(run_program("v\ni\n@\n", ""), (vec![], 0));
    }
}
