from typing import List

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from tgbot.keyboards.user.main import MainMenu


class ScheduleMenu(CallbackData, prefix="schedule_menu"):
    menu: str


class MonthNavigation(CallbackData, prefix="month_nav"):
    """Callback data для навигации по месяцам"""

    action: str  # "prev", "next", "-", "detailed", "compact"
    current_month: str  # текущий месяц
    schedule_type: str = "my"  # "my", "duties", "heads"


# Список месяцев на русском языке
MONTHS_RU = [
    "январь",
    "февраль",
    "март",
    "апрель",
    "май",
    "июнь",
    "июль",
    "август",
    "сентябрь",
    "октябрь",
    "ноябрь",
    "декабрь",
]

# Эмодзи для месяцев
MONTH_EMOJIS = {
    "январь": "❄️",
    "февраль": "💙",
    "март": "🌸",
    "апрель": "🌷",
    "май": "🌻",
    "июнь": "☀️",
    "июль": "🏖️",
    "август": "🌾",
    "сентябрь": "🍂",
    "октябрь": "🎃",
    "ноябрь": "🍁",
    "декабрь": "🎄",
}


def schedule_kb() -> InlineKeyboardMarkup:
    """
    Клавиатура меню графиков.

    :return: Объект встроенной клавиатуры для возврата главного меню
    """
    buttons = [
        [
            InlineKeyboardButton(
                text="👔 Мой график", callback_data=ScheduleMenu(menu="my").pack()
            ),
        ],
        [
            InlineKeyboardButton(
                text="👮‍♂️ Старшие", callback_data=ScheduleMenu(menu="duties").pack()
            ),
            InlineKeyboardButton(
                text="👑 РГ", callback_data=ScheduleMenu(menu="heads").pack()
            ),
        ],
        [
            InlineKeyboardButton(
                text="↩️ Назад", callback_data=MainMenu(menu="main").pack()
            ),
        ],
    ]

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=buttons,
    )
    return keyboard


def get_available_months() -> List[str]:
    """
    Получает список доступных месяцев из Excel файла

    Returns:
        Список доступных месяцев
    """
    # TODO: Здесь можно добавить логику для автоматического определения
    # доступных месяцев из Excel файла
    # Пока возвращаем все месяцы
    return MONTHS_RU


def get_month_index(month: str) -> int:
    """
    Получает индекс месяца в списке

    Args:
        month: Название месяца

    Returns:
        Индекс месяца или 0, если не найден
    """
    try:
        return MONTHS_RU.index(month.lower())
    except ValueError:
        return 0


def get_next_month(current_month: str, available_months: List[str]) -> str:
    """
    Получает следующий доступный месяц

    Args:
        current_month: Текущий месяц
        available_months: Список доступных месяцев

    Returns:
        Следующий месяц или текущий, если следующего нет
    """
    try:
        current_index = available_months.index(current_month.lower())
        if current_index < len(available_months) - 1:
            return available_months[current_index + 1]
        else:
            return current_month.lower()  # Возвращаем текущий, если следующего нет
    except (ValueError, IndexError):
        return current_month.lower()


def get_prev_month(current_month: str, available_months: List[str]) -> str:
    """
    Получает предыдущий доступный месяц

    Args:
        current_month: Текущий месяц
        available_months: Список доступных месяцев

    Returns:
        Предыдущий месяц или текущий, если предыдущего нет
    """
    try:
        current_index = available_months.index(current_month.lower())
        if current_index > 0:
            return available_months[current_index - 1]
        else:
            return current_month.lower()  # Возвращаем текущий, если предыдущего нет
    except (ValueError, IndexError):
        return current_month.lower()


