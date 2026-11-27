import sys
import uuid
import math
import html
import subprocess
import shutil
import traceback

from datetime import datetime
from string import Template

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QRectF, QSettings
from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient, QFont, QFontMetrics
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QFrame,
    QScrollArea,
    QMenu
)

import psutil

from modules.config import SYSTEM_PROMPT, CREATE_NO_WINDOW
from modules.database import (
    DatabaseWorker,
    db_startup,
    db_create_chat,
    db_save_message,
    db_load_messages,
    db_delete_chat,
    make_chat_title
)

from modules.ai_client import send_message

try:
    from modules.ai_client import warm_up
except ImportError:
    # Старый ai_client.py без прогрева модели.
    def warm_up():
        return True

from modules.speech_recognition import SpeechWorker
from modules.speech_synthesis import speak
from modules.command_executor import execute_command, confirm_command
from modules.media_control import execute_media_command
from modules.text_processing import (
    prepare_ai_response,
    prepare_voice_response
)


DEFAULT_CHAT_TITLE = "Новый чат"

COLUMN_MAX_WIDTH = 780

# Быстрые команды на пустом экране: (подпись, команда)
SUGGESTIONS = [
    ("🧮  Калькулятор", "открой калькулятор"),
    ("💻  О системе", "информация о системе"),
    ("📊  Процессы", "список процессов"),
    ("🌐  Браузер", "открой браузер"),
]


# =====================================================================
# ФОНОВЫЕ ПОТОКИ
# =====================================================================

class AIWorker(QThread):
    finished_response = Signal(dict)

    def __init__(self, messages):
        super().__init__()
        self.messages = messages

    def run(self):
        try:
            result = send_message(
                self.messages,
                SYSTEM_PROMPT
            )
            self.finished_response.emit(result)

        except Exception as error:
            self.finished_response.emit({
                "success": False,
                "response": str(error)
            })


class WarmupWorker(QThread):
    """Загружает модель в память при запуске, чтобы первый ответ был быстрым."""

    finished_warmup = Signal(bool)

    def run(self):
        try:
            self.finished_warmup.emit(bool(warm_up()))
        except Exception:
            self.finished_warmup.emit(False)


class SpeakWorker(QThread):
    """Озвучка в отдельном потоке: окно больше не зависает во время речи."""

    finished_speaking = Signal(dict)

    def __init__(self, text):
        super().__init__()
        self.text = text

    def run(self):
        try:
            result = speak(self.text)
        except Exception as error:
            result = {"success": False, "error": str(error)}

        if not isinstance(result, dict):
            result = {"success": True}

        self.finished_speaking.emit(result)


class StatsWorker(QThread):
    """Нагрузка CPU/RAM/GPU собирается вне интерфейсного потока."""

    updated = Signal(float, float, float)

    def __init__(self):
        super().__init__()
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        psutil.cpu_percent(interval=None)

        has_nvidia = shutil.which("nvidia-smi") is not None

        while self._running:
            try:
                cpu = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory().percent
                gpu = -1.0

                if has_nvidia:
                    result = subprocess.run(
                        [
                            "nvidia-smi",
                            "--query-gpu=utilization.gpu",
                            "--format=csv,noheader,nounits"
                        ],
                        capture_output=True,
                        text=True,
                        timeout=2,
                        creationflags=CREATE_NO_WINDOW
                    )

                    if result.returncode == 0:
                        gpu = float(
                            result.stdout.strip().splitlines()[0]
                        )

                self.updated.emit(cpu, ram, gpu)

            except Exception:
                pass

            for _ in range(20):
                if not self._running:
                    return
                self.msleep(100)


# =====================================================================
# ТЕМЫ
# =====================================================================

THEMES = {
    # Тёмная: графитовая, спокойная
    "dark": {
        "bg": "#212121",
        "sidebar": "#171717",
        "text": "#ececec",
        "muted": "#9b9b9b",
        "border": "#2f2f2f",
        "hover": "#262626",
        "selected": "#2f2f2f",
        "bubble": "#2f2f2f",
        "input_bg": "#2a2a2a",
        "input_border": "#3a3a3a",
        "send_bg": "#ececec",
        "send_fg": "#171717",
        "send_hover": "#ffffff",
        "sel_bg": "#3b4a78",
        "ok": "#4cc9a0",
        "err": "#ff7b7b",
        "busy": "#f0b95a",
        "scroll": "#3a3a3a",
        "scroll_hover": "#4a4a4a",
        "menu_bg": "#2a2a2a",
        "bot_bg": "#2a2a2a",
        "bot_border": "#383838",
        "user_a": "#5b7cff",
        "user_b": "#8b5cf6",
        "user_text": "#ffffff",
        "bg_top": "#1a1b24"
    },

    # Светлая: тёплая бумажная
    "light": {
        "bg": "#faf9f5",
        "sidebar": "#f0eee6",
        "text": "#262522",
        "muted": "#7b786f",
        "border": "#e3e0d5",
        "hover": "#e8e5da",
        "selected": "#e0ddd0",
        "bubble": "#ece8dc",
        "input_bg": "#ffffff",
        "input_border": "#dad6c9",
        "send_bg": "#c96442",
        "send_fg": "#ffffff",
        "send_hover": "#b9573a",
        "sel_bg": "#f1cdbd",
        "ok": "#1f9d72",
        "err": "#d64545",
        "busy": "#b7791f",
        "scroll": "#d6d2c4",
        "scroll_hover": "#c4bfae",
        "menu_bg": "#ffffff",
        "bot_bg": "#ffffff",
        "bot_border": "#e3e0d5",
        "user_a": "#d4714f",
        "user_b": "#e8985f",
        "user_text": "#ffffff",
        "bg_top": "#f4f1e7"
    }
}


