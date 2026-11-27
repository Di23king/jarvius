import re
import html
import unicodedata


def normalize_text(text):
    if not isinstance(text, str):
        return ""

    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\ufeff", "")
    text = text.replace("\u200b", "")
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def clean_recognized_text(text):
    text = normalize_text(text)
    text = text.replace("С‘", "Рµ")
    text = re.sub(r"[^\w\s.,!?;:\-+%#@/]", "", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def remove_markdown(text):
    text = normalize_text(text)
    text = text.replace('`', ' ')
    text = text.replace('', '')
    for marker in ('**', '__', '~~', '*', '_'):
        text = text.replace(marker, '')
    text = text.replace('#', '')
    text = text.replace('>', '')
    text = text.replace('|', ' ')
    return text.strip()

def clean_for_speech(text):
    text = normalize_text(text)
    text = remove_markdown(text)

    text = html.unescape(text)
    text = re.sub(r"https?://\S+", "СЃСЃС‹Р»РєР°", text)
    text = re.sub(r"www\.\S+", "СЃСЃС‹Р»РєР°", text)
    text = re.sub(r"\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b", "Р°РґСЂРµСЃ СЌР»РµРєС‚СЂРѕРЅРЅРѕР№ РїРѕС‡С‚С‹", text)

    text = re.sub(r"[#*_`~|<>{}\[\]]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def limit_text(text, max_length=4000):
    text = normalize_text(text)

    if len(text) <= max_length:
        return text

    shortened = text[:max_length].rsplit(" ", 1)[0]

    return shortened.rstrip(".,;:!? ") + "..."


def split_sentences(text):
    text = normalize_text(text)

    if not text:
        return []

    parts = re.split(r"(?<=[.!?])\s+", text)

    return [part.strip() for part in parts if part.strip()]


def prepare_ai_input(text, max_length=4000):
    text = clean_recognized_text(text)
    return limit_text(text, max_length)


def prepare_ai_response(text, max_length=4000):
    text = normalize_text(text)
    text = remove_markdown(text)

    return limit_text(text, max_length)


def prepare_voice_response(text, max_length=2000):
    text = clean_for_speech(text)

    return limit_text(text, max_length)


def is_empty_text(text):
    return not normalize_text(text)
