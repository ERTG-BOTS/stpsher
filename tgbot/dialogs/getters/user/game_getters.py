from html import escape

from infrastructure.database.models import Employee
from infrastructure.database.repo.STP.requests import MainRequestsRepo


# Хелперы
def get_status_emoji(status: str) -> str:
    """Возвращает эмодзи в зависимости от статуса"""
    status_emojis = {
        "stored": "📦",
        "review": "⏳",
        "used_up": "🔒",
        "canceled": "🔥",
        "rejected": "⛔",
    }
    return status_emojis.get(status, "❓")


# Фильтры
async def product_filter_getter(**kwargs):
    """
    Фильтрует предметы в зависимости от выбранного радио-фильтра
    """
    base_data = await products_getter(**kwargs)
    dialog_manager = kwargs.get("dialog_manager")

    # Проверяем текущий выбор фильтра (стандартно на 'Доступные')
    filter_type = dialog_manager.dialog_data.get("product_filter", "available")

    # Устанавливаем стандартный фильтр если не установлено иное
    if "product_filter" not in dialog_manager.dialog_data:
        dialog_manager.dialog_data["product_filter"] = "available"

    products = base_data["products"]
    user_balance = base_data["user_balance"]

    if filter_type == "available":
        # Фильтруем предметы, доступные пользователю
        filtered_products = [
            p for p in products if p[4] <= user_balance
        ]  # p[4] это стоимость
    else:  # "Все предметы"
        filtered_products = products

    return {
        "products": filtered_products,
        "user_balance": user_balance,
        "product_filter": filter_type,
    }


async def inventory_filter_getter(**kwargs):
    """
    Фильтрует предметы в инвентаре в зависимости от выбранного радио-фильтра
    """
    base_data = await inventory_getter(**kwargs)
    dialog_manager = kwargs.get("dialog_manager")

    # Проверяем текущий выбор фильтра (стандартно на 'all')
    filter_type = dialog_manager.dialog_data.get("purchases_filter", "all")

    # Устанавливаем стандартный фильтр если не установлено иное
    if "purchases_filter" not in dialog_manager.dialog_data:
        dialog_manager.dialog_data["purchases_filter"] = "all"

    products = base_data["products"]
    total_bought = base_data["total_bought"]

    if filter_type != "all":
        # Фильтруем предметы по статусу
        filtered_products = [
            p
            for p in products
            if p[5] == filter_type  # p[5] это status
        ]
    else:
        filtered_products = products

    return {
        "products": filtered_products,
        "total_bought": total_bought,
        "inventory_filter": filter_type,
    }


def get_position_display_name(position: str) -> str | None:
    """Возвращает отображаемое имя для позиции"""
    match position:
        case "Специалист":
            return "Спец"
        case "Специалист первой линии":
            return "Спец"
        case "Специалист второй линии":
            return "Спец"
        case "Ведущий специалист":
            return "Ведущий"
        case "Ведущий специалист первой линии":
            return "Ведущий"
        case "Ведущий специалист второй линии":
            return "Ведущий"
        case "Эксперт":
            return "Эксперт"
        case "Эксперт второй линии":
            return "Эксперт"
        case _:
            return position


def get_position_callback_key(position: str) -> str:
    """Возвращает ключ для callback без русских символов"""
    match position:
        case "Специалист":
            return "spec"
        case "Специалист первой линии":
            return "spec_ntp1"
        case "Специалист второй линии":
            return "spec_ntp2"
        case "Ведущий специалист":
            return "lead_spec"
        case "Ведущий специалист первой линии":
            return "lead_spec_ntp1"
        case "Ведущий специалист второй линии":
            return "lead_spec_ntp2"
        case "Эксперт":
            return "expert"
        case "Эксперт второй линии":
            return "expert_ntp2"
        case _:
            return position.lower().replace(" ", "_")


