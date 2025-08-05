from aiogram.filters import BaseFilter
from aiogram.types import Message

from infrastructure.database.models.user import User
from tgbot.misc.dicts import executed_codes

ADMIN_ROLE = 10


class AdminFilter(BaseFilter):
    async def __call__(self, obj: Message, user: User, **kwargs) -> bool:
        if user is None:
            return False

        return user.Role == executed_codes["root"]
