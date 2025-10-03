import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from infrastructure.database.models import Employee
from infrastructure.database.repo.STP.requests import MainRequestsRepo
from tgbot.filters.role import DutyFilter
from tgbot.keyboards.user.game.main import GameMenu
from tgbot.keyboards.user.game.products import (
    DutyPurchaseActionMenu,
    DutyPurchaseActivationMenu,
    duty_products_activation_kb,
    duty_purchases_detail_kb,
)

duty_game_products_router = Router()
duty_game_products_router.message.filter(F.chat.type == "private", DutyFilter())
duty_game_products_router.callback_query.filter(
    F.message.chat.type == "private", DutyFilter()
)

logger = logging.getLogger(__name__)


@duty_game_products_router.callback_query(
    GameMenu.filter(F.menu == "products_activation")
)
async def duty_products_activation(
    callback: CallbackQuery,
    callback_data: GameMenu,
    user: Employee,
    stp_repo: MainRequestsRepo,
):
    """
    Обработчик меню покупок для активации дежурными
    Показывает покупки со статусом "review" и manager_role == 3 (Дежурный)
    Дежурный видит только покупки из своего направления (НТП или НЦК)
    """

    # Достаём номер страницы из callback data, стандартно = 1
    page = getattr(callback_data, "page", 1)

    # Получаем покупки ожидающие активации с manager_role == 3 (Дежурный)
    review_purchases = await stp_repo.purchase.get_review_purchases_for_activation(
        manager_role=3
    )

    if not review_purchases:
        await callback.message.edit_text(
            """<b>✍️ Активация предметов</b>

Нет предметов, ожидающих активации 😊""",
            reply_markup=duty_products_activation_kb(page, 0, []),
        )
        return

    # Фильтруем покупки по направлению дежурного
    # Дежурный может видеть только покупки из своего направления
    division_filtered_purchases = []
    for purchase_details in review_purchases:
        product = purchase_details.product_info
        if product.division == user.division:
            division_filtered_purchases.append(purchase_details)

    if not division_filtered_purchases:
        await callback.message.edit_text(
            """<b>✍️ Активация предметов</b>

Нет предметов, ожидающих активации 😊""",
            reply_markup=duty_products_activation_kb(page, 0, []),
        )
        return

    # Логика пагинации
    purchases_per_page = 5
    total_purchases = len(division_filtered_purchases)
    total_pages = (total_purchases + purchases_per_page - 1) // purchases_per_page

    # Считаем начало и конец текущей страницы
    start_idx = (page - 1) * purchases_per_page
    end_idx = start_idx + purchases_per_page
    page_purchases = division_filtered_purchases[start_idx:end_idx]

    # Построение списка покупок для текущей страницы
    purchases_list = []
    for counter, purchase_details in enumerate(page_purchases, start=start_idx + 1):
        purchase = purchase_details.user_purchase
        product = purchase_details.product_info

        # Получаем информацию о пользователе
        purchase_user = await stp_repo.employee.get_user(user_id=purchase.user_id)
        user_name = (
            purchase_user.fullname if purchase_user else f"ID: {purchase.user_id}"
        )

        if purchase_user and purchase_user.username:
            purchases_list.append(f"""{counter}. <b>{product.name}</b> - {purchase.bought_at.strftime("%d.%m.%Y в %H:%M")}
<blockquote><b>👤 Специалист</b>
<a href='t.me/{purchase_user.username}'>{user_name}</a> из {product.division}

<b>📝 Описание</b>
{product.description}</blockquote>""")
        else:
            purchases_list.append(f"""{counter}. <b>{product.name}</b> - {purchase.bought_at.strftime("%d.%m.%Y в %H:%M")}
<blockquote><b>👤 Специалист</b>
<a href='tg://user?id={purchase_user.user_id if purchase_user else purchase.user_id}'>{user_name}</a> из {product.division}

<b>📝 Описание</b>
{product.description}</blockquote>""")
        purchases_list.append("")

    message_text = f"""<b>✍️ Активация предметов</b>

{chr(10).join(purchases_list)}"""

    await callback.message.edit_text(
        message_text,
        reply_markup=duty_products_activation_kb(page, total_pages, page_purchases),
    )

    logger.info(
        f"[Дежурный] - [Активация] {callback.from_user.username} ({callback.from_user.id}): Просмотр активации предметов, страница {page}, направление: {user.division}"
    )


@duty_game_products_router.callback_query(DutyPurchaseActivationMenu.filter())
async def duty_purchase_activation_detail(
    callback: CallbackQuery,
    callback_data: DutyPurchaseActivationMenu,
    stp_repo: MainRequestsRepo,
):
    """Показывает детальную информацию о покупке и предмете для активации"""
    purchase_id = callback_data.purchase_id
    current_page = callback_data.page

    # Получаем информацию о конкретной покупке
    purchase_details = await stp_repo.purchase.get_purchase_details(purchase_id)

    if not purchase_details:
        await callback.message.edit_text(
            """<b>✅ Активация</b>

Не смог найти описание для предмета ☹""",
            reply_markup=duty_purchases_detail_kb(purchase_id, current_page),
        )
        return

    purchase = purchase_details.user_purchase
    product = purchase_details.product_info

    # Получаем информацию о пользователе
    purchase_user: Employee = await stp_repo.employee.get_user(user_id=purchase.user_id)
    user_head: Employee = await stp_repo.employee.get_user(fullname=purchase_user.head)

    user_info = (
        f"<a href='t.me/{purchase_user.username}'>{purchase_user.fullname}</a>"
        if purchase_user and purchase_user.username
        else f"{purchase_user.fullname if purchase_user else f'ID: {purchase.user_id}'}"
    )
    head_info = (
        f"<a href='t.me/{user_head.username}'>{purchase_user.head}</a>"
        if user_head and user_head.username
        else purchase_user.head
        if purchase_user
        else "-"
    )

    message_text = f"""
<b>🎯 Активация предмета</b>

<b>🏆 О предмете</b>  
<blockquote><b>Название</b>
{product.name}

<b>📝 Описание</b>
{product.description}

<b>💵 Стоимость</b>
{product.cost} баллов

<b>🔰 Направление</b>
{product.division}

<b>📍 Активаций</b>
{purchase.usage_count} ➡️ {purchase.usage_count + 1} ({product.count} всего)</blockquote>"""

    message_text += f"""

<b>👤 О специалисте</b>
<blockquote><b>ФИО</b>
{user_info}

<b>Должность</b>
{purchase_user.position if purchase_user else "-"} {purchase_user.division if purchase_user else "-"}

<b>Руководитель</b>
{head_info}</blockquote>

<b>📅 Дата покупки</b>  
{purchase.bought_at.strftime("%d.%m.%Y в %H:%M")}
"""
    await callback.message.edit_text(
        message_text,
        reply_markup=duty_purchases_detail_kb(purchase_id, current_page),
    )


@duty_game_products_router.callback_query(DutyPurchaseActionMenu.filter())
async def duty_purchase_action(
    callback: CallbackQuery,
    callback_data: DutyPurchaseActionMenu,
    stp_repo: MainRequestsRepo,
    user: Employee,
):
    """Обработка подтверждения/отклонения активации дежурными"""
    purchase_id = callback_data.purchase_id
    action = callback_data.action

    try:
        # Получаем информацию о покупке
        purchase_details = await stp_repo.purchase.get_purchase_details(purchase_id)

        if not purchase_details:
            await callback.answer("❌ Покупка не найдена", show_alert=True)
            return

        purchase = purchase_details.user_purchase
        product = purchase_details.product_info
        employee_user: Employee = await stp_repo.employee.get_user(
            user_id=purchase.user_id
        )

        # Проверяем, что дежурный может активировать только предметы из своего направления
        if product.division != user.division:
            await callback.answer(
                f"❌ Ты можешь активировать только предметы из направления {user.division}",
                show_alert=True,
            )
            return

        if action == "approve":
            # Подтверждаем активацию покупки
            await stp_repo.purchase.approve_purchase_usage(
                purchase_id=purchase_id,
                updated_by_user_id=callback.from_user.id,
            )

            await callback.answer(
                f"""✅ Предмет '{product.name}' активирован!
                
Специалист {employee_user.fullname} был уведомлен об изменении статуса""",
                show_alert=True,
            )

            if purchase.usage_count >= product.count:
                employee_notify_message = f"""<b>👌 Предмет активирован:</b> {product.name}

Дежурный <a href='t.me/{user.username}'>{user.fullname}</a> подтвердил активацию предмета

У <b>{product.name}</b> не осталось использований 

<i>Купить его повторно можно в <b>💎 Магазине</b></i>"""
            else:
                employee_notify_message = f"""<b>👌 Предмет активирован:</b> {product.name}

Дежурный <a href='t.me/{user.username}'>{user.fullname}</a> подтвердил активацию предмета

📍 Осталось активаций: {product.count - purchase.usage_count} из {product.count}"""

            await callback.bot.send_message(
                chat_id=employee_user.user_id,
                text=employee_notify_message,
            )

            logger.info(
                f"[Дежурный] - [Подтверждение] {callback.from_user.username} ({callback.from_user.id}) подтвердил {product.name} для пользователя {employee_user.username} ({purchase.user_id})"
            )

        elif action == "reject":
            # Отклоняем активацию покупки
            await stp_repo.purchase.reject_purchase_usage(
                purchase_id=purchase_id, updated_by_user_id=callback.from_user.id
            )

            await callback.answer(
                f"""❌ Активация предмета '{product.name}' отклонена

Специалист {employee_user.fullname} был уведомлен об изменении статуса предмета""",
                show_alert=True,
            )

            await callback.bot.send_message(
                chat_id=employee_user.user_id,
                text=f"""<b>Активация отменена:</b> {product.name}

Дежурный <a href='t.me/{user.username}'>{user.fullname}</a> отменил активацию предмета""",
            )

            logger.info(
                f"[Дежурный] - [Отклонение] {callback.from_user.username} ({callback.from_user.id}) отклонил активацию {product.name} для пользователя {employee_user.username} ({purchase.user_id})"
            )

        # Возвращаемся к списку покупок для активации
        await duty_products_activation(
            callback=callback,
            callback_data=GameMenu(menu="products_activation"),
            user=user,
            stp_repo=stp_repo,
        )

    except Exception as e:
        logger.error(f"Error updating purchase status: {e}")
        await callback.answer("❌ Ошибка при обработке покупки", show_alert=True)
