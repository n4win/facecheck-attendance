/** @OnlyCurrentDoc */
// Bound to the existing attendance spreadsheet. No face data, email or web app.
const ABSENCE_CONFIG = {
  attendanceSheetId: 0,
  sessions: 'Attendance_Sessions',
  monitor: 'Attendance_Automation',
  timezone: 'Asia/Bangkok'
};
const ROUND_HEADERS = ['SESSION_ID', 'DATE', 'STUDENT_ID', 'NAME', 'OPENED_AT', 'ROSTER_COUNT', 'END_TIME'];
const ATTENDANCE_HEADERS = ['DATE', 'NAME', 'STUDENT_ID', 'TIME', 'STATUS', 'ANNOTATION'];

function attendanceBook_() {
  const book = SpreadsheetApp.getActiveSpreadsheet();
  if (!book) {
    throw new Error('Install this script from Extensions > Apps Script in your attendance spreadsheet.');
  }
  return book;
}

function assertHeaders_(values, expected) {
  if (!values.length || expected.some((name, i) => String(values[0][i] || '').trim().toUpperCase() !== name)) {
    throw new Error('Unexpected sheet headers: ' + expected.join(', '));
  }
}

function ensureSheet_(book, name, headers) {
  const sheet = book.getSheetByName(name) || book.insertSheet(name);
  if (!sheet.getLastRow()) sheet.appendRow(headers);
  assertHeaders_(sheet.getDataRange().getDisplayValues(), headers);
  sheet.setFrozenRows(1);
  sheet.getRange(1, 1, 1, headers.length).setFontWeight('bold').setBackground('#E4EFF1');
  sheet.autoResizeColumns(1, headers.length);
  return sheet;
}

// Run once from the editor and approve the Google authorization screen.
function setupAttendanceAutomation() {
  testAbsencePlanner();
  const book = attendanceBook_();
  const source = book.getSheetById(ABSENCE_CONFIG.attendanceSheetId);
  if (!source) throw new Error('Attendance sheet not found');
  assertHeaders_(source.getDataRange().getDisplayValues(), ATTENDANCE_HEADERS);
  const rounds = book.getSheetByName(ABSENCE_CONFIG.sessions);
  if (rounds && rounds.getLastRow()) {
    const headers = rounds.getDataRange().getDisplayValues();
    assertHeaders_(headers, ROUND_HEADERS.slice(0, 6));
    if (!headers[0][6]) rounds.getRange(1, 7).setValue('END_TIME');
  }
  ensureSheet_(book, ABSENCE_CONFIG.sessions, ROUND_HEADERS);
  ensureSheet_(book, ABSENCE_CONFIG.monitor, ['KEY', 'VALUE']);
  const triggers = ScriptApp.getProjectTriggers().filter(t => t.getHandlerFunction() === 'finalizeAttendanceAbsences');
  if (!triggers.length) {
    ScriptApp.newTrigger('finalizeAttendanceAbsences').timeBased().everyMinutes(15).create();
  }
  updateMonitor_(book, 'enabled', '', 0);
  console.log('Automatic absence enabled: checks every 15 minutes, cutoff class end time (legacy rounds: midnight), Asia/Bangkok.');
}

function isoAttendanceDay_(value) {
  const text = String(value).trim();
  const match = /^(\d{2})-(\d{2})-(\d{4})$/.exec(text);
  const iso = match ? `${match[3]}-${match[2]}-${match[1]}` : text;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) throw new Error('Invalid attendance date: ' + text);
  const date = new Date(iso + 'T00:00:00Z');
  if (isNaN(date.getTime()) || date.toISOString().slice(0, 10) !== iso) throw new Error('Invalid attendance date: ' + text);
  return iso;
}

function displayAttendanceDay_(iso) {
  return iso.slice(8, 10) + '-' + iso.slice(5, 7) + '-' + iso.slice(0, 4);
}

