from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.widgets.kbd import Radio, Row, ScrollingGroup, Select, SwitchTo
from aiogram_dialog.widgets.text import Const, Format
from aiogram_dialog.window import Window

from tgbot.dialogs.events.common.filters import on_filter_change
from tgbot.dialogs.events.user.search import on_search_query, on_user_select
from tgbot.dialogs.getters.common.search_getters import (
    search_heads_getter,
    search_results_getter,
    search_specialists_getter,
    search_user_info_getter,
)
from tgbot.dialogs.getters.user.user_getters import db_getter
from tgbot.misc.states.user.main import UserSG

search_window = Window(
    Format("""🕵🏻 <b>Поиск сотрудника</b>

<i>Выбери должность искомого человека или воспользуйся общим поиском</i>"""),
    Row(
        SwitchTo(
            Const("👤 Специалисты"), id="schedules", state=UserSG.search_specialists
        ),
        SwitchTo(Const("👑 Руководители"), id="kpi", state=UserSG.search_heads),
    ),
    SwitchTo(Const("🕵🏻 Поиск"), id="game", state=UserSG.search_query),
    SwitchTo(Const("↩️ Назад"), id="menu", state=UserSG.menu),
    getter=db_getter,
    state=UserSG.search,
)

search_specialists_window = Window(
    Format(
        """👤 Специалисты

Найдено специалистов: {total_specialists}""",
    ),
    ScrollingGroup(
        Select(
            Format("{item[2]} {item[1]}"),
            id="search_specialists",
            items="specialists_list",
            item_id_getter=lambda item: item[0],
            on_click=on_user_select,
        ),
        width=2,
        height=5,
        hide_on_single_page=True,
        id="search_scroll",
    ),
    Row(
        Radio(
            Format("🔘 {item[1]}"),
            Format("⚪️ {item[1]}"),
            id="search_divisions",
            item_id_getter=lambda item: item[0],
            items="division_options",
            on_click=on_filter_change,
        ),
    ),
    Row(
        SwitchTo(Const("↩️ Назад"), id="menu", state=UserSG.search),
        SwitchTo(Const("🏠 Домой"), id="home", state=UserSG.menu),
    ),
    getter=search_specialists_getter,
    state=UserSG.search_specialists,
)


search_heads_window = Window(
    Format(
        """👑 Руководители
    
Найдено руководителей: {total_heads}""",
    ),
    ScrollingGroup(
        Select(
            Format("{item[2]} {item[1]}"),
            id="search_heads",
            items="heads_list",
            item_id_getter=lambda item: item[0],
            on_click=on_user_select,
        ),
        width=2,
        height=5,
        hide_on_single_page=True,
        id="search_scroll",
    ),
    Row(
        Radio(
            Format("🔘 {item[1]}"),
            Format("⚪️ {item[1]}"),
            id="search_divisions",
            item_id_getter=lambda item: item[0],
            items="division_options",
            on_click=on_filter_change,
        ),
    ),
    Row(
        SwitchTo(Const("↩️ Назад"), id="menu", state=UserSG.search),
        SwitchTo(Const("🏠 Домой"), id="home", state=UserSG.menu),
    ),
    getter=search_heads_getter,
    state=UserSG.search_heads,
)

search_query_window = Window(
    Format("""🕵🏻 Поиск сотрудника

Введи:
• Часть имени/фамилии или полное ФИО
• ID пользователя (число)
• Username Telegram (@username или username)

<i>Например: Иванов, 123456789, @username, username</i>"""),
    TextInput(id="search_query", on_success=on_search_query),
    SwitchTo(Const("↩️ Назад"), id="back", state=UserSG.search),
    state=UserSG.search_query,
)

search_results_window = Window(
    Format("""🔍 <b>Результаты поиска</b>

По запросу "<code>{search_query}</code>" найдено: {total_found} сотрудников"""),
    ScrollingGroup(
        Select(
            Format("{item[1]}"),
            id="search_results",
            items="search_results",
            item_id_getter=lambda item: item[0],
            on_click=on_user_select,
        ),
        width=1,
        height=5,
        hide_on_single_page=True,
        id="search_results_scroll",
    ),
    Row(
        SwitchTo(Const("↩️ Назад"), id="back", state=UserSG.search),
        SwitchTo(Const("🏠 Домой"), id="home", state=UserSG.menu),
    ),
    getter=search_results_getter,
    state=UserSG.search_result,
    parse_mode="HTML",
)

search_no_results_window = Window(
    Format("""❌ <b>Ничего не найдено</b>

По запросу "<code>{search_query}</code>" сотрудники не найдены.

Попробуйте:
• Проверить правильность написания
• Использовать только часть имени или фамилии
• Поискать по username без @
• Использовать числовой ID пользователя"""),
    Row(
        SwitchTo(Const("🔄 Новый поиск"), id="new_search", state=UserSG.search_query),
        SwitchTo(Const("↩️ Назад"), id="back", state=UserSG.search),
    ),
    SwitchTo(Const("🏠 Домой"), id="home", state=UserSG.menu),
    getter=search_results_getter,
    state=UserSG.search_no_results,
)

search_user_info_window = Window(
    Format("{user_info}"),
    Row(
        SwitchTo(Const("↩️ Назад"), id="back", state=UserSG.search_result),
        SwitchTo(Const("🏠 Домой"), id="home", state=UserSG.menu),
    ),
    getter=search_user_info_getter,
    state=UserSG.search_user_detail,
)
