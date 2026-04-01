"""PyQt6 widget that renders upcoming Google Calendar events."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import webbrowser
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from PyQt6.QtCore import QObject, QEvent, QPoint, QThread, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import (
    QAction,
    QColor,
    QCloseEvent,
    QGuiApplication,
    QIcon,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QMenu,
    QLabel,
    QSizePolicy,
    QDialog,
    QVBoxLayout,
    QWidget,
)

from core.auth import MissingCredentialsError
from core.calendar_service import CalendarEvent, CalendarSyncResult, LOCAL_TIMEZONE
from ui.config_dialog import ConfigDialog
from utils.config import get_app_icon_path, load_settings, save_window_position
from utils.datetime_helpers import format_event_datetime

REFRESH_INTERVAL_MINUTES = 15
POSITION_SAVE_DELAY_MS = 250
NOTIFICATION_LEAD_MINUTES = 10
NOTIFICATION_CHECK_INTERVAL_MS = 60 * 1000
logger = logging.getLogger("zyna-calendar")


class ClickableLabel(QLabel):
    """Minimal clickable label used for lightweight interactions."""

    clicked = pyqtSignal()

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        """Initialize the clickable label."""

        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Emit a signal when the label is released with the left button."""

        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self.clicked.emit()

        super().mouseReleaseEvent(event)


class EventSyncThread(QThread):
    """Background thread that fetches events without blocking the UI."""

    sync_completed = pyqtSignal(object)
    sync_failed = pyqtSignal(str)
    def __init__(
        self,
        events_provider: Callable[[], CalendarSyncResult],
        parent: QWidget | None = None,
    ) -> None:
        """Store the callable used to load events in the background."""

        super().__init__(parent)
        self._events_provider = events_provider

    def run(self) -> None:
        """Execute the blocking Calendar API request in a worker thread."""

        try:
            result = self._events_provider()
        except MissingCredentialsError as error:
            self.sync_failed.emit(str(error))
            return
        except Exception:  # pragma: no cover - defensive thread fallback
            logger.exception("Unexpected error in background sync thread")
            self.sync_failed.emit("No se pudo actualizar el calendario.")
            return

        self.sync_completed.emit(result)


