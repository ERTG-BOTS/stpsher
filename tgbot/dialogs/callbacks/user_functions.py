from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.kbd import Button

from tgbot.misc.states.user.main import UserSG


async def switch_to_detailed(
    callback: CallbackQuery, button: Button, dialog_manager: DialogManager
):
    await dialog_manager.switch_to(UserSG.schedule_my_detailed)
