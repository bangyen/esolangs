import Esolangs.seventy_four

/-- 74 executable: read the program from the file given as the first
argument (default ``test.txt``) and run it. -/
def main (args : List String) : IO Unit := do
  let path := args.getD 0 "test.txt"
  let c ← IO.FS.readFile path
  SeventyFour.run (String.Legacy.mkIterator c) c.front true SeventyFour.limit ""
