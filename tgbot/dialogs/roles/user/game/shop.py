from aiogram_dialog.widgets.common import sync_scroll
from aiogram_dialog.widgets.kbd import (
    Button,
    Radio,
    Row,
    ScrollingGroup,
    Select,
    SwitchTo,
)
from aiogram_dialog.widgets.text import Const, Format, List
from aiogram_dialog.window import Window

from tgbot.dialogs.events.user.game import (
    on_confirm_purchase,
    on_filter_change,
    on_product_click,
    on_sell_product,
    use_product,
)
from tgbot.dialogs.getters.user.game_getters import (
    confirmation_getter,
    product_filter_getter,
    success_getter,
)
from tgbot.misc.states.user.main import UserSG

shop_window = Window(
    Format("""💎 <b>Магазин</b>

<b>✨ Твой баланс:</b> {user_balance} баллов\n"""),
    List(
        Format("""{pos}. <b>{item[1]}</b>
<blockquote>💵 Стоимость: {item[3]} баллов
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
            item_id_getter=lambda item: item[0],  # Идентификатор предмета
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
        SwitchTo(Const("↩️ Назад"), id="menu", state=UserSG.game),
        SwitchTo(Const("🏠 Домой"), id="home", state=UserSG.menu),
    ),
    getter=product_filter_getter,
    state=UserSG.game_shop,
)

confirm_window = Window(
    Format("""<b>🎯 Покупка предмета:</b> {product_name}

<b>📝 Описание</b>
{product_description}

<b>📍 Количество использований:</b> {product_count}

<b>✨ Баланс</b>
• Текущий: {user_balance} баллов
• Спишется: {product_cost} баллов
• Останется: {balance_after_purchase} баллов

<i>Купленные предметы можно найти в <b>🎒 Инвентаре</b></i>"""),
    Button(
        Const("✅ Купить"),
        id="confirm_buy",
        on_click=on_confirm_purchase,
    ),
    Row(
        SwitchTo(Const("↩️ Назад"), id="menu", state=UserSG.game_shop),
        SwitchTo(Const("🏠 Домой"), id="home", state=UserSG.menu),
    ),
    getter=confirmation_getter,
    state=UserSG.game_shop_confirm,
)

success_window = Window(
    Format("""<b>✅ Приобретен предмет:</b> {product_name}

<b>📍 Количество активаций:</b> {product_count}

<b>✨ Баланс</b>
• Был: {user_balance} баллов
• Списано: {product_cost} баллов
• Стало: {new_balance} баллов

<b>📝 Описание</b>
{product_description}

<i>🎯 Ты можешь использовать его сейчас или позже в <b>🎒 Инвентаре</b></i>"""),
    Row(
        Button(
            Const("🎯 Использовать"),
            id="use_product",
            on_click=use_product,
        ),
        Button(
            Const("💸 Продать"),
            id="sell_product",
            on_click=on_sell_product,
        ),
    ),
    Row(
        SwitchTo(Const("🎒 Инвентарь"), id="inventory", state=UserSG.game_inventory),
        SwitchTo(Const("💎 Магазин"), id="inventory", state=UserSG.game_shop),
    ),
    Row(
        SwitchTo(Const("🏮 К игре"), id="to_game", state=UserSG.game),
        SwitchTo(Const("🏠 Домой"), id="home", state=UserSG.menu),
    ),
    getter=success_getter,
    state=UserSG.game_shop_success,
)
