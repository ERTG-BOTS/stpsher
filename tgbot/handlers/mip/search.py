import datetime
import logging
import re
from typing import Sequence

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    Message,
)

from infrastructure.api.production_calendar import production_calendar
from infrastructure.database.models import Employee
from infrastructure.database.repo.KPI.requests import KPIRequestsRepo
from infrastructure.database.repo.STP.requests import MainRequestsRepo
from tgbot.filters.role import MipFilter
from tgbot.handlers.user.schedule.main import schedule_service
from tgbot.keyboards.mip.search import (
    EditUserMenu,
    HeadGroupMembersMenuForSearch,
    HeadGroupMenu,
    HeadMemberActionMenuForSearch,
    HeadMemberDetailMenuForSearch,
    HeadMemberRoleChangeForSearch,
    MipScheduleNavigation,
    SearchMemberScheduleMenu,
    SearchMemberScheduleNavigation,
    SearchMenu,
    SearchUserResult,
    SelectUserRole,
    ViewUserSchedule,
    edit_user_back_kb,
    get_month_name_by_index,
    head_group_members_kb_for_search,
    head_member_detail_kb_for_search,
    role_selection_kb,
    search_back_kb,
    search_main_kb,
    search_member_schedule_kb,
    search_results_kb,
    user_detail_kb,
    user_schedule_with_month_kb,
)
from tgbot.keyboards.mip.search_kpi import (
    SearchMemberKPIMenu,
    SearchUserKPIMenu,
    search_member_kpi_kb,
    search_user_kpi_kb,
)
from tgbot.keyboards.user.main import MainMenu
from tgbot.misc.dicts import role_names, russian_months
from tgbot.misc.states.mip.search import EditEmployee, SearchEmployee
from tgbot.services.leveling import LevelingSystem
from tgbot.services.schedule import ScheduleParser

mip_search_router = Router()
mip_search_router.message.filter(F.chat.type == "private", MipFilter())
mip_search_router.callback_query.filter(F.message.chat.type == "private", MipFilter())

logger = logging.getLogger(__name__)

# Константы для пагинации
USERS_PER_PAGE = 10


def filter_users_by_type(users: Sequence[Employee], search_type: str) -> list[Employee]:
    """
    Фильтрация пользователей по типу поиска

    :param users: Список пользователей
    :param search_type: Тип поиска (specialists, heads, all)
    :return: Отфильтрованный список пользователей
    """
    if search_type == "specialists":
        # Специалисты - роль 1 (обычные пользователи)
        return [user for user in users if user.role == 1]
    elif search_type == "heads":
        # Руководители - роль 2 (головы)
        return [user for user in users if user.role == 2]
    else:
        # Все пользователи
        return list(users)


async def get_user_statistics(user_id: int, stp_repo: MainRequestsRepo) -> dict:
    """Получить статистику пользователя (уровень, очки, достижения, покупки)"""
    try:
        # Получаем базовые данные
        user_purchases = await stp_repo.purchase.get_user_purchases(user_id)
        achievements_sum = await stp_repo.transaction.get_user_achievements_sum(user_id)
        purchases_sum = await stp_repo.purchase.get_user_purchases_sum(user_id)

        # Рассчитываем уровень
        user_balance = await stp_repo.transaction.get_user_balance(user_id)
        current_level = LevelingSystem.calculate_level(achievements_sum)

        return {
            "level": current_level,
            "balance": user_balance,
            "total_earned": achievements_sum,
            "total_spent": purchases_sum,
            "purchases_count": len(user_purchases),
        }
    except Exception as e:
        logger.error(f"Ошибка получения статистики пользователя {user_id}: {e}")
        return {
            "level": 0,
            "balance": 0,
            "total_earned": 0,
            "total_spent": 0,
            "purchases_count": 0,
        }


async def get_group_statistics(head_name: str, stp_repo: MainRequestsRepo) -> dict:
    """Получить общую статистику группы руководителя"""
    try:
        # Получаем сотрудников группы
        group_users = await stp_repo.employee.get_users_by_head(head_name)

        total_points = 0
        group_purchases = {}

        for user in group_users:
            if user.user_id:  # Только авторизованные пользователи
                # Суммируем очки
                achievements_sum = await stp_repo.transaction.get_user_achievements_sum(
                    user.user_id
                )
                total_points += achievements_sum

                # Собираем статистику предметов
                most_bought_product = await stp_repo.purchase.get_most_bought_product(
                    user.user_id
                )
                if most_bought_product:
                    product_name = most_bought_product[0]
                    product_count = most_bought_product[1]
                    group_purchases[product_name] = (
                        group_purchases.get(product_name, 0) + product_count
                    )

        return {
            "total_users": len(group_users),
            "total_points": total_points,
        }
    except Exception as e:
        logger.error(f"Ошибка получения статистики группы {head_name}: {e}")
        return {
            "total_users": 0,
            "total_points": 0,
        }


async def get_group_statistics_by_id(
    head_user_id: int, stp_repo: MainRequestsRepo
) -> dict:
    """Получить общую статистику группы руководителя по его ID"""
    try:
        # Получаем руководителя по ID
        head_user = await stp_repo.employee.get_user(user_id=head_user_id)
        if not head_user:
            return {
                "total_users": 0,
                "total_points": 0,
                "most_popular_achievement": None,
                "most_popular_product": None,
            }

        # Используем существующую функцию
        return await get_group_statistics(head_user.fullname, stp_repo)
    except Exception as e:
        logger.error(f"Ошибка получения статистики группы по ID {head_user_id}: {e}")
        return {
            "total_users": 0,
            "total_points": 0,
            "most_popular_achievement": None,
            "most_popular_product": None,
        }


@mip_search_router.callback_query(MainMenu.filter(F.menu == "search"))
async def search_main_menu(callback: CallbackQuery, state: FSMContext):
    """Главное меню поиска сотрудников"""
    await state.clear()
    await callback.message.edit_text(
        """<b>🕵🏻 Поиск сотрудника</b>

<i>Выбери должность искомого человека или воспользуйся общим поиском</i>""",
        reply_markup=search_main_kb(),
    )


@mip_search_router.callback_query(SearchMenu.filter(F.menu == "specialists"))
async def show_specialists(
    callback: CallbackQuery, callback_data: SearchMenu, stp_repo: MainRequestsRepo
):
    """Показать всех специалистов с пагинацией"""
    page = callback_data.page

    # Получаем всех пользователей и фильтруем специалистов
    all_users = await stp_repo.employee.get_users()
    if not all_users:
        await callback.answer("❌ Пользователи не найдены", show_alert=True)
        return

    specialists = filter_users_by_type(all_users, "specialists")

    if not specialists:
        await callback.answer("❌ Специалисты не найдены", show_alert=True)
        return

    # Пагинация
    total_users = len(specialists)
    total_pages = (total_users + USERS_PER_PAGE - 1) // USERS_PER_PAGE

    start_idx = (page - 1) * USERS_PER_PAGE
    end_idx = start_idx + USERS_PER_PAGE
    page_users = specialists[start_idx:end_idx]

    await callback.message.edit_text(
        f"""<b>👤 Специалисты</b>

Найдено специалистов: {total_users}
Страница {page} из {total_pages}""",
        reply_markup=search_results_kb(page_users, page, total_pages, "specialists"),
    )


@mip_search_router.callback_query(SearchMenu.filter(F.menu == "heads"))
async def show_heads(
    callback: CallbackQuery, callback_data: SearchMenu, stp_repo: MainRequestsRepo
):
    """Показать всех руководителей с пагинацией"""
    page = callback_data.page

    # Получаем всех пользователей и фильтруем руководителей
    all_users = await stp_repo.employee.get_users()
    if not all_users:
        await callback.answer("❌ Пользователи не найдены", show_alert=True)
        return

    heads = filter_users_by_type(all_users, "heads")

    if not heads:
        await callback.answer("❌ Руководители не найдены", show_alert=True)
        return

    # Пагинация
    total_users = len(heads)
    total_pages = (total_users + USERS_PER_PAGE - 1) // USERS_PER_PAGE

    start_idx = (page - 1) * USERS_PER_PAGE
    end_idx = start_idx + USERS_PER_PAGE
    page_users = heads[start_idx:end_idx]

    await callback.message.edit_text(
        f"""<b>👑 Руководители</b>

Найдено руководителей: {total_users}
Страница {page} из {total_pages}

<i>💡 Нажми на руководителя, чтобы увидеть его группу</i>""",
        reply_markup=search_results_kb(page_users, page, total_pages, "heads"),
    )


@mip_search_router.callback_query(SearchMenu.filter(F.menu == "start_search"))
async def start_search(callback: CallbackQuery, state: FSMContext):
    """Начать поиск по имени"""
    bot_message = await callback.message.edit_text(
        """<b>🔍 Поиск сотрудника</b>

Введи часть имени, фамилии или полное ФИО сотрудника:

<i>Например: Иванов, Иван, Иванов И, Иванов Иван и т.д.</i>""",
        reply_markup=search_back_kb(),
    )

    await state.update_data(bot_message_id=bot_message.message_id)
    await state.set_state(SearchEmployee.waiting_search_query)


@mip_search_router.message(SearchEmployee.waiting_search_query)
async def process_search_query(
    message: Message, state: FSMContext, stp_repo: MainRequestsRepo
):
    """Обработка поискового запроса"""
    search_query = message.text.strip()
    state_data = await state.get_data()
    bot_message_id = state_data.get("bot_message_id")

    # Удаляем сообщение пользователя
    await message.delete()

    if not search_query or len(search_query) < 2:
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=bot_message_id,
            text="""<b>🔍 Поиск сотрудника</b>

❌ Поисковый запрос слишком короткий (минимум 2 символа)

Введи часть имени, фамилии или полное ФИО сотрудника:

<i>Например: Иванов, Иван, Иванов И, Иванов Иван и т.д.</i>""",
            reply_markup=search_back_kb(),
        )
        return

    try:
        # Поиск пользователей по частичному совпадению ФИО
        found_users = await stp_repo.employee.get_users_by_fio_parts(
            search_query, limit=50
        )

        if not found_users:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=bot_message_id,
                text=f"""<b>🔍 Поиск сотрудника</b>

❌ По запросу "<code>{search_query}</code>" ничего не найдено

Попробуй другой запрос или проверь правильность написания

<i>Например: Иванов, Иван, Иванов И, Иванов Иван и т.д.</i>""",
                reply_markup=search_back_kb(),
            )
            return

        # Сортировка результатов (сначала точные совпадения)
        sorted_users = sorted(
            found_users,
            key=lambda u: (
                # Сначала полные совпадения
                search_query.lower() not in u.fullname.lower(),
                # Потом по алфавиту
                u.fullname,
            ),
        )

        # Пагинация результатов
        total_found = len(sorted_users)
        total_pages = (total_found + USERS_PER_PAGE - 1) // USERS_PER_PAGE
        page_users = sorted_users[:USERS_PER_PAGE]

        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=bot_message_id,
            text=f"""<b>🔍 Результаты поиска</b>

По запросу "<code>{search_query}</code>" найдено: {total_found} сотрудников
Страница 1 из {total_pages}""",
            reply_markup=search_results_kb(
                page_users, 1, total_pages, "search_results"
            ),
        )

        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка при поиске пользователей: {e}")
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=bot_message_id,
            text="""<b>🔍 Поиск сотрудника</b>

❌ Произошла ошибка при поиске. Попробуй позже

<i>Например: Иванов, Иван, Иванов И, Иванов Иван и т.д.</i>""",
            reply_markup=search_back_kb(),
        )


@mip_search_router.callback_query(SearchUserResult.filter())
async def show_user_details(
    callback: CallbackQuery, callback_data: SearchUserResult, stp_repo: MainRequestsRepo
):
    """Показать детальную информацию о найденном пользователе"""
    user_id = callback_data.user_id
    return_to = callback_data.return_to
    head_id = callback_data.head_id

    try:
        user = await stp_repo.employee.get_user(user_id=user_id)
        user_head = await stp_repo.employee.get_user(fullname=user.head)

        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        if not user_head:
            await callback.answer(
                "❌ Не найдена информация о руководителя пользователя", show_alert=True
            )
            return

        # Определение роли
        role_name = role_names.get(user.role, "Неизвестная роль")

        # Получаем статистику пользователя
        stats = await get_user_statistics(user_id, stp_repo)

        # Формирование информации о пользователе
        user_info = f"""<b>👤 Информация о сотруднике</b>

<b>ФИО:</b> <a href='t.me/{user.username}'>{user.fullname}</a>
<b>Должность:</b> {user.position} {user.division}
<b>Руководитель:</b> <a href='t.me/{user_head.username}'>{user.head}</a>

🛡️<b>Уровень доступа:</b> {role_name} ({user.role})"""

        if user.email:
            user_info += f"\n<b>Рабочая почта:</b> {user.email}"

        # Добавляем статистику уровня (только для специалистов и дежурных)
        if user.user_id and user.role in [1, 3]:
            user_info += f"""

<blockquote expandable><b>📊 Статистика игрока</b>
<b>⚔️ Уровень:</b> {stats["level"]}
<b>✨ Баланс:</b> {stats["balance"]} баллов
<b>📈 Всего заработано:</b> {stats["total_earned"]} баллов
<b>💸 Всего потрачено:</b> {stats["total_spent"]} баллов</blockquote>"""

        # Дополнительная информация для руководителей
        if user.role == 2:  # Руководитель
            group_stats = await get_group_statistics(user.fullname, stp_repo)

            user_info += f"""

<blockquote expandable><b>👥 Статистика группы</b>
<b>Сотрудников в группе:</b> {group_stats["total_users"]}
<b>Общие очки группы:</b> {group_stats["total_points"]} баллов</blockquote>

<i>💡 Нажми кнопку ниже чтобы увидеть список группы</i>"""

        # Определяем возможность редактирования и параметры клавиатуры
        can_edit = user.role in [1, 2, 3]  # Специалисты, дежурные и руководители
        is_head = user.role == 2  # Руководитель
        head_user_id = user.user_id if is_head else 0

        await callback.message.edit_text(
            user_info,
            reply_markup=user_detail_kb(
                user_id, return_to, head_id, can_edit, is_head, head_user_id
            ),
        )

    except Exception as e:
        logger.error(f"Ошибка при получении информации о пользователе: {e}")
        await callback.answer("❌ Ошибка при получении данных", show_alert=True)