def get_position_from_callback(callback_key: str) -> str:
    """Возвращает оригинальную позицию по ключу callback"""
    match callback_key:
        case "spec":
            return "Специалист"
        case "spec_ntp1":
            return "Специалист первой линии"
        case "spec_ntp2":
            return "Специалист второй линии"
        case "lead_spec":
            return "Ведущий специалист"
        case "lead_spec_ntp1":
            return "Ведущий специалист первой линии"
        case "lead_spec_ntp2":
            return "Ведущий специалист второй линии"
        case "expert":
            return "Эксперт"
        case "expert_ntp2":
            return "Эксперт второй линии"
        case _:
            return callback_key


async def achievements_filter_getter(**kwargs):
    """
    Фильтрует достижения в зависимости от выбранной позиции и периода
    """
    base_data = await user_achievements_getter(**kwargs)
    dialog_manager = kwargs.get("dialog_manager")

    # Получаем все достижения для определения доступных позиций
    all_achievements = base_data["achievements"]

    # Получаем информацию о пользователе для фильтрации
    user = kwargs.get("user")

    # Фильтруем достижения по подразделению пользователя
    if user:
        if "НТП1" in user.division:
            # Показываем только достижения для первой линии
            allowed_positions = [
                "Специалист первой линии",
                "Ведущий специалист первой линии",
            ]
            achievements = [
                ach
                for ach in all_achievements
                if ach[4] in allowed_positions  # ach[4] это position
            ]
        elif "НТП2" in user.division:
            # Показываем только достижения для второй линии
            allowed_positions = [
                "Специалист второй линии",
                "Ведущий специалист второй линии",
                "Эксперт второй линии",
            ]
            achievements = [
                ach
                for ach in all_achievements
                if ach[4] in allowed_positions  # ach[4] это position
            ]
        else:
            # Для остальных подразделений показываем все достижения
            achievements = all_achievements
    else:
        achievements = all_achievements

    # Извлекаем уникальные позиции из отфильтрованных достижений
    positions = set()
    for achievement in achievements:
        positions.add(achievement[4])  # achievement[4] это position

    # Создаем данные для радио-кнопок позиций с callback-безопасными ключами
    position_radio_data = []
    for pos in list(positions):
        callback_key = get_position_callback_key(pos)
        display_name = get_position_display_name(pos)
        position_radio_data.append((callback_key, display_name))

    # Добавляем опцию "Все" в начало
    position_radio_data.insert(0, ("all", "Все"))

    # Создаем данные для радио-кнопок периодов
    period_radio_data = [
        ("all", "Все"),
        ("d", "День"),
        ("w", "Неделя"),
        ("m", "Месяц"),
    ]

    # Проверяем текущий выбор фильтра позиции (стандартно на 'all')
    selected_position = dialog_manager.dialog_data.get(
        "achievement_position_filter", "all"
    )

    # Проверяем текущий выбор фильтра периода (стандартно на 'all')
    selected_period = dialog_manager.dialog_data.get("achievement_period_filter", "all")

    # Устанавливаем стандартные фильтры если не установлено иное
    if "achievement_position_filter" not in dialog_manager.dialog_data:
        dialog_manager.dialog_data["achievement_position_filter"] = "all"
        selected_position = "all"

    if "achievement_period_filter" not in dialog_manager.dialog_data:
        dialog_manager.dialog_data["achievement_period_filter"] = "all"
        selected_period = "all"

    # Фильтруем достижения по выбранной позиции
    if selected_position == "all":
        filtered_achievements = achievements
    else:
        # Конвертируем callback key обратно в оригинальную позицию для фильтрации
        actual_position = get_position_from_callback(selected_position)
        filtered_achievements = [
            a
            for a in achievements
            if a[4] == actual_position  # a[4] это position
        ]

    # Дополнительно фильтруем по периоду
    if selected_period != "all":
        # Нужно получить оригинальные данные для фильтрации по периоду
        # achievement[5] содержит отформатированный период, но нам нужен оригинальный
        stp_repo = kwargs.get("stp_repo")
        user = kwargs.get("user")

        if stp_repo and user:
            # Нормализуем division как в user_achievements_getter
            normalized_division = "НЦК" if "НЦК" in user.division else "НТП"
            original_data = await stp_repo.achievement.get_achievements(
                division=normalized_division
            )
            # Создаем словарь для быстрого поиска периода по ID
            period_map = {ach.id: ach.period for ach in original_data}

            # Фильтруем по периоду
            filtered_achievements = [
                a
                for a in filtered_achievements
                if period_map.get(a[0]) == selected_period  # a[0] это ID достижения
            ]

    return {
        "achievements": filtered_achievements,
        "position_radio_data": position_radio_data,
        "period_radio_data": period_radio_data,
        "achievement_position_filter": selected_position,
        "achievement_period_filter": selected_period,
        "checked": selected_position,  # Explicit checked state for Position Radio
        "checked_period": selected_period,  # Explicit checked state for Period Radio
    }