// Pure planner. Use the first complete roster and the latest opening deadline.
// Legacy rounds without END_TIME retain the next-midnight deadline.
function planAbsences(sessionRows, attendanceRows, nowISO) {
  const todayISO = nowISO.slice(0, 10);
  isoAttendanceDay_(todayISO);
  const now = Date.parse(nowISO.length === 10 ? nowISO + "T00:00:00+07:00" : nowISO);
  if (!Number.isFinite(now)) throw new Error("Invalid current time");
  const sessions = new Map();
  sessionRows.forEach(row => {
    if (!row.some(v => String(v).trim())) return;
    const [session, rawDay, rawId, rawName, rawOpened, rawCount, rawEnd] = row;
    const day = isoAttendanceDay_(rawDay);
    const id = String(rawId).trim(), name = String(rawName).trim();
    const opened = String(rawOpened).trim(), count = Number(rawCount);
    if (!session || !id || !name || name.toLowerCase() === 'unknown' ||
        !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+07:00$/.test(opened) ||
        !Number.isInteger(count) || count < 1) throw new Error('Invalid session roster');
    isoAttendanceDay_(opened.slice(0, 10));
    const end = String(rawEnd || "").trim();
    if (end && !/^([01]\d|2[0-3]):[0-5]\d$/.test(end)) throw new Error("Invalid class end time");
    const key = String(session);
    if (!sessions.has(key)) sessions.set(key, {day, opened, count, end, students: new Map()});
    const round = sessions.get(key);
    if (round.day !== day || round.opened !== opened || round.count !== count || round.end !== end ||
        (round.students.has(id) && round.students.get(id) !== name)) throw new Error('Conflicting session roster');
    round.students.set(id, name);
  });
  const days = new Map();
  [...sessions.values()].sort((a, b) => a.opened.localeCompare(b.opened)).forEach(round => {
    if (round.students.size !== round.count) throw new Error('Incomplete session roster; no absences written');
    if (!days.has(round.day)) days.set(round.day, {students: round.students, openedDay: round.opened.slice(0, 10)});
    const day = days.get(round.day);
    day.openedDay = [day.openedDay, round.opened.slice(0, 10)].sort().pop();
    // Latest reopening determines the deadline; retain the original student roster.
    // Past-date corrections get until class end on the day they are reopened.
    const effectiveDay = [round.day, round.opened.slice(0, 10)].sort().pop();
    day.deadline = round.end
      ? Date.parse(effectiveDay + 'T' + round.end + ':00+07:00')
      : Date.parse(effectiveDay + 'T00:00:00+07:00') + 86400000;
  });
  const existing = new Set();
  attendanceRows.forEach(row => {
    if (!row.some(v => String(v).trim())) return;
    // Unknown attendance is not a student attendance record.
    if (String(row[1]).trim().toLowerCase() === 'unknown') return;
    const id = String(row[2] || '').trim();
    if (!id) return;
    const day = isoAttendanceDay_(row[0]);
    // Preserve all existing rows, including absences, leave, and manual corrections.
    existing.add(day + '|' + id);
  });
  const additions = [];
  [...days.entries()].sort((a, b) => a[0].localeCompare(b[0])).forEach(([day, round]) => {
    if (now < round.deadline) return;
    round.students.forEach((name, id) => {
      const key = day + '|' + id;
      if (!existing.has(key)) {
        additions.push([displayAttendanceDay_(day), name, id, '-', 'ขาดเรียน', 'ไม่มีหมายเหตุ']);
        existing.add(key);
      }
    });
  });
  return additions;
}

function updateMonitor_(book, state, error, added) {
  const sheet = book.getSheetByName(ABSENCE_CONFIG.monitor);
  if (!sheet) return;
  sheet.getRange(2, 1, 5, 2).setValues([
    ['STATE', state], ['TIMEZONE', ABSENCE_CONFIG.timezone],
    ['LAST_CHECK', Utilities.formatDate(new Date(), ABSENCE_CONFIG.timezone, 'yyyy-MM-dd HH:mm:ss')],
    ['LAST_ADDED', added], ['LAST_ERROR', error]
  ]);
}

function readAttendance_(sheet) {
  const values = sheet.getDataRange().getValues();
  assertHeaders_(values, ATTENDANCE_HEADERS);
  return values.slice(1).map(row => {
    if (row[0] instanceof Date) row[0] = Utilities.formatDate(row[0], ABSENCE_CONFIG.timezone, 'dd-MM-yyyy');
    return row;
  });
}

