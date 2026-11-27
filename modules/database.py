# -*- coding: utf-8 -*-

import re
import sqlite3

from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, Signal

from modules.config import BASE_DIR, MAX_HISTORY_MESSAGES


MEMORY_DIR = BASE_DIR / "memory"

CHAT_DB_FILE = MEMORY_DIR / "chat_history.db"
MEMORY_DB_FILE = MEMORY_DIR / "jarvis_memory.db"

NAME_PREFIX = "Имя пользователя — "

AUTHOR_TO_ROLE = {
    "ВЫ": "user",
    "J.A.R.V.I.S.": "assistant"
}

ROLE_TO_AUTHOR = {
    "user": "ВЫ",
    "assistant": "J.A.R.V.I.S.",
    "system": "СИСТЕМА"
}


CHAT_SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created TEXT NOT NULL,
    FOREIGN KEY (chat_id) REFERENCES chats (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_chat
ON messages (chat_id, id);
"""


MEMORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    key TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL,
    created TEXT NOT NULL,
    updated TEXT NOT NULL
);
"""


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def _py_lower(value):
    if not isinstance(value, str):
        return value

    return value.lower().replace("ё", "е")


class DatabaseWorker(QObject):

    _done = Signal(object, object)
    failed = Signal(str)

    def __init__(self):
        super().__init__()

        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="jarvis-db"
        )

        self._chat = None
        self._mem = None
        self._closed = False

        self._done.connect(self._deliver)

    def _open(self):
        if self._chat is not None:
            return

        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

        chat = sqlite3.connect(
            str(CHAT_DB_FILE),
            check_same_thread=False
        )

        mem = sqlite3.connect(
            str(MEMORY_DB_FILE),
            check_same_thread=False
        )

        chat.execute("PRAGMA foreign_keys = ON")

        chat.create_function(
            "pylower",
            1,
            _py_lower,
            deterministic=True
        )

        chat.executescript(CHAT_SCHEMA)
        mem.executescript(MEMORY_SCHEMA)

        self._chat = chat
        self._mem = mem

    def _deliver(self, callback, result):
        try:
            callback(result)
        except Exception as error:
            print(
                f"[DB] Ошибка обработки результата: {error}"
            )

    def call(self, func, callback=None):

        if self._closed:
            return

        def task():
            try:
                self._open()

                result = func(
                    self._chat,
                    self._mem
                )

            except Exception as error:
                print(f"[DB] Ошибка: {error}")
                self.failed.emit(str(error))
                return

            if callback is not None:
                self._done.emit(callback, result)

        try:
            self._executor.submit(task)
        except RuntimeError:
            pass

    def close(self):
        if self._closed:
            return

        self._closed = True

        def finish():
            for connection in (self._chat, self._mem):
                if connection is not None:
                    try:
                        connection.close()
                    except Exception:
                        pass

            self._chat = None
            self._mem = None

        try:
            self._executor.submit(finish)
        except RuntimeError:
            pass

        self._executor.shutdown(wait=True)


# ==============================
# CHAT DATABASE
# ==============================

def db_create_chat(chat, chat_id, title):
    stamp = now_iso()

    with chat:
        chat.execute(
            "INSERT OR IGNORE INTO chats "
            "(id, title, created, updated) "
            "VALUES (?, ?, ?, ?)",
            (chat_id, title, stamp, stamp)
        )


def db_save_message(chat, chat_id, role, content):
    stamp = now_iso()

    try:
        with chat:
            chat.execute(
                "INSERT INTO messages "
                "(chat_id, role, content, created) "
                "VALUES (?, ?, ?, ?)",
                (chat_id, role, content, stamp)
            )

            chat.execute(
                "UPDATE chats SET updated = ? "
                "WHERE id = ?",
                (stamp, chat_id)
            )

    except sqlite3.IntegrityError:
        pass


def db_list_chats(chat, query):
    query = (query or "").strip()

    if query:
        pattern = (
            "%"
            + _py_lower(query)
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
            + "%"
        )

        rows = chat.execute(
            """
            SELECT c.id, c.title, c.updated
            FROM chats c
            WHERE pylower(c.title) LIKE ? ESCAPE '\\'
               OR EXISTS (
                    SELECT 1
                    FROM messages m
                    WHERE m.chat_id = c.id
                      AND pylower(m.content) LIKE ? ESCAPE '\\'
               )
            ORDER BY c.updated DESC, c.rowid DESC
            """,
            (pattern, pattern)
        ).fetchall()

    else:
        rows = chat.execute(
            "SELECT id, title, updated FROM chats "
            "ORDER BY updated DESC, rowid DESC"
        ).fetchall()

    return [
        {
            "id": row[0],
            "title": row[1],
            "updated": row[2]
        }
        for row in rows
    ]


def db_load_messages(chat, chat_id):
    rows = chat.execute(
        """
        SELECT role, content
        FROM (
            SELECT id, role, content
            FROM messages
            WHERE chat_id = ?
            ORDER BY id DESC
            LIMIT ?
        )
        ORDER BY id
        """,
        (chat_id, MAX_HISTORY_MESSAGES)
    ).fetchall()

    return [
        (row[0], row[1])
        for row in rows
    ]


def db_delete_chat(chat, chat_id):
    with chat:
        chat.execute(
            "DELETE FROM messages WHERE chat_id = ?",
            (chat_id,)
        )

        chat.execute(
            "DELETE FROM chats WHERE id = ?",
            (chat_id,)
        )


# ==============================
# MEMORY DATABASE
# ==============================

def db_load_facts(mem):
    rows = mem.execute(
        "SELECT id, category, key, text FROM facts "
        "ORDER BY created, rowid"
    ).fetchall()

    return [
        {
            "id": row[0],
            "category": row[1],
            "key": row[2],
            "text": row[3]
        }
        for row in rows
    ]


def db_add_fact(mem, fact, stamp):
    with mem:
        mem.execute(
            "INSERT OR REPLACE INTO facts "
            "(id, category, key, text, created, updated) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                fact["id"],
                fact["category"],
                fact.get("key", ""),
                fact["text"],
                stamp,
                stamp
            )
        )


def db_update_fact(mem, fact_id, text, category):
    with mem:
        mem.execute(
            "UPDATE facts "
            "SET text = ?, category = ?, updated = ? "
            "WHERE id = ?",
            (text, category, now_iso(), fact_id)
        )


def db_delete_fact(mem, fact_id):
    with mem:
        mem.execute(
            "DELETE FROM facts WHERE id = ?",
            (fact_id,)
        )


def db_clear_facts(mem):
    with mem:
        mem.execute("DELETE FROM facts")


# ==============================
# STARTUP
# ==============================

def db_startup(chat, mem):
    facts = db_load_facts(mem)

    chats = db_list_chats(chat, "")

    last_id = chats[0]["id"] if chats else None

    messages = (
        db_load_messages(chat, last_id)
        if last_id else []
    )

    return {
        "facts": facts,
        "chats": chats,
        "last_id": last_id,
        "messages": messages
    }


def make_chat_title(text):
    title = re.sub(
        r"\s+",
        " ",
        str(text)
    ).strip()

    if len(title) > 40:
        title = title[:40].rstrip() + "..."

    if not title:
        return "Новый чат"

    return title[0].upper() + title[1:]


def trim_history(history, limit=32):
    system = [
        message
        for message in history[:1]
        if message.get("role") == "system"
    ]

    rest = history[len(system):]

    if len(rest) > limit:
        rest = rest[-limit:]

        while rest and rest[0].get("role") != "user":
            rest = rest[1:]

    return system + rest
