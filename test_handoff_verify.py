import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
import zipfile


SCRIPT = Path(__file__).with_name("handoff_verify.py")


class HandoffVerifyTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(TemporaryDirectory())
        root = Path(self.temp)
        self.source = root / "source folder"
        self.copy = root / "copy folder"
        (self.source / "空資料夾").mkdir(parents=True)
        (self.source / "檔案.bin").write_bytes(b"\x00\xff123")
        (self.source / "folder").mkdir()
        (self.source / "only-source.txt").write_bytes(b"original")
        shutil.copytree(self.source, self.copy)

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-X", "utf8", str(SCRIPT), *(str(arg) for arg in args)],
            capture_output=True,
            encoding="utf-8",
            check=False,
        )

    def test_match_includes_unicode_and_empty_directories(self):
        result = self.run_cli(self.source, self.copy)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "Directory trees match.")

    def test_reports_all_difference_types(self):
        (self.copy / "檔案.bin").write_bytes(b"\x00\xff124")
        (self.copy / "folder").rmdir()
        (self.copy / "folder").touch()
        (self.copy / "only-source.txt").unlink()
        (self.copy / "only-copy.txt").touch()
        (self.copy / "空資料夾").rmdir()

        result = self.run_cli(self.source, self.copy, "--json")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            "status": "different",
            "differences": [
                {"path": "folder", "kind": "type"},
                {"path": "only-copy.txt", "kind": "extra"},
                {"path": "only-source.txt", "kind": "missing"},
                {"path": "檔案.bin", "kind": "content"},
                {"path": "空資料夾", "kind": "missing"},
            ],
        })

    def test_invalid_and_overlapping_roots(self):
        for target in (self.copy / "missing", self.copy / "檔案.bin", self.source / "folder", self.source):
            with self.subTest(target=target):
                result = self.run_cli(self.source, target, "--json")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(json.loads(result.stdout)["status"], "error")

    def test_zip_reports_a_hidden_release_directory_dropped_during_packaging(self):
        hidden = self.source / "site" / ".export"
        hidden.mkdir(parents=True)
        (hidden / "index.html").write_text("export", encoding="utf-8")
        (hidden.parent / "readme.txt").write_text("site", encoding="utf-8")
        artifact = Path(self.temp) / "release.zip"

        for include_hidden in (True, False):
            with self.subTest(include_hidden=include_hidden):
                with zipfile.ZipFile(artifact, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    for path in self.source.rglob("*"):
                        relative = path.relative_to(self.source)
                        if path.is_dir() and any(path.iterdir()):
                            continue
                        if include_hidden or ".export" not in relative.parts:
                            archive.write(path, relative.as_posix())

                result = self.run_cli(self.source, artifact, "--json")
                expected = [] if include_hidden else [
                    {"path": "site/.export", "kind": "missing"},
                    {"path": "site/.export/index.html", "kind": "missing"},
                ]
                self.assertEqual(result.returncode, int(bool(expected)), result.stderr)
                self.assertEqual(json.loads(result.stdout)["differences"], expected)

    def test_rejects_zip_with_a_file_and_folder_at_the_same_path(self):
        artifact = Path(self.temp) / "ambiguous.zip"
        with zipfile.ZipFile(artifact, "w") as archive:
            archive.writestr("docs/readme", "text")
            archive.writestr("docs", "not a directory")
        result = self.run_cli(self.source, artifact, "--json")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("both a file and a directory", json.loads(result.stdout)["error"])

    @unittest.skipUnless(sys.platform == "win32", "Windows junction test")
    def test_windows_junction_is_reported_instead_of_followed(self):
        link = self.copy / "junction"
        created = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/j", str(link), str(self.source)],
            capture_output=True,
            check=False,
        )
        if created.returncode:
            self.skipTest("The test filesystem did not allow creating a junction")
        result = self.run_cli(self.source, self.copy)
        self.assertEqual(result.returncode, 2)
        self.assertIn("Unsupported entry", result.stderr)


if __name__ == "__main__":
    unittest.main()
