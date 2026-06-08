from __future__ import annotations

import re


COMMAND_REPLACEMENTS = {
    "новая строка": "\n",
    "new line": "\n",
    "абзац": "\n\n",
    "new paragraph": "\n\n",
    "точка с запятой": ";",
    "semicolon": ";",
    "двоеточие": ":",
    "colon": ":",
    "запятая": ",",
    "comma": ",",
    "точка": ".",
    "period": ".",
    "dot": ".",
    "вопросительный знак": "?",
    "question mark": "?",
    "восклицательный знак": "!",
    "exclamation mark": "!",
    "открывающая скобка": "(",
    "закрывающая скобка": ")",
    "open parenthesis": "(",
    "close parenthesis": ")",
    "левая скобка": "(",
    "правая скобка": ")",
    "нижнее подчёркивание": "_",
    "нижнее подчеркивание": "_",
    "андерскор": "_",
    "underscore": "_",
    "слэш": "/",
    "slash": "/",
    "прямой слэш": "/",
    "forward slash": "/",
    "обратный слэш": "\\",
    "backslash": "\\",
    "дефис": "-",
    "hyphen": "-",
    "dash": "-",
    "минус": "-",
    "плюс": "+",
    "plus": "+",
    "равно": "=",
    "equals": "=",
    "собака": "@",
    "at sign": "@",
    "решётка": "#",
    "решетка": "#",
    "hash": "#",
    "двойная кавычка": '"',
    "double quote": '"',
    "одинарная кавычка": "'",
    "single quote": "'",
}

TECH_REPLACEMENTS = {
    "джейсон": "json",
    "питон": "python",
    "пай": "py",
    "пи вай": "py",
    "энви": "env",
    "икс эм эл": "xml",
    "эйч ти эм эл": "html",
    "си эс эс": "css",
    "джей эс": "js",
    "тайп скрипт": "typescript",
    "тс": "ts",
}

FILLER_WORDS = {
    "um",
    "uh",
    "ah",
    "erm",
    "\u044d\u043c",
    "\u044d\u044d",
}

LIST_MARKERS = {
    "one": 1,
    "first": 1,
    "1": 1,
    "two": 2,
    "second": 2,
    "2": 2,
    "three": 3,
    "third": 3,
    "3": 3,
    "four": 4,
    "fourth": 4,
    "4": 4,
    "five": 5,
    "fifth": 5,
    "5": 5,
    "six": 6,
    "sixth": 6,
    "6": 6,
    "seven": 7,
    "seventh": 7,
    "7": 7,
    "eight": 8,
    "eighth": 8,
    "8": 8,
    "nine": 9,
    "ninth": 9,
    "9": 9,
    "ten": 10,
    "tenth": 10,
    "10": 10,
    "\u043f\u0435\u0440\u0432\u043e\u0435": 1,
    "\u043f\u0435\u0440\u0432\u044b\u0439": 1,
    "\u0440\u0430\u0437": 1,
    "\u0432\u0442\u043e\u0440\u043e\u0435": 2,
    "\u0432\u0442\u043e\u0440\u043e\u0439": 2,
    "\u0434\u0432\u0430": 2,
    "\u0442\u0440\u0435\u0442\u044c\u0435": 3,
    "\u0442\u0440\u0435\u0442\u0438\u0439": 3,
    "\u0442\u0440\u0438": 3,
    "\u0447\u0435\u0442\u0432\u0435\u0440\u0442\u043e\u0435": 4,
    "\u0447\u0435\u0442\u0432\u0435\u0440\u0442\u044b\u0439": 4,
    "\u0447\u0435\u0442\u044b\u0440\u0435": 4,
    "\u043f\u044f\u0442\u043e\u0435": 5,
    "\u043f\u044f\u0442\u044b\u0439": 5,
    "\u043f\u044f\u0442\u044c": 5,
}


def postprocess_text(
    text: str,
    enable_commands: bool = True,
    auto_cleanup: bool = False,
    format_lists: bool = False,
) -> str:
    value = text.strip()
    if not value:
        return value

    if enable_commands:
        value = _replace_phrases(value, COMMAND_REPLACEMENTS)
        value = _replace_phrases(value, TECH_REPLACEMENTS)
        value = _normalize_symbol_spacing(value)

    if auto_cleanup:
        value = cleanup_text(value)
    if format_lists:
        value = format_numbered_list(value)

    return _final_spacing(value)


def cleanup_text(text: str) -> str:
    value = text.strip()
    if not value:
        return value

    value = _remove_fillers(value)
    value = _apply_self_corrections(value)
    value = _collapse_repeated_words(value)
    value = _final_spacing(value)
    if not _looks_like_code_or_path(value):
        value = _capitalize_first(value)
    value = _add_safe_terminal_punctuation(value)
    return value


