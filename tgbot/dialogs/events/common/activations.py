from aiogram_dialog import DialogManager

from infrastructure.database.models import Employee
from infrastructure.database.repo.STP.requests import MainRequestsRepo


async def on_activation_click(
    callback, widget, dialog_manager: DialogManager, item_id, **kwargs
):
    """
    Обработчик нажатия на активацию - переход к детальному просмотру
    """

    stp_repo: MainRequestsRepo = dialog_manager.middleware_data["stp_repo"]

    try:
        # Получаем детальную информацию о покупке
        purchase_details = await stp_repo.purchase.get_purchase_details(item_id)

        if not purchase_details:
            await callback.answer("❌ Покупка не найдена", show_alert=True)
            return

        purchase = purchase_details.user_purchase
        product = purchase_details.product_info

        # Получаем информацию о пользователе
        purchase_user: Employee = await stp_repo.employee.get_user(
            user_id=purchase.user_id
        )
        purchase_user_head: Employee = (
            await stp_repo.employee.get_user(fullname=purchase_user.head)
            if purchase_user and purchase_user.head
            else None
        )

        user_info = (
            f"<a href='t.me/{purchase_user.username}'>{purchase_user.fullname}</a>"
            if purchase_user and purchase_user.username
            else purchase_user.fullname
            if purchase_user
            else f"ID: {purchase.user_id}"
        )

        head_info = (
            f"<a href='t.me/{purchase_user_head.username}'>{purchase_user.head}</a>"
            if purchase_user_head and purchase_user_head.username
            else purchase_user.head
            if purchase_user and purchase_user.head
            else "-"
        )

        # Сохраняем информацию о выбранной активации в dialog_data
        dialog_manager.dialog_data["selected_activation"] = {
            "purchase_id": purchase.id,
            "product_name": product.name,
            "product_description": product.description,
            "product_cost": product.cost,
            "product_count": product.count,
            "product_division": product.division,
            "bought_at": purchase.bought_at.strftime("%d.%m.%Y в %H:%M"),
            "usage_count": purchase.usage_count,
            "user_name": user_info,
            "fullname": purchase_user.fullname,
            "user_division": purchase_user.division if purchase_user else "Неизвестно",
            "user_position": purchase_user.position if purchase_user else "Неизвестно",
            "user_head": head_info,
            "user_username": purchase_user.username if purchase_user else None,
            "user_id": purchase_user.user_id if purchase_user else purchase.user_id,
        }

        # Переходим к окну детального просмотра активации
        # Определяем текущую группу состояний динамически
        current_state = dialog_manager.current_context().state
        state_group = current_state.group

        # Переходим к детальному просмотру в рамках текущей группы состояний
        await dialog_manager.switch_to(getattr(state_group, "game_activation_detail"))

    except Exception as e:
        print(f"Error in on_activation_click: {e}")
        await callback.answer(
            "❌ Ошибка получения информации об активации", show_alert=True
        )


async def on_approve_activation(
    callback, widget, dialog_manager: DialogManager, **kwargs
):
    """
    Обработчик подтверждения активации
    """
    stp_repo: MainRequestsRepo = dialog_manager.middleware_data["stp_repo"]
    user: Employee = dialog_manager.middleware_data["user"]
    activation_info = dialog_manager.dialog_data["selected_activation"]

    try:
        # Подтверждаем активацию
        await stp_repo.purchase.approve_purchase_usage(
            purchase_id=activation_info["purchase_id"],
            updated_by_user_id=callback.from_user.id,
        )

        await callback.answer(
            f"✅ Предмет '{activation_info['product_name']}' активирован!\n\nСпециалист {activation_info['fullname']} был уведомлен об изменении статуса",
            show_alert=True,
        )

        # Уведомляем пользователя
        if activation_info["usage_count"] >= activation_info["product_count"]:
            employee_notify_message = f"""<b>👌 Предмет активирован:</b> {activation_info["product_name"]}

Менеджер <a href='t.me/{user.username}'>{user.fullname}</a> подтвердил активацию предмета

У <b>{activation_info["product_name"]}</b> не осталось использований

<i>Купить его повторно можно в <b>💎 Магазине</b></i>"""
        else:
            remaining_uses = (
                activation_info["product_count"] - activation_info["usage_count"]
            )
            employee_notify_message = f"""<b>👌 Предмет активирован:</b> {activation_info["product_name"]}

Менеджер <a href='t.me/{user.username}'>{user.fullname}</a> подтвердил активацию предмета

📍 Осталось активаций: {remaining_uses} из {activation_info["product_count"]}"""

        await callback.bot.send_message(
            chat_id=activation_info["user_id"],
            text=employee_notify_message,
        )

        # Возвращаемся к списку активаций
        # Определяем текущую группу состояний динамически
        current_state = dialog_manager.current_context().state
        state_group = current_state.group

        await dialog_manager.switch_to(getattr(state_group, "game_products_activation"))

    except Exception as e:
        print(f"Error in on_approve_activation: {e}")
        await callback.answer("❌ Ошибка при подтверждении активации", show_alert=True)


async def on_reject_activation(
    callback, widget, dialog_manager: DialogManager, **kwargs
):
    """
    Обработчик отклонения активации
    """
    stp_repo: MainRequestsRepo = dialog_manager.middleware_data["stp_repo"]
    user: Employee = dialog_manager.middleware_data["user"]
    activation_info = dialog_manager.dialog_data["selected_activation"]

    try:
        # Отклоняем активацию
        await stp_repo.purchase.reject_purchase_usage(
            purchase_id=activation_info["purchase_id"],
            updated_by_user_id=callback.from_user.id,
        )

        await callback.answer(
            f"❌ Активация предмета '{activation_info['product_name']}' отклонена\n\nСпециалист {activation_info['fullname']} был уведомлен об изменении статуса",
            show_alert=True,
        )

        # Уведомляем пользователя
        employee_notify_message = f"""<b>Активация отменена:</b> {activation_info["product_name"]}

Менеджер <a href='t.me/{user.username}'>{user.fullname}</a> отменил активацию <b>{activation_info["product_name"]}</b>

<i>Использование предмета не будет засчитано</i>"""

        await callback.bot.send_message(
            chat_id=activation_info["user_id"],
            text=employee_notify_message,
        )

        # Возвращаемся к списку активаций
        # Определяем текущую группу состояний динамически
        current_state = dialog_manager.current_context().state
        state_group = current_state.group

        await dialog_manager.switch_to(getattr(state_group, "game_products_activation"))

    except Exception as e:
        print(f"Error in on_reject_activation: {e}")
        await callback.answer("❌ Ошибка при отклонении активации", show_alert=True)
