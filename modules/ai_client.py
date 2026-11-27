import requests

from modules.config import (
    MODEL,
    OLLAMA_URL,
    OLLAMA_NUM_CTX,
    SYSTEM_PROMPT
)

def check_ollama():
    try:
        response = requests.get(
            "http://localhost:11434/api/tags",
            timeout=5
        )
        response.raise_for_status()
        return True
    except requests.RequestException:
        return False

def get_available_models():
    try:
        response = requests.get(
            "http://localhost:11434/api/tags",
            timeout=5
        )
        response.raise_for_status()

        data = response.json()
        return [
            model.get("name", "")
            for model in data.get("models", [])
        ]

    except (requests.RequestException, ValueError):
        return []

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

    payload = {
        "model": MODEL,
        "messages": chat_messages,
        "stream": False,
        "options": {
            "num_ctx": OLLAMA_NUM_CTX
        }
    }

    try:
        response = requests.post(
            OLLAMA_URL,
            json=payload,
            timeout=180
        )

        response.raise_for_status()
        data = response.json()

        answer = data.get("message", {}).get("content", "")

        if not answer:
            return {
                "success": False,
                "response": "Модель вернула пустой ответ."
            }

        return {
            "success": True,
            "response": answer.strip()
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