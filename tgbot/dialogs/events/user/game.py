from aiogram_dialog import DialogManager

from infrastructure.database.repo.STP.requests import MainRequestsRepo
from tgbot.misc.states.user.main import UserSG


async def on_product_click(
    callback, widget, dialog_manager: DialogManager, item_id, **kwargs
):
    """
    Обработчик нажатия на продукт - переход к подтверждению покупки
    """
    stp_repo: MainRequestsRepo = dialog_manager.middleware_data["stp_repo"]
    user = dialog_manager.middleware_data["user"]

    try:
        product_info = await stp_repo.product.get_product(item_id)
    except Exception as e:
        print(e)
        await callback.answer(
            "❌ Ошибка получения информации о предмете", show_alert=True
        )
        return

    # Получаем баланс пользователя
    user_balance = await stp_repo.transaction.get_user_balance(user.user_id)

    # Проверяем, достаточно ли баллов
    if user_balance < product_info.cost:
        await callback.answer(
            f"❌ Недостаточно баллов!\nУ тебя: {user_balance} баллов\nНужно: {product_info.cost} баллов",
            show_alert=True,
        )
        return

    # Сохраняем информацию о выбранном продукте в dialog_data
    dialog_manager.dialog_data["selected_product"] = {
        "id": product_info.id,
        "name": product_info.name,
        "description": product_info.description,
        "cost": product_info.cost,
        "count": product_info.count,
    }
    dialog_manager.dialog_data["user_balance"] = user_balance

    # Переходим к окну подтверждения
    await dialog_manager.switch_to(UserSG.game_shop_confirm)


async def on_filter_change(callback, widget, dialog_manager, item_id, **kwargs):
    """
    Обработчик нажатия на фильтр
    """
    if widget.widget_id == "shop_filter":
        dialog_manager.dialog_data["product_filter"] = item_id
    elif widget.widget_id == "inventory_filter":
        dialog_manager.dialog_data["purchases_filter"] = item_id
    elif widget.widget_id == "achievement_position_filter":
        dialog_manager.dialog_data["achievement_position_filter"] = item_id
    elif widget.widget_id == "achievement_period_filter":
        dialog_manager.dialog_data["achievement_period_filter"] = item_id
    elif widget.widget_id == "history_type_filter":
        dialog_manager.dialog_data["history_type_filter"] = item_id
    elif widget.widget_id == "history_source_filter":
        dialog_manager.dialog_data["history_source_filter"] = item_id
    await callback.answer()


async def on_confirm_purchase(
    callback, widget, dialog_manager: DialogManager, **kwargs
):
    """
    Обработчик подтверждения покупки
    """
    stp_repo: MainRequestsRepo = dialog_manager.middleware_data["stp_repo"]
    user = dialog_manager.middleware_data["user"]
    product_info = dialog_manager.dialog_data["selected_product"]

    # Получаем актуальный баланс пользователя
    user_balance = await stp_repo.transaction.get_user_balance(user.user_id)

    if user_balance < product_info["cost"]:
        await callback.answer(
            f"❌ Недостаточно баллов!\nУ тебя: {user_balance}, нужно: {product_info['cost']}",
            show_alert=True,
        )
        return

    try:
        # Создаем покупку со статусом "stored"
        new_purchase = await stp_repo.purchase.add_purchase(
            user_id=user.user_id, product_id=product_info["id"], status="stored"
        )
        await stp_repo.transaction.add_transaction(
            user_id=user.user_id,
            transaction_type="spend",
            source_type="product",
            source_id=product_info["id"],
            amount=product_info["cost"],
            comment=f"Автоматическая покупка предмета {product_info['name']}",
        )

        # Сохраняем информацию о покупке
        dialog_manager.dialog_data["new_purchase"] = {"id": new_purchase.id}
        dialog_manager.dialog_data["new_balance"] = user_balance - product_info["cost"]

        # Переходим к окну успешной покупки
        await dialog_manager.switch_to(UserSG.game_shop_success)

    except Exception:
        await callback.answer("❌ Ошибка при покупке предмета", show_alert=True)


