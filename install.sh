#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$PROJECT_ROOT/venv"
AUTOSTART_DIR="$HOME/.config/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/zyna-calendar.desktop"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "Instalando Zyna-Calendar en: $PROJECT_ROOT"

# Entorno virtual aislado para las dependencias de Google API.
# --system-site-packages hereda PyQt6 instalado por el sistema y evita
# el bloqueo global de pip en entornos PEP 668.
"$PYTHON_BIN" -m venv --system-site-packages "$VENV_PATH"
"$VENV_PATH/bin/pip" install --upgrade pip
"$VENV_PATH/bin/pip" install -r "$PROJECT_ROOT/requirements.txt"

echo "Verificando importaciones dentro del entorno virtual..."
"$VENV_PATH/bin/python" -c "import PyQt6.QtWidgets; print('PyQt6 OK')"
"$VENV_PATH/bin/python" -c "import googleapiclient; print('googleapiclient OK')"

chmod +x "$PROJECT_ROOT/main.py"
chmod +x "$PROJECT_ROOT/install.sh"
chmod +x "$PROJECT_ROOT/zyna-calendar"

mkdir -p "$AUTOSTART_DIR"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Zyna Calendar
Comment=Widget de escritorio para Google Calendar
Exec=$VENV_PATH/bin/python $PROJECT_ROOT/main.py
Path=$PROJECT_ROOT
Terminal=false
X-GNOME-Autostart-enabled=true
StartupNotify=false
EOF

if ! command -v notify-send >/dev/null 2>&1; then
    echo "Aviso: 'notify-send' no está disponible. Las notificaciones nativas no funcionarán hasta instalarlo."
fi

echo "Instalación completada."
echo "Autostart creado en: $DESKTOP_FILE"