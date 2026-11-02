# FaceCheck Attendance

ระบบเช็คชื่อนักศึกษาด้วยใบหน้า เป็นแอปเดสก์ท็อป Python/Tkinter ภาษาไทย บันทึกผลการเช็คชื่อไว้ในเครื่อง หรือส่งไป Google Sheets ของคุณเองได้ถ้าเชื่อมต่อ

## ความสามารถ

- **ลงทะเบียนนักศึกษา:** เก็บภาพใบหน้าหลังนักศึกษายืนยันความยินยอม
- **จัดการข้อมูลนักศึกษา:** ค้นหา แก้ไขชื่อและรหัส และจัดการข้อมูลใบหน้า
- **เช็คชื่อด้วยการสแกน:** ตั้งเวลาเข้าเรียนและเช็คชื่อผ่านกล้อง โดยจดจำใบหน้าในเครื่องด้วย OpenCV, SFace และ KNN
- **เช็คชื่อโดยอาจารย์:** เลือกนักศึกษาและระบุสถานะด้วยมือ
- **สรุปขาดเรียนอัตโนมัติ (ไม่บังคับ):** ใช้ Google Sheets ร่วมกับ Google Apps Script ใน `google_apps_script/`

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
- Google service account เฉพาะกรณีที่ต้องการส่งข้อมูลเข้า Google Sheets

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

## ที่เก็บข้อมูล

| วิธีรัน | โฟลเดอร์ข้อมูล |
|---|---|
| จากซอร์สโค้ด | `data/` ในโปรเจค |
| จากตัวติดตั้งบน Windows | `%APPDATA%\FaceCheck Attendance` |
| จากตัวติดตั้งบน macOS | `~/Library/Application Support/FaceCheck Attendance` |
| จากตัวติดตั้งบน Linux | `~/.local/share/FaceCheck Attendance` |

ถ้าไม่ได้เชื่อม Google ผลการเช็คชื่อจะอยู่ใน `attendance_records.csv` ซึ่งเปิดด้วย Excel ได้ ส่วนการถอนการติดตั้งจะไม่ลบโฟลเดอร์นี้ หากต้องการลบข้อมูลใบหน้าให้ลบเอง

## เชื่อม Google Sheets (ไม่บังคับ)

1. สร้าง service account และดาวน์โหลดไฟล์ key แบบ JSON จาก Google Cloud Console
2. เปิดใช้ Google Sheets API และ Google Drive API ในโปรเจคเดียวกัน
3. สร้าง Google Sheet ที่แผ่นแรกว่างเปล่า แล้วแชร์เป็น Editor ให้อีเมลของ service account
4. ในโปรแกรม เปิด **ตั้งค่า Google Sheets และโฟลเดอร์ข้อมูล** ระบุชื่อหรือลิงก์ของชีต เลือกไฟล์ key แล้วกด **ทดสอบและบันทึก**

> **ความปลอดภัย:** ไฟล์ key ใช้เข้าถึงชีตได้ ห้าม commit หรือแจกให้ผู้อื่น ผลการเช็คชื่อที่บันทึกในเครื่องก่อนเชื่อม Google จะไม่ถูกส่งขึ้นชีตให้อัตโนมัติ

ถ้าต้องการสรุปขาดเรียนอัตโนมัติ ให้ติดตั้ง Apps Script ตาม [docs/AUTO_ABSENCE.md](docs/AUTO_ABSENCE.md) แล้วกด **ทดสอบและบันทึก** อีกครั้ง ส่วนรายงาน Looker Studio ยังต้องตั้งค่าเองด้วย `report_setup.py`

## โมเดล

ใช้โมเดล SFace จาก OpenCV Zoo ภายใต้สัญญาอนุญาต Apache 2.0 รายละเอียดอยู่ใน [models/README.md](models/README.md)

## เอกสารเพิ่มเติม

- [สรุปขาดเรียนอัตโนมัติบน Google](docs/AUTO_ABSENCE.md)

## สร้างตัวติดตั้ง

GitHub Actions สร้างตัวติดตั้งทุกระบบตาม [.github/workflows/build.yml](.github/workflows/build.yml) และตรวจตัวแพ็กด้วย `--self-check` เมื่อ push tag เช่น `v1.0.0` จะได้ Release แบบ draft ให้ตรวจก่อนเผยแพร่

## สัญญาอนุญาต

โค้ดของโปรเจคใช้ [MIT License](LICENSE) ส่วนโมเดล SFace ใช้ Apache 2.0 ([models/SFace-LICENSE](models/SFace-LICENSE)) ตัวตรวจจับใบหน้า Haar cascade มาจาก OpenCV และมีสัญญาอนุญาตอยู่ในหัวไฟล์ ตัวติดตั้งยังรวมไลบรารีอื่นตามสัญญาอนุญาตของแต่ละตัว เช่น OpenCV, NumPy, SciPy, scikit-learn, Pillow และ PyInstaller