@mip_search_router.callback_query(HeadGroupMenu.filter())
async def show_head_group(
    callback: CallbackQuery, callback_data: HeadGroupMenu, stp_repo: MainRequestsRepo
):
    """Показать группу руководителя (список его сотрудников) с использованием функциональности head group members"""
    head_id = callback_data.head_id
    page = callback_data.page

    try:
        # Получаем информацию о руководителе по user_id
        head_user = await stp_repo.employee.get_user(user_id=head_id)
        if not head_user:
            await callback.answer("❌ Руководитель не найден", show_alert=True)
            return

        # Получаем всех сотрудников этого руководителя
        group_members = await stp_repo.employee.get_users_by_head(head_user.fullname)

        if not group_members:
            await callback.message.edit_text(
                f"""👥 <b>Группа: {head_user.fullname}</b>

У этого руководителя пока нет подчиненных в системе
            
<i>Если это ошибка, обратись к администратору.</i>""",
                reply_markup=head_group_members_kb_for_search(
                    [], current_page=1, head_id=head_id
                ),
            )
            return

        # Показываем группу с использованием того же стиля, что и в head group members
        total_members = len(group_members)

        message_text = f"""👥 <b>Группа: {head_user.fullname}</b>

Участники группы: <b>{total_members}</b>

<blockquote><b>Обозначения</b>
🔒 - не авторизован в боте
👮 - дежурный
🔨 - root</blockquote>

<i>Нажми на участника для просмотра подробной информации</i>"""

        await callback.message.edit_text(
            message_text,
            reply_markup=head_group_members_kb_for_search(
                group_members, current_page=page, head_id=head_id
            ),
        )

    except Exception as e:
        logger.error(f"Ошибка при получении группы руководителя {head_id}: {e}")
        await callback.answer("❌ Ошибка при получении данных группы", show_alert=True)


@mip_search_router.callback_query(EditUserMenu.filter())
async def start_edit_user(
    callback: CallbackQuery,
    callback_data: EditUserMenu,
    state: FSMContext,
    stp_repo: MainRequestsRepo,
):
    """Начать редактирование данных пользователя"""
    user_id = callback_data.user_id
    action = callback_data.action

    if action == "edit_fullname":
        # Получаем текущие данные пользователя
        user = await stp_repo.employee.get_user(user_id=user_id)
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        bot_message = await callback.message.edit_text(
            f"""<b>✏️ Изменение ФИО</b>

<b>Текущее ФИО:</b> {user.fullname}

Введи новое ФИО:

<i>Например: Иванов Иван Иванович</i>""",
            reply_markup=edit_user_back_kb(user_id),
        )

        await state.update_data(
            bot_message_id=bot_message.message_id,
            user_id=user_id,
            current_fullname=user.fullname,
        )
        await state.set_state(EditEmployee.waiting_new_fullname)

    elif action == "edit_role":
        # Получаем текущие данные пользователя
        user = await stp_repo.employee.get_user(user_id=user_id)
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        # Получаем название текущей роли
        current_role_name = (
            role_names[user.role]
            if user.role < len(role_names)
            else f"Неизвестная роль ({user.role})"
        )

        await callback.message.edit_text(
            f"""🛡️ <b>Изменение уровня доступа</b>

<b>Сотрудник:</b> <a href='t.me/{user.username}'>{user.fullname}</a>
<b>Текущий уровень доступа:</b> {current_role_name}

Выбери новую уровень для пользователя:

<i>Пользователь получит уведомление об изменении</i>""",
            reply_markup=role_selection_kb(user_id, user.role),
        )


@mip_search_router.message(EditEmployee.waiting_new_fullname)
async def process_edit_fullname(
    message: Message, state: FSMContext, stp_repo: MainRequestsRepo
):
    """Обработка изменения ФИО пользователя"""
    import re

    new_fullname = message.text.strip()
    state_data = await state.get_data()
    bot_message_id = state_data.get("bot_message_id")
    user_id = state_data.get("user_id")
    current_fullname = state_data.get("current_fullname")

    # Удаляем сообщение пользователя
    await message.delete()

    # Валидация ФИО
    fullname_pattern = r"^[А-Яа-яЁё]+ [А-Яа-яЁё]+ [А-Яа-яЁё]+$"
    if not re.match(fullname_pattern, new_fullname):
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=bot_message_id,
            text=f"""<b>✏️ Изменение ФИО</b>

<b>Текущее ФИО:</b> {current_fullname}

❌ Неверный формат ФИО. Попробуй ещё раз:

<i>Например: Иванов Иван Иванович</i>""",
            reply_markup=edit_user_back_kb(user_id),
        )
        return

    try:
        # Обновляем ФИО в базе данных
        await stp_repo.employee.update_user(user_id=user_id, fullname=new_fullname)

        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=bot_message_id,
            text=f"""<b>✅ ФИО изменено</b>

<b>Было:</b> <code>{current_fullname}</code>
<b>Стало:</b> <code>{new_fullname}</code>

Изменения сохранены в базе данных.""",
            reply_markup=edit_user_back_kb(user_id),
        )

        await state.clear()
        logger.info(
            f"[МИП] - [Изменение ФИО] {message.from_user.username} ({message.from_user.id}) изменил ФИО пользователя {user_id}: {current_fullname} → {new_fullname}"
        )

    except Exception as e:
        logger.error(f"Ошибка при изменении ФИО пользователя {user_id}: {e}")
        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=bot_message_id,
            text=f"""<b>✏️ Изменение ФИО</b>

❌ Произошла ошибка при сохранении. Попробуй позже

<b>Текущее ФИО:</b> {current_fullname}""",
            reply_markup=edit_user_back_kb(user_id),
        )


