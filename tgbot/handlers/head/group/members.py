import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from infrastructure.database.models import Employee
from infrastructure.database.repo.KPI.requests import KPIRequestsRepo
from infrastructure.database.repo.STP.requests import MainRequestsRepo
from tgbot.dialogs.getters.common.schedule_getters import schedule_service
from tgbot.filters.role import HeadFilter
from tgbot.keyboards.head.group.game_profile import (
    HeadMemberGameHistoryMenu,
    HeadMemberGameProfileMenu,
    HeadMemberTransactionDetailMenu,
    head_member_game_history_kb,
    head_member_game_profile_kb,
    head_member_transaction_detail_kb,
)
from tgbot.keyboards.head.group.main import GroupManagementMenu
from tgbot.keyboards.head.group.members import (
    HeadGroupMembersMenu,
    HeadMemberActionMenu,
    HeadMemberDetailMenu,
    HeadMemberKPIMenu,
    HeadMemberScheduleMenu,
    HeadMemberScheduleNavigation,
    HeadMemberStatusChange,
    HeadMemberStatusSelect,
    get_month_name_by_index,
    head_group_members_kb,
    head_member_detail_kb,
    head_member_schedule_kb,
)
from tgbot.keyboards.head.group.members_kpi import head_member_kpi_kb
from tgbot.keyboards.head.group.members_status import head_member_status_select_kb
from tgbot.misc.helpers import get_role
from tgbot.services.salary import KPICalculator, SalaryCalculator, SalaryFormatter

head_group_members_router = Router()
head_group_members_router.message.filter(F.chat.type == "private", HeadFilter())
head_group_members_router.callback_query.filter(
    F.message.chat.type == "private", HeadFilter()
)

logger = logging.getLogger(__name__)


@head_group_members_router.callback_query(
    GroupManagementMenu.filter(F.menu == "members")
)
async def group_mgmt_members_cb(
    callback: CallbackQuery, user: Employee, stp_repo: MainRequestsRepo
):
    """Обработчик состава группы"""
    if not user:
        await callback.message.edit_text(
            """❌ <b>Ошибка</b>
            
Не удалось найти информацию в базе данных."""
        )
        return

    # Получаем всех сотрудников этого руководителя
    group_members = await stp_repo.employee.get_users_by_head(user.fullname)

    if not group_members:
        await callback.message.edit_text(
            """👥 <b>Состав группы</b>

У тебя пока нет подчиненных в системе
            
<i>Если это ошибка, обратись к администратору.</i>""",
            reply_markup=head_group_members_kb([], current_page=1),
        )
        return

    # Показываем первую страницу по умолчанию
    total_members = len(group_members)

    message_text = f"""👥 <b>Состав группы</b>

Участники твоей группы: <b>{total_members}</b>

<blockquote><b>Обозначения</b>
🔒 - не авторизован в боте
👮 - дежурный
👶🏻 - стажер
🔨 - root</blockquote>

<i>Нажми на участника для просмотра подробной информации</i>"""

    await callback.message.edit_text(
        message_text,
        reply_markup=head_group_members_kb(group_members, current_page=1),
    )


@head_group_members_router.callback_query(HeadGroupMembersMenu.filter())
async def group_members_pagination_cb(
    callback: CallbackQuery,
    callback_data: HeadGroupMembersMenu,
    user: Employee,
    stp_repo: MainRequestsRepo,
):
    """Обработчик пагинации списка участников группы"""
    if not user:
        await callback.answer("❌ Ошибка получения данных", show_alert=True)
        return

    # Получаем всех сотрудников этого руководителя
    group_members = await stp_repo.employee.get_users_by_head(user.fullname)

    if not group_members:
        await callback.answer("❌ Участники не найдены", show_alert=True)
        return

    total_members = len(group_members)
    page = callback_data.page

    message_text = f"""👥 <b>Состав группы</b>

Участники твоей группы: <b>{total_members}</b>

<blockquote><b>Обозначения</b>
🔒 - не авторизован в боте
👮 - дежурный
👶🏻 - стажер
🔨 - root</blockquote>

<i>Нажми на участника для просмотра подробной информации</i>"""

    await callback.message.edit_text(
        message_text,
        reply_markup=head_group_members_kb(group_members, current_page=page),
    )


