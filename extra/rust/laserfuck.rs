use rand::Rng;
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
    let mut rng = rand::thread_rng();
    let mut lsrs = Vec::new();
    let mut jmp = false;
    let mut ind = 0;
    let mut ptr = 0;

    let len = text.len();
    let new = (0, false);
    let mut tape = vec![new];

    for (k, v) in text.iter().enumerate() {
        if let Some(n) = v.iter().position(|&c| c == 'o') {
            if lsrs.len() > 0 {
                return;
            } else {
                let num = rng.gen_range(0..4);
                let lsr = Laser(k, n, num);
                lsrs.push(lsr);
            }
        }
    }

    while lsrs.len() > 0 {
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
                let n = rng.gen_range(0..2);
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

    let out = text.len() > 0 && text[0].len() > 0 && text[0][0] == '\u{FF}';
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
                    print!("\n");
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