@mip_search_router.callback_query(SearchUserKPIMenu.filter())
async def search_user_kpi_menu(
    callback: CallbackQuery,
    callback_data: SearchUserKPIMenu,
    stp_repo: MainRequestsRepo,
    kpi_repo: KPIRequestsRepo,
):
    """Полноценное KPI меню для пользователя из поиска"""
    user_id = callback_data.user_id
    action = callback_data.action
    return_to = callback_data.return_to
    head_id = callback_data.head_id

    try:
        # Получаем пользователя
        user = await stp_repo.employee.get_user(user_id=user_id)
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        # Получаем KPI данные пользователя
        try:
            premium = await kpi_repo.spec_premium.get_premium(fullname=user.fullname)

            if premium is None:
                message_text = f"""📊 <b>KPI: {user.fullname}</b>

❌ <b>Данные KPI не найдены</b>

Показатели эффективности для этого сотрудника отсутствуют в системе или не загружены.

<i>Обратись к администратору для проверки данных</i>"""

                await callback.message.edit_text(
                    message_text,
                    reply_markup=search_user_kpi_kb(
                        user_id, return_to, head_id, action
                    ),
                )
                return

            def format_value(value, suffix=""):
                return f"{value}{suffix}" if value is not None else "—"

            def format_percentage(value):
                return f"{value}%" if value is not None else "—"

            if action == "main":
                message_text = f"""🌟 <b>Показатели</b>

<b>ФИО:</b> <a href="https://t.me/{user.username}">{user.fullname}</a>
<b>Подразделение:</b> {user.position or "Не указано"} {user.division or "Не указано"}

📊 <b>Оценка клиента - {format_percentage(premium.csi_premium)}</b>
<blockquote>Факт: {format_value(premium.csi)}
План: {format_value(premium.csi_normative)}</blockquote>

🎯 <b>Отклик</b>
<blockquote>Факт: {format_value(premium.csi_response)}
План: {format_value(round(premium.csi_response_normative)) if premium.csi_response_normative else "—"}</blockquote>

🔧 <b>FLR - {format_percentage(premium.flr_premium)}</b>
<blockquote>Факт: {format_value(premium.flr)}
План: {format_value(premium.flr_normative)}</blockquote>

⚖️ <b>ГОК - {format_percentage(premium.gok_premium)}</b>
<blockquote>Факт: {format_value(premium.gok)}
План: {format_value(premium.gok_normative)}</blockquote>

🎯 <b>Цель - {format_percentage(premium.target_premium)}</b>
<blockquote>Тип: {premium.target_type or "—"}
Факт: {format_value(premium.target)}
План: {format_value(round(premium.target_goal_first)) if premium.target_goal_first else "—"} / {format_value(round(premium.target_goal_second)) if premium.target_goal_second else "—"}</blockquote>

💼 <b>Дополнительно</b>
<blockquote>Дисциплина: {format_percentage(premium.discipline_premium)}
Тестирование: {format_percentage(premium.tests_premium)}
Благодарности: {format_percentage(premium.thanks_premium)}
Наставничество: {format_percentage(premium.tutors_premium)}
Ручная правка: {format_percentage(premium.head_adjust_premium)}</blockquote>

💰 <b>Итого:</b>
<b>Общая премия: {format_percentage(premium.total_premium)}</b>

{"📈 Всего чатов: " + format_value(premium.contacts_count) if user.division == "НЦК" else "📈 Всего звонков: " + format_value(premium.contacts_count)}
{"⏰ Задержка: " + format_value(premium.delay, " сек") if user.division != "НЦК" else ""}

<i>Выгружено: {premium.updated_at.strftime("%d.%m.%y %H:%M") if premium.updated_at else "—"}</i>"""

            elif action == "calculator":
                def calculate_csi_needed(division: str, current_csi, normative):
                    if normative == 0 or normative is None:
                        return "—"

                    current_csi = current_csi or 0

                    results = []

                    if division == "НЦК":
                        thresholds = [
                            (101, 20, "≥ 101%"),
                            (100.5, 15, "≥ 100,5%"),
                            (100, 10, "≥ 100%"),
                            (98, 5, "≥ 98%"),
                            (0, 0, "&lt; 98%"),
                        ]
                    elif division == "НТП1":
                        thresholds = [
                            (101, 20, "≥ 101%"),
                            (100.5, 15, "≥ 100,5%"),
                            (100, 10, "≥ 100%"),
                            (98, 5, "≥ 98%"),
                            (0, 0, "&lt; 98%"),
                        ]
                    else:
                        thresholds = [
                            (100.8, 20, "≥ 100.8%"),
                            (100.4, 15, "≥ 100.4%"),
                            (100, 10, "≥ 100%"),
                            (98, 5, "≥ 98%"),
                            (0, 0, "&lt; 98%"),
                        ]

                    for threshold, premium_percent, description in thresholds:
                        needed_csi = (threshold / 100) * normative

                        if current_csi >= needed_csi:
                            results.append(f"{premium_percent}%: ✅ ({description})")
                        else:
                            difference = needed_csi - current_csi
                            results.append(
                                f"{premium_percent}%: {needed_csi:.3f} [+{difference:.3f}] ({description})"
                            )

                    return "\n".join(results)

                def calculate_flr_needed(division: str, current_flr, normative):
                    if normative == 0 or normative is None:
                        return "—"

                    current_flr = current_flr or 0

                    results = []

                    if division == "НЦК":
                        thresholds = [
                            (103, 30, "≥ 103%"),
                            (102, 25, "≥ 102%"),
                            (101, 21, "≥ 101%"),
                            (100, 18, "≥ 100%"),
                            (95, 13, "≥ 95%"),
                            (0, 8, "&lt; 95%"),
                        ]
                    elif division == "НТП1":
                        thresholds = [
                            (109, 30, "≥ 109%"),
                            (106, 25, "≥ 106%"),
                            (103, 21, "≥ 103%"),
                            (100, 18, "≥ 100%"),
                            (90, 13, "≥ 90%"),
                            (0, 8, "&lt; 90%"),
                        ]
                    else:
                        thresholds = [
                            (107, 30, "≥ 107%"),
                            (104, 25, "≥ 104%"),
                            (102, 21, "≥ 102%"),
                            (100, 18, "≥ 100%"),
                            (97, 13, "≥ 97%"),
                            (0, 8, "&lt; 97%"),
                        ]

                    for threshold, premium_percent, description in thresholds:
                        needed_flr = (threshold / 100) * normative

                        if current_flr >= needed_flr:
                            results.append(f"{premium_percent}%: ✅ ({description})")
                        else:
                            difference = needed_flr - current_flr
                            results.append(
                                f"{premium_percent}%: {needed_flr:.2f} [+{difference:.2f}] ({description})"
                            )

                    return "\n".join(results)

                def calculate_gok_needed(division: str, current_gok, normative):
                    if normative == 0 or normative is None:
                        return "—"

                    current_gok = current_gok or 0

                    results = []

                    if division == "НЦК":
                        thresholds = [
                            (100, 17, "≥ 100%"),
                            (95, 15, "≥ 95%"),
                            (90, 12, "≥ 90%"),
                            (85, 9, "≥ 85%"),
                            (80, 5, "≥ 80%"),
                            (0, 0, "&lt; 80%"),
                        ]
                    elif division == "НТП1":
                        thresholds = [
                            (100, 17, "≥ 100%"),
                            (95, 15, "≥ 95%"),
                            (90, 12, "≥ 90%"),
                            (85, 9, "≥ 85%"),
                            (80, 5, "≥ 80%"),
                            (0, 0, "&lt; 80%"),
                        ]
                    else:
                        thresholds = [
                            (100, 17, "≥ 100%"),
                            (95, 15, "≥ 95%"),
                            (90, 12, "≥ 90%"),
                            (84, 9, "≥ 84%"),
                            (70, 5, "≥ 70%"),
                            (0, 0, "&lt; 70%"),
                        ]

                    for threshold, premium_percent, description in thresholds:
                        needed_gok = (threshold / 100) * normative

                        if current_gok >= needed_gok:
                            results.append(f"{premium_percent}%: ✅ ({description})")
                        else:
                            difference = needed_gok - current_gok
                            results.append(
                                f"{premium_percent}%: {needed_gok:.3f} [+{difference:.3f}] ({description})"
                            )

                    return "\n".join(results)

                def calculate_target_needed(
                    current_target,
                    target_goal_first,
                    target_goal_second,
                    target_type=None,
                ):
                    if target_goal_first is None and target_goal_second is None:
                        return "—"

                    current_target = current_target or 0

                    # Determine if this is a sales target (higher is better) or AHT target (lower is better)
                    is_sales_target = (
                        target_type and "Продажа оборудования" in target_type
                    )
                    is_aht_target = target_type and "AHT" in target_type

                    results = []

                    # All divisions have the same target premium thresholds
                    if target_goal_second and target_goal_second > 0:
                        # When there's a second goal, use it as the main normative
                        normative = target_goal_second

                        if is_aht_target:
                            # For AHT, lower is better - calculate percentage as (normative / current * 100)
                            target_rate = (
                                (normative / current_target * 100)
                                if current_target > 0
                                else 0
                            )
                        elif is_sales_target:
                            # For sales, higher is better - calculate percentage as (current / normative * 100)
                            target_rate = (
                                (current_target / normative * 100)
                                if normative > 0
                                else 0
                            )
                        else:
                            # Default behavior (higher is better) - calculate percentage as (current / normative * 100)
                            target_rate = (
                                (current_target / normative * 100)
                                if normative > 0
                                else 0
                            )

                        if target_rate > 100.01:
                            results.append("28%: ✅ (≥ 100,01% - план 2 и более)")
                        else:
                            if is_aht_target:
                                # For AHT, we need to be lower than the target
                                needed_for_28 = normative / (100.01 / 100)
                                difference = current_target - needed_for_28
                                results.append(
                                    f"28%: {needed_for_28:.2f} [-{difference:.2f}] (≥ 100,01% - план 2 и более)"
                                )
                            else:
                                # For sales, we need to be higher than the target
                                needed_for_28 = (100.01 / 100) * normative
                                difference = needed_for_28 - current_target
                                results.append(
                                    f"28%: {needed_for_28:.2f} [+{difference:.2f}] (≥ 100,01% - план 2 и более)"
                                )

                        if target_rate >= 100.00:
                            results.append(
                                "18%: ✅ (≥ 100,00% - план 1 и менее плана 2)"
                            )
                        else:
                            if is_aht_target:
                                needed_for_18 = normative / (100.00 / 100)
                                difference = current_target - needed_for_18
                                results.append(
                                    f"18%: {needed_for_18:.2f} [-{difference:.2f}] (= 100,00% - план 1 и менее плана 2)"
                                )
                            else:
                                needed_for_18 = (100.00 / 100) * normative
                                difference = needed_for_18 - current_target
                                results.append(
                                    f"18%: {needed_for_18:.2f} [+{difference:.2f}] (= 100,00% - план 1 и менее плана 2)"
                                )

                        if target_rate < 99.99:
                            results.append("0%: — (&lt; 99,99% - менее плана 1)")
                        else:
                            results.append("0%: ✅ (&lt; 99,99% - менее плана 1)")

                    elif target_goal_first and target_goal_first > 0:
                        # When there's only first goal, use it as normative
                        normative = target_goal_first

                        if is_aht_target:
                            # For AHT, lower is better
                            target_rate = (
                                (normative / current_target * 100)
                                if current_target > 0
                                else 0
                            )
                        elif is_sales_target:
                            # For sales, higher is better
                            target_rate = (
                                (current_target / normative * 100)
                                if normative > 0
                                else 0
                            )
                        else:
                            # Default behavior (higher is better)
                            target_rate = (
                                (current_target / normative * 100)
                                if normative > 0
                                else 0
                            )

                        if target_rate > 100.01:
                            results.append("28%: ✅ (≥ 100,01% - план 2 и более)")
                        else:
                            if is_aht_target:
                                needed_for_28 = normative / (100.01 / 100)
                                difference = current_target - needed_for_28
                                results.append(
                                    f"28%: {needed_for_28:.2f} [-{difference:.2f}] (≥ 100,01% - план 2 и более)"
                                )
                            else:
                                needed_for_28 = (100.01 / 100) * normative
                                difference = needed_for_28 - current_target
                                results.append(
                                    f"28%: {needed_for_28:.2f} [+{difference:.2f}] (≥ 100,01% - план 2 и более)"
                                )

                        if target_rate >= 100.00:
                            results.append(
                                "18%: ✅ (≥ 100,00% - план 1 и менее плана 2)"
                            )
                        else:
                            if is_aht_target:
                                needed_for_18 = normative / (100.00 / 100)
                                difference = current_target - needed_for_18
                                results.append(
                                    f"18%: {needed_for_18:.2f} [-{difference:.2f}] (≥ 100,00% - план 1 и менее плана 2)"
                                )
                            else:
                                needed_for_18 = (100.00 / 100) * normative
                                difference = needed_for_18 - current_target
                                results.append(
                                    f"18%: {needed_for_18:.2f} [+{difference:.2f}] (≥ 100,00% - план 1 и менее плана 2)"
                                )

                        if target_rate < 99.99:
                            results.append("0%: — (&lt; 99,99% - менее плана 1)")
                        else:
                            results.append("0%: ✅ (&lt; 99,99% - менее плана 1)")

                    return "\n".join(results)

                csi_calculation = calculate_csi_needed(
                    user.division, premium.csi, premium.csi_normative
                )
                flr_calculation = calculate_flr_needed(
                    user.division, premium.flr, premium.flr_normative
                )
                gok_calculation = calculate_gok_needed(
                    user.division, premium.gok, premium.gok_normative
                )
                target_calculation = calculate_target_needed(
                    premium.target,
                    premium.target_goal_first,
                    premium.target_goal_second,
                    premium.target_type,
                )

                message_text = f"""🧮 <b>Калькулятор KPI</b>

<b>ФИО:</b> <a href="https://t.me/{user.username}">{user.fullname}</a>
<b>Подразделение:</b> {user.position or "Не указано"} {user.division or "Не указано"}

📊 <b>Оценка клиента</b>
<blockquote>Текущий: {format_value(premium.csi)} ({format_percentage(premium.csi_normative_rate)})
План: {format_value(premium.csi_normative)}

<b>Для премии:</b>
{csi_calculation}</blockquote>

🔧 <b>FLR</b>
<blockquote>Текущий: {format_value(premium.flr)} ({format_percentage(premium.flr_normative_rate)})
План: {format_value(premium.flr_normative)}

<b>Для премии:</b>
{flr_calculation}</blockquote>

⚖️ <b>ГОК</b>
<blockquote>Текущий: {format_value(round(premium.gok))} ({format_percentage(premium.gok_normative_rate)})
План: {format_value(round(premium.gok_normative))}

<b>Для премии:</b>
{gok_calculation}</blockquote>

🎯 <b>Цель</b>
<blockquote>Факт: {format_value(premium.target)} ({format_percentage(round((premium.target_goal_first / premium.target * 100) if premium.target_type and "AHT" in premium.target_type and premium.target and premium.target > 0 and premium.target_goal_first else (premium.target / premium.target_goal_first * 100) if premium.target_goal_first and premium.target_goal_first > 0 else 0))} / {format_percentage(round((premium.target_goal_second / premium.target * 100) if premium.target_type and "AHT" in premium.target_type and premium.target and premium.target > 0 and premium.target_goal_second else (premium.target / premium.target_goal_second * 100) if premium.target_goal_second and premium.target_goal_second > 0 else 0))})
План: {format_value(round(premium.target_goal_first))} / {format_value(round(premium.target_goal_second))}

Требуется минимум 100 {"чатов" if user.division == "НЦК" else "звонков"} для получения премии за цель

<b>Для премии:</b>
{target_calculation}</blockquote>

<i>Данные от: {premium.updated_at.strftime("%d.%m.%y %H:%M") if premium.updated_at else "—"}</i>"""

            elif action == "salary":
                # Реализация расчета зарплаты аналогично пользовательскому
                def format_value(value, suffix=""):
                    return f"{value}{suffix}" if value is not None else "—"

                def format_percentage(value):
                    return f"{value}%" if value is not None else "—"

                pay_rate = 0.0
                match user.division:
                    case "НЦК":
                        match user.position:
                            case "Специалист":
                                pay_rate = 156.7
                            case "Ведущий специалист":
                                pay_rate = 164.2
                            case "Эксперт":
                                pay_rate = 195.9
                    case "НТП1":
                        match user.position:
                            case "Специалист первой линии":
                                pay_rate = 143.6
                    case "НТП2":
                        match user.position:
                            case "Специалист второй линии":
                                pay_rate = 166
                            case "Ведущий специалист второй линии":
                                pay_rate = 181
                            case "Эксперт второй линии":
                                pay_rate = 195.9

                # Get current month working hours from actual schedule
                now = datetime.datetime.now(
                    datetime.timezone(datetime.timedelta(hours=5))
                )
                current_month_name = russian_months[now.month]

                def calculate_night_hours(start_hour, start_min, end_hour, end_min):
                    """Calculate night hours (22:00-06:00) from a work shift"""
                    start_minutes = start_hour * 60 + start_min
                    end_minutes = end_hour * 60 + end_min

                    # Handle overnight shifts
                    if end_minutes < start_minutes:
                        end_minutes += 24 * 60

                    night_start = 22 * 60  # 22:00 in minutes
                    night_end = 6 * 60  # 06:00 in minutes (next day)

                    total_night_minutes = 0

                    # Check for night hours in first day (22:00-24:00)
                    first_day_night_start = night_start
                    first_day_night_end = 24 * 60  # Midnight

                    if (
                        start_minutes < first_day_night_end
                        and end_minutes > first_day_night_start
                    ):
                        overlap_start = max(start_minutes, first_day_night_start)
                        overlap_end = min(end_minutes, first_day_night_end)
                        if overlap_end > overlap_start:
                            total_night_minutes += overlap_end - overlap_start

                    # Check for night hours in second day (00:00-06:00)
                    if end_minutes > 24 * 60:  # Shift continues to next day
                        second_day_start = 24 * 60
                        second_day_end = end_minutes
                        second_day_night_start = 24 * 60  # 00:00 next day
                        second_day_night_end = 24 * 60 + night_end  # 06:00 next day

                        if (
                            second_day_start < second_day_night_end
                            and second_day_end > second_day_night_start
                        ):
                            overlap_start = max(
                                second_day_start, second_day_night_start
                            )
                            overlap_end = min(second_day_end, second_day_night_end)
                            if overlap_end > overlap_start:
                                total_night_minutes += overlap_end - overlap_start

                    return total_night_minutes / 60  # Convert to hours

                # Get actual schedule data with additional shifts detection
                schedule_parser = ScheduleParser()
                try:
                    schedule_data, additional_shifts_data = (
                        schedule_parser.get_user_schedule_with_additional_shifts(
                            user.fullname, current_month_name, user.division
                        )
                    )

                    # Calculate actual working hours from schedule with holiday detection
                    total_working_hours = 0
                    working_days = 0
                    holiday_hours = 0
                    holiday_days_worked = []
                    night_hours = 0
                    night_holiday_hours = 0

                    # Additional shift tracking
                    additional_shift_hours = 0
                    additional_shift_holiday_hours = 0
                    additional_shift_days_worked = []
                    additional_shift_night_hours = 0
                    additional_shift_night_holiday_hours = 0

                    # Process regular schedule
                    for day, schedule_time in schedule_data.items():
                        if schedule_time and schedule_time not in [
                            "Не указано",
                            "В",
                            "О",
                        ]:
                            time_match = re.search(
                                r"(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})", schedule_time
                            )
                            if time_match:
                                start_hour, start_min, end_hour, end_min = map(
                                    int, time_match.groups()
                                )
                                start_minutes = start_hour * 60 + start_min
                                end_minutes = end_hour * 60 + end_min

                                # Handle overnight shifts
                                if end_minutes < start_minutes:
                                    end_minutes += 24 * 60

                                day_hours = (end_minutes - start_minutes) / 60

                                # Calculate night hours for this shift
                                shift_night_hours = calculate_night_hours(
                                    start_hour, start_min, end_hour, end_min
                                )

                                # For 12-hour shifts, subtract 1 hour for lunch break
                                if day_hours == 12:
                                    day_hours = 11
                                    # Adjust night hours proportionally if lunch break affects them
                                    if shift_night_hours > 0:
                                        shift_night_hours = shift_night_hours * (
                                            11 / 12
                                        )

                                # Check if this day is a holiday
                                try:
                                    work_date = datetime.date(
                                        now.year, now.month, int(day)
                                    )
                                    is_holiday = await production_calendar.is_holiday(
                                        work_date
                                    )
                                    holiday_name = (
                                        await production_calendar.get_holiday_name(
                                            work_date
                                        )
                                    )

                                    if is_holiday and holiday_name:
                                        holiday_hours += day_hours
                                        night_holiday_hours += shift_night_hours
                                        holiday_days_worked.append(
                                            f"{day} - {holiday_name} (+{day_hours:.0f}ч)"
                                        )
                                    else:
                                        night_hours += shift_night_hours
                                except (ValueError, Exception):
                                    # Ignore date parsing errors or API failures
                                    night_hours += shift_night_hours

                                total_working_hours += day_hours
                                working_days += 1

                    # Process additional shifts
                    for day, schedule_time in additional_shifts_data.items():
                        if schedule_time and schedule_time not in [
                            "Не указано",
                            "В",
                            "О",
                        ]:
                            time_match = re.search(
                                r"(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})", schedule_time
                            )
                            if time_match:
                                start_hour, start_min, end_hour, end_min = map(
                                    int, time_match.groups()
                                )
                                start_minutes = start_hour * 60 + start_min
                                end_minutes = end_hour * 60 + end_min

                                # Handle overnight shifts
                                if end_minutes < start_minutes:
                                    end_minutes += 24 * 60

                                day_hours = (end_minutes - start_minutes) / 60

                                # Calculate night hours for this additional shift
                                shift_night_hours = calculate_night_hours(
                                    start_hour, start_min, end_hour, end_min
                                )

                                # For 12-hour shifts, subtract 1 hour for lunch break
                                if day_hours == 12:
                                    day_hours = 11
                                    # Adjust night hours proportionally if lunch break affects them
                                    if shift_night_hours > 0:
                                        shift_night_hours = shift_night_hours * (
                                            11 / 12
                                        )

                                # Check if this day is a holiday
                                try:
                                    work_date = datetime.date(
                                        now.year, now.month, int(day)
                                    )
                                    is_holiday = await production_calendar.is_holiday(
                                        work_date
                                    )
                                    holiday_name = (
                                        await production_calendar.get_holiday_name(
                                            work_date
                                        )
                                    )

                                    if is_holiday and holiday_name:
                                        additional_shift_holiday_hours += day_hours
                                        additional_shift_night_holiday_hours += (
                                            shift_night_hours
                                        )
                                        additional_shift_days_worked.append(
                                            f"{day} - {holiday_name} (+{day_hours:.0f}ч доп.)"
                                        )
                                    else:
                                        additional_shift_night_hours += (
                                            shift_night_hours
                                        )
                                        additional_shift_days_worked.append(
                                            f"{day} - Доп. смена (+{day_hours:.0f}ч)"
                                        )
                                except (ValueError, Exception):
                                    # Ignore date parsing errors or API failures
                                    additional_shift_night_hours += shift_night_hours
                                    additional_shift_days_worked.append(
                                        f"{day} - Доп. смена (+{day_hours:.0f}ч)"
                                    )

                                additional_shift_hours += day_hours

                except Exception as e:
                    # If schedule calculation fails, show basic info
                    message_text = f"""💰 <b>Расчет зарплаты</b>

<b>ФИО:</b> <a href="https://t.me/{user.username}">{user.fullname}</a>
<b>Подразделение:</b> {user.position or "Не указано"} {user.division or "Не указано"}

❌ <b>Ошибка расчета</b>

Не удалось получить данные расписания для расчета зарплаты.

<i>Ошибка: {str(e)}</i>"""
                else:
                    # Calculate salary components with holiday x2 multiplier, night hours x1.2, and additional shifts
                    # Separate regular and night hours
                    regular_hours = (
                        total_working_hours
                        - holiday_hours
                        - night_hours
                        - night_holiday_hours
                    )
                    regular_additional_shift_hours = (
                        additional_shift_hours
                        - additional_shift_holiday_hours
                        - additional_shift_night_hours
                        - additional_shift_night_holiday_hours
                    )

                    # Base salary calculation
                    base_salary = (
                        (regular_hours * pay_rate)
                        + (holiday_hours * pay_rate * 2)
                        + (night_hours * pay_rate * 1.2)
                        + (night_holiday_hours * pay_rate * 2.4)
                    )

                    # Additional shifts calculation: (pay_rate * 2) + (pay_rate * 0.63) per hour
                    additional_shift_rate = (pay_rate * 2) + (pay_rate * 0.63)
                    additional_shift_holiday_rate = (
                        additional_shift_rate * 2
                    )  # Double for holidays
                    additional_shift_night_rate = (
                        additional_shift_rate * 1.2
                    )  # Night multiplier
                    additional_shift_night_holiday_rate = (
                        additional_shift_rate * 2.4
                    )  # Night + holiday

                    additional_shift_salary = (
                        (regular_additional_shift_hours * additional_shift_rate)
                        + (
                            additional_shift_holiday_hours
                            * additional_shift_holiday_rate
                        )
                        + (additional_shift_night_hours * additional_shift_night_rate)
                        + (
                            additional_shift_night_holiday_hours
                            * additional_shift_night_holiday_rate
                        )
                    )

                    # Calculate individual KPI premium amounts (based only on base salary, not additional shifts)
                    csi_premium_amount = base_salary * (
                        (premium.csi_premium or 0) / 100
                    )
                    flr_premium_amount = base_salary * (
                        (premium.flr_premium or 0) / 100
                    )
                    gok_premium_amount = base_salary * (
                        (premium.gok_premium or 0) / 100
                    )
                    target_premium_amount = base_salary * (
                        (premium.target_premium or 0) / 100
                    )
                    discipline_premium_amount = base_salary * (
                        (premium.discipline_premium or 0) / 100
                    )
                    tests_premium_amount = base_salary * (
                        (premium.tests_premium or 0) / 100
                    )
                    thanks_premium_amount = base_salary * (
                        (premium.thanks_premium or 0) / 100
                    )
                    tutors_premium_amount = base_salary * (
                        (premium.tutors_premium or 0) / 100
                    )
                    head_adjust_premium_amount = base_salary * (
                        (premium.head_adjust_premium or 0) / 100
                    )

                    premium_multiplier = (premium.total_premium or 0) / 100
                    premium_amount = base_salary * premium_multiplier
                    total_salary = (
                        base_salary + premium_amount + additional_shift_salary
                    )

                    message_text = f"""💰 <b>Расчет зарплаты</b>

<b>ФИО:</b> <a href="https://t.me/{user.username}">{user.fullname}</a>
<b>Подразделение:</b> {user.position or "Не указано"} {user.division or "Не указано"}

📅 <b>Период:</b> {current_month_name} {now.year}

⏰ <b>Рабочие часы:</b>
<blockquote>Рабочих дней: {working_days}
Всего часов: {round(total_working_hours)}{
                        f'''

🎉 Праздничные дни (x2): {round(holiday_hours)}ч
{chr(10).join(holiday_days_worked)}'''
                        if holiday_days_worked
                        else ""
                    }{
                        f'''

⭐ Доп. смены: {round(additional_shift_hours)}ч
{chr(10).join(additional_shift_days_worked)}'''
                        if additional_shift_days_worked
                        else ""
                    }</blockquote>

💵 <b>Оклад:</b>
<blockquote>Ставка в час: {format_value(pay_rate, " ₽")}

{
                        chr(10).join(
                            [
                                line
                                for line in [
                                    f"Обычные часы: {round(regular_hours)}ч × {pay_rate} ₽ = {round(regular_hours * pay_rate)} ₽"
                                    if regular_hours > 0
                                    else None,
                                    f"Ночные часы: {round(night_hours)}ч × {round(pay_rate * 1.2, 2)} ₽ = {round(night_hours * pay_rate * 1.2)} ₽"
                                    if night_hours > 0
                                    else None,
                                    f"Праздничные часы: {round(holiday_hours)}ч × {pay_rate * 2} ₽ = {round(holiday_hours * pay_rate * 2)} ₽"
                                    if holiday_hours > 0
                                    else None,
                                    f"Ночные праздничные часы: {round(night_holiday_hours)}ч × {round(pay_rate * 2.4, 2)} ₽ = {round(night_holiday_hours * pay_rate * 2.4)} ₽"
                                    if night_holiday_hours > 0
                                    else None,
                                ]
                                if line is not None
                            ]
                        )
                    }

Сумма оклада: {format_value(round(base_salary), " ₽")}</blockquote>{
                        f'''

⭐ <b>Доп. смены:</b>
<blockquote>{
                            chr(10).join(
                                [
                                    line
                                    for line in [
                                        f"Обычные доп. смены: {round(regular_additional_shift_hours)}ч × {additional_shift_rate:.2f} ₽ = {round(regular_additional_shift_hours * additional_shift_rate)} ₽"
                                        if regular_additional_shift_hours > 0
                                        else None,
                                        f"Ночные доп. смены: {round(additional_shift_night_hours)}ч × {additional_shift_night_rate:.2f} ₽ = {round(additional_shift_night_hours * additional_shift_night_rate)} ₽"
                                        if additional_shift_night_hours > 0
                                        else None,
                                        f"Праздничные доп. смены: {round(additional_shift_holiday_hours)}ч × {additional_shift_holiday_rate:.2f} ₽ = {round(additional_shift_holiday_hours * additional_shift_holiday_rate)} ₽"
                                        if additional_shift_holiday_hours > 0
                                        else None,
                                        f"Ночные праздничные доп. смены: {round(additional_shift_night_holiday_hours)}ч × {additional_shift_night_holiday_rate:.2f} ₽ = {round(additional_shift_night_holiday_hours * additional_shift_night_holiday_rate)} ₽"
                                        if additional_shift_night_holiday_hours > 0
                                        else None,
                                    ]
                                    if line is not None
                                ]
                            )
                        }

Сумма доп. смен: {format_value(round(additional_shift_salary), " ₽")}</blockquote>'''
                        if additional_shift_salary > 0
                        else ""
                    }

🎁 <b>Премия:</b>
<blockquote expandable>Общий процент премии: {format_percentage(premium.total_premium)}
Общая сумма премии: {format_value(round(premium_amount), " ₽")}
Стоимость 1% премии: ~{
                        round(premium_amount / premium.total_premium)
                        if premium.total_premium and premium.total_premium > 0
                        else 0
                    } ₽

🌟 Показатели:
Оценка: {format_percentage(premium.csi_premium)} = {
                        format_value(round(csi_premium_amount), " ₽")
                    }
FLR: {format_percentage(premium.flr_premium)} = {
                        format_value(round(flr_premium_amount), " ₽")
                    }
ГОК: {format_percentage(premium.gok_premium)} = {
                        format_value(round(gok_premium_amount), " ₽")
                    }
Цель: {format_percentage(premium.target_premium)} = {
                        format_value(round(target_premium_amount), " ₽")
                    }

💼 Дополнительно:
Дисциплина: {format_percentage(premium.discipline_premium)} = {
                        format_value(round(discipline_premium_amount), " ₽")
                    }
Тестирование: {format_percentage(premium.tests_premium)} = {
                        format_value(round(tests_premium_amount), " ₽")
                    }
Благодарности: {format_percentage(premium.thanks_premium)} = {
                        format_value(round(thanks_premium_amount), " ₽")
                    }
Наставничество: {format_percentage(premium.tutors_premium)} = {
                        format_value(round(tutors_premium_amount), " ₽")
                    }
Ручная правка: {format_percentage(premium.head_adjust_premium)} = {
                        format_value(round(head_adjust_premium_amount), " ₽")
                    }</blockquote>

💰 <b>Итого к выплате:</b>
~<b>{format_value(round(total_salary, 1), " ₽")}</b>

<blockquote expandable>⚠️ <b>Важное</b>

Расчет представляет <b>примерную</b> сумму после вычета НДФЛ
Районный коэффициент <b>не участвует в расчете</b>, т.к. примерно покрывает НДФЛ

🧪 <b>Формулы</b>
Обычные часы: часы × ставка
Праздничные часы: часы × ставка × 2
Ночные часы: часы × ставка × 1.2
Ночные праздничные часы: часы × ставка × 2.4
Доп. смены: часы × (ставка × 2.63)

Ночными часами считается локальное время 22:00 - 6:00
Праздничные дни считаются по производственному <a href='https://www.consultant.ru/law/ref/calendar/proizvodstvennye/'>календарю</a></blockquote>

<i>Расчет от: {now.strftime("%d.%m.%y %H:%M")}</i>
<i>Данные премии от: {
                        premium.updated_at.strftime("%d.%m.%y %H:%M")
                        if premium.updated_at
                        else "—"
                    }</i>"""

        except Exception as e:
            logger.error(f"Ошибка при получении KPI для {user.fullname}: {e}")

            # Проверяем, является ли ошибка отсутствием таблицы
            error_str = str(e)
            if "Table" in error_str and "doesn't exist" in error_str:
                message_text = f"""📊 <b>KPI: {user.fullname}</b>

⚠️ <b>Система KPI недоступна</b>

Таблица показателей эффективности не найдена в базе данных.

<i>Обратись к администратору для настройки системы KPI.</i>"""
            else:
                message_text = f"""📊 <b>KPI: {user.fullname}</b>

❌ <b>Ошибка загрузки данных</b>

Произошла ошибка при получении показателей эффективности.

<i>Попробуй позже или обратись к администратору для проверки данных</i>"""

        await callback.message.edit_text(
            message_text,
            reply_markup=search_user_kpi_kb(user_id, return_to, head_id, action),
        )

    except Exception as e:
        logger.error(f"Ошибка при получении KPI пользователя {user_id}: {e}")
        await callback.answer("❌ Ошибка при получении KPI", show_alert=True)


