# นโยบายความเป็นส่วนตัวของ FaceCheck Attendance

มีผลตั้งแต่วันที่ 3 พฤศจิกายน 2026 ([English below](#privacy-policy))

FaceCheck Attendance เป็นโปรแกรมโอเพนซอร์สสำหรับเช็คชื่อนักศึกษาด้วยใบหน้า ทำงานบนเครื่องของผู้ใช้ **ผู้พัฒนาไม่มีเซิร์ฟเวอร์ที่รับข้อมูลจากโปรแกรม และไม่ได้รับข้อมูลของผู้ใช้หรือนักศึกษา**

## ข้อมูลที่โปรแกรมใช้และที่เก็บ

| ข้อมูล | ที่เก็บ |
|---|---|
| ภาพใบหน้าตัวอย่าง ชื่อ รหัสนักศึกษา และหลักฐานความยินยอม | เครื่องที่ติดตั้งโปรแกรม |
| ผลเช็คชื่อ ได้แก่ ชื่อ รหัสนักศึกษา วันที่ เวลา สถานะ และหมายเหตุ | Google Sheet บน Drive ของผู้ใช้ที่เข้าสู่ระบบ |
| สำเนาการเช็คชื่อด้วยมือ และรายการที่รอส่งเมื่อเชื่อมต่อไม่ได้ | เครื่องที่ติดตั้งโปรแกรม |
| อีเมลบัญชี Google และรหัสของชีต | ไฟล์ตั้งค่าในเครื่องที่ติดตั้งโปรแกรม |
| สิทธิ์การเข้าสู่ระบบ Google (refresh token) | keychain ของระบบปฏิบัติการในเครื่องนั้น |
| รายชื่อและรหัสนักศึกษาของรอบเช็คชื่อ เมื่อผู้ใช้ติดตั้งระบบสรุปขาดเรียน | แท็บในชีตเดียวกัน บน Drive ของผู้ใช้ |

โปรแกรมประมวลผลใบหน้าในเครื่อง และไม่ส่งภาพใบหน้าไปยัง Google หรือผู้พัฒนา

## การใช้ข้อมูลจาก Google

โปรแกรมขอสิทธิ์เท่าที่จำเป็นดังนี้:

- `openid` และ `userinfo.email`: เพื่อแสดงว่าเข้าสู่ระบบด้วยบัญชีใด
- `drive.file`: เพื่อสร้าง เปิด และแก้ไขชีตที่ใช้กับโปรแกรมนี้ โปรแกรมไม่เห็นไฟล์อื่นใน Drive

ข้อมูลจาก Google ถูกใช้เพื่อบันทึกและแสดงผลเช็คชื่อให้ผู้ใช้เท่านั้น ไม่ถูกขาย ไม่ถูกโอนให้บุคคลอื่น ไม่ถูกใช้โฆษณา และไม่ถูกใช้ฝึกโมเดล AI

การใช้และการโอนข้อมูลที่ได้รับจาก Google APIs เป็นไปตาม [Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy) รวมถึงข้อกำหนด Limited Use

## บริการของ Google ที่ผู้ใช้เลือกใช้ได้

- **สรุปขาดเรียนอัตโนมัติ:** ถ้าผู้ใช้ติดตั้ง Apps Script สคริปต์จะทำงานในบัญชี Google ของผู้ใช้ และเข้าถึงเฉพาะชีตที่ติดตั้ง
- **รายงาน:** ปุ่มรายงานเปิด Data Studio ด้วยบัญชีของผู้ใช้ โดยนำรายงานต้นแบบที่ไม่มีข้อมูลจริงมาแสดงข้อมูลจากชีตของผู้ใช้ เจ้าของรายงานต้นแบบไม่ได้รับข้อมูลนี้ ตราบใดที่ผู้ใช้ไม่ได้แชร์ให้เอง

การใช้บริการเหล่านี้เป็นไปตามข้อกำหนดของ Google

## ผู้รับผิดชอบข้อมูล

สถานศึกษาหรือผู้สอนที่นำโปรแกรมไปใช้เป็นผู้รับผิดชอบข้อมูลของนักศึกษา รวมถึงการขอความยินยอม การกำหนดผู้เข้าถึง ระยะเวลาเก็บ และการตอบคำขอของเจ้าของข้อมูลตามกฎหมาย เช่น PDPA เจ้าของข้อมูลจึงควรติดต่อผู้รับผิดชอบที่แสดงในหนังสือขอความยินยอม

## การยกเลิกและการลบข้อมูล

- **ออกจากระบบ:** กด **ออกจากระบบ** ในหน้าตั้งค่า ระบบจะลบการเข้าสู่ระบบออกจากเครื่องและขอให้ Google ยกเลิกสิทธิ์
- **ยกเลิกสิทธิ์เอง:** ไปที่ [สิทธิ์ของบัญชี Google](https://myaccount.google.com/permissions)
- **ลบผลเช็คชื่อ:** ลบชีต `FaceCheck Attendance` ออกจาก Google Drive
- **ลบข้อมูลในเครื่อง:** ลบรายบุคคลได้ในหน้าจัดการข้อมูลนักศึกษา หรือลบโฟลเดอร์ข้อมูลซึ่งดูตำแหน่งได้ในหน้าตั้งค่า การถอนการติดตั้งจะไม่ลบโฟลเดอร์นี้

## ติดต่อ

สอบถามเกี่ยวกับโปรแกรมได้ที่ [GitHub Issues](https://github.com/n4win/facecheck-attendance/issues) โปรดอย่าโพสต์ข้อมูลส่วนบุคคลของนักศึกษา เพราะหน้านี้เป็นสาธารณะ

หากนโยบายเปลี่ยนแปลง จะปรับปรุงที่หน้านี้พร้อมวันที่มีผล

---

# Privacy Policy

Effective November 3, 2026

FaceCheck Attendance is an open-source app that takes student attendance by face recognition on the user's own computer. **The developer runs no server that receives data from the app and does not receive any user or student data.**

## Data the app uses and where it is kept

| Data | Location |
|---|---|
| Face samples, names, student IDs and consent records | The computer running the app |
| Attendance results: name, student ID, date, time, status and note | A Google Sheet in the signed-in user's Drive |
| Copies of manual attendance and items waiting to be sent | The computer running the app |
| Google account email and the sheet's ID | A settings file on the computer running the app |
| Google sign-in permission (refresh token) | The operating system's keychain on that computer |
| Round rosters of names and student IDs, if the user installs the absence system | A tab in the same sheet in the user's Drive |

Faces are processed on the computer. Face images are not sent to Google or to the developer.

## Use of Google data

The app requests only these permissions:

- `openid` and `userinfo.email`: to show which account is signed in
- `drive.file`: to create, open and edit the sheet used with this app. The app cannot see other files in Drive.

Data from Google is used only to record and show attendance to the user. It is not sold, not transferred to others, not used for advertising, and not used to train AI models.

The app's use and transfer of information received from Google APIs adheres to the [Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy), including the Limited Use requirements.

## Optional Google services

- **Automatic absence summary:** if the user installs the Apps Script, it runs in the user's own Google account and accesses only the sheet it is installed in.
- **Reports:** the report button opens Data Studio with the user's account, showing data from the user's sheet in a template report that holds no real data. The template's owner does not receive this data unless the user shares it.

These services are subject to Google's terms.

## Who is responsible for the data

The school or teacher using the app is responsible for student data, including consent, access, retention and responding to data subject requests under laws such as Thailand's PDPA. Data subjects should contact the person named in the consent notice.

## Revoking access and deleting data

- **Sign out:** press the sign-out button in the settings window. This removes the sign-in from the computer and asks Google to revoke access.
- **Revoke manually:** visit your [Google Account permissions](https://myaccount.google.com/permissions).
- **Delete attendance results:** delete the `FaceCheck Attendance` sheet from Google Drive.
- **Delete local data:** remove individuals in the student management window, or delete the data folder shown in the settings window. Uninstalling does not delete this folder.

## Contact

Questions about the app can be raised through [GitHub Issues](https://github.com/n4win/facecheck-attendance/issues). Please do not post personal data about students, because this page is public.

Changes to this policy will be published on this page with a new effective date.
