import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram_dialog import DialogManager, StartMode
from aiogram_dialog.api.exceptions import NoContextError

from infrastructure.database.models import Employee
from infrastructure.database.repo.STP.requests import MainRequestsRepo
from tgbot.handlers.group.whois import create_user_info_message
from tgbot.handlers.user.search.main import user_search_router
from tgbot.keyboards.user.main import auth_kb
from tgbot.misc.helpers import get_role
from tgbot.misc.states.user.main import UserSG

logger = logging.getLogger(__name__)

user_router = Router()
user_router.message.filter(F.chat.type == "private")
user_router.callback_query.filter(F.message.chat.type == "private")

# Включаем роутер поиска для пользователей
user_router.include_router(user_search_router)


@user_router.message(CommandStart())
async def user_start_cmd(
    message: Message, user: Employee, dialog_manager: DialogManager, **kwargs
):
    if not user:
        await message.answer(
            """👋 Привет

Я - бот-помощник СТП

Используй кнопку ниже для авторизации""",
            reply_markup=auth_kb(),
        )
        return

    try:
        await dialog_manager.done()
    except NoContextError:
        pass

    await dialog_manager.start(UserSG.menu, mode=StartMode.RESET_STACK)


@user_router.message(Command("whois"))
async def private_whois_command(
    message: Message, user: Employee, stp_repo: MainRequestsRepo
):
    """Команда /whois для приватных сообщений - работает с пересланными сообщениями и аргументами"""

    # Проверяем авторизацию пользователя
    if not user:
        await message.reply(
            "❌ Для использования команды /whois необходимо авторизоваться в боте"
        )
        return

    # Проверяем, есть ли пересланное сообщение или это ответ на пересланное сообщение
    forwarded_user_id = None
    forward_info = {}
    privacy_error = False

    # Проверяем пересланное сообщение в самой команде
    if message.forward_from:
        forwarded_user_id = message.forward_from.id
        forward_info = {
            "user_id": message.forward_from.id,
            "first_name": message.forward_from.first_name,
            "last_name": message.forward_from.last_name,
            "username": message.forward_from.username,
            "is_bot": message.forward_from.is_bot,
        }
    elif message.forward_sender_name:
        # Пользователь включил режим конфиденциальности - forward_from недоступен
        privacy_error = True
        forward_info = {
            "sender_name": message.forward_sender_name,
            "forward_date": message.forward_date,
        }
    elif message.forward_from_chat:
        # Сообщение переслано из чата/канала
        forward_info = {
            "from_chat": True,
            "chat_id": message.forward_from_chat.id,
            "chat_title": message.forward_from_chat.title,
            "chat_type": message.forward_from_chat.type,
        }
    # Проверяем ответ на пересланное сообщение
    elif message.reply_to_message:
        if message.reply_to_message.forward_from:
            forwarded_user_id = message.reply_to_message.forward_from.id
            forward_info = {
                "user_id": message.reply_to_message.forward_from.id,
                "first_name": message.reply_to_message.forward_from.first_name,
                "last_name": message.reply_to_message.forward_from.last_name,
                "username": message.reply_to_message.forward_from.username,
                "is_bot": message.reply_to_message.forward_from.is_bot,
            }
        elif message.reply_to_message.forward_sender_name:
            privacy_error = True
            forward_info = {
                "sender_name": message.reply_to_message.forward_sender_name,
                "forward_date": message.reply_to_message.forward_date,
            }
        elif message.reply_to_message.forward_from_chat:
            forward_info = {
                "from_chat": True,
                "chat_id": message.reply_to_message.forward_from_chat.id,
                "chat_title": message.reply_to_message.forward_from_chat.title,
                "chat_type": message.reply_to_message.forward_from_chat.type,
            }

    # Если есть информация о пересланном сообщении, но пользователь скрыл свой ID из-за настроек приватности
    if privacy_error:
        await message.reply(
            f"""<b>🔒 Информация недоступна</b>

Пользователь <b>{forward_info.get("sender_name", "Неизвестно")}</b> включил режим конфиденциальности в настройках Telegram.

<b>Из-за настроек приватности недоступно:</b>
• Telegram ID пользователя
• Username пользователя
• Поиск в базе сотрудников

<b>💡 Доступная информация:</b>
• Имя отправителя: <code>{forward_info.get("sender_name", "Скрыто")}</code>
• Дата пересылки: <code>{forward_info.get("forward_date", "Неизвестно")}</code>

<b>Что можно сделать:</b>
• Попросить пользователя отключить "Forwarding Privacy" в настройках Telegram
• Использовать поиск по имени: <code>/whois {forward_info.get("sender_name", "").split()[0] if forward_info.get("sender_name") else "имя"}</code>""",
        )
        return

    # Если переслано из чата/канала
    if forward_info.get("from_chat"):
        chat_type_name = {
            "channel": "канала",
            "supergroup": "супергруппы",
            "group": "группы",
        }.get(forward_info.get("chat_type"), "чата")

        await message.reply(
            f"""<b>📢 Сообщение из {chat_type_name}</b>

<b>Информация о источнике:</b>
• Название: <code>{forward_info.get("chat_title", "Неизвестно")}</code>
• ID чата: <code>{forward_info.get("chat_id")}</code>
• Тип: <code>{forward_info.get("chat_type")}</code>

<b>ℹ️ Примечание:</b>
Команда /whois работает только с пересланными сообщениями от пользователей, а не из чатов или каналов.""",
        )
        return

    if forwarded_user_id:
        try:
            # Ищем пользователя в базе данных
            target_user = await stp_repo.employee.get_user(user_id=forwarded_user_id)

            if not target_user:
                await message.reply(
                    f"""<b>❌ Пользователь не найден</b>

Пользователь с ID <code>{forwarded_user_id}</code> не найден в базе

<b>Возможные причины:</b>
• Пользователь не авторизован в боте
• Пользователь не является сотрудником СТП
• Пользователь был удален из базы

<b>💡 Подсказка:</b>
Для получения данных искомому пользователю необходимо авторизоваться в @stpsher_bot"""
                )
                return

            # Получаем информацию о руководителе, если указан
            user_head = None
            if target_user.head:
                user_head = await stp_repo.employee.get_user(fullname=target_user.head)

            # Формируем и отправляем ответ с информацией о пользователе
            user_info_message = create_user_info_message(target_user, user_head)

            await message.reply(user_info_message, parse_mode="HTML")

            # Логируем использование команды
            logger.info(
                f"[WHOIS PRIVATE] {user.fullname} ({message.from_user.id}) запросил информацию о {target_user.fullname} ({target_user.user_id}) через пересланное сообщение"
            )

        except Exception as e:
            logger.error(f"Ошибка при выполнении команды /whois в приватном чате: {e}")
            await message.reply(
                "❌ Произошла ошибка при получении информации о пользователе. Попробуйте позже."
            )
        return

    # Проверяем, есть ли аргументы для поиска
    command_parts = message.text.split(maxsplit=1)
    if len(command_parts) > 1:
        search_query = command_parts[1].strip()

        if len(search_query) < 1:
            await message.reply("❌ Поисковый запрос не может быть пустым")
            return

        try:
            # Попытка поиска по user_id (если запрос состоит только из цифр)
            if search_query.isdigit():
                user_id = int(search_query)
                target_user = await stp_repo.employee.get_user(user_id=user_id)

                if target_user:
                    # Получаем информацию о руководителе
                    user_head = None
                    if target_user.head:
                        user_head = await stp_repo.employee.get_user(
                            fullname=target_user.head
                        )

                    user_info_message = create_user_info_message(target_user, user_head)
                    await message.reply(user_info_message, parse_mode="HTML")

                    logger.info(
                        f"[WHOIS PRIVATE] {user.fullname} ({message.from_user.id}) нашел по user_id '{search_query}': {target_user.fullname}"
                    )
                    return

            # Попытка поиска по username (если начинается с @ или похоже на username)
            username_query = search_query
            if username_query.startswith("@"):
                username_query = username_query[1:]  # Убираем @

            # Проверяем, похоже ли на username (без пробелов, может содержать буквы, цифры, подчеркивания)
            if username_query and all(c.isalnum() or c == "_" for c in username_query):
                target_user = await stp_repo.employee.get_user(username=username_query)

                if target_user:
                    # Получаем информацию о руководителе
                    user_head = None
                    if target_user.head:
                        user_head = await stp_repo.employee.get_user(
                            fullname=target_user.head
                        )

                    user_info_message = create_user_info_message(target_user, user_head)
                    await message.reply(user_info_message, parse_mode="HTML")

                    logger.info(
                        f"[WHOIS PRIVATE] {user.fullname} ({message.from_user.id}) нашел по username '{search_query}': {target_user.fullname}"
                    )
                    return

            # Если не найден по user_id или username, ищем по ФИО
            if len(search_query) < 2:
                await message.reply(
                    "❌ Поисковый запрос по имени слишком короткий (минимум 2 символа)"
                )
                return

            # Поиск пользователей по частичному совпадению ФИО
            found_users = await stp_repo.employee.get_users_by_fio_parts(
                search_query, limit=10
            )

            if not found_users:
                await message.reply(
                    f"""<b>❌ Пользователь не найден</b>

По запросу "<code>{search_query}</code>" ничего не найдено.

<b>💡 Попробуй:</b>
• Поиск по ID: <code>/whois 123456789</code>
• Поиск по username: <code>/whois @roman_domru</code> или <code>/whois roman_domru</code>
• Поиск по имени: <code>/whois Иванов</code> или <code>/whois Петр Иванов</code>
• Использовать inline-поиск: <code>@stpsher_bot {search_query}</code>"""
                )
                return

            # Если найден только один пользователь, показываем полную информацию
            if len(found_users) == 1:
                target_user = found_users[0]

                # Получаем информацию о руководителе
                user_head = None
                if target_user.head:
                    user_head = await stp_repo.employee.get_user(
                        fullname=target_user.head
                    )

                user_info_message = create_user_info_message(target_user, user_head)
                await message.reply(user_info_message, parse_mode="HTML")

                # Логируем использование команды
                logger.info(
                    f"[WHOIS PRIVATE] {user.fullname} ({message.from_user.id}) нашел по запросу '{search_query}': {target_user.fullname}"
                )
                return

            # Если найдено несколько пользователей, показываем список
            sorted_users = sorted(
                found_users,
                key=lambda u: (
                    search_query.lower() not in u.fullname.lower(),
                    u.fullname,
                ),
            )

            # Формируем список найденных пользователей
            user_list = []
            for idx, found_user in enumerate(sorted_users, 1):
                role_info = get_role(found_user.role)
                user_entry = f"{idx}. <b>{role_info['emoji']} {found_user.fullname}</b>"

                if found_user.position and found_user.division:
                    user_entry += f"\n   💼 {found_user.position} {found_user.division}"

                if found_user.username:
                    user_entry += f"\n   📱 @{found_user.username}"

                user_list.append(user_entry)

            users_text = "\n\n".join(user_list)

            await message.reply(
                f"""<b>🔍 Найдено пользователей: {len(sorted_users)}</b>

По запросу "<code>{search_query}</code>":

{users_text}

<b>💡 Для получения подробной информации:</b>
• По ID: <code>/whois 123456789</code>
• По username: <code>/whois @username</code>
• По имени: <code>/whois Полное Имя</code>
• Inline-поиск: <code>@stpsher_bot {search_query}</code>
• Пересланное сообщение + <code>/whois</code>""",
            )

            # Логируем использование команды
            logger.info(
                f"[WHOIS PRIVATE] {user.fullname} ({message.from_user.id}) нашел {len(sorted_users)} пользователей по запросу '{search_query}'"
            )

        except Exception as e:
            logger.error(
                f"Ошибка при поиске пользователей для команды /whois в приватном чате: {e}"
            )
            await message.reply(
                "❌ Произошла ошибка при поиске пользователей. Попробуйте позже."
            )
        return

    # Если нет ни пересланного сообщения, ни аргументов - показываем инструкцию
    await message.reply(
        """<b>ℹ️ Использование команды /whois в приватном чате</b>

<b>Способы поиска:</b>

<b>1. По пересланному сообщению:</b>
• Перешлите мне сообщение от пользователя
• Ответьте на пересланное сообщение командой <code>/whois</code>

<b>2. По Telegram ID:</b>
• <code>/whois 123456789</code>

<b>3. По username:</b>
• <code>/whois @roman_domru</code>
• <code>/whois roman_domru</code>

<b>4. По имени/фамилии:</b>
• <code>/whois Иванов</code>
• <code>/whois Петр</code>
• <code>/whois Иванов Петр</code>

<b>💡 Альтернатива:</b>
Используйте inline-поиск: <code>@stpsher_bot имя</code>""",
    )


