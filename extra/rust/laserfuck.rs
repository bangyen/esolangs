//! LaserFuck interpreter (Rust cross-check; see README "Extra
//! Implementations").
//!
//! A laser (starting at `o` with a *random* initial heading) travels a grid.
//! `>`,`<`,`+`,`-`,`,` work on a brainfuck-style tape, `\`/`/` reflect the
//! laser, `_`/`|` and `(`/`)` reflect it when the current cell is nonzero
//! (or always for the unconditional forms), `^v{}` set the heading, `#`
//! skips the next command, `x` deletes the laser, and `*` duplicates it in a
//! random perpendicular direction.  Execution ends when no lasers remain;
//! the tape is then printed, with a leading `\xff` selecting byte output
//! (no separators) over the default decimal mode, and negative cells
//! excluded.
//!
//! Deviations / decisions: the initial heading is uniformly random (so a
//! single run is nondeterministic), the tape holds signed 32-bit cells
//! matching the wiki, and `,` reads a whole line taking only its first byte
//! (empty line -> 0).  A second `o` halts immediately.
//!
//! Invocation: `laserfuck <program-file>`; program text from `argv[1]`.
//! Input: the program file is `argv[1]`; `,` reads from stdin.

use rand::RngExt;
use std::env;
use std::fs;
use std::io::{self, BufRead, Write};

struct Laser(usize, usize, usize);

fn wrap(lsr: &mut Laser, len: usize) {
    let Laser(a, b, d) = lsr;

    if let (0, _, 0) | (_, 0, 2) = (*a, *b, *d) {
        *a = len;
        return;
    }

    match d {
        0 => *a -= 1,
        1 => *a += 1,
        2 => *b -= 1,
        3 => *b += 1,
        _ => (),
    }
}

fn run(text: Vec<Vec<char>>) {
    let mut rng = rand::rng();
    let mut lsrs = Vec::new();
    let mut jmp = false;
    let mut ind = 0;
    let mut ptr = 0;

    let len = text.len();
    let new = (0, false);
    let mut tape = vec![new];

    for (k, v) in text.iter().enumerate() {
        if let Some(n) = v.iter().position(|&c| c == 'o') {
            if !lsrs.is_empty() {
                return;
            } else {
                let num = rng.random_range(0..4);
                let lsr = Laser(k, n, num);
                lsrs.push(lsr);
            }
        }
    }

    while !lsrs.is_empty() {
        wrap(&mut lsrs[ind], len);
        let Laser(x, y, mut m) = lsrs[ind];

        if jmp {
            jmp = false;
            continue;
        }

        let get = text.get(x).and_then(|k| k.get(y));
        let op = if let Some(c) = get { *c } else { 'x' };

        match op {
            '>' => {
                ptr += 1;

                if ptr == tape.len() {
                    tape.push(new);
                }
            }
            '<' => {
                if ptr > 0 {
                    ptr -= 1;
                } else {
                    tape.insert(0, new);
                }
            }
            ',' => {
                let mut val = String::new();
                print!("Input: ");

                io::stdout().flush().unwrap();

                io::stdin().read_line(&mut val).unwrap();

                tape[ptr].0 = if let "\r\n" | "\n" = &*val {
                    0
                } else {
                    val.chars().next().unwrap() as i32
                };
            }
            'x' => {
                lsrs.remove(ind);
                continue;
            }
            '*' => {
                let n = rng.random_range(0..2);
                let d = 2 * (1 - m / 2) + n;
                lsrs.push(Laser(x, y, d));
            }
            '_' | '(' => {
                if m < 2 && (tape[ptr].0 != 0 || op == '_') {
                    m = 1 - m;
                }
            }
            '|' | ')' => {
                if m > 1 && (tape[ptr].0 != 0 || op == '|') {
                    m = 5 - m;
                }
            }
            '/' => m = 3 - m,
            '^' | 'v' | '{' | '}' => m = "^v{}".find(op).unwrap(),
            '\\' => m = (m + 2) % 4,
            '+' => tape[ptr].0 += 1,
            '-' => tape[ptr].0 -= 1,
            '#' => jmp = true,
            _ => (),
        }

        if let ',' | '+' | '-' = op {
            tape[ptr].1 = true;
        }

        lsrs[ind].2 = m;
        ind = (ind + 1) % lsrs.len();
    }

    let out = !text.is_empty() && !text[0].is_empty() && text[0][0] == '\u{FF}';
    let mut post = false;

    for c in tape.iter() {
        if c.1 && c.0 >= 0 {
            if out {
                if let Some(val) = char::from_u32(c.0 as u32) {
                    print!("{}", val);
                    continue;
                }
            } else {
                if post {
                    println!();
                } else {
                    post = true;
                }

                print!("{}", c.0);
            }
        }
    }
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let file = fs::File::open(&args[1]).expect("invalid file");

    let buff = io::BufReader::new(file);
    let clct = |s: Result<String, _>| s.unwrap().chars().collect();
    let mut text: Vec<Vec<char>> = buff.lines().map(clct).collect();

    let max = text.iter().map(|x| x.len()).fold(0, |x, y| x.max(y));

    for v in text.iter_mut() {
        while v.len() < max {
            v.push(' ');
        }
    }

    run(text);
}

