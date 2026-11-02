# FaceCheck Attendance

ระบบเช็คชื่อนักศึกษาด้วยใบหน้า เป็นแอปเดสก์ท็อป Python/Tkinter ภาษาไทย ครูเข้าสู่ระบบด้วยบัญชี Google ของตัวเอง แล้วผลเช็คชื่อจะบันทึกลงชีตบน Drive ของครูคนนั้น ส่วนข้อมูลใบหน้าประมวลผลและเก็บอยู่ในเครื่องที่ใช้สแกน

## ความสามารถ

- **ลงทะเบียนนักศึกษา:** เก็บภาพใบหน้าหลังนักศึกษายืนยันความยินยอม
- **จัดการข้อมูลนักศึกษา:** ค้นหา แก้ไขชื่อและรหัส และจัดการข้อมูลใบหน้า
- **เช็คชื่อด้วยการสแกน:** ตั้งเวลาเข้าเรียนและเช็คชื่อผ่านกล้อง โดยจดจำใบหน้าในเครื่องด้วย OpenCV, SFace และ KNN
- **เช็คชื่อโดยอาจารย์:** เลือกนักศึกษาและระบุสถานะด้วยมือ
- **สรุปขาดเรียนอัตโนมัติ (ไม่บังคับ):** ติดตั้ง Google Apps Script ใน `google_apps_script/` ลงในชีตของคุณ

## ดาวน์โหลดและติดตั้ง

