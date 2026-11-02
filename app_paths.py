"""ที่อยู่ไฟล์ของโปรแกรม: ไฟล์ที่มากับโปรแกรมอ่านอย่างเดียว ส่วนข้อมูลผู้ใช้แยกโฟลเดอร์เมื่อติดตั้ง."""
import os
from pathlib import Path
import sys

APP_NAME = "FaceCheck Attendance"


def is_packaged():
    return getattr(sys, "frozen", False)


def resource_dir():
    return Path(sys._MEIPASS) if is_packaged() else Path(__file__).resolve().parent


def user_data_dir():
    override = os.environ.get("FACECHECK_DATA_DIR")
    if override:
        return Path(override)
    # รันจากซอร์สโค้ดใช้โฟลเดอร์ data เดิม เพื่อให้ข้อมูลที่มีอยู่ทำงานต่อได้
    if not is_packaged():
        return resource_dir() / "data"
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / APP_NAME


def restore_system_libraries():
    """ตัวแพ็กบน Linux เปลี่ยน LD_LIBRARY_PATH ต้องคืนค่าก่อนเปิดเบราว์เซอร์หรือโปรแกรมของระบบ."""
    if not is_packaged():
        return
    original = os.environ.pop("LD_LIBRARY_PATH_ORIG", None)
    os.environ.pop("LD_LIBRARY_PATH", None)
    if original:
        os.environ["LD_LIBRARY_PATH"] = original


RESOURCE_DIR = resource_dir()
DATA_DIR = user_data_dir()
FACE_DETECTOR_PATH = RESOURCE_DIR / "data" / "haarcascade_frontalface_default.xml"
MODEL_PATH = RESOURCE_DIR / "models" / "face_recognition_sface_2021dec.onnx"
# ไม่อยู่ใน repo: ตอน build ตัวติดตั้ง GitHub Actions จะเขียนไฟล์นี้จาก secret
OAUTH_CLIENT_PATH = RESOURCE_DIR / "oauth_client.json"