@head_group_members_router.callback_query(HeadMemberDetailMenu.filter())
async def member_detail_cb(
    callback: CallbackQuery,
    callback_data: HeadMemberDetailMenu,
    stp_repo: MainRequestsRepo,
):
    """Обработчик детального просмотра участника группы"""
    member = await stp_repo.employee.get_user(main_id=callback_data.member_id)

    if not member:
        await callback.answer("❌ Участник не найден", show_alert=True)
        return

    # Формируем информацию об участнике
    message_text = f"""👤 <b>Информация об участнике</b>

<b>ФИО:</b> <a href="https://t.me/{member.username}">{member.fullname}</a>
<b>Должность:</b> {member.position or "Не указано"} {member.division or ""}
<b>Email:</b> {member.email or "Не указано"}

🛡️ <b>Уровень доступа:</b> {get_role(member.role)["name"]}"""

    # Добавляем статус только для неавторизованных пользователей
    if not member.user_id:
        message_text += "\n<b>Статус:</b> 🔒 Не авторизован в боте"

    await callback.message.edit_text(
        message_text,
        reply_markup=head_member_detail_kb(member, callback_data.page, member.role),
    )


@head_group_members_router.callback_query(HeadMemberActionMenu.filter())
async def member_action_cb(
    callback: CallbackQuery,
    callback_data: HeadMemberActionMenu,
    stp_repo: MainRequestsRepo,
):
    """Обработчик действий с участником (расписание/KPI)"""
    member = await stp_repo.employee.get_user(main_id=callback_data.member_id)

    if not member:
        await callback.answer("❌ Участник не найден", show_alert=True)
        return

    if callback_data.action == "schedule":
        # Вызываем обработчик просмотра расписания
        schedule_callback_data = HeadMemberScheduleMenu(
            member_id=member.id, month_idx=0, page=callback_data.page
        )
        await view_member_schedule(callback, schedule_callback_data, stp_repo)
        return

    elif callback_data.action == "game_profile":
        # Вызываем обработчик просмотра игрового профиля
        game_profile_callback_data = HeadMemberGameProfileMenu(
            member_id=member.id, page=callback_data.page
        )
        await view_member_game_profile(callback, game_profile_callback_data, stp_repo)
        return

    elif callback_data.action == "casino":
        if member.is_casino_allowed:
            await stp_repo.employee.update_user(
                user_id=member.user_id, is_casino_allowed=False
            )
        else:
            await stp_repo.employee.update_user(
                user_id=member.user_id, is_casino_allowed=True
            )
        await member_detail_cb(
            callback,
            callback_data=HeadMemberDetailMenu(member_id=member.id),
            stp_repo=stp_repo,
        )

    else:
        await callback.answer("❌ Неизвестное действие", show_alert=True)
        return


@head_group_members_router.callback_query(HeadMemberScheduleMenu.filter())
async def view_member_schedule(
    callback: CallbackQuery,
    callback_data: HeadMemberScheduleMenu,
    stp_repo: MainRequestsRepo,
):
    """Обработчик просмотра расписания участника группы"""
    member_id = callback_data.member_id
    requested_month_idx = callback_data.month_idx
    page = callback_data.page

    try:
        member = await stp_repo.employee.get_user(main_id=member_id)

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
                reply_markup=head_member_schedule_kb(
                    member_id=member_id,
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
                reply_markup=head_member_schedule_kb(
                    member_id=member_id,
                    current_month=current_month,
                    page=page,
                    is_detailed=False,
                ),
            )

    except Exception as e:
        logger.error(f"Ошибка при получении расписания участника {member_id}: {e}")
        await callback.answer("❌ Ошибка при получении расписания", show_alert=True)


