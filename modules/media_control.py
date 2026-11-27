import ctypes
import time
import re

user32 = ctypes.windll.user32

KEYEVENTF_KEYUP = 0x0002

VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF

VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3

def press_key(key):
    try:
        user32.keybd_event(key, 0, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(key, 0, KEYEVENTF_KEYUP, 0)
        return True
    except Exception:
        return False

def volume_up(steps=1):
    for _ in range(max(1, min(int(steps), 50))):
        if not press_key(VK_VOLUME_UP):
            return False
    return True

def volume_down(steps=1):
    for _ in range(max(1, min(int(steps), 50))):
        if not press_key(VK_VOLUME_DOWN):
            return False
    return True

def volume_mute():
    return press_key(VK_VOLUME_MUTE)

def media_play_pause():
    return press_key(VK_MEDIA_PLAY_PAUSE)

def media_next():
    return press_key(VK_MEDIA_NEXT_TRACK)

def media_previous():
    return press_key(VK_MEDIA_PREV_TRACK)

def media_stop():
    return press_key(VK_MEDIA_STOP)

def execute_media_command(command):
    command = str(command).lower().strip()
    command = re.sub(r"\s+", " ", command)

    commands = {
        "громче": volume_up,
        "увеличь громкость": volume_up,
        "сделай громче": volume_up,

        "тише": volume_down,
        "уменьши громкость": volume_down,
        "сделай тише": volume_down,

        "выключи звук": volume_mute,
        "включи звук": volume_mute,
        "без звука": volume_mute,

        "пауза": media_play_pause,
        "продолжи": media_play_pause,
        "продолжи воспроизведение": media_play_pause,

        "следующий трек": media_next,
        "следующий": media_next,
        "скип": media_next,
        "skip": media_next,
        "дальше": media_next,
        "следующая песня": media_next,

        "предыдущий трек": media_previous,
        "предыдущий": media_previous,
        "прошлый": media_previous,
        "верни": media_previous,
        "предыдущая песня": media_previous,

        "останови музыку": media_stop,
    }

    action = commands.get(command)

    # Если это не мультимедийная команда,
    # возвращаем None, чтобы сообщение ушло в Qwen.
    if action is None:
        return None

    result = action()

    return {
        "success": result,
        "response": (
            "Команда выполнена"
            if result
            else "Не удалось выполнить команду"
        )
    }