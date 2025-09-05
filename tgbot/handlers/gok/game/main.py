import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from infrastructure.database.repo.STP.requests import MainRequestsRepo
from tgbot.filters.role import GokFilter
from tgbot.keyboards.gok.main import (
    gok_kb,
    GokFilterToggleMenu,
    GokGameMenu,
    toggle_filter,
    GokProductsMenu,
)
from tgbot.keyboards.user.main import MainMenu

gok_game_router = Router()
gok_game_router.message.filter(F.chat.type == "private", GokFilter())
gok_game_router.callback_query.filter(F.message.chat.type == "private", GokFilter())

logger = logging.getLogger(__name__)


def filter_items_by_division(items, active_filters):
    """Filter achievements or products by division based on active filters"""
    # Filter by specific divisions
    filtered_items = []
    for item in items:
        if item.division in active_filters:
            filtered_items.append(item)

    return filtered_items


@gok_game_router.callback_query(MainMenu.filter(F.menu == "game"))
async def gok_achievements_cmd(callback: CallbackQuery):
    await callback.message.edit_text(
        """<b>🏮 Игра</b>

Здесь ты можешь:
- Подтверждать/отклонять покупки специалистов
- Просматривать список достижений
- Просматривать список предметов""",
        reply_markup=gok_kb(),
    )


@gok_game_router.callback_query(GokFilterToggleMenu.filter())
async def gok_toggle_filter_handler(
    callback: CallbackQuery,
    callback_data: GokFilterToggleMenu,
    stp_repo: MainRequestsRepo,
):
    """Обработчик переключения фильтров"""
    from tgbot.handlers.gok.game.achievements import gok_achievements_all
    from tgbot.handlers.gok.game.products import gok_products_all

    menu = callback_data.menu
    filter_name = callback_data.filter_name
    current_filters = callback_data.current_filters

    # Переключаем фильтр
    new_filters = toggle_filter(current_filters, filter_name)

    # Переходим на первую страницу при изменении фильтров
    if menu == "achievements_all":
        await gok_achievements_all(
            callback,
            GokGameMenu(menu="achievements_all", page=1, filters=new_filters),
            stp_repo,
        )
    elif menu == "products_all":
        await gok_products_all(
            callback,
            GokProductsMenu(menu="products_all", page=1, filters=new_filters),
            stp_repo,
        )