@head_group_members_router.callback_query(HeadMemberScheduleNavigation.filter())
async def navigate_member_schedule(
    callback: CallbackQuery,
    callback_data: HeadMemberScheduleNavigation,
    stp_repo: MainRequestsRepo,
):
    """Навигация по расписанию участника группы"""
    member_id = callback_data.member_id
    action = callback_data.action
    month_idx = callback_data.month_idx
    page = callback_data.page

    try:
        member = await stp_repo.employee.get_user(main_id=member_id)

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
                reply_markup=head_member_schedule_kb(
                    member_id=member_id,
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
                reply_markup=head_member_schedule_kb(
                    member_id=member_id,
                    current_month=month_to_display,
                    page=page,
                    is_detailed=not compact,
                ),
            )

    except Exception as e:
        logger.error(f"Ошибка при навигации по расписанию участника {member_id}: {e}")
        await callback.answer("❌ Ошибка при получении расписания", show_alert=True)


@head_group_members_router.callback_query(HeadMemberKPIMenu.filter())
async def view_member_kpi(
    callback: CallbackQuery,
    callback_data: HeadMemberKPIMenu,
    user: Employee,
    stp_repo: MainRequestsRepo,
    kpi_repo: KPIRequestsRepo,
):
    """Обработчик KPI меню участника группы"""
    member_id = callback_data.member_id
    action = callback_data.action
    page = callback_data.page

    message_text = ""

    try:
        member = await stp_repo.employee.get_user(main_id=member_id)

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
                    reply_markup=head_member_kpi_kb(member_id, page, action),
                )
                return

            if action == "main":
                message_text = f"""🌟 <b>Показатели</b>

<b>ФИО:</b> <a href="https://t.me/{member.username}">{member.fullname}</a>
<b>Должность:</b> {member.position or "Не указано"} {member.division or ""}

📊 <b>Оценка клиента - {SalaryFormatter.format_percentage(premium.csi_premium)}</b>
<blockquote>Факт: {SalaryFormatter.format_value(premium.csi)}
План: {SalaryFormatter.format_value(premium.csi_normative)}</blockquote>

🎯 <b>Отклик</b>
<blockquote>Факт: {SalaryFormatter.format_value(premium.csi_response)}
План: {SalaryFormatter.format_value(round(premium.csi_response_normative)) if premium.csi_response_normative else "—"}</blockquote>

🔧 <b>FLR - {SalaryFormatter.format_percentage(premium.flr_premium)}</b>
<blockquote>Факт: {SalaryFormatter.format_value(premium.flr)}
План: {SalaryFormatter.format_value(premium.flr_normative)}</blockquote>

⚖️ <b>ГОК - {SalaryFormatter.format_percentage(premium.gok_premium)}</b>
<blockquote>Факт: {SalaryFormatter.format_value(premium.gok)}
План: {SalaryFormatter.format_value(premium.gok_normative)}</blockquote>

🎯 <b>Цель - {SalaryFormatter.format_percentage(premium.target_premium)}</b>
<blockquote>Тип: {premium.target_type or "—"}
Факт: {SalaryFormatter.format_value(premium.target)}
План: {SalaryFormatter.format_value(round(premium.target_goal_first)) if premium.target_goal_first else "—"} / {SalaryFormatter.format_value(round(premium.target_goal_second)) if premium.target_goal_second else "—"}</blockquote>

💼 <b>Дополнительно</b>
<blockquote>Дисциплина: {SalaryFormatter.format_percentage(premium.discipline_premium)}
Тестирование: {SalaryFormatter.format_percentage(premium.tests_premium)}
Благодарности: {SalaryFormatter.format_percentage(premium.thanks_premium)}
Наставничество: {SalaryFormatter.format_percentage(premium.tutors_premium)}
Ручная правка: {SalaryFormatter.format_percentage(premium.head_adjust_premium)}</blockquote>

💰 <b>Итого:</b>
<b>Общая премия: {SalaryFormatter.format_percentage(premium.total_premium)}</b>

{"📈 Всего чатов: " + SalaryFormatter.format_value(premium.contacts_count) if member.division == "НЦК" else "📈 Всего звонков: " + SalaryFormatter.format_value(premium.contacts_count)}
{"⏰ Задержка: " + SalaryFormatter.format_value(premium.delay, " сек") if member.division != "НЦК" else ""}

<i>Выгружено: {premium.updated_at.strftime("%d.%m.%y %H:%M") if premium.updated_at else "—"}</i>"""

            elif action == "calculator":
                csi_calculation = KPICalculator.calculate_csi_needed(
                    member.division, premium.csi, premium.csi_normative
                )
                flr_calculation = KPICalculator.calculate_flr_needed(
                    member.division, premium.flr, premium.flr_normative
                )
                gok_calculation = KPICalculator.calculate_gok_needed(
                    member.division, premium.gok, premium.gok_normative
                )
                target_calculation = KPICalculator.calculate_target_needed(
                    premium.target,
                    premium.target_goal_first,
                    premium.target_goal_second,
                    premium.target_type,
                )

                message_text = f"""🧮 <b>Калькулятор KPI</b>

<b>ФИО:</b> <a href="https://t.me/{member.username}">{member.fullname}</a>
<b>Должность:</b> {member.position or "Не указано"} {member.division or ""}

📊 <b>Оценка клиента</b>
<blockquote>Текущий: {SalaryFormatter.format_value(premium.csi)} ({SalaryFormatter.format_percentage(premium.csi_normative_rate)})
План: {SalaryFormatter.format_value(premium.csi_normative)}

<b>Для премии:</b>
{csi_calculation}</blockquote>

🔧 <b>FLR</b>
<blockquote>Текущий: {SalaryFormatter.format_value(premium.flr)} ({SalaryFormatter.format_percentage(premium.flr_normative_rate)})
План: {SalaryFormatter.format_value(premium.flr_normative)}

<b>Для премии:</b>
{flr_calculation}</blockquote>

⚖️ <b>ГОК</b>
<blockquote>Текущий: {SalaryFormatter.format_value(round(premium.gok))} ({SalaryFormatter.format_percentage(premium.gok_normative_rate)})
План: {SalaryFormatter.format_value(round(premium.gok_normative))}

<b>Для премии:</b>
{gok_calculation}</blockquote>

🎯 <b>Цель</b>
<blockquote>Факт: {SalaryFormatter.format_value(premium.target)} ({SalaryFormatter.format_percentage(round((premium.target_goal_first / premium.target * 100) if premium.target_type and "AHT" in premium.target_type and premium.target and premium.target > 0 and premium.target_goal_first else (premium.target / premium.target_goal_first * 100) if premium.target_goal_first and premium.target_goal_first > 0 else 0))} / {SalaryFormatter.format_percentage(round((premium.target_goal_second / premium.target * 100) if premium.target_type and "AHT" in premium.target_type and premium.target and premium.target > 0 and premium.target_goal_second else (premium.target / premium.target_goal_second * 100) if premium.target_goal_second and premium.target_goal_second > 0 else 0))})
План: {SalaryFormatter.format_value(round(premium.target_goal_first))} / {SalaryFormatter.format_value(round(premium.target_goal_second))}

Требуется минимум 100 {"чатов" if member.division == "НЦК" else "звонков"} для получения премии за цель

<b>Для премии:</b>
{target_calculation}</blockquote>

<i>Данные от: {premium.updated_at.strftime("%d.%m.%y %H:%M") if premium.updated_at else "—"}</i>"""

            elif action == "salary":
                user_premium = await kpi_repo.spec_premium.get_premium(
                    fullname=user.fullname
                )

                salary_result = await SalaryCalculator.calculate_salary(
                    user=user, premium_data=user_premium
                )

                message_text = SalaryFormatter.format_salary_message(
                    salary_result, user_premium
                )

        except Exception as e:
            logger.error(f"Ошибка при получении KPI для {member.fullname}: {e}")

            message_text = f"""📊 <b>KPI: {member.fullname}</b>

❌ <b>Ошибка загрузки данных</b>

Произошла ошибка при получении показателей

<i>Попробуй позже или обратись к администратору для проверки данных.</i>"""

        await callback.message.edit_text(
            message_text,
            reply_markup=head_member_kpi_kb(member_id, page, action),
        )

    except Exception as e:
        logger.error(f"Ошибка при просмотре KPI участника {member_id}: {e}")
        await callback.answer("❌ Ошибка при получении KPI", show_alert=True)


