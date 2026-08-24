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

from PyQt6.QtCore import QEvent, QObject, QPoint, QRect, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QAction,
    QCloseEvent,
    QColor,
    QEnterEvent,
    QGuiApplication,
    QIcon,
    QMouseEvent,
    QMoveEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.auth import MissingCredentialsError, init_manual_auth, run_loopback_auth
from core.calendar_service import (
    LOCAL_TIMEZONE,
    CalendarClient,
    CalendarEvent,
    CalendarSyncResult,
)
from ui.auth_dialog import AuthDialog
from ui.config_dialog import ConfigDialog
from ui.update_dialog import UpdateDialog
from utils.config import (
    APP_VERSION,
    DEFAULT_OPACITY,
    MAX_OPACITY,
    MIN_OPACITY,
    get_app_icon_path,
    get_theme_palette,
    load_settings,
    rgba_string,
    save_window_position,
)
from utils.datetime_helpers import format_event_datetime
from utils.update_checker import (
    ReleaseInfo,
    UpdateCheckError,
    fetch_latest_release,
    is_newer_version,
)

REFRESH_INTERVAL_MINUTES = 15
POSITION_SAVE_DELAY_MS = 250
NOTIFICATION_LEAD_MINUTES = 10
NOTIFICATION_CHECK_INTERVAL_MS = 60 * 1000
CACHE_WARNING_FLOOR_MINUTES = 30
CLICK_DRAG_THRESHOLD = 6
TODAY_OPACITY_BOOST = 25
SOON_OPACITY_BOOST = 15
SOON_WINDOW_DAYS = 2
UPDATE_CHECK_INTERVAL_MS = 12 * 60 * 60 * 1000
STARTUP_UPDATE_DELAY_MS = 15 * 1000
logger = logging.getLogger("zyna-calendar")


class EventSyncThread(QThread):
    """Background thread that fetches events without blocking the UI."""

    sync_completed = pyqtSignal(object)
    sync_failed = pyqtSignal(object)

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
        except Exception as error:
            logger.exception("Background sync failed")
            self.sync_failed.emit(error)
            return

        self.sync_completed.emit(result)


class SilentUpdateThread(QThread):
    """Background thread that checks for a newer release without a dialog."""

    update_available = pyqtSignal(object)
    up_to_date = pyqtSignal()
    check_failed = pyqtSignal(str)

    def __init__(
        self,
        repo: str,
        parent: QWidget | None = None,
    ) -> None:
        """Store the repository slug used for the request."""

        super().__init__(parent)
        self._repo = repo

    def run(self) -> None:
        """Fetch the latest release and compare versions."""

        try:
            release = fetch_latest_release(self._repo)
        except UpdateCheckError as error:
            self.check_failed.emit(str(error))
            return
        except Exception:  # pragma: no cover - defensive thread fallback
            logger.exception("Unexpected error in silent update check")
            self.check_failed.emit("No se pudo consultar las actualizaciones.")
            return

        if is_newer_version(release.version, APP_VERSION):
            self.update_available.emit(release)
        else:
            self.up_to_date.emit()


