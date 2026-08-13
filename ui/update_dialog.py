"""Update dialog that checks, downloads and installs new releases."""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from utils.config import APP_VERSION, get_app_icon_path, load_settings
from utils.update_checker import (
    AssetInfo,
    ReleaseInfo,
    UpdateCheckError,
    UpdateDownloadError,
    download_asset,
    fetch_expected_digest,
    fetch_latest_release,
    install_deb,
    is_newer_version,
    sha256_of,
    verify_digest,
)

logger = logging.getLogger("zyna-calendar")


class CheckReleaseThread(QThread):
    """Background thread that queries the latest GitHub release."""

    finished_ok = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, repo: str, parent: QWidget | None = None) -> None:
        """Store the repository slug used for the request."""

        super().__init__(parent)
        self._repo = repo

    def run(self) -> None:
        """Fetch the release payload in a worker thread."""

        try:
            release = fetch_latest_release(self._repo)
        except UpdateCheckError as error:
            self.failed.emit(str(error))
            return
        except Exception:  # pragma: no cover - defensive thread fallback
            logger.exception("Unexpected error in update check thread")
            self.failed.emit("No se pudo consultar las actualizaciones.")
            return
        self.finished_ok.emit(release)


class DownloadThread(QThread):
    """Background thread that downloads the selected .deb package."""

    progress_changed = pyqtSignal(int, int)
    finished_ok = pyqtSignal(str, bool)
    failed = pyqtSignal(str)

    def __init__(self, asset: AssetInfo, destination: Path, parent: QWidget | None = None) -> None:
        """Store the asset and the download destination."""

        super().__init__(parent)
        self._asset = asset
        self._destination = destination

    def run(self) -> None:
        """Download the package and verify its SHA-256 digest."""

        try:
            download_asset(self._asset, self._destination, self.progress_changed.emit)
        except UpdateDownloadError as error:
            self.failed.emit(str(error))
            return

        expected = None
        if self._asset.digest_url:
            expected = fetch_expected_digest(self._asset.digest_url)
        verified = bool(expected and verify_digest(self._destination, expected))
        self.finished_ok.emit(str(self._destination), verified)


class InstallThread(QThread):
    """Background thread that installs the downloaded package."""

    finished_ok = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, deb_path: Path, parent: QWidget | None = None) -> None:
        """Store the package path used by the privilege prompt."""

        super().__init__(parent)
        self._deb_path = deb_path

    def run(self) -> None:
        """Run the package installation in a worker thread."""

        try:
            install_deb(self._deb_path)
        except UpdateDownloadError as error:
            self.failed.emit(str(error))
            return
        except Exception:  # pragma: no cover - defensive thread fallback
            logger.exception("Unexpected error in install thread")
            self.failed.emit("La instalacion no pudo completarse.")
            return
        self.finished_ok.emit("Instalacion completada con exito.")


