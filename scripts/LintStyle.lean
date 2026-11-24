import Mathlib.Tactic.Linter.TextBased

open Lean Lean.Linter Mathlib.Linter.TextBased

def main (args : List String) : IO UInt32 := do
  unless args.isEmpty do
    throw <| IO.userError "Usage: lake exe lint-style (read-only; no options)"
  let result ← IO.Process.output { cmd := "git", args := #["ls-files", "-z", "--", "src/*.lean"] }
  unless result.exitCode == 0 do
    throw <| IO.userError result.stderr
  let files := result.stdout.splitOn "\x00" |>.filter (!·.isEmpty)
  if files.isEmpty then
    throw <| IO.userError "lint-style: no tracked Lean sources under src/"
  let paths := files.toArray.map fun file => ((file.dropEnd 5).toString.replace "/" ".").toName
  let modules := files.toArray.map fun file =>
    (((file.drop 4).toString.dropEnd 5).toString.replace "/" ".").toName
  let exceptionsFile : System.FilePath := "scripts/nolints-style.txt"
  let exceptions ← if ← exceptionsFile.pathExists then IO.FS.lines exceptionsFile else pure #[]
  let legacyNames := exceptions.filterMap fun line => do
    let name ← line.dropPrefix? "-- module-name: "
    pure name.toString.toName
  let opts : LinterOptions := { toOptions := {}, linterSets := {} }
  IO.println s!"Checking {files.length} tracked Lean sources"
  let errors ← lintModules opts exceptions paths .humanReadable false
  let checkedNames := modules.filter (!legacyNames.contains ·)
  let names ← modulesNotUpperCamelCase opts checkedNames
  let forbidden ← modulesOSForbidden opts checkedNames
  return min (errors + names.toUInt32 + forbidden.toUInt32) 125