@user_router.message(F.forward_from)
async def handle_forwarded_message(
    message: Message, user: Employee, stp_repo: MainRequestsRepo
):
    """Автоматически показывает информацию о пользователе при пересылке его сообщения"""

    # Проверяем авторизацию пользователя
    if not user:
        await message.reply(
            "❌ Для просмотра информации о пользователе необходимо авторизоваться в боте"
        )
        return

    forwarded_user_id = message.forward_from.id

    try:
        # Ищем пользователя в базе данных
        target_user = await stp_repo.employee.get_user(user_id=forwarded_user_id)

        if not target_user:
            await message.reply(
                f"""<b>❌ Пользователь не найден</b>

Пользователь с ID <code>{forwarded_user_id}</code> не найден в базе

<b>Возможные причины:</b>
• Пользователь не авторизован в боте
• Пользователь не является сотрудником СТП
• Пользователь был удален из базы

<b>💡 Подсказка:</b>
Для получения данных искомому пользователю необходимо авторизоваться в @stpsher_bot""",
            )
            return

        # Получаем информацию о руководителе, если указан
        user_head = None
        if target_user.head:
            user_head = await stp_repo.employee.get_user(fullname=target_user.head)

        # Формируем и отправляем ответ с информацией о пользователе
        user_info_message = create_user_info_message(target_user, user_head)

        await message.reply(user_info_message, parse_mode="HTML")

        # Логируем использование функции
        logger.info(
            f"[FORWARDED MESSAGE] {user.fullname} ({message.from_user.id}) получил информацию о {target_user.fullname} ({target_user.user_id}) через пересланное сообщение"
        )

    except Exception as e:
        logger.error(f"Ошибка при обработке пересланного сообщения: {e}")
        await message.reply(
            "❌ Произошла ошибка при получении информации о пользователе. Попробуйте позже."
        )