def schedule_with_month_kb(
    current_month: str, schedule_type: str = "my"
) -> InlineKeyboardMarkup:
    """
    Объединенная клавиатура: меню расписаний + навигация по месяцам

    Args:
        current_month: Текущий выбранный месяц
        schedule_type: Тип пользователя

    Returns:
        Объект встроенной клавиатуры
    """
    available_months = get_available_months()
    current_month = current_month.lower()

    # Получаем предыдущий и следующий месяцы
    prev_month = get_prev_month(current_month, available_months)
    next_month = get_next_month(current_month, available_months)

    # Эмодзи для текущего месяца
    month_emoji = MONTH_EMOJIS.get(current_month, "📅")

    # Создаем ряд навигации по месяцам
    nav_row = []

    # Кнопка "Назад" (только если есть предыдущий месяц)
    if prev_month != current_month:
        nav_row.append(
            InlineKeyboardButton(
                text="◀️",
                callback_data=MonthNavigation(
                    action="prev", current_month=prev_month, schedule_type=schedule_type
                ).pack(),
            )
        )

    # Кнопка текущего месяца (всегда присутствует)
    nav_row.append(
        InlineKeyboardButton(
            text=f"{month_emoji} {current_month.capitalize()}",
            callback_data=MonthNavigation(
                action="-",
                current_month=current_month,
                schedule_type=schedule_type,
            ).pack(),
        )
    )

    # Кнопка "Вперед" (только если есть следующий месяц)
    if next_month != current_month:
        nav_row.append(
            InlineKeyboardButton(
                text="▶️",
                callback_data=MonthNavigation(
                    action="next", current_month=next_month, schedule_type=schedule_type
                ).pack(),
            )
        )

    buttons = [
        nav_row,  # Ряд навигации по месяцам
        [
            InlineKeyboardButton(
                text="📋 Подробнее",
                callback_data=MonthNavigation(
                    action="detailed",
                    current_month=current_month,
                    schedule_type=schedule_type,
                ).pack(),
            ),
        ],
        [
            InlineKeyboardButton(
                text="↩️ Назад", callback_data=MainMenu(menu="schedule").pack()
            ),
            InlineKeyboardButton(
                text="🏠 Главная", callback_data=MainMenu(menu="main").pack()
            ),
        ],
    ]

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard


def create_detailed_schedule_keyboard(current_month: str, schedule_type: str):
    """Создает клавиатуру для детального режима расписания"""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    available_months = get_available_months()
    current_month_lower = current_month.lower()

    # Получаем предыдущий и следующий месяцы
    prev_month = get_prev_month(current_month_lower, available_months)
    next_month = get_next_month(current_month_lower, available_months)

    # Эмодзи для текущего месяца
    month_emoji = MONTH_EMOJIS.get(current_month_lower, "📅")

    buttons = []

    # Навигация по месяцам (только если есть доступные месяцы)
    nav_row = []

    # Кнопка "Назад" (только если есть предыдущий месяц)
    if prev_month != current_month_lower:  # Есть предыдущий месяц
        nav_row.append(
            InlineKeyboardButton(
                text="◀️",
                callback_data=MonthNavigation(
                    action="prev", current_month=prev_month, schedule_type=schedule_type
                ).pack(),
            )
        )

    # Текущий месяц
    nav_row.append(
        InlineKeyboardButton(
            text=f"{month_emoji} {current_month.capitalize()}",
            callback_data=MonthNavigation(
                action="-",
                current_month=current_month_lower,
                schedule_type=schedule_type,
            ).pack(),
        )
    )

    # Кнопка "Вперед" (только если есть следующий месяц)
    if next_month != current_month_lower:  # Есть следующий месяц
        nav_row.append(
            InlineKeyboardButton(
                text="▶️",
                callback_data=MonthNavigation(
                    action="next", current_month=next_month, schedule_type=schedule_type
                ).pack(),
            )
        )

    buttons.append(nav_row)

    # Кнопка "Кратко"
    buttons.append(
        [
            InlineKeyboardButton(
                text="📋 Кратко",
                callback_data=MonthNavigation(
                    action="compact",
                    current_month=current_month_lower,
                    schedule_type=schedule_type,
                ).pack(),
            ),
        ]
    )

    # Кнопки навигации
    buttons.append(
        [
            InlineKeyboardButton(
                text="↩️ Назад", callback_data=MainMenu(menu="schedule").pack()
            ),
            InlineKeyboardButton(
                text="🏠 Главная", callback_data=MainMenu(menu="main").pack()
            ),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)
