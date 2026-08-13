"""Manual authentication dialog for Google OAuth."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.auth import complete_manual_auth
from utils.config import get_app_icon_path


class AuthWorker(QThread):
    """Background worker to complete OAuth without blocking the UI."""

    completed = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, code: str, parent: QWidget | None = None) -> None:
        """Store the authorization code."""

        super().__init__(parent)
        self._code = code

    def run(self) -> None:
        """Execute the token exchange."""

        try:
            complete_manual_auth(self._code)
        except Exception as error:
            self.failed.emit(str(error))
            return
        self.completed.emit()


class AuthDialog(QDialog):
    """Dialog that guides the user through manual OAuth."""

    def __init__(self, auth_url: str, parent: QWidget | None = None) -> None:
        """Initialize the dialog with the generated auth URL."""

        super().__init__(parent)
        self._auth_url = auth_url
        self.setWindowTitle("Autorización de Google")
        self.setModal(True)
        self.setMinimumWidth(420)

        icon_path = get_app_icon_path()
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._status_label = QLabel("")
        self._worker: AuthWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the dialog content."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("Autorización manual requerida")
        title.setObjectName("auth-title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        url_label = QLabel("1. Copia y abre esta URL en tu navegador:")
        url_label.setObjectName("auth-label")

        url_box = QPlainTextEdit()
        url_box.setReadOnly(True)
        url_box.setPlainText(self._auth_url)
        url_box.setObjectName("auth-url")
        url_box.setFixedHeight(90)

        code_label = QLabel("2. Pega el código de autorización aquí:")
        code_label.setObjectName("auth-label")

        self._code_input = QLineEdit()
        self._code_input.setPlaceholderText("Código de autorización")
        self._code_input.setObjectName("auth-code")
        self._code_input.returnPressed.connect(self._authorize)

        self._status_label.setObjectName("auth-status")
        self._status_label.setWordWrap(True)

        button_row = QHBoxLayout()
        button_row.addStretch()
        cancel_button = QPushButton("Cancelar")
        cancel_button.clicked.connect(self.reject)
        confirm_button = QPushButton("Autorizar")
        confirm_button.clicked.connect(self._authorize)
        self._confirm_button = confirm_button
        button_row.addWidget(cancel_button)
        button_row.addWidget(confirm_button)

        layout.addWidget(title)
        layout.addWidget(url_label)
        layout.addWidget(url_box)
        layout.addWidget(code_label)
        layout.addWidget(self._code_input)
        layout.addWidget(self._status_label)
        layout.addLayout(button_row)

        self.setStyleSheet(
            """
            QDialog {
                background-color: rgba(30, 35, 45, 235);
                color: #ffffff;
            }
            QLabel#auth-title {
                font-size: 15px;
                font-weight: 600;
            }
            QLabel#auth-label {
                font-size: 12px;
                color: #a0a0a0;
            }
            QPlainTextEdit#auth-url {
                background-color: rgba(255, 255, 255, 20);
                border: 1px solid rgba(53, 114, 182, 120);
                border-radius: 6px;
                color: #ffffff;
            }
            QLineEdit#auth-code {
                background-color: rgba(255, 255, 255, 20);
                border: 1px solid rgba(53, 114, 182, 120);
                border-radius: 6px;
                padding: 4px 6px;
                color: #ffffff;
            }
            QLabel#auth-status {
                color: #a0a0a0;
                font-size: 11px;
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

    def _authorize(self) -> None:
        """Complete the manual authorization using the provided code."""

        code = self._code_input.text().strip()
        if not code:
            self._status_label.setText("Ingresa el código para continuar.")
            return

        if self._worker is not None and self._worker.isRunning():
            return

        self._status_label.setText("Validando código...")
        self._confirm_button.setEnabled(False)
        self._code_input.setEnabled(False)

        self._worker = AuthWorker(code, self)
        self._worker.completed.connect(self._handle_success)
        self._worker.failed.connect(self._handle_failure)
        self._worker.start()

    def _handle_success(self) -> None:
        """Close the dialog when authorization succeeds."""

        self._status_label.setText("Autenticación completada. Sincronizando...")
        self.accept()

    def _handle_failure(self, message: str) -> None:
        """Restore the UI if authorization fails."""

        readable_message = message
        if "invalid_grant" in message or "Bad Request" in message:
            readable_message = "Código inválido o expirado. Intenta nuevamente."
        self._status_label.setText(f"Error al autorizar: {readable_message}")
        self._confirm_button.setEnabled(True)
        self._code_input.setEnabled(True)