ดาวน์โหลดไฟล์ของระบบคุณจากหน้า [Releases](https://github.com/n4win/facecheck-attendance/releases) โดยไม่ต้องลง Python ใช้พื้นที่หลังติดตั้งประมาณ 450 MB

| ระบบ | ไฟล์ | วิธีติดตั้ง |
|---|---|---|
| Windows 64 บิต | `FaceCheck-Attendance-Windows-x64-Setup.exe` | เปิดไฟล์แล้วทำตามขั้นตอน ต้องใช้สิทธิ์ผู้ดูแลเครื่อง |
| macOS (Apple Silicon) | `FaceCheck-Attendance-macOS-AppleSilicon.dmg` | เปิดไฟล์แล้วลากแอปไปที่ Applications |
| macOS (Intel) | `FaceCheck-Attendance-macOS-Intel.dmg` | เปิดไฟล์แล้วลากแอปไปที่ Applications |
| Ubuntu / Debian | `FaceCheck-Attendance-Linux-amd64.deb` | `sudo apt install ./FaceCheck-Attendance-Linux-amd64.deb` |
| Linux อื่น ๆ | `FaceCheck-Attendance-Linux-x86_64.tar.gz` | แตกไฟล์แล้วรัน `FaceCheckAttendance/FaceCheckAttendance` |

ตัวติดตั้งยังไม่มีใบรับรองผู้พัฒนา ระบบจึงเตือนในการเปิดครั้งแรก:

- **Windows:** กด **More info** แล้วกด **Run anyway**
- **macOS:** เมื่อถูกบล็อก ไปที่ **System Settings → Privacy & Security** แล้วกด **Open Anyway** และเมื่อระบบถาม ให้อนุญาตการใช้กล้อง

ระบบเตือนเพราะไม่รู้จักผู้พัฒนา ไม่ได้ตรวจเนื้อหาโปรแกรมให้ จึงควรดาวน์โหลดจากหน้า Releases ของ repo นี้เท่านั้น

โปรแกรมเก็บใบหน้าซึ่งเป็นข้อมูลอ่อนไหว ผู้ที่นำไปใช้เป็นผู้รับผิดชอบการขอความยินยอมและการดูแลข้อมูลตามกฎหมาย เช่น PDPA

## รันจากซอร์สโค้ด

### สิ่งที่ต้องมี

- Python 3 พร้อม `venv` และ `tkinter` (ทดสอบบน Python 3.14 และ Linux)
- กล้องเว็บแคม สำหรับการลงทะเบียนและการสแกน
- ฟอนต์ไทย เช่น Noto Sans Thai
- บัญชี Google และอินเทอร์เน็ต สำหรับการเช็คชื่อ
- `oauth_client.json` ที่รากโปรเจค ถ้าจะทดสอบการเข้าสู่ระบบจากซอร์สโค้ด (ดูหัวข้อสร้างตัวติดตั้ง)

บน Ubuntu ติดตั้ง `tkinter` ด้วย:

```bash
sudo apt install python3-tk
```

### ติดตั้งและรัน

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python -m unittest discover -s tests   # รันเทสต์
python menu.py                         # เปิดโปรแกรม
```

## ไฟล์ที่ไม่อยู่ใน repo

ไฟล์ต่อไปนี้มีความลับหรือข้อมูลส่วนบุคคล จึงถูกตัดออกด้วย `.gitignore` ห้ามนำขึ้น repo:

| ไฟล์ | เนื้อหา |
|---|---|
| `/*.json` | key ของ Google service account ที่รากโปรเจค |
| `data/*` ยกเว้น `haarcascade_frontalface_default.xml` | ข้อมูลใบหน้า รายชื่อ ฐานข้อมูลความยินยอมและการเช็คชื่อ |
| `Attendance/` | ประวัติการเช็คชื่อ |
| `documents/` | เอกสารโครงงานและผลการทดลอง |
| `docs/screenshots/`, `docs/TEACHER_DASHBOARD.md`, `docs/ABSENCE_DASHBOARD.md`, `docs/AUTO_ABSENCE_HISTORY.md` | ภาพหน้าจอและบันทึกที่มีข้อมูลของการใช้งานจริง |
| `reports/LOOKER_STUDIO_SETUP.md`, `reports/looker_studio_config.json`, `reports/absence_report_config.json` | ค่าตั้งรายงานที่มีข้อมูลจริง |

## ข้อมูลอยู่ที่ไหน

| ข้อมูล | ที่เก็บ |
|---|---|
| ผลเช็คชื่อ | ชีตชื่อ `FaceCheck Attendance` บน Google Drive ของครูที่เข้าสู่ระบบ |
| การเข้าสู่ระบบ Google | keychain ของระบบ (Windows Credential Manager, macOS Keychain หรือ Secret Service บน Linux) ไม่เก็บเป็นไฟล์ธรรมดา |
| ข้อมูลใบหน้า รายชื่อ และหลักฐานความยินยอม | โฟลเดอร์ข้อมูลในเครื่อง เพราะกล้องต้องใช้เทียบหน้าตอนสแกน |
| สำเนาการเช็คด้วยมือ และรายการรอส่งตอนเน็ตหลุด | โฟลเดอร์ข้อมูลในเครื่อง |

| วิธีรัน | โฟลเดอร์ข้อมูล |
|---|---|
| จากซอร์สโค้ด | `data/` ในโปรเจค |
| จากตัวติดตั้งบน Windows | `%APPDATA%\FaceCheck Attendance` |
| จากตัวติดตั้งบน macOS | `~/Library/Application Support/FaceCheck Attendance` |
| จากตัวติดตั้งบน Linux | `~/.local/share/FaceCheck Attendance` |

การถอนการติดตั้งจะไม่ลบโฟลเดอร์นี้ หากต้องการลบข้อมูลใบหน้าให้ลบเอง

## เข้าสู่ระบบ Google

ในเมนูหลักกด **เข้าสู่ระบบ Google และตั้งค่า** แล้วกด **เข้าสู่ระบบด้วย Google** เบราว์เซอร์จะเปิดให้เลือกบัญชีและกดอนุญาต จากนั้นโปรแกรมจะสร้างชีตให้ หรือใช้ชีตเดิมถ้าเคยเข้าสู่ระบบแล้ว ต้องเข้าสู่ระบบก่อนจึงจะเช็คชื่อได้ ส่วนการลงทะเบียนและจัดการรายชื่อใช้ได้โดยไม่ต้องเข้าสู่ระบบ

โปรแกรมขอสิทธิ์ `drive.file` จึงเข้าถึงได้เฉพาะไฟล์ที่ใช้กับโปรแกรมนี้ ไม่เห็นไฟล์อื่นใน Drive และยกเลิกสิทธิ์ได้ทุกเมื่อจาก [หน้าบัญชี Google](https://myaccount.google.com/permissions)

### ขั้นสูง: ใช้ชีตที่มีอยู่ด้วยไฟล์ key

สำหรับชีตที่มีอยู่แล้ว ให้สร้าง service account ใน Google Cloud Console แล้วดาวน์โหลดไฟล์ key แบบ JSON เปิดใช้ Google Sheets API และ Google Drive API แชร์ชีตเป็น Editor ให้อีเมลของ service account จากนั้นติ๊ก **ขั้นสูง** ในหน้าตั้งค่า ระบุชื่อหรือลิงก์ของชีต เลือกไฟล์ key แล้วกด **ทดสอบและบันทึก** แถวแรกของแผ่นแรกต้องว่างหรือเป็น `DATE, NAME, STUDENT_ID, TIME, STATUS, ANNOTATION`

> **ความปลอดภัย:** ไฟล์ key ใช้เข้าถึงชีตได้ ห้าม commit หรือแจกให้ผู้อื่น โปรแกรมเก็บสำเนาไว้ในโฟลเดอร์ข้อมูล

### สรุปขาดเรียนอัตโนมัติ

ติดตั้ง Apps Script ลงในชีตตาม [docs/AUTO_ABSENCE.md](docs/AUTO_ABSENCE.md) แล้วกด **ตรวจการเชื่อมต่อ** (หรือ **ทดสอบและบันทึก** ถ้าใช้ไฟล์ key) ส่วนรายงาน Looker Studio ยังต้องตั้งค่าเองด้วย `report_setup.py`

## โมเดล

ใช้โมเดล SFace จาก OpenCV Zoo ภายใต้สัญญาอนุญาต Apache 2.0 รายละเอียดอยู่ใน [models/README.md](models/README.md)

## เอกสารเพิ่มเติม

- [สรุปขาดเรียนอัตโนมัติบน Google](docs/AUTO_ABSENCE.md)

## สร้างตัวติดตั้ง

GitHub Actions สร้างตัวติดตั้งทุกระบบตาม [.github/workflows/build.yml](.github/workflows/build.yml) และตรวจตัวแพ็กด้วย `--self-check` เมื่อ push tag เช่น `v1.0.0` จะได้ Release แบบ draft ให้ตรวจก่อนเผยแพร่

การเข้าสู่ระบบต้องมี OAuth client แบบ Desktop app ที่เปิด Google Sheets API และ Google Drive API และเพิ่ม scope `openid`, `userinfo.email` และ `drive.file` แล้ว ให้เก็บเนื้อหาไฟล์ JSON ของ client ไว้ใน GitHub secret ชื่อ `GOOGLE_OAUTH_CLIENT_JSON` การ build จาก tag จะหยุดถ้าไม่มี secret นี้ ไฟล์นี้ไม่อยู่ใน repo แต่จะถูกรวมในตัวติดตั้ง ซึ่ง [Google ถือว่าแอปเดสก์ท็อปเก็บ client secret เป็นความลับไม่ได้](https://developers.google.com/identity/protocols/oauth2/native-app) และใช้การเข้าถึงข้อมูลผู้ใช้ไม่ได้ถ้าผู้ใช้ไม่กดอนุญาต

## สัญญาอนุญาต

โค้ดของโปรเจคใช้ [MIT License](LICENSE) ส่วนโมเดล SFace ใช้ Apache 2.0 ([models/SFace-LICENSE](models/SFace-LICENSE)) ตัวตรวจจับใบหน้า Haar cascade มาจาก OpenCV และมีสัญญาอนุญาตอยู่ในหัวไฟล์ ตัวติดตั้งยังรวมไลบรารีอื่นตามสัญญาอนุญาตของแต่ละตัว เช่น OpenCV, NumPy, SciPy, scikit-learn, Pillow และ PyInstaller
