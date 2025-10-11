import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery
from stp_database import Employee
from stp_database.repo.STP.requests import MainRequestsRepo

from tgbot.keyboards.user.game.achievements import (
    AchievementsMenu,
    achievements_paginated_kb,
    to_achievements_kb,
)
from tgbot.keyboards.user.game.main import GameMenu

user_game_achievements_router = Router()
user_game_achievements_router.message.filter(
    F.chat.type == "private",
)
user_game_achievements_router.callback_query.filter(F.message.chat.type == "private")

logger = logging.getLogger(__name__)


@user_game_achievements_router.callback_query(GameMenu.filter(F.menu == "achievements"))
async def user_achievements_cb(
    callback: CallbackQuery, user: Employee, stp_repo: MainRequestsRepo
):
    # Получаем достижения только для направления пользователя
    user_achievements = await stp_repo.achievement.get_achievements(
        division=user.division
    )

    if not user_achievements:
        await callback.message.edit_text(
            """<b>🎯 Достижения</b>

В твоем направлении пока нет доступных достижений 😔""",
            reply_markup=to_achievements_kb(),
        )
        return

    # Логика пагинации
    achievements_per_page = 5
    total_achievements = len(user_achievements)
    total_pages = (
        total_achievements + achievements_per_page - 1
    ) // achievements_per_page

    # Считаем начало и конец первой страницы
    start_idx = 0
    end_idx = achievements_per_page
    page_achievements = user_achievements[start_idx:end_idx]

    # Построение списка достижений для первой страницы
    achievements_list = []
    for counter, achievement in enumerate(page_achievements, start=1):
        # Экранируем HTML символы в полях
        description = (
            str(achievement.description).replace("<", "&lt;").replace(">", "&gt;")
        )
        name = str(achievement.name).replace("<", "&lt;").replace(">", "&gt;")
        position = str(achievement.position).replace("<", "&lt;").replace(">", "&gt;")

        period = ""
        match achievement.period:
            case "d":
                period = "Раз в день"
            case "w":
                period = "Раз в неделю"
            case "m":
                period = "Раз в месяц"
            case "A":
                period = "Вручную"
            case _:
                period = "Неизвестно"

        achievements_list.append(f"""{counter}. <b>{name}</b>
<blockquote>🏅 Награда: {achievement.reward} баллов
📝 Описание: {description}
🔰 Должность: {position}
🕒 Начисление: {period}</blockquote>""")
        achievements_list.append("")

    message_text = f"""<b>🎯 Достижения</b>

<b>📊 Всего достижений:</b> {total_achievements}

{chr(10).join(achievements_list)}"""

    await callback.message.edit_text(
        message_text, reply_markup=achievements_paginated_kb(1, total_pages)
    )

    logger.info(
        f"[Пользователь] - [Меню] {callback.from_user.username} ({callback.from_user.id}): "
        f"Открыто меню достижений направления {user.division}, страница 1"
    )


@user_game_achievements_router.callback_query(AchievementsMenu.filter(F.menu == "all"))
async def achievements_all(
    callback: CallbackQuery,
    callback_data: AchievementsMenu,
    user: Employee,
    stp_repo: MainRequestsRepo,
):
    """
    Обработчик клика на меню всех возможных достижений для пользователя
    Пользователь видит только достижения своего направления с пагинацией
    """

    # Достаём номер страницы из callback data, стандартно = 1
    page = getattr(callback_data, "page", 1)

    # Получаем достижения только для направления пользователя
    user_achievements = await stp_repo.achievement.get_achievements(
        division=user.division
    )

    if not user_achievements:
        await callback.message.edit_text(
            """<b>🎯 Все возможные достижения</b>

В твоем направлении пока нет доступных достижений 😔""",
            reply_markup=to_achievements_kb(),
        )
        return

    # Логика пагинации
    achievements_per_page = 5
    total_achievements = len(user_achievements)
    total_pages = (
        total_achievements + achievements_per_page - 1
    ) // achievements_per_page

    # Считаем начало и конец текущей страницы
    start_idx = (page - 1) * achievements_per_page
    end_idx = start_idx + achievements_per_page
    page_achievements = user_achievements[start_idx:end_idx]

    # Построение списка достижений для текущей страницы
    achievements_list = []
    for counter, achievement in enumerate(page_achievements, start=start_idx + 1):
        # Экранируем HTML символы в полях
        description = (
            str(achievement.description).replace("<", "&lt;").replace(">", "&gt;")
        )
        name = str(achievement.name).replace("<", "&lt;").replace(">", "&gt;")
        position = str(achievement.position).replace("<", "&lt;").replace(">", "&gt;")

        period = ""
        match achievement.period:
            case "d":
                period = "Раз в день"
            case "w":
                period = "Раз в неделю"
            case "m":
                period = "Раз в месяц"
            case "A":
                period = "Вручную"
            case _:
                period = "Неизвестно"

        achievements_list.append(f"""{counter}. <b>{name}</b>
<blockquote>🏅 Награда: {achievement.reward} баллов
📝 Описание: {description}
🔰 Должность: {position}
🕒 Начисление: {period}</blockquote>""")
        achievements_list.append("")

    message_text = f"""<b>🎯 Все возможные достижения</b>

<b>📊 Всего достижений:</b> {total_achievements}

{chr(10).join(achievements_list)}"""

    await callback.message.edit_text(
        message_text, reply_markup=achievements_paginated_kb(page, total_pages)
    )

    logger.info(
        f"[Пользователь] - [Меню] {callback.from_user.username} ({callback.from_user.id}): "
        f"Открыто меню всех достижений направления {user.division}, страница {page}"
    )