class EventCard(QWidget):
    """Compact event row rendered with labels and QPainter."""

    def __init__(self, event: CalendarEvent, parent: QWidget | None = None) -> None:
        """Build a single event card."""

        super().__init__(parent)
        self._event = event
        self._is_hovered = False
        self.setObjectName("event-card")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(62)
        self._build_ui()

    @property
    def drag_handles(self) -> tuple[QWidget, ...]:
        """Return the widgets that should initiate widget dragging."""

        return (self, self._title_label, self._time_label)

    def paintEvent(self, event) -> None:  # noqa: N802
        """Draw the event background with a subtle hover transition."""

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        background_color = QColor(44, 51, 64, 168)
        if self._is_hovered:
            background_color = QColor(56, 65, 81, 188)

        border_color = QColor("#3572b6")
        border_color.setAlpha(95)

        painter.setPen(QPen(border_color, 1))
        painter.setBrush(background_color)
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 12, 12)
        super().paintEvent(event)

    def enterEvent(self, event) -> None:  # noqa: N802
        """Activate hover styling when the pointer enters the card."""

        self._is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        """Restore the base style when the pointer leaves the card."""

        self._is_hovered = False
        self.update()
        super().leaveEvent(event)

    def _build_ui(self) -> None:
        """Create labels for title, time and browser link."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        self._title_label = QLabel(self._event.title)
        self._title_label.setObjectName("event_summary")
        self._title_label.setWordWrap(True)
        self._title_label.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.MinimumExpanding,
        )
        self._title_label.setContentsMargins(0, 2, 0, 4)
        font_metrics = self._title_label.fontMetrics()
        self._title_label.setMinimumHeight(font_metrics.height() + 6)

        self._time_label = QLabel(
            format_event_datetime(self._event.start_at, self._event.is_all_day)
        )
        self._time_label.setObjectName("event-time")

        self._link_label = ClickableLabel("Abrir evento")
        self._link_label.setObjectName("event-link")
        self._link_label.clicked.connect(self._open_event_link)

        layout.addWidget(self._title_label)
        layout.addWidget(self._time_label)
        layout.addWidget(self._link_label)

    def _open_event_link(self) -> None:
        """Open the Google Calendar event in the default browser."""

        if self._event.html_link:
            webbrowser.open(self._event.html_link, new=2)


class CalendarWidget(QWidget):
    """Frameless desktop widget that lists upcoming events."""

    def __init__(
        self,
        events_provider: Callable[[], CalendarSyncResult],
        settings: dict[str, Any],
    ) -> None:
        """Build the floating calendar widget.

        Args:
            events_provider: Callable that returns the next calendar events.
            settings: Local widget settings loaded from disk.
        """

        super().__init__()
        self._events_provider = events_provider
        self._settings = settings
        self._drag_offset: QPoint | None = None
        self._sync_thread: EventSyncThread | None = None
        self._current_events: list[CalendarEvent] = []
        self._notified_event_ids: set[str] = set()
        self._configure_position_persistence()
        self._build_ui()
        self._apply_window_settings()
        self._configure_refresh_timer()
        self._configure_notification_timer()
        self.refresh_events()

    def refresh_events(self) -> None:
        """Start a background sync if no sync is already running."""

        if self._sync_thread is not None and self._sync_thread.isRunning():
            self._status_label.setText("Sincronizacion en curso...")
            return

        self._set_sync_enabled(False)
        self._status_label.setText("Sincronizando eventos...")

        self._sync_thread = EventSyncThread(self._events_provider, self)
        self._sync_thread.sync_completed.connect(self._render_sync_result)
        self._sync_thread.sync_failed.connect(self._render_error)
        self._sync_thread.finished.connect(self._handle_sync_finished)
        self._sync_thread.start()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Capture the drag offset for the floating frameless widget."""

        self._begin_drag(event)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Move the widget while the primary mouse button is pressed."""

        self._drag_to(event)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Reset the drag state and persist the latest widget position."""

        self._finish_drag(event)
        super().mouseReleaseEvent(event)

    def moveEvent(self, event) -> None:  # noqa: N802
        """Debounce persistence so the last dragged position survives restarts."""

        self._position_save_timer.start(POSITION_SAVE_DELAY_MS)
        super().moveEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Save the last window position before closing the widget."""

        self._persist_position()
        if self._sync_thread is not None and self._sync_thread.isRunning():
            self._sync_thread.wait(500)
        super().closeEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Forward mouse drag events from child widgets to the window."""

        if event.type() == QEvent.Type.MouseButtonPress:
            self._begin_drag(event)
        elif event.type() == QEvent.Type.MouseMove:
            self._drag_to(event)
        elif event.type() == QEvent.Type.MouseButtonRelease:
            self._finish_drag(event)

        return super().eventFilter(watched, event)

    def _build_ui(self) -> None:
        """Create the minimal widget layout and styles."""

        self.setObjectName("calendar-widget")

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("calendar-card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 14, 14, 14)
        card_layout.setSpacing(10)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel("Zyna Calendar")
        title_label.setObjectName("title-label")

        self._menu_button = HamburgerButton()
        self._menu_button.setObjectName("menu-button")
        self._menu_button.clicked.connect(self._show_menu)
        self._menu = self._build_menu()

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self._menu_button)

        self._status_label = QLabel("Cargando eventos...")
        self._status_label.setObjectName("status-label")
        self._status_label.setWordWrap(True)

        self._events_container = QWidget()
        self._events_container.setObjectName("events-container")
        self._events_layout = QVBoxLayout(self._events_container)
        self._events_layout.setContentsMargins(0, 0, 0, 0)
        self._events_layout.setSpacing(8)

        footer_label = QLabel("Arrastra el widget para moverlo por el escritorio.")
        footer_label.setObjectName("footer-label")
        footer_label.setWordWrap(True)

        card_layout.addLayout(header_layout)
        card_layout.addWidget(self._status_label)
        card_layout.addWidget(self._events_container)
        card_layout.addWidget(footer_label)
        root_layout.addWidget(card)

        self._register_drag_handle(self)
        self._register_drag_handle(card)
        self._register_drag_handle(title_label)
        self._register_drag_handle(self._status_label)
        self._register_drag_handle(footer_label)

        self.setStyleSheet(
            """
            QWidget#calendar-widget {
                background: transparent;
            }
            QFrame#calendar-card {
                background-color: rgba(30, 35, 45, 200);
                border: 1px solid #3572b6;
                border-radius: 12px;
            }
            QLabel#title-label {
                color: #ffffff;
                font-size: 17px;
                font-weight: 600;
            }
            QLabel#status-label {
                color: #a0a0a0;
                font-size: 11px;
            }
            QWidget#menu-button {
                background: transparent;
            }
            QWidget#events-container {
                background: transparent;
            }
            QLabel#event_summary {
                background: transparent;
                color: #ffffff;
                font-size: 13px;
                font-weight: 600;
                margin-top: -6px;    /* <--- Desplazarlo hacia arriba */
                padding-top: 0px;
                padding-bottom: 0px; /* Mantenerlo alineado con los bordes (y, g, p) */
            }
            QLabel#event-time,
            QLabel#footer-label {
                background: transparent;
                color: #a0a0a0;
                font-size: 11px;
            }
            QLabel#event-link {
                background: transparent;
                color: #7fb2ff;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#event-link:hover {
                color: #ffffff;
            }
            QMenu {
                background-color: rgba(30, 35, 45, 235);
                color: #ffffff;
                border: 1px solid #3572b6;
                border-radius: 10px;
            }
            QMenu::item {
                padding: 6px 18px;
            }
            QMenu::item:selected {
                background-color: rgba(53, 114, 182, 160);
            }
            """
        )

    def _apply_window_settings(self) -> None:
        """Apply frameless and transparent window options."""

        bottom_hint = getattr(
            Qt.WindowType,
            "WindowStaysAtBottomHint",
            Qt.WindowType.WindowStaysOnBottomHint,
        )
        flags = (
            Qt.WindowType.FramelessWindowHint
            | bottom_hint
            | Qt.WindowType.Tool
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(int(self._settings["window_width"]))
        self.move(
            int(self._settings["window_x"]),
            int(self._settings["window_y"]),
        )
        self._ensure_on_screen()
        icon_path = get_app_icon_path()
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

    def _configure_refresh_timer(self) -> None:
        """Refresh the event list periodically with a lightweight timer."""

        if hasattr(self, "_refresh_timer") and self._refresh_timer is not None:
            self._refresh_timer.stop()
            self._refresh_timer.deleteLater()

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh_events)
        interval_minutes = int(self._settings.get("refresh_interval", 15))
        if interval_minutes > 0:
            interval_ms = interval_minutes * 60 * 1000
            self._refresh_timer.start(interval_ms)
        else:
            self._refresh_timer.stop()

    def _configure_position_persistence(self) -> None:
        """Configure a debounce timer for saving widget coordinates."""

        self._position_save_timer = QTimer(self)
        self._position_save_timer.setSingleShot(True)
        self._position_save_timer.timeout.connect(self._persist_position)

    def _configure_notification_timer(self) -> None:
        """Check periodically whether the next event is close enough to notify."""

        self._notification_timer = QTimer(self)
        self._notification_timer.timeout.connect(self._check_upcoming_event_notification)
        self._notification_timer.start(NOTIFICATION_CHECK_INTERVAL_MS)

    def _render_sync_result(self, result: CalendarSyncResult) -> None:
        """Replace the event list after a successful sync or cache fallback."""

        self._clear_events()
        self._current_events = result.events
        self._prune_notified_events()

        if not result.events:
            self._status_label.setText(result.status_message)
            placeholder_text = "No hay eventos programados."
            if result.is_from_cache:
                placeholder_text = "No hay eventos recientes en caché."
            elif "Sin conexión" in result.status_message:
                placeholder_text = "Sin conexión y sin caché local."
            self._add_placeholder_label(placeholder_text)
            return

        self._status_label.setText(result.status_message)

        for event in result.events:
            event_card = EventCard(event, self._events_container)
            self._events_layout.addWidget(event_card)
            for drag_handle in event_card.drag_handles:
                self._register_drag_handle(drag_handle)

        self._events_container.adjustSize()
        self.adjustSize()
        self._ensure_on_screen()
        self._check_upcoming_event_notification()

    def _render_error(self, message: str) -> None:
        """Show a lightweight error state when sync fails."""

        self._clear_events()
        self._current_events = []
        self._prune_notified_events()
        self._status_label.setText(message)
        self._add_placeholder_label("Revisa tus credenciales o la red.")
        self._events_container.adjustSize()
        self.adjustSize()
        self._ensure_on_screen()

    def _handle_sync_finished(self) -> None:
        """Restore the manual sync control after the background job ends."""

        self._set_sync_enabled(True)
        if self._sync_thread is not None:
            self._sync_thread.deleteLater()
            self._sync_thread = None

    def _clear_events(self) -> None:
        """Remove every event row from the container layout."""

        while self._events_layout.count():
            item = self._events_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _add_placeholder_label(self, message: str) -> None:
        """Show a simple placeholder row when there are no event cards."""

        placeholder = QLabel(message)
        placeholder.setObjectName("event-time")
        placeholder.setWordWrap(True)
        self._events_layout.addWidget(placeholder)

    def _set_sync_enabled(self, is_enabled: bool) -> None:
        """Toggle the manual sync label state."""

        self._menu_button.setEnabled(is_enabled)

    def _register_drag_handle(self, widget: QWidget) -> None:
        """Install an event filter so dragging works across the widget."""

        widget.installEventFilter(self)

    def _begin_drag(self, event: QMouseEvent) -> None:
        """Store the offset required to move the widget."""

        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def _drag_to(self, event: QMouseEvent) -> None:
        """Move the widget according to the current cursor position."""

        if self._drag_offset and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)

    def _finish_drag(self, event: QMouseEvent) -> None:
        """Clear drag state and save the latest coordinates."""

        if event.button() == Qt.MouseButton.LeftButton and self._drag_offset is not None:
            self._persist_position()
            self._drag_offset = None

    def _persist_position(self) -> None:
        """Save the current widget coordinates into local settings."""

        self._settings = save_window_position(self.x(), self.y())

    def _ensure_on_screen(self) -> None:
        """Clamp the widget position so it remains visible on the screen."""

        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return

        geometry = screen.availableGeometry()
        max_x = geometry.x() + max(0, geometry.width() - self.width())
        max_y = geometry.y() + max(0, geometry.height() - self.height())

        new_x = min(max(self.x(), geometry.x()), max_x)
        new_y = min(max(self.y(), geometry.y()), max_y)

        if (new_x, new_y) != (self.x(), self.y()):
            self.move(new_x, new_y)
            self._persist_position()

    def _check_upcoming_event_notification(self) -> None:
        """Notify when the next timed event starts within ten minutes."""

        now = datetime.now(LOCAL_TIMEZONE)
        next_event = next(
            (
                event
                for event in self._current_events
                if not event.is_all_day and event.start_at >= now
            ),
            None,
        )

        if next_event is None:
            return

        time_until_event = next_event.start_at - now
        if (
            timedelta()
            <= time_until_event
            <= timedelta(minutes=NOTIFICATION_LEAD_MINUTES)
            and next_event.event_id not in self._notified_event_ids
        ):
            self._send_desktop_notification(next_event)
            self._notified_event_ids.add(next_event.event_id)

    def _send_desktop_notification(self, event: CalendarEvent) -> None:
        """Send a native Linux notification using notify-send."""

        notification_body = f"{event.title}\nComienza a las {event.start_at.strftime('%H:%M')}"
        try:
            subprocess.run(
                [
                    "notify-send",
                    "--app-name=Zyna Calendar",
                    "Próximo evento",
                    notification_body,
                ],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            logger.warning("notify-send is not available in this environment")
        except Exception:
            logger.exception("Failed to send desktop notification")

    def _prune_notified_events(self) -> None:
        """Keep notification state only for events still present in memory."""

        active_event_ids = {event.event_id for event in self._current_events}
        self._notified_event_ids.intersection_update(active_event_ids)

    def _build_menu(self) -> QMenu:
        """Create the menu for sync, settings, and lifecycle actions."""

        menu = QMenu(self)

        sync_action = QAction("Sync Manual", self)
        sync_action.triggered.connect(self.refresh_events)
        menu.addAction(sync_action)

        config_action = QAction("Configuracion", self)
        config_action.triggered.connect(self._open_config_dialog)
        menu.addAction(config_action)

        info_action = QAction("Info", self)
        info_action.triggered.connect(self._open_info_dialog)
        menu.addAction(info_action)

        restart_action = QAction("Reiniciar Applet", self)
        restart_action.triggered.connect(self._restart_applet)
        menu.addAction(restart_action)

        exit_action = QAction("Salir", self)
        exit_action.triggered.connect(self.close)
        menu.addAction(exit_action)

        return menu

    def _show_menu(self) -> None:
        """Display the hamburger menu anchored to the button."""

        if not self._menu_button.isEnabled():
            return
        global_pos = self._menu_button.mapToGlobal(self._menu_button.rect().bottomRight())
        self._menu.exec(global_pos)

    def _open_config_dialog(self) -> None:
        """Open the configuration dialog and apply updated settings."""

        dialog = ConfigDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._settings = load_settings()
            self.setFixedWidth(int(self._settings["window_width"]))
            self._configure_refresh_timer()
            self.refresh_events()

    def _open_info_dialog(self) -> None:
        """Display an informational dialog about the widget."""

        dialog = InfoDialog(self)
        dialog.exec()

    def _restart_applet(self) -> None:
        """Restart the Python process cleanly."""

        self._persist_position()
        python_executable = sys.executable
        os.execl(python_executable, python_executable, *sys.argv)


class HamburgerButton(QWidget):
    """Hamburger icon button rendered with QPainter."""

    clicked = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the button surface."""

        super().__init__(parent)
        self.setFixedSize(26, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event) -> None:  # noqa: N802
        """Draw the hamburger icon."""

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#ffffff"))
        pen.setWidth(2)
        painter.setPen(pen)

        y_positions = (6, 11, 16)
        for y in y_positions:
            painter.drawLine(4, y, self.width() - 4, y)
        super().paintEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """Emit the click signal on left-button release."""

        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class InfoDialog(QDialog):
    """Dialog that shows app information."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the info dialog."""

        super().__init__(parent)
        self.setWindowTitle("Zyna Calendar")
        self.setModal(True)
        self.setMinimumWidth(320)

        icon_path = get_app_icon_path()
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        logo_label = QLabel()
        logo_label.setObjectName("info-logo")
        if icon_path.exists():
            pixmap = QPixmap(str(icon_path))
            logo_label.setPixmap(pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio))
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Zyna Calendar")
        title.setObjectName("info-title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        body = QLabel(
            "Widget de escritorio ligero para Google Calendar.\n"
            "Integrado con Zorin OS Lite (XFCE)."
        )
        body.setObjectName("info-body")
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setWordWrap(True)

        layout.addWidget(logo_label)
        layout.addWidget(title)
        layout.addWidget(body)

        self.setStyleSheet(
            """
            QDialog {
                background-color: rgba(30, 35, 45, 235);
                color: #ffffff;
            }
            QLabel#info-title {
                font-size: 16px;
                font-weight: 600;
            }
            QLabel#info-body {
                font-size: 12px;
                color: #a0a0a0;
            }
            """
        )
