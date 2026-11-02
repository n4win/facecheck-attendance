# Build: pyinstaller packaging/facecheck.spec --distpath dist --workpath build
# Bundle only code, the face detector and the model. Never add a key or other files from data/.
from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_submodules, copy_metadata

ROOT = Path(SPECPATH).parent
# Written from a GitHub Actions secret when building a release; never committed.
OAUTH_CLIENT = ROOT / "oauth_client.json"

a = Analysis(
    [str(ROOT / "menu.py")],
    pathex=[str(ROOT)],
    datas=[
        (str(ROOT / "data" / "haarcascade_frontalface_default.xml"), "data"),
        (str(ROOT / "models" / "face_recognition_sface_2021dec.onnx"), "models"),
        (str(ROOT / "models" / "SFace-LICENSE"), "models"),
        (str(ROOT / "LICENSE"), "."),
        *([(str(OAUTH_CLIENT), ".")] if OAUTH_CLIENT.is_file() else []),
        # keyring finds its OS backend through package metadata at runtime.
        *copy_metadata("keyring"),
    ],
    # Pillow loads _tkinter_finder at runtime for the camera preview; analysis cannot see it.
    hiddenimports=["PIL._tkinter_finder", *collect_submodules("keyring.backends")],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="FaceCheckAttendance", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="FaceCheckAttendance")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="FaceCheck Attendance.app",
        bundle_identifier="io.github.n4win.facecheck-attendance",
        info_plist={
            "NSCameraUsageDescription": "ใช้กล้องเพื่อลงทะเบียนใบหน้าและเช็คชื่อนักศึกษา โดยประมวลผลภาพในเครื่องนี้",
            "NSHighResolutionCapable": True,
        },
    )
