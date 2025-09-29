from aiogram_dialog import Window
from aiogram_dialog.widgets.kbd import Row, SwitchTo
from aiogram_dialog.widgets.text import Const, Format

from tgbot.dialogs.getters.common.kpi import (
    kpi_getter,
    kpi_requirements_getter,
    salary_getter,
)
from tgbot.misc.states.user.main import UserSG

kpi_window = Window(
    Format("{kpi_text}"),
    Row(
        SwitchTo(
            Const("🧮 Нормативы"),
            id="calculator",
            state=UserSG.kpi_requirements,
        ),
        SwitchTo(
            Const("💰 Зарплата"),
            id="salary",
            state=UserSG.salary,
        ),
    ),
    SwitchTo(Const("🔄 Обновить"), id="update", state=UserSG.kpi),
    SwitchTo(Const("↩️ Назад"), id="menu", state=UserSG.menu),
    getter=kpi_getter,
    state=UserSG.kpi,
)

kpi_requirements_window = Window(
    Format("{requirements_text}"),
    Row(
        SwitchTo(Const("🌟 Показатели"), id="kpi", state=UserSG.kpi),
        SwitchTo(
            Const("💰 Зарплата"),
            id="salary",
            state=UserSG.salary,
        ),
    ),
    SwitchTo(Const("🔄 Обновить"), id="update", state=UserSG.kpi_requirements),
    SwitchTo(Const("↩️ Назад"), id="menu", state=UserSG.menu),
    getter=kpi_requirements_getter,
    state=UserSG.kpi_requirements,
)

salary_window = Window(
    Format("{salary_text}"),
    Row(
        SwitchTo(Const("🌟 Показатели"), id="kpi", state=UserSG.kpi),
        SwitchTo(
            Const("🧮 Нормативы"),
            id="calculator",
            state=UserSG.kpi_requirements,
        ),
    ),
    SwitchTo(Const("🔄 Обновить"), id="update", state=UserSG.salary),
    SwitchTo(Const("↩️ Назад"), id="menu", state=UserSG.menu),
    getter=salary_getter,
    state=UserSG.salary,
)