@head_group_members_router.callback_query(HeadMemberStatusSelect.filter())
async def show_member_status_select(
    callback: CallbackQuery,
    callback_data: HeadMemberStatusSelect,
    stp_repo: MainRequestsRepo,
):
    """Обработчик показа меню выбора статуса участника группы"""
    member_id = callback_data.member_id
    page = callback_data.page

    try:
        member = await stp_repo.employee.get_user(main_id=member_id)

        if not member:
            await callback.answer("❌ Участник не найден", show_alert=True)
            return

        # Проверяем, что роль может быть изменена
        if member.role not in [1, 3]:
            await callback.answer(
                "❌ Уровень доступа этого пользователя нельзя изменить", show_alert=True
            )
            return

        # Формируем информацию об участнике
        message_text = f"""⚙️ <b>Изменение статуса</b>

<b>ФИО:</b> <a href="https://t.me/{member.username}">{member.fullname}</a>
<b>Должность:</b> {member.position or "Не указано"} {member.division or ""}

<i>Выбери новый статус для участника:</i>"""

        await callback.message.edit_text(
            message_text,
            reply_markup=head_member_status_select_kb(
                member_id=member_id,
                page=page,
                current_role=member.role,
                is_trainee=member.is_trainee,
            ),
        )

    except Exception as e:
        logger.error(
            f"Ошибка при отображении выбора статуса участника {member_id}: {e}"
        )
        await callback.answer("❌ Ошибка при отображении меню", show_alert=True)


