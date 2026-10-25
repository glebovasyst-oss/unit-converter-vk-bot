"""VK-бот «Калькулятор единиц измерения» для сообщества.

Запуск:
    venv\\Scripts\\python.exe main.py

Токен сообщества берётся из переменной окружения VK_TOKEN
или из файла .env (ищется рядом с main.py и в родительской папке).
"""

from __future__ import annotations

import asyncio
import logging
import math
from logging.handlers import RotatingFileHandler

from vkbottle import Keyboard, KeyboardButtonColor, Text
from vkbottle.bot import Bot, Message
from vkbottle.bot import rules as r
from vkbottle.dispatch.rules import ABCRule

from config import BASE_DIR, get_token

LOG_FILE = BASE_DIR / "bot.log"

logger = logging.getLogger(__name__)


# ===================== Настройки =====================


def setup_logging() -> None:
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    # Чтобы эмодзи и кириллица не роняли логи в консоли Windows.
    stream = getattr(stream_handler, "stream", None)
    if stream is not None and hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logging.basicConfig(
        level=logging.INFO,
        handlers=[stream_handler, file_handler],
        force=True,
    )
    logging.getLogger("vkbottle").setLevel(logging.INFO)


# ===================== Единицы измерения =====================

# Множители к базовой единице системы.
CONVERSIONS: dict[str, dict[str, float]] = {
    "length": {
        "km": 1000.0,
        "m": 1.0,
        "cm": 0.01,
        "mm": 0.001,
    },
    "area": {
        "km2": 1_000_000.0,
        "m2": 1.0,
        "cm2": 0.0001,
        "ha": 10_000.0,
        "a": 100.0,
    },
    "volume": {
        "m3": 1.0,
        "l": 0.001,
        "ml": 0.000001,
        "cm3": 0.000001,
        "dm3": 0.001,
    },
}

UNIT_NAMES: dict[str, str] = {
    "km": "км",
    "m": "м",
    "cm": "см",
    "mm": "мм",
    "km2": "км²",
    "m2": "м²",
    "cm2": "см²",
    "ha": "га",
    "a": "а",
    "m3": "м³",
    "l": "л",
    "ml": "мл",
    "cm3": "см³",
    "dm3": "дм³",
}

SYSTEM_TITLES: dict[str, str] = {
    "length": "📏 Длина",
    "area": "📐 Площадь",
    "volume": "📦 Объём",
}

SYSTEM_DESCRIPTIONS: dict[str, str] = {
    "length": "км, м, см, мм",
    "area": "км², м², см², га, а",
    "volume": "м³, л, мл, см³, дм³",
}

START_TEXTS = [
    "начать",
    "start",
    "/start",
    "старт",
    "меню",
    "menu",
    "/menu",
]

HELP_TEXTS = [
    "помощь",
    "help",
    "/help",
    "инфо",
    "/info",
]


# ===================== Логика =====================


def convert(value: float, from_unit: str, to_unit: str, system: str) -> float:
    """Переводит value из from_unit в to_unit в заданной системе."""
    multipliers = CONVERSIONS[system]
    return value * multipliers[from_unit] / multipliers[to_unit]


def format_number(value: float) -> str:
    """Короткое человекочитаемое представление числа."""
    if not math.isfinite(value):
        return "—"
    if value == 0:
        return "0"

    abs_value = abs(value)
    if 1e-9 <= abs_value < 1e12:
        text = f"{value:.10f}".rstrip("0").rstrip(".")
        return text or "0"
    return f"{value:.6g}"


def parse_number(text: str | None) -> float | None:
    """Разбирает число, в том числе «5,5», «1 000», «−3»."""
    if not text:
        return None

    cleaned = (
        text.strip()
        .replace("\u00a0", "")
        .replace("\u202f", "")
        .replace(" ", "")
        .replace(",", ".")
        .replace("−", "-")
    )
    if not cleaned:
        return None

    try:
        value = float(cleaned)
    except (TypeError, ValueError):
        return None

    return value if math.isfinite(value) else None


# ===================== Клавиатуры =====================


