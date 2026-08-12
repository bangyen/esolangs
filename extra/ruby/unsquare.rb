# frozen_string_literal: true

# Unsquare interpreter (Ruby cross-check; see README "Extra
# Implementations").
#
# A stack-based language with an accumulator.  `O`/`I` push 0/1, `A` pops
# the stack into the accumulator, `S` swaps the top two, `+`/`-`/`x` add
# 2/subtract 2/double the accumulator, `P` pushes it, `o` prints the top of
# the stack as a byte, `i` reads a line of input pushing its first
# character, and `>`/`<` are a loop bracket pair that jump forward/back to
# the matching bracket when the accumulator is neither 0 nor 1.
#
# Error handling: popping an empty stack or an unmatched `<` is an invalid
# operation (nil arithmetic / nil indexing).  `o` always treats the top as a
# character, unlike the Rust cross-check which falls back to a decimal value
# when it is not a valid character.
#
# Input: the program file is `ARGV[0]`; `i` reads from stdin.

code = File.read(ARGV[0])
ARGV.clear

ind = acc = 0
line = ''
ptr = []
stk = []

def find(str, sym)
  num = 1
  while num.nonzero?
    case str[sym += 1]
    when '>'
      num += 1
    when '<'
      num -= 1
    end
  end
  sym
end

while (c = code[ind])
  case c
  when 'O'
    stk.push(0)
  when 'I'
    stk.push(1)
  when 'A'
    acc = stk.pop
  when 'S'
    x = stk.pop
    y = stk.pop
    stk.push(x).push(y)
  when '+'
    acc += 2
  when '-'
    acc -= 2
  when 'x'
    acc *= 2
  when 'P'
    stk.push(acc)
  when 'o'
    print stk[-1].chr
    line = 10.chr
  when 'i'
    print "#{line}Input: "
    stk.push(gets[0].ord)
    line = ''
  when '>'
    if acc.nonzero? && (acc != 1)
      ptr.push(ind)
    else
      ind = find(code, ind)
    end
  when '<'
    if acc.nonzero? && (acc != 1)
      ind = ptr[-1]
    else
      ptr.pop
    end
  end
  ind += 1
end
