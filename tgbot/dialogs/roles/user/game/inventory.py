from aiogram_dialog.widgets.kbd import (
    Button,
    Radio,
    Row,
    ScrollingGroup,
    Select,
    SwitchTo,
)
from aiogram_dialog.widgets.text import Const, Format
from aiogram_dialog.window import Window

from tgbot.dialogs.events.user.game import (
    on_filter_change,
    on_inventory_cancel_activation,
    on_inventory_product_click,
    on_inventory_sell_product,
    use_product,
)
from tgbot.dialogs.getters.user.game_getters import (
    inventory_detail_getter,
    inventory_filter_getter,
)
from tgbot.misc.states.user.main import UserSG


def get_status_emoji(status: str) -> str:
    """Возвращает эмодзи в зависимости от статуса"""
    status_emojis = {
        "stored": "📦",
        "review": "⏳",
        "used_up": "🔒",
    }
    return status_emojis.get(status, "❓")


inventory_window = Window(
    Format("""🎒 <b>Инвентарь</b>

Здесь ты найдешь все свои покупки, а так же их статус и многое другое

Используй фильтры для поиска нужных предметов:
📦 - Готов к использованию
⏳ - На проверке
🔒 - Не осталось использований

<i>Всего предметов приобретено: {total_bought}</i>"""),
    ScrollingGroup(
        Select(
            Format("{item[1]}"),
            id="inventory_product",
            items="products",
            item_id_getter=lambda item: item[0],  # ID покупки для обработчика клика
            on_click=on_inventory_product_click,
        ),
        width=2,
        height=2,
        hide_on_single_page=True,
        id="inventory_scroll",
    ),
    Radio(
        Format("🔘 {item[1]}"),
        Format("⚪️ {item[1]}"),
        id="inventory_filter",
        item_id_getter=lambda item: item[0],
        items=[
            ("all", "📋 Все"),
            ("stored", f"{get_status_emoji('stored')}"),
            ("review", f"{get_status_emoji('review')}"),
            ("used_up", f"{get_status_emoji('used_up')}"),
        ],
        on_click=on_filter_change,
    ),
    Row(
        SwitchTo(Const("↩️ Назад"), id="menu", state=UserSG.game),
        SwitchTo(Const("🏠 Домой"), id="home", state=UserSG.menu),
    ),
    getter=inventory_filter_getter,
    state=UserSG.game_inventory,
)


inventory_detail_window = Window(
    Format("""
<b>🛍️ Предмет:</b> {product_name}

<b>📊 Статус</b>
{status_name}

<b>📍 Активаций</b>
{usage_count} из {product_count}

<b>💵 Стоимость</b>
{product_cost} баллов

<b>📝 Описание</b>
{product_description}

<blockquote expandable><b>📅 Дата покупки</b>
{bought_at}</blockquote>{comment_text}{updated_by_text}"""),
    # Кнопки действий с предметом
    Button(
        Const("🎯 Использовать"),
        id="use_product",
        on_click=use_product,
        when="can_use",
    ),
    Button(
        Const("💸 Вернуть"),
        id="sell_product",
        on_click=on_inventory_sell_product,
        when="can_sell",
    ),
    Button(
        Const("✋🏻 Отменить активацию"),
        id="cancel_activation",
        on_click=on_inventory_cancel_activation,
        when="can_cancel",
    ),
    Row(
        SwitchTo(Const("↩️ Назад"), id="back_to_inventory", state=UserSG.game_inventory),
        SwitchTo(Const("🏠 Домой"), id="home", state=UserSG.menu),
    ),
    getter=inventory_detail_getter,
    state=UserSG.game_inventory_detail,
)
