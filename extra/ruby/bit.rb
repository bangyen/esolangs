# frozen_string_literal: true

# bit~ interpreter (Ruby cross-check; see README "Extra Implementations").
#
# An 8-cell bit pool with a pointer: `~` flips the current bit, `>`/`<` move
# the pointer (extending the pool on `>`), `)` reads a byte of input into the
# pool as 8 bits, `(` prints the pool as a byte, and `{`/`}` are a loop
# bracket pair: `{` jumps forward to the matching `}` when the current bit is
# zero, `}` jumps back to the matching `{` when it is nonzero.
#
# Invocation: `ruby bit.rb <program-file>`; program text from `ARGV[0]`.
# Input: the program file is `ARGV[0]`; `)` reads from stdin and raises
# `input exhausted` at EOF (the wiki leaves EOF undefined).

code = File.read(ARGV[0])
tape = [cell = i = 0] * 8
line = ''
ARGV.clear

def find(str, sym, dir)
  num = dir
  while num.nonzero?
    case str[sym += dir]
    when '{'
      num += 1
    when '}'
      num -= 1
    end
  end
  sym
end

while (c = code[i])
  case c
  when '~'
    tape[cell] ^= 1
  when '>'
    cond = cell + 8 > tape.size
    tape.push(0) if cond
    cell += 1
  when '<'
    cell -= 1 if cell.nonzero?
  when ')'
    print "#{line}Input: "
    inp = gets
    raise 'input exhausted' if inp.nil?

    val = '0' * 8 + inp[0].ord.to_s(2)
    tape[cell..cell + 7] =
      val[-8..].chars.map(&:to_i)
    line = ''
  when '('
    val = tape[cell..cell + 7]
    print val.join.to_i(2).chr
    line = 10.chr
  when '{'
    i = find(code, i, 1) \
    if tape[cell].zero?
  when '}'
    i = find(code, i, -1) \
    unless tape[cell].zero?
  end
  i += 1
end
