from typing import List, Optional

from sqlalchemy import select

from infrastructure.database.models.STP.achievement import Achievement
from infrastructure.database.repo.base import BaseRepo


class AchievementsRepo(BaseRepo):
    async def get_achievements(self, division: str = None) -> List[Achievement]:
        """
        Получаем полный список достижений

        Args:
            division: Фильтр по направлению (НЦК, НТП и т.д.)
        """

        if division:
            select_stmt = select(Achievement).where(Achievement.division == division)
        else:
            select_stmt = select(Achievement)

        result = await self.session.execute(select_stmt)
        achievements = result.scalars().all()

        return list(achievements)

    async def get_achievement(self, achievement_id: int) -> Optional[Achievement]:
        """
        Получение информации о достижении по его идентификатору

        Args:
            achievement_id: Уникальный идентификатор достижения в таблице achievements
        """

        select_stmt = select(Achievement).where(Achievement.id == achievement_id)
        result = await self.session.execute(select_stmt)

        return result.scalar_one()