@head_group_members_router.callback_query(HeadMemberStatusChange.filter())
async def change_member_status(
    callback: CallbackQuery,
    callback_data: HeadMemberStatusChange,
    stp_repo: MainRequestsRepo,
):
    """Обработчик изменения статуса участника группы (стажер/дежурный)"""
    member_id = callback_data.member_id
    status_type = callback_data.status_type

    try:
        member = await stp_repo.employee.get_user(main_id=member_id)

        if not member:
            await callback.answer("❌ Участник не найден", show_alert=True)
            return

        # Проверяем, что роль может быть изменена
        if member.role not in [1, 3] and status_type == "duty":
            await callback.answer(
                "❌ Уровень доступа этого пользователя нельзя изменить", show_alert=True
            )
            return

        notification_text = ""
        changes_made = False

        if status_type == "trainee":
            # Переключаем статус стажера
            new_trainee_status = not member.is_trainee
            await stp_repo.employee.update_user(
                user_id=member.user_id, is_trainee=new_trainee_status
            )

            status_text = "стажер" if new_trainee_status else "не стажер"
            notification_text = f"Статус стажера изменен: {status_text}"
            changes_made = True

            logger.info(
                f"[Руководитель] - [Изменение статуса стажера] {callback.from_user.username} ({callback.from_user.id}) изменил статус стажера участника {member_id}: {member.is_trainee}"
            )

        elif status_type == "duty":
            # Определяем старую и новую роль ДО изменения
            old_role_name = "Дежурный" if member.role == 3 else "Специалист"
            new_role = 1 if member.role == 3 else 3
            new_role_name = "Специалист" if new_role == 1 else "Дежурный"

            # Переключаем роль дежурного
            await stp_repo.employee.update_user(user_id=member.user_id, role=new_role)

            notification_text = f"Роль изменена: {old_role_name} → {new_role_name}"
            changes_made = True

            # Отправляем уведомление пользователю о смене роли (только если он авторизован)
            if member.user_id:
                try:
                    await callback.bot.send_message(
                        chat_id=member.user_id,
                        text=f"""<b>🔔 Изменение роли</b>

Уровень был изменен: {old_role_name} → {new_role_name}

<i>Изменения могут повлиять на доступные функции бота</i>""",
                    )
                except TelegramBadRequest as e:
                    logger.error(
                        f"Не удалось отправить уведомление пользователю {member.user_id}: {e}"
                    )

            logger.info(
                f"[Руководитель] - [Изменение роли] {callback.from_user.username} ({callback.from_user.id}) изменил роль участника {member_id}: {old_role_name} → {new_role_name}"
            )

        if changes_made:
            await callback.answer(notification_text)

            await show_member_status_select(
                callback,
                HeadMemberStatusSelect(member_id=member.id),
                stp_repo,
            )
        else:
            await callback.answer("❌ Неизвестный тип статуса", show_alert=True)

    except Exception as e:
        logger.error(f"Ошибка при изменении статуса участника {member_id}: {e}")
        await callback.answer("❌ Ошибка при изменении статуса", show_alert=True)


