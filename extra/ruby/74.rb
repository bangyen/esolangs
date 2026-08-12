# frozen_string_literal: true

# 74 interpreter (Ruby cross-check; see README "Extra Implementations").
#
# A one-bit tape language.  `0`/`1` prepend their bit to the output string,
# and `H` writes an `H` only if the output already starts with `0` (the first
# character written).  The program is scanned repeatedly; once the output
# starts with `H` the program prints it and halts.  A program whose output
# never starts with `H` loops forever.
#
# Invocation: `ruby 74.rb <program-file>`; program text from `ARGV[0]`.
# Input: the program file is `ARGV[0]`; the language has no input command.

code = File.read(ARGV[0]).chars
data = ''

loop do
  code.each do |c|
    case c
    when '0'
      data = "0#{data}"
    when '1'
      data = "1#{data}"
    when 'H'
      data.gsub!(/^0/, 'H0')
    end
  end
  break if data[0] == 'H'
end

print data
