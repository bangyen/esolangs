# frozen_string_literal: true

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
