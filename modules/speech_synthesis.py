import subprocess
import tempfile
import winsound

from pathlib import Path

from modules.config import (
    BASE_DIR,
    PIPER_EXE,
    PIPER_VOICE_FILE,
    VOICE_ENABLED,
    CREATE_NO_WINDOW
)

from modules.text_processing import clean_for_speech


def get_piper_paths():
    piper = BASE_DIR / PIPER_EXE
    voice = BASE_DIR / PIPER_VOICE_FILE

    return piper, voice


def check_piper():
    piper, voice = get_piper_paths()

    if not piper.exists():
        return False, f"Не найден Piper: {piper}"

    if not voice.exists():
        return False, f"Не найдена модель голоса: {voice}"

    return True, "Piper готов к работе"


def synthesize_speech(text, output_path=None):
    text = clean_for_speech(text)

    if not text:
        return {
            "success": False,
            "error": "Пустой текст"
        }

    status, message = check_piper()

    if not status:
        return {
            "success": False,
            "error": message
        }

    piper, voice = get_piper_paths()

    if output_path is None:
        temp = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False
        )
        output_path = Path(temp.name)
        temp.close()
    else:
        output_path = Path(output_path)

    command = [
        str(piper),
        "--model", str(voice),
        "--output_file", str(output_path)
    ]

    try:
        result = subprocess.run(
            command,
            input=text,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=120,
            creationflags=CREATE_NO_WINDOW
        )

        if result.returncode != 0:
            return {
                "success": False,
                "error": result.stderr.strip() or "Ошибка Piper"
            }

        if not output_path.exists() or output_path.stat().st_size == 0:
            return {
                "success": False,
                "error": "Piper не создал аудиофайл"
            }

        return {
            "success": True,
            "path": str(output_path)
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Превышено время ожидания Piper"
        }

    except Exception as error:
        return {
            "success": False,
            "error": str(error)
        }


def play_audio(audio_path):
    audio_path = Path(audio_path)

    if not audio_path.exists():
        return False

    try:
        winsound.PlaySound(
            str(audio_path),
            winsound.SND_FILENAME
        )
        return True

    except Exception:
        return False


def speak(text):
    if not VOICE_ENABLED:
        return {
            "success": False,
            "error": "Голосовой вывод отключён"
        }

    result = synthesize_speech(text)

    if not result["success"]:
        return result

    audio_path = Path(result["path"])

    try:
        played = play_audio(audio_path)

        if not played:
            return {
                "success": False,
                "error": "Не удалось воспроизвести аудио"
            }

        return {
            "success": True,
            "message": "Речь воспроизведена"
        }

    finally:
        try:
            audio_path.unlink(missing_ok=True)
        except Exception:
            pass