@user_router.message(F.forward_sender_name)
async def handle_forwarded_message_privacy(message: Message, user: Employee):
    """Обрабатывает пересланные сообщения с включенным режимом конфиденциальности"""

    # Проверяем авторизацию пользователя
    if not user:
        await message.reply(
            "❌ Для просмотра информации о пользователе необходимо авторизоваться в боте"
        )
        return

    await message.reply(
        f"""<b>🔒 Информация недоступна</b>

Пользователь <b>{message.forward_sender_name}</b> включил режим конфиденциальности в настройках Telegram.

<b>Из-за настроек приватности недоступно:</b>
• Telegram ID пользователя
• Username пользователя
• Поиск в базе сотрудников

<b>💡 Доступная информация:</b>
• Имя отправителя: <code>{message.forward_sender_name}</code>
• Дата пересылки: <code>{message.forward_date}</code>

<b>Что можно сделать:</b>
• Попросить пользователя отключить "Forwarding Privacy" в настройках Telegram
• Использовать поиск по имени: <code>/whois {message.forward_sender_name.split()[0] if message.forward_sender_name else "имя"}</code>

<b>💡 Подсказка:</b>
Попробуйте найти пользователя по имени с помощью команды /whois""",
    )

    # Логируем обращение
    logger.info(
        f"[FORWARDED MESSAGE PRIVACY] {user.fullname} ({message.from_user.id}) получил сообщение с конфиденциальностью от {message.forward_sender_name}"
    )


