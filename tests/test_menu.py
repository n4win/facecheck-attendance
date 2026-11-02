import os
import sys
import unittest
import unittest.mock
from unittest.mock import patch

import menu
import self_check


class MenuTests(unittest.TestCase):
    def test_every_menu_item_can_be_dispatched(self):
        for _, name in menu.MENU_ITEMS + (("ตั้งค่า", "settings_window"),):
            target = "open_window" if name == "kru_check" else "main"
            with patch(f"{name}.{target}") as opened:
                menu.run_tool(name)
            opened.assert_called_once_with()

    def test_unknown_tool_is_rejected(self):
        with self.assertRaises(SystemExit):
            menu.run_tool("rm")

    def test_source_run_launches_menu_script_with_python(self):
        command = menu.tool_command("studata")
        self.assertEqual(command[0], sys.executable)
        self.assertTrue(command[1].endswith("menu.py"))
        self.assertEqual(command[2:], ["--tool", "studata"])

    def test_packaged_run_relaunches_itself_without_script_path(self):
        with patch.object(menu, "is_packaged", return_value=True):
            self.assertEqual(menu.tool_command("scanstu"), [sys.executable, "--tool", "scanstu"])

    def test_attendance_windows_ask_for_sign_in_first(self):
        with patch.object(menu.google_settings, "is_configured", return_value=False), \
             patch.object(menu.messagebox, "askyesno", return_value=True) as ask, \
             patch.object(menu.subprocess, "Popen") as popen, patch.object(menu, "tool_command", side_effect=lambda name: [name]):
            root = unittest.mock.Mock()
            menu.open_script(root, "scanstu")
        ask.assert_called_once()
        popen.assert_called_once_with(["settings_window"])

    def test_declining_sign_in_opens_nothing_and_other_windows_stay_open_to_use(self):
        with patch.object(menu.google_settings, "is_configured", return_value=False), \
             patch.object(menu.messagebox, "askyesno", return_value=False), \
             patch.object(menu.subprocess, "Popen") as popen, patch.object(menu, "tool_command", side_effect=lambda name: [name]):
            root = unittest.mock.Mock()
            menu.open_script(root, "kru_check")
            popen.assert_not_called()
            menu.open_script(root, "add_face_student")
            popen.assert_called_once_with(["add_face_student"])

    def test_self_check_refuses_to_run_against_real_data(self):
        with patch.dict(os.environ):
            os.environ.pop("FACECHECK_DATA_DIR", None)
            with patch("sys.stderr"):
                self.assertEqual(self_check.run("unused.txt", [], menu.tool_command), 2)
        self.assertFalse(os.path.exists("unused.txt"))


if __name__ == "__main__":
    unittest.main()