@mip_search_router.callback_query(SearchMemberKPIMenu.filter())
async def search_member_kpi_menu(
    callback: CallbackQuery,
    callback_data: SearchMemberKPIMenu,
    stp_repo: MainRequestsRepo,
    kpi_repo: KPIRequestsRepo,
):
    """Полноценное KPI меню для участника группы из поиска"""
    member_id = callback_data.member_id
    head_id = callback_data.head_id
    action = callback_data.action
    page = callback_data.page

    try:
        # Поиск участника по ID
        all_users = await stp_repo.employee.get_users()
        member = None
        for user in all_users:
            if user.id == member_id:
                member = user
                break

        if not member:
            await callback.answer("❌ Участник не найден", show_alert=True)
            return

        # Получаем KPI данные участника
        try:
            premium = await kpi_repo.spec_premium.get_premium(fullname=member.fullname)

            if premium is None:
                message_text = f"""📊 <b>KPI: {member.fullname}</b>

❌ <b>Данные KPI не найдены</b>

Показатели эффективности для этого сотрудника отсутствуют в системе или не загружены.

<i>Обратись к администратору для проверки данных</i>"""

                await callback.message.edit_text(
                    message_text,
                    reply_markup=search_member_kpi_kb(member_id, head_id, page, action),
                )
                return

            def format_value(value, suffix=""):
                return f"{value}{suffix}" if value is not None else "—"

            def format_percentage(value):
                return f"{value}%" if value is not None else "—"

            if action == "main":
                message_text = f"""🌟 <b>Показатели</b>

<b>ФИО:</b> <a href="https://t.me/{member.username}">{member.fullname}</a>
<b>Должность:</b> {member.position or "Не указано"} {member.division or ""}

📊 <b>Оценка клиента - {format_percentage(premium.csi_premium)}</b>
<blockquote>Факт: {format_value(premium.csi)}
План: {format_value(premium.csi_normative)}</blockquote>

🎯 <b>Отклик</b>
<blockquote>Факт: {format_value(premium.csi_response)}
План: {format_value(round(premium.csi_response_normative)) if premium.csi_response_normative else "—"}</blockquote>

🔧 <b>FLR - {format_percentage(premium.flr_premium)}</b>
<blockquote>Факт: {format_value(premium.flr)}
План: {format_value(premium.flr_normative)}</blockquote>

⚖️ <b>ГОК - {format_percentage(premium.gok_premium)}</b>
<blockquote>Факт: {format_value(premium.gok)}
План: {format_value(premium.gok_normative)}</blockquote>

🎯 <b>Цель - {format_percentage(premium.target_premium)}</b>
<blockquote>Тип: {premium.target_type or "—"}
Факт: {format_value(premium.target)}
План: {format_value(round(premium.target_goal_first)) if premium.target_goal_first else "—"} / {format_value(round(premium.target_goal_second)) if premium.target_goal_second else "—"}</blockquote>

💼 <b>Дополнительно</b>
<blockquote>Дисциплина: {format_percentage(premium.discipline_premium)}
Тестирование: {format_percentage(premium.tests_premium)}
Благодарности: {format_percentage(premium.thanks_premium)}
Наставничество: {format_percentage(premium.tutors_premium)}
Ручная правка: {format_percentage(premium.head_adjust_premium)}</blockquote>

💰 <b>Итого:</b>
<b>Общая премия: {format_percentage(premium.total_premium)}</b>

{"📈 Всего чатов: " + format_value(premium.contacts_count) if member.division == "НЦК" else "📈 Всего звонков: " + format_value(premium.contacts_count)}
{"⏰ Задержка: " + format_value(premium.delay, " сек") if member.division != "НЦК" else ""}

<i>Выгружено: {premium.updated_at.strftime("%d.%m.%y %H:%M") if premium.updated_at else "—"}</i>"""

            elif action == "calculator":
                # Реализация калькулятора KPI аналогично пользовательскому
                def calculate_csi_needed(division: str, current_csi, normative):
                    if normative == 0 or normative is None:
                        return "—"

                    current_csi = current_csi or 0

                    results = []

                    if division == "НЦК":
                        thresholds = [
                            (101, 20, "≥ 101%"),
                            (100.5, 15, "≥ 100,5%"),
                            (100, 10, "≥ 100%"),
                            (98, 5, "≥ 98%"),
                            (0, 0, "&lt; 98%"),
                        ]
                    elif division == "НТП1":
                        thresholds = [
                            (101, 20, "≥ 101%"),
                            (100.5, 15, "≥ 100,5%"),
                            (100, 10, "≥ 100%"),
                            (98, 5, "≥ 98%"),
                            (0, 0, "&lt; 98%"),
                        ]
                    else:
                        thresholds = [
                            (100.8, 20, "≥ 100.8%"),
                            (100.4, 15, "≥ 100.4%"),
                            (100, 10, "≥ 100%"),
                            (98, 5, "≥ 98%"),
                            (0, 0, "&lt; 98%"),
                        ]

                    for threshold, premium_percent, description in thresholds:
                        needed_csi = (threshold / 100) * normative

                        if current_csi >= needed_csi:
                            results.append(f"{premium_percent}%: ✅ ({description})")
                        else:
                            difference = needed_csi - current_csi
                            results.append(
                                f"{premium_percent}%: {needed_csi:.3f} [+{difference:.3f}] ({description})"
                            )

                    return "\n".join(results)

                def calculate_flr_needed(division: str, current_flr, normative):
                    if normative == 0 or normative is None:
                        return "—"

                    current_flr = current_flr or 0

                    results = []

                    if division == "НЦК":
                        thresholds = [
                            (103, 30, "≥ 103%"),
                            (102, 25, "≥ 102%"),
                            (101, 21, "≥ 101%"),
                            (100, 18, "≥ 100%"),
                            (95, 13, "≥ 95%"),
                            (0, 8, "&lt; 95%"),
                        ]
                    elif division == "НТП1":
                        thresholds = [
                            (109, 30, "≥ 109%"),
                            (106, 25, "≥ 106%"),
                            (103, 21, "≥ 103%"),
                            (100, 18, "≥ 100%"),
                            (90, 13, "≥ 90%"),
                            (0, 8, "&lt; 90%"),
                        ]
                    else:
                        thresholds = [
                            (107, 30, "≥ 107%"),
                            (104, 25, "≥ 104%"),
                            (102, 21, "≥ 102%"),
                            (100, 18, "≥ 100%"),
                            (97, 13, "≥ 97%"),
                            (0, 8, "&lt; 97%"),
                        ]

                    for threshold, premium_percent, description in thresholds:
                        needed_flr = (threshold / 100) * normative

                        if current_flr >= needed_flr:
                            results.append(f"{premium_percent}%: ✅ ({description})")
                        else:
                            difference = needed_flr - current_flr
                            results.append(
                                f"{premium_percent}%: {needed_flr:.2f} [+{difference:.2f}] ({description})"
                            )

                    return "\n".join(results)

                def calculate_gok_needed(division: str, current_gok, normative):
                    if normative == 0 or normative is None:
                        return "—"

                    current_gok = current_gok or 0

                    results = []

                    if division == "НЦК":
                        thresholds = [
                            (100, 17, "≥ 100%"),
                            (95, 15, "≥ 95%"),
                            (90, 12, "≥ 90%"),
                            (85, 9, "≥ 85%"),
                            (80, 5, "≥ 80%"),
                            (0, 0, "&lt; 80%"),
                        ]
                    elif division == "НТП1":
                        thresholds = [
                            (100, 17, "≥ 100%"),
                            (95, 15, "≥ 95%"),
                            (90, 12, "≥ 90%"),
                            (85, 9, "≥ 85%"),
                            (80, 5, "≥ 80%"),
                            (0, 0, "&lt; 80%"),
                        ]
                    else:
                        thresholds = [
                            (100, 17, "≥ 100%"),
                            (95, 15, "≥ 95%"),
                            (90, 12, "≥ 90%"),
                            (84, 9, "≥ 84%"),
                            (70, 5, "≥ 70%"),
                            (0, 0, "&lt; 70%"),
                        ]

                    for threshold, premium_percent, description in thresholds:
                        needed_gok = (threshold / 100) * normative

                        if current_gok >= needed_gok:
                            results.append(f"{premium_percent}%: ✅ ({description})")
                        else:
                            difference = needed_gok - current_gok
                            results.append(
                                f"{premium_percent}%: {needed_gok:.3f} [+{difference:.3f}] ({description})"
                            )

                    return "\n".join(results)

                def calculate_target_needed(
                    current_target,
                    target_goal_first,
                    target_goal_second,
                    target_type=None,
                ):
                    if target_goal_first is None and target_goal_second is None:
                        return "—"

                    current_target = current_target or 0

                    # Determine if this is a sales target (higher is better) or AHT target (lower is better)
                    is_sales_target = (
                        target_type and "Продажа оборудования" in target_type
                    )
                    is_aht_target = target_type and "AHT" in target_type

                    results = []

                    # All divisions have the same target premium thresholds
                    if target_goal_second and target_goal_second > 0:
                        # When there's a second goal, use it as the main normative
                        normative = target_goal_second

                        if is_aht_target:
                            # For AHT, lower is better - calculate percentage as (normative / current * 100)
                            target_rate = (
                                (normative / current_target * 100)
                                if current_target > 0
                                else 0
                            )
                        elif is_sales_target:
                            # For sales, higher is better - calculate percentage as (current / normative * 100)
                            target_rate = (
                                (current_target / normative * 100)
                                if normative > 0
                                else 0
                            )
                        else:
                            # Default behavior (higher is better) - calculate percentage as (current / normative * 100)
                            target_rate = (
                                (current_target / normative * 100)
                                if normative > 0
                                else 0
                            )

                        if target_rate > 100.01:
                            results.append("28%: ✅ (≥ 100,01% - план 2 и более)")
                        else:
                            if is_aht_target:
                                # For AHT, we need to be lower than the target
                                needed_for_28 = normative / (100.01 / 100)
                                difference = current_target - needed_for_28
                                results.append(
                                    f"28%: {needed_for_28:.2f} [-{difference:.2f}] (≥ 100,01% - план 2 и более)"
                                )
                            else:
                                # For sales, we need to be higher than the target
                                needed_for_28 = (100.01 / 100) * normative
                                difference = needed_for_28 - current_target
                                results.append(
                                    f"28%: {needed_for_28:.2f} [+{difference:.2f}] (≥ 100,01% - план 2 и более)"
                                )

                        if target_rate >= 100.00:
                            results.append(
                                "18%: ✅ (≥ 100,00% - план 1 и менее плана 2)"
                            )
                        else:
                            if is_aht_target:
                                needed_for_18 = normative / (100.00 / 100)
                                difference = current_target - needed_for_18
                                results.append(
                                    f"18%: {needed_for_18:.2f} [-{difference:.2f}] (= 100,00% - план 1 и менее плана 2)"
                                )
                            else:
                                needed_for_18 = (100.00 / 100) * normative
                                difference = needed_for_18 - current_target
                                results.append(
                                    f"18%: {needed_for_18:.2f} [+{difference:.2f}] (= 100,00% - план 1 и менее плана 2)"
                                )

                        if target_rate < 99.99:
                            results.append("0%: — (&lt; 99,99% - менее плана 1)")
                        else:
                            results.append("0%: ✅ (&lt; 99,99% - менее плана 1)")

                    elif target_goal_first and target_goal_first > 0:
                        # When there's only first goal, use it as normative
                        normative = target_goal_first

                        if is_aht_target:
                            # For AHT, lower is better
                            target_rate = (
                                (normative / current_target * 100)
                                if current_target > 0
                                else 0
                            )
                        elif is_sales_target:
                            # For sales, higher is better
                            target_rate = (
                                (current_target / normative * 100)
                                if normative > 0
                                else 0
                            )
                        else:
                            # Default behavior (higher is better)
                            target_rate = (
                                (current_target / normative * 100)
                                if normative > 0
                                else 0
                            )

                        if target_rate > 100.01:
                            results.append("28%: ✅ (≥ 100,01% - план 2 и более)")
                        else:
                            if is_aht_target:
                                needed_for_28 = normative / (100.01 / 100)
                                difference = current_target - needed_for_28
                                results.append(
                                    f"28%: {needed_for_28:.2f} [-{difference:.2f}] (≥ 100,01% - план 2 и более)"
                                )
                            else:
                                needed_for_28 = (100.01 / 100) * normative
                                difference = needed_for_28 - current_target
                                results.append(
                                    f"28%: {needed_for_28:.2f} [+{difference:.2f}] (≥ 100,01% - план 2 и более)"
                                )

                        if target_rate >= 100.00:
                            results.append(
                                "18%: ✅ (≥ 100,00% - план 1 и менее плана 2)"
                            )
                        else:
                            if is_aht_target:
                                needed_for_18 = normative / (100.00 / 100)
                                difference = current_target - needed_for_18
                                results.append(
                                    f"18%: {needed_for_18:.2f} [-{difference:.2f}] (≥ 100,00% - план 1 и менее плана 2)"
                                )
                            else:
                                needed_for_18 = (100.00 / 100) * normative
                                difference = needed_for_18 - current_target
                                results.append(
                                    f"18%: {needed_for_18:.2f} [+{difference:.2f}] (≥ 100,00% - план 1 и менее плана 2)"
                                )

                        if target_rate < 99.99:
                            results.append("0%: — (&lt; 99,99% - менее плана 1)")
                        else:
                            results.append("0%: ✅ (&lt; 99,99% - менее плана 1)")

                    return "\n".join(results)

                csi_calculation = calculate_csi_needed(
                    member.division, premium.csi, premium.csi_normative
                )
                flr_calculation = calculate_flr_needed(
                    member.division, premium.flr, premium.flr_normative
                )
                gok_calculation = calculate_gok_needed(
                    member.division, premium.gok, premium.gok_normative
                )
                target_calculation = calculate_target_needed(
                    premium.target,
                    premium.target_goal_first,
                    premium.target_goal_second,
                    premium.target_type,
                )

                message_text = f"""🧮 <b>Калькулятор KPI</b>

<b>ФИО:</b> <a href="https://t.me/{member.username}">{member.fullname}</a>
<b>Должность:</b> {member.position or "Не указано"} {member.division or ""}

📊 <b>Оценка клиента</b>
<blockquote>Текущий: {format_value(premium.csi)} ({format_percentage(premium.csi_normative_rate)})
План: {format_value(premium.csi_normative)}

<b>Для премии:</b>
{csi_calculation}</blockquote>

🔧 <b>FLR</b>
<blockquote>Текущий: {format_value(premium.flr)} ({format_percentage(premium.flr_normative_rate)})
План: {format_value(premium.flr_normative)}

<b>Для премии:</b>
{flr_calculation}</blockquote>

⚖️ <b>ГОК</b>
<blockquote>Текущий: {format_value(round(premium.gok))} ({format_percentage(premium.gok_normative_rate)})
План: {format_value(round(premium.gok_normative))}

<b>Для премии:</b>
{gok_calculation}</blockquote>

🎯 <b>Цель</b>
<blockquote>Факт: {format_value(premium.target)} ({format_percentage(round((premium.target_goal_first / premium.target * 100) if premium.target_type and "AHT" in premium.target_type and premium.target and premium.target > 0 and premium.target_goal_first else (premium.target / premium.target_goal_first * 100) if premium.target_goal_first and premium.target_goal_first > 0 else 0))} / {format_percentage(round((premium.target_goal_second / premium.target * 100) if premium.target_type and "AHT" in premium.target_type and premium.target and premium.target > 0 and premium.target_goal_second else (premium.target / premium.target_goal_second * 100) if premium.target_goal_second and premium.target_goal_second > 0 else 0))})
План: {format_value(round(premium.target_goal_first))} / {format_value(round(premium.target_goal_second))}

Требуется минимум 100 {"чатов" if member.division == "НЦК" else "звонков"} для получения премии за цель

<b>Для премии:</b>
{target_calculation}</blockquote>

<i>Данные от: {premium.updated_at.strftime("%d.%m.%y %H:%M") if premium.updated_at else "—"}</i>"""

            elif action == "salary":
                # Реализация расчета зарплаты аналогично пользовательскому
                def format_value(value, suffix=""):
                    return f"{value}{suffix}" if value is not None else "—"

                def format_percentage(value):
                    return f"{value}%" if value is not None else "—"

                pay_rate = 0.0
                match member.division:
                    case "НЦК":
                        match member.position:
                            case "Специалист":
                                pay_rate = 156.7
                            case "Ведущий специалист":
                                pay_rate = 164.2
                            case "Эксперт":
                                pay_rate = 195.9
                    case "НТП1":
                        match member.position:
                            case "Специалист первой линии":
                                pay_rate = 143.6
                    case "НТП2":
                        match member.position:
                            case "Специалист второй линии":
                                pay_rate = 166
                            case "Ведущий специалист второй линии":
                                pay_rate = 181
                            case "Эксперт второй линии":
                                pay_rate = 195.9

                # Get current month working hours from actual schedule
                now = datetime.datetime.now(
                    datetime.timezone(datetime.timedelta(hours=5))
                )
                current_month_name = russian_months[now.month]

                def calculate_night_hours(start_hour, start_min, end_hour, end_min):
                    """Calculate night hours (22:00-06:00) from a work shift"""
                    start_minutes = start_hour * 60 + start_min
                    end_minutes = end_hour * 60 + end_min

                    # Handle overnight shifts
                    if end_minutes < start_minutes:
                        end_minutes += 24 * 60

                    night_start = 22 * 60  # 22:00 in minutes
                    night_end = 6 * 60  # 06:00 in minutes (next day)

                    total_night_minutes = 0

                    # Check for night hours in first day (22:00-24:00)
                    first_day_night_start = night_start
                    first_day_night_end = 24 * 60  # Midnight

                    if (
                        start_minutes < first_day_night_end
                        and end_minutes > first_day_night_start
                    ):
                        overlap_start = max(start_minutes, first_day_night_start)
                        overlap_end = min(end_minutes, first_day_night_end)
                        if overlap_end > overlap_start:
                            total_night_minutes += overlap_end - overlap_start

                    # Check for night hours in second day (00:00-06:00)
                    if end_minutes > 24 * 60:  # Shift continues to next day
                        second_day_start = 24 * 60
                        second_day_end = end_minutes
                        second_day_night_start = 24 * 60  # 00:00 next day
                        second_day_night_end = 24 * 60 + night_end  # 06:00 next day

                        if (
                            second_day_start < second_day_night_end
                            and second_day_end > second_day_night_start
                        ):
                            overlap_start = max(
                                second_day_start, second_day_night_start
                            )
                            overlap_end = min(second_day_end, second_day_night_end)
                            if overlap_end > overlap_start:
                                total_night_minutes += overlap_end - overlap_start

                    return total_night_minutes / 60  # Convert to hours

                # Get actual schedule data with additional shifts detection
                schedule_parser = ScheduleParser()
                try:
                    schedule_data, additional_shifts_data = (
                        schedule_parser.get_user_schedule_with_additional_shifts(
                            member.fullname, current_month_name, member.division
                        )
                    )

                    # Calculate actual working hours from schedule with holiday detection
                    total_working_hours = 0
                    working_days = 0
                    holiday_hours = 0
                    holiday_days_worked = []
                    night_hours = 0
                    night_holiday_hours = 0

                    # Additional shift tracking
                    additional_shift_hours = 0
                    additional_shift_holiday_hours = 0
                    additional_shift_days_worked = []
                    additional_shift_night_hours = 0
                    additional_shift_night_holiday_hours = 0

                    # Process regular schedule
                    for day, schedule_time in schedule_data.items():
                        if schedule_time and schedule_time not in [
                            "Не указано",
                            "В",
                            "О",
                        ]:
                            time_match = re.search(
                                r"(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})", schedule_time
                            )
                            if time_match:
                                start_hour, start_min, end_hour, end_min = map(
                                    int, time_match.groups()
                                )
                                start_minutes = start_hour * 60 + start_min
                                end_minutes = end_hour * 60 + end_min

                                # Handle overnight shifts
                                if end_minutes < start_minutes:
                                    end_minutes += 24 * 60

                                day_hours = (end_minutes - start_minutes) / 60

                                # Calculate night hours for this shift
                                shift_night_hours = calculate_night_hours(
                                    start_hour, start_min, end_hour, end_min
                                )

                                # For 12-hour shifts, subtract 1 hour for lunch break
                                if day_hours == 12:
                                    day_hours = 11
                                    # Adjust night hours proportionally if lunch break affects them
                                    if shift_night_hours > 0:
                                        shift_night_hours = shift_night_hours * (
                                            11 / 12
                                        )

                                # Check if this day is a holiday
                                try:
                                    work_date = datetime.date(
                                        now.year, now.month, int(day)
                                    )
                                    is_holiday = await production_calendar.is_holiday(
                                        work_date
                                    )
                                    holiday_name = (
                                        await production_calendar.get_holiday_name(
                                            work_date
                                        )
                                    )

                                    if is_holiday and holiday_name:
                                        holiday_hours += day_hours
                                        night_holiday_hours += shift_night_hours
                                        holiday_days_worked.append(
                                            f"{day} - {holiday_name} (+{day_hours:.0f}ч)"
                                        )
                                    else:
                                        night_hours += shift_night_hours
                                except (ValueError, Exception):
                                    # Ignore date parsing errors or API failures
                                    night_hours += shift_night_hours

                                total_working_hours += day_hours
                                working_days += 1

                    # Process additional shifts
                    for day, schedule_time in additional_shifts_data.items():
                        if schedule_time and schedule_time not in [
                            "Не указано",
                            "В",
                            "О",
                        ]:
                            time_match = re.search(
                                r"(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})", schedule_time
                            )
                            if time_match:
                                start_hour, start_min, end_hour, end_min = map(
                                    int, time_match.groups()
                                )
                                start_minutes = start_hour * 60 + start_min
                                end_minutes = end_hour * 60 + end_min

                                # Handle overnight shifts
                                if end_minutes < start_minutes:
                                    end_minutes += 24 * 60

                                day_hours = (end_minutes - start_minutes) / 60

                                # Calculate night hours for this additional shift
                                shift_night_hours = calculate_night_hours(
                                    start_hour, start_min, end_hour, end_min
                                )

                                # For 12-hour shifts, subtract 1 hour for lunch break
                                if day_hours == 12:
                                    day_hours = 11
                                    # Adjust night hours proportionally if lunch break affects them
                                    if shift_night_hours > 0:
                                        shift_night_hours = shift_night_hours * (
                                            11 / 12
                                        )

                                # Check if this day is a holiday
                                try:
                                    work_date = datetime.date(
                                        now.year, now.month, int(day)
                                    )
                                    is_holiday = await production_calendar.is_holiday(
                                        work_date
                                    )
                                    holiday_name = (
                                        await production_calendar.get_holiday_name(
                                            work_date
                                        )
                                    )

                                    if is_holiday and holiday_name:
                                        additional_shift_holiday_hours += day_hours
                                        additional_shift_night_holiday_hours += (
                                            shift_night_hours
                                        )
                                        additional_shift_days_worked.append(
                                            f"{day} - {holiday_name} (+{day_hours:.0f}ч доп.)"
                                        )
                                    else:
                                        additional_shift_night_hours += (
                                            shift_night_hours
                                        )
                                        additional_shift_days_worked.append(
                                            f"{day} - Доп. смена (+{day_hours:.0f}ч)"
                                        )
                                except (ValueError, Exception):
                                    # Ignore date parsing errors or API failures
                                    additional_shift_night_hours += shift_night_hours
                                    additional_shift_days_worked.append(
                                        f"{day} - Доп. смена (+{day_hours:.0f}ч)"
                                    )

                                additional_shift_hours += day_hours

                except Exception as e:
                    # If schedule calculation fails, show basic info
                    message_text = f"""💰 <b>Расчет зарплаты</b>

<b>ФИО:</b> <a href="https://t.me/{member.username}">{member.fullname}</a>
<b>Должность:</b> {member.position or "Не указано"} {member.division or ""}

❌ <b>Ошибка расчета</b>

Не удалось получить данные расписания для расчета зарплаты.

<i>Ошибка: {str(e)}</i>"""
                else:
                    # Calculate salary components with holiday x2 multiplier, night hours x1.2, and additional shifts
                    # Separate regular and night hours
                    regular_hours = (
                        total_working_hours
                        - holiday_hours
                        - night_hours
                        - night_holiday_hours
                    )
                    regular_additional_shift_hours = (
                        additional_shift_hours
                        - additional_shift_holiday_hours
                        - additional_shift_night_hours
                        - additional_shift_night_holiday_hours
                    )

                    # Base salary calculation
                    base_salary = (
                        (regular_hours * pay_rate)
                        + (holiday_hours * pay_rate * 2)
                        + (night_hours * pay_rate * 1.2)
                        + (night_holiday_hours * pay_rate * 2.4)
                    )

                    # Additional shifts calculation: (pay_rate * 2) + (pay_rate * 0.63) per hour
                    additional_shift_rate = (pay_rate * 2) + (pay_rate * 0.63)
                    additional_shift_holiday_rate = (
                        additional_shift_rate * 2
                    )  # Double for holidays
                    additional_shift_night_rate = (
                        additional_shift_rate * 1.2
                    )  # Night multiplier
                    additional_shift_night_holiday_rate = (
                        additional_shift_rate * 2.4
                    )  # Night + holiday

                    additional_shift_salary = (
                        (regular_additional_shift_hours * additional_shift_rate)
                        + (
                            additional_shift_holiday_hours
                            * additional_shift_holiday_rate
                        )
                        + (additional_shift_night_hours * additional_shift_night_rate)
                        + (
                            additional_shift_night_holiday_hours
                            * additional_shift_night_holiday_rate
                        )
                    )

                    # Calculate individual KPI premium amounts (based only on base salary, not additional shifts)
                    csi_premium_amount = base_salary * (
                        (premium.csi_premium or 0) / 100
                    )
                    flr_premium_amount = base_salary * (
                        (premium.flr_premium or 0) / 100
                    )
                    gok_premium_amount = base_salary * (
                        (premium.gok_premium or 0) / 100
                    )
                    target_premium_amount = base_salary * (
                        (premium.target_premium or 0) / 100
                    )
                    discipline_premium_amount = base_salary * (
                        (premium.discipline_premium or 0) / 100
                    )
                    tests_premium_amount = base_salary * (
                        (premium.tests_premium or 0) / 100
                    )
                    thanks_premium_amount = base_salary * (
                        (premium.thanks_premium or 0) / 100
                    )
                    tutors_premium_amount = base_salary * (
                        (premium.tutors_premium or 0) / 100
                    )
                    head_adjust_premium_amount = base_salary * (
                        (premium.head_adjust_premium or 0) / 100
                    )

                    premium_multiplier = (premium.total_premium or 0) / 100
                    premium_amount = base_salary * premium_multiplier
                    total_salary = (
                        base_salary + premium_amount + additional_shift_salary
                    )

                    message_text = f"""💰 <b>Расчет зарплаты</b>

<b>ФИО:</b> <a href="https://t.me/{member.username}">{member.fullname}</a>
<b>Должность:</b> {member.position or "Не указано"} {member.division or ""}

📅 <b>Период:</b> {current_month_name} {now.year}

⏰ <b>Рабочие часы:</b>
<blockquote>Рабочих дней: {working_days}
Всего часов: {round(total_working_hours)}{
                        f'''

🎉 Праздничные дни (x2): {round(holiday_hours)}ч
{chr(10).join(holiday_days_worked)}'''
                        if holiday_days_worked
                        else ""
                    }{
                        f'''

⭐ Доп. смены: {round(additional_shift_hours)}ч
{chr(10).join(additional_shift_days_worked)}'''
                        if additional_shift_days_worked
                        else ""
                    }</blockquote>

💵 <b>Оклад:</b>
<blockquote>Ставка в час: {format_value(pay_rate, " ₽")}

{
                        chr(10).join(
                            [
                                line
                                for line in [
                                    f"Обычные часы: {round(regular_hours)}ч × {pay_rate} ₽ = {round(regular_hours * pay_rate)} ₽"
                                    if regular_hours > 0
                                    else None,
                                    f"Ночные часы: {round(night_hours)}ч × {round(pay_rate * 1.2, 2)} ₽ = {round(night_hours * pay_rate * 1.2)} ₽"
                                    if night_hours > 0
                                    else None,
                                    f"Праздничные часы: {round(holiday_hours)}ч × {pay_rate * 2} ₽ = {round(holiday_hours * pay_rate * 2)} ₽"
                                    if holiday_hours > 0
                                    else None,
                                    f"Ночные праздничные часы: {round(night_holiday_hours)}ч × {round(pay_rate * 2.4, 2)} ₽ = {round(night_holiday_hours * pay_rate * 2.4)} ₽"
                                    if night_holiday_hours > 0
                                    else None,
                                ]
                                if line is not None
                            ]
                        )
                    }

Сумма оклада: {format_value(round(base_salary), " ₽")}</blockquote>{
                        f'''

⭐ <b>Доп. смены:</b>
<blockquote>{
                            chr(10).join(
                                [
                                    line
                                    for line in [
                                        f"Обычные доп. смены: {round(regular_additional_shift_hours)}ч × {additional_shift_rate:.2f} ₽ = {round(regular_additional_shift_hours * additional_shift_rate)} ₽"
                                        if regular_additional_shift_hours > 0
                                        else None,
                                        f"Ночные доп. смены: {round(additional_shift_night_hours)}ч × {additional_shift_night_rate:.2f} ₽ = {round(additional_shift_night_hours * additional_shift_night_rate)} ₽"
                                        if additional_shift_night_hours > 0
                                        else None,
                                        f"Праздничные доп. смены: {round(additional_shift_holiday_hours)}ч × {additional_shift_holiday_rate:.2f} ₽ = {round(additional_shift_holiday_hours * additional_shift_holiday_rate)} ₽"
                                        if additional_shift_holiday_hours > 0
                                        else None,
                                        f"Ночные праздничные доп. смены: {round(additional_shift_night_holiday_hours)}ч × {additional_shift_night_holiday_rate:.2f} ₽ = {round(additional_shift_night_holiday_hours * additional_shift_night_holiday_rate)} ₽"
                                        if additional_shift_night_holiday_hours > 0
                                        else None,
                                    ]
                                    if line is not None
                                ]
                            )
                        }

Сумма доп. смен: {format_value(round(additional_shift_salary), " ₽")}</blockquote>'''
                        if additional_shift_salary > 0
                        else ""
                    }

🎁 <b>Премия:</b>
<blockquote expandable>Общий процент премии: {format_percentage(premium.total_premium)}
Общая сумма премии: {format_value(round(premium_amount), " ₽")}
Стоимость 1% премии: ~{
                        round(premium_amount / premium.total_premium)
                        if premium.total_premium and premium.total_premium > 0
                        else 0
                    } ₽

🌟 Показатели:
Оценка: {format_percentage(premium.csi_premium)} = {
                        format_value(round(csi_premium_amount), " ₽")
                    }
FLR: {format_percentage(premium.flr_premium)} = {
                        format_value(round(flr_premium_amount), " ₽")
                    }
ГОК: {format_percentage(premium.gok_premium)} = {
                        format_value(round(gok_premium_amount), " ₽")
                    }
Цель: {format_percentage(premium.target_premium)} = {
                        format_value(round(target_premium_amount), " ₽")
                    }

💼 Дополнительно:
Дисциплина: {format_percentage(premium.discipline_premium)} = {
                        format_value(round(discipline_premium_amount), " ₽")
                    }
Тестирование: {format_percentage(premium.tests_premium)} = {
                        format_value(round(tests_premium_amount), " ₽")
                    }
Благодарности: {format_percentage(premium.thanks_premium)} = {
                        format_value(round(thanks_premium_amount), " ₽")
                    }
Наставничество: {format_percentage(premium.tutors_premium)} = {
                        format_value(round(tutors_premium_amount), " ₽")
                    }
Ручная правка: {format_percentage(premium.head_adjust_premium)} = {
                        format_value(round(head_adjust_premium_amount), " ₽")
                    }</blockquote>

💰 <b>Итого к выплате:</b>
~<b>{format_value(round(total_salary, 1), " ₽")}</b>

<blockquote expandable>⚠️ <b>Важное</b>

Расчет представляет <b>примерную</b> сумму после вычета НДФЛ
Районный коэффициент <b>не участвует в расчете</b>, т.к. примерно покрывает НДФЛ

🧪 <b>Формулы</b>
Обычные часы: часы × ставка
Праздничные часы: часы × ставка × 2
Ночные часы: часы × ставка × 1.2
Ночные праздничные часы: часы × ставка × 2.4
Доп. смены: часы × (ставка × 2.63)

Ночными часами считается локальное время 22:00 - 6:00
Праздничные дни считаются по производственному <a href='https://www.consultant.ru/law/ref/calendar/proizvodstvennye/'>календарю</a></blockquote>

<i>Расчет от: {now.strftime("%d.%m.%y %H:%M")}</i>
<i>Данные премии от: {
                        premium.updated_at.strftime("%d.%m.%y %H:%M")
                        if premium.updated_at
                        else "—"
                    }</i>"""

        except Exception as e:
            logger.error(f"Ошибка при получении KPI для {member.fullname}: {e}")

            # Проверяем, является ли ошибка отсутствием таблицы
            error_str = str(e)
            if "Table" in error_str and "doesn't exist" in error_str:
                message_text = f"""📊 <b>KPI: {member.fullname}</b>

⚠️ <b>Система KPI недоступна</b>

Таблица показателей эффективности не найдена в базе данных.

<i>Обратись к администратору для настройки системы KPI.</i>"""
            else:
                message_text = f"""📊 <b>KPI: {member.fullname}</b>

❌ <b>Ошибка загрузки данных</b>

Произошла ошибка при получении показателей эффективности.

<i>Попробуй позже или обратись к администратору для проверки данных</i>"""

        await callback.message.edit_text(
            message_text,
            reply_markup=search_member_kpi_kb(member_id, head_id, page, action),
        )

    except Exception as e:
        logger.error(f"Ошибка при получении KPI участника {member_id}: {e}")
        await callback.answer("❌ Ошибка при получении KPI", show_alert=True)


