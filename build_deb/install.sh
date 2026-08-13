#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEB_PATH="${1:-$PROJECT_ROOT/build_deb/zyna-calendar_0.1.8_all.deb}"

if [[ ! -f "$DEB_PATH" ]]; then
    echo "No se encontro el paquete .deb en: $DEB_PATH"
    exit 1
fi

echo "Instalando dependencias del sistema..."
sudo apt-get update
sudo apt-get install -y \
    python3 \
    python3-pyqt6 \
    python3-pip \
    python3-venv \
    libnotify-bin

echo "Instalando paquete: $DEB_PATH"
sudo dpkg -i "$DEB_PATH"

echo "Corrigiendo dependencias si es necesario..."
sudo apt-get -f install -y

echo "Instalacion completada."