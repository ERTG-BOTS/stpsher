# tgbot/handlers/mip/search.py
import logging
from typing import Sequence

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from infrastructure.database.models import User
from infrastructure.database.repo.STP.requests import MainRequestsRepo
from tgbot.filters.role import MipFilter
from tgbot.keyboards.mip.search import (
    EditUserMenu,
    HeadGroupMenu,
    MipScheduleNavigation,
    SearchMenu,
    SearchUserResult,
    ViewUserSchedule,
    edit_user_back_kb,
    get_month_name_by_index,
    head_group_kb,
    search_back_kb,
    search_main_kb,
    search_results_kb,
    user_detail_kb,
    user_schedule_with_month_kb,
)
from tgbot.keyboards.user.main import MainMenu
from tgbot.misc.states.mip.search import EditEmployee, SearchEmployee
from tgbot.services.leveling import LevelingSystem
from tgbot.handlers.user.schedule.main import schedule_service

mip_search_router = Router()
mip_search_router.message.filter(F.chat.type == "private", MipFilter())
mip_search_router.callback_query.filter(F.message.chat.type == "private", MipFilter())

logger = logging.getLogger(__name__)

# Константы для пагинации
USERS_PER_PAGE = 10


def filter_users_by_type(users: Sequence[User], search_type: str) -> list[User]:
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
    """Получить статистику пользователя (уровень, очки, достижения, награды)"""
    try:
        # Получаем базовые данные
        user_achievements = await stp_repo.user_achievement.get_user_achievements(
            user_id
        )
        user_awards = await stp_repo.user_award.get_user_awards(user_id)
        achievements_sum = await stp_repo.user_achievement.get_user_achievements_sum(
            user_id
        )
        awards_sum = await stp_repo.user_award.get_user_awards_sum(user_id)

        # Получаем самые частые
        most_frequent_achievement = (
            await stp_repo.user_achievement.get_most_frequent_achievement(user_id)
        )
        most_used_award = await stp_repo.user_award.get_most_used_award(user_id)

        # Рассчитываем уровень
        current_level = LevelingSystem.calculate_level(achievements_sum)
        user_balance = achievements_sum - awards_sum

        return {
            "level": current_level,
            "balance": user_balance,
            "total_earned": achievements_sum,
            "total_spent": awards_sum,
            "achievements_count": len(user_achievements),
            "awards_count": len(user_awards),
            "most_frequent_achievement": most_frequent_achievement,
            "most_used_award": most_used_award,
        }
    except Exception as e:
        logger.error(f"Ошибка получения статистики пользователя {user_id}: {e}")
        return {
            "level": 0,
            "balance": 0,
            "total_earned": 0,
            "total_spent": 0,
            "achievements_count": 0,
            "awards_count": 0,
            "most_frequent_achievement": None,
            "most_used_award": None,
        }


async def get_group_statistics(head_name: str, stp_repo: MainRequestsRepo) -> dict:
    """Получить общую статистику группы руководителя"""
    try:
        # Получаем сотрудников группы
        group_users = await stp_repo.user.get_users_by_head(head_name)

        total_points = 0
        group_achievements = {}
        group_awards = {}

        for user in group_users:
            if user.user_id:  # Только авторизованные пользователи
                # Суммируем очки
                achievements_sum = (
                    await stp_repo.user_achievement.get_user_achievements_sum(
                        user.user_id
                    )
                )
                total_points += achievements_sum

                # Собираем статистику достижений
                most_frequent_achievement = (
                    await stp_repo.user_achievement.get_most_frequent_achievement(
                        user.user_id
                    )
                )
                if most_frequent_achievement:
                    achievement_name = most_frequent_achievement[0]
                    achievement_count = most_frequent_achievement[1]
                    group_achievements[achievement_name] = (
                        group_achievements.get(achievement_name, 0) + achievement_count
                    )

                # Собираем статистику наград
                most_used_award = await stp_repo.user_award.get_most_used_award(
                    user.user_id
                )
                if most_used_award:
                    award_name = most_used_award[0]
                    award_count = most_used_award[1]
                    group_awards[award_name] = (
                        group_awards.get(award_name, 0) + award_count
                    )

        # Находим самые популярные
        most_popular_achievement = (
            max(group_achievements.items(), key=lambda x: x[1])
            if group_achievements
            else None
        )
        most_popular_award = (
            max(group_awards.items(), key=lambda x: x[1]) if group_awards else None
        )

        return {
            "total_users": len(group_users),
            "total_points": total_points,
            "most_popular_achievement": most_popular_achievement,
            "most_popular_award": most_popular_award,
        }
    except Exception as e:
        logger.error(f"Ошибка получения статистики группы {head_name}: {e}")
        return {
            "total_users": 0,
            "total_points": 0,
            "most_popular_achievement": None,
            "most_popular_award": None,
        }