@mip_search_router.callback_query(ViewUserSchedule.filter())
async def view_user_schedule(
    callback: CallbackQuery,
    callback_data: ViewUserSchedule,
    stp_repo: MainRequestsRepo,
):
    """Просмотр расписания пользователя"""
    user_id = callback_data.user_id
    return_to = callback_data.return_to
    head_id = callback_data.head_id
    requested_month_idx = callback_data.month_idx

    try:
        # Получаем пользователя
        user = await stp_repo.employee.get_user(user_id=user_id)
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        # Определяем месяц для отображения
        if requested_month_idx > 0:
            current_month = get_month_name_by_index(requested_month_idx)
        else:
            current_month = schedule_service.get_current_month()

        try:
            # Получаем расписание пользователя (компактный формат) с дежурствами
            schedule_response = await schedule_service.get_user_schedule_response(
                user=user, month=current_month, compact=True, stp_repo=stp_repo
            )

            await callback.message.edit_text(
                f"""<b>📅 График сотрудника</b>

<b>ФИО:</b> <a href='t.me/{user.username}'>{user.fullname}</a>
<b>Подразделение:</b> {user.position or "Не указано"} {user.division or "Не указано"}

<blockquote>{schedule_response}</blockquote>""",
                reply_markup=user_schedule_with_month_kb(
                    user_id=user_id,
                    current_month=current_month,
                    return_to=return_to,
                    head_id=head_id,
                    is_detailed=False,
                ),
            )

        except Exception as schedule_error:
            # Если не удалось получить расписание, показываем ошибку
            error_message = "❌ График для данного сотрудника не найдено"
            if "не найден" in str(schedule_error).lower():
                error_message = f"❌ Сотрудник {user.fullname} не найден в графике"
            elif "файл" in str(schedule_error).lower():
                error_message = "❌ Файл графика недоступен"

            await callback.message.edit_text(
                f"""<b>📅 График сотрудника</b>

<b>ФИО:</b> <a href='t.me/{user.username}'>{user.fullname}</a>
<b>Подразделение:</b> {user.position or "Не указано"} {user.division or "Не указано"}

{error_message}

<i>Возможно, сотрудник не включен в текущий график или файл недоступен.</i>""",
                reply_markup=user_schedule_with_month_kb(
                    user_id=user_id,
                    current_month=current_month,
                    return_to=return_to,
                    head_id=head_id,
                    is_detailed=False,
                ),
            )

    except Exception as e:
        logger.error(f"Ошибка при получении расписания пользователя {user_id}: {e}")
        await callback.answer("❌ Ошибка при получении расписания", show_alert=True)


