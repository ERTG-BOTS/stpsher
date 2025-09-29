import datetime
import logging
from typing import Optional

import pytz
from aiogram import F, Router
from aiogram.types import CallbackQuery

from infrastructure.database.models import Employee
from tgbot.keyboards.user.main import MainMenu, auth_kb
from tgbot.keyboards.user.schedule.main import (
    get_yekaterinburg_date,
    schedule_kb,
)
from tgbot.misc.dicts import russian_months
from tgbot.services.schedule import (
    DutyScheduleParser,
    HeadScheduleParser,
    ScheduleError,
    ScheduleFileNotFoundError,
    ScheduleFormatter,
    ScheduleParser,
    UserNotFoundError,
)
from tgbot.services.schedule.parsers import GroupScheduleParser

logger = logging.getLogger(__name__)

user_schedule_router = Router()
user_schedule_router.message.filter(F.chat.type == "private")
user_schedule_router.callback_query.filter(F.message.chat.type == "private")


class ScheduleHandlerService:
    """Сервис для обработки операций с расписанием"""

    def __init__(self):
        self.schedule_parser = ScheduleParser()
        self.duty_parser = DutyScheduleParser()
        self.head_parser = HeadScheduleParser()
        self.group_parser = GroupScheduleParser()
        self.formatter = ScheduleFormatter()
        self.yekaterinburg_tz = pytz.timezone("Asia/Yekaterinburg")

    @staticmethod
    async def check_user_auth(callback: CallbackQuery, user: Employee) -> bool:
        """Проверяет авторизацию пользователя"""
        if not user:
            await callback.message.answer(
                """👋 Привет

Я - бот-помощник СТП

Используй кнопку ниже для авторизации""",
                reply_markup=auth_kb(),
            )
            return False
        return True

    @staticmethod
    async def handle_schedule_error(
        callback: CallbackQuery, error: Exception, fallback_markup=None
    ) -> None:
        """Обработка ошибок расписания"""
        if fallback_markup is None:
            fallback_markup = schedule_kb()

        if isinstance(error, UserNotFoundError):
            error_msg = "❌ Пользователь не найден в расписании"
        elif isinstance(error, ScheduleFileNotFoundError):
            error_msg = "❌ Файл расписания не найден"
        elif isinstance(error, ScheduleError):
            error_msg = f"❌ Ошибка расписания: {error}"
        else:
            error_msg = f"❌ Ошибка при получении данных:\n<code>{error}</code>"

        logger.error(f"Schedule error: {error}", exc_info=True)

        try:
            await callback.message.edit_text(
                text=error_msg,
                reply_markup=fallback_markup,
            )
        except Exception as edit_error:
            logger.error(f"Failed to edit message: {edit_error}")
            await callback.answer(error_msg, show_alert=True)

    @staticmethod
    def get_current_month() -> str:
        """Получает текущий месяц"""
        return russian_months[datetime.datetime.now().month]

    @staticmethod
    def get_current_date():
        """Получает текущую дату по Екатеринбургу"""
        yekaterinburg_tz = pytz.timezone("Asia/Yekaterinburg")
        return datetime.datetime.now(yekaterinburg_tz)

    def parse_date_from_callback(self, date_str: str) -> datetime.datetime:
        """Парсит дату из callback data"""
        target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        return self.yekaterinburg_tz.localize(target_date)

    async def get_user_schedule_response(
        self, user: Employee, month: str, compact: bool = True, stp_repo=None
    ) -> str:
        """Получает расписание пользователя с информацией о дежурствах"""
        if stp_repo:
            # Fetch duty information when stp_repo is available (for heads/MIP viewing others)
            return await self.schedule_parser.get_user_schedule_formatted_with_duties(
                fullname=user.fullname,
                month=month,
                division=user.division,
                compact=compact,
                stp_repo=stp_repo,
            )
        else:
            # Use regular schedule when no stp_repo (for users viewing their own schedule)
            return self.schedule_parser.get_user_schedule_formatted(
                fullname=user.fullname,
                month=month,
                division=user.division,
                compact=compact,
            )

    async def get_duties_response(
        self, division: str, date: Optional[datetime.datetime] = None, stp_repo=None
    ) -> str:
        """Получает расписание дежурных"""
        if date is None:
            date = get_yekaterinburg_date()

        duties = await self.duty_parser.get_duties_for_date(date, division, stp_repo)

        # Фильтруем дежурных, которых нет в базе данных (уволенных)
        if stp_repo:
            active_duties = []
            for duty in duties:
                try:
                    user = await stp_repo.employee.get_user(fullname=duty.name)
                    if user:
                        active_duties.append(duty)
                    else:
                        logger.debug(
                            f"[График дежурств] Сотрудник {duty.name} не найден в базе данных"
                        )
                except Exception as e:
                    logger.debug(
                        f"[График дежурств] Ошибка проверки сотрудника {duty.name} в БД: {e}"
                    )
                    # Если не можем проверить - включаем пользователя в список дежурных для избежания false negative
                    active_duties.append(duty)
            duties = active_duties

        # Check if today's date is selected to highlight current duties
        today = get_yekaterinburg_date().date()
        highlight_current = (date.date() == today) and stp_repo

        # Get formatted duties schedule with optional current duty highlighting
        return await self.duty_parser.format_schedule(
            duties, date, highlight_current, division, stp_repo
        )

    async def get_heads_response(
        self, division: str, date: Optional[datetime.datetime] = None, stp_repo=None
    ) -> str:
        """Получает расписание руководителей групп"""
        if date is None:
            date = get_yekaterinburg_date()

        heads = await self.head_parser.get_heads_for_date(date, division, stp_repo)

        return self.head_parser.format_schedule(heads, date)

    async def get_group_schedule_response(
        self,
        user: Employee,
        date: Optional[datetime.datetime] = None,
        page: int = 1,
        stp_repo=None,
        is_head: bool = False,
    ) -> tuple[str, int, bool, bool]:
        """
        Получает групповое расписание для пользователя или руководителя

        :param user: Пользователь
        :param date: Дата (по умолчанию сегодня)
        :param page: Страница для пагинации
        :param stp_repo: Репозиторий БД
        :param is_head: Является ли пользователь руководителем
        :return: (текст, общее количество страниц, есть предыдущая, есть следующая)
        """
        if date is None:
            date = get_yekaterinburg_date()

        try:
            if is_head:
                # Для руководителя - показываем его группу
                group_members = await self.group_parser.get_group_members_for_head(
                    user.fullname, date, user.division, stp_repo
                )
                return self.group_parser.format_group_schedule_for_head(
                    date, group_members, page
                )
            else:
                # Для обычного пользователя - показываем коллег по группе
                group_members = await self.group_parser.get_group_members_for_user(
                    user.fullname, date, user.division, stp_repo
                )
                return self.group_parser.format_group_schedule_for_user(
                    date, group_members, page
                )

        except Exception as e:
            logger.error(f"Ошибка получения группового расписания: {e}")
            return "❌ Ошибка получения расписания группы", 1, False, False


# Создаем единственный экземпляр сервиса
schedule_service = ScheduleHandlerService()


@user_schedule_router.callback_query(MainMenu.filter(F.menu == "schedule"))
async def schedule(callback: CallbackQuery, user: Employee):
    """Главное меню расписаний"""
    if not await schedule_service.check_user_auth(callback, user):
        return

    await callback.message.edit_text(
        """<b>📅 Меню графиков</b>
        
Здесь ты найдешь все, что связано с графиками""",
        reply_markup=schedule_kb(),
    )
