import json
from pathlib import Path
import tempfile
import threading
import unittest
import unittest.mock
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

from google.auth.exceptions import RefreshError
from keyring.errors import PasswordSetError

import google_auth
import google_settings

CLIENT = {"installed": {"client_id": "client-id", "client_secret": "public-secret", "token_uri": "https://oauth2.googleapis.com/token",
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth", "redirect_uris": ["http://localhost"]}}


class AuthCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.dir = Path(folder.name)
        self.client_path = self.dir / "oauth_client.json"
        self.client_path.write_text(json.dumps(CLIENT), encoding="utf-8")
        self.store = {}
        for target, name, value in ((google_auth, "OAUTH_CLIENT_PATH", self.client_path),
                                    (google_settings, "SETTINGS_PATH", self.dir / "google_settings.json"),
                                    (google_settings, "KEY_PATH", self.dir / "key.json")):
            patcher = patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        for name, function in (("set_password", lambda _s, _u, value: self.store.update(token=value)),
                               ("get_password", lambda _s, _u: self.store.get("token")),
                               ("delete_password", lambda _s, _u: self.store.pop("token", None))):
            patcher = patch(f"keyring.{name}", side_effect=function)
            patcher.start()
            self.addCleanup(patcher.stop)


class ClientConfigTests(AuthCase):
    def test_build_without_client_explains_itself(self):
        self.client_path.unlink()
        with self.assertRaisesRegex(ValueError, "ยังไม่ได้ตั้งค่า"):
            google_auth.client_config()

    def test_wrong_client_type_is_rejected(self):
        self.client_path.write_text(json.dumps({"web": {}}), encoding="utf-8")
        with self.assertRaises(ValueError):
            google_auth.client_config()


class BrowserFlowTests(AuthCase):
    def test_browser_flow_asks_narrow_offline_access_and_works_without_console(self):
        seen = {}

        def browser_opens(url, **_):
            seen.update(parse_qs(urlparse(url).query))
            redirect = seen["redirect_uri"][0]
            threading.Thread(target=lambda: seen.update(page=urlopen(f"{redirect}?code=abc&state={seen['state'][0]}").read().decode("utf-8"))).start()
            return True

        browser = Mock(open=Mock(side_effect=browser_opens))
        with patch("webbrowser.get", return_value=browser), \
             patch("google_auth_oauthlib.flow.InstalledAppFlow.fetch_token", return_value={}), \
             patch("google_auth_oauthlib.flow.InstalledAppFlow.credentials", new_callable=unittest.mock.PropertyMock, return_value="credentials"), \
             patch("sys.stdout", None), patch("sys.stderr", None):
            self.assertEqual(google_auth.run_browser_sign_in(), "credentials")
        scopes = seen["scope"][0].split()
        self.assertIn("https://www.googleapis.com/auth/drive.file", scopes)
        self.assertNotIn("https://www.googleapis.com/auth/drive", scopes)
        self.assertNotIn("https://www.googleapis.com/auth/spreadsheets", scopes)
        self.assertEqual(seen["access_type"], ["offline"])
        self.assertIn("code_challenge", seen)
        self.assertTrue(seen["redirect_uri"][0].startswith("http://localhost:"))
        for _ in range(100):
            if "page" in seen:
                break
            threading.Event().wait(0.02)
        self.assertIn("เข้าสู่ระบบสำเร็จ", seen["page"])


class SignInTests(AuthCase):
    def session(self, files):
        session = Mock()
        session.get.side_effect = lambda url, **kwargs: Mock(
            json=lambda: {"files": files} if url == google_auth.FILES_URL else {"email": "teacher@example.test"})
        return session

    def connect(self, files):
        client = Mock()
        client.create.return_value.id = "new-id"
        client.open_by_key.return_value.sheet1.spreadsheet.worksheets.return_value = [Mock(title="ชีต1")]
        with patch("google.auth.transport.requests.AuthorizedSession", return_value=self.session(files)), \
             patch.object(google_auth, "authorize", return_value=client):
            return google_auth.connect_account("credentials"), client

    def test_first_sign_in_creates_sheet_with_headers(self):
        details, client = self.connect([])
        self.assertEqual(details, {"spreadsheet_id": "new-id", "account": "teacher@example.test", "auto_absence": False})
        client.create.assert_called_once_with(google_auth.SHEET_TITLE)
        self.assertEqual(client.create.return_value.sheet1.update.call_args.kwargs["range_name"], "A1:F1")

    def test_returning_user_gets_existing_sheet_and_no_duplicate(self):
        details, client = self.connect([{"id": "old-id"}])
        self.assertEqual(details["spreadsheet_id"], "old-id")
        client.create.assert_not_called()

    def test_search_skips_trashed_files(self):
        session = self.session([])
        google_auth.find_sheet_id(session)
        self.assertIn("trashed=false", session.get.call_args.kwargs["params"]["q"])

    def test_sign_in_keeps_token_out_of_files(self):
        details = {"spreadsheet_id": "id", "account": "teacher@example.test", "auto_absence": False}
        with patch.object(google_auth, "run_browser_sign_in", return_value=Mock(refresh_token="secret-refresh-token")), \
             patch.object(google_auth, "connect_account", return_value=details):
            google_auth.sign_in()
        self.assertEqual(self.store["token"], "secret-refresh-token")
        self.assertEqual(google_settings.load()["spreadsheet_id"], "id")
        for path in self.dir.iterdir():
            self.assertNotIn("secret-refresh-token", path.read_text(encoding="utf-8"))

    def test_failed_browser_sign_in_changes_nothing(self):
        with patch.object(google_auth, "run_browser_sign_in", side_effect=RuntimeError("denied")):
            with self.assertRaises(RuntimeError):
                google_auth.sign_in()
        self.assertFalse(google_settings.is_configured())
        self.assertEqual(self.store, {})

    def test_keychain_failure_never_falls_back_to_a_file(self):
        details = {"spreadsheet_id": "id", "account": "a", "auto_absence": False}
        with patch.object(google_auth, "run_browser_sign_in", return_value=Mock(refresh_token="secret-refresh-token")), \
             patch.object(google_auth, "connect_account", return_value=details), \
             patch("keyring.set_password", side_effect=PasswordSetError("locked")):
            with self.assertRaisesRegex(ValueError, "keychain"):
                google_auth.sign_in()
        self.assertFalse(google_settings.is_configured())

    def test_missing_refresh_token_is_reported(self):
        with patch.object(google_auth, "run_browser_sign_in", return_value=Mock(refresh_token=None)):
            with self.assertRaises(ValueError):
                google_auth.sign_in()


class UseAndSignOutTests(AuthCase):
    def test_revoked_access_asks_to_sign_in_again(self):
        self.store["token"] = "token"
        with patch.object(google_auth, "authorize", side_effect=RefreshError("invalid_grant")):
            with self.assertRaisesRegex(ValueError, "เข้าสู่ระบบใหม่"):
                google_auth.open_worksheet("id")

    def test_missing_token_asks_to_sign_in_again(self):
        with self.assertRaisesRegex(ValueError, "เข้าสู่ระบบ"):
            google_auth.open_worksheet("id")

    def test_status_check_updates_absence_flag_without_writing_to_sheet(self):
        google_settings.save_account("id", "teacher@example.test", False)
        sheet = Mock()
        sheet.spreadsheet.worksheets.return_value = [Mock(title="Attendance_Sessions")]
        with patch.object(google_auth, "open_worksheet", return_value=sheet):
            self.assertTrue(google_auth.refresh_status())
        self.assertTrue(google_settings.load()["auto_absence"])
        self.assertEqual([call[0] for call in sheet.method_calls if call[0] in ("update", "append_row", "delete_rows")], [])

    def test_sign_out_clears_this_machine_and_revokes(self):
        google_settings.save_account("id", "teacher@example.test")
        self.store["token"] = "token"
        with patch("requests.post") as post:
            self.assertTrue(google_auth.sign_out())
        post.assert_called_once()
        self.assertEqual(post.call_args.kwargs["data"], {"token": "token"})
        self.assertFalse(google_settings.is_configured())
        self.assertEqual(self.store, {})

    def test_sign_out_offline_still_clears_this_machine(self):
        import requests
        google_settings.save_account("id", "teacher@example.test")
        self.store["token"] = "token"
        with patch("requests.post", side_effect=requests.ConnectionError):
            self.assertFalse(google_auth.sign_out())
        self.assertEqual(self.store, {})
        self.assertFalse(google_settings.is_configured())


if __name__ == "__main__":
    unittest.main()