def get_main_keyboard() -> Keyboard:
    """Главная клавиатура с режимами."""
    kb = Keyboard(one_time=False)
    kb.add(
        Text(label="📏 Длина", payload={"cmd": "length"}),
        color=KeyboardButtonColor.POSITIVE,
    )
    kb.add(
        Text(label="📐 Площадь", payload={"cmd": "area"}),
        color=KeyboardButtonColor.POSITIVE,
    )
    kb.add(
        Text(label="📦 Объём", payload={"cmd": "volume"}),
        color=KeyboardButtonColor.POSITIVE,
    )
    kb.row()
    kb.add(Text(label="ℹ️ Помощь", payload={"cmd": "help"}))
    return kb


def get_convert_keyboard(system: str) -> Keyboard:
    """Клавиатура с единицами выбранной системы."""
    kb = Keyboard(one_time=False)

    units = list(CONVERSIONS[system])
    for index, unit in enumerate(units, start=1):
        # ВАЖНО: Keyboard.add в vkbottle 4.11 принимает только одну кнопку,
        # поэтому кнопки добавляются по одной (в старом коде был *row).
        kb.add(
            Text(label=UNIT_NAMES[unit], payload={"unit": unit}),
            color=KeyboardButtonColor.SECONDARY,
        )
        if index % 3 == 0:
            kb.row()

    if len(units) % 3:
        kb.row()

    kb.add(
        Text(label="🔙 Назад", payload={"cmd": "back"}),
        color=KeyboardButtonColor.NEGATIVE,
    )
    return kb


# ===================== Состояния пользователей =====================


class UserState:
    def __init__(self) -> None:
        self.system: str | None = None
        self.from_unit: str | None = None
        self.waiting_for_value: bool = False

    def reset(self) -> None:
        self.system = None
        self.from_unit = None
        self.waiting_for_value = False


states: dict[int, UserState] = {}


def get_state(user_id: int) -> UserState:
    if user_id not in states:
        states[user_id] = UserState()
    return states[user_id]


# ===================== Правила =====================


class UnitPayloadRule(ABCRule[Message]):
    """Срабатывает на кнопку единицы измерения: {"unit": "<код>"}.

    Штатный PayloadRule сравнивает payload целиком (точное совпадение),
    поэтому {"unit": str} у него никогда не совпадает с {"unit": "km"}.
    """

    async def check(self, event: Message) -> bool:
        payload = event.get_payload_json()
        return isinstance(payload, dict) and isinstance(payload.get("unit"), str)


# ===================== Бот =====================

TOKEN = get_token()
bot = Bot(token=TOKEN)


@bot.error_handler.register_error_handler(Exception)
async def on_error(error: Exception) -> None:
    logger.exception("Необработанная ошибка: %s", error)


@bot.on.message(r.PayloadContainsRule({"command": "start"}))
async def cmd_start_button(message: Message) -> None:
    """Кнопка VK «Начать общение» в меню сообщества."""
    await _start(message)


@bot.on.message(r.TextRule(START_TEXTS, ignore_case=True))
async def cmd_start_text(message: Message) -> None:
    await _start(message)


@bot.on.message(r.PayloadContainsRule({"cmd": "help"}))
async def cmd_help_button(message: Message) -> None:
    await _help(message)


@bot.on.message(r.TextRule(HELP_TEXTS, ignore_case=True))
async def cmd_help_text(message: Message) -> None:
    await _help(message)


async def _help(message: Message) -> None:
    await message.answer(
        "ℹ️ Как пользоваться калькулятором:\n\n"
        "1. Выберите систему: длина, площадь или объём.\n"
        "2. Нажмите кнопку с исходной единицей.\n"
        "3. Отправьте число (например: 5.5 или 100).\n\n"
        "Можно вводить несколько чисел подряд — "
        "бот каждый раз пересчитает их во все единицы системы.",
        keyboard=get_main_keyboard(),
    )


def systems_menu() -> str:
    lines = [f"{SYSTEM_TITLES[s]} — {SYSTEM_DESCRIPTIONS[s]}" for s in CONVERSIONS]
    return "Выберите систему:\n\n" + "\n".join(lines)


async def _start(message: Message) -> None:
    get_state(message.from_id).reset()

    await message.answer(
        "Привет! Я калькулятор единиц измерения.\n" + systems_menu(),
        keyboard=get_main_keyboard(),
    )


async def _select_system(message: Message, system: str) -> None:
    state = get_state(message.from_id)
    state.reset()
    state.system = system

    await message.answer(
        f"{SYSTEM_TITLES[system]}.\nВыберите исходную единицу:",
        keyboard=get_convert_keyboard(system),
    )


