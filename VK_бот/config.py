"""Общие настройки: загрузка токена сообщества из окружения / .env."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ENV_FILES = (BASE_DIR / ".env", BASE_DIR.parent / ".env")


def load_env_file() -> None:
    """Загружает .env без сторонних зависимостей.

    Ищет файл рядом с кодом и в родительской папке (VK_бот/.env).
    Уже заданные переменные окружения не перезаписываются.
    """
    for env_path in ENV_FILES:
        if not env_path.is_file():
            continue
        try:
            content = env_path.read_text(encoding="utf-8-sig")
        except OSError:
            continue

        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            if key.startswith("export "):
                key = key[len("export ") :].strip()
            if key:
                os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def get_token() -> str:
    load_env_file()
    return (
        os.getenv("VK_TOKEN")
        or os.getenv("VK_BOT_TOKEN")
        or os.getenv("TOKEN")
        or ""
    ).strip()