@mip_search_router.callback_query(MipScheduleNavigation.filter())
async def navigate_user_schedule(
    callback: CallbackQuery,
    callback_data: MipScheduleNavigation,
    stp_repo: MainRequestsRepo,
):
    """Навигация по месяцам в расписании пользователя"""
    user_id = callback_data.user_id
    action = callback_data.action
    month_idx = callback_data.month_idx
    return_to = callback_data.return_to
    head_id = callback_data.head_id

    try:
        # Получаем пользователя
        user = await stp_repo.employee.get_user(user_id=user_id)
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        # Определяем компактность вывода
        compact = action not in ["detailed"]

        # Преобразуем индекс месяца в название
        month_to_display = get_month_name_by_index(month_idx)

        try:
            # Получаем расписание пользователя с дежурствами
            schedule_response = await schedule_service.get_user_schedule_response(
                user=user, month=month_to_display, compact=compact, stp_repo=stp_repo
            )

            await callback.message.edit_text(
                f"""<b>📅 График сотрудника</b>

<b>ФИО:</b> <a href='t.me/{user.username}'>{user.fullname}</a>
<b>Подразделение:</b> {user.position or "Не указано"} {user.division or "Не указано"}

<blockquote>{schedule_response}</blockquote>""",
                reply_markup=user_schedule_with_month_kb(
                    user_id=user_id,
                    current_month=month_to_display,
                    return_to=return_to,
                    head_id=head_id,
                    is_detailed=not compact,
                ),
            )

        except Exception as schedule_error:
            # Если не удалось получить расписание, показываем ошибку
            error_message = "❌ График для данного сотрудника не найдено"
            if "не найден" in str(schedule_error).lower():
                error_message = f"❌ Сотрудник {user.fullname} не найден в графике"
            elif "файл" in str(schedule_error).lower():
                error_message = "❌ Файл графика недоступен"

            await callback.message.edit_text(
                f"""<b>📅 График сотрудника</b>

<b>ФИО:</b> <a href='t.me/{user.username}'>{user.fullname}</a>
<b>Подразделение:</b> {user.position or "Не указано"} {user.division or "Не указано"}

{error_message}

<i>Возможно, сотрудник не включен в текущий график или файл недоступен.</i>""",
                reply_markup=user_schedule_with_month_kb(
                    user_id=user_id,
                    current_month=month_to_display,
                    return_to=return_to,
                    head_id=head_id,
                    is_detailed=not compact,
                ),
            )

    except Exception as e:
        logger.error(f"Ошибка при навигации по расписанию пользователя {user_id}: {e}")
        await callback.answer("❌ Ошибка при получении расписания", show_alert=True)


