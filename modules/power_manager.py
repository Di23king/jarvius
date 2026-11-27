import os
import subprocess

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def lock_pc():
    try:
        if os.name != "nt":
            return "Эта функция работает только в Windows."

        subprocess.Popen(
            ["rundll32.exe", "user32.dll,LockWorkStation"],
            creationflags=CREATE_NO_WINDOW
        )
        return "Компьютер заблокирован."
    except Exception as error:
        return f"Ошибка блокировки: {error}"


def sleep_pc():
    try:
        if os.name != "nt":
            return "Эта функция работает только в Windows."

        subprocess.Popen(
            ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
            creationflags=CREATE_NO_WINDOW
        )
        return "Отправлена команда перехода в спящий режим."
    except Exception as error:
        return f"Ошибка перехода в спящий режим: {error}"


def shutdown_pc():
    if os.name != "nt":
        return "Эта функция работает только в Windows."

    return "Для выключения требуется подтверждение пользователя."


def restart_pc():
    if os.name != "nt":
        return "Эта функция работает только в Windows."

    return "Для перезагрузки требуется подтверждение пользователя."
