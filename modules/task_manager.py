import re

COMMAND_PATTERNS = {
    "open_website": [
        r"^(?:открой сайт|зайди на сайт|перейди на сайт)\s+(.+)$",
    ],
    "open_app": [
        r"^(?:открой|запусти|включи)\s+(.+)$",
    ],
    "search_files": [
        r"^(?:найди файл|найди файлы|поищи файл|поищи файлы)\s*(.*)$",
    ],
    "system_info": [
        r"^(?:информация о системе|характеристики компьютера|состояние компьютера|информация о компьютере)$",
    ],
    "processes": [
        r"^(?:список процессов|какие процессы запущены|покажи процессы|открой список процессов)$",
    ],
    "lock_pc": [
        r"^(?:заблокируй компьютер|заблокируй пк|заблокируй систему)$",
    ],
    "sleep_pc": [
        r"^(?:переведи компьютер в сон|усыпи компьютер|режим сна)$",
    ],
    "shutdown_pc": [
        r"^(?:выключи компьютер|выключи пк|заверши работу компьютера)$",
    ],
    "restart_pc": [
        r"^(?:перезагрузи компьютер|перезагрузи пк|перезапусти компьютер)$",
    ],
    "stop": [
        r"^(?:стоп|отмена|отмени)$",
    ],
}

def normalize_command(text):
    if not isinstance(text, str):
        return ""

    text = text.lower().strip()
    text = text.replace("ё", "е")
    text = re.sub(r"\s+", " ", text)

    return text

def extract_argument(text, pattern):
    match = re.search(pattern, text, re.IGNORECASE)

    if not match:
        return ""

    if match.lastindex:
        return match.group(1).strip()

    return ""

def recognize_command(text):
    normalized = normalize_command(text)

    if not normalized:
        return {
            "type": "empty",
            "argument": "",
            "recognized": False,
        }

    for command_type, patterns in COMMAND_PATTERNS.items():
        for pattern in patterns:
            argument = extract_argument(normalized, pattern)

            if re.match(pattern, normalized, re.IGNORECASE):
                return {
                    "type": command_type,
                    "argument": argument,
                    "recognized": True,
                }

    return {
        "type": "chat",
        "argument": normalized,
        "recognized": False,
    }

def is_command(text):
    result = recognize_command(text)
    return result["recognized"]

def get_command_type(text):
    return recognize_command(text)["type"]

def get_command_argument(text):
    return recognize_command(text)["argument"]

def format_command_result(result):
    if not isinstance(result, dict):
        return str(result)

    if result.get("success"):
        return result.get("response", "Команда выполнена")

    return result.get("response", "Не удалось выполнить команду")