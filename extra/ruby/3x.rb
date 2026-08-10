# frozen_string_literal: true

# 3x interpreter.
#
# Per the esolangs wiki, stack items can be any rational number: ``3`` pushes
# the rational 3, ``x`` computes the exact rational ``(A-B)/C``, and ``?``
# reads a number (integer, decimal, or fraction like ``1/3``).  Variables are
# named by arbitrary rationals (Ruby hashes keep distinct keys for e.g. 1 and
# 1/2), so no truncation happens anywhere.

code = File.read(ARGV[0])
ARGV.clear
line = ''
ptr = []
stk = []
var = {}
ind = 0
var.default = Rational(3)

def find(str, sym)
  num = 1
  while num.nonzero?
    case str[sym += 1]
    when '('
      num += 1
    when ')'
      num -= 1
    end
  end
  sym
end

while (c = code[ind])
  case c
  when '3'
    stk.push(Rational(3))
  when 'x'
    x = stk.pop
    y = stk.pop
    z = stk.pop
    n = (x - y) / z
    stk.push(n)
  when '?'
    print "#{line}Input: "
    stk.push(Rational(gets.strip))
    line = ''
  when '!'
    n = stk.pop
    print n.denominator == 1 ? n.to_i : n
    line = 10.chr
  when 'v'
    n = stk.pop
    var[stk.pop] = n
  when '^'
    stk.push(var[stk.pop])
  when '#'
    x = stk.pop
    y = stk.pop
    stk.push(x).push(y)
  when '('
    if stk[-1].nonzero?
      ptr.push(ind)
    else
      ind = find(code, ind)
    end
  when ')'
    if stk[-1].nonzero?
      ind = ptr[-1]
    else
      ptr.pop
    end
  when '['
    s = code[ind..]
    print s[/\[([^\]]*)\]/, 1]
    line = 10.chr
  end
  ind += 1
end
