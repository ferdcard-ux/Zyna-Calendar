"""Configuration dialog for Zyna-Calendar settings."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ui.update_dialog import UpdateDialog
from utils.config import (
    CUSTOM_THEME_KEY,
    MAX_OPACITY,
    MIN_OPACITY,
    PROJECT_ROOT,
    THEMES,
    contrast_ratio,
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
        self.setMinimumWidth(420)

        icon_path = get_app_icon_path()
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._settings = load_settings()
        self._custom_hex_inputs: dict[str, QLineEdit] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        """Construct the dialog with General and Appearance tabs."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        tabs = QTabWidget()
        tabs.addTab(self._build_general_tab(), "General")
        tabs.addTab(self._build_appearance_tab(), "Apariencia")
        tabs.addTab(self._build_update_tab(), "Actualizar")
        layout.addWidget(tabs)

        button_row = QHBoxLayout()
        button_row.addStretch()
        cancel_button = QPushButton("Cancelar")
        cancel_button.clicked.connect(self.reject)
        save_button = QPushButton("Guardar")
        save_button.clicked.connect(self._save_settings)
        button_row.addWidget(cancel_button)
        button_row.addWidget(save_button)
        layout.addLayout(button_row)

        self.setStyleSheet(self._build_stylesheet())

    def _build_general_tab(self) -> QWidget:
        """Build the tab with sync and credential options."""

        tab = QWidget()
        form_layout = QGridLayout(tab)
        form_layout.setContentsMargins(8, 8, 8, 8)
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

        return tab

    def _build_update_tab(self) -> QWidget:
        """Build the tab with update repository and auto-check options."""

        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        repo_label = QLabel("Repositorio de actualizaciones (owner/repo)")
        self._repo_input = QLineEdit(str(self._settings.get("update_repo", "")))
        self._repo_input.setPlaceholderText("ej. ferdev/zyna-calendar")
        repo_hint = QLabel("Deja el campo vacio para desactivar las actualizaciones.")
        repo_hint.setObjectName("refresh-note")
        layout.addWidget(repo_label)
        layout.addWidget(self._repo_input)
        layout.addWidget(repo_hint)

        self._auto_check_checkbox = QCheckBox("Buscar actualizaciones automaticamente")
        self._auto_check_checkbox.setChecked(bool(self._settings.get("update_auto_check", True)))
        auto_hint = QLabel("Comprueba cada 12 horas y al iniciar la aplicacion.")
        auto_hint.setObjectName("refresh-note")
        layout.addWidget(self._auto_check_checkbox)
        layout.addWidget(auto_hint)

        check_now_button = QPushButton("Buscar actualizaciones ahora")
        check_now_button.clicked.connect(self._open_update_dialog)
        layout.addWidget(check_now_button)

        layout.addStretch()
        return tab

    def _open_update_dialog(self) -> None:
        """Open the update dialog without closing the configuration."""

        dialog = UpdateDialog(self)
        dialog.exec()

    def _build_appearance_tab(self) -> QWidget:
        """Build the tab with transparency, themes and custom colors."""

        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        opacity_label = QLabel("Transparencia de la ventana")
        self._opacity_slider = QSlider()
        self._opacity_slider.setOrientation(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(MIN_OPACITY, MAX_OPACITY)
        self._opacity_slider.setValue(int(self._settings.get("opacity", 78)))
        self._opacity_value = QLabel(f"{self._opacity_slider.value()}%")
        self._opacity_slider.valueChanged.connect(self._on_opacity_changed)
        opacity_hint = QLabel(f"Minimo seguro {MIN_OPACITY}% para mantener el texto legible.")
        opacity_hint.setObjectName("refresh-note")

        opacity_row = QHBoxLayout()
        opacity_row.addWidget(opacity_label)
        opacity_row.addStretch()
        opacity_row.addWidget(self._opacity_value)
        layout.addLayout(opacity_row)
        layout.addWidget(self._opacity_slider)
        layout.addWidget(opacity_hint)

        theme_label = QLabel("Tema de color")
        self._theme_combo = QComboBox()
        for theme_key, theme_data in THEMES.items():
            self._theme_combo.addItem(theme_data["name"], theme_key)
        self._theme_combo.addItem("Personalizado", CUSTOM_THEME_KEY)
        current_theme = str(self._settings.get("theme", "classic"))
        theme_index = self._theme_combo.findData(current_theme)
        self._theme_combo.setCurrentIndex(max(0, theme_index))
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        layout.addWidget(theme_label)
        layout.addWidget(self._theme_combo)

        custom_label = QLabel("Colores personalizados")
        custom_label.setObjectName("custom-title")
        layout.addWidget(custom_label)

        color_grid = QGridLayout()
        color_grid.setHorizontalSpacing(10)
        color_grid.setVerticalSpacing(8)
        color_keys = [
            ("theme_bg_color", "Fondo", "#1E232D"),
            ("theme_card_color", "Tarjetas", "#2C3340"),
            ("theme_text_color", "Texto", "#FFFFFF"),
            ("theme_accent_color", "Acento", "#3572B6"),
        ]
        for row, (settings_key, label_text, default_hex) in enumerate(color_keys):
            color_label = QLabel(label_text)
            color_input = QLineEdit(str(self._settings.get(settings_key, default_hex)))
            color_input.setObjectName("hex-input")
            color_input.setMaxLength(7)
            color_input.setPlaceholderText("#RRGGBB")
            color_input.textChanged.connect(self._on_custom_color_changed)
            pick_button = QPushButton("Seleccionar")
            pick_button.clicked.connect(
                lambda _checked=False, key=settings_key, line_edit=color_input: self._pick_color(
                    key, line_edit
                )
            )
            color_grid.addWidget(color_label, row, 0)
            color_grid.addWidget(color_input, row, 1)
            color_grid.addWidget(pick_button, row, 2)
            self._custom_hex_inputs[settings_key] = color_input
        layout.addLayout(color_grid)

        self._contrast_note = QLabel("")
        self._contrast_note.setObjectName("contrast-note")
        self._contrast_note.setWordWrap(True)
        layout.addWidget(self._contrast_note)
        self._update_contrast_note()

        layout.addStretch()
        return tab

    def _on_opacity_changed(self, value: int) -> None:
        """Refresh the opacity percentage label."""

        self._opacity_value.setText(f"{value}%")

    def _on_theme_changed(self, index: int) -> None:
        """Fill the custom color fields from a preset theme."""

        theme_key = self._theme_combo.itemData(index)
        if theme_key == CUSTOM_THEME_KEY:
            return
        theme_data = THEMES.get(str(theme_key))
        if theme_data is None:
            return
        self._custom_hex_inputs["theme_bg_color"].setText(theme_data["bg"])
        self._custom_hex_inputs["theme_card_color"].setText(theme_data["card"])
        self._custom_hex_inputs["theme_text_color"].setText(theme_data["text"])
        self._custom_hex_inputs["theme_accent_color"].setText(theme_data["accent"])

    def _on_custom_color_changed(self, _text: str) -> None:
        """Switch to the custom theme and refresh the contrast hint."""

        if self._theme_combo.currentData() != CUSTOM_THEME_KEY:
            self._theme_combo.setCurrentIndex(self._theme_combo.findData(CUSTOM_THEME_KEY))
        self._update_contrast_note()

    def _pick_color(self, settings_key: str, line_edit: QLineEdit) -> None:
        """Open the native color picker and apply the selection."""

        initial = QColor(line_edit.text() or "#FFFFFF")
        selected = QColorDialog.getColor(initial, self, "Seleccionar color")
        if selected.isValid():
            line_edit.setText(selected.name().upper())
            self._update_contrast_note()

    def _update_contrast_note(self) -> None:
        """Show a warning when text color does not contrast with the background."""

        background = self._custom_hex_inputs["theme_bg_color"].text()
        text = self._custom_hex_inputs["theme_text_color"].text()
        ratio = contrast_ratio(background, text)
        if ratio >= 4.5:
            self._contrast_note.setText(f"Contraste Fondo/Texto: {ratio:.1f}:1 (excelente)")
        elif ratio >= 3.0:
            self._contrast_note.setText(f"Contraste Fondo/Texto: {ratio:.1f}:1 (aceptable)")
        else:
            self._contrast_note.setText(
                f"Contraste Fondo/Texto: {ratio:.1f}:1 (bajo, revisa la legibilidad)"
            )

    def _build_stylesheet(self) -> str:
        """Build the dialog stylesheet."""

        return """
            QDialog {
                background-color: rgba(30, 35, 45, 235);
                color: #ffffff;
            }
            QLabel {
                font-size: 12px;
            }
            QLabel#refresh-note, QLabel#contrast-note {
                color: #a0a0a0;
                font-size: 10px;
            }
            QLabel#custom-title {
                font-size: 12px;
                font-weight: 600;
                margin-top: 6px;
            }
            QLineEdit, QSpinBox, QComboBox {
                background-color: rgba(255, 255, 255, 20);
                border: 1px solid rgba(53, 114, 182, 120);
                border-radius: 6px;
                padding: 4px 6px;
                color: #ffffff;
            }
            QLineEdit#hex-input {
                width: 90px;
            }
            QCheckBox {
                color: #ffffff;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background-color: rgba(255, 255, 255, 40);
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 16px;
                height: 16px;
                margin: -5px 0;
                background-color: #3572b6;
                border-radius: 8px;
            }
            QTabWidget::pane {
                border: 1px solid rgba(53, 114, 182, 120);
                border-radius: 8px;
                top: -1px;
            }
            QTabBar::tab {
                padding: 6px 14px;
                color: #ffffff;
            }
            QTabBar::tab:selected {
                background-color: rgba(53, 114, 182, 160);
                border-radius: 6px;
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
        self._settings["opacity"] = int(self._opacity_slider.value())
        theme_key = str(self._theme_combo.currentData() or CUSTOM_THEME_KEY)
        self._settings["theme"] = theme_key
        self._settings["theme_bg_color"] = self._custom_hex_inputs["theme_bg_color"].text()
        self._settings["theme_card_color"] = self._custom_hex_inputs["theme_card_color"].text()
        self._settings["theme_text_color"] = self._custom_hex_inputs["theme_text_color"].text()
        self._settings["theme_accent_color"] = self._custom_hex_inputs["theme_accent_color"].text()
        self._settings["update_repo"] = self._repo_input.text().strip()
        self._settings["update_auto_check"] = self._auto_check_checkbox.isChecked()
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
