# EXCON interpreter (R cross-check; see README "Extra Implementations").
#
# An 8-cell bit pool with a pointer: ":" resets the pool and pointer, "^"
# flips the current bit, "<" moves the pointer down, and "!" prints the pool
# as a binary byte (MSB first).  The language is straight-line with no
# control flow.
#
# Deviations: the pool is indexed 1..8 with the pointer starting at 8 and "<"
# decrementing it with no bounds check, so a program with more than 7 "<"s
# runs off the pool rather than faulting (the Python interpreter raises
# HaltError instead).  R's stdout cannot carry a NUL byte, so "!" of an
# all-zero pool prints nothing rather than the NUL the Python interpreter
# writes.  "cat" is used instead of a single output channel.
#
# Input: the program file is the first command-line argument; the language
# has no input command.

file <- commandArgs(trailingOnly = TRUE)[1]
size <- file.info(file)$size
strg <- readChar(file, size)
syms <- strsplit(strg, "")[[1]]


tape <- rep(c(0), times = 8)
cell <- 8


bin <- function(arr) {
  sum <- 0
  for (k in c(1:8))
  if (tape[k])
    sum <- sum + 2 ^ (8 - k)
  sum
}


for (char in syms) {
  if (char == ":") {
    cell <- 8
    tape <- rep(c(0), times = 8)
  } else if (char == "^") {
    tape[cell] <- 1 - tape[cell]
  } else if (char == "!") {
    num <- bin(tape)
    cat(intToUtf8(num))
  } else if (char == "<") {
    cell <- cell - 1
  }
}
