use std::io::{self, Write};
use ::core::fmt::Display;
use std::char;
use std::env;
use std::fs;

fn print<T : Display>(value: T) {
    print!("{}", value);
    io::stdout()
        .flush()
        .unwrap();
}

fn run(text: Vec<char>) {
    let mut stk = Vec::new();
    let mut jmp = Vec::new();
    let mut out = false;
    let mut ind = 0;
    let mut acc = 0;

    while ind < text.len() {
        match text[ind] {
            'O' => stk.push(0),
            'I' => stk.push(1),
            'A' => acc = stk.pop()
                .expect("empty stack"),
            'S' => {
                let n = stk.len();
                stk.swap(n - 1, n - 2);
            }
            '+' => acc += 2,
            '-' => acc -= 2,
            'x' => acc *= 2,
            'P' => stk.push(acc),
            'o' => {
                out = true;
                let val = stk.last()
                    .expect("empty stack");
                
                if let Some(c)
                        = char::from_u32(
                            *val as u32) {
                    print(c);
                } else {
                    print(val);
                }
            }
            'i' => {
                let mut val = String::new();

                if out {
                    print('\n');
                    out = false;
                }

                while val.trim() == "" {
                    print("Input: ");
                    io::stdin()
                        .read_line(&mut val)
                        .unwrap();
                }

                stk.push(
                    val.chars()
                        .next()
                        .unwrap()
                    as i128
                );
            }
            '>' => {
                if acc == 0 || acc == 1 {
                    let mut num = 1;

                    while num > 0 {
                        ind += 1;

                        match text[ind] {
                            '>' => num += 1,
                            '<' => num -= 1,
                            _ => ()
                        }
                    }
                } else {
                    jmp.push(ind - 1);
                }
            }
            '<' => ind = jmp.pop()
                .expect("missing bracket"),
            _ => ()
        }
        
        ind += 1;
    }
}

fn main() {
    let args: Vec<String>
        = env::args().collect();
    let text = fs::read_to_string(&args[1])
        .expect("invalid file")
        .chars()
        .collect();
    
    run(text);
}
