import os
import tempfile
import unittest
from pathlib import Path

from ThemeTools import patch_asar_theme as theme


CSS_PATH = "webview/assets/app-shared-fixture.css"
RUNTIME_PATH = "webview/assets/index-fixture.js"
MAIN_PATH = ".vite/build/main-fixture.js"
BOOTSTRAP_PATH = ".vite/build/bootstrap-fixture.js"


def write_fixture(path, files):
    header = {"files": {}}
    offset = 0
    for name, data in files.items():
        node = header
        parts = name.split("/")
        for part in parts[:-1]:
            node = node["files"].setdefault(part, {"files": {}})
        node["files"][parts[-1]] = {"size": len(data), "offset": str(offset)}
        offset += len(data)
    header["files"]["native.node"] = {"size": 4, "unpacked": True}
    path.write_bytes(theme.encode_header(header) + b"".join(files.values()))


class PatchAsarTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="CyberCodex-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.asar = self.root / "app.asar"
        self.banner = self.root / "banner.jpg"
        self.city = self.root / "city.jpg"
        self.video = self.root / "UI_BackgroundMain.BGPlanet.webm"
        self.banner.write_bytes(b"banner image")
        self.city.write_bytes(b"city image")
        self.video.write_bytes(b"background video")
        (self.root / "UI_BackgroundMain.BGPlanet@2.webm").write_bytes(b"next video")
        self.files = {
            theme.TARGET_HTML: (
                b'<script src="./assets/index-fixture.js"></script>'
                b'<link href="./assets/app-shared-fixture.css">'
            ),
            CSS_PATH: b"body { color: white; }",
            RUNTIME_PATH: b"console.log('original');",
            MAIN_PATH: b"symbolColor:app.nativeTheme.shouldUseDarkColors?dark:light",
            BOOTSTRAP_PATH: (
                b"function core(){return process.platform===`win32`&&"
                b"settings({key:`codexWindowsAppContainedCore`})===`1`}"
                b"function launch(){let options={enableUpdater:settings.shouldIncludeUpdater(window)};}"
            ),
            "unchanged.bin": bytes(range(256)),
        }
        write_fixture(self.asar, self.files)

    def apply_theme(self):
        theme.patch_asar(
            str(self.asar), str(self.banner), "-", str(self.city), str(self.video), "-"
        )

    def test_patch_preserves_files_backup_and_repeatability(self):
        original = self.asar.read_bytes()
        self.apply_theme()
        patched = self.asar.read_bytes()
        backup = Path(str(self.asar) + ".official")
        self.assertEqual(backup.read_bytes(), original)
        header, start = theme.read_asar(self.asar)
        for path in (theme.TARGET_HTML, CSS_PATH, RUNTIME_PATH):
            data = theme.read_packed_file(self.asar, header, start, path)
            self.assertTrue(data.startswith(self.files[path]))
            self.assertGreater(len(data), len(self.files[path]))
        css = theme.read_packed_file(self.asar, header, start, CSS_PATH)
        runtime = theme.read_packed_file(self.asar, header, start, RUNTIME_PATH)
        self.assertIn(b"CYBERCODEX_READABLE_NEON_V10", css)
        self.assertIn(b"data:image/jpeg;base64,", css)
        self.assertIn(b"data:video/webm;base64,", runtime)
        self.assertIn(b"cybercodex-review-action", runtime)
        self.assertNotIn(b"${sources}", runtime)
        self.assertIn(
            b"symbolColor:dark",
            theme.read_packed_file(self.asar, header, start, MAIN_PATH),
        )
        bootstrap = theme.read_packed_file(self.asar, header, start, BOOTSTRAP_PATH)
        self.assertIn(b"function core(){return!1}", bootstrap)
        self.assertIn(b"enableUpdater:!1", bootstrap)
        self.assertEqual(len(bootstrap), len(self.files[BOOTSTRAP_PATH]))
        self.assertEqual(
            theme.read_packed_file(self.asar, header, start, "unchanged.bin"),
            self.files["unchanged.bin"],
        )
        self.assertEqual(header["files"]["native.node"], {"size": 4, "unpacked": True})
        self.apply_theme()
        self.assertEqual(self.asar.read_bytes(), patched)
        self.assertEqual(backup.read_bytes(), original)

    def test_unknown_bootstrap_leaves_archive_intact(self):
        self.files[BOOTSTRAP_PATH] = b"const unsupportedVersion = true;"
        write_fixture(self.asar, self.files)
        original = self.asar.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "startup gates"):
            self.apply_theme()
        self.assertEqual(self.asar.read_bytes(), original)
        self.assertEqual(Path(str(self.asar) + ".official").read_bytes(), original)
        self.assertEqual(list(self.root.glob("app-themed-*.asar")), [])

    def test_relative_video_path_is_not_duplicated(self):
        previous_directory = os.getcwd()
        try:
            os.chdir(self.root)
            videos = theme.discover_background_videos(self.video.name)
        finally:
            os.chdir(previous_directory)
        self.assertEqual(videos, [str(self.video), str(self.root / "UI_BackgroundMain.BGPlanet@2.webm")])


if __name__ == "__main__":
    unittest.main()
