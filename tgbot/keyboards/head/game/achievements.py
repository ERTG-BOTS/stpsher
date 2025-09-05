from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from tgbot.keyboards.gok.main import GokGameMenu, create_filters_row
from tgbot.keyboards.head.group.main import GroupManagementMenu


def head_achievements_paginated_kb(
    page: int, total_pages: int, filters: str
) -> InlineKeyboardMarkup:
    """
    Клавиатура с пагинацией для списка достижений для руководителей
    :param page: Текущая страница
    :param total_pages: Всего страниц
    :param filters: Активные фильтры
    :return:
    """
    buttons = []

    # Add filter buttons
    filter_buttons = create_filters_row("achievements_all", filters, page)
    if filter_buttons:
        buttons.append(filter_buttons)

    # Pagination controls
    nav_buttons = []

    if page > 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text="↩️ Назад",
                callback_data=GokGameMenu(
                    menu="achievements_all", page=page - 1, filters=filters
                ).pack(),
            )
        )

    nav_buttons.append(
        InlineKeyboardButton(
            text=f"📄 {page}/{total_pages}",
            callback_data="current_page",
        )
    )

    if page < total_pages:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Вперёд ➡️",
                callback_data=GokGameMenu(
                    menu="achievements_all", page=page + 1, filters=filters
                ).pack(),
            )
        )

    buttons.append(nav_buttons)

    # Back button - return to game menu for heads
    buttons.append(
        [
            InlineKeyboardButton(
                text="↩️ Назад",
                callback_data=GroupManagementMenu(menu="game").pack(),
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)