async def products_getter(**kwargs):
    """
    Получение списка предметов для магазина
    """
    stp_repo: MainRequestsRepo = kwargs.get("stp_repo")
    user: Employee = kwargs.get("user")

    user_balance: int = await stp_repo.transaction.get_user_balance(
        user_id=user.user_id
    )
    products = await stp_repo.product.get_products(division=user.division)

    formatted_products = []
    for product in products:
        formatted_products.append(
            (product.id, product.name, product.description, product.count, product.cost)
        )

    return {
        "products": formatted_products,
        "user_balance": user_balance,
    }


async def confirmation_getter(**kwargs):
    """
    Геттер для окна подтверждения покупки
    """
    dialog_manager = kwargs.get("dialog_manager")
    product_info = dialog_manager.dialog_data.get("selected_product")
    user_balance = dialog_manager.dialog_data.get("user_balance", 0)

    if not product_info:
        return {}

    balance_after_purchase = user_balance - product_info["cost"]

    return {
        "product_name": product_info["name"],
        "product_description": product_info["description"],
        "product_count": product_info["count"],
        "product_cost": product_info["cost"],
        "user_balance": user_balance,
        "balance_after_purchase": balance_after_purchase,
    }


async def success_getter(**kwargs):
    """
    Геттер для окна успешной покупки
    """
    dialog_manager = kwargs.get("dialog_manager")
    product_info = dialog_manager.dialog_data.get("selected_product")
    user_balance = dialog_manager.dialog_data.get("user_balance", 0)
    new_balance = dialog_manager.dialog_data.get("new_balance", 0)

    if not product_info:
        return {}

    return {
        "product_name": product_info["name"],
        "product_description": product_info["description"],
        "product_count": product_info["count"],
        "product_cost": product_info["cost"],
        "user_balance": user_balance,
        "new_balance": new_balance,
    }


async def achievements_getter(**kwargs):
    stp_repo: MainRequestsRepo = kwargs.get("stp_repo")

    if "division" in kwargs:
        achievements_list = await stp_repo.achievement.get_achievements(
            division=kwargs["division"]
        )
    else:
        achievements_list = await stp_repo.achievement.get_achievements()

    formatted_achievements = []
    for achievement in achievements_list:
        period = "Неизвестно"  # Default value
        match achievement.period:
            case "d":
                period = "Раз в день"
            case "w":
                period = "Раз в неделю"
            case "m":
                period = "Раз в месяц"
            case "A":
                period = "Вручную"
            case _:
                period = "Неизвестно"

        formatted_achievements.append(
            (
                achievement.id,
                escape(achievement.name),
                achievement.reward,
                escape(achievement.description),
                achievement.position,
                period,
            )
        )

    return {
        "achievements": formatted_achievements,
    }


async def user_achievements_getter(**kwargs):
    """
    Получение достижений для конкретного подразделения пользователя
    """
    user: Employee = kwargs.get("user")

    # Передаем division пользователя в базовый getter
    return await achievements_getter(
        division="НЦК" if "НЦК" in user.division else "НТП", **kwargs
    )


