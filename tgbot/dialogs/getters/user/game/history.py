from infrastructure.database.models import Employee
from infrastructure.database.repo.STP.requests import MainRequestsRepo


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