@head_group_members_router.callback_query(HeadMemberGameProfileMenu.filter())
async def view_member_game_profile(
    callback: CallbackQuery,
    callback_data: HeadMemberGameProfileMenu,
    stp_repo: MainRequestsRepo,
):
    """Обработчик просмотра игрового профиля участника группы"""
    from tgbot.services.leveling import LevelingSystem

    member_id = callback_data.member_id
    page = callback_data.page

    try:
        member = await stp_repo.employee.get_user(main_id=member_id)

        if not member:
            await callback.answer("❌ Участник не найден", show_alert=True)
            return

        # Проверяем, что у участника есть user_id (авторизован в боте)
        if not member.user_id:
            await callback.message.edit_text(
                f"""🏮 <b>Игровой профиль</b>

<b>ФИО:</b> <a href="https://t.me/{member.username}">{member.fullname}</a>

❌ <b>Пользователь не авторизован в боте</b>

<i>Игровой профиль доступен только для авторизованных пользователей</i>""",
                reply_markup=head_member_game_profile_kb(
                    member_id=member.id, page=page
                ),
            )
            return

        # Получаем игровую статистику пользователя
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
            reply_markup=head_member_game_profile_kb(member_id=member.id, page=page),
        )

    except Exception as e:
        logger.error(
            f"Ошибка при получении игрового профиля участника {member_id}: {e}"
        )
        await callback.answer(
            "❌ Ошибка при получении игрового профиля", show_alert=True
        )


@head_group_members_router.callback_query(HeadMemberGameHistoryMenu.filter())
async def view_member_game_history(
    callback: CallbackQuery,
    callback_data: HeadMemberGameHistoryMenu,
    stp_repo: MainRequestsRepo,
):
    """Обработчик просмотра истории транзакций участника группы"""
    member_id = callback_data.member_id
    history_page = callback_data.history_page
    page = callback_data.page

    try:
        member = await stp_repo.employee.get_user(main_id=member_id)

        if not member:
            await callback.answer("❌ Участник не найден", show_alert=True)
            return

        # Проверяем, что у участника есть user_id (авторизован в боте)
        if not member.user_id:
            await callback.message.edit_text(
                f"""📜 <b>История баланса</b>

<b>ФИО:</b> <a href="https://t.me/{member.username}">{member.fullname}</a>

❌ <b>Пользователь не авторизован в боте</b>

<i>История баланса доступна только для авторизованных пользователей</i>""",
                reply_markup=head_member_game_history_kb(
                    member_id=member.id, transactions=[], current_page=1, page=page
                ),
            )
            return

        # Получаем транзакции пользователя
        user_transactions = await stp_repo.transaction.get_user_transactions(
            user_id=member.user_id
        )

        if not user_transactions:
            message_text = f"""📜 <b>История баланса</b>

<b>ФИО:</b> <a href="https://t.me/{member.username}">{member.fullname}</a>
<b>Должность:</b> {member.position or "Не указано"} {member.division or ""}

Здесь отображается вся история операций с баллами

У этого участника пока нет транзакций 🙂

<i>Транзакции появляются при покупке предметов, получении достижений и других операциях с баллами</i>"""
        else:
            total_transactions = len(user_transactions)
            message_text = f"""📜 <b>История баланса</b>

<b>ФИО:</b> <a href="https://t.me/{member.username}">{member.fullname}</a>
<b>Должность:</b> {member.position or "Не указано"} {member.division or ""}

Здесь отображается вся история операций с баллами

<i>Всего транзакций: {total_transactions}</i>"""

        await callback.message.edit_text(
            message_text,
            reply_markup=head_member_game_history_kb(
                member_id=member.id,
                transactions=user_transactions,
                current_page=history_page,
                page=page,
            ),
        )

    except Exception as e:
        logger.error(
            f"Ошибка при получении истории транзакций участника {member_id}: {e}"
        )
        await callback.answer(
            "❌ Ошибка при получении истории транзакций", show_alert=True
        )


