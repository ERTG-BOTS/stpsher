import asyncio
import logging
import re
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from infrastructure.database.models import Employee
from infrastructure.database.repo.STP.requests import MainRequestsRepo
from tgbot.filters.casino import IsCasinoAllowed
from tgbot.filters.role import (
    DutyFilter,
    MultiRoleFilter,
    SpecialistFilter,
)
from tgbot.handlers.user.game.casino import (
    get_bowling_result_multiplier,
    get_darts_result_multiplier,
    get_dice_result_multiplier,
    get_slot_result_multiplier,
)

logger = logging.getLogger(__name__)

group_casino_router = Router()
group_casino_router.message.filter(
    F.chat.type.in_(("group", "supergroup")),
    MultiRoleFilter(SpecialistFilter(), DutyFilter()),
    IsCasinoAllowed(),
)


def parse_amount(text: str) -> Optional[int]:
    """Парсинг суммы из текста команды"""
    # Ищем число в команде, например: /slots 100 или slots@stpsher_bot 100
    match = re.search(r"(?:/|^)(?:slots|dice|darts|bowling)(?:@\w+)?\s+(\d+)", text)
    if match:
        return int(match.group(1))
    return None


async def play_casino_game(
    message: Message,
    user: Employee,
    stp_repo: MainRequestsRepo,
    game_type: str,
    bet_amount: int,
):
    """Общая функция для игры в казино в группе"""
    if not user.is_casino_allowed:
        await message.reply(
            """❌ <b>Доступ к казино закрыт</b>

<i>Если считаешь, что это ошибка - обратись к своему руководителю</i>""",
        )
        return

    # Проверяем баланс пользователя
    user_balance = await stp_repo.transaction.get_user_balance(user.user_id)

    if bet_amount > user_balance:
        await message.reply(
            f"""❌ <b>Недостаточно средств!</b>
            
💰 Баланс: {user_balance} баллов
💸 Ставка: {bet_amount} баллов

Получай достижения @stpsher_bot для заработка баллов!""",
        )
        return

    # Минимальная ставка
    if bet_amount < 10:
        await message.reply(
            """❌ <b>Минимальная ставка - 10 баллов!</b>
            
Попробуй еще раз с большей ставкой""",
        )
        return

    # Настройки для разных игр
    game_config = {
        "dice": {
            "loading_text": "🎲 <b>Кидаем кости...</b>",
            "emoji": "🎲",
            "multiplier_func": get_dice_result_multiplier,
            "game_name": "костях",
        },
        "darts": {
            "loading_text": "🎯 <b>Бросаем дартс...</b>",
            "emoji": "🎯",
            "multiplier_func": get_darts_result_multiplier,
            "game_name": "дартсе",
        },
        "bowling": {
            "loading_text": "🎳 <b>Катим шар...</b>",
            "emoji": "🎳",
            "multiplier_func": get_bowling_result_multiplier,
            "game_name": "боулинге",
        },
        "slots": {
            "loading_text": "🎰 <b>Крутим барабан...</b>",
            "emoji": "🎰",
            "multiplier_func": get_slot_result_multiplier,
            "game_name": "слотах",
        },
    }

    config = game_config.get(game_type, game_config["slots"])

    # Информируем о начале игры
    loading_msg = await message.reply(
        f"""{config["loading_text"]}
        
👤 Игрок: {user.fullname}
💰 Ставка: {bet_amount} баллов
⏰ Ждем результат...""",
    )

    # Отправляем анимированную игру
    game_result = await message.answer_dice(emoji=config["emoji"])
    game_value = game_result.dice.value

    # Ждем анимацию
    if game_type == "dice":
        await asyncio.sleep(3)
    else:
        await asyncio.sleep(2)

    # Определяем результат
    result_text, multiplier = config["multiplier_func"](game_value)
    game_name = config["game_name"]

    if multiplier > 0:
        # Выигрыш
        winnings = int(bet_amount * multiplier)

        # Записываем транзакцию выигрыша
        transaction, new_balance = await stp_repo.transaction.add_transaction(
            user_id=user.user_id,
            transaction_type="earn",
            source_type="casino",
            amount=winnings - bet_amount,
            comment=f"Выигрыш в {game_name} (группа): {result_text} (x{multiplier})",
        )

        final_result = f"""🎉 <b>Победа!</b> 🎉

👤 <b>{user.fullname}</b>
{result_text}

🔥 Выигрыш: {bet_amount} x{multiplier} = {winnings} баллов!
✨ Баланс: {user_balance} → {new_balance} баллов"""

        logger.info(
            f"[Казино-Группа] {user.fullname} выиграл {winnings} баллов в {game_name} ({result_text})"
        )

    else:
        # Проигрыш
        # Списываем ставку
        transaction, new_balance = await stp_repo.transaction.add_transaction(
            user_id=user.user_id,
            transaction_type="spend",
            source_type="casino",
            amount=bet_amount,
            comment=f"Проигрыш в {game_name} (группа): {result_text}",
        )

        final_result = f"""💔 <b>Проигрыш</b>

👤 <b>{user.fullname}</b>
{result_text}

💸 Потрачено: -{bet_amount} баллов
✨ Баланс: {user_balance} → {new_balance} баллов

<i>Попробуй еще раз - удача рядом!</i>"""

        logger.info(
            f"[Казино-Группа] {user.fullname} проиграл {bet_amount} баллов в {game_name} ({result_text})"
        )

    # Удаляем сообщение загрузки и показываем финальный результат
    await loading_msg.delete()
    await message.reply(final_result)


