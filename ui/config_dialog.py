"""Configuration dialog for Zyna-Calendar settings."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from utils.config import (
    PROJECT_ROOT,
    get_app_icon_path,
    get_autostart_path,
    load_settings,
    save_settings,
)


class ConfigDialog(QDialog):
    """Dialog for editing local widget settings."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the dialog with current settings."""

        super().__init__(parent)
        self.setWindowTitle("Configuracion")
        self.setModal(True)
        self.setMinimumWidth(360)

        icon_path = get_app_icon_path()
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._settings = load_settings()
        self._build_ui()

    def _build_ui(self) -> None:
        """Construct the dialog layout."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        form_layout = QGridLayout()
        form_layout.setHorizontalSpacing(12)
        form_layout.setVerticalSpacing(10)

        events_label = QLabel("Numero de eventos")
        self._events_spin = QSpinBox()
        self._events_spin.setRange(1, 8)
        self._events_spin.setValue(int(self._settings.get("max_events", 5)))

        refresh_label = QLabel("Intervalo de sincronizacion (min):")
        self._refresh_spin = QSpinBox()
        self._refresh_spin.setRange(0, 1440)
        self._refresh_spin.setValue(int(self._settings.get("refresh_interval", 15)))
        refresh_note = QLabel("0 = Sincronizacion automatica desactivada")
        refresh_note.setObjectName("refresh-note")

        autostart_label = QLabel("Autostart")
        self._autostart_checkbox = QCheckBox("Iniciar con el sistema")
        self._autostart_checkbox.setChecked(bool(self._settings.get("autostart_enabled", False)))

        credentials_label = QLabel("Ruta de credentials")
        self._credentials_input = QLineEdit(str(self._settings.get("credentials_path", "")))
        self._credentials_input.setPlaceholderText(str(PROJECT_ROOT / "credentials.json"))
        browse_button = QPushButton("Buscar")
        browse_button.clicked.connect(self._browse_credentials)

        form_layout.addWidget(events_label, 0, 0)
        form_layout.addWidget(self._events_spin, 0, 1)
        form_layout.addWidget(refresh_label, 1, 0)
        form_layout.addWidget(self._refresh_spin, 1, 1)
        form_layout.addWidget(refresh_note, 2, 1)
        form_layout.addWidget(autostart_label, 3, 0)
        form_layout.addWidget(self._autostart_checkbox, 3, 1)
        form_layout.addWidget(credentials_label, 4, 0)
        form_layout.addWidget(self._credentials_input, 4, 1)
        form_layout.addWidget(browse_button, 4, 2)

        button_row = QHBoxLayout()
        button_row.addStretch()
        cancel_button = QPushButton("Cancelar")
        cancel_button.clicked.connect(self.reject)
        save_button = QPushButton("Guardar")
        save_button.clicked.connect(self._save_settings)
        button_row.addWidget(cancel_button)
        button_row.addWidget(save_button)

        layout.addLayout(form_layout)
        layout.addStretch()
        layout.addLayout(button_row)

        self.setStyleSheet(
            """
            QDialog {
                background-color: rgba(30, 35, 45, 235);
                color: #ffffff;
            }
            QLabel {
                font-size: 12px;
            }
            QLineEdit, QSpinBox {
                background-color: rgba(255, 255, 255, 20);
                border: 1px solid rgba(53, 114, 182, 120);
                border-radius: 6px;
                padding: 4px 6px;
                color: #ffffff;
            }
            QCheckBox {
                color: #ffffff;
            }
            QLabel#refresh-note {
                color: #a0a0a0;
                font-size: 10px;
            }
            QPushButton {
                background-color: rgba(53, 114, 182, 160);
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: rgba(53, 114, 182, 210);
            }
            """
        )

    def _browse_credentials(self) -> None:
        """Open a file picker to select credentials.json."""

        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Selecciona credentials.json",
            str(PROJECT_ROOT),
            "JSON (*.json)",
        )
        if selected:
            self._credentials_input.setText(selected)

    def _save_settings(self) -> None:
        """Persist settings and update autostart if needed."""

        self._settings["max_events"] = int(self._events_spin.value())
        self._settings["refresh_interval"] = int(self._refresh_spin.value())
        self._settings["credentials_path"] = self._credentials_input.text().strip()
        self._settings["autostart_enabled"] = self._autostart_checkbox.isChecked()
        save_settings(self._settings)
        self._apply_autostart(self._settings["autostart_enabled"])
        self.accept()

    def _apply_autostart(self, enabled: bool) -> None:
        """Enable or disable the autostart desktop file."""

        autostart_path = get_autostart_path()
        autostart_path.parent.mkdir(parents=True, exist_ok=True)

        if not enabled:
            if autostart_path.exists():
                autostart_path.unlink()
            return

        exec_target = self._resolve_exec_target()
        desktop_entry = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Version=1.0\n"
            "Name=Zyna Calendar\n"
            "PowerBy=FerDev\n"
            "Comment=Widget de escritorio para Google Calendar\n"
            f"Exec={exec_target}\n"
            f"Path={PROJECT_ROOT}\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n"
            "StartupNotify=false\n"
        )
        autostart_path.write_text(desktop_entry, encoding="utf-8")

    def _resolve_exec_target(self) -> str:
        """Return the best executable path for autostart."""

        system_entry = Path("/usr/bin/zyna-calendar")
        if system_entry.exists():
            return str(system_entry)

        return f"{sys.executable} {PROJECT_ROOT / 'main.py'}"
