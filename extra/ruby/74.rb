# frozen_string_literal: true

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