@mip_search_router.callback_query(SelectUserRole.filter())
async def process_role_change(
    callback: CallbackQuery, callback_data: SelectUserRole, stp_repo: MainRequestsRepo
):
    """Обработка изменения роли пользователя"""
    user_id = callback_data.user_id
    new_role = callback_data.role

    try:
        # Получаем данные пользователя
        user = await stp_repo.employee.get_user(user_id=user_id)
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        # Проверяем, что роль действительно изменилась
        if user.role == new_role:
            await callback.answer("❌ Пользователь уже имеет эту роль", show_alert=True)
            return

        # Получаем названия ролей
        old_role_name = (
            role_names[user.role]
            if user.role < len(role_names)
            else f"Неизвестный уровень ({user.role})"
        )
        new_role_name = (
            role_names[new_role]
            if new_role < len(role_names)
            else f"Неизвестный уровень ({new_role})"
        )

        # Обновляем роль в базе данных
        await stp_repo.employee.update_user(user_id=user_id, role=new_role)

        # Отправляем уведомление пользователю о смене роли
        try:
            await callback.bot.send_message(
                chat_id=user_id,
                text=f"""<b>🔔 Изменение роли</b>

Уровень был изменен: {old_role_name} → {new_role_name}

<i>Изменения могут повлиять на доступные функции бота</i>""",
            )
        except Exception as notify_error:
            logger.error(
                f"Не удалось отправить уведомление пользователю {user_id}: {notify_error}"
            )

        logger.info(
            f"[МИП] - [Изменение роли] {callback.from_user.username} ({callback.from_user.id}) изменил роль пользователя {user_id}: {old_role_name} → {new_role_name}"
        )

        # Возвращаемся к информации о пользователе
        # Создаем новый callback_data для возврата к пользователю
        user_callback_data = SearchUserResult(user_id=user_id)
        await show_user_details(callback, user_callback_data, stp_repo)

    except Exception as e:
        logger.error(f"Ошибка при изменении роли пользователя {user_id}: {e}")
        await callback.answer("❌ Ошибка при сохранении роли", show_alert=True)


# Обработчики для search-специфичных callback data (для интеграции с head group members)


