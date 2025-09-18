from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from tgbot.keyboards.user.main import MainMenu


def main_kb() -> InlineKeyboardMarkup:
    """
    Клавиатура главного меню.

    :return: Объект встроенной клавиатуры для возврата главного меню
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="📅 Графики", callback_data=MainMenu(menu="schedule").pack()
            ),
            InlineKeyboardButton(
                text="🌟 Показатели", callback_data=MainMenu(menu="kpi").pack()
            ),
        ],
        [
            InlineKeyboardButton(
                text="❤️ Группа",
                callback_data=MainMenu(menu="group_management").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="🔍 Поиск сотрудников",
                callback_data=MainMenu(menu="head_search").pack(),
            ),
        ],
    ]

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=buttons,
    )
    return keyboard