class LoopbackAuthThread(QThread):
    """Background worker that runs the automatic loopback OAuth flow."""

    completed = pyqtSignal()
    failed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Build the worker without touching the network yet."""

        super().__init__(parent)

    def run(self) -> None:
        """Run the local-server OAuth flow; fall back signals on any failure."""

        try:
            run_loopback_auth()
        except Exception:
            logger.exception("Loopback OAuth flow failed")
            self.failed.emit()
            return
        self.completed.emit()


class EventCard(QWidget):
    """Compact event row rendered with labels and QPainter."""

    def __init__(
        self,
        event: CalendarEvent,
        parent: QWidget | None = None,
        theme: dict[str, str] | None = None,
        opacity: int | None = None,
    ) -> None:
        """Build a single event card.

        Args:
            event: Calendar event to render.
            parent: Parent container widget.
            theme: Active color palette keys ``bg``/``card``/``accent``.
            opacity: Base opacity percentage for the card background.
        """

        super().__init__(parent)
        self._event = event
        self._is_hovered = False
        self._theme = dict(theme or {})
        self._opacity = opacity if opacity is not None else DEFAULT_OPACITY
        self._press_position: QPoint | None = None
        self.setObjectName("event-card")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(62)
        self._build_ui()

    @property
    def drag_handles(self) -> tuple[QWidget, ...]:
        """Return the widgets that should initiate widget dragging."""

        return (self, self._title_label, self._time_label)

    def paintEvent(self, event: QPaintEvent | None) -> None:  # noqa: N802
        """Draw the event background with a subtle hover transition."""

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        card_hex = self._theme.get("card", "#2C3340")
        accent_hex = self._theme.get("accent", "#3572B6")
        card_color = QColor(card_hex)
        card_color.setAlpha(self._card_alpha())
        if self._is_hovered:
            card_color = card_color.lighter(112)

        border_color = QColor(accent_hex)
        border_color.setAlpha(95)

        painter.setPen(QPen(border_color, 1))
        painter.setBrush(card_color)
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 12, 12)
        super().paintEvent(event)

    def enterEvent(self, event: QEnterEvent | None) -> None:  # noqa: N802
        """Activate hover styling when the pointer enters the card."""

        self._is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent | None) -> None:  # noqa: N802
        """Restore the base style when the pointer leaves the card."""

        self._is_hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        """Remember the press location to distinguish clicks from drags."""

        if event is not None and event.button() == Qt.MouseButton.LeftButton:
            self._press_position = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        """Open the event link when the click was not a drag gesture."""

        if (
            event is not None
            and event.button() == Qt.MouseButton.LeftButton
            and self._was_click(event)
        ):
            self._open_event_link()
        self._press_position = None
        super().mouseReleaseEvent(event)

    def _was_click(self, event: QMouseEvent) -> bool:
        """Return True when the pointer barely moved between press and release."""

        if self._press_position is None:
            return False
        released = event.globalPosition().toPoint()
        return (released - self._press_position).manhattanLength() <= CLICK_DRAG_THRESHOLD

    def _card_alpha(self) -> int:
        """Convert the configured opacity percentage into an alpha channel."""

        clamped = max(MIN_OPACITY, min(MAX_OPACITY, self._opacity))
        return int(round(clamped * 255 / 100))

    def _build_ui(self) -> None:
        """Create labels for title and time."""

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

        layout.addWidget(self._title_label)
        layout.addWidget(self._time_label)

    def _open_event_link(self) -> None:
        """Open the Google Calendar event in the default browser."""

        if self._event.html_link:
            webbrowser.open(self._event.html_link, new=2)


class CalendarWidget(QWidget):
    """Frameless desktop widget that lists upcoming events."""

    def __init__(
        self,
        calendar_client: CalendarClient,
        settings: dict[str, Any],
    ) -> None:
        """Build the floating calendar widget.

        Args:
            calendar_client: Client used to query upcoming calendar events.
            settings: Local widget settings loaded from disk.
        """

        super().__init__()
        self._calendar_client = calendar_client
        self._settings = settings
        self._events_provider = self._make_events_provider()
        self._theme = get_theme_palette(settings)
        self._drag_offset: QPoint | None = None
        self._sync_thread: EventSyncThread | None = None
        self._refresh_timer: QTimer | None = None
        self._current_events: list[CalendarEvent] = []
        self._notified_event_ids: set[str] = set()
        self._notified_today_ids: set[str] = set()
        self._load_notification_state()
        self._mini_icon: QWidget | None = None
        self._minimized_geometry: QRect | None = None
        self._last_sync_warning_key: str | None = None
        self._update_thread: SilentUpdateThread | None = None
        self._configure_position_persistence()
        self._build_ui()
        self._apply_window_settings()
        self._configure_refresh_timer()
        self._configure_notification_timer()
        self._configure_update_timer()
        self.refresh_events()

    def _make_events_provider(self) -> Callable[[], CalendarSyncResult]:
        """Build a provider that always reads the current widget settings."""

        def provider() -> CalendarSyncResult:
            return self._calendar_client.list_upcoming_events(
                calendar_id=str(self._settings.get("calendar_id", "primary")),
                max_results=int(self._settings.get("max_events", 5)),
            )

        return provider

    def refresh_events(self) -> None:
        """Start a background sync if no sync is already running."""

        if self._sync_thread is not None and self._sync_thread.isRunning():
            self._status_label.setText("Sincronización en curso...")
            return

        self._set_sync_enabled(False)
        self._status_label.setText("Sincronizando eventos...")

        self._sync_thread = EventSyncThread(self._events_provider, self)
        self._sync_thread.sync_completed.connect(self._render_sync_result)
        self._sync_thread.sync_failed.connect(self._render_error)
        self._sync_thread.finished.connect(self._handle_sync_finished)
        self._sync_thread.start()

    def mousePressEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        """Capture the drag offset for the floating frameless widget."""

        if event is not None:
            self._begin_drag(event)
        if event is not None:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        """Move the widget while the primary mouse button is pressed."""

        if event is not None:
            self._drag_to(event)
        if event is not None:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        """Reset the drag state and persist the latest widget position."""

        if event is not None:
            self._finish_drag(event)
        if event is not None:
            super().mouseReleaseEvent(event)

    def moveEvent(self, event: QMoveEvent | None) -> None:  # noqa: N802
        """Debounce persistence so the last dragged position survives restarts."""

        self._position_save_timer.start(POSITION_SAVE_DELAY_MS)
        if event is not None:
            super().moveEvent(event)

    def closeEvent(self, event: QCloseEvent | None) -> None:  # noqa: N802
        """Save the last window position before closing the widget."""

        self._persist_position()
        if self._sync_thread is not None and self._sync_thread.isRunning():
            self._sync_thread.wait(500)
        if event is not None:
            super().closeEvent(event)

    def eventFilter(self, watched: QObject | None, event: QEvent | None) -> bool:
        """Forward mouse drag events from child widgets to the window."""

        if isinstance(event, QMouseEvent):
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

        self._menu_button = HamburgerButton(self._theme)
        self._menu_button.setObjectName("menu-button")
        self._menu_button.clicked.connect(self._show_menu)
        self._menu = self._build_menu()

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self._menu_button)

        self._status_label = QLabel("Cargando eventos...")
        self._status_label.setObjectName("status-label")
        self._status_label.setWordWrap(True)

        self._sync_health_label = QLabel("")
        self._sync_health_label.setObjectName("sync-health-label")
        self._sync_health_label.setWordWrap(True)
        self._sync_health_label.hide()

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
        card_layout.addWidget(self._sync_health_label)
        card_layout.addWidget(self._events_container)
        card_layout.addWidget(footer_label)
        root_layout.addWidget(card)

        self._register_drag_handle(self)
        self._register_drag_handle(card)
        self._register_drag_handle(title_label)
        self._register_drag_handle(self._status_label)
        self._register_drag_handle(footer_label)

        self.setStyleSheet(self._build_stylesheet())

    def _build_stylesheet(self) -> str:
        """Build the Qt stylesheet from the active theme and opacity."""

        bg_alpha = self._alpha_from_opacity()
        text_color = self._theme.get("text", "#FFFFFF")
        muted_text = rgba_string(text_color, 175)
        accent = self._theme.get("accent", "#3572B6")
        bg = rgba_string(self._theme.get("bg", "#1E232D"), bg_alpha)

        return f"""
            QWidget#calendar-widget {{
                background: transparent;
            }}
            QFrame#calendar-card {{
                background-color: {bg};
                border: 1px solid {accent};
                border-radius: 12px;
            }}
            QLabel#title-label {{
                color: {text_color};
                font-size: 17px;
                font-weight: 600;
            }}
            QLabel#status-label {{
                color: {muted_text};
                font-size: 11px;
            }}
            QLabel#sync-health-label {{
                color: #ffd27d;
                font-size: 11px;
                font-weight: 600;
                background-color: rgba(120, 72, 10, 110);
                border: 1px solid rgba(255, 190, 92, 120);
                border-radius: 8px;
                padding: 6px 8px;
            }}
            QWidget#menu-button {{
                background: transparent;
            }}
            QWidget#events-container {{
                background: transparent;
            }}
            QLabel#event_summary {{
                background: transparent;
                color: {text_color};
                font-size: 13px;
                font-weight: 600;
                margin-top: -6px;
                padding-top: 0px;
                padding-bottom: 0px;
            }}
            QLabel#event-time,
            QLabel#footer-label {{
                background: transparent;
                color: {muted_text};
                font-size: 11px;
            }}
            QMenu {{
                background-color: {bg};
                color: {text_color};
                border: 1px solid {accent};
                border-radius: 10px;
            }}
            QMenu::item {{
                padding: 6px 18px;
            }}
            QMenu::item:selected {{
                background-color: {rgba_string(accent, 160)};
            }}
            """

    def _alpha_from_opacity(self) -> int:
        """Convert the configured opacity percentage into an alpha channel."""

        opacity = int(self._settings.get("opacity", DEFAULT_OPACITY))
        clamped = max(MIN_OPACITY, min(MAX_OPACITY, opacity))
        return int(round(clamped * 255 / 100))

    def _apply_window_settings(self) -> None:
        """Apply frameless and transparent window options."""

        bottom_hint = getattr(
            Qt.WindowType,
            "WindowStaysAtBottomHint",
            Qt.WindowType.WindowStaysOnBottomHint,
        )
        flags = Qt.WindowType.FramelessWindowHint | bottom_hint | Qt.WindowType.Tool
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
        """Check periodically for upcoming and today event notifications."""

        self._notification_timer = QTimer(self)
        self._notification_timer.timeout.connect(self._check_upcoming_event_notification)
        self._notification_timer.timeout.connect(self._notify_today_events)
        self._notification_timer.start(NOTIFICATION_CHECK_INTERVAL_MS)

    def _configure_update_timer(self) -> None:
        """Schedule a silent update check at startup and every 12 hours."""

        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._check_for_updates_silent)
        self._update_timer.start(UPDATE_CHECK_INTERVAL_MS)

        if self._update_checks_enabled():
            QTimer.singleShot(STARTUP_UPDATE_DELAY_MS, self._check_for_updates_silent)

    def _update_checks_enabled(self) -> bool:
        """Return True when a repo is set and auto-check is enabled."""

        repo = str(self._settings.get("update_repo", "")).strip()
        return bool(repo) and bool(self._settings.get("update_auto_check", True))

    def _check_for_updates_silent(self) -> None:
        """Start a background check that only notifies when a newer version exists."""

        repo = str(self._settings.get("update_repo", "")).strip()
        if not repo:
            return
        if self._update_thread is not None and self._update_thread.isRunning():
            return

        self._update_thread = SilentUpdateThread(repo, self)
        self._update_thread.update_available.connect(self._on_update_available)
        self._update_thread.check_failed.connect(self._on_update_check_failed)
        self._update_thread.start()

    def _on_update_available(self, release: ReleaseInfo) -> None:
        """Show a desktop notification when a newer release exists."""

        self._notify_send(
            "Actualización disponible",
            f"Zyna-Calendar {release.version} está listo para instalar.",
        )

    def _on_update_check_failed(self, message: str) -> None:
        """Log a failed silent check without bothering the user."""

        logger.info("Silent update check skipped: %s", message)

    def _render_sync_result(self, result: CalendarSyncResult) -> None:
        """Replace the event list after a successful sync or cache fallback."""

        self._clear_events()
        self._current_events = result.events
        self._prune_notified_events()
        self._update_sync_health(result)

        if not result.events:
            self._status_label.setText(result.status_message)
            placeholder_text = "No hay eventos programados."
            if result.is_from_cache:
                placeholder_text = "No hay eventos recientes en caché."
            elif "Sin conexión" in result.status_message:
                placeholder_text = "Sin conexión y sin caché local."
            self._add_placeholder_label(placeholder_text)
            self._auto_resize()
            self._ensure_on_screen()
            return

        self._status_label.setText(result.status_message)

        for event in result.events:
            event_card = EventCard(
                event,
                self._events_container,
                theme=self._theme,
                opacity=self._card_opacity_for(event),
            )
            self._events_layout.addWidget(event_card)
            for drag_handle in event_card.drag_handles:
                self._register_drag_handle(drag_handle)

        self._auto_resize()
        self._ensure_on_screen()
        self._check_upcoming_event_notification()
        self._notify_today_events()

    def _render_error(self, error: Exception) -> None:
        """Show a cache-aware error state when sync fails."""

        result = self._calendar_client.fallback_result(error)
        if result.events or result.is_from_cache:
            self._render_sync_result(result)
            return

        self._clear_events()
        self._current_events = []
        self._prune_notified_events()
        self._sync_health_label.setText(
            "La sincronización con Google falló. Revisa credenciales o red."
        )
        self._sync_health_label.show()
        self._status_label.setText(result.status_message)
        self._add_placeholder_label(result.sync_warning or "Revisa tus credenciales o la red.")
        self._auto_resize()
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
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _add_placeholder_label(self, message: str) -> None:
        """Show a simple placeholder row when there are no event cards."""

        placeholder = QLabel(message)
        placeholder.setObjectName("event-time")
        placeholder.setWordWrap(True)
        self._events_layout.addWidget(placeholder)

    def _card_opacity_for(self, event: CalendarEvent) -> int:
        """Return the card opacity emphasizing today and soon events.

        The opacity value is the card background alpha, so a HIGHER value makes
        the card more visible against the desktop. Today gets +25% and events
        within two days +15%, capped at MAX_OPACITY.
        """

        base_opacity = int(self._settings.get("opacity", DEFAULT_OPACITY))
        days_until = (event.start_at.date() - datetime.now(LOCAL_TIMEZONE).date()).days
        if days_until <= 0:
            return min(MAX_OPACITY, base_opacity + TODAY_OPACITY_BOOST)
        if days_until <= SOON_WINDOW_DAYS:
            return min(MAX_OPACITY, base_opacity + SOON_OPACITY_BOOST)
        return base_opacity

    def _auto_resize(self) -> None:
        """Resize the widget so it grows and shrinks with the event count."""

        events_height = self._events_content_height()
        self._events_container.setFixedHeight(events_height)
        self.setMinimumHeight(0)
        self.adjustSize()

    def _events_content_height(self) -> int:
        """Return the height needed to lay out every row in the events list."""

        spacing = self._events_layout.spacing()
        total_height = 0
        row_count = 0
        for index in range(self._events_layout.count()):
            item = self._events_layout.itemAt(index)
            if item is None:
                continue
            widget = item.widget()
            if widget is None:
                continue
            row_count += 1
            hint = widget.sizeHint().height()
            if hint <= 0:
                hint = widget.minimumHeight()
            total_height += max(hint, widget.minimumHeight())

        if row_count > 1 and spacing > 0:
            total_height += (row_count - 1) * spacing
        return total_height

    def _notify_today_events(self) -> None:
        """Send a persistent desktop notification for events happening today."""

        today = datetime.now(LOCAL_TIMEZONE).date()
        today_events = [
            event
            for event in self._current_events
            if event.start_at.date() == today and event.event_id not in self._notified_today_ids
        ]
        for event in today_events:
            self._send_today_event_notification(event)
            self._notified_today_ids.add(event.event_id)
        if today_events:
            self._persist_notification_state()

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
            timedelta() <= time_until_event <= timedelta(minutes=NOTIFICATION_LEAD_MINUTES)
            and next_event.event_id not in self._notified_event_ids
        ):
            self._send_desktop_notification(next_event)
            self._notified_event_ids.add(next_event.event_id)
            self._persist_notification_state()

    def _send_desktop_notification(
        self,
        event: CalendarEvent,
        title: str = "Próximo evento",
        persistent: bool = False,
    ) -> None:
        """Send a native Linux notification using notify-send."""

        notification_body = f"{event.title}\nComienza a las {event.start_at.strftime('%H:%M')}"
        self._notify_send(title, notification_body, persistent=persistent)

    def _send_today_event_notification(self, event: CalendarEvent) -> None:
        """Send a persistent desktop notification for a today event."""

        if event.is_all_day:
            notification_body = f"{event.title}\nEvento de todo el día"
        else:
            notification_body = f"{event.title}\nHoy a las {event.start_at.strftime('%H:%M')}"
        self._notify_send("Evento de hoy", notification_body, persistent=True)

    def _notify_send(self, title: str, body: str, persistent: bool = False) -> None:
        """Run notify-send with optional persistent (non-expiring) notification."""

        command = [
            "notify-send",
            "--app-name=Zyna Calendar",
            title,
            body,
        ]
        if persistent:
            command.insert(2, "--expire-time=0")
        try:
            subprocess.run(
                command,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            logger.warning("notify-send is not available in this environment")
        except Exception:
            logger.exception("Failed to send desktop notification")

    def _load_notification_state(self) -> None:
        """Restore persisted notification state, resetting it on a new day."""

        from utils.config import load_notification_state

        state = load_notification_state()
        today = datetime.now(LOCAL_TIMEZONE).date().isoformat()
        if state.get("date") != today:
            return
        self._notified_today_ids = set(state.get("notified_today", []))
        self._notified_event_ids = set(state.get("notified_upcoming", []))

    def _persist_notification_state(self) -> None:
        """Save which notifications already fired so restarts do not repeat them."""

        from utils.config import save_notification_state

        save_notification_state(self._notified_today_ids, self._notified_event_ids)

    def _prune_notified_events(self) -> None:
        """Keep notification state only for events still present in memory."""

        active_event_ids = {event.event_id for event in self._current_events}
        self._notified_event_ids.intersection_update(active_event_ids)
        self._notified_today_ids.intersection_update(active_event_ids)
        self._persist_notification_state()

    def _update_sync_health(self, result: CalendarSyncResult) -> None:
        """Show a visible warning when the widget is serving stale cached data."""

        if not result.requires_attention:
            self._sync_health_label.hide()
            self._sync_health_label.clear()
            self._last_sync_warning_key = None
            return

        warning_message = result.sync_warning.strip()
        if result.is_from_cache and result.last_success_at is not None:
            age_message = self._format_last_sync_age(result.last_success_at)
            if age_message:
                warning_message = f"{warning_message} {age_message}".strip()

        self._sync_health_label.setText(warning_message)
        self._sync_health_label.show()

        warning_key = f"{result.status_message}|{warning_message}"
        if warning_key != self._last_sync_warning_key:
            self._send_sync_health_notification(result.status_message, warning_message)
            self._last_sync_warning_key = warning_key

    def _format_last_sync_age(self, last_success_at: datetime | None) -> str:
        """Describe how old the last successful Google sync is."""

        if last_success_at is None:
            return ""

        elapsed = datetime.now(LOCAL_TIMEZONE) - last_success_at
        elapsed_minutes = max(0, int(elapsed.total_seconds() // 60))
        threshold_minutes = max(
            CACHE_WARNING_FLOOR_MINUTES,
            int(self._settings.get("refresh_interval", REFRESH_INTERVAL_MINUTES)) * 2,
        )
        if elapsed_minutes < threshold_minutes:
            return ""

        if elapsed_minutes < 60:
            return f"Última sincronización real con Google hace {elapsed_minutes} minutos."

        hours, minutes = divmod(elapsed_minutes, 60)
        if minutes == 0:
            return f"Última sincronización real con Google hace {hours} horas."
        return f"Última sincronización real con Google hace {hours} h {minutes} min."

    def _send_sync_health_notification(self, title: str, message: str) -> None:
        """Send a desktop notification for persistent sync-health warnings."""

        if not message:
            return

        try:
            subprocess.run(
                [
                    "notify-send",
                    "--app-name=Zyna Calendar",
                    title,
                    message,
                ],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            logger.warning("notify-send is not available in this environment")
        except Exception:
            logger.exception("Failed to send sync health notification")

    def _build_menu(self) -> QMenu:
        """Create the menu for sync, settings, and lifecycle actions."""

        menu = QMenu(self)

        sync_action = QAction("Sync Manual", self)
        sync_action.triggered.connect(self.refresh_events)
        menu.addAction(sync_action)

        refresh_token_action = QAction("Refresh Token", self)
        refresh_token_action.triggered.connect(self._refresh_token)
        menu.addAction(refresh_token_action)

        config_action = QAction("Configuración", self)
        config_action.triggered.connect(self._open_config_dialog)
        menu.addAction(config_action)

        update_action = QAction("Buscar actualizaciones", self)
        update_action.triggered.connect(self._open_update_dialog)
        menu.addAction(update_action)

        info_action = QAction("Info", self)
        info_action.triggered.connect(self._open_info_dialog)
        menu.addAction(info_action)

        restart_action = QAction("Reiniciar Applet", self)
        restart_action.triggered.connect(self._restart_applet)
        menu.addAction(restart_action)

        minimize_action = QAction("Minimizar", self)
        minimize_action.triggered.connect(self._minimize_to_icon)
        menu.addAction(minimize_action)

        exit_action = QAction("Salir", self)
        exit_action.triggered.connect(self._quit_app)
        menu.addAction(exit_action)

        return menu

    def _refresh_token(self) -> None:
        """Renew a revoked token using loopback auth with manual fallback."""

        self._status_label.setText("Actualizando token...")

        try:
            run_loopback_auth()
        except MissingCredentialsError as error:
            self._status_label.setText(f"Falta credentials.json: {error}")
            return
        except Exception:
            logger.exception("Flujo loopback no disponible; se usará el modo manual")
            if not self._refresh_token_manual():
                return

        self._status_label.setText("Token renovado. Sincronizando...")
        self._calendar_client.invalidate()
        self.refresh_events()

    def _refresh_token_manual(self) -> bool:
        """Run the copy/paste dialog flow. Returns True when authorized."""

        try:
            _, auth_url = init_manual_auth()
        except MissingCredentialsError as error:
            self._status_label.setText(f"Falta credentials.json: {error}")
            return False
        except Exception:
            logger.exception("No se pudo iniciar el flujo de autorización")
            self._status_label.setText("No se pudo iniciar la autorización.")
            return False

        dialog = AuthDialog(auth_url, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return True
        self._status_label.setText("Autorización cancelada.")
        return False

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
            self._theme = get_theme_palette(self._settings)
            self.setFixedWidth(int(self._settings["window_width"]))
            self.setStyleSheet(self._build_stylesheet())
            self._configure_refresh_timer()
            self.refresh_events()

    def _open_info_dialog(self) -> None:
        """Display an informational dialog about the widget."""

        dialog = InfoDialog(self)
        dialog.exec()

    def _open_update_dialog(self) -> None:
        """Open the update dialog for a manual release check."""

        dialog = UpdateDialog(self)
        dialog.exec()

    def _restart_applet(self) -> None:
        """Restart the Python process cleanly."""

        self._persist_position()
        python_executable = sys.executable
        os.execl(python_executable, python_executable, *sys.argv)

    def _quit_app(self) -> None:
        """Persist state, stop timers, and force a total application exit."""

        self._persist_position()
        if self._mini_icon is not None:
            self._mini_icon.close()
            self._mini_icon = None
        if self._refresh_timer is not None:
            self._refresh_timer.stop()
        if self._notification_timer is not None:
            self._notification_timer.stop()
        if self._sync_thread is not None and self._sync_thread.isRunning():
            self._sync_thread.wait(500)
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def _minimize_to_icon(self) -> None:
        """Hide the widget and show a small draggable icon."""

        self._minimized_geometry = QRect(self.pos(), self.size())
        self.hide()

        if self._mini_icon is None:
            self._mini_icon = MiniIconWidget(self._theme)
            self._mini_icon.restore_requested.connect(self._restore_from_icon)

        self._mini_icon.move(self._minimized_geometry.topLeft())
        self._mini_icon.show()
        self._mini_icon.raise_()

    def _restore_from_icon(self) -> None:
        """Restore the full widget and hide the minimized icon."""

        if self._mini_icon is not None:
            self._mini_icon.hide()
        if self._minimized_geometry is not None:
            self.setGeometry(self._minimized_geometry)
        self.show()
        self.raise_()
        self.activateWindow()
        self.refresh_events()


class MiniIconWidget(QWidget):
    """Small draggable icon shown while the calendar widget is minimized."""

    restore_requested = pyqtSignal()

    def __init__(self, theme: dict[str, str], parent: QWidget | None = None) -> None:
        """Build a compact draggable icon window."""

        super().__init__(parent)
        self._theme = dict(theme)
        self._drag_offset: QPoint | None = None
        self.setObjectName("mini-icon")
        self.setFixedSize(52, 52)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Zyna Calendar - doble clic para restaurar")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        icon_path = get_app_icon_path()
        self._icon_pixmap = QPixmap(str(icon_path)) if icon_path.exists() else QPixmap()

    def paintEvent(self, event: QPaintEvent | None) -> None:  # noqa: N802
        """Draw a rounded tile with the app icon."""

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bg_hex = self._theme.get("bg", "#1E232D")
        accent_hex = self._theme.get("accent", "#3572B6")
        background = QColor(bg_hex)
        background.setAlpha(230)

        painter.setPen(QPen(QColor(accent_hex), 2))
        painter.setBrush(background)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 14, 14)

        if not self._icon_pixmap.isNull():
            icon_size = 32
            target_rect = QRect(0, 0, icon_size, icon_size)
            target_rect.moveCenter(self.rect().center())
            painter.drawPixmap(target_rect, self._icon_pixmap)
        if event is not None:
            super().paintEvent(event)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        """Capture the drag offset for the icon."""

        if event is not None and event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        """Move the icon while dragging."""

        if (
            self._drag_offset is not None
            and event is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            self.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        """Reset the drag state."""

        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        """Restore the full widget on double click."""

        if event is not None and event.button() == Qt.MouseButton.LeftButton:
            self.restore_requested.emit()
        super().mouseDoubleClickEvent(event)


class HamburgerButton(QWidget):
    """Hamburger icon button rendered with QPainter."""

    clicked = pyqtSignal()

    def __init__(
        self,
        theme: dict[str, str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the button surface with the active theme colors."""

        super().__init__(parent)
        self._line_color = dict(theme or {}).get("text", "#FFFFFF")
        self.setFixedSize(26, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, event: QPaintEvent | None) -> None:  # noqa: N802
        """Draw the hamburger icon."""

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(self._line_color))
        pen.setWidth(2)
        painter.setPen(pen)

        y_positions = (6, 11, 16)
        for y in y_positions:
            painter.drawLine(4, y, self.width() - 4, y)
        if event is not None:
            super().paintEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        """Emit the click signal on left-button release."""

        if event is not None and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        if event is not None:
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
            "Widget de escritorio ligero para Google Calendar.\nIntegrado con Zorin OS Lite (XFCE)."
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
