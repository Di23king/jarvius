import psutil
import os


def get_process_list(limit=30):
    try:
        processes = []

        for process in psutil.process_iter(
            ["pid", "name", "cpu_percent", "memory_percent"]
        ):
            try:
                info = process.info

                processes.append({
                    "pid": info["pid"],
                    "name": info["name"] or "Unknown",
                    "cpu": info["cpu_percent"] or 0,
                    "ram": info["memory_percent"] or 0
                })

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        processes.sort(
            key=lambda item: item["ram"],
            reverse=True
        )

        return processes[:max(1, min(int(limit), 100))]

    except Exception as error:
        return f"Ошибка получения процессов: {error}"


def format_process_list(processes):
    if isinstance(processes, str):
        return processes

    if not processes:
        return "Процессы не найдены."

    lines = ["Список процессов:"]

    for process in processes:
        lines.append(
            f"PID: {process['pid']} | "
            f"Имя: {process['name']} | "
            f"CPU: {process['cpu']}% | "
            f"RAM: {process['ram']:.1f}%"
        )

    return "\n".join(lines)


def find_process(query):
    if not query or not query.strip():
        return "Укажи название процесса."

    query = query.lower().strip()
    results = []

    for process in psutil.process_iter(["pid", "name"]):
        try:
            name = process.info["name"] or ""

            if query in name.lower():
                results.append({
                    "pid": process.info["pid"],
                    "name": name
                })

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if not results:
        return "Процесс не найден."

    lines = ["Найденные процессы:"]

    for process in results:
        lines.append(
            f"{process['name']} | PID: {process['pid']}"
        )

    return "\n".join(lines)


def get_process_info(pid):
    try:
        process = psutil.Process(int(pid))

        return {
            "pid": process.pid,
            "name": process.name(),
            "status": process.status(),
            "cpu": process.cpu_percent(interval=0.5),
            "ram": process.memory_percent(),
            "memory": process.memory_info().rss,
            "threads": process.num_threads()
        }

    except psutil.NoSuchProcess:
        return "Процесс не найден."

    except psutil.AccessDenied:
        return "Нет доступа к информации о процессе."

    except (ValueError, TypeError):
        return "Некорректный PID."

    except Exception as error:
        return f"Ошибка: {error}"


def get_top_processes(limit=10):
    try:
        processes = []

        for process in psutil.process_iter(
            ["pid", "name", "memory_percent"]
        ):
            try:
                process.cpu_percent(interval=None)

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        psutil.cpu_percent(interval=0.5)

        for process in psutil.process_iter(
            ["pid", "name", "memory_percent", "cpu_percent"]
        ):
            try:
                info = process.info

                processes.append({
                    "pid": info["pid"],
                    "name": info["name"] or "Unknown",
                    "cpu": info["cpu_percent"] or 0,
                    "ram": info["memory_percent"] or 0
                })

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        processes.sort(
            key=lambda item: item["cpu"],
            reverse=True
        )

        return format_process_list(
            processes[:max(1, min(int(limit), 50))]
        )

    except Exception as error:
        return f"Ошибка: {error}"


def terminate_process(pid):
    try:
        pid = int(pid)

        if pid <= 4 or pid == os.getpid():
            return "Запрещено завершать этот системный процесс."

        process = psutil.Process(pid)

        if process.name().lower() in {
            "system",
            "registry",
            "csrss.exe",
            "wininit.exe",
            "services.exe",
            "smss.exe",
            "lsass.exe"
        }:
            return "Защита: завершение системного процесса запрещено."

        process.terminate()

        try:
            process.wait(timeout=3)
            return f"Процесс {process.name()} успешно завершён."

        except psutil.TimeoutExpired:
            return "Процесс не завершился за 3 секунды. Принудительное завершение не выполнялось."

    except psutil.NoSuchProcess:
        return "Процесс уже не существует."

    except psutil.AccessDenied:
        return "Недостаточно прав для завершения процесса."

    except (ValueError, TypeError):
        return "Некорректный PID."

    except Exception as error:
        return f"Ошибка завершения процесса: {error}"