async def on_sell_product(callback, widget, dialog_manager: DialogManager, **kwargs):
    """
    Обработчик продажи предмета
    """
    stp_repo: MainRequestsRepo = dialog_manager.middleware_data["stp_repo"]
    user = dialog_manager.middleware_data["user"]
    new_purchase = dialog_manager.dialog_data["new_purchase"]
    product_info = dialog_manager.dialog_data["selected_product"]

    try:
        success = await stp_repo.purchase.delete_user_purchase(new_purchase["id"])
        await stp_repo.transaction.add_transaction(
            user_id=user.user_id,
            transaction_type="earn",
            source_type="product",
            source_id=product_info["id"],
            amount=product_info["cost"],
            comment=f"Возврат предмета: {product_info['name']}",
        )

        if success:
            await callback.answer(
                f"✅ Продано: {product_info['name']}.\nВозвращено: {product_info['cost']} баллов"
            )
            # Возвращаемся в магазин
            await dialog_manager.switch_to(UserSG.game_shop)
        else:
            await callback.answer("❌ Ошибка при продаже предмета", show_alert=True)

    except Exception:
        await callback.answer("❌ Ошибка при продаже предмета", show_alert=True)


async def on_inventory_product_click(
    callback, widget, dialog_manager: DialogManager, item_id, **kwargs
):
    """
    Обработчик нажатия на предмет в инвентаре - переход к детальному просмотру
    """
    stp_repo: MainRequestsRepo = dialog_manager.middleware_data["stp_repo"]

    try:
        user_product_detail = await stp_repo.purchase.get_purchase_details(item_id)
    except Exception as e:
        print(e)
        await callback.answer(
            "❌ Ошибка получения информации о предмете", show_alert=True
        )
        return

    if not user_product_detail:
        await callback.answer("❌ Предмет не найден", show_alert=True)
        return

    # Сохраняем информацию о выбранном предмете из инвентаря в dialog_data
    user_product = user_product_detail.user_purchase
    product_info = user_product_detail.product_info

    dialog_manager.dialog_data["selected_inventory_product"] = {
        "user_product_id": user_product.id,
        "product_name": product_info.name,
        "product_description": product_info.description,
        "product_cost": product_info.cost,
        "product_count": product_info.count,
        "status": user_product.status,
        "usage_count": user_product.usage_count,
        "current_usages": user_product_detail.current_usages,
        "max_usages": user_product_detail.max_usages,
        "bought_at": user_product.bought_at.strftime("%d.%m.%Y в %H:%M"),
        "comment": user_product.comment,
        "updated_by_user_id": user_product.updated_by_user_id,
        "updated_at": user_product.updated_at.strftime("%d.%m.%Y в %H:%M")
        if user_product.updated_at
        else None,
    }

    # Переходим к окну детального просмотра предмета инвентаря
    await dialog_manager.switch_to(UserSG.game_inventory_detail)


async def use_product(callback, widget, dialog_manager: DialogManager, **kwargs):
    """
    Обработчик использования предмета из инвентаря или после покупки
    """
    stp_repo: MainRequestsRepo = dialog_manager.middleware_data["stp_repo"]

    # Проверяем, откуда вызвана функция - из success окна или из инвентаря
    if dialog_manager.current_context().state == UserSG.game_shop_success:
        # Используем данные только что купленного предмета
        new_purchase = dialog_manager.dialog_data["new_purchase"]
        product_info = dialog_manager.dialog_data["selected_product"]
        user_product_id = new_purchase["id"]
        product_name = product_info["name"]
    else:
        # Используем данные предмета из инвентаря
        product_info = dialog_manager.dialog_data["selected_inventory_product"]
        user_product_id = product_info["user_product_id"]
        product_name = product_info["product_name"]

    try:
        success = await stp_repo.purchase.use_purchase(user_product_id)

        if success:
            await callback.answer(
                f"✅ Предмет {product_name} отправлен на рассмотрение!",
                show_alert=True,
            )
            # Обновляем данные предмета и возвращаемся
            if dialog_manager.current_context().state == UserSG.game_shop_success:
                await dialog_manager.switch_to(UserSG.game_shop)
            else:
                await dialog_manager.switch_to(UserSG.game_inventory)
        else:
            await callback.answer("❌ Невозможно использовать предмет", show_alert=True)

    except Exception as e:
        print(f"Error using product: {e}")
        await callback.answer("❌ Ошибка при использовании предмета", show_alert=True)