async def get_group_statistics_by_id(
    head_user_id: int, stp_repo: MainRequestsRepo
) -> dict:
    """Получить общую статистику группы руководителя по его ID"""
    try:
        # Получаем руководителя по ID
        head_user = await stp_repo.user.get_user(user_id=head_user_id)
        if not head_user:
            return {
                "total_users": 0,
                "total_points": 0,
                "most_popular_achievement": None,
                "most_popular_award": None,
            }

        # Используем существующую функцию
        return await get_group_statistics(head_user.fullname, stp_repo)
    except Exception as e:
        logger.error(f"Ошибка получения статистики группы по ID {head_user_id}: {e}")
        return {
            "total_users": 0,
            "total_points": 0,
            "most_popular_achievement": None,
            "most_popular_award": None,
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
    all_users = await stp_repo.user.get_users()
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
    all_users = await stp_repo.user.get_users()
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
        f"""<b>👔 Руководители</b>

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
        found_users = await stp_repo.user.get_users_by_fio_parts(search_query, limit=50)

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
        user = await stp_repo.user.get_user(user_id=user_id)
        user_head = await stp_repo.user.get_user(fullname=user.head)

        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        # Определение роли
        role_names = {
            0: "Не авторизован",
            1: "Специалист",
            2: "Руководитель",
            3: "Дежурный",
            5: "ГОК",
            6: "МИП",
            10: "Администратор",
        }
        role_name = role_names.get(user.role, f"Неизвестная роль ({user.role})")

        # Получаем статистику пользователя
        stats = await get_user_statistics(user_id, stp_repo)

        # Формирование информации о пользователе
        user_info = f"""<b>👤 Информация о сотруднике</b>

<b>ФИО:</b> <a href='t.me/{user.username}'>{user.fullname}</a>
<b>Должность:</b> {user.position} {user.division}
<b>Руководитель:</b> <a href='t.me/{user_head.username}'>{user.head}</a>
<b>Роль:</b> {role_name} ({user.role})"""

        if user.email:
            user_info += f"\n<b>Рабочая почта:</b> {user.email}"

        # Добавляем статистику уровня (только для специалистов и дежурных)
        if user.user_id and user.role in [1, 3]:
            # Форматируем достижения и награды
            achievement_text = "Нет достижений"
            if stats["most_frequent_achievement"]:
                achievement_text = f"{stats['most_frequent_achievement'][0]} ({stats['most_frequent_achievement'][1]}x)"

            award_text = "Нет наград"
            if stats["most_used_award"]:
                award_text = (
                    f"{stats['most_used_award'][0]} ({stats['most_used_award'][1]}x)"
                )

            user_info += f"""

<b>📊 Статистика игрока</b>
<b>⚔️ Уровень:</b> {stats["level"]}
<b>✨ Баланс:</b> {stats["balance"]} баллов
<b>📈 Всего заработано:</b> {stats["total_earned"]} баллов
<b>💸 Всего потрачено:</b> {stats["total_spent"]} баллов

<b>🎯 Достижения ({stats["achievements_count"]}):</b>
<b>Самое частое:</b> {achievement_text}

<b>🏅 Награды ({stats["awards_count"]}):</b>
<b>Самая частая:</b> {award_text}"""

        # Дополнительная информация для руководителей
        if user.role == 2:  # Руководитель
            group_stats = await get_group_statistics(user.fullname, stp_repo)

            group_achievement_text = "Нет данных"
            if group_stats["most_popular_achievement"]:
                group_achievement_text = f"{group_stats['most_popular_achievement'][0]} ({group_stats['most_popular_achievement'][1]}x)"

            group_award_text = "Нет данных"
            if group_stats["most_popular_award"]:
                group_award_text = f"{group_stats['most_popular_award'][0]} ({group_stats['most_popular_award'][1]}x)"

            user_info += f"""

<b>👥 Статистика группы</b>
<b>Сотрудников в группе:</b> {group_stats["total_users"]}
<b>Общие очки группы:</b> {group_stats["total_points"]} баллов
<b>Популярное достижение:</b> {group_achievement_text}
<b>Популярная награда:</b> {group_award_text}

<i>💡 Нажми кнопку ниже чтобы увидеть список группы</i>"""

        # Определяем возможность редактирования и параметры клавиатуры
        can_edit = user.role in [1, 2]  # Специалисты и руководители
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
    """Показать группу руководителя (список его сотрудников)"""
    head_name = callback_data.head_name
    page = callback_data.page

    try:
        # Получаем сотрудников группы
        group_users = await stp_repo.user.get_users_by_head(head_name)

        if not group_users:
            await callback.answer("❌ Сотрудники не найдены", show_alert=True)
            return

        # Сортируем по ФИО
        sorted_users = sorted(group_users, key=lambda u: u.fullname)

        # Пагинация
        total_users = len(sorted_users)
        total_pages = (total_users + USERS_PER_PAGE - 1) // USERS_PER_PAGE

        start_idx = (page - 1) * USERS_PER_PAGE
        end_idx = start_idx + USERS_PER_PAGE
        page_users = sorted_users[start_idx:end_idx]

        # Получаем статистику группы
        group_stats = await get_group_statistics(head_name, stp_repo)

        group_achievement_text = "Нет данных"
        if group_stats["most_popular_achievement"]:
            group_achievement_text = f"{group_stats['most_popular_achievement'][0]} ({group_stats['most_popular_achievement'][1]}x)"

        group_award_text = "Нет данных"
        if group_stats["most_popular_award"]:
            group_award_text = f"{group_stats['most_popular_award'][0]} ({group_stats['most_popular_award'][1]}x)"

        await callback.message.edit_text(
            f"""<b>👥 Группа: {head_name}</b>

<b>Сотрудников:</b> {total_users}
<b>Общие очки:</b> {group_stats["total_points"]} баллов
<b>Популярное достижение:</b> {group_achievement_text}
<b>Популярная награда:</b> {group_award_text}

<b>Страница {page} из {total_pages}</b>""",
            reply_markup=head_group_kb(page_users, head_name, page, total_pages),
        )

    except Exception as e:
        logger.error(f"Ошибка при получении группы руководителя {head_name}: {e}")
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
        user = await stp_repo.user.get_user(user_id=user_id)
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
        await stp_repo.user.update_user(user_id=user_id, fullname=new_fullname)

        await message.bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=bot_message_id,
            text=f"""<b>✅ ФИО изменено</b>

<b>Было:</b> {current_fullname}
<b>Стало:</b> {new_fullname}

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
        user = await stp_repo.user.get_user(user_id=user_id)
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        # Определяем месяц для отображения
        if requested_month_idx > 0:
            current_month = get_month_name_by_index(requested_month_idx)
        else:
            current_month = schedule_service.get_current_month()

        try:
            # Получаем расписание пользователя (компактный формат)
            schedule_response = await schedule_service.get_user_schedule_response(
                user=user, month=current_month, compact=True
            )

            await callback.message.edit_text(
                f"""<b>📅 График сотрудника</b>

<b>ФИО:</b> <a href='t.me/{user.username}'>{user.fullname}</a>
<b>Подразделение:</b> {user.division}

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
            error_message = "❌ Расписание для данного сотрудника не найдено"
            if "не найден" in str(schedule_error).lower():
                error_message = f"❌ Сотрудник {user.fullname} не найден в расписании"
            elif "файл" in str(schedule_error).lower():
                error_message = "❌ Файл расписания недоступен"

            await callback.message.edit_text(
                f"""<b>📅 График сотрудника</b>

<b>ФИО:</b> <a href='t.me/{user.username}'>{user.fullname}</a>
<b>Подразделение:</b> {user.division}

{error_message}

<i>Возможно, сотрудник не включен в текущее расписание или файл недоступен.</i>""",
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
        user = await stp_repo.user.get_user(user_id=user_id)
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        # Определяем компактность вывода
        compact = action not in ["detailed"]

        # Преобразуем индекс месяца в название
        month_to_display = get_month_name_by_index(month_idx)

        try:
            # Получаем расписание пользователя
            schedule_response = await schedule_service.get_user_schedule_response(
                user=user, month=month_to_display, compact=compact
            )

            await callback.message.edit_text(
                f"""<b>📅 График сотрудника</b>

<b>ФИО:</b> <a href='t.me/{user.username}'>{user.fullname}</a>
<b>Подразделение:</b> {user.division}

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
            error_message = "❌ Расписание для данного сотрудника не найдено"
            if "не найден" in str(schedule_error).lower():
                error_message = f"❌ Сотрудник {user.fullname} не найден в расписании"
            elif "файл" in str(schedule_error).lower():
                error_message = "❌ Файл расписания недоступен"

            await callback.message.edit_text(
                f"""<b>📅 График сотрудника</b>

<b>ФИО:</b> <a href='t.me/{user.username}'>{user.fullname}</a>
<b>Подразделение:</b> {user.division}

{error_message}

<i>Возможно, сотрудник не включен в текущее расписание или файл недоступен.</i>""",
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
