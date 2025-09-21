import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from infrastructure.database.models import Employee
from infrastructure.database.repo.STP.requests import MainRequestsRepo
from tgbot.keyboards.mip.game.purchases import purchase_notify_kb
from tgbot.keyboards.user.game.inventory import (
    CancelActivationMenu,
    InventoryHistoryMenu,
    ProductDetailMenu,
    SellProductMenu,
    UseProductMenu,
    inventory_kb,
    product_detail_kb,
    to_game_kb,
)
from tgbot.keyboards.user.game.main import GameMenu
from tgbot.keyboards.user.game.shop import ProductDetailsShop
from tgbot.misc.dicts import roles
from tgbot.services.broadcaster import broadcast
from tgbot.services.mailing import (
    send_activation_product_email,
    send_cancel_product_email,
)
from tgbot.services.schedule import DutyScheduleParser


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


user_game_inventory_router = Router()
user_game_inventory_router.message.filter(
    F.chat.type == "private",
)
user_game_inventory_router.callback_query.filter(F.message.chat.type == "private")

logger = logging.getLogger(__name__)


@user_game_inventory_router.callback_query(GameMenu.filter(F.menu == "inventory"))
async def game_inventory(callback: CallbackQuery, stp_repo: MainRequestsRepo):
    """Показывает инвентарь"""
    user_products_with_details = (
        await stp_repo.purchase.get_user_purchases_with_details(
            user_id=callback.from_user.id
        )
    )

    if not user_products_with_details:
        await callback.message.edit_text(
            """🎒 <b>Инвентарь</b>

Здесь ты найдешь все приобретенные предметы, а так же их статус и многое другое

У тебя пока нет купленных предметов 🙂

<i>Купить предметы можно в <b>💎 Магазине</b></i>""",
            reply_markup=to_game_kb(),
        )
        return

    # Показываем первую страницу по умолчанию
    total_products = len(user_products_with_details)
    message_text = f"""🎒 <b>Инвентарь</b>

Здесь ты найдешь все свои покупки, а так же их статус и многое другое

<i>Всего предметов приобретено: {total_products}</i>"""

    await callback.message.edit_text(
        message_text,
        reply_markup=inventory_kb(user_products_with_details, current_page=1),
    )


@user_game_inventory_router.callback_query(
    InventoryHistoryMenu.filter(F.menu == "inventory")
)
async def game_inventory_paginated(
    callback: CallbackQuery,
    callback_data: InventoryHistoryMenu,
    stp_repo: MainRequestsRepo,
):
    """Обработчик пагинации истории предметов"""
    page = callback_data.page

    user_products_with_details = (
        await stp_repo.purchase.get_user_purchases_with_details(
            user_id=callback.from_user.id
        )
    )

    if not user_products_with_details:
        await callback.message.edit_text(
            """🎒 <b>Инвентарь</b>

Здесь ты найдешь все приобретенные предметы, а так же их статус и многое другое

У тебя пока нет купленных предметов 🙂

<i>Купить предметы можно в <b>💎 Магазине</b></i>""",
            reply_markup=to_game_kb(),
        )
        return

    total_products = len(user_products_with_details)
    message_text = f"""🎒 <b>Инвентарь</b>

Здесь ты найдешь все приобретенные предметы, а так же их статус и многое другое

<i>Всего предметов приобретено: {total_products}</i>"""

    await callback.message.edit_text(
        message_text,
        reply_markup=inventory_kb(user_products_with_details, current_page=page),
    )