def format_numbered_list(text: str) -> str:
    value = _final_spacing(text)
    matches = list(_list_marker_matches(value))
    if len(matches) < 2:
        return text
    if matches[0].start() > 2:
        return text
    marker_numbers = [LIST_MARKERS[_normalize_marker(match.group(1))] for match in matches]
    if marker_numbers[0] != 1 or marker_numbers[1] != 2:
        return text
    if _normalize_marker(matches[0].group(1)) in {"one", "1", "\u0440\u0430\u0437"} and len(matches) < 3:
        return text
    if any(later <= earlier for earlier, later in zip(marker_numbers, marker_numbers[1:])):
        return text

    items: list[str] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(value)
        item = value[start:end].strip(" \t\n\r,.;:-")
        if not item:
            return text
        items.append(_capitalize_first(_final_spacing(item)))

    if len(items) < 2:
        return text
    return "\n".join(f"{index}. {item}" for index, item in enumerate(items, start=1))


def _replace_phrases(text: str, replacements: dict[str, str]) -> str:
    value = text
    for phrase, replacement in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        pattern = re.compile(rf"(?<!\w){re.escape(phrase)}(?!\w)", re.IGNORECASE)
        value = pattern.sub(lambda _match, replacement=replacement: replacement, value)
    return value


def _normalize_symbol_spacing(text: str) -> str:
    value = text
    value = re.sub(r"\s+([,.:;!?%)\]}])", r"\1", value)
    value = re.sub(r"([({\[])\s+", r"\1", value)
    value = re.sub(r"(?<=[A-Za-z\u0400-\u04ff])\s*\.\s*(?=[A-Za-z\u0400-\u04ff])", ".", value)
    value = re.sub(r"\s*([_/@#=+\\])\s*", r"\1", value)
    value = re.sub(r"(?<=\w)\s*-\s*(?=\w)", "-", value)
    value = re.sub(r":\s*\\", r":\\", value)
    value = re.sub(r"\n[ \t]+", "\n", value)
    return value


def _remove_fillers(text: str) -> str:
    value = text
    for word in sorted(FILLER_WORDS, key=len, reverse=True):
        value = re.sub(rf"(?<!\w){re.escape(word)}(?!\w)[, ]*", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"(^|[.!?]\s+)\u043d\u0443[, ]+", r"\1", value, flags=re.IGNORECASE)
    value = re.sub(r"\b\u043d\u0443\s+\u043d\u0443\b", "\u043d\u0443", value, flags=re.IGNORECASE)
    return value


def _apply_self_corrections(text: str) -> str:
    value = text
    value = re.sub(
        r"\b(at|in|on|to|for|from|with)\s+\S+\s+(?:no|not|sorry)\s+\1\s+",
        lambda match: f"{match.group(1)} ",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"\b(at|in|on|to|for|from|with)\s+\S+\s+(?:no|not|sorry)\s+",
        lambda match: f"{match.group(1)} ",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"(?<!\w)(\u0432|\u0432\u043e|\u043d\u0430|\u043a|\u043a\u043e|\u0441|\u0441\u043e|\u0443|\u0434\u043b\u044f|\u043e\u0442|\u0434\u043e)\s+\S+\s+(?:\u043d\u0435\u0442|\u043e\u0439)\s+\1\s+",
        lambda match: f"{match.group(1)} ",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"(?<!\w)(\u0432|\u0432\u043e|\u043d\u0430|\u043a|\u043a\u043e|\u0441|\u0441\u043e|\u0443|\u0434\u043b\u044f|\u043e\u0442|\u0434\u043e)\s+\S+\s+(?:\u043d\u0435\u0442|\u043e\u0439)\s+",
        lambda match: f"{match.group(1)} ",
        value,
        flags=re.IGNORECASE,
    )
    return value


def _collapse_repeated_words(text: str) -> str:
    return re.sub(r"\b([\w\u0400-\u04ff]+)(\s+\1\b)+", r"\1", text, flags=re.IGNORECASE)


def _capitalize_first(text: str) -> str:
    for index, char in enumerate(text):
        if char.isalpha():
            return text[:index] + char.upper() + text[index + 1 :]
    return text


def _add_safe_terminal_punctuation(text: str) -> str:
    value = text.strip()
    if not value or "\n" in value or re.search(r"[.!?:;]$", value):
        return value
    if _looks_like_code_or_path(value):
        return value
    if len(re.findall(r"[\w\u0400-\u04ff]+", value)) < 3:
        return value
    return value + "."


def _looks_like_code_or_path(text: str) -> bool:
    return bool(re.search(r"[\\/@#_=]|\w+\.\w+", text))


def _list_marker_matches(text: str):
    marker_pattern = "|".join(re.escape(marker) for marker in sorted(LIST_MARKERS, key=len, reverse=True))
    return re.finditer(rf"(?<!\w)({marker_pattern})(?:[.)])?(?!\w)", text, flags=re.IGNORECASE)


def _normalize_marker(marker: str) -> str:
    return marker.rstrip(".)").casefold()


def _final_spacing(text: str) -> str:
    value = re.sub(r"[ \t]{2,}", " ", text)
    value = re.sub(r"[ \t]*\n[ \t]*", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    value = _normalize_symbol_spacing(value)
    return value.strip()
