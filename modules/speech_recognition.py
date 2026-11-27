import json
import queue
from pathlib import Path

import sounddevice as sd
from vosk import Model, KaldiRecognizer
from PySide6.QtCore import QThread, Signal

from modules.config import (
    BASE_DIR,
    VOSK_MODEL_PATH,
    SAMPLE_RATE,
    MICROPHONE_NAME,
    BARGE_IN_ENABLED
)


class SpeechWorker(QThread):

    recognized = Signal(str)
    partial = Signal(str)
    stop_heard = Signal(str)
    status_changed = Signal(str)

    shared_model = None

    def __init__(self):
        super().__init__()

        self.running = False
        self.paused = False
        self.was_paused = False
        self.listening = False
        self.barge_in = BARGE_IN_ENABLED
        self.audio_queue = queue.Queue()

    def stop_listening(self):
        self.running = False

    def audio_callback(self, indata, frames, time_info, status):
        self.audio_queue.put(bytes(indata))

    def is_stop_phrase(self, text):
        words = text.lower().split()

        stop_words = {"стоп"}
        cancel_words = {"отмена"}

        words = [
            word for word in words
            if word not in {"джарвис", "джервис", "жарвис"}
        ]

        if not words or len(words) > 2:
            return False

        return all(
            word in stop_words or word in cancel_words
            for word in words
        )

    def check_stop_word(self, recognizer, data):
        try:
            if recognizer.AcceptWaveform(data):
                text = json.loads(
                    recognizer.Result()
                ).get("text", "")
            else:
                text = json.loads(
                    recognizer.PartialResult()
                ).get("partial", "")

        except Exception:
            return None

        text = text.strip()

        if text and self.is_stop_phrase(text):
            recognizer.Reset()
            return text

        return None

    def run(self):
        had_error = False

        try:
            self.running = True

            model_path = BASE_DIR / VOSK_MODEL_PATH

            if not model_path.exists():
                had_error = True
                self.status_changed.emit(
                    "ОШИБКА: МОДЕЛЬ VOSK НЕ НАЙДЕНА"
                )
                return

            if SpeechWorker.shared_model is None:
                self.status_changed.emit("ЗАГРУЗКА VOSK...")
                SpeechWorker.shared_model = Model(str(model_path))

            recognizer = KaldiRecognizer(
                SpeechWorker.shared_model,
                SAMPLE_RATE
            )

            stop_recognizer = None

            if self.barge_in:
                grammar = json.dumps(
                    ["стоп", "отмена", "[unk]"],
                    ensure_ascii=False
                )

                stop_recognizer = KaldiRecognizer(
                    SpeechWorker.shared_model,
                    SAMPLE_RATE,
                    grammar
                )

            devices = sd.query_devices()
            device_id = None

            for i, device in enumerate(devices):
                if MICROPHONE_NAME.lower() in device["name"].lower():
                    if device["max_input_channels"] > 0:
                        device_id = i
                        break

            if device_id is None:
                had_error = True
                self.status_changed.emit(
                    "USB-МИКРОФОН НЕ НАЙДЕН"
                )
                return

            last_partial = ""

            with sd.RawInputStream(
                samplerate=SAMPLE_RATE,
                blocksize=4000,
                device=device_id,
                dtype="int16",
                channels=1,
                callback=self.audio_callback
            ):
                self.listening = True
                self.status_changed.emit("СЛУШАЮ ВАС...")

                while self.running:
                    try:
                        data = self.audio_queue.get(timeout=0.2)
                    except queue.Empty:
                        continue

                    if self.paused:
                        self.was_paused = True

                        if stop_recognizer is not None:
                            word = self.check_stop_word(
                                stop_recognizer,
                                data
                            )

                            if word:
                                self.stop_heard.emit(word)

                        continue

                    if self.was_paused:
                        self.was_paused = False

                        while not self.audio_queue.empty():
                            try:
                                self.audio_queue.get_nowait()
                            except queue.Empty:
                                break

                        recognizer.Reset()

                        if stop_recognizer is not None:
                            stop_recognizer.Reset()

                        last_partial = ""
                        continue

                    if recognizer.AcceptWaveform(data):
                        result = json.loads(recognizer.Result())
                        text = result.get("text", "").strip()

                        last_partial = ""

                        if text:
                            self.recognized.emit(text)

                    else:
                        partial = json.loads(
                            recognizer.PartialResult()
                        ).get("partial", "").strip()

                        if partial and partial != last_partial:
                            last_partial = partial
                            self.partial.emit(partial)

            self.listening = False

            if not self.paused:
                final_result = json.loads(recognizer.FinalResult())
                final_text = final_result.get("text", "").strip()

                if final_text:
                    self.recognized.emit(final_text)

        except Exception as error:
            had_error = True
            self.status_changed.emit(
                f"ОШИБКА МИКРОФОНА: {error}"
            )

        finally:
            self.running = False
            self.listening = False

            if not had_error:
                self.status_changed.emit("SYSTEM ONLINE")
