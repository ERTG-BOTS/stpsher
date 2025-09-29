from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram_dialog import DialogManager, StartMode
from aiogram_dialog.api.exceptions import NoContextError

from infrastructure.database.models import Employee
from tgbot.filters.role import HeadFilter
from tgbot.misc.states.head import HeadSG

head_router = Router()
head_router.message.filter(F.chat.type == "private", HeadFilter())
head_router.callback_query.filter(F.message.chat.type == "private", HeadFilter())


@head_router.message(CommandStart())
async def admin_start_cmd(
    message: Message, user: Employee, dialog_manager: DialogManager, **kwargs
):
    try:
        await dialog_manager.done()
    except NoContextError:
        pass

    await dialog_manager.start(HeadSG.menu, mode=StartMode.RESET_STACK)
