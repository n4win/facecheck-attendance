#!/bin/sh
# Usage: packaging/build_linux.sh VERSION  (run from the project root after PyInstaller)
set -eu
version="$1"
mkdir -p installers
tar -czf "installers/FaceCheck-Attendance-Linux-x86_64.tar.gz" -C dist FaceCheckAttendance

stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
mkdir -p "$stage/DEBIAN" "$stage/opt" "$stage/usr/bin" "$stage/usr/share/applications"
cp -a dist/FaceCheckAttendance "$stage/opt/facecheck-attendance"
ln -s /opt/facecheck-attendance/FaceCheckAttendance "$stage/usr/bin/facecheck-attendance"
cat > "$stage/usr/share/applications/facecheck-attendance.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=FaceCheck Attendance
Comment=Face recognition attendance for students
Exec=facecheck-attendance
Terminal=false
Categories=Education;
DESKTOP
cat > "$stage/DEBIAN/control" <<CONTROL
Package: facecheck-attendance
Version: $version
Section: education
Priority: optional
Architecture: amd64
Depends: libgl1, libglib2.0-0t64 | libglib2.0-0
Recommends: fonts-noto-core
Maintainer: n4win <n4win@users.noreply.github.com>
Description: Face recognition attendance for students
 Desktop app that keeps attendance locally and can send it to your own Google Sheet.
CONTROL
dpkg-deb --root-owner-group --build "$stage" "installers/FaceCheck-Attendance-Linux-amd64.deb"
