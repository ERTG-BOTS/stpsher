from aiogram import F, Router
from aiogram.types import CallbackQuery

from tgbot.keyboards.user.main import MainMenu

user_kpi_router = Router()
user_kpi_router.message.filter(F.chat.type == "private")
user_kpi_router.callback_query.filter(F.message.chat.type == "private")


@user_kpi_router.callback_query(MainMenu.filter(F.menu == "kpi"))
async def user_kpi_cb(callback: CallbackQuery):
    await callback.answer(
        """🚧 Функционал пока недоступен

Вернись через недельку 🧐""",
        show_alert=True,
    )
