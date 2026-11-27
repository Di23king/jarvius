# -*- coding: utf-8 -*-

import re
import difflib


NAME_PREFIX = "Имя пользователя — "

REMEMBER_RE = re.compile(
    r"^\s*(?:(?:джарвис|джервис|жарвис)[\s,]+)?"
    r"(?:пожалуйста[\s,]+)?"
    r"запомни(?![а-яё])(?:\s+пожалуйста)?[\s,:\-]*(?:что\s+)?(.*)$",
    re.IGNORECASE | re.DOTALL
)

FORGET_RE = re.compile(
    r"^\s*(?:(?:джарвис|джервис|жарвис)[\s,]+)?"
    r"(?:пожалуйста[\s,]+)?"
    r"забудь(?![а-яё])(?:\s+пожалуйста)?[\s,:\-]*(?:что\s+)?(.*)$",
    re.IGNORECASE | re.DOTALL
)

RECALL_PATTERNS = [
    r"\bчто ты (?:еще )?(?:обо мне )?(?:помнишь|знаешь|запомнил)"
    r"(?: обо мне| про меня)?$",
    r"\bчто ты (?:еще )?(?:помнишь|знаешь|запомнил) (?:обо мне|про меня)\b",
    r"\bчто тебе (?:обо мне )?известно(?: обо мне)?$",
    r"^(?:покажи|открой) (?:мою )?память$"
]

NAME_ASK_PATTERN = (
    r"\bкак (?:меня зовут|ты меня зовешь|меня звать)\b"
)

NAME_SET_PATTERN = (
    r"(?:меня зовут|мое имя|зови меня|меня звать)\s+"
    r"([a-zа-яё][a-zа-яё\-]{1,29})\b"
)

NAME_STOPWORDS = {
    "как", "не", "так", "что", "уже", "тоже",
    "же", "просто", "теперь", "ли", "а", "и"
}

FORGET_STOP_WORDS = {
    "что", "это", "эту", "этот", "мне", "меня",
    "мой", "моя", "мое", "мои", "про", "обо",
    "для", "как", "так", "уже", "или", "все",
    "очень"
}

WAKE_WORDS = [
    "джарвис",
    "джервис",
    "жарвис",
    "джарви",
    "джарвиз",
    "джарвес",
    "джарвисс",
    "дарвис",
    "жервис",
    "джарвису"
]


def is_wake_word(word):
    word = (word or "").lower().replace("ё", "е")

    if len(word) < 5:
        return False

    if word in WAKE_WORDS:
        return True

    return any(
        difflib.SequenceMatcher(None, word, wake).ratio() >= 0.78
        for wake in WAKE_WORDS[:3]
    )


def clean_for_match(text):
    text = str(text).lower().replace("ё", "е")
    text = re.sub(r"[^\w\s\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    words = text.split()

    while words and is_wake_word(words[0]):
        words.pop(0)

    return " ".join(words)


def format_name(name):
    return "-".join(
        part.capitalize()
        for part in name.split("-")
    )


def guess_category(text):
    t = clean_for_match(text)

    if re.search(
        r"\b(?:компьютер\w*|пк|видеокарт\w*|процессор\w*|"
        r"ноутбук\w*|озу|оператив\w+|монитор\w*|windows|"
        r"виндовс|gtx|rtx|ryzen|ssd)\b",
        t
    ):
        return "компьютер"

    if re.search(
        r"\b(?:проект\w*|разрабатыва\w+|делаю|пишу|"
        r"программ\w+|jarvis|джарвис)\b",
        t
    ):
        return "проекты"

    if re.search(
        r"\b(?:люблю|любим\w+|нравит\w+|предпочита\w+|"
        r"обожаю|ненавижу|хочу)\b",
        t
    ):
        return "предпочтения"

    if re.search(
        r"\b(?:интересу\w+|увлека\w+|хобби|играю|"
        r"смотрю|слушаю|занимаюсь)\b",
        t
    ):
        return "интересы"

    return "другое"


def fact_stems(text):
    words = re.findall(
        r"[a-zа-яё0-9]+",
        clean_for_match(text)
    )

    return {
        word[:5]
        for word in words
        if len(word) >= 3 and word not in FORGET_STOP_WORDS
    }


def find_facts_to_forget(facts, target):
    target_clean = clean_for_match(target)

    if re.search(r"\bимя\b|меня зовут", target_clean):
        return [
            fact for fact in facts
            if fact.get("key") == "name"
        ]

    stems = fact_stems(target)

    if not stems:
        return []

    scored = []
    best = 0.0

    for fact in facts:
        score = (
            len(stems & fact_stems(fact["text"]))
            / len(stems)
        )

        scored.append((score, fact))
        best = max(best, score)

    if best < 0.6:
        return []

    return [
        fact for score, fact in scored
        if score == best
    ]


def parse_memory_command(text):
    cleaned = clean_for_match(text)

    if not cleaned:
        return None

    match = REMEMBER_RE.match(text)

    if match:
        fact_text = match.group(1).strip(
            " \t\r\n.,;:!?-"
        )

        if not fact_text:
            return {
                "action": "remember",
                "text": ""
            }

        return {
            "action": "remember",
            "text": fact_text
        }

    match = FORGET_RE.match(text)

    if match:
        target = match.group(1).strip(
            " \t\r\n.,;:!?-"
        )

        if not target:
            return {
                "action": "forget",
                "text": ""
            }

        return {
            "action": "forget",
            "text": target
        }

    if any(
        re.search(pattern, cleaned)
        for pattern in RECALL_PATTERNS
    ):
        return {"action": "recall"}

    if re.search(NAME_ASK_PATTERN, cleaned):
        return {"action": "ask_name"}

    if len(cleaned.split()) <= 6:
        match = re.search(NAME_SET_PATTERN, cleaned)

        if match and match.group(1) not in NAME_STOPWORDS:
            return {
                "action": "set_name",
                "name": format_name(match.group(1))
            }

    return None
