"""เข้าสู่ระบบ Google ของผู้ใช้แต่ละคน: ผลเช็คชื่ออยู่ในชีตของเขาเอง และ token อยู่ใน keychain ของระบบ."""
import json

from app_paths import OAUTH_CLIENT_PATH, restore_system_libraries
import google_settings

# drive.file เข้าถึงได้เฉพาะไฟล์ที่ใช้กับโปรแกรมนี้ ไม่เห็นไฟล์อื่นใน Drive ของผู้ใช้
SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/drive.file"]
SHEET_TITLE = "FaceCheck Attendance"
KEYRING_SERVICE = "FaceCheck Attendance"
KEYRING_USER = "google-refresh-token"
SIGN_IN_TIMEOUT_SECONDS = 300
FILES_URL = "https://www.googleapis.com/drive/v3/files"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
SHEET_MIME_TYPE = "application/vnd.google-apps.spreadsheet"
SUCCESS_PAGE = "เข้าสู่ระบบสำเร็จ กลับไปที่โปรแกรม FaceCheck Attendance ได้เลย และปิดหน้านี้ได้"


def client_config():
    try:
        config = json.loads(OAUTH_CLIENT_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ValueError("รุ่นนี้ยังไม่ได้ตั้งค่าการเข้าสู่ระบบ Google") from None
    if not isinstance(config, dict) or "client_id" not in config.get("installed", {}):
        raise ValueError("ไฟล์ตั้งค่าการเข้าสู่ระบบ Google ไม่ถูกต้อง")
    return config


def save_refresh_token(token):
    import keyring
    from keyring.errors import KeyringError
    try:
        keyring.set_password(KEYRING_SERVICE, KEYRING_USER, token)
    except (KeyringError, OSError) as exc:
        # ไม่เขียน token ลงไฟล์ธรรมดาแทน เพราะคนอื่นในเครื่องอาจนำไปเข้าถึงชีตได้
        raise ValueError(f"เก็บการเข้าสู่ระบบใน keychain ของเครื่องไม่ได้: {exc}") from None


def load_refresh_token():
    import keyring
    from keyring.errors import KeyringError
    try:
        return keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
    except (KeyringError, OSError) as exc:
        raise ValueError(f"อ่านการเข้าสู่ระบบจาก keychain ของเครื่องไม่ได้: {exc}") from None


def delete_refresh_token():
    import keyring
    from keyring.errors import KeyringError
    try:
        keyring.delete_password(KEYRING_SERVICE, KEYRING_USER)
    except (KeyringError, OSError):
        pass


def credentials_from_token(token):
    from google.oauth2.credentials import Credentials
    client = client_config()["installed"]
    return Credentials(None, refresh_token=token, token_uri=client["token_uri"], client_id=client["client_id"],
                       client_secret=client.get("client_secret"), scopes=SCOPES)


def stored_credentials():
    token = load_refresh_token()
    if not token:
        raise ValueError("กรุณาเข้าสู่ระบบ Google ใหม่อีกครั้งจากหน้าตั้งค่า")
    return credentials_from_token(token)


def authorize(credentials):
    import gspread
    client = gspread.authorize(credentials)
    client.set_timeout((10, 30))
    return client


def open_worksheet(spreadsheet_id):
    from google.auth.exceptions import RefreshError
    try:
        return authorize(stored_credentials()).open_by_key(spreadsheet_id).sheet1
    except RefreshError:
        raise ValueError("การเข้าสู่ระบบ Google หมดอายุหรือถูกยกเลิก กรุณาเข้าสู่ระบบใหม่จากหน้าตั้งค่า") from None


def run_browser_sign_in():
    from google_auth_oauthlib.flow import InstalledAppFlow
    restore_system_libraries()
    flow = InstalledAppFlow.from_client_config(client_config(), SCOPES)
    return flow.run_local_server(port=0, prompt="consent", access_type="offline", authorization_prompt_message="",
                                 success_message=SUCCESS_PAGE, timeout_seconds=SIGN_IN_TIMEOUT_SECONDS)


def account_email(session):
    response = session.get(USERINFO_URL, timeout=30)
    response.raise_for_status()
    return response.json().get("email", "")


def find_sheet_id(session):
    """เครื่องใหม่หรือเข้าสู่ระบบซ้ำต้องใช้ชีตเดิม ไม่สร้างไฟล์ซ้ำใน Drive."""
    response = session.get(FILES_URL, timeout=30, params={
        "q": f"mimeType='{SHEET_MIME_TYPE}' and name='{SHEET_TITLE}' and trashed=false",
        "orderBy": "modifiedTime desc", "fields": "files(id)", "pageSize": 1,
    })
    response.raise_for_status()
    files = response.json().get("files", [])
    return files[0]["id"] if files else None


def create_sheet(client):
    from attendance_sheets import HEADERS
    book = client.create(SHEET_TITLE)
    book.sheet1.update(range_name="A1:F1", values=[HEADERS], value_input_option="RAW")
    return book.id


def absence_system_installed(worksheet):
    from attendance_sessions import SESSION_SHEET
    return SESSION_SHEET in [tab.title for tab in worksheet.spreadsheet.worksheets()]


def connect_account(credentials):
    from google.auth.transport.requests import AuthorizedSession
    session = AuthorizedSession(credentials)
    client = authorize(credentials)
    spreadsheet_id = find_sheet_id(session) or create_sheet(client)
    worksheet = client.open_by_key(spreadsheet_id).sheet1
    return dict(spreadsheet_id=spreadsheet_id, account=account_email(session),
                auto_absence=absence_system_installed(worksheet))


def sign_in():
    credentials = run_browser_sign_in()
    if not credentials.refresh_token:
        raise ValueError("Google ไม่ได้ส่งสิทธิ์การใช้งานระยะยาว กรุณาลองเข้าสู่ระบบอีกครั้ง")
    details = connect_account(credentials)
    save_refresh_token(credentials.refresh_token)
    google_settings.save_account(**details)
    return details


def refresh_status():
    """ตรวจว่ายังเข้าถึงชีตได้ และติดตั้งระบบสรุปขาดเรียนแล้วหรือยัง โดยอ่านอย่างเดียว."""
    settings = google_settings.load()
    if settings is None or "spreadsheet_id" not in settings:
        raise ValueError("กรุณาเข้าสู่ระบบ Google ก่อน")
    installed = absence_system_installed(open_worksheet(settings["spreadsheet_id"]))
    google_settings.save_account(settings["spreadsheet_id"], settings.get("account", ""), installed)
    return installed


def sign_out():
    """ลบการเข้าสู่ระบบในเครื่องก่อน แล้วค่อยขอให้ Google ยกเลิก token ถ้าทำได้."""
    import requests
    token = load_refresh_token()
    google_settings.clear()
    delete_refresh_token()
    if token:
        try:
            requests.post(REVOKE_URL, data={"token": token}, timeout=10)
        except requests.RequestException:
            return False
    return True