async def on_inventory_sell_product(
    callback, widget, dialog_manager: DialogManager, **kwargs
):
    """
    Обработчик продажи предмета из инвентаря
    """
    stp_repo: MainRequestsRepo = dialog_manager.middleware_data["stp_repo"]
    user = dialog_manager.middleware_data["user"]
    product_info = dialog_manager.dialog_data["selected_inventory_product"]
    user_product_id = product_info["user_product_id"]

    try:
        success = await stp_repo.purchase.delete_user_purchase(user_product_id)
        await stp_repo.transaction.add_transaction(
            user_id=user.user_id,
            transaction_type="earn",
            source_type="product",
            source_id=user_product_id,  # Используем user_product_id как source_id
            amount=product_info["product_cost"],
            comment=f"Возврат предмета: {product_info['product_name']}",
        )

        if success:
            await callback.answer(
                f"✅ Продано: {product_info['product_name']}.\nВозвращено: {product_info['product_cost']} баллов"
            )
            # Возвращаемся к инвентарю
            await dialog_manager.switch_to(UserSG.game_inventory)
        else:
            await callback.answer("❌ Ошибка при продаже предмета", show_alert=True)

    except Exception as e:
        print(f"Error selling product: {e}")
        await callback.answer("❌ Ошибка при продаже предмета", show_alert=True)


async def on_inventory_cancel_activation(
    callback, widget, dialog_manager: DialogManager, **kwargs
):
    """
    Обработчик отмены активации предмета из инвентаря
    """
    stp_repo: MainRequestsRepo = dialog_manager.middleware_data["stp_repo"]
    product_info = dialog_manager.dialog_data["selected_inventory_product"]
    user_product_id = product_info["user_product_id"]

    try:
        # Меняем статус обратно на "stored"
        success = await stp_repo.purchase.update_purchase(
            purchase_id=user_product_id, status="stored"
        )

        if success:
            await callback.answer(
                f"✅ Активация предмета '{product_info['product_name']}' отменена!"
            )
            # Возвращаемся к инвентарю
            await dialog_manager.switch_to(UserSG.game_inventory)
        else:
            await callback.answer("❌ Ошибка при отмене активации", show_alert=True)

    except Exception as e:
        print(f"Error canceling activation: {e}")
        await callback.answer("❌ Ошибка при отмене активации", show_alert=True)


async def on_transaction_click(
    callback, widget, dialog_manager: DialogManager, item_id, **kwargs
):
    """
    Обработчик нажатия на транзакцию - переход к детальному просмотру
    """
    stp_repo: MainRequestsRepo = dialog_manager.middleware_data["stp_repo"]

    try:
        transaction = await stp_repo.transaction.get_transaction(item_id)
    except Exception as e:
        print(e)
        await callback.answer(
            "❌ Ошибка получения информации о транзакции", show_alert=True
        )
        return

    if not transaction:
        await callback.answer("❌ Транзакция не найдена", show_alert=True)
        return

    # Сохраняем информацию о выбранной транзакции в dialog_data
    dialog_manager.dialog_data["selected_transaction"] = {
        "id": transaction.id,
        "amount": transaction.amount,
        "type": transaction.type,
        "source_type": transaction.source_type,
        "source_id": transaction.source_id,
        "comment": transaction.comment or "",
        "created_at": transaction.created_at.strftime("%d.%m.%Y в %H:%M"),
    }

    # Переходим к окну детального просмотра транзакции
    await dialog_manager.switch_to(UserSG.game_history_detail)