STYLE_TEMPLATE = Template("""
QWidget {
    background: transparent;
    color: $text;
}

QWidget#Root {
    background: $bg;
}

QToolTip, QMenu {
    background: $menu_bg;
    border: 1px solid $border;
    color: $text;
    padding: 4px;
}

QMenu::item {
    padding: 8px 18px;
    border-radius: 6px;
}

QMenu::item:selected {
    background: $hover;
}

/* ---------- Боковая панель ---------- */

QFrame#Sidebar {
    background: $sidebar;
    border-right: 1px solid $border;
}

QLabel#Brand {
    font-size: 15px;
    font-weight: 600;
    letter-spacing: 2px;
}

QLabel#BrandSub {
    color: $muted;
    font-size: 11px;
}

QPushButton#NewChat {
    background: transparent;
    border: 1px solid $border;
    border-radius: 10px;
    padding: 10px 12px;
    text-align: left;
    color: $text;
}

QPushButton#NewChat:hover {
    background: $hover;
}

QLabel#SectionLabel {
    color: $muted;
    font-size: 12px;
    font-weight: 600;
    padding-left: 4px;
}

QListWidget#ChatList {
    border: none;
    outline: 0;
    background: transparent;
}

QListWidget#ChatList::item {
    padding: 9px 10px;
    border-radius: 8px;
    color: $text;
    margin: 1px 0;
}

QListWidget#ChatList::item:hover {
    background: $hover;
}

QListWidget#ChatList::item:selected {
    background: $selected;
    color: $text;
}

QLabel#Footer {
    color: $muted;
    font-size: 11px;
    padding-left: 4px;
}

QPushButton#ThemeBtn {
    background: transparent;
    border: 1px solid $border;
    border-radius: 18px;
    min-width: 36px;
    max-width: 36px;
    min-height: 36px;
    max-height: 36px;
    font-size: 16px;
}

QPushButton#ThemeBtn:hover {
    background: $hover;
}

/* ---------- Основная область ---------- */

QFrame#Main {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 $bg_top, stop: 0.45 $bg, stop: 1 $bg
    );
}

QLabel#ChatTitle {
    font-size: 15px;
    font-weight: 600;
}

QLabel#StatusText {
    color: $ok;
    font-size: 12px;
}

QLabel#StatusText[state="error"] {
    color: $err;
}

QLabel#StatusText[state="busy"] {
    color: $busy;
}

QLabel#GreetTitle {
    font-size: 30px;
    font-weight: 600;
}

QLabel#GreetSub {
    color: $muted;
    font-size: 16px;
}

/* ---------- Сообщения ---------- */

QFrame#UserBubble {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 $user_a, stop: 1 $user_b
    );
    border-radius: 18px;
    border-bottom-right-radius: 6px;
}

QFrame#BotBubble {
    background: $bot_bg;
    border: 1px solid $bot_border;
    border-radius: 18px;
    border-bottom-left-radius: 6px;
}

QLabel#UserText {
    background: transparent;
    color: $user_text;
}

QLabel#BotText {
    background: transparent;
    color: $text;
}

QLabel#Avatar {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 $user_a, stop: 1 $user_b
    );
    color: #ffffff;
    border-radius: 15px;
    font-size: 14px;
    font-weight: 700;
}

QPushButton#Chip {
    background: $input_bg;
    border: 1px solid $border;
    border-radius: 17px;
    padding: 8px 14px;
    color: $text;
    font-size: 13px;
}

QPushButton#Chip:hover {
    background: $hover;
    border-color: $muted;
}

QLabel#TypingText {
    color: $muted;
}

/* ---------- Ввод ---------- */

QFrame#InputBar {
    background: $input_bg;
    border: 1px solid $input_border;
    border-radius: 26px;
}

QLineEdit#Input {
    background: transparent;
    border: none;
    padding: 10px 6px;
    font-size: 15px;
    color: $text;
    selection-background-color: $sel_bg;
}

QPushButton#Send {
    background: $send_bg;
    color: $send_fg;
    border: none;
    border-radius: 18px;
    min-width: 36px;
    max-width: 36px;
    min-height: 36px;
    max-height: 36px;
    font-size: 18px;
    font-weight: 700;
}

QPushButton#Send:hover {
    background: $send_hover;
}

QPushButton#Send:disabled {
    background: $hover;
    color: $muted;
}

QPushButton#VoiceBtn {
    background: transparent;
    border: 1px solid $border;
    border-radius: 18px;
    min-width: 36px;
    max-width: 36px;
    min-height: 36px;
    max-height: 36px;
    font-size: 16px;
}

QPushButton#VoiceBtn:hover {
    border-color: $muted;
}

QPushButton#VoiceBtn[on="true"] {
    border-color: $ok;
}

/* ---------- Полосы прокрутки ---------- */

QScrollArea {
    border: none;
    background: transparent;
}

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 4px 2px;
}

QScrollBar::handle:vertical {
    background: $scroll;
    border-radius: 3px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: $scroll_hover;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
}
""")


