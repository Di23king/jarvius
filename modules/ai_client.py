import re

import requests

from modules.config import (
    MODEL,
    OLLAMA_URL,
    OLLAMA_NUM_CTX,
    SYSTEM_PROMPT
)

TAGS_URL = "http://localhost:11434/api/tags"

# Сколько держать модель в памяти после последнего запроса.
# Без этого Ollama выгружает модель, и каждый ответ начинается с загрузки.
KEEP_ALIVE = "30m"

# Максимум токенов в ответе. Для голосового помощника хватает с запасом.
MAX_TOKENS = 300

# Первый запрос после запуска может грузить модель, поэтому таймаут большой.
# Обычные ответы после прогрева идут за секунды.
REQUEST_TIMEOUT = 120

THINK_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def check_ollama():
    try:
        response = requests.get(TAGS_URL, timeout=3)
        response.raise_for_status()
        return True
    except requests.RequestException:
        return False


def get_available_models():
    try:
        response = requests.get(TAGS_URL, timeout=3)
        response.raise_for_status()

        data = response.json()
        return [
            model.get("name", "")
            for model in data.get("models", [])
        ]

    except (requests.RequestException, ValueError):
        return []


def _build_payload(chat_messages):
    return {
        "model": MODEL,
        "messages": chat_messages,
        "stream": False,

        # Главное исправление: не включать режим рассуждений.
        # Qwen 3.x по умолчанию долго "думает" перед ответом.
        "think": False,

        "keep_alive": KEEP_ALIVE,

        "options": {
            "num_ctx": OLLAMA_NUM_CTX,
            "num_predict": MAX_TOKENS,
            "temperature": 0.6
        }
    }


def _clean_answer(text):
    # На случай, если модель всё равно вернула рассуждения в тексте.
    text = THINK_PATTERN.sub("", text or "")
    return text.strip()


def warm_up():
    """
    Загружает модель в память заранее.
    Вызывать при запуске программы в отдельном потоке,
    чтобы первый ответ не ждал загрузки.
    """
    if not check_ollama():
        return False

    try:
        requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": "привет"}],
                "stream": False,
                "think": False,
                "keep_alive": KEEP_ALIVE,
                "options": {"num_predict": 1}
            },
            timeout=REQUEST_TIMEOUT
        )
        return True

    except requests.RequestException:
        return False


def send_message(messages, system_prompt=None):
    if not check_ollama():
        return {
            "success": False,
            "response": "Ollama не запущена или недоступна."
        }

    if system_prompt is None:
        system_prompt = SYSTEM_PROMPT

    chat_messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]

    chat_messages.extend(messages)

    try:
        response = requests.post(
            OLLAMA_URL,
            json=_build_payload(chat_messages),
            timeout=REQUEST_TIMEOUT
        )

        response.raise_for_status()
        data = response.json()

        message = data.get("message", {})
        answer = _clean_answer(message.get("content", ""))

        if not answer:
            return {
                "success": False,
                "response": "Модель вернула пустой ответ."
            }

        return {
            "success": True,
            "response": answer
        }

    except requests.Timeout:
        return {
            "success": False,
            "response": "Модель слишком долго отвечает."
        }

    except requests.ConnectionError:
        return {
            "success": False,
            "response": "Не удалось подключиться к Ollama."
        }

    except requests.RequestException as error:
        return {
            "success": False,
            "response": f"Ошибка запроса к Ollama: {error}"
        }

    except (ValueError, KeyError) as error:
        return {
            "success": False,
            "response": f"Ошибка обработки ответа модели: {error}"
        }
