"""Run after `lake build lint-style`: python3 scripts/tests/test_lint_style.py."""

from pathlib import Path
import subprocess
import tempfile
import unittest


EXECUTABLE = Path(__file__).resolve().parents[2] / ".lake/build/bin/lint-style"
VALID = b"example : True := by trivial\n"


class LintStyleTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)

    def track(self, name, content=VALID):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        subprocess.run(["git", "add", "--", name], cwd=self.root, check=True)

    def check(self):
        return subprocess.run([str(EXECUTABLE)], cwd=self.root, capture_output=True, text=True)

    def test_leaf_modules_and_untracked_files(self):
        self.track("src/Example/Leaf.lean")
        (self.root / "src/Example/Untracked.lean").write_text("def ũ := 0\n", encoding="utf-8")
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Checking 1 tracked Lean sources", result.stdout)

    def test_empty_checkout_fails(self):
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no tracked Lean sources", result.stdout + result.stderr)

    def test_violations_fail(self):
        for name, content, diagnostic in [
            ("src/Example/Leaf.lean", VALID.replace(b"\n", b"\r\n"), "windows line endings"),
            ("src/Example/Leaf.lean", b"example : True := by trivial ; done\n", "space before a semicolon"),
            ("src/Example/Leaf.lean", "def ũ := 0\n".encode(), "not on the allowlist"),
            ("src/Example/lowerCase.lean", VALID, "UpperCamelCase"),
            ("src/Example/Bad'Name.lean", VALID, "non-ASCII-alphanumeric"),
            ("src/Example/Valid₂.lean", VALID, "Example.Valid₂"),
            ("src/Example/CON.lean", VALID, "forbidden in Windows filenames"),
        ]:
            with self.subTest(name=name, diagnostic=diagnostic):
                self.track(name, content)
                result = self.check()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(diagnostic, result.stdout + result.stderr)

    def test_exceptions_are_scoped(self):
        self.track("src/Example/legacy.lean", "def ũ := 0\n".encode())
        exceptions = self.root / "scripts/nolints-style.txt"
        exceptions.parent.mkdir()
        exceptions.write_text(
            "-- module-name: Example.legacy\n"
            "src/Example/legacy.lean : line 1 : ERR_UNICODE : This line contains a unicode character "
            "that is not on the allowlist 'ũ' (U+0169). For adding new symbols see "
            "`Mathlib.Linter.TextBased.UnicodeLinter.othersInMathlib`.\n",
            encoding="utf-8",
        )
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.track("src/Example/Other.lean", "def ũ := 0\n".encode())
        result = self.check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("src/Example/Other.lean", result.stdout)
        self.track("src/Example/another.lean")
        result = self.check()
        self.assertIn("Example.another", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
