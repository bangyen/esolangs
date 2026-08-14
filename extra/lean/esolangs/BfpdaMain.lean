import Esolangs.bfpda

/-- BF-PDA executable: read the program from the file given as the first
argument (default ``test.txt``) and run it, exiting with the interpreter's
status (3 on an empty-stack operation). -/
def main (args : List String) : IO UInt32 := do
  let path := args.getD 0 "test.txt"
  let c ← IO.FS.readFile path
  let code ← Bfpda.run (String.Legacy.mkIterator c) c.front Bfpda.limit [] ""
  pure code.toUInt32