@head_group_members_router.callback_query(HeadMemberTransactionDetailMenu.filter())
async def view_member_transaction_detail(
    callback: CallbackQuery,
    callback_data: HeadMemberTransactionDetailMenu,
    stp_repo: MainRequestsRepo,
):
    """Обработчик детального просмотра транзакции участника группы"""
    member_id = callback_data.member_id
    transaction_id = callback_data.transaction_id
    history_page = callback_data.history_page
    page = callback_data.page

    try:
        member = await stp_repo.employee.get_user(main_id=member_id)

        if not member:
            await callback.answer("❌ Участник не найден", show_alert=True)
            return

        # Получаем информацию о транзакции
        transaction = await stp_repo.transaction.get_transaction(transaction_id)

        if not transaction:
            await callback.message.edit_text(
                f"""📊 <b>Детали транзакции</b>

<b>ФИО:</b> <a href="https://t.me/{member.username}">{member.fullname}</a>

❌ Не смог найти информацию о транзакции""",
                reply_markup=head_member_transaction_detail_kb(
                    member_id=member_id, history_page=history_page, page=page
                ),
            )
            return

        # Определяем эмодзи и текст типа операции
        type_emoji = "➕" if transaction.type == "earn" else "➖"
        type_text = "Начисление" if transaction.type == "earn" else "Списание"

        # Определяем источник транзакции
        source_names = {
            "achievement": "🏆 Достижение",
            "product": "🛒 Покупка предмета",
            "manual": "✍️ Ручная операция",
            "casino": "🎰 Казино",
        }
        source_name = source_names.get(transaction.source_type, "❓ Неизвестно")
        if transaction.source_type == "achievement" and transaction.source_id:
            achievement = await stp_repo.achievement.get_achievement(
                transaction.source_id
            )
            match achievement.period:
                case "d":
                    source_name = "🏆 Ежедневное достижение: " + achievement.name
                case "w":
                    source_name = "🏆 Еженедельное достижение: " + achievement.name
                case "m":
                    source_name = "🏆 Ежемесячное достижение: " + achievement.name

        # Формируем сообщение с подробной информацией
        message_text = f"""📊 <b>Детали транзакции</b>

<b>ФИО:</b> <a href="https://t.me/{member.username}">{member.fullname}</a>
<b>Должность:</b> {member.position or "Не указано"} {member.division or ""}

<b>📈 Операция</b>
{type_emoji} {type_text} <b>{transaction.amount}</b> баллов

<b>🔢 ID:</b> <code>{transaction.id}</code>

<b>📍 Источник</b>
{source_name}

<b>📅 Дата создания</b>
{transaction.created_at.strftime("%d.%m.%Y в %H:%M")}"""

        if transaction.comment:
            message_text += f"\n\n<b>💬 Комментарий</b>\n<blockquote expandable>{transaction.comment}</blockquote>"

        await callback.message.edit_text(
            message_text,
            reply_markup=head_member_transaction_detail_kb(
                member_id=member_id, history_page=history_page, page=page
            ),
        )

    except Exception as e:
        logger.error(f"Ошибка при получении деталей транзакции {transaction_id}: {e}")
        await callback.answer(
            "❌ Ошибка при получении деталей транзакции", show_alert=True
        )