@user_game_inventory_router.callback_query(ProductDetailMenu.filter())
async def product_detail_view(
    callback: CallbackQuery,
    callback_data: ProductDetailMenu,
    stp_repo: MainRequestsRepo,
):
    """Обработчик детального просмотра предметов пользователя"""
    user_product_id = callback_data.user_product_id

    # Получаем информацию о предмете
    user_product_detail = await stp_repo.purchase.get_purchase_details(user_product_id)

    if not user_product_detail:
        await callback.message.edit_text(
            """<b>🎒 Инвентарь</b>

Не смог найти описание для предмета ☹""",
            reply_markup=to_game_kb(),
        )
        return

    user_product = user_product_detail.user_purchase
    product_info = user_product_detail.product_info

    status_names = {
        "stored": "Готов к использованию",
        "review": "На проверке",
        "used_up": "Полностью использован",
        "canceled": "Отменен",
        "rejected": "Отклонен",
    }
    status_name = status_names.get(user_product.status, "Неизвестный статус")

    # Проверяем возможные действия с купленным предметом
    can_use = (
        user_product.status == "stored"
        and user_product_detail.current_usages < user_product_detail.max_usages
    )

    # Можно продать только если статус "stored" И usage_count равен 0 (не использовался)
    can_sell = user_product.status == "stored" and user_product.usage_count == 0

    # Можно отменить активацию если статус "review" (на проверке)
    can_cancel = user_product.status == "review"

    # Формируем сообщение с подробной информацией
    message_text = f"""
<b>🛒 Предмет:</b> {product_info.name}

<b>📊 Статус</b>  
{status_name}

<b>📍 Активаций</b>
{user_product.usage_count} из {product_info.count}

<b>💵 Стоимость</b>  
{product_info.cost} баллов

<b>📝 Описание</b>  
{product_info.description}

<blockquote expandable><b>📅 Дата покупки</b>  
{user_product.bought_at.strftime("%d.%m.%Y в %H:%M")}</blockquote>"""

    if user_product.comment:
        message_text += f"\n\n<b>💬 Комментарий</b>\n└ {user_product.comment}"

    if user_product.updated_by_user_id:
        manager = await stp_repo.employee.get_user(
            user_id=user_product.updated_by_user_id
        )
        if manager.username:
            message_text += (
                f"\n\n<blockquote expandable><b>👤 Последний проверяющий</b>\n<a href='t.me/{manager.username}'>"
                f"{manager.fullname}</a>"
            )
        else:
            message_text += (
                f"\n\n<blockquote expandable><b>👤 Последний проверяющий</b>\n<a href='tg://user?id={manager.user_id}'>"
                f"{manager.fullname}</a>"
            )
        message_text += f"\n\n<b>📅 Дата проверки</b>\n{user_product.updated_at.strftime('%d.%m.%Y в %H:%M')}</blockquote>"

    # Updated keyboard logic - default to inventory context when accessed from inventory
    keyboard = product_detail_kb(
        user_product.id,
        can_use=can_use,
        can_sell=can_sell,
        can_cancel=can_cancel,
        source_menu="inventory",
    )

    await callback.message.edit_text(message_text, reply_markup=keyboard)


@user_game_inventory_router.callback_query(ProductDetailsShop.filter())
async def product_detail_view_from_shop(
    callback: CallbackQuery,
    callback_data: ProductDetailsShop,
    stp_repo: MainRequestsRepo,
):
    """Обработчик детального просмотра купленного предмета пользователя из контекста магазина"""
    user_product_id = callback_data.user_product_id

    # Получаем информацию о предмете
    user_product_detail = await stp_repo.purchase.get_purchase_details(user_product_id)

    if not user_product_detail:
        await callback.message.edit_text(
            """<b>🎒 Инвентарь</b>

Не смог найти описание для предмета ☹""",
            reply_markup=to_game_kb(),
        )
        return

    user_product = user_product_detail.user_purchase
    product_info = user_product_detail.product_info

    status_names = {
        "stored": "Готов к использованию",
        "review": "На проверке",
        "used_up": "Полностью использован",
        "canceled": "Отменен",
        "rejected": "Отклонен",
    }
    status_name = status_names.get(user_product.status, "Неизвестный статус")

    # Проверяем возможные действия с купленным предметом из контекста магазина
    can_use = (
        user_product.status == "stored"
        and user_product_detail.current_usages < user_product_detail.max_usages
    )

    # Можно продать только если статус "stored" И usage_count равен 0 (не использовался)
    can_sell = user_product.status == "stored" and user_product.usage_count == 0

    # Можно отменить активацию если статус "review" (на проверке)
    can_cancel = user_product.status == "review"

    # Формируем сообщение с подробной информацией
    message_text = f"""
<b>🛒 Предмет:</b> {product_info.name}

<b>📊 Статус</b>  
{status_name}

<b>📍 Активаций</b>
{user_product.usage_count} из {product_info.count}

<b>💵 Стоимость</b>  
{product_info.cost} баллов

<b>📝 Описание</b>  
{product_info.description}

<blockquote expandable><b>📅 Дата покупки</b>  
{user_product.bought_at.strftime("%d.%m.%Y в %H:%M")}</blockquote>"""

    if user_product.comment:
        message_text += f"\n\n<b>💬 Комментарий</b>\n└ {user_product.comment}"

    if user_product.updated_by_user_id:
        manager = await stp_repo.employee.get_user(
            user_id=user_product.updated_by_user_id
        )
        if manager.username:
            message_text += (
                f"\n\n<blockquote expandable><b>👤 Последний проверяющий</b>\n<a href='t.me/{manager.username}'>"
                f"{manager.fullname}</a>"
            )
        else:
            message_text += (
                f"\n\n<blockquote expandable><b>👤 Последний проверяющий</b>\n<a href='tg://user?id={manager.user_id}'>"
                f"{manager.fullname}</a>"
            )
        message_text += f"\n\n<b>📅 Дата проверки</b>\n{user_product.updated_at.strftime('%d.%m.%Y в %H:%M')}</blockquote>"

    # Updated keyboard logic - set shop context since this came from shop
    keyboard = product_detail_kb(
        user_product.id,
        can_use=can_use,
        can_sell=can_sell,
        can_cancel=can_cancel,
        source_menu="shop",
    )

    await callback.message.edit_text(message_text, reply_markup=keyboard)


