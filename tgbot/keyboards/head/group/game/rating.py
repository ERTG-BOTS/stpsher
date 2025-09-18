from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from tgbot.keyboards.user.main import MainMenu


class RatingMenu(CallbackData, prefix="rating"):
    metric: str
    period: str = "day"


def rating_menu_kb(
    current_period: str = "day", current_metric: str = "csi"
) -> InlineKeyboardMarkup:
    """
    Клавиатура рейтинга группы с выбором метрик и периода.

    :param current_period: Текущий выбранный период
    :param current_metric: Текущая выбранная метрика
    :return: Объект встроенной клавиатуры для рейтинга группы
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="📊 Оценка",
                callback_data=RatingMenu(metric="csi", period=current_period).pack(),
            ),
            InlineKeyboardButton(
                text="📞 Отклик",
                callback_data=RatingMenu(metric="pok", period=current_period).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="📈 FLR",
                callback_data=RatingMenu(metric="flr", period=current_period).pack(),
            ),
            InlineKeyboardButton(
                text="🎯 Цель",
                callback_data=RatingMenu(
                    metric="sales_count", period=current_period
                ).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="День" + (" ✅" if current_period == "day" else ""),
                callback_data=RatingMenu(metric=current_metric, period="day").pack(),
            ),
            InlineKeyboardButton(
                text="Неделя" + (" ✅" if current_period == "week" else ""),
                callback_data=RatingMenu(metric=current_metric, period="week").pack(),
            ),
            InlineKeyboardButton(
                text="Месяц" + (" ✅" if current_period == "month" else ""),
                callback_data=RatingMenu(metric=current_metric, period="month").pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="↩️ Назад",
                callback_data=MainMenu(menu="group_management").pack(),
            ),
            InlineKeyboardButton(
                text="🏠 Домой",
                callback_data=MainMenu(menu="main").pack(),
            ),
        ],
    ]

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard
