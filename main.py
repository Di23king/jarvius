import sys
import uuid
import html
import math
import subprocess
import shutil
import traceback

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient, QFont
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QLineEdit,
    QPushButton,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QFrame,
    QProgressBar
)

import psutil

from modules.config import SYSTEM_PROMPT
from modules.database import (
    DatabaseWorker,
    db_startup,
    db_create_chat,
    db_save_message,
    db_load_messages
)

from modules.ai_client import send_message
from modules.speech_recognition import SpeechWorker
from modules.speech_synthesis import speak
from modules.command_executor import execute_command, confirm_command
from modules.media_control import execute_media_command
from modules.text_processing import (
    prepare_ai_response,
    prepare_voice_response
)


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


class ReactorWidget(QWidget):

    def __init__(self):
        super().__init__()

        self.angle = 0
        self.active = False

        self.setMinimumSize(230, 230)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(30)

    def animate(self):
        self.angle = (self.angle + 2) % 360
        self.update()

    def set_active(self, active):
        self.active = active
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        cx = self.width() / 2
        cy = self.height() / 2

        radius = min(self.width(), self.height()) * 0.34

        color = QColor("#39caff")

        if self.active:
            color = QColor("#55e6ff")

        gradient = QRadialGradient(cx, cy, radius * 1.7)
        gradient.setColorAt(0, QColor(30, 170, 230, 65))
        gradient.setColorAt(0.55, QColor(20, 100, 160, 20))
        gradient.setColorAt(1, QColor(10, 20, 35, 0))

        painter.setPen(Qt.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(
            int(cx - radius * 1.7),
            int(cy - radius * 1.7),
            int(radius * 3.4),
            int(radius * 3.4)
        )

        painter.setBrush(Qt.NoBrush)

        for i in range(4):
            current_radius = radius * (0.55 + i * 0.18)

            pen = QPen(color)
            pen.setWidth(2 if i == 0 else 1)
            pen.setColor(QColor(
                color.red(),
                color.green(),
                color.blue(),
                180 - i * 35
            ))

            painter.setPen(pen)

            painter.drawEllipse(
                int(cx - current_radius),
                int(cy - current_radius),
                int(current_radius * 2),
                int(current_radius * 2)
            )

        painter.save()
        painter.translate(cx, cy)
        painter.rotate(self.angle)

        pen = QPen(color)
        pen.setWidth(3)
        painter.setPen(pen)

        painter.drawArc(
            int(-radius * 1.3),
            int(-radius * 1.3),
            int(radius * 2.6),
            int(radius * 2.6),
            0,
            95 * 16
        )

        painter.drawArc(
            int(-radius * 1.3),
            int(-radius * 1.3),
            int(radius * 2.6),
            int(radius * 2.6),
            180 * 16,
            95 * 16
        )

        painter.restore()

        core_gradient = QRadialGradient(cx, cy, radius * 0.55)
        core_gradient.setColorAt(0, QColor("#a5f2ff"))
        core_gradient.setColorAt(0.35, QColor("#28b9ed"))
        core_gradient.setColorAt(1, QColor("#07517e"))

        painter.setPen(QPen(color, 2))
        painter.setBrush(core_gradient)

        painter.drawEllipse(
            int(cx - radius * 0.48),
            int(cy - radius * 0.48),
            int(radius * 0.96),
            int(radius * 0.96)
        )

        painter.setPen(QColor("#ffffff"))

        font = QFont("Segoe UI", 10)
        font.setBold(True)
        painter.setFont(font)

        painter.drawText(
            self.rect(),
            Qt.AlignCenter,
            "J.A.R.V.I.S."
        )

        painter.end()


class JarvisWindow(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("J.A.R.V.I.S. V2")
        self.resize(1450, 900)
        self.setMinimumSize(1050, 680)

        self.db = DatabaseWorker()

        self.speech = None
        self.ai_worker = None

        self.chat_id = None
        self.history = []
        self.facts = []

        self.voice_enabled = True
        self.waiting_response = False
        self.pending_command = None

        self.init_ui()

        self.db.failed.connect(self.database_error)

        self.stats_timer = QTimer(self)
        self.stats_timer.timeout.connect(self.update_stats)
        self.stats_timer.start(2000)

        self.db.call(
            db_startup,
            self.startup_finished
        )

    def init_ui(self):

        self.setStyleSheet("""
            QWidget {
                background-color: #090e17;
                color: #dceaf5;
                font-family: Segoe UI;
                font-size: 13px;
            }

            QFrame#Panel {
                background-color: #101927;
                border: 1px solid #1d3448;
                border-radius: 12px;
            }

            QLabel#Title {
                color: #54d6ff;
                font-size: 25px;
                font-weight: bold;
                letter-spacing: 3px;
            }

            QLabel#Subtitle {
                color: #68879d;
                font-size: 10px;
            }

            QLabel#Section {
                color: #55cfff;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 2px;
            }

            QLabel#Metric {
                color: #d9f5ff;
                font-size: 18px;
                font-weight: bold;
            }

            QLabel#Small {
                color: #7893a8;
                font-size: 11px;
            }

            QTextEdit, QLineEdit, QListWidget {
                background-color: #0b1420;
                border: 1px solid #20384c;
                border-radius: 8px;
                padding: 10px;
                color: #e8f7ff;
                selection-background-color: #12658b;
            }

            QListWidget::item {
                padding: 12px;
                border-radius: 6px;
                margin: 2px;
            }

            QListWidget::item:selected {
                background-color: #123b55;
                color: #70dcff;
            }

            QListWidget::item:hover {
                background-color: #152b3c;
            }

            QPushButton {
                background-color: #123d59;
                border: 1px solid #237ba5;
                border-radius: 7px;
                padding: 10px 15px;
                color: #d9f5ff;
                font-weight: bold;
            }

            QPushButton:hover {
                background-color: #17658d;
                border-color: #45caff;
            }

            QPushButton:disabled {
                background-color: #202b36;
                color: #657786;
                border-color: #303d49;
            }

            QProgressBar {
                background-color: #08111b;
                border: 1px solid #233b50;
                border-radius: 4px;
                height: 7px;
                text-align: center;
            }

            QProgressBar::chunk {
                background-color: #24b9ed;
                border-radius: 4px;
            }

            QSplitter::handle {
                background-color: #142638;
                width: 2px;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(15, 15, 15, 15)
        root.setSpacing(12)

        # HEADER

        header = QFrame()
        header.setObjectName("Panel")

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 12, 18, 12)

        title_box = QVBoxLayout()

        title = QLabel("J.A.R.V.I.S.")
        title.setObjectName("Title")

        subtitle = QLabel("PERSONAL ARTIFICIAL INTELLIGENCE SYSTEM")
        subtitle.setObjectName("Subtitle")

        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        header_layout.addLayout(title_box)
        header_layout.addStretch()

        self.system_status = QLabel("● SYSTEM STARTING")
        self.system_status.setStyleSheet(
            "color: #e7bd59; font-weight: bold;"
        )

        header_layout.addWidget(self.system_status)

        root.addWidget(header)

        # MAIN SPLITTER

        splitter = QSplitter(Qt.Horizontal)

        # LEFT PANEL

        left_panel = QFrame()
        left_panel.setObjectName("Panel")
        left_panel.setMinimumWidth(210)
        left_panel.setMaximumWidth(300)

        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 15, 12, 15)

        chats_label = QLabel("CHAT DATABASE")
        chats_label.setObjectName("Section")

        self.chat_list = QListWidget()
        self.chat_list.itemClicked.connect(self.select_chat)

        new_chat_button = QPushButton("+  НОВЫЙ ЧАТ")
        new_chat_button.clicked.connect(self.new_chat)

        left_layout.addWidget(chats_label)
        left_layout.addWidget(self.chat_list)
        left_layout.addWidget(new_chat_button)

        left_layout.addSpacing(15)

        memory_label = QLabel("MEMORY SYSTEM")
        memory_label.setObjectName("Section")

        self.memory_count = QLabel("Сохранено фактов: 0")
        self.memory_count.setObjectName("Small")

        left_layout.addWidget(memory_label)
        left_layout.addWidget(self.memory_count)

        left_layout.addStretch()

        version_label = QLabel("J.A.R.V.I.S. V2\nLOCAL AI CORE")
        version_label.setObjectName("Subtitle")

        left_layout.addWidget(version_label)

        # CENTER PANEL

        center_panel = QFrame()
        center_panel.setObjectName("Panel")

        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(15, 15, 15, 15)
        center_layout.setSpacing(12)

        center_header = QHBoxLayout()

        chat_title = QLabel("NEURAL INTERFACE")
        chat_title.setObjectName("Section")

        self.chat_state = QLabel("ONLINE")
        self.chat_state.setStyleSheet("color: #4fd6a0;")

        center_header.addWidget(chat_title)
        center_header.addStretch()
        center_header.addWidget(self.chat_state)

        center_layout.addLayout(center_header)

        self.chat = QTextEdit()
        self.chat.setReadOnly(True)
        self.chat.setPlaceholderText(
            "История взаимодействия с J.A.R.V.I.S."
        )

        center_layout.addWidget(self.chat, 1)

        input_layout = QHBoxLayout()

        self.input = QLineEdit()
        self.input.setPlaceholderText(
            "Введите команду или сообщение..."
        )

        self.input.returnPressed.connect(self.send_text)

        send_button = QPushButton("ОТПРАВИТЬ")
        send_button.clicked.connect(self.send_text)

        self.voice_button = QPushButton("ГОЛОС: ВКЛ")
        self.voice_button.clicked.connect(self.toggle_voice)

        input_layout.addWidget(self.input, 1)
        input_layout.addWidget(send_button)
        input_layout.addWidget(self.voice_button)

        center_layout.addLayout(input_layout)

        # RIGHT PANEL

        right_panel = QFrame()
        right_panel.setObjectName("Panel")
        right_panel.setMinimumWidth(230)
        right_panel.setMaximumWidth(330)

        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 15, 12, 15)

        reactor_title = QLabel("CORE REACTOR")
        reactor_title.setObjectName("Section")
        reactor_title.setAlignment(Qt.AlignCenter)

        right_layout.addWidget(reactor_title)

        self.reactor = ReactorWidget()

        right_layout.addWidget(self.reactor, 1)

        self.reactor_status = QLabel("ЯДРО АКТИВНО")
        self.reactor_status.setAlignment(Qt.AlignCenter)
        self.reactor_status.setStyleSheet(
            "color: #48cfff; font-weight: bold;"
        )

        right_layout.addWidget(self.reactor_status)

        right_layout.addSpacing(15)

        stats_title = QLabel("SYSTEM MONITOR")
        stats_title.setObjectName("Section")

        right_layout.addWidget(stats_title)

        self.cpu_value = QLabel("CPU: 0%")
        self.cpu_value.setObjectName("Metric")

        self.cpu_bar = QProgressBar()
        self.cpu_bar.setRange(0, 100)
        self.cpu_bar.setTextVisible(False)

        self.ram_value = QLabel("RAM: 0%")
        self.ram_value.setObjectName("Metric")

        self.ram_bar = QProgressBar()
        self.ram_bar.setRange(0, 100)
        self.ram_bar.setTextVisible(False)

        self.gpu_value = QLabel("GPU: —")
        self.gpu_value.setObjectName("Metric")

        right_layout.addWidget(self.cpu_value)
        right_layout.addWidget(self.cpu_bar)
        right_layout.addWidget(self.ram_value)
        right_layout.addWidget(self.ram_bar)
        right_layout.addWidget(self.gpu_value)

        splitter.addWidget(left_panel)
        splitter.addWidget(center_panel)
        splitter.addWidget(right_panel)

        splitter.setSizes([230, 850, 280])

        root.addWidget(splitter, 1)

    # DATABASE

    def startup_finished(self, data):

        self.facts = data.get("facts", [])

        self.memory_count.setText(
            f"Сохранено фактов: {len(self.facts)}"
        )

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

            self.render_history()

        else:
            self.new_chat()

        self.start_speech()

        self.set_status("Система готова")

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

    def new_chat(self):

        self.chat_id = str(uuid.uuid4())

        self.history = []
        self.chat.clear()

        title = "Новый чат"

        item = QListWidgetItem(title)
        item.setData(Qt.UserRole, self.chat_id)

        self.chat_list.addItem(item)
        self.chat_list.setCurrentItem(item)

        chat_id = self.chat_id

        self.db.call(
            lambda chat, mem: db_create_chat(
                chat,
                chat_id,
                title
            )
        )

        self.set_status("Создан новый чат")

    def select_chat(self, item):

        chat_id = item.data(Qt.UserRole)

        if not chat_id:
            return

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

    # CHAT

    def render_history(self):

        self.chat.clear()

        for message in self.history:

            if message["role"] == "user":
                self.add_message("ВЫ", message["content"])

            elif message["role"] == "assistant":
                self.add_message(
                    "J.A.R.V.I.S.",
                    message["content"]
                )

    def add_message(self, author, text):

        safe_author = html.escape(str(author))
        safe_text = html.escape(str(text)).replace("\n", "<br>")

        color = "#57cfff"

        if author == "ВЫ":
            color = "#82aaff"

        self.chat.append(
            f'<p style="margin-top:12px;">'
            f'<b style="color:{color};">{safe_author}</b><br>'
            f'<span style="color:#dceaf5;">{safe_text}</span>'
            f'</p>'
        )

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

        self.set_status("JARVIS обрабатывает запрос")

        self.input.setEnabled(False)

        self.reactor.set_active(True)
        self.reactor_status.setText("ОБРАБОТКА ЗАПРОСА")

        messages = self.history[-32:]

        self.ai_worker = AIWorker(messages)

        self.ai_worker.finished_response.connect(
            self.ai_finished
        )

        self.ai_worker.start()

    def ai_finished(self, result):

        self.waiting_response = False

        self.input.setEnabled(True)

        self.reactor.set_active(False)
        self.reactor_status.setText("ЯДРО АКТИВНО")

        if not result.get("success"):

            self.show_response(
                result.get(
                    "response",
                    "Неизвестная ошибка AI"
                )
            )

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

            if self.speech:
                self.speech.paused = True

            voice_text = prepare_voice_response(text)

            if voice_text:
                speak(voice_text)

            if self.speech and self.voice_enabled:
                self.speech.paused = False

    # VOICE

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

            self.voice_button.setText("ГОЛОС: ВКЛ")

            self.set_status("Слушаю...")

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

            self.voice_button.setText("ГОЛОС: ВКЛ")

            if self.speech is None:
                self.start_speech()
            else:
                self.speech.paused = False

        else:

            self.voice_button.setText("ГОЛОС: ВЫКЛ")

            if self.speech:
                self.speech.paused = True

        self.set_status(
            "Голос включён" if self.voice_enabled
            else "Голос выключен"
        )

    # SYSTEM MONITOR

    def update_stats(self):

        try:

            cpu = psutil.cpu_percent()
            ram = psutil.virtual_memory().percent

            self.cpu_value.setText(f"CPU: {cpu:.0f}%")
            self.cpu_bar.setValue(int(cpu))

            self.ram_value.setText(f"RAM: {ram:.0f}%")
            self.ram_bar.setValue(int(ram))

            if shutil.which("nvidia-smi"):

                result = subprocess.run(
                    [
                        "nvidia-smi",
                        "--query-gpu=utilization.gpu",
                        "--format=csv,noheader,nounits"
                    ],
                    capture_output=True,
                    text=True,
                    timeout=2
                )

                if result.returncode == 0:
                    value = result.stdout.strip().splitlines()[0]
                    self.gpu_value.setText(f"GPU: {value}%")
                else:
                    self.gpu_value.setText("GPU: —")

            else:
                self.gpu_value.setText("GPU: N/A")

        except Exception:
            pass

    # STATUS

    def set_status(self, text):

        self.status = text

        self.system_status.setText(
            f"● {text.upper()}"
        )

        if "ошибка" in text.lower():
            self.system_status.setStyleSheet(
                "color: #ff6868; font-weight: bold;"
            )
        else:
            self.system_status.setStyleSheet(
                "color: #50d9a0; font-weight: bold;"
            )

    def database_error(self, error):

        self.set_status("Ошибка базы данных")

        print("[DATABASE ERROR]", error)

    # CLOSE

    def closeEvent(self, event):

        self.voice_enabled = False

        if self.speech:

            self.speech.stop_listening()
            self.speech.wait(3000)

        if self.ai_worker and self.ai_worker.isRunning():
            self.ai_worker.wait(3000)

        self.db.close()

        event.accept()


def main():

    app = QApplication(sys.argv)

    window = JarvisWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":

    try:
        main()

    except Exception:

        traceback.print_exc()

        input("Нажми Enter для выхода...")