@user_game_inventory_router.callback_query(UseProductMenu.filter())
async def use_product_handler(
    callback: CallbackQuery,
    callback_data: UseProductMenu,
    user: Employee,
    stp_repo: MainRequestsRepo,
):
    """
    Хендлер нажатия на "Использовать предмет" в открытой информации о приобретенном предмете
    :param callback:
    :param callback_data:
    :param user:
    :param stp_repo:
    :return:
    """
    user_product_id = callback_data.user_product_id

    # Получаем информацию о предмете
    user_product_detail = await stp_repo.purchase.get_purchase_details(user_product_id)
    if not user_product_detail:
        await callback.answer("❌ Предмет не найден", show_alert=True)
        return

    success = await stp_repo.purchase.use_purchase(user_product_id)

    # Refresh the product detail view
    await product_detail_view(
        callback, ProductDetailMenu(user_product_id=user_product_id), stp_repo
    )

    if success:
        product_name = user_product_detail.product_info.name
        role_lookup = {v: k for k, v in roles.items()}
        confirmer = role_lookup.get(
            user_product_detail.product_info.manager_role, "Неизвестно"
        )

        await callback.answer(
            f"✅ Предмет {product_name} отправлен на рассмотрение!\n\n"
            f"🔔 На проверке у: {confirmer}",
            show_alert=True,
        )

        if user_product_detail.product_info.manager_role == 3:
            product_managers = await stp_repo.employee.get_users_by_role(
                role=user_product_detail.product_info.manager_role,
                division=user_product_detail.product_info.division,
            )
        else:
            product_managers = await stp_repo.employee.get_users_by_role(
                role=user_product_detail.product_info.manager_role
            )

        manager_ids = [
            manager.user_id
            for manager in product_managers
            if manager.user_id
            and manager.user_id != user_product_detail.user_purchase.user_id
        ]

        if manager_ids:
            notification_text = f"""<b>🔔 Новый предмет на активацию</b>

<b>🛒 Предмет:</b> {product_name}
<b>👤 Заявитель:</b> <a href='t.me/{user.username}'>{user.fullname}</a>
<b>📋 Описание:</b> {user_product_detail.product_info.description}

<b>Требуется рассмотрение заявки</b>"""

            user_head: Employee | None = await stp_repo.employee.get_user(
                fullname=user.head
            )

            duty_scheduler = DutyScheduleParser()
            current_duty = await duty_scheduler.get_current_senior_duty(
                division=user_head.division, stp_repo=stp_repo
            )
            current_duty_user = await stp_repo.employee.get_user(
                user_id=current_duty.user_id
            )
            await send_activation_product_email(
                user,
                user_head,
                current_duty_user,
                user_product_detail.product_info,
                user_product_detail.user_purchase,
            )

            result = await broadcast(
                bot=callback.bot,
                users=manager_ids,
                text=notification_text,
                reply_markup=purchase_notify_kb(),
            )

            logger.info(
                f"[Использование предмета] {user.username} ({user.user_id}) отправил на рассмотрение '{product_name}'. Уведомлено менеджеров: {result} из {len([m for m in product_managers if m.user_id])}"
            )
    else:
        await callback.answer("❌ Невозможно использовать предмет", show_alert=True)


