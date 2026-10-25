"""Проверка готовности сообщества VK к работе бота.

Запуск:
    venv\\Scripts\\python.exe VK_бот\\diag.py

Проверяет:
  1. что VK_TOKEN найден и действителен;
  2. к какому сообществу он относится;
  3. включён ли Long Poll API и нужные события.
"""

from __future__ import annotations

import asyncio
import sys

from vkbottle.api import API

from config import get_token


def out(text: str) -> None:
    print(text)


async def main() -> int:
    token = get_token()
    if not token:
        out("[FAIL] VK_TOKEN не найден.")
        out("       Добавьте строку VK_TOKEN=... в файл VK_бот/.env")
        return 1

    api = API(token)

    try:
        groups = await api.groups.get_by_id()
    except Exception as error:
        out(f"[FAIL] Токен не подошёл: {type(error).__name__}: {error}")
        out("       Сгенерируйте новый токен в настройках сообщества.")
        return 1

    if not groups.groups:
        out("[FAIL] Токен не относится ни к одному сообществу.")
        out("       Нужен ключ доступа сообщества, а не пользователя.")
        return 1

    group = groups.groups[0]

    out(f"[OK]   Токен действителен. Сообщество: {group.name} (id={group.id})")

    try:
        settings = await api.groups.get_long_poll_settings(group_id=group.id)
    except Exception as error:
        out(f"[FAIL] Не удалось прочитать настройки Long Poll: {type(error).__name__}: {error}")
        return 1

    out(f"[{'OK' if settings.is_enabled else 'FAIL'}]   Long Poll API: "
        f"{'включён' if settings.is_enabled else 'ВЫКЛЮЧЕН'}")

    # В vkbottle 4.11 события лежат в settings.events.
    events = getattr(settings, "events", settings)
    message_new = bool(getattr(events, "message_new", False))
    out(f"[{'OK' if message_new else 'FAIL'}]   Событие «Новые сообщения» "
        f"(message_new): {'включено' if message_new else 'ВЫКЛЮЧЕНО'}")

    # Боту они не обязательны, но полезны при доработке.
    for field, title in (
        ("message_reply", "Ответы на сообщения"),
        ("message_edit", "Изменение сообщений"),
    ):
        enabled = bool(getattr(events, field, False))
        out(f"[i]    Событие «{title}» ({field}): "
            f"{'включено' if enabled else 'выключено'}")

    try:
        server = await api.groups.get_long_poll_server(group_id=group.id)
        out(f"[OK]   Long Poll сервер доступен: {server.server} (ts={server.ts})")
    except Exception as error:
        out(f"[FAIL] Long Poll сервер недоступен: {type(error).__name__}: {error}")
        return 1

    if settings.is_enabled and message_new:
        out("")
        out("Всё готово: можно запускать бота (start_bot.bat).")
        return 0

    out("")
    out("Включите Long Poll API и событие «Новые сообщения»:")
    out("  Управление сообществом -> Сообщения -> Настройки для бота")
    out("  -> Возможности ботов -> Long Poll API.")
    return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    raise SystemExit(asyncio.run(main()))
