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
