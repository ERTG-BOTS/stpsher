from aiogram_dialog.widgets.common import sync_scroll
from aiogram_dialog.widgets.kbd import (
    Radio,
    Row,
    ScrollingGroup,
    Select,
    SwitchTo,
)
from aiogram_dialog.widgets.text import Const, Format, List
from aiogram_dialog.window import Window

from tgbot.dialogs.events.common.filters import on_filter_change
from tgbot.dialogs.events.user.shop import on_product_click


def create_products_window(state_group, menu_state, product_filter_getter):
    """Create shop products list window for a given state group with role-based filtering"""

    shop_window = Window(
        Format("""💎 <b>Магазин</b>

<b>✨ Твой баланс:</b> {user_balance} баллов\n"""),
        List(
            Format("""{pos}. <b>{item[1]}</b>
<blockquote>💵 Стоимость: {item[4]} баллов
📝 Описание: {item[2]}
📍 Активаций: {item[3]}</blockquote>\n"""),
            items="products",
            id="shop_products",
            page_size=4,
        ),
        ScrollingGroup(
            Select(
                Format("{pos}. {item[1]}"),
                id="product",
                items="products",
                item_id_getter=lambda item: item[0],
                on_click=on_product_click,
            ),
            width=2,
            height=2,
            hide_on_single_page=True,
            id="shop_scroll",
            on_page_changed=sync_scroll("shop_products"),
        ),
        Row(
            Radio(
                Format("🔘 {item[1]}"),
                Format("⚪️ {item[1]}"),
                id="shop_filter",
                item_id_getter=lambda item: item[0],
                items=[("available", "Доступные"), ("all", "Все предметы")],
                on_click=on_filter_change,
            ),
        ),
        Row(
            SwitchTo(Const("↩️ Назад"), id="menu", state=menu_state),
            SwitchTo(Const("🏠 Домой"), id="home", state=menu_state),
        ),
        getter=product_filter_getter,
        state=state_group.game_products,
    )

    return shop_window