@group_casino_router.message(Command("slots"))
async def slots_command(message: Message, user: Employee, stp_repo: MainRequestsRepo):
    """Команда /slots для игры в слоты в группе"""

    # Парсим сумму из команды
    bet_amount = parse_amount(message.text)

    if bet_amount is None:
        await message.reply(
            """🎰 <b>Игра в слоты</b>

<b>Использование:</b> <code>/slots [сумма]</code>

<b>Примеры:</b>
• <code>/slots 50</code> - поставить 50 баллов
• <code>/slots 100</code> - поставить 100 баллов

<b>💎 Таблица наград:</b>
🎰 Джекпот (777) → x5.0
🔥 Три в ряд → x3.5  
✨ Две семерки → x2.5

<b>Минимальная ставка:</b> 10 баллов""",
        )
        return

    await play_casino_game(message, user, stp_repo, "slots", bet_amount)


@group_casino_router.message(Command("dice"))
async def dice_command(message: Message, user: Employee, stp_repo: MainRequestsRepo):
    """Команда /dice для игры в кости в группе"""

    # Парсим сумму из команды
    bet_amount = parse_amount(message.text)

    if bet_amount is None:
        await message.reply(
            """🎲 <b>Игра в кости</b>

<b>Использование:</b> <code>/dice [сумма]</code>

<b>Примеры:</b>
• <code>/dice 50</code> - поставить 50 баллов
• <code>/dice 100</code> - поставить 100 баллов

<b>💎 Таблица наград:</b>
· Выпало 6 → 2x
· Выпало 5 → 1.5x
· Выпало 4 → 0.75x (утешительный приз)

<b>Минимальная ставка:</b> 10 баллов""",
        )
        return

    await play_casino_game(message, user, stp_repo, "dice", bet_amount)


@group_casino_router.message(Command("darts"))
async def darts_command(message: Message, user: Employee, stp_repo: MainRequestsRepo):
    """Команда /darts для игры в дартс в группе"""

    # Парсим сумму из команды
    bet_amount = parse_amount(message.text)

    if bet_amount is None:
        await message.reply(
            """🎯 <b>Игра в дартс</b>

<b>Использование:</b> <code>/darts [сумма]</code>

<b>Примеры:</b>
• <code>/darts 50</code> - поставить 50 баллов
• <code>/darts 100</code> - поставить 100 баллов

<b>💎 Таблица наград:</b>
· В яблочко → 2x
· 1 кольцо от центра → 1.5x
· 2 кольцо от центра → 0.75x (утешительный приз)

<b>Минимальная ставка:</b> 10 баллов""",
        )
        return

    await play_casino_game(message, user, stp_repo, "darts", bet_amount)


@group_casino_router.message(Command("bowling"))
async def bowling_command(message: Message, user: Employee, stp_repo: MainRequestsRepo):
    """Команда /bowling для игры в боулинг в группе"""

    # Парсим сумму из команды
    bet_amount = parse_amount(message.text)

    if bet_amount is None:
        await message.reply(
            """🎳 <b>Игра в боулинг</b>

<b>Использование:</b> <code>/bowling [сумма]</code>

<b>Примеры:</b>
• <code>/bowling 50</code> - поставить 50 баллов
• <code>/bowling 100</code> - поставить 100 баллов

<b>💎 Таблица наград:</b>
· Страйк → 2x
· 5 кеглей → 1.5x
· 4 кегли → 0.75x (утешительный приз)

<b>Минимальная ставка:</b> 10 баллов""",
        )
        return

    await play_casino_game(message, user, stp_repo, "bowling", bet_amount)


__all__ = ["group_casino_router"]
