# frozen_string_literal: true

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
    val = '0' * 8 + gets[0].ord.to_s(2)
    tape[cell..cell + 7] =
      val[-8..-1].chars.map(&:to_i)
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
