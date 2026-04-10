#!/usr/bin/env bash

set -euo pipefail

APP_SLUG="zyna-calendar"
CONFIG_DIR="${HOME}/.config/${APP_SLUG}"
AUTOSTART_FILE="${HOME}/.config/autostart/zyna-calendar.desktop"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="${PROJECT_ROOT}/venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "Desinstalador de Zyna-Calendar"

read -r -p "¿Deseas desinstalar el applet del sistema? [s/N]: " remove_app
if [[ "${remove_app}" =~ ^[sS]$ ]]; then
    if command -v dpkg >/dev/null 2>&1 && dpkg -s zyna-calendar >/dev/null 2>&1; then
        echo "El paquete .deb esta instalado. Se requiere sudo para removerlo."
        sudo apt remove -y zyna-calendar || true
    else
        echo "No se detecto paquete .deb instalado. Continuando con limpieza local."
    fi

    if [[ -f "${AUTOSTART_FILE}" ]]; then
        rm -f "${AUTOSTART_FILE}"
        echo "Autostart eliminado: ${AUTOSTART_FILE}"
    fi

    if [[ -d "${VENV_PATH}" ]]; then
        rm -rf "${VENV_PATH}"
        echo "Entorno virtual eliminado: ${VENV_PATH}"
    fi
fi

read -r -p "¿Deseas eliminar los datos locales (cache, token, settings)? [s/N]: " remove_data
if [[ "${remove_data}" =~ ^[sS]$ ]]; then
    if [[ -d "${CONFIG_DIR}" ]]; then
        rm -rf "${CONFIG_DIR}"
        echo "Datos locales eliminados: ${CONFIG_DIR}"
    fi
fi

read -r -p "¿Deseas eliminar las dependencias instaladas con pip --user? [s/N]: " remove_deps
if [[ "${remove_deps}" =~ ^[sS]$ ]]; then
    "${PYTHON_BIN}" -m pip uninstall -y google-api-python-client google-auth-httplib2 google-auth-oauthlib uritemplate httplib2 || true
    echo "Dependencias de usuario eliminadas."
fi

echo "Desinstalacion completada."