async def inventory_getter(**kwargs):
    """
    Получение предметов из инвентаря пользователя
    """
    stp_repo: MainRequestsRepo = kwargs.get("stp_repo")
    user: Employee = kwargs.get("user")

    user_products = await stp_repo.purchase.get_user_purchases_with_details(
        user_id=user.user_id
    )

    total_bought: int = len(user_products)

    formatted_products = []
    for product in user_products:
        user_product = product.user_purchase
        product_info = product.product_info

        date_str = user_product.bought_at.strftime("%d.%m.%y")
        status_emoji = get_status_emoji(user_product.status)
        usage_info = f"({product.current_usages}/{product.max_usages})"
        button_text = f"{status_emoji} {usage_info} {product_info.name} ({date_str})"

        formatted_products.append(
            (
                user_product.id,  # ID для обработчика клика
                button_text,  # Текст кнопки с эмодзи и статусом
                product_info.name,
                product_info.description,
                product_info.cost,
                user_product.status,
                product.current_usages,
                product.max_usages,
            )
        )

    return {
        "total_bought": total_bought,
        "products": formatted_products,
    }


async def inventory_detail_getter(**kwargs):
    """
    Геттер для окна детального просмотра предмета инвентаря
    """
    dialog_manager = kwargs.get("dialog_manager")
    product_info = dialog_manager.dialog_data.get("selected_inventory_product")

    if not product_info:
        return {}

    status_names = {
        "stored": "Готов к использованию",
        "review": "На проверке",
        "used_up": "Полностью использован",
        "canceled": "Отменен",
        "rejected": "Отклонен",
    }
    status_name = status_names.get(product_info["status"], "Неизвестный статус")

    # Проверяем возможные действия с купленным предметом
    can_use = (
        product_info["status"] == "stored"
        and product_info["current_usages"] < product_info["max_usages"]
    )

    # Можно продать только если статус "stored" И usage_count равен 0 (не использовался)
    can_sell = product_info["status"] == "stored" and product_info["usage_count"] == 0

    # Можно отменить активацию если статус "review" (на проверке)
    can_cancel = product_info["status"] == "review"

    # Формируем дополнительные тексты
    comment_text = ""
    if product_info.get("comment"):
        comment_text = f"\n\n<b>💬 Комментарий</b>\n└ {product_info['comment']}"

    updated_by_text = ""
    if product_info.get("updated_by_user_id") and product_info.get("updated_at"):
        updated_by_text = f"\n\n<blockquote expandable><b>👤 Последняя проверка</b>\n<b>📅 Дата проверки:</b> {product_info['updated_at']}</blockquote>"

    return {
        "product_name": product_info["product_name"],
        "product_description": product_info["product_description"],
        "product_cost": product_info["product_cost"],
        "product_count": product_info["product_count"],
        "status_name": status_name,
        "usage_count": product_info["usage_count"],
        "bought_at": product_info["bought_at"],
        "comment_text": comment_text,
        "updated_by_text": updated_by_text,
        "can_use": can_use,
        "can_sell": can_sell,
        "can_cancel": can_cancel,
    }


async def history_filter_getter(**kwargs):
    """
    Фильтрует транзакции в зависимости от выбранных радио-фильтров (тип и источник)
    """
    base_data = await history_getter(**kwargs)
    dialog_manager = kwargs.get("dialog_manager")

    # Проверяем текущий выбор фильтров (стандартно на 'all')
    type_filter = dialog_manager.dialog_data.get("history_type_filter", "all")
    source_filter = dialog_manager.dialog_data.get("history_source_filter", "all")

    # Устанавливаем стандартные фильтры если не установлено иное
    if "history_type_filter" not in dialog_manager.dialog_data:
        dialog_manager.dialog_data["history_type_filter"] = "all"
    if "history_source_filter" not in dialog_manager.dialog_data:
        dialog_manager.dialog_data["history_source_filter"] = "all"

    transactions = base_data["history_products"]
    total_transactions = base_data["total_transactions"]

    # Применяем фильтр по типу транзакции
    if type_filter == "earn":
        filtered_transactions = [
            t
            for t in transactions
            if t[6] == "earn"  # t[6] это type
        ]
    elif type_filter == "spend":
        filtered_transactions = [
            t
            for t in transactions
            if t[6] == "spend"  # t[6] это type
        ]
    else:  # "all"
        filtered_transactions = transactions

    # Применяем фильтр по источнику транзакции
    if source_filter != "all":
        filtered_transactions = [
            t
            for t in filtered_transactions
            if t[7] == source_filter  # t[7] это source_type
        ]

    return {
        "history_products": filtered_transactions,
        "total_transactions": total_transactions,
        "filtered_count": len(filtered_transactions),
        "history_type_filter": type_filter,
        "history_source_filter": source_filter,
    }


