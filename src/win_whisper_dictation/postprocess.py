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


def postprocess_text(text: str, enable_commands: bool = True) -> str:
    value = text.strip()
    if not value:
        return value

    if enable_commands:
        value = _replace_phrases(value, COMMAND_REPLACEMENTS)
        value = _replace_phrases(value, TECH_REPLACEMENTS)
        value = _normalize_symbol_spacing(value)

    return re.sub(r"[ \t]{2,}", " ", value).strip()


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
    value = re.sub(r"(?<=\w)\s*\.\s*(?=\w)", ".", value)
    value = re.sub(r"\s*([_/@#=+\\])\s*", r"\1", value)
    value = re.sub(r"(?<=\w)\s*-\s*(?=\w)", "-", value)
    value = re.sub(r":\s*\\", r":\\", value)
    value = re.sub(r"\n[ \t]+", "\n", value)
    return value
