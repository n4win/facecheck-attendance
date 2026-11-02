import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import app_paths


class AppPathsTests(unittest.TestCase):
    def test_source_run_keeps_project_data_folder(self):
        with patch.dict(os.environ):
            os.environ.pop("FACECHECK_DATA_DIR", None)
            self.assertEqual(app_paths.user_data_dir(), Path(app_paths.__file__).resolve().parent / "data")

    def test_packaged_run_uses_per_user_folder_on_each_system(self):
        home = Path("/home/tester")
        cases = (("linux", {"XDG_DATA_HOME": "/xdg"}, Path("/xdg") / app_paths.APP_NAME),
                 ("linux", {}, home / ".local/share" / app_paths.APP_NAME),
                 ("darwin", {}, home / "Library/Application Support" / app_paths.APP_NAME),
                 ("win32", {"APPDATA": "/appdata"}, Path("/appdata") / app_paths.APP_NAME))
        for platform, env, expected in cases:
            with patch.dict(os.environ, env, clear=True), patch.object(sys, "platform", platform), \
                 patch.object(sys, "frozen", True, create=True), patch.object(Path, "home", return_value=home):
                self.assertEqual(app_paths.user_data_dir(), expected)

    def test_packaged_resources_come_from_bundle(self):
        with patch.object(sys, "frozen", True, create=True), patch.object(sys, "_MEIPASS", "/bundle", create=True):
            self.assertEqual(app_paths.resource_dir(), Path("/bundle"))

    def test_override_wins(self):
        with patch.dict(os.environ, {"FACECHECK_DATA_DIR": "/custom"}):
            self.assertEqual(app_paths.user_data_dir(), Path("/custom"))


if __name__ == "__main__":
    unittest.main()
