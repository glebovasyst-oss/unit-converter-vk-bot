"""Ручной прослушиватель событий сообщества (для отладки Long Poll).

Запуск:
    venv\\Scripts\\python.exe VK_бот\\diag_poll.py

Скрипт слушает события ~60 секунд и печатает всё, что приходит от VK.
Отправьте сообщение сообществу — здесь должно появиться событие message_new.
"""

from __future__ import annotations

import asyncio
import json
import sys

import aiohttp
from vkbottle.api import API

from config import get_token

WAIT_SECONDS = 25
ITERATIONS = 3


def out(text: str) -> None:
    print(text, flush=True)


async def main() -> int:
    token = get_token()
    if not token:
        out("[FAIL] VK_TOKEN не найден. Добавьте его в VK_бот/.env")
        return 1

    api = API(token)

    try:
        group = (await api.groups.get_by_id()).groups[0]
    except Exception as error:
        out(f"[FAIL] Токен не подошёл: {type(error).__name__}: {error}")
        return 1

    out(f"Сообщество: {group.name} (id={group.id})")
    out("Слушаю события ~60 секунд. Отправьте сообщение сообществу...\n")

    server = await api.groups.get_long_poll_server(group_id=group.id)
    endpoint = (
        f"{server.server}?act=a_check&key={server.key}"
        f"&ts={server.ts}&wait={WAIT_SECONDS}"
    )

    timeout = aiohttp.ClientTimeout(total=WAIT_SECONDS + 10)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        for attempt in range(1, ITERATIONS + 1):
            async with session.get(endpoint) as response:
                data = await response.json()

            if data.get("failed"):
                code = data["failed"]
                out(f"[{attempt}] Long Poll вернул failed={code}, обновляю ключ...")
                server = await api.groups.get_long_poll_server(group_id=group.id)
                endpoint = (
                    f"{server.server}?act=a_check&key={server.key}"
                    f"&ts={server.ts}&wait={WAIT_SECONDS}"
                )
                continue

            ts = data.get("ts", server.ts)
            endpoint = (
                f"{server.server}?act=a_check&key={server.key}"
                f"&ts={ts}&wait={WAIT_SECONDS}"
            )

            updates = data.get("updates", [])
            if not updates:
                out(f"[{attempt}] событий нет (ts={ts})")
                continue

            for update in updates:
                out(f"[{attempt}] СОБЫТИЕ: {update.get('type')}")
                out(json.dumps(update, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        out("Остановлено пользователем.")
