#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="0.1.5"
BUILD_ROOT="$PROJECT_ROOT/build_deb"
PKG_ROOT="$BUILD_ROOT/pkgroot"
DEBIAN_DIR="$PKG_ROOT/DEBIAN"
APP_DIR="$PKG_ROOT/opt/zyna-calendar"
BIN_DIR="$PKG_ROOT/usr/bin"
ICON_DIR="$PKG_ROOT/usr/share/icons/hicolor/128x128/apps"
APP_DESKTOP_DIR="$PKG_ROOT/usr/share/applications"

rm -rf "$PKG_ROOT"
mkdir -p "$DEBIAN_DIR" "$APP_DIR" "$BIN_DIR" "$ICON_DIR" "$APP_DESKTOP_DIR"

cp -r "$PROJECT_ROOT/core" "$APP_DIR/"
cp -r "$PROJECT_ROOT/ui" "$APP_DIR/"
cp -r "$PROJECT_ROOT/utils" "$APP_DIR/"
cp "$PROJECT_ROOT/main.py" "$APP_DIR/"
cp "$PROJECT_ROOT/icon-128x128.png" "$APP_DIR/"
cp "$PROJECT_ROOT/uninstall.sh" "$APP_DIR/"
cp "$PROJECT_ROOT/zyna-calendar" "$BIN_DIR/zyna-calendar"

if [[ -f "$APP_DIR/credentials.json" ]]; then
    rm -f "$APP_DIR/credentials.json"
fi

for doc in README.md CHANGELOG.md USERGUIDE.md FAQ.md; do
    if [[ -f "$PROJECT_ROOT/$doc" ]]; then
        cp "$PROJECT_ROOT/$doc" "$APP_DIR/"
    fi
done

cp "$BUILD_ROOT/DEBIAN/control" "$DEBIAN_DIR/"
cp "$BUILD_ROOT/DEBIAN/postinst" "$DEBIAN_DIR/"
cp "$BUILD_ROOT/DEBIAN/prerm" "$DEBIAN_DIR/"
chmod 755 "$DEBIAN_DIR/postinst" "$DEBIAN_DIR/prerm"

cp "$PROJECT_ROOT/icon-128x128.png" "$ICON_DIR/zyna-calendar.png"

cat > "$APP_DESKTOP_DIR/zyna-calendar.desktop" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Zyna Calendar
Comment=Widget de escritorio para Google Calendar
Exec=/usr/bin/zyna-calendar
Icon=zyna-calendar
Terminal=false
Categories=Utility;Office;
EOF

chmod 755 "$APP_DIR/main.py"
chmod 755 "$APP_DIR/uninstall.sh"
chmod 755 "$BIN_DIR/zyna-calendar"

dpkg-deb --build "$PKG_ROOT" "$BUILD_ROOT/zyna-calendar_${VERSION}_all.deb"

echo "Paquete generado en: $BUILD_ROOT/zyna-calendar_${VERSION}_all.deb"
