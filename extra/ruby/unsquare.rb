# frozen_string_literal: true

# Unsquare interpreter (Ruby cross-check; see README "Extra
# Implementations").
#
# A stack-based language with an accumulator.  `O`/`I` push 0/1, `A` pops
# the stack into the accumulator, `S` swaps the top two, `+`/`-`/`x` add
# 2/subtract 2/double the accumulator, `P` pushes it, `o` prints the top of
# the stack as a character (or a decimal value when it is not a valid code
# point), `i` reads a line of input pushing its first character, and
# `>`/`<` are a loop bracket pair: `>` jumps forward to the matching `<`
# when the accumulator is 0 or 1, and `<` jumps back to the matching `>`
# when it is not 0 nor 1.
#
# Error handling: popping an empty stack, a swap with fewer than two
# elements, an `o` on an empty stack, an unmatched `<`, a `>` with no
# matching `<`, or an exhausted input exits with status 3 (invalid
# operation, matching the Rust and Python cross-checks and the 0 = success /
# 2 = malformed / 3 = invalid-op convention); `i` re-prompts on blank input.
#
# Invocation: `ruby unsquare.rb <program-file>`; program text from `ARGV[0]`.
# Input: the program file is `ARGV[0]`; `i` reads from stdin.

code = File.read(ARGV[0])
ARGV.clear

ind = acc = 0
line = ""
ptr = []
stk = []

def pop(stk)
  raise SystemExit.new(3, "empty stack") if stk.empty?

  stk.pop
end

def find(str, sym)
  num = 1
  while num.nonzero?
    sym += 1
    raise SystemExit.new(3, "unmatched >") if sym >= str.length

    case str[sym]
    when ">"
      num += 1
    when "<"
      num -= 1
    end
  end
  sym
end

def print_top(stk)
  raise SystemExit.new(3, "empty stack") if stk.empty?

  v = stk[-1]
  if v >= 0 && v <= 0x10FFFF && !(0xD800..0xDFFF).include?(v)
    print v.chr(Encoding::UTF_8)
  else
    print v
  end
end

while (c = code[ind])
  case c
  when "O"
    stk.push(0)
  when "I"
    stk.push(1)
  when "A"
    acc = pop(stk)
  when "S"
    raise SystemExit.new(3, "empty stack") if stk.size < 2

    x = pop(stk)
    y = pop(stk)
    stk.push(x).push(y)
  when "+"
    acc += 2
  when "-"
    acc -= 2
  when "x"
    acc *= 2
  when "P"
    stk.push(acc)
  when "o"
    line = 10.chr
    print_top(stk)
  when "i"
    print "#{line}Input: "
    val = gets
    raise SystemExit.new(3, "input exhausted") if val.nil?

    # \p{Space} is Unicode whitespace, matching the Rust and Python
    # references' trim/strip (Ruby's String#strip also drops NUL bytes)
    while val =~ /\A\p{Space}*\z/
      print "#{line}Input: "
      val = gets
      raise SystemExit.new(3, "input exhausted") if val.nil?
    end

    stk.push(val[0].ord)
    line = ""
  when ">"
    if acc.nonzero? && (acc != 1)
      ptr.push(ind)
    else
      ind = find(code, ind)
    end
  when "<"
    if acc.nonzero? && (acc != 1)
      raise SystemExit.new(3, "unmatched <") if ptr.empty?

      ind = ptr[-1]
    else
      raise SystemExit.new(3, "unmatched <") if ptr.empty?

      ptr.pop
    end
  end
  ind += 1
end
