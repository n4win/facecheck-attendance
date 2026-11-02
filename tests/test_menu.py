import os
import sys
import unittest
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

    def test_self_check_refuses_to_run_against_real_data(self):
        with patch.dict(os.environ):
            os.environ.pop("FACECHECK_DATA_DIR", None)
            with patch("sys.stderr"):
                self.assertEqual(self_check.run("unused.txt", [], menu.tool_command), 2)
        self.assertFalse(os.path.exists("unused.txt"))


if __name__ == "__main__":
    unittest.main()