@bot.on.message(r.PayloadContainsRule({"cmd": "length"}))
async def cmd_length(message: Message) -> None:
    await _select_system(message, "length")


@bot.on.message(r.PayloadContainsRule({"cmd": "area"}))
async def cmd_area(message: Message) -> None:
    await _select_system(message, "area")


@bot.on.message(r.PayloadContainsRule({"cmd": "volume"}))
async def cmd_volume(message: Message) -> None:
    await _select_system(message, "volume")


@bot.on.message(UnitPayloadRule())
async def cmd_unit(message: Message) -> None:
    payload = message.get_payload_json()
    unit = payload.get("unit") if isinstance(payload, dict) else None

    state = get_state(message.from_id)
    if state.system is None:
        await message.answer(
            "Сначала выберите систему: 📏 Длина, 📐 Площадь или 📦 Объём.",
            keyboard=get_main_keyboard(),
        )
        return

    if unit not in CONVERSIONS[state.system]:
        # Например, старая кнопка от другой системы или самодельный payload.
        await message.answer(
            "Эта единица не относится к выбранной системе. "
            "Выберите единицу на клавиатуре ниже.",
            keyboard=get_convert_keyboard(state.system),
        )
        return

    state.from_unit = unit
    state.waiting_for_value = True

    await message.answer(
        f"Введите число в {UNIT_NAMES[unit]}:\n"
        "(например: 5.5 или 100)"
    )


@bot.on.message(r.PayloadContainsRule({"cmd": "back"}))
async def cmd_back(message: Message) -> None:
    get_state(message.from_id).reset()
    await message.answer(
        systems_menu(),
        keyboard=get_main_keyboard(),
    )


@bot.on.message()
async def cmd_text(message: Message) -> None:
    text = (message.text or "").strip()

    # Текстовые команды без payload (на случай, если кнопка недоступна).
    normalized = text.lower()
    if normalized in START_TEXTS:
        await _start(message)
        return
    if normalized in HELP_TEXTS:
        await _help(message)
        return

    state = get_state(message.from_id)

    if not (state.waiting_for_value and state.from_unit and state.system):
        logger.info(
            "Сообщение вне сценария: from_id=%s text=%r payload=%r",
            message.from_id,
            message.text,
            message.payload,
        )
        await message.answer(
            "Не понял сообщение. Выберите систему на клавиатуре "
            "или отправьте «начать».",
            keyboard=get_main_keyboard(),
        )
        return

    value = parse_number(text)
    if value is None:
        await message.answer(
            "❌ Не удалось распознать число.\n"
            "Введите число (например: 5.5 или 100)"
        )
        return

    system = state.system
    from_unit = state.from_unit

    results: list[str] = []
    for unit in CONVERSIONS[system]:
        if unit == from_unit:
            continue
        converted = convert(value, from_unit, unit, system)
        if not math.isfinite(converted):
            await message.answer(
                "❌ Слишком большое число для пересчёта. "
                "Введите число поменьше."
            )
            return
        results.append(f"  {UNIT_NAMES[unit]}: {format_number(converted)}")

    await message.answer(
        f"✅ {format_number(value)} {UNIT_NAMES[from_unit]} =\n"
        + "\n".join(results)
        + "\n\nМожно ввести ещё одно число "
        "или выбрать другую единицу.",
        keyboard=get_convert_keyboard(system),
    )


# ===================== Запуск =====================


async def main() -> None:
    if not TOKEN:
        logger.critical(
            "Не задан токен сообщества. Добавьте VK_TOKEN=... в файл .env "
            "рядом с main.py (или в переменные окружения)."
        )
        raise SystemExit(1)

    try:
        groups = await bot.api.groups.get_by_id()
        group = groups.groups[0]
        logger.info("Токен сообщества: %s (id=%s)", group.name, group.id)
    except Exception:
        logger.exception(
            "Не удалось получить данные сообщества по токену. "
            "Проверьте, что токен действующий и выдан сообществу."
        )
        raise SystemExit(1) from None

    logger.info("Запуск бота (Long Poll)...")
    await bot.run_polling()


if __name__ == "__main__":
    setup_logging()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен.")
