import Esolangs.Excon

/-- EXCON executable: read the program from the file given as the first
argument (default ``test.txt``) and run it. -/
def main (args : List String) : IO Unit := do
  let path := args.getD 0 "test.txt"
  let c ← IO.FS.readFile path
  Excon.run c.length (String.Legacy.mkIterator c) c.front Excon.empty_list 7 ""
