import Esolangs.bfpda

/-- BF-PDA executable: read the program from the file given as the first
argument (default ``test.txt``) and run it. -/
def main (args : List String) : IO Unit := do
  let path := args.getD 0 "test.txt"
  let c ← IO.FS.readFile path
  Bfpda.run (String.Legacy.mkIterator c) c.front Bfpda.limit [] ""
