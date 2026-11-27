import platform
import subprocess
import json
import psutil


def format_bytes(size):
    units = ["B", "KB", "MB", "GB", "TB"]

    for unit in units:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024

    return f"{size:.1f} PB"


def describe_cpu():
    try:
        cpu = psutil.cpu_percent(interval=0.5)
        physical = psutil.cpu_count(logical=False)
        logical = psutil.cpu_count(logical=True)
        frequency = psutil.cpu_freq()

        result = [
            "Процессор:",
            f"Загрузка: {cpu}%",
            f"Физические ядра: {physical}",
            f"Логические ядра: {logical}"
        ]

        if frequency:
            result.append(f"Частота: {frequency.current:.0f} МГц")

        return "\n".join(result)

    except Exception as error:
        return f"Ошибка CPU: {error}"


def describe_ram():
    try:
        ram = psutil.virtual_memory()

        return "\n".join([
            "Оперативная память:",
            f"Всего: {format_bytes(ram.total)}",
            f"Используется: {format_bytes(ram.used)}",
            f"Доступно: {format_bytes(ram.available)}",
            f"Загрузка: {ram.percent}%"
        ])

    except Exception as error:
        return f"Ошибка RAM: {error}"


def describe_gpu():
    try:
        if platform.system() != "Windows":
            return "Информация о GPU доступна только в Windows."

        command = [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM | ConvertTo-Json -Compress"
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )

        if result.returncode != 0 or not result.stdout.strip():
            return "Не удалось получить информацию о видеокарте."

        adapters = json.loads(result.stdout)

        if isinstance(adapters, dict):
            adapters = [adapters]

        lines = ["Видеокарты:"]

        for gpu in adapters:
            lines.append(f"Название: {gpu.get('Name', 'Неизвестно')}")

            memory = gpu.get("AdapterRAM")

            if isinstance(memory, (int, float)) and memory > 0:
                lines.append(f"Видеопамять: {format_bytes(memory)}")

        return "\n".join(lines)

    except Exception as error:
        return f"Ошибка GPU: {error}"


def describe_temperatures():
    try:
        if not hasattr(psutil, "sensors_temperatures"):
            return "Датчики температуры недоступны."

        temperatures = psutil.sensors_temperatures()

        if not temperatures:
            return "Датчики температуры недоступны."

        lines = ["Температуры:"]

        for sensor, entries in temperatures.items():
            for entry in entries:
                if entry.current is not None:
                    label = entry.label or sensor
                    lines.append(f"{label}: {entry.current} C")

        return "\n".join(lines)

    except Exception as error:
        return f"Ошибка температуры: {error}"


def describe_disks():
    try:
        lines = ["Диски:"]

        for partition in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(partition.mountpoint)

                lines.append(
                    f"\nДиск: {partition.mountpoint}\n"
                    f"Всего: {format_bytes(usage.total)}\n"
                    f"Занято: {format_bytes(usage.used)}\n"
                    f"Свободно: {format_bytes(usage.free)}\n"
                    f"Загрузка: {usage.percent}%"
                )

            except (PermissionError, OSError):
                continue

        return "\n".join(lines)

    except Exception as error:
        return f"Ошибка дисков: {error}"


def get_system_info(metric="summary"):
    metric = (metric or "summary").lower().strip()

    functions = {
        "cpu": describe_cpu,
        "ram": describe_ram,
        "gpu": describe_gpu,
        "temperature": describe_temperatures,
        "cpu_temp": describe_temperatures,
        "gpu_temp": describe_temperatures,
        "disk": describe_disks
    }

    if metric in functions:
        return functions[metric]()

    if metric == "summary":
        return "\n\n".join([
            describe_cpu(),
            describe_ram(),
            describe_gpu(),
            describe_disks()
        ])

    return f"Неизвестный параметр: {metric}"


def collect_stats():
    try:
        ram = psutil.virtual_memory()

        return {
            "cpu": psutil.cpu_percent(interval=None),
            "ram": ram.percent,
            "ram_used": ram.used,
            "ram_total": ram.total
        }

    except Exception:
        return {
            "cpu": 0,
            "ram": 0,
            "ram_used": 0,
            "ram_total": 0
        }