async def history_getter(**kwargs):
    """
    Получение истории транзакций пользователя
    """
    stp_repo: MainRequestsRepo = kwargs.get("stp_repo")
    user: Employee = kwargs.get("user")

    user_transactions = await stp_repo.transaction.get_user_transactions(
        user_id=user.user_id
    )

    total_transactions = len(user_transactions)

    formatted_transactions = []
    for transaction in user_transactions:
        # Определяем эмодзи и текст типа операции
        type_emoji = "➕" if transaction.type == "earn" else "➖"
        type_text = "Начисление" if transaction.type == "earn" else "Списание"

        # Определяем источник транзакции
        source_names = {
            "achievement": "🏆",
            "product": "🛒",
            "manual": "✍️",
            "casino": "🎰",
        }
        source_icon = source_names.get(transaction.source_type, "❓")

        date_str = transaction.created_at.strftime("%d.%m.%y")
        button_text = f"{type_emoji} {transaction.amount} {source_icon} ({date_str})"

        formatted_transactions.append(
            (
                transaction.id,  # ID для обработчика клика
                button_text,  # Текст кнопки
                transaction.amount,  # Сумма
                type_text,  # Тип операции (текст)
                source_icon,  # Иконка источника
                date_str,  # Дата
                transaction.type,  # Тип операции (earn/spend)
                transaction.source_type,  # Тип источника
                transaction.comment or "",  # Комментарий
                transaction.created_at.strftime("%d.%m.%Y в %H:%M"),  # Полная дата
            )
        )

    return {
        "history_products": formatted_transactions,
        "total_transactions": total_transactions,
    }


async def history_detail_getter(**kwargs):
    """
    Геттер для окна детального просмотра транзакции
    """
    dialog_manager = kwargs.get("dialog_manager")
    stp_repo: MainRequestsRepo = kwargs.get("stp_repo")
    transaction_info = dialog_manager.dialog_data.get("selected_transaction")

    if not transaction_info:
        return {}

    # Определяем эмодзи и текст типа операции
    type_emoji = "➕" if transaction_info["type"] == "earn" else "➖"
    type_text = "Начисление" if transaction_info["type"] == "earn" else "Списание"

    # Определяем источник транзакции
    source_names = {
        "achievement": "🏆 Достижение",
        "product": "🛒 Покупка предмета",
        "manual": "✍️ Ручная операция",
        "casino": "🎰 Казино",
    }
    source_name = source_names.get(transaction_info["source_type"], "❓ Неизвестно")

    # Дополнительная информация для достижений
    if (
        transaction_info["source_type"] == "achievement"
        and transaction_info["source_id"]
    ):
        try:
            achievement = await stp_repo.achievement.get_achievement(
                transaction_info["source_id"]
            )
            if achievement:
                match achievement.period:
                    case "d":
                        source_name = "🏆 Ежедневное достижение: " + achievement.name
                    case "w":
                        source_name = "🏆 Еженедельное достижение: " + achievement.name
                    case "m":
                        source_name = "🏆 Ежемесячное достижение: " + achievement.name
        except Exception:
            # Если не удалось получить информацию о достижении, оставляем базовое название
            pass

    return {
        "transaction_id": transaction_info["id"],
        "type_emoji": type_emoji,
        "type_text": type_text,
        "amount": transaction_info["amount"],
        "source_name": source_name,
        "created_at": transaction_info["created_at"],
        "comment": transaction_info["comment"],
    }