def build_style(theme_name):
    tokens = THEMES.get(theme_name, THEMES["dark"])
    return STYLE_TEMPLATE.safe_substitute(tokens)


# =====================================================================
# ВИДЖЕТЫ
# =====================================================================

class OrbWidget(QWidget):
    """Небольшой индикатор состояния: ожидание, обработка, речь."""

    COLORS = {
        "idle": "#7c9cff",
        "thinking": "#f5b84b",
        "speaking": "#3fd6b0"
    }

    SPEEDS = {
        "idle": 0.07,
        "thinking": 0.16,
        "speaking": 0.30
    }

    def __init__(self, size=34):
        super().__init__()

        self.state = "idle"
        self.phase = 0.0

        self.setFixedSize(size, size)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(40)

    def set_state(self, state):
        if state in self.COLORS:
            self.state = state
            self.update()

    def tick(self):
        self.phase = (
            self.phase + self.SPEEDS[self.state]
        ) % (2 * math.pi)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        color = QColor(self.COLORS[self.state])

        cx = self.width() / 2
        cy = self.height() / 2

        pulse = (math.sin(self.phase) + 1) / 2

        glow = QRadialGradient(cx, cy, self.width() / 2)
        glow_color = QColor(color)
        glow_color.setAlpha(int(50 + pulse * 70))
        glow.setColorAt(0, glow_color)
        glow.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))

        painter.setPen(Qt.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(
            QRectF(0, 0, self.width(), self.height())
        )

        ring_radius = self.width() * 0.34
        ring_color = QColor(color)
        ring_color.setAlpha(150)

        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(ring_color, 1.6))
        painter.drawEllipse(
            QRectF(
                cx - ring_radius,
                cy - ring_radius,
                ring_radius * 2,
                ring_radius * 2
            )
        )

        if self.state == "thinking":
            arc_pen = QPen(color, 2.4)
            arc_pen.setCapStyle(Qt.RoundCap)
            painter.setPen(arc_pen)

            start = int(-self.phase * 180 / math.pi * 16)

            painter.drawArc(
                QRectF(
                    cx - ring_radius,
                    cy - ring_radius,
                    ring_radius * 2,
                    ring_radius * 2
                ),
                start,
                100 * 16
            )

        core_radius = self.width() * 0.13
        core_radius += pulse * (
            self.width() * 0.05 if self.state == "speaking"
            else self.width() * 0.02
        )

        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(
            QRectF(
                cx - core_radius,
                cy - core_radius,
                core_radius * 2,
                core_radius * 2
            )
        )

        painter.end()


def message_html(text):
    safe = html.escape(str(text)).replace("\n", "<br>")

    return (
        '<p style="line-height:150%; margin:0;">'
        + safe
        + "</p>"
    )


def make_message_font():
    font = QFont()
    font.setPixelSize(15)
    return font


def make_avatar():
    avatar = QLabel("J")
    avatar.setObjectName("Avatar")
    avatar.setAlignment(Qt.AlignCenter)
    avatar.setFixedSize(30, 30)
    return avatar


class MessageRow(QWidget):
    """
    Сообщение пользователя - цветная плашка справа.
    Ответ JARVIS - плашка с рамкой и аватаром слева.
    """

    def __init__(self, role, text):
        super().__init__()

        self.role = role
        self.plain = str(text)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.label = QLabel()
        self.label.setFont(make_message_font())
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.RichText)
        self.label.setText(message_html(self.plain))
        self.label.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )

        self.bubble = QFrame()

        inner = QVBoxLayout(self.bubble)
        inner.setContentsMargins(16, 10, 16, 11)
        inner.addWidget(self.label)

        if role == "user":
            self.label.setObjectName("UserText")
            self.bubble.setObjectName("UserBubble")

            layout.addStretch(1)
            layout.addWidget(self.bubble)

        else:
            self.label.setObjectName("BotText")
            self.bubble.setObjectName("BotBubble")

            layout.addWidget(make_avatar(), 0, Qt.AlignTop)
            layout.addWidget(self.bubble)
            layout.addStretch(1)

    def apply_width(self, column_width):
        """Ширина плашки подгоняется под текст."""

        avatar_space = 0 if self.role == "user" else 40

        inner_max = max(
            120,
            int((column_width - avatar_space) * 0.88) - 32
        )

        metrics = QFontMetrics(self.label.font())

        longest = max(
            (
                metrics.horizontalAdvance(line)
                for line in self.plain.split("\n")
            ),
            default=0
        )

        self.label.setFixedWidth(min(longest + 14, inner_max))


