"""Import all routers and add them to routers_list."""

from tgbot.handlers.admin.main import admin_router
from tgbot.handlers.admin.schedule.list import admin_list_router
from tgbot.handlers.admin.schedule.main import admin_schedule_router
from tgbot.handlers.admin.schedule.upload import admin_upload_router
from tgbot.handlers.deep.group.settings import deeplink_group
from tgbot.handlers.gok.game.achievements import gok_game_achievements_router
from tgbot.handlers.gok.game.main import gok_game_router
from tgbot.handlers.gok.game.products import gok_game_products_router
from tgbot.handlers.gok.main import gok_router
from tgbot.handlers.group.admin.admin import group_admin_router
from tgbot.handlers.group.admin.settings import group_settings_router
from tgbot.handlers.group.cmds import group_cmds_router
from tgbot.handlers.group.group_join import chat_member
from tgbot.handlers.group.main import group_main_router
from tgbot.handlers.group.management import group_management_router
from tgbot.handlers.group.user.casino import group_casino_router
from tgbot.handlers.group.user.main import group_user_router
from tgbot.handlers.group.whois import whois_router
from tgbot.handlers.head.group.game.achievements import head_game_achievements_router
from tgbot.handlers.head.group.game.casino import head_game_casino_router
from tgbot.handlers.head.group.game.filters import head_game_filters_router
from tgbot.handlers.head.group.game.history import head_game_history_router
from tgbot.handlers.head.group.game.main import head_game_router
from tgbot.handlers.head.group.game.products import head_game_products_router
from tgbot.handlers.head.group.game.rating import head_group_game_rating_router
from tgbot.handlers.head.group.main import head_group_router
from tgbot.handlers.head.group.members import head_group_members_router
from tgbot.handlers.head.group.rating import head_group_rating_router
from tgbot.handlers.head.main import head_router
from tgbot.handlers.inline.inline import user_inline_router
from tgbot.handlers.mip.broadcast import mip_broadcast_router
from tgbot.handlers.mip.game.achievements import mip_game_achievements_router
from tgbot.handlers.mip.game.main import mip_game_router
from tgbot.handlers.mip.game.products import mip_game_products_router
from tgbot.handlers.mip.main import mip_router
from tgbot.handlers.mip.schedule.list import mip_list_router
from tgbot.handlers.mip.schedule.main import mip_schedule_router
from tgbot.handlers.mip.schedule.upload import mip_upload_router
from tgbot.handlers.root.main import root_router
from tgbot.handlers.search.main import search_router
from tgbot.handlers.user.auth.main import user_auth_router
from tgbot.handlers.user.game.achievements import user_game_achievements_router
from tgbot.handlers.user.game.casino import user_game_casino_router
from tgbot.handlers.user.game.history import user_game_history_router
from tgbot.handlers.user.game.inventory import user_game_inventory_router
from tgbot.handlers.user.game.products import duty_game_products_router
from tgbot.handlers.user.game.shop import user_game_shop_router
from tgbot.handlers.user.links import user_links_router
from tgbot.handlers.user.main import user_router

routers_list = [
    deeplink_group,
    root_router,
    admin_router,
    admin_schedule_router,
    admin_upload_router,
    admin_list_router,
    gok_router,
    gok_game_router,
    gok_game_products_router,
    gok_game_achievements_router,
    head_router,
    head_game_router,
    head_game_history_router,
    head_game_achievements_router,
    head_game_products_router,
    head_game_filters_router,
    head_group_game_rating_router,
    head_group_router,
    head_group_members_router,
    head_group_rating_router,
    head_game_casino_router,
    mip_router,
    mip_game_router,
    mip_game_products_router,
    mip_game_achievements_router,
    mip_broadcast_router,
    mip_schedule_router,
    mip_upload_router,
    mip_list_router,
    search_router,
    user_router,
    user_auth_router,
    duty_game_products_router,
    user_game_shop_router,
    user_game_inventory_router,
    user_game_achievements_router,
    user_game_casino_router,
    user_game_history_router,
    user_links_router,
    user_inline_router,
    group_main_router,
    group_cmds_router,
    group_management_router,
    whois_router,
    group_admin_router,
    group_user_router,
    group_casino_router,
    group_settings_router,
    chat_member,
]

__all__ = [
    "routers_list",
]
