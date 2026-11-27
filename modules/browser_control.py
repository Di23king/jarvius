import ctypes
import time
import urllib.parse
import webbrowser


user32 = ctypes.windll.user32

KEYEVENTF_KEYUP = 0x0002

VK_CONTROL = 0x11
VK_ALT = 0x12
VK_SHIFT = 0x10
VK_TAB = 0x09
VK_W = 0x57
VK_T = 0x54
VK_R = 0x52
VK_L = 0x4C
VK_LEFT = 0x25
VK_RIGHT = 0x27


def press_key(key):
    try:
        user32.keybd_event(key, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(key, 0, KEYEVENTF_KEYUP, 0)
        return True
    except Exception:
        return False


def press_combination(*keys):
    pressed = []

    try:
        for key in keys:
            user32.keybd_event(key, 0, 0, 0)
            pressed.append(key)

        time.sleep(0.05)

        return True

    except Exception:
        return False

    finally:
        for key in reversed(pressed):
            user32.keybd_event(key, 0, KEYEVENTF_KEYUP, 0)


def new_tab():
    return press_combination(VK_CONTROL, VK_T)


def close_tab():
    return press_combination(VK_CONTROL, VK_W)


def next_tab():
    return press_combination(VK_CONTROL, VK_TAB)


def previous_tab():
    return press_combination(VK_CONTROL, VK_SHIFT, VK_TAB)


def refresh_page():
    return press_key(VK_F5) if False else press_combination(VK_CONTROL, VK_R)


def go_back():
    return press_combination(VK_ALT, VK_LEFT)


def go_forward():
    return press_combination(VK_ALT, VK_RIGHT)


def open_google_search(query):
    query = str(query).strip()

    if not query:
        return {
            "success": False,
            "response": "Не указан поисковый запрос"
        }

    try:
        url = "https://www.google.com/search?q=" + urllib.parse.quote(query)
        webbrowser.open_new_tab(url)

        return {
            "success": True,
            "response": f"Ищу в Google: {query}"
        }

    except Exception as error:
        return {
            "success": False,
            "response": f"Ошибка поиска: {error}"
        }


def execute_browser_command(command, argument=""):
    command = str(command).lower().strip()

    commands = {
        "новая вкладка": new_tab,
        "открой новую вкладку": new_tab,
        "закрой вкладку": close_tab,
        "следующая вкладка": next_tab,
        "предыдущая вкладка": previous_tab,
        "обнови страницу": refresh_page,
        "назад": go_back,
        "вперед": go_forward
    }

    if command in ("поиск", "найди в интернете", "поищи в интернете"):
        return open_google_search(argument)

    action = commands.get(command)

    if action is None:
        return {
            "success": False,
            "response": "Неизвестная команда браузера"
        }

    result = action()

    return {
        "success": result,
        "response": "Команда выполнена" if result else "Не удалось выполнить команду"
    }
