import os
import shutil
import subprocess
import webbrowser
import ipaddress

from pathlib import Path
from urllib.parse import urlparse


CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def open_app(app_name):
    app_name = (app_name or "").lower().strip()

    aliases = {
        "edge": ["edge", "microsoft edge", "эдж", "браузер"],
        "steam": ["steam", "стим"],
        "word": ["word", "microsoft word", "ворд"],
        "notepad": ["notepad", "блокнот"],
        "calculator": ["calculator", "калькулятор"],
        "explorer": ["explorer", "проводник"]
    }

    selected = None

    for key, names in aliases.items():
        if app_name == key or app_name in names:
            selected = key
            break

    if selected is None:
        return "Эта программа пока не входит в список разрешённых."

    try:
        if selected == "notepad":
            subprocess.Popen(["notepad.exe"])
            return "Блокнот успешно открыт."

        if selected == "calculator":
            subprocess.Popen(["calc.exe"])
            return "Калькулятор успешно открыт."

        if selected == "explorer":
            subprocess.Popen(["explorer.exe"])
            return "Проводник успешно открыт."

        if selected == "edge":
            paths = [
                Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
                Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Microsoft/Edge/Application/msedge.exe",
                Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Edge/Application/msedge.exe"
            ]

            for path in paths:
                if path.exists():
                    subprocess.Popen([str(path)])
                    return "Microsoft Edge успешно открыт."

            edge = shutil.which("msedge")

            if edge:
                subprocess.Popen([edge])
                return "Microsoft Edge успешно открыт."

            subprocess.Popen(["cmd", "/c", "start", "", "microsoft-edge:"])
            return "Команда запуска Edge отправлена."

        if selected == "steam":
            paths = [
                Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Steam/steam.exe",
                Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Steam/steam.exe"
            ]

            for path in paths:
                if path.exists():
                    subprocess.Popen([str(path)])
                    return "Steam успешно открыт."

            steam = shutil.which("steam")

            if steam:
                subprocess.Popen([steam])
                return "Steam успешно открыт."

            return "Не удалось найти Steam."

        if selected == "word":
            paths = [
                Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Microsoft Office/root/Office16/WINWORD.EXE",
                Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Microsoft Office/root/Office16/WINWORD.EXE",
                Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Microsoft Office/Office16/WINWORD.EXE",
                Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Microsoft Office/Office16/WINWORD.EXE"
            ]

            for path in paths:
                if path.exists():
                    subprocess.Popen([str(path)])
                    return "Microsoft Word успешно открыт."

            word = shutil.which("WINWORD.EXE")

            if word:
                subprocess.Popen([word])
                return "Microsoft Word успешно открыт."

            return "Не удалось найти Microsoft Word."

    except Exception as error:
        return f"Ошибка запуска программы: {error}"

    return "Не удалось выполнить команду."


def open_website(address):
    address = (address or "").strip()

    websites = {
        "youtube": "https://www.youtube.com",
        "ютуб": "https://www.youtube.com",
        "google": "https://www.google.com",
        "гугл": "https://www.google.com",
        "vk": "https://vk.com",
        "вк": "https://vk.com",
        "twitch": "https://www.twitch.tv",
        "твич": "https://www.twitch.tv",
        "discord": "https://discord.com",
        "дискорд": "https://discord.com",
        "steam": "https://store.steampowered.com",
        "стим": "https://store.steampowered.com"
    }

    if address.lower() in websites:
        address = websites[address.lower()]

    if "://" not in address:
        address = "https://" + address

    try:
        parsed = urlparse(address)

        if parsed.scheme not in ("http", "https"):
            return "Разрешены только HTTP и HTTPS сайты."

        if not parsed.hostname:
            return "Некорректный адрес сайта."

        hostname = parsed.hostname.lower()

        if hostname == "localhost" or hostname.endswith(".localhost"):
            return "Открытие локальных адресов запрещено."

        try:
            ip = ipaddress.ip_address(hostname)

            if not ip.is_global:
                return "Открытие частных IP-адресов запрещено."

        except ValueError:
            pass

        success = webbrowser.open(address)

        if success:
            return f"Открываю {hostname}."

        return "Не удалось открыть сайт."

    except Exception as error:
        return f"Ошибка открытия сайта: {error}"
