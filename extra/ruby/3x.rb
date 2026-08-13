# frozen_string_literal: true

# 3x interpreter.
#
# Per the esolangs wiki, stack items can be any rational number: ``3`` pushes
# the rational 3, ``x`` computes the exact rational ``(A-B)/C``, and ``?``
# reads a number (integer, decimal, or fraction like ``1/3``).  Variables are
# named by arbitrary rationals (Ruby hashes keep distinct keys for e.g. 1 and
# 1/2), so no truncation happens anywhere.
#
# Invocation: `ruby 3x.rb <program-file>`; program text from `ARGV[0]`.
# Input: `?` reads from stdin.  A command that pops an empty stack exits
# with status 3 (invalid operation; the cross-check convention is 0 =
# success, 2 = malformed program, 3 = invalid operation).  The wiki leaves
# empty-stack behavior undefined; this implementation treats it as an error.

code = File.read(ARGV[0])
ARGV.clear
line = ""
ptr = []
stk = []
var = {}
ind = 0
var.default = Rational(3)

def pop(stk)
  raise SystemExit.new(3, "empty stack") if stk.empty?

  stk.pop
end

def top(stk)
  raise SystemExit.new(3, "empty stack") if stk.empty?

  stk[-1]
end

def find(str, sym)
  num = 1
  while num.nonzero?
    sym += 1
    raise SystemExit.new(3, "unmatched (") if sym >= str.length

    case str[sym]
    when "("
      num += 1
    when ")"
      num -= 1
    end
  end
  sym
end

while (c = code[ind])
  case c
  when "3"
    stk.push(Rational(3))
  when "x"
    x = pop(stk)
    y = pop(stk)
    z = pop(stk)
    raise SystemExit.new(3, "division by zero") if z.zero?

    n = (x - y) / z
    stk.push(n)
  when "?"
    print "#{line}Input: "
    stk.push(Rational(gets.strip))
    line = ""
  when "!"
    n = pop(stk)
    print (n.denominator == 1) ? n.to_i : n
    line = 10.chr
  when "v"
    n = pop(stk)
    var[pop(stk)] = n
  when "^"
    stk.push(var[pop(stk)])
  when "#"
    x = pop(stk)
    y = pop(stk)
    stk.push(x).push(y)
  when "("
    if top(stk).nonzero?
      ptr.push(ind)
    else
      ind = find(code, ind)
    end
  when ")"
    if top(stk).nonzero?
      raise SystemExit.new(3, "unmatched )") if ptr.empty?

      ind = ptr[-1]
    else
      ptr.pop
    end
  when "["
    if (close = code.index("]", ind))
      print code[(ind + 1)...close]
      ind = close
    end
    line = 10.chr
  end
  ind += 1
end
