from aiogram_dialog.widgets.kbd import (
    Button,
    Row,
    SwitchTo,
)
from aiogram_dialog.widgets.text import Const, Format
from aiogram_dialog.window import Window

from tgbot.dialogs.getters.user.game.game import game_getter
from tgbot.misc.states.dialogs.user import UserSG

game_window = Window(
    Format("""🏮 <b>Игра</b>

{level_info}

<blockquote expandable><b>✨ Баланс</b>
Всего заработано: {achievements_sum} баллов
Всего потрачено: {purchases_sum} баллов</blockquote>"""),
    SwitchTo(Const("💎 Магазин"), id="shop", state=UserSG.game_products),
    SwitchTo(
        Const("✍️ Активация предметов"),
        id="products_activation",
        when="is_duty",
        state=UserSG.game_products_activation,
    ),
    Row(
        SwitchTo(
            Const("🎒 Инвентарь"),
            id="inventory",
            state=UserSG.game_inventory,
        ),
        Button(
            Const("🎲 Казино"),
            id="casino",
        ),
    ),
    SwitchTo(
        Const("🎯 Достижения"),
        id="achievements",
        state=UserSG.game_achievements,
    ),
    SwitchTo(
        Const("📜 История баланса"),
        id="history",
        state=UserSG.game_history,
    ),
    SwitchTo(Const("↩️ Назад"), id="menu", state=UserSG.menu),
    getter=game_getter,
    state=UserSG.game,
)
