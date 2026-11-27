import ctypes
import os
import threading
import time
import uuid

def show_notification(title, message, duration=5):
    """
    Показывает системное уведомление Windows.
    """

    title = str(title).strip()
    message = str(message).strip()

    if not title or not message:
        return {
            "success": False,
            "response": "Заголовок и текст уведомления не должны быть пустыми"
        }

    try:
        from winotify import Notification

        notification = Notification(
            app_id="JARVIS V2",
            title=title,
            msg=message,
            duration="short" if duration <= 5 else "long"
        )

        notification.show()

        return {
            "success": True,
            "response": "Уведомление отправлено"
        }

    except ImportError:
        return {
            "success": False,
            "response": "Не установлен winotify. Выполни: py -m pip install winotify"
        }

    except Exception as error:
        return {
            "success": False,
            "response": f"Ошибка уведомления: {error}"
        }

def notify_jarvis(message):
    return show_notification("JARVIS", message)

def notify_error(message):
    return show_notification("JARVIS — Ошибка", message, duration=8)

def notify_success(message):
    return show_notification("JARVIS — Готово", message)

def notify_reminder(message):
    return show_notification("JARVIS — Напоминание", message, duration=8)

def schedule_notification(title, message, delay):
    """
    Планирует уведомление через указанное количество секунд.
    """

    try:
        delay = max(1, int(delay))

        timer = threading.Timer(
            delay,
            show_notification,
            args=(title, message)
        )

        timer.daemon = True
        timer.start()

        return {
            "success": True,
            "response": f"Уведомление запланировано через {delay} сек."
        }

    except Exception as error:
        return {
            "success": False,
            "response": f"Не удалось запланировать уведомление: {error}"
        }