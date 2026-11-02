"""ค่าการเชื่อม Google Sheets ของผู้ใช้แต่ละคน: บัญชีที่เข้าสู่ระบบ หรือไฟล์ key แบบขั้นสูง."""
import json
import os
from pathlib import Path

from app_paths import DATA_DIR

SETTINGS_PATH = DATA_DIR / "google_settings.json"
KEY_PATH = DATA_DIR / "google_service_account.json"


def is_configured():
    return SETTINGS_PATH.exists()


def load():
    """คืน None เมื่อยังไม่ได้เชื่อม ถ้าไฟล์เสียต้องแจ้งเตือน เพื่อไม่ให้ผู้ใช้เข้าใจว่าส่งข้อมูลสำเร็จ."""
    if not is_configured():
        return None
    try:
        settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"อ่านค่าการเชื่อม Google ไม่ได้ กรุณาตั้งค่าใหม่: {exc}") from None
    if isinstance(settings, dict) and str(settings.get("spreadsheet_id", "")).strip():
        return settings
    if not isinstance(settings, dict) or not str(settings.get("spreadsheet", "")).strip():
        raise ValueError("ค่าการเชื่อม Google ไม่ครบ กรุณาตั้งค่าใหม่")
    if not KEY_PATH.is_file():
        raise ValueError("ไม่พบไฟล์ key ของ Google กรุณาตั้งค่าใหม่")
    return settings


def absence_summary_enabled():
    try:
        settings = load()
    except ValueError:
        return False
    return settings is not None and bool(settings.get("auto_absence", True))


def key_email(path):
    """ตรวจว่าเป็น key ของ service account และคืนอีเมลที่ต้องแชร์ชีตให้."""
    try:
        key = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ValueError("อ่านไฟล์ key ไม่ได้ กรุณาเลือกไฟล์ JSON จาก Google Cloud") from None
    if not isinstance(key, dict) or key.get("type") != "service_account" or not key.get("client_email") or not key.get("private_key"):
        raise ValueError("ไฟล์นี้ไม่ใช่ key ของ service account")
    return key["client_email"]


def write_private(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(text)
    temporary.replace(path)


def save(spreadsheet, key_source=None, auto_absence=False):
    spreadsheet = spreadsheet.strip()
    if not spreadsheet:
        raise ValueError("กรุณาระบุชื่อหรือลิงก์ของ Google Sheet")
    if key_source is not None:
        key_email(key_source)
        write_private(KEY_PATH, Path(key_source).read_text(encoding="utf-8"))
    elif not KEY_PATH.is_file():
        raise ValueError("กรุณาเลือกไฟล์ key ของ service account")
    write_private(SETTINGS_PATH, json.dumps({"spreadsheet": spreadsheet, "auto_absence": auto_absence}, ensure_ascii=False, indent=2))


def save_account(spreadsheet_id, account, auto_absence=False):
    """บันทึกชีตของบัญชีที่เข้าสู่ระบบ ส่วน token อยู่ใน keychain ไม่อยู่ในไฟล์นี้."""
    KEY_PATH.unlink(missing_ok=True)
    write_private(SETTINGS_PATH, json.dumps({"spreadsheet_id": spreadsheet_id, "account": account, "auto_absence": auto_absence}, ensure_ascii=False, indent=2))


def clear():
    SETTINGS_PATH.unlink(missing_ok=True)
    KEY_PATH.unlink(missing_ok=True)