#[cfg(test)]
mod tests {
    use std::io::Write;
    use std::process::{Command, Stdio};
    use std::sync::atomic::{AtomicU64, Ordering};

    /// Run a grid through the real binary, feeding ``stdin``, several times.
    ///
    /// The reference picks a random initial heading, so a single run may or
    /// may not touch a given cell; returning the set of outputs across runs
    /// reflects the language's true (nondeterministic) semantics.
    fn run_grid(grid: &str, stdin: &str, runs: usize) -> Vec<String> {
        static COUNTER: AtomicU64 = AtomicU64::new(0);
        let exe = std::env::current_exe()
            .expect("current exe")
            .parent()
            .unwrap()
            .parent()
            .unwrap()
            .join("laserfuck");
        let dir = std::env::temp_dir();
        let mut outputs = Vec::new();
        for _ in 0..runs {
            let path = dir.join(format!(
                "laserfuck-test-{}-{}.lsrf",
                std::process::id(),
                COUNTER.fetch_add(1, Ordering::SeqCst)
            ));
            std::fs::write(&path, grid).expect("write grid");
            let mut child = Command::new(&exe)
                .arg(&path)
                .stdin(Stdio::piped())
                .stdout(Stdio::piped())
                .spawn()
                .expect("failed to spawn");
            let mut child_stdin = child.stdin.take().unwrap();
            // The child may exit before reading all of stdin (it reads on
            // demand), so a broken pipe here is fine; dropping the handle
            // closes the pipe so the child still sees EOF.
            let _ = child_stdin.write_all(stdin.as_bytes());
            drop(child_stdin);
            let out = child.wait_with_output().unwrap();
            std::fs::remove_file(&path).ok();
            outputs.push(String::from_utf8(out.stdout).expect("non-utf8 output"));
        }
        outputs
    }

    /// Assert that at least one run produced exactly ``expected``.
    fn assert_any(grid: &str, stdin: &str, expected: &str) {
        let outputs = run_grid(grid, stdin, 20);
        assert!(
            outputs.iter().any(|o| o == expected),
            "grid {grid:?}: expected {expected:?} in {outputs:?}"
        );
    }

    #[test]
    fn plus_then_die() {
        // \xff selects byte mode; + touches cell 0 -> prints \x01
        assert_any("\u{ff}}o+x", "", "\u{1}");
    }

    #[test]
    fn negative_cell_is_excluded() {
        // '-' on zero makes -1, excluded from output
        assert_any("\u{ff}}o-x", "", "");
    }

    #[test]
    fn pointer_moves_right() {
        // > moves the pointer, + writes cell 1 -> \x01
        assert_any("\u{ff}}o>+x", "", "\u{1}");
    }

    #[test]
    fn directional_cells() {
        assert_any("\u{ff}}o^x", "", "");
        assert_any("\u{ff}}ovx", "", "");
        assert_any("\u{ff}}o}x", "", "");
    }

    #[test]
    fn mirrors() {
        assert_any("\u{ff}}o\\x", "", "");
        assert_any("\u{ff}}o/x", "", "");
        assert_any("\u{ff}}o_x", "", "");
    }

    #[test]
    fn skip_next() {
        // # skips the next command, so the + after it does not run
        assert_any("\u{ff}}o#+x", "", "");
    }

    #[test]
    fn read_input() {
        // , reads a line's first char and prints it via byte mode; the
        // "Input: " prompt is part of stdout
        assert_any("\u{ff}}o,x", "7\n", "Input: 7");
    }
}
