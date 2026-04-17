#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEB_PATH="${1:-$PROJECT_ROOT/build_deb/zyna-calendar_0.1.5_all.deb}"

if [[ ! -f "$DEB_PATH" ]]; then
    echo "No se encontro el paquete .deb en: $DEB_PATH"
    exit 1
fi

echo "Instalando dependencias del sistema..."
sudo apt-get update
sudo apt-get install -y \
    python3 \
    "python3-pyqt5 | python3-pyqt6" \
    libnotify-bin \
    python3-googleapi \
    python3-google-auth \
    python3-google-auth-httplib2 \
    python3-google-auth-oauthlib \
    python3-httplib2 \
    python3-requests

echo "Instalando paquete: $DEB_PATH"
sudo dpkg -i "$DEB_PATH"

echo "Corrigiendo dependencias si es necesario..."
sudo apt-get -f install -y

echo "Instalacion completada."
