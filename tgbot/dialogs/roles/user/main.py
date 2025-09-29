from aiogram_dialog import Dialog, DialogManager
from aiogram_dialog.widgets.kbd import ManagedRadio, Row, SwitchTo
from aiogram_dialog.widgets.text import Const, Format
from aiogram_dialog.window import Window

from tgbot.dialogs.getters.user.user_getters import db_getter
from tgbot.dialogs.roles.user.game import (
    confirm_window,
    game_window,
    inventory_detail_window,
    inventory_window,
    shop_window,
    success_window,
)
from tgbot.dialogs.roles.user.kpi import (
    kpi_requirements_window,
    kpi_window,
    salary_window,
)
from tgbot.dialogs.roles.user.schedule import (
    schedule_duties_window,
    schedule_group_window,
    schedule_heads_window,
    schedule_my_window,
    schedule_window,
)
from tgbot.misc.states.user.main import UserSG

menu_window = Window(
    Format("""👋 Привет, <b>{user.fullname}</b>!

Я - бот-помощник СТП

<i>Используй меню для взаимодействия с ботом</i>"""),
    Row(
        SwitchTo(Const("📅 Графики"), id="schedules", state=UserSG.schedule),
        SwitchTo(Const("🌟 Показатели"), id="kpi", state=UserSG.kpi),
    ),
    SwitchTo(Const("🏮 Игра"), id="game", state=UserSG.game),
    Row(
        SwitchTo(Const("🕵🏻 Поиск сотрудника"), id="search", state=UserSG.search),
        SwitchTo(Const("👯‍♀️ Группы"), id="groups", state=UserSG.groups),
    ),
    getter=db_getter,
    state=UserSG.menu,
)


async def on_start(start_data, manager: DialogManager, **kwargs):
    """Установка значений по умолчанию при запуске диалога"""
    # Устанавливаем значение по умолчанию для фильтра магазина
    shop_filter: ManagedRadio = manager.find("shop_filter")
    await shop_filter.set_checked("available")

    inventory_filter: ManagedRadio = manager.find("inventory_filter")
    await inventory_filter.set_checked("all")


user_dialog = Dialog(
    menu_window,
    schedule_window,
    schedule_my_window,
    schedule_duties_window,
    schedule_group_window,
    schedule_heads_window,
    kpi_window,
    kpi_requirements_window,
    salary_window,
    game_window,
    shop_window,
    confirm_window,
    success_window,
    inventory_window,
    inventory_detail_window,
    on_start=on_start,
    getter=db_getter,
)