class TypingRow(QWidget):
    """Индикатор «Думаю…» в плашке JARVIS."""

    def __init__(self):
        super().__init__()

        self.step = 0

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.bubble = QFrame()
        self.bubble.setObjectName("BotBubble")

        inner = QVBoxLayout(self.bubble)
        inner.setContentsMargins(16, 10, 16, 11)

        self.label = QLabel("Думаю")
        self.label.setObjectName("TypingText")
        self.label.setFont(make_message_font())

        # Фиксированная ширина, чтобы плашка не дёргалась при анимации.
        metrics = QFontMetrics(self.label.font())
        self.label.setFixedWidth(metrics.horizontalAdvance("Думаю...") + 6)

        inner.addWidget(self.label)

        layout.addWidget(make_avatar(), 0, Qt.AlignTop)
        layout.addWidget(self.bubble)
        layout.addStretch(1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(400)

    def tick(self):
        self.step = (self.step + 1) % 4
        self.label.setText("Думаю" + "." * self.step)

    def apply_width(self, column_width):
        pass


def centered_column(widget, max_width=COLUMN_MAX_WIDTH):
    """Оборачивает виджет в центрированную колонку ограниченной ширины."""

    widget.setMaximumWidth(max_width)

    wrapper = QWidget()

    layout = QHBoxLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)

    layout.addStretch(1)
    layout.addWidget(widget, 100)
    layout.addStretch(1)

    return wrapper


def greeting_text():
    hour = datetime.now().hour

    if hour < 6:
        return "Доброй ночи"

    if hour < 12:
        return "Доброе утро"

    if hour < 18:
        return "Добрый день"

    return "Добрый вечер"


class ChatView(QScrollArea):

    chip_clicked = Signal(str)

    def __init__(self):
        super().__init__()

        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.rows = []
        self.typing_row = None

        self.container = QWidget()

        outer = QHBoxLayout(self.container)
        outer.setContentsMargins(24, 24, 24, 24)

        self.column = QWidget()
        self.column.setMaximumWidth(COLUMN_MAX_WIDTH)

        outer.addStretch(1)
        outer.addWidget(self.column, 100)
        outer.addStretch(1)

        self.content = QVBoxLayout(self.column)
        self.content.setContentsMargins(0, 0, 0, 0)
        self.content.setSpacing(22)

        # Приветствие для пустого чата

        self.hint = QWidget()

        hint_layout = QVBoxLayout(self.hint)
        hint_layout.setContentsMargins(0, 110, 0, 0)
        hint_layout.setSpacing(8)

        self.greet_title = QLabel(greeting_text())
        self.greet_title.setObjectName("GreetTitle")
        self.greet_title.setAlignment(Qt.AlignCenter)

        greet_sub = QLabel("Чем могу помочь?")
        greet_sub.setObjectName("GreetSub")
        greet_sub.setAlignment(Qt.AlignCenter)

        hint_layout.addWidget(self.greet_title)
        hint_layout.addWidget(greet_sub)
        hint_layout.addSpacing(18)

        chips_row = QHBoxLayout()
        chips_row.setSpacing(8)
        chips_row.addStretch(1)

        for caption, command in SUGGESTIONS:
            chip = QPushButton(caption)
            chip.setObjectName("Chip")
            chip.setCursor(Qt.PointingHandCursor)
            chip.clicked.connect(
                lambda checked=False, c=command: self.chip_clicked.emit(c)
            )
            chips_row.addWidget(chip)

        chips_row.addStretch(1)

        hint_layout.addLayout(chips_row)

        self.content.addWidget(self.hint)
        self.content.addStretch(1)

        self.setWidget(self.container)

    def column_width(self):
        return max(
            300,
            min(COLUMN_MAX_WIDTH, self.viewport().width() - 48)
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)

        width = self.column_width()

        for row in self.rows:
            row.apply_width(width)

    def insert_row(self, row):
        # Последний элемент layout - растяжка, вставляем перед ней.
        self.content.insertWidget(self.content.count() - 1, row)

    def add_message(self, role, text):
        row = MessageRow(role, text)
        row.apply_width(self.column_width())

        self.hint.hide()
        self.insert_row(row)

        self.rows.append(row)

        self.scroll_to_bottom()

    def show_typing(self, visible):
        if visible and self.typing_row is None:
            self.typing_row = TypingRow()

            self.hint.hide()
            self.insert_row(self.typing_row)

            self.scroll_to_bottom()

        elif not visible and self.typing_row is not None:
            self.content.removeWidget(self.typing_row)
            self.typing_row.deleteLater()
            self.typing_row = None

            if not self.rows:
                self.show_hint()

    def show_hint(self):
        self.greet_title.setText(greeting_text())
        self.hint.show()

    def clear(self):
        self.show_typing(False)

        for row in self.rows:
            self.content.removeWidget(row)
            row.deleteLater()

        self.rows = []

        self.show_hint()

    def scroll_to_bottom(self):
        def go():
            bar = self.verticalScrollBar()
            bar.setValue(bar.maximum())

        # Раскладка досчитывается не мгновенно, поэтому два прохода.
        QTimer.singleShot(0, go)
        QTimer.singleShot(60, go)