class UpdateDialog(QDialog):
    """Dialog that checks, downloads and installs app updates."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the dialog and start an automatic release check."""

        super().__init__(parent)
        self.setWindowTitle("Actualizar Zyna-Calendar")
        self.setModal(True)
        self.setMinimumSize(460, 380)

        icon_path = get_app_icon_path()
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._release: ReleaseInfo | None = None
        self._downloaded_path: Path | None = None
        self._digest_verified = False
        self._settings = load_settings()
        self._repo = str(self._settings.get("update_repo", "")).strip()

        self._check_thread: CheckReleaseThread | None = None
        self._download_thread: DownloadThread | None = None
        self._install_thread: InstallThread | None = None

        self._build_ui()
        self._start_check()

    def _build_ui(self) -> None:
        """Construct the dialog layout."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        self._version_label = QLabel(f"Version actual: {APP_VERSION}")
        self._version_label.setObjectName("version-label")
        layout.addWidget(self._version_label)

        self._status_label = QLabel("Buscando actualizaciones...")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        self._notes = QTextEdit()
        self._notes.setReadOnly(True)
        self._notes.setPlaceholderText("Notas de la version disponible.")
        self._notes.setMaximumHeight(140)
        layout.addWidget(self._notes)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        self._hash_label = QLabel("")
        self._hash_label.setObjectName("hash-label")
        self._hash_label.setWordWrap(True)
        layout.addWidget(self._hash_label)

        layout.addStretch()

        button_row = QHBoxLayout()
        button_row.addStretch()

        self._check_button = QPushButton("Buscar actualizaciones")
        self._check_button.clicked.connect(self._start_check)
        button_row.addWidget(self._check_button)

        self._download_button = QPushButton("Descargar")
        self._download_button.setEnabled(False)
        self._download_button.clicked.connect(self._start_download)
        button_row.addWidget(self._download_button)

        self._install_button = QPushButton("Instalar")
        self._install_button.setEnabled(False)
        self._install_button.clicked.connect(self._start_install)
        button_row.addWidget(self._install_button)

        close_button = QPushButton("Cerrar")
        close_button.clicked.connect(self.reject)
        button_row.addWidget(close_button)

        layout.addLayout(button_row)
        self.setStyleSheet(self._build_stylesheet())

    def _build_stylesheet(self) -> str:
        """Build the dialog stylesheet matching the config dialog."""

        return """
            QDialog {
                background-color: rgba(30, 35, 45, 235);
                color: #ffffff;
            }
            QLabel {
                font-size: 12px;
            }
            QLabel#version-label, QLabel#hash-label {
                color: #a0a0a0;
                font-size: 10px;
            }
            QTextEdit {
                background-color: rgba(255, 255, 255, 20);
                border: 1px solid rgba(53, 114, 182, 120);
                border-radius: 6px;
                padding: 6px;
                color: #ffffff;
                font-size: 11px;
            }
            QProgressBar {
                background-color: rgba(255, 255, 255, 20);
                border: 1px solid rgba(53, 114, 182, 120);
                border-radius: 6px;
                color: #ffffff;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #3572b6;
                border-radius: 5px;
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
            QPushButton:disabled {
                background-color: rgba(53, 114, 182, 70);
                color: rgba(255, 255, 255, 120);
            }
            """

    def _start_check(self) -> None:
        """Start a background release check."""

        if not self._repo:
            self._status_label.setText(
                "No hay repositorio configurado. Indicalo en la pestana Actualizar."
            )
            return

        self._check_button.setEnabled(False)
        self._download_button.setEnabled(False)
        self._install_button.setEnabled(False)
        self._notes.clear()
        self._hash_label.clear()
        self._status_label.setText("Buscando actualizaciones...")

        self._check_thread = CheckReleaseThread(self._repo, self)
        self._check_thread.finished_ok.connect(self._on_check_finished)
        self._check_thread.failed.connect(self._on_check_failed)
        self._check_thread.finished.connect(self._check_button.setEnabled)
        self._check_thread.start()

    def _on_check_finished(self, release: ReleaseInfo) -> None:
        """Display the fetched release and enable download when newer."""

        self._release = release
        self._check_button.setEnabled(True)

        if release.asset is None:
            self._status_label.setText("No se encontro un paquete .deb en la release.")
            return

        if not is_newer_version(release.version, APP_VERSION):
            self._status_label.setText(f"Ya tienes la ultima version ({APP_VERSION}).")
            self._notes.setPlainText(release.body.strip())
            return

        self._status_label.setText(f"Nueva version {release.version} disponible.")
        self._notes.setPlainText(release.body.strip())
        self._download_button.setEnabled(True)

    def _on_check_failed(self, message: str) -> None:
        """Show the check error to the user."""

        self._check_button.setEnabled(True)
        self._status_label.setText(message)

    def _start_download(self) -> None:
        """Download the selected package with progress reporting."""

        if self._release is None or self._release.asset is None:
            return

        self._check_button.setEnabled(False)
        self._download_button.setEnabled(False)
        self._install_button.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._status_label.setText("Descargando...")

        destination = Path.home() / "Downloads" / self._release.asset.name
        self._download_thread = DownloadThread(self._release.asset, destination, self)
        self._download_thread.progress_changed.connect(self._on_download_progress)
        self._download_thread.finished_ok.connect(self._on_download_finished)
        self._download_thread.failed.connect(self._on_download_failed)
        self._download_thread.start()

    def _on_download_progress(self, written: int, total: int) -> None:
        """Update the progress bar while downloading."""

        percent = int(written * 100 / total) if total > 0 else 0
        self._progress_bar.setValue(percent)

    def _on_download_finished(self, path: str, verified: bool) -> None:
        """Show the download result and enable installation."""

        self._downloaded_path = Path(path)
        self._digest_verified = verified
        self._progress_bar.setValue(100)
        self._check_button.setEnabled(True)

        digest = sha256_of(self._downloaded_path)
        if verified:
            self._status_label.setText("Descarga completada y verificada.")
            self._hash_label.setText(f"SHA-256 (verificado): {digest}")
        else:
            self._status_label.setText(
                "Descarga completada sin digest publicado; se muestran los datos reales."
            )
            self._hash_label.setText(f"SHA-256 real: {digest}")

        self._install_button.setEnabled(True)

    def _on_download_failed(self, message: str) -> None:
        """Restore the buttons and show the failure."""

        self._progress_bar.setVisible(False)
        self._check_button.setEnabled(True)
        self._download_button.setEnabled(True)
        self._status_label.setText(message)

    def _start_install(self) -> None:
        """Start the package installation through a privilege prompt."""

        if self._downloaded_path is None:
            return

        self._check_button.setEnabled(False)
        self._download_button.setEnabled(False)
        self._install_button.setEnabled(False)
        self._status_label.setText("Instalando...")

        self._install_thread = InstallThread(self._downloaded_path, self)
        self._install_thread.finished_ok.connect(self._on_install_finished)
        self._install_thread.failed.connect(self._on_install_failed)
        self._install_thread.start()

    def _on_install_finished(self, message: str) -> None:
        """Report a successful installation."""

        self._status_label.setText(f"{message} Reinicia la aplicacion para aplicar el cambio.")
        self._install_button.setEnabled(True)
        self._check_button.setEnabled(True)

    def _on_install_failed(self, message: str) -> None:
        """Restore the buttons and show the installation error."""

        self._install_button.setEnabled(True)
        self._check_button.setEnabled(True)
        self._status_label.setText(message)
