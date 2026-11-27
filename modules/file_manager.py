import os
from pathlib import Path


# ==========================================
# НАСТРОЙКИ ПОИСКА
# ==========================================

DEFAULT_LIMIT = 30
MAX_LIMIT = 50

EXCLUDED_DIRECTORIES = {
    "venv",
    "__pycache__",
    "node_modules",
    ".git",
}


# ==========================================
# ДОСТУПНЫЕ ПАПКИ
# ==========================================

def get_search_locations():
    """
    Возвращает доступные папки для поиска.
    """

    home = Path.home()

    return {
        "desktop": [home / "Desktop"],
        "documents": [home / "Documents"],
        "downloads": [home / "Downloads"],
        "all": [
            home / "Desktop",
            home / "Documents",
            home / "Downloads",
        ],
    }


# ==========================================
# ФОРМАТИРОВАНИЕ РЕЗУЛЬТАТОВ
# ==========================================

def format_results(results):
    """
    Преобразует список найденных файлов в текст.
    """

    if not results:
        return "Ничего не найдено."

    output = [
        f"Найдено файлов: {len(results)}"
    ]

    for index, path in enumerate(results, 1):
        output.append(f"{index}. {path}")

    return "\n".join(output)


# ==========================================
# ПОИСК ФАЙЛОВ
# ==========================================

def search_files(query, location="all", extension="", limit=DEFAULT_LIMIT):
    """
    Ищет файлы по названию.

    query     — название или часть названия файла.
    location  — desktop, documents, downloads, all.
    extension — расширение файла.
    limit     — максимальное количество результатов.
    """

    query = (query or "").strip().lower()

    if not query:
        return "Укажи название файла для поиска."

    locations = get_search_locations()

    roots = locations.get(location.lower())

    if roots is None:
        return "Неизвестная папка для поиска."

    extension = (extension or "").lower().strip()

    if extension and not extension.startswith("."):
        extension = "." + extension

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = DEFAULT_LIMIT

    limit = max(1, min(limit, MAX_LIMIT))

    results = []

    for root in roots:

        if not root.exists() or not root.is_dir():
            continue

        def handle_walk_error(error):
            # Недоступные папки пропускаются.
            pass

        for current, dirs, files in os.walk(
            root,
            onerror=handle_walk_error
        ):

            dirs[:] = [
                directory
                for directory in dirs
                if directory.lower() not in EXCLUDED_DIRECTORIES
                and not directory.startswith(".")
            ]

            for filename in files:

                if query not in filename.lower():
                    continue

                if (
                    extension
                    and Path(filename).suffix.lower() != extension
                ):
                    continue

                full_path = Path(current) / filename

                results.append(str(full_path))

                if len(results) >= limit:
                    return format_results(results)

    return format_results(results)