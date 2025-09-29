from infrastructure.database.models import Employee
from infrastructure.database.repo.STP.requests import MainRequestsRepo
from tgbot.dialogs.getters.common.db_getters import db_getter
from tgbot.services.leveling import LevelingSystem


async def game_getter(**kwargs):
    base_data = await db_getter(**kwargs)
    stp_repo: MainRequestsRepo = base_data.get("stp_repo")
    user: Employee = base_data.get("user")

    user_balance = await stp_repo.transaction.get_user_balance(user_id=user.user_id)
    achievements_sum = await stp_repo.transaction.get_user_achievements_sum(
        user_id=user.user_id
    )
    purchases_sum = await stp_repo.purchase.get_user_purchases_sum(user_id=user.user_id)
    level_info = LevelingSystem.get_level_info_text(achievements_sum, user_balance)

    return {
        **base_data,
        "achievements_sum": achievements_sum,
        "purchases_sum": purchases_sum,
        "level_info": level_info,
    }