# =====================================================================
# ГЛАВНОЕ ОКНО
# =====================================================================

class JarvisWindow(QWidget):

    def __init__(self):
        super().__init__()

        self.setObjectName("Root")
        self.setWindowTitle("J.A.R.V.I.S.")
        self.resize(1240, 820)
        self.setMinimumSize(900, 600)

        self.db = DatabaseWorker()

        self.speech = None
        self.ai_worker = None
        self.warmup_worker = None
        self.speak_worker = None

        self.chat_id = None
        self.history = []
        self.facts = []

        self.voice_enabled = True
        self.waiting_response = False
        self.pending_command = None

        self.speaking = False
        self.speak_queue = []

        self.status = ""

        self.settings = QSettings("JarvisV2", "Jarvis")
        self.theme = self.load_theme()

        self.init_ui()

        self.apply_theme(self.theme)

        self.db.failed.connect(self.database_error)

        self.stats_worker = StatsWorker()
        self.stats_worker.updated.connect(self.update_stats)
        self.stats_worker.start()

        self.db.call(
            db_startup,
            self.startup_finished
        )

    # ------------------------------------------------------------
    # ТЕМА
    # ------------------------------------------------------------

    def load_theme(self):
        try:
            value = self.settings.value("theme", "dark")
            return value if value in THEMES else "dark"
        except Exception:
            return "dark"

    def apply_theme(self, theme):

        self.theme = theme

        self.setStyleSheet(build_style(theme))

        self.theme_button.setText("☀️" if theme == "dark" else "🌙")

        self.theme_button.setToolTip(
            "Светлая тема" if theme == "dark" else "Тёмная тема"
        )

        try:
            self.settings.setValue("theme", theme)
        except Exception:
            pass

    def toggle_theme(self):
        self.apply_theme(
            "light" if self.theme == "dark" else "dark"
        )

    # ------------------------------------------------------------
    # ИНТЕРФЕЙС
    # ------------------------------------------------------------

    def init_ui(self):

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self.build_sidebar())
        root.addWidget(self.build_main(), 1)

    def build_sidebar(self):

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(260)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(8)

        brand = QLabel("JARVIS")
        brand.setObjectName("Brand")

        brand_sub = QLabel("Личный ассистент")
        brand_sub.setObjectName("BrandSub")

        layout.addWidget(brand)
        layout.addWidget(brand_sub)
        layout.addSpacing(10)

        new_chat_button = QPushButton("+   Новый чат")
        new_chat_button.setObjectName("NewChat")
        new_chat_button.setCursor(Qt.PointingHandCursor)
        new_chat_button.clicked.connect(self.new_chat)

        layout.addWidget(new_chat_button)
        layout.addSpacing(10)

        chats_label = QLabel("Чаты")
        chats_label.setObjectName("SectionLabel")

        layout.addWidget(chats_label)

        self.chat_list = QListWidget()
        self.chat_list.setObjectName("ChatList")
        self.chat_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.chat_list.customContextMenuRequested.connect(
            self.chat_context_menu
        )
        self.chat_list.itemClicked.connect(self.select_chat)

        layout.addWidget(self.chat_list, 1)

        self.footer = QLabel("CPU —  ·  RAM —  ·  GPU —")
        self.footer.setObjectName("Footer")

        layout.addWidget(self.footer)

        return sidebar

    def build_main(self):

        main = QFrame()
        main.setObjectName("Main")

        layout = QVBoxLayout(main)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Шапка

        header = QWidget()
        header.setFixedHeight(60)

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 0, 24, 0)
        header_layout.setSpacing(12)

        self.orb = OrbWidget(34)

        self.chat_title = QLabel(DEFAULT_CHAT_TITLE)
        self.chat_title.setObjectName("ChatTitle")

        self.status_text = QLabel("● Запуск")
        self.status_text.setObjectName("StatusText")
        self.status_text.setProperty("state", "busy")

        header_layout.addWidget(self.orb)
        header_layout.addWidget(self.chat_title)
        header_layout.addStretch(1)
        self.theme_button = QPushButton("☀️")
        self.theme_button.setObjectName("ThemeBtn")
        self.theme_button.setCursor(Qt.PointingHandCursor)
        self.theme_button.clicked.connect(self.toggle_theme)

        header_layout.addWidget(self.status_text)
        header_layout.addWidget(self.theme_button)

        layout.addWidget(header)

        # Сообщения

        self.chat_view = ChatView()
        self.chat_view.chip_clicked.connect(self.process_chip)

        layout.addWidget(self.chat_view, 1)

        # Ввод

        input_bar = QFrame()
        input_bar.setObjectName("InputBar")

        input_layout = QHBoxLayout(input_bar)
        input_layout.setContentsMargins(20, 7, 8, 7)
        input_layout.setSpacing(8)

        self.input = QLineEdit()
        self.input.setObjectName("Input")
        self.input.setPlaceholderText("Напишите сообщение…")
        self.input.returnPressed.connect(self.send_text)

        self.voice_button = QPushButton("🎤")
        self.voice_button.setObjectName("VoiceBtn")
        self.voice_button.setCursor(Qt.PointingHandCursor)
        self.voice_button.setProperty("on", True)
        self.voice_button.clicked.connect(self.toggle_voice)

        self.send_button = QPushButton("↑")
        self.send_button.setObjectName("Send")
        self.send_button.setCursor(Qt.PointingHandCursor)
        self.send_button.clicked.connect(self.send_text)

        input_layout.addWidget(self.input, 1)
        input_layout.addWidget(self.voice_button)
        input_layout.addWidget(self.send_button)

        input_wrap = centered_column(input_bar)
        input_wrap.layout().setContentsMargins(24, 8, 24, 22)

        layout.addWidget(input_wrap)

        return main

    # ------------------------------------------------------------
    # ЧАТЫ
    # ------------------------------------------------------------

    def find_item(self, chat_id):

        for index in range(self.chat_list.count()):
            item = self.chat_list.item(index)

            if item.data(Qt.UserRole) == chat_id:
                return item

        return None

    def chat_context_menu(self, position):

        item = self.chat_list.itemAt(position)

        if item is None:
            return

        menu = QMenu(self)
        delete_action = menu.addAction("Удалить чат")

        chosen = menu.exec(
            self.chat_list.viewport().mapToGlobal(position)
        )

        if chosen == delete_action:
            self.delete_chat(item)

    def delete_chat(self, item):

        chat_id = item.data(Qt.UserRole)

        if not chat_id:
            return

        self.db.call(
            lambda chat, mem: db_delete_chat(chat, chat_id)
        )

        self.chat_list.takeItem(self.chat_list.row(item))

        if chat_id != self.chat_id:
            return

        if self.chat_list.count():
            first = self.chat_list.item(0)
            self.chat_list.setCurrentItem(first)
            self.select_chat(first)
        else:
            self.new_chat()

    # ------------------------------------------------------------
    # БАЗА ДАННЫХ
    # ------------------------------------------------------------

    def startup_finished(self, data):

        self.facts = data.get("facts", [])

        self.chat_list.clear()

        for chat_data in data.get("chats", []):

            item = QListWidgetItem(chat_data["title"])
            item.setData(Qt.UserRole, chat_data["id"])

            self.chat_list.addItem(item)

        if data.get("last_id"):

            self.chat_id = data["last_id"]

            self.history = [
                {
                    "role": role,
                    "content": content
                }
                for role, content in data.get("messages", [])
            ]

            current = self.find_item(self.chat_id)

            if current:
                self.chat_list.setCurrentItem(current)
                self.chat_title.setText(current.text())

            self.render_history()

        else:
            self.new_chat()

        self.start_speech()
        self.start_warmup()

    def start_warmup(self):

        self.set_status("Загрузка модели…", "busy")

        self.warmup_worker = WarmupWorker()
        self.warmup_worker.finished_warmup.connect(
            self.warmup_finished
        )
        self.warmup_worker.start()

    def warmup_finished(self, ok):

        if ok:
            self.set_status("Система готова")
        else:
            self.set_status("Ошибка: Ollama не запущена")

    def save_message(self, role, content):

        if not self.chat_id:
            return

        chat_id = self.chat_id

        self.db.call(
            lambda chat, mem: db_save_message(
                chat,
                chat_id,
                role,
                content
            )
        )

        # Название чата берём из первого сообщения пользователя.
        if role == "user":
            self.rename_chat_from_first_message(chat_id, content)

    def rename_chat_from_first_message(self, chat_id, text):

        item = self.find_item(chat_id)

        if item is None or item.text() != DEFAULT_CHAT_TITLE:
            return

        title = make_chat_title(text)

        item.setText(title)

        if chat_id == self.chat_id:
            self.chat_title.setText(title)

        def update(chat, mem):
            with chat:
                chat.execute(
                    "UPDATE chats SET title = ? WHERE id = ?",
                    (title, chat_id)
                )

        self.db.call(update)

    def new_chat(self):

        self.chat_id = str(uuid.uuid4())

        self.history = []
        self.chat_view.clear()

        item = QListWidgetItem(DEFAULT_CHAT_TITLE)
        item.setData(Qt.UserRole, self.chat_id)

        self.chat_list.insertItem(0, item)
        self.chat_list.setCurrentItem(item)

        self.chat_title.setText(DEFAULT_CHAT_TITLE)

        chat_id = self.chat_id

        self.db.call(
            lambda chat, mem: db_create_chat(
                chat,
                chat_id,
                DEFAULT_CHAT_TITLE
            )
        )

        self.set_status("Создан новый чат")

        self.input.setFocus()

    def select_chat(self, item):

        chat_id = item.data(Qt.UserRole)

        if not chat_id:
            return

        if self.waiting_response:
            # Не переключаем чат, пока идёт ответ: он попал бы не туда.
            current = self.find_item(self.chat_id)

            if current:
                self.chat_list.setCurrentItem(current)

            self.set_status("Дождитесь ответа", "busy")
            return

        self.chat_title.setText(item.text())

        self.db.call(
            lambda chat, mem: db_load_messages(
                chat,
                chat_id
            ),
            lambda messages: self.chat_loaded(
                chat_id,
                messages
            )
        )

    def chat_loaded(self, chat_id, messages):

        self.chat_id = chat_id

        self.history = [
            {
                "role": role,
                "content": content
            }
            for role, content in messages
        ]

        self.render_history()

        self.set_status("История загружена")

    # ------------------------------------------------------------
    # ЧАТ
    # ------------------------------------------------------------

    def render_history(self):

        self.chat_view.clear()

        for message in self.history:

            if message["role"] == "user":
                self.add_message("ВЫ", message["content"])

            elif message["role"] == "assistant":
                self.add_message(
                    "J.A.R.V.I.S.",
                    message["content"]
                )

    def add_message(self, author, text):

        role = "user" if author == "ВЫ" else "assistant"

        self.chat_view.add_message(role, text)

    def process_chip(self, command):

        if self.waiting_response:
            return

        self.process_input(command)

    def send_text(self):

        text = self.input.text().strip()

        if not text:
            return

        self.input.clear()

        self.process_input(text)

    def process_input(self, text):

        if self.waiting_response:
            return

        self.add_message("ВЫ", text)

        self.history.append({
            "role": "user",
            "content": text
        })

        self.save_message("user", text)

        # CONFIRMATION

        if self.pending_command:

            answer = text.lower().strip()

            confirmed = answer in [
                "да",
                "подтверждаю",
                "подтвердить",
                "верно"
            ]

            result = confirm_command(
                self.pending_command,
                confirmed
            )

            self.pending_command = None

            self.show_response(
                result.get("response", "")
            )

            return

        # MEDIA COMMANDS

        media_result = execute_media_command(text)

        if media_result is not None:

            self.show_response(
                media_result.get(
                    "response",
                    "Команда выполнена"
                )
            )

            return

        # WINDOWS COMMANDS

        command = execute_command(text)

        if command.get("action") == "completed":

            self.show_response(command["response"])
            return

        if command.get("action") == "confirmation_required":

            self.pending_command = command["command"]

            self.show_response(command["response"])
            return

        if command.get("action") == "stop":

            self.show_response(command["response"])
            return

        # AI

        self.ask_ai()

    def ask_ai(self):

        self.waiting_response = True

        self.set_status("JARVIS думает…", "busy")

        self.input.setEnabled(False)
        self.send_button.setEnabled(False)

        self.chat_view.show_typing(True)
        self.refresh_orb()

        messages = self.history[-32:]

        self.ai_worker = AIWorker(messages)

        self.ai_worker.finished_response.connect(
            self.ai_finished
        )

        self.ai_worker.start()

    def ai_finished(self, result):

        self.waiting_response = False

        self.input.setEnabled(True)
        self.send_button.setEnabled(True)

        self.chat_view.show_typing(False)
        self.refresh_orb()

        if not result.get("success"):

            self.show_response(
                result.get(
                    "response",
                    "Неизвестная ошибка AI"
                )
            )

            self.input.setFocus()

            return

        answer = prepare_ai_response(
            result["response"]
        )

        # show_response сам сохраняет ответ.
        # Повторно добавлять его в историю нельзя.

        self.show_response(answer)

        self.input.setFocus()

    def show_response(self, text):

        self.add_message("J.A.R.V.I.S.", text)

        self.history.append({
            "role": "assistant",
            "content": text
        })

        self.save_message("assistant", text)

        self.set_status("Система готова")

        if self.voice_enabled:
            self.enqueue_speech(text)

    # ------------------------------------------------------------
    # ОЗВУЧКА (в отдельном потоке)
    # ------------------------------------------------------------

    def enqueue_speech(self, text):

        voice_text = prepare_voice_response(text)

        if not voice_text:
            return

        self.speak_queue.append(voice_text)

        if not self.speaking:
            self.speak_next()

    def speak_next(self):

        if not self.speak_queue:
            self.speaking = False

            if self.speech and self.voice_enabled:
                self.speech.paused = False

            self.refresh_orb()
            return

        text = self.speak_queue.pop(0)

        self.speaking = True

        # Пока JARVIS говорит, микрофон не слушает.
        if self.speech:
            self.speech.paused = True

        self.refresh_orb()

        self.speak_worker = SpeakWorker(text)
        self.speak_worker.finished_speaking.connect(
            self.speak_finished
        )
        self.speak_worker.start()

    def speak_finished(self, result):

        if not result.get("success", True):
            error = result.get("error", "неизвестная ошибка")
            self.set_status(f"Ошибка озвучки: {error}")

        self.speak_next()

    def stop_speaking(self):

        self.speak_queue.clear()

        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass

    # ------------------------------------------------------------
    # ГОЛОСОВОЙ ВВОД
    # ------------------------------------------------------------

    def start_speech(self):

        if not self.voice_enabled:
            return

        try:

            self.speech = SpeechWorker()

            self.speech.recognized.connect(
                self.voice_recognized
            )

            self.speech.status_changed.connect(
                self.set_status
            )

            self.speech.stop_heard.connect(
                self.voice_stop
            )

            self.speech.start()

            self.update_voice_button()

            self.set_status("Слушаю…")

        except Exception as error:

            self.set_status(
                f"Ошибка микрофона: {error}"
            )

    def voice_recognized(self, text):

        if self.waiting_response:
            return

        if not self.voice_enabled:
            return

        self.process_input(text)

    def voice_stop(self, text):

        self.set_status("Команда остановлена")

        if self.speech:
            self.speech.paused = True

    def toggle_voice(self):

        self.voice_enabled = not self.voice_enabled

        if self.voice_enabled:

            if self.speech is None:
                self.start_speech()
            else:
                self.speech.paused = False

        else:

            self.stop_speaking()

            if self.speech:
                self.speech.paused = True

        self.update_voice_button()

    def update_voice_button(self):

        self.voice_button.setText(
            "🎤" if self.voice_enabled else "🔇"
        )

        self.voice_button.setToolTip(
            "Голос включён. Нажмите, чтобы выключить"
            if self.voice_enabled
            else "Голос выключен. Нажмите, чтобы включить"
        )

        self.voice_button.setProperty("on", self.voice_enabled)

        self.repolish(self.voice_button)

    # ------------------------------------------------------------
    # СИСТЕМНЫЙ МОНИТОР
    # ------------------------------------------------------------

    def update_stats(self, cpu, ram, gpu):

        gpu_text = f"{gpu:.0f}%" if gpu >= 0 else "н/д"

        self.footer.setText(
            f"CPU {cpu:.0f}%  ·  RAM {ram:.0f}%  ·  GPU {gpu_text}"
        )

    # ------------------------------------------------------------
    # СТАТУС
    # ------------------------------------------------------------

    def repolish(self, widget):

        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

    def refresh_orb(self):

        if self.waiting_response:
            self.orb.set_state("thinking")

        elif self.speaking:
            self.orb.set_state("speaking")

        else:
            self.orb.set_state("idle")

    def set_status(self, text, state=None):

        self.status = text

        if state is None:
            state = (
                "error" if "ошибка" in text.lower()
                else "ok"
            )

        self.status_text.setText(f"● {text}")
        self.status_text.setProperty("state", state)

        self.repolish(self.status_text)

    def database_error(self, error):

        self.set_status("Ошибка базы данных")

        print("[DATABASE ERROR]", error)

    # ------------------------------------------------------------
    # ЗАКРЫТИЕ
    # ------------------------------------------------------------

    def stop_thread(self, thread, timeout=3000):

        if thread is None:
            return

        if thread.isRunning() and not thread.wait(timeout):
            thread.terminate()
            thread.wait(1000)

    def closeEvent(self, event):

        self.voice_enabled = False

        self.stop_speaking()

        self.stats_worker.stop()

        if self.speech:
            self.speech.stop_listening()
            self.stop_thread(self.speech)

        self.stop_thread(self.stats_worker)
        self.stop_thread(self.ai_worker)
        self.stop_thread(self.warmup_worker)
        self.stop_thread(self.speak_worker)

        self.db.close()

        event.accept()


def main():

    app = QApplication(sys.argv)

    font = QFont("Segoe UI")
    font.setPixelSize(14)
    app.setFont(font)

    window = JarvisWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":

    try:
        main()

    except Exception:

        traceback.print_exc()

        input("Нажми Enter для выхода...")