function finalizeAttendanceAbsences() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return;
  let book;
  try {
    book = attendanceBook_();
    const source = book.getSheetById(ABSENCE_CONFIG.attendanceSheetId);
    const sessionSheet = book.getSheetByName(ABSENCE_CONFIG.sessions);
    if (!source || !sessionSheet) throw new Error('Run setupAttendanceAutomation first');
    const values = sessionSheet.getDataRange().getDisplayValues();
    assertHeaders_(values, ROUND_HEADERS);
    const today = Utilities.formatDate(new Date(), ABSENCE_CONFIG.timezone, "yyyy-MM-dd'T'HH:mm:ssXXX");
    const additions = planAbsences(values.slice(1), readAttendance_(source), today);
    let added = 0;
    // Re-read before each append so a retry or concurrent check-in is respected.
    for (const row of additions) {
      const latestSessions = sessionSheet.getDataRange().getDisplayValues();
      assertHeaders_(latestSessions, ROUND_HEADERS);
      const stillMissing = planAbsences(latestSessions.slice(1), readAttendance_(source), today)
        .some(candidate => candidate[0] === row[0] && candidate[2] === row[2]);
      if (stillMissing) {
        // Leading apostrophe stores literal text, including IDs with leading zeroes.
        source.appendRow(row.map(value => "'" + String(value)));
        added += 1;
      }
    }
    SpreadsheetApp.flush();
    updateMonitor_(book, 'enabled', '', added);
    console.log('Absence check complete; added ' + added + ' rows.');
  } catch (error) {
    if (book) updateMonitor_(book, 'error', String(error.message || error), 0);
    throw error;
  } finally {
    lock.releaseLock();
  }
}

function testAbsencePlanner() {
  function eq(actual, expected, label) {
    if (JSON.stringify(actual) !== JSON.stringify(expected)) throw new Error('Test failed: ' + label);
  }
  const roster = [
    ['r1', '29-09-2026', '001', 'Student One', '2026-09-29T08:00:00+07:00', '2'],
    ['r1', '29-09-2026', '002', 'Student Two', '2026-09-29T08:00:00+07:00', '2']
  ];
  const actual = [['29-09-2026', 'Student One', '001', '08:00:00', 'ตรงเวลา', 'ไม่มีหมายเหตุ']];
  const absent = [['29-09-2026', 'Student Two', '002', '-', 'ขาดเรียน', 'ไม่มีหมายเหตุ']];
  eq(planAbsences(roster, actual, '2026-09-29'), [], 'not before midnight');
  eq(planAbsences(roster, actual, '2026-09-30'), absent, 'missing student after midnight');
  eq(planAbsences(roster, actual.concat(absent), '2026-09-30'), [], 'idempotent retry');
  eq(planAbsences([], actual, '2026-10-01'), [], 'no unopened days');
  eq(planAbsences(roster, [], '2026-10-01').length, 2, 'zero attendees');
  eq(planAbsences(roster, actual.map(r => r.map((v, i) => i === 4 ? 'มาสาย' : v)), '2026-09-30'), absent, 'late is present');
  eq(planAbsences(roster, actual.concat([['29-09-2026', 'Manual', '002', '09:00', 'มา', '']]), '2026-09-30'), [], 'manual attendance');
  const reopened = roster.map(r => [r[0] + 'new', r[1], r[2], r[3], '2026-09-30T08:00:00+07:00', r[5]]);
  eq(planAbsences(roster.concat(reopened), actual, '2026-09-30'), [], 'reopened past date waits');
  let invalid = false;
  try { planAbsences(roster.slice(0, 1), actual, '2026-09-30'); } catch (_) { invalid = true; }
  eq(invalid, true, 'partial roster rejected');
  const timed = roster.map(r => r.concat('10:00'));
  eq(planAbsences(timed, actual, '2026-09-29T09:59:59+07:00'), [], 'before class end');
  eq(planAbsences(timed, actual, '2026-09-29T10:00:00+07:00'), absent, 'at class end');
  eq(planAbsences(timed, actual.concat(absent), '2026-09-29T10:15:00+07:00'), [], 'class end retry');
  eq(planAbsences(timed, [], '2026-09-29T10:15:00+07:00').length, 2, 'class end zero attendees');
  eq(planAbsences(timed, actual, '2026-09-29T03:00:00Z'), absent, 'timezone equivalence');
  const later = timed.map(r => [r[0] + 'later', r[1], r[2], r[3], '2026-09-29T09:30:00+07:00', r[5], '12:00']);
  eq(planAbsences(timed.concat(later), actual, '2026-09-29T10:15:00+07:00'), [], 'reopening extends end');
  let badEnd = false;
  try { planAbsences(roster.map(r => r.concat('24:00')), actual, '2026-09-30'); } catch (_) { badEnd = true; }
  eq(badEnd, true, 'invalid end fails safely');
  console.log('PASS: absence planner tests (no real attendance data written).');
}