@user_router.message(F.forward_from_chat)
async def handle_forwarded_message_from_chat(message: Message, user: Employee):
    """Обрабатывает сообщения, пересланные из чатов/каналов"""

    # Проверяем авторизацию пользователя
    if not user:
        await message.reply(
            "❌ Для просмотра информации о пользователе необходимо авторизоваться в боте"
        )
        return

    chat_type_name = {
        "channel": "канала",
        "supergroup": "супергруппы",
        "group": "группы",
    }.get(message.forward_from_chat.type, "чата")

    await message.reply(
        f"""<b>📢 Сообщение из {chat_type_name}</b>

<b>Информация о источнике:</b>
• Название: <code>{message.forward_from_chat.title}</code>
• ID чата: <code>{message.forward_from_chat.id}</code>
• Тип: <code>{message.forward_from_chat.type}</code>

<b>ℹ️ Примечание:</b>
Команда /whois работает только с пересланными сообщениями от пользователей, а не из чатов или каналов.

<b>💡 Для поиска пользователей используйте:</b>
• <code>/whois имя_пользователя</code>
• <code>/whois @username</code>
• <code>/whois 123456789</code> (Telegram ID)""",
    )

    # Логируем обращение
    logger.info(
        f"[FORWARDED FROM CHAT] {user.fullname} ({message.from_user.id}) получил сообщение из чата {message.forward_from_chat.title} ({message.forward_from_chat.id})"
    )
