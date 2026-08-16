//! Shared I/O helpers for the cross-check interpreters.
//!
//! Several interpreters read line-based input from stdin and print a
//! leading-newline-then-`Input: ` prompt before each read (matching the
//! Python interpreters' `IO` layer).  The prompt and read helpers are the
//! same in each, so they live here.
//!
//! Each binary is its own crate, so a helper a given binary does not use is
//! dead code in that build; the allow is the price of sharing the module.

#![allow(dead_code)]

use std::io::{self, BufRead, Write};

/// Print a newline (if the previous command printed), then an `Input: `
/// prompt, and mark that a prompt is now pending.
pub fn prompt(out: &mut bool) {
    let mut stdout = io::stdout();
    if *out {
        stdout.write_all(b"\n").unwrap();
    }
    stdout.write_all(b"Input: ").unwrap();
    stdout.flush().unwrap();
    *out = false;
}

/// Read one line from stdin, or None on EOF.
pub fn read_line() -> Option<Vec<u8>> {
    let mut stdin = io::stdin().lock();
    let mut line: Vec<u8> = Vec::new();
    if stdin.read_until(b'\n', &mut line).unwrap_or(0) == 0 {
        return None;
    }
    Some(line)
}