@mip_search_router.callback_query(HeadGroupMembersMenuForSearch.filter())
async def group_members_pagination_cb_search(
    callback: CallbackQuery,
    callback_data: HeadGroupMembersMenuForSearch,
    stp_repo: MainRequestsRepo,
):
    """Обработчик пагинации списка участников группы из поиска"""
    head_id = callback_data.head_id
    page = callback_data.page

    try:
        # Получаем информацию о руководителе
        head_user = await stp_repo.employee.get_user(user_id=head_id)
        if not head_user:
            await callback.answer("❌ Руководитель не найден", show_alert=True)
            return

        # Получаем всех сотрудников этого руководителя
        group_members = await stp_repo.employee.get_users_by_head(head_user.fullname)

        if not group_members:
            await callback.answer("❌ Участники не найдены", show_alert=True)
            return

        total_members = len(group_members)

        message_text = f"""👥 <b>Группа: {head_user.fullname}</b>

Участники группы: <b>{total_members}</b>

<blockquote><b>Обозначения</b>
🔒 - не авторизован в боте
👮 - дежурный
🔨 - root</blockquote>

<i>Нажми на участника для просмотра подробной информации</i>"""

        await callback.message.edit_text(
            message_text,
            reply_markup=head_group_members_kb_for_search(
                group_members, current_page=page, head_id=head_id
            ),
        )

    except Exception as e:
        logger.error(f"Ошибка при пагинации группы руководителя {head_id}: {e}")
        await callback.answer("❌ Ошибка при получении данных", show_alert=True)


@mip_search_router.callback_query(HeadMemberDetailMenuForSearch.filter())
async def member_detail_cb_search(
    callback: CallbackQuery,
    callback_data: HeadMemberDetailMenuForSearch,
    stp_repo: MainRequestsRepo,
):
    """Обработчик детального просмотра участника группы из поиска"""
    member_id = callback_data.member_id
    head_id = callback_data.head_id
    page = callback_data.page

    try:
        # Поиск участника по ID
        all_users = await stp_repo.employee.get_users()
        member = None
        for user in all_users:
            if user.id == member_id:
                member = user
                break

        if not member:
            await callback.answer("❌ Участник не найден", show_alert=True)
            return

        # Формируем информацию об участнике
        message_text = f"""👤 <b>Информация об участнике</b>

<b>ФИО:</b> <a href="https://t.me/{member.username}">{member.fullname}</a>
<b>Должность:</b> {member.position or "Не указано"} {member.division or ""}
<b>Email:</b> {member.email or "Не указано"}

🛡️ <b>Уровень доступа:</b> <code>{role_names.get(member.role, "Неизвестно")}</code>"""

        # Добавляем статус только для неавторизованных пользователей
        if not member.user_id:
            message_text += "\n<b>Статус:</b> 🔒 Не авторизован в боте"

        message_text += "\n\n<i>Выбери действие:</i>"

        await callback.message.edit_text(
            message_text,
            reply_markup=head_member_detail_kb_for_search(
                member_id, head_id, page, member.role
            ),
        )

    except Exception as e:
        logger.error(f"Ошибка при просмотре участника {member_id}: {e}")
        await callback.answer(
            "❌ Ошибка при получении данных участника", show_alert=True
        )


@mip_search_router.callback_query(HeadMemberActionMenuForSearch.filter())
async def member_action_cb_search(
    callback: CallbackQuery,
    callback_data: HeadMemberActionMenuForSearch,
    stp_repo: MainRequestsRepo,
    kpi_repo: KPIRequestsRepo,
):
    """Обработчик действий с участником (расписание/KPI/игра) из поиска"""
    member_id = callback_data.member_id
    head_id = callback_data.head_id
    action = callback_data.action
    page = callback_data.page

    try:
        # Поиск участника по ID
        all_users = await stp_repo.employee.get_users()
        member = None
        for user in all_users:
            if user.id == member_id:
                member = user
                break

        if not member:
            await callback.answer("❌ Участник не найден", show_alert=True)
            return

        if action == "schedule":
            # Вызываем обработчик просмотра расписания
            schedule_callback_data = SearchMemberScheduleMenu(
                member_id=member.id, head_id=head_id, month_idx=0, page=page
            )
            await view_search_member_schedule(
                callback, schedule_callback_data, stp_repo
            )
            return

        elif action == "game_profile":
            # Проверяем, что у участника есть user_id (авторизован в боте)
            if not member.user_id:
                await callback.message.edit_text(
                    f"""🏮 <b>Игровой профиль</b>

<b>ФИО:</b> <a href="https://t.me/{member.username}">{member.fullname}</a>

❌ <b>Пользователь не авторизован в боте</b>

<i>Игровой профиль доступен только для авторизованных пользователей</i>""",
                    reply_markup=head_member_detail_kb_for_search(
                        member_id, head_id, page, member.role
                    ),
                )
                return

            user_balance = await stp_repo.transaction.get_user_balance(
                user_id=member.user_id
            )
            achievements_sum = await stp_repo.transaction.get_user_achievements_sum(
                user_id=member.user_id
            )
            purchases_sum = await stp_repo.purchase.get_user_purchases_sum(
                user_id=member.user_id
            )
            level_info_text = LevelingSystem.get_level_info_text(
                achievements_sum, user_balance
            )

            # Формируем сообщение с игровым профилем
            message_text = f"""🏮 <b>Игровой профиль</b>

<b>ФИО:</b> <a href="https://t.me/{member.username}">{member.fullname}</a>
<b>Должность:</b> {member.position or "Не указано"} {member.division or ""}

{level_info_text}

<blockquote expandable><b>✨ Баланс</b>
Всего заработано: {achievements_sum} баллов
Всего потрачено: {purchases_sum} баллов</blockquote>"""

            await callback.message.edit_text(
                message_text,
                reply_markup=head_member_detail_kb_for_search(
                    member_id, head_id, page, member.role
                ),
            )
            return

        else:
            await callback.answer("❌ Неизвестное действие", show_alert=True)
            return

    except Exception as e:
        logger.error(
            f"Ошибка при выполнении действия {action} для участника {member_id}: {e}"
        )
        await callback.answer("❌ Ошибка при выполнении действия", show_alert=True)


@mip_search_router.callback_query(HeadMemberRoleChangeForSearch.filter())
async def change_member_role_search(
    callback: CallbackQuery,
    callback_data: HeadMemberRoleChangeForSearch,
    stp_repo: MainRequestsRepo,
):
    """Обработчик смены роли участника группы из поиска"""
    member_id = callback_data.member_id
    head_id = callback_data.head_id
    page = callback_data.page

    try:
        # Поиск участника по ID
        all_users = await stp_repo.employee.get_users()
        member = None
        for user in all_users:
            if user.id == member_id:
                member = user
                break

        if not member:
            await callback.answer("❌ Участник не найден", show_alert=True)
            return

        # Проверяем, что роль может быть изменена
        if member.role not in [1, 3]:
            await callback.answer(
                "❌ Уровень доступа этого пользователя нельзя изменить", show_alert=True
            )
            return

        # Определяем новый уровень доступа
        new_role = 3 if member.role == 1 else 1
        old_role_name = "Специалист" if member.role == 1 else "Дежурный"
        new_role_name = "Дежурный" if new_role == 3 else "Специалист"

        # Обновляем уровень в базе данных
        await stp_repo.employee.update_user(user_id=member.user_id, role=new_role)

        # Отправляем уведомление пользователю о смене роли (только если он авторизован)
        if member.user_id:
            try:
                await callback.bot.send_message(
                    chat_id=member.user_id,
                    text=f"""<b>🔔 Изменение роли</b>

Уровень был изменен: {old_role_name} → {new_role_name}

<i>Изменения могут повлиять на доступные функции бота</i>""",
                )
                await callback.answer(
                    "Отправили специалисту уведомление об изменении роли"
                )
            except Exception as e:
                await callback.answer("Не удалось отправить уведомление специалисту :(")
                logger.error(
                    f"Не удалось отправить уведомление пользователю {member.user_id}: {e}"
                )

        logger.info(
            f"[МИП] - [Изменение роли] {callback.from_user.username} ({callback.from_user.id}) изменил роль участника {member_id}: {old_role_name} → {new_role_name}"
        )

        # Возвращаемся к детальной информации участника
        member_detail_callback_data = HeadMemberDetailMenuForSearch(
            member_id=member_id, head_id=head_id, page=page
        )
        await member_detail_cb_search(callback, member_detail_callback_data, stp_repo)

    except Exception as e:
        logger.error(f"Ошибка при изменении роли участника {member_id}: {e}")
        await callback.answer("❌ Ошибка при изменении роли", show_alert=True)


@mip_search_router.callback_query(SearchMemberScheduleMenu.filter())
async def view_search_member_schedule(
    callback: CallbackQuery,
    callback_data: SearchMemberScheduleMenu,
    stp_repo: MainRequestsRepo,
):
    """Обработчик просмотра расписания участника группы из поиска"""
    member_id = callback_data.member_id
    head_id = callback_data.head_id
    requested_month_idx = callback_data.month_idx
    page = callback_data.page

    try:
        # Поиск участника по ID
        all_users = await stp_repo.employee.get_users()
        member = None
        for user in all_users:
            if user.id == member_id:
                member = user
                break

        if not member:
            await callback.answer("❌ Участник не найден", show_alert=True)
            return

        # Определяем месяц для отображения
        if requested_month_idx > 0:
            current_month = get_month_name_by_index(requested_month_idx)
        else:
            current_month = schedule_service.get_current_month()

        try:
            # Получаем расписание участника (компактный формат) с дежурствами
            schedule_response = await schedule_service.get_user_schedule_response(
                user=member, month=current_month, compact=True, stp_repo=stp_repo
            )

            await callback.message.edit_text(
                f"""📅 <b>График участника</b>

<b>ФИО:</b> <a href="https://t.me/{member.username}">{member.fullname}</a>
<b>Должность:</b> {member.position or "Не указано"} {member.division or "Не указано"}

<blockquote>{schedule_response}</blockquote>""",
                reply_markup=search_member_schedule_kb(
                    member_id=member_id,
                    head_id=head_id,
                    current_month=current_month,
                    page=page,
                    is_detailed=False,
                ),
            )

        except Exception as schedule_error:
            # Если не удалось получить расписание, показываем ошибку
            error_message = "❌ График для данного сотрудника не найдено"
            if "не найден" in str(schedule_error).lower():
                error_message = f"❌ Сотрудник {member.fullname} не найден в графике"
            elif "файл" in str(schedule_error).lower():
                error_message = "❌ Файл графика недоступен"

            await callback.message.edit_text(
                f"""📅 <b>График участника</b>

<b>ФИО:</b> <a href="https://t.me/{member.username}">{member.fullname}</a>
<b>Должность:</b> {member.position or "Не указано"} {member.division or "Не указано"}

{error_message}

<i>Возможно, сотрудник не включен в текущий график или файл недоступен.</i>""",
                reply_markup=search_member_schedule_kb(
                    member_id=member_id,
                    head_id=head_id,
                    current_month=current_month,
                    page=page,
                    is_detailed=False,
                ),
            )

    except Exception as e:
        logger.error(f"Ошибка при получении расписания участника {member_id}: {e}")
        await callback.answer("❌ Ошибка при получении расписания", show_alert=True)


@mip_search_router.callback_query(SearchMemberScheduleNavigation.filter())
async def navigate_search_member_schedule(
    callback: CallbackQuery,
    callback_data: SearchMemberScheduleNavigation,
    stp_repo: MainRequestsRepo,
):
    """Навигация по расписанию участника группы из поиска"""
    member_id = callback_data.member_id
    head_id = callback_data.head_id
    action = callback_data.action
    month_idx = callback_data.month_idx
    page = callback_data.page

    try:
        # Поиск участника по ID
        all_users = await stp_repo.employee.get_users()
        member = None
        for user in all_users:
            if user.id == member_id:
                member = user
                break

        if not member:
            await callback.answer("❌ Участник не найден", show_alert=True)
            return

        # Определяем компактность вывода
        compact = action not in ["detailed"]

        # Преобразуем индекс месяца в название
        month_to_display = get_month_name_by_index(month_idx)

        try:
            # Получаем график участника с дежурствами
            schedule_response = await schedule_service.get_user_schedule_response(
                user=member, month=month_to_display, compact=compact, stp_repo=stp_repo
            )

            await callback.message.edit_text(
                f"""📅 <b>График участника</b>

<b>ФИО:</b> <a href="https://t.me/{member.username}">{member.fullname}</a>
<b>Должность:</b> {member.position or "Не указано"} {member.division or "Не указано"}

<blockquote>{schedule_response}</blockquote>""",
                reply_markup=search_member_schedule_kb(
                    member_id=member_id,
                    head_id=head_id,
                    current_month=month_to_display,
                    page=page,
                    is_detailed=not compact,
                ),
            )

        except Exception as schedule_error:
            # Если не удалось получить расписание, показываем ошибку
            error_message = "❌ График для данного сотрудника не найдено"
            if "не найден" in str(schedule_error).lower():
                error_message = f"❌ Сотрудник {member.fullname} не найден в графике"
            elif "файл" in str(schedule_error).lower():
                error_message = "❌ Файл графика недоступен"

            await callback.message.edit_text(
                f"""📅 <b>График участника</b>

<b>ФИО:</b> <a href="https://t.me/{member.username}">{member.fullname}</a>
<b>Должность:</b> {member.position or "Не указано"} {member.division or "Не указано"}

{error_message}

<i>Возможно, сотрудник не включен в текущий график или файл недоступен.</i>""",
                reply_markup=search_member_schedule_kb(
                    member_id=member_id,
                    head_id=head_id,
                    current_month=month_to_display,
                    page=page,
                    is_detailed=not compact,
                ),
            )

    except Exception as e:
        logger.error(f"Ошибка при навигации по расписанию участника {member_id}: {e}")
        await callback.answer("❌ Ошибка при получении расписания", show_alert=True)