@user_game_inventory_router.callback_query(SellProductMenu.filter())
async def sell_product_handler(
    callback: CallbackQuery,
    callback_data: SellProductMenu,
    user: Employee,
    stp_repo: MainRequestsRepo,
):
    """
    Хендлер продажи предмета - удаляет запись из БД и возвращает баллы
    """
    user_product_id = callback_data.user_product_id
    source_menu = callback_data.source_menu

    # Получаем информацию о предмете
    user_product_detail = await stp_repo.purchase.get_purchase_details(user_product_id)
    if not user_product_detail:
        await callback.answer("❌ Предмет не найден", show_alert=True)
        return

    user_product = user_product_detail.user_purchase
    product_info = user_product_detail.product_info

    # Проверяем, что предмет можно продать (статус "stored" и usage_count = 0)
    if user_product.status != "stored" or user_product.usage_count > 0:
        await callback.answer(
            "❌ Нельзя продать уже использованный предмет", show_alert=True
        )
        return

    try:
        success = await stp_repo.purchase.delete_user_purchase(user_product_id)
        await stp_repo.transaction.add_transaction(
            user_id=user_product.user_id,
            transaction_type="earn",
            source_type="product",
            source_id=product_info.id,
            amount=product_info.cost,
            comment=f"Возврат предмета: {product_info.name}",
        )

        if success:
            await callback.answer(
                f"✅ Продано: {product_info.name}.\nВозвращено: {product_info.cost} баллов"
            )

            logger.info(
                f"[Продажа предмета] {user.username} ({user.user_id}) продал  '{product_info.name}' за {product_info.cost} баллов"
            )

            # Context-aware navigation
            if source_menu == "shop":
                # Return to shop if user came from purchase flow
                from tgbot.handlers.user.game.shop import game_shop
                from tgbot.keyboards.user.game.shop import ShopMenu

                await game_shop(
                    callback=callback,
                    user=user,
                    callback_data=ShopMenu(menu="available", page=1),
                    stp_repo=stp_repo,
                )
            else:
                # Return to inventory if user came from inventory menu
                await game_inventory(
                    callback=callback,
                    stp_repo=stp_repo,
                )
        else:
            await callback.answer("❌ Ошибка при продаже предмета", show_alert=True)

    except Exception as e:
        logger.error(f"Error selling product: {e}")
        await callback.answer("❌ Ошибка при продаже предмета", show_alert=True)


@user_game_inventory_router.callback_query(CancelActivationMenu.filter())
async def cancel_activation_handler(
    callback: CallbackQuery,
    callback_data: CancelActivationMenu,
    user: Employee,
    stp_repo: MainRequestsRepo,
):
    """
    Хендлер отмены активации предмета - меняет статус с "review" обратно на "stored"
    """
    user_product_id = callback_data.user_product_id

    # Получаем информацию о предмете
    user_product_detail = await stp_repo.purchase.get_purchase_details(user_product_id)
    if not user_product_detail:
        await callback.answer("❌ Предмет не найден", show_alert=True)
        return

    user_product = user_product_detail.user_purchase
    product_info = user_product_detail.product_info

    # Проверяем, что купленный предмет на рассмотрении
    if user_product.status != "review":
        await callback.answer(
            "❌ Нельзя отменить активацию этого предмета", show_alert=True
        )
        return

    try:
        # Меняем статус обратно на "stored"
        success = await stp_repo.purchase.update_purchase(
            purchase_id=user_product_id, status="stored"
        )

        if success:
            await callback.answer(
                f"✅ Активация предмета '{product_info.name}' отменена!"
            )

            # Refresh the product detail view
            await product_detail_view(
                callback, ProductDetailMenu(user_product_id=user_product_id), stp_repo
            )

            user_head: Employee | None = await stp_repo.employee.get_user(
                fullname=user.head
            )
            duty_scheduler = DutyScheduleParser()
            current_duty = await duty_scheduler.get_current_senior_duty(
                division=user_head.division, stp_repo=stp_repo
            )
            current_duty_user = await stp_repo.employee.get_user(
                user_id=current_duty.user_id
            )
            await send_cancel_product_email(
                user, user_head, current_duty_user, product_info, user_product
            )

            logger.info(
                f"[Отмена активации] {user.username} ({user.user_id}) отменил активацию '{product_info.name}'"
            )
        else:
            await callback.answer("❌ Ошибка при отмене активации", show_alert=True)

    except Exception as e:
        logger.error(f"Error canceling activation: {e}")
        await callback.answer("❌ Ошибка при отмене активации", show_alert=True)
