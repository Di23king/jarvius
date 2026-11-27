import ctypes
import time


user32 = ctypes.windll.user32

SW_MINIMIZE = 6
SW_MAXIMIZE = 3
SW_RESTORE = 9

VK_MENU = 0x12
VK_F4 = 0x73
VK_TAB = 0x09
VK_D = 0x44
VK_LWIN = 0x5B
VK_SHIFT = 0x10

KEYEVENTF_KEYUP = 0x0002


def get_active_window():
    try:
        return user32.GetForegroundWindow()
    except Exception:
        return None


def minimize_window():
    try:
        hwnd = get_active_window()

        if not hwnd:
            return False

        user32.ShowWindow(hwnd, SW_MINIMIZE)
        return True

    except Exception:
        return False


def maximize_window():
    try:
        hwnd = get_active_window()

        if not hwnd:
            return False

        user32.ShowWindow(hwnd, SW_MAXIMIZE)
        return True

    except Exception:
        return False


def restore_window():
    try:
        hwnd = get_active_window()

        if not hwnd:
            return False

        user32.ShowWindow(hwnd, SW_RESTORE)
        return True

    except Exception:
        return False


def close_window():
    try:
        hwnd = get_active_window()

        if not hwnd:
            return False

        user32.PostMessageW(hwnd, 0x0010, 0, 0)
        return True

    except Exception:
        return False


def press_key(key):
    try:
        user32.keybd_event(key, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(key, 0, KEYEVENTF_KEYUP, 0)
        return True
    except Exception:
        return False


def switch_window():
    try:
        user32.keybd_event(VK_MENU, 0, 0, 0)
        user32.keybd_event(VK_TAB, 0, 0, 0)
        time.sleep(0.1)
        user32.keybd_event(VK_TAB, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        return True
    except Exception:
        return False


def show_desktop():
    try:
        user32.keybd_event(VK_LWIN, 0, 0, 0)
        user32.keybd_event(VK_D, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(VK_D, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)
        return True
    except Exception:
        return False


def execute_window_command(command):
    command = str(command).lower().strip()

    commands = {
        "сверни окно": minimize_window,
        "свернуть окно": minimize_window,
        "разверни окно": maximize_window,
        "развернуть окно": maximize_window,
        "восстанови окно": restore_window,
        "закрой окно": close_window,
        "закрыть окно": close_window,
        "переключи окно": switch_window,
        "следующее окно": switch_window,
        "покажи рабочий стол": show_desktop,
        "рабочий стол": show_desktop
    }

    action = commands.get(command)

    if action is None:
        return {
            "success": False,
            "response": "Неизвестная команда управления окнами"
        }

    result = action()

    return {
        "success": result,
        "response": "Команда выполнена" if result else "Не удалось выполнить команду"
    }
