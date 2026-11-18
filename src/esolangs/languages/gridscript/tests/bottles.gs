#99 BOTTLES OF BEER.

@width 7
@height 39

(1,1):START
(3,1):STORE 99
(5,1):GO EAST
(7,1):GO SOUTH
(7,3):PRINT
(7,5):PRINT " bottles of beer on the wall,"
(7,7):PRINT NEWLINE
(7,9):PRINT
(7,11):PRINT " bottles of beer."
(7,13):PRINT NEWLINE
(7,15):PRINT "Take one down and pass it around,"
(7,17):PRINT NEWLINE
(7,19):SWITCH =1
(7,21):PRINT
(7,23):PRINT " bottles of beer on the wall!"
(7,25):DECREMENT
(7,27):GO WEST
(5,27):GO NORTH
(5,25):PRINT NEWLINE
(5,23):PRINT NEWLINE
(3,19):GO SOUTH
(3,21):PRINT "1 bottle of beer on the wall!"
(3,23):PRINT NEWLINE
(3,25):PRINT NEWLINE
(3,27):PRINT "1 bottle of beer on the wall,"
(3,29):PRINT NEWLINE
(3,31):PRINT "1 bottle of beer"
(3,33):PRINT NEWLINE
(3,35):PRINT "Take one down and pass it around,"
(3,37):PRINT NEWLINE
(3,39):PRINT "No more bottles of beer on the wall."
