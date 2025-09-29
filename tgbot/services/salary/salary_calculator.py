import datetime
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from infrastructure.api.production_calendar import production_calendar
from infrastructure.database.models import Employee
from tgbot.misc.dicts import russian_months
from tgbot.services.schedule import ScheduleParser

from .pay_rates import PayRateService


@dataclass
class SalaryCalculationResult:
    """Result of salary calculation"""

    # Базовая информация
    user: Employee
    current_month_name: str
    current_year: int
    pay_rate: float

    # Рабочие часы
    working_days: int
    total_working_hours: float
    regular_hours: float
    night_hours: float
    holiday_hours: float
    night_holiday_hours: float
    holiday_days_worked: List[str]

    # Дополнительные смены
    additional_shift_hours: float
    additional_shift_holiday_hours: float
    additional_shift_night_hours: float
    additional_shift_night_holiday_hours: float
    additional_shift_days_worked: List[str]

    # Компоненты зарплаты
    base_salary: float
    additional_shift_salary: float
    additional_shift_rate: float
    additional_shift_holiday_rate: float
    additional_shift_night_rate: float
    additional_shift_night_holiday_rate: float

    # Премия
    csi_premium_amount: float
    flr_premium_amount: float
    gok_premium_amount: float
    target_premium_amount: float
    discipline_premium_amount: float
    tests_premium_amount: float
    thanks_premium_amount: float
    tutors_premium_amount: float
    head_adjust_premium_amount: float
    premium_amount: float

    # Финальный подсчет зарплаты
    total_salary: float

    # Мета
    calculation_time: datetime.datetime
    premium_updated_at: Optional[datetime.datetime]


class SalaryCalculator:
    """Central service for salary calculations"""

    @staticmethod
    def _calculate_night_hours(
        start_hour: int, start_min: int, end_hour: int, end_min: int
    ) -> float:
        """
        Подсчет ночных часов (с 22:00 до 06:00) по локальному времени сотрудника
        """
        start_minutes = start_hour * 60 + start_min
        end_minutes = end_hour * 60 + end_min

        if end_minutes < start_minutes:
            end_minutes += 24 * 60

        night_start = 22 * 60  # 22:00 в минутах
        night_end = 6 * 60  # 06:00 в минутах (следующий день)

        total_night_minutes = 0

        # Проверяем рабочие часы в первый день (22:00-24:00)
        first_day_night_start = night_start
        first_day_night_end = 24 * 60  # Полночь

        if start_minutes < first_day_night_end and end_minutes > first_day_night_start:
            overlap_start = max(start_minutes, first_day_night_start)
            overlap_end = min(end_minutes, first_day_night_end)
            if overlap_end > overlap_start:
                total_night_minutes += overlap_end - overlap_start

        # Проверяем ночные часы во второй день (00:00-06:00)
        if end_minutes > 24 * 60:  # Смена продолжается на следующий день
            second_day_start = 24 * 60
            second_day_end = end_minutes
            second_day_night_start = 24 * 60  # 00:00 следующего дня
            second_day_night_end = 24 * 60 + night_end  # 06:00 следующего дня

            if (
                second_day_start < second_day_night_end
                and second_day_end > second_day_night_start
            ):
                overlap_start = max(second_day_start, second_day_night_start)
                overlap_end = min(second_day_end, second_day_night_end)
                if overlap_end > overlap_start:
                    total_night_minutes += overlap_end - overlap_start

        return total_night_minutes / 60  # Конвертируем в часы

    @staticmethod
    async def _process_schedule_data(
        schedule_data: Dict[str, str],
        now: datetime.datetime,
        is_additional_shift: bool = False,
    ) -> Tuple[float, float, float, float, float, List[str]]:
        """Обработка данных графика и возврат разбивки рабочего времени"""
        total_hours = 0.0
        night_hours = 0.0
        holiday_hours = 0.0
        night_holiday_hours = 0.0
        working_days = 0
        days_worked = []

        for day, schedule_time in schedule_data.items():
            if schedule_time and schedule_time not in ["Не указано", "В", "О"]:
                # Парсим время в виде "08:00-17:00"
                time_match = re.search(
                    r"(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})", schedule_time
                )
                if time_match:
                    start_hour, start_min, end_hour, end_min = map(
                        int, time_match.groups()
                    )
                    start_minutes = start_hour * 60 + start_min
                    end_minutes = end_hour * 60 + end_min

                    if end_minutes < start_minutes:
                        end_minutes += 24 * 60

                    day_hours = (end_minutes - start_minutes) / 60

                    # Считаем ночные часы для этой смены
                    shift_night_hours = SalaryCalculator._calculate_night_hours(
                        start_hour, start_min, end_hour, end_min
                    )

                    # Для 12-часовой смены отнимаем 1 час на обед
                    if day_hours == 12:
                        day_hours = 11
                        if shift_night_hours > 0:
                            shift_night_hours = shift_night_hours * (11 / 12)

                    # Проверка на праздничный день
                    try:
                        work_date = datetime.date(now.year, now.month, int(day))
                        is_holiday = await production_calendar.is_holiday(work_date)
                        holiday_name = await production_calendar.get_holiday_name(
                            work_date
                        )

                        if is_holiday and holiday_name:
                            holiday_hours += day_hours
                            night_holiday_hours += shift_night_hours
                            if is_additional_shift:
                                days_worked.append(
                                    f"{day} - {holiday_name} (+{day_hours:.0f}ч доп.)"
                                )
                            else:
                                days_worked.append(
                                    f"{day} - {holiday_name} (+{day_hours:.0f}ч)"
                                )
                        else:
                            night_hours += shift_night_hours
                            if is_additional_shift:
                                days_worked.append(
                                    f"{day} - Доп. смена (+{day_hours:.0f}ч)"
                                )
                    except (ValueError, Exception):
                        night_hours += shift_night_hours
                        if is_additional_shift:
                            days_worked.append(
                                f"{day} - Доп. смена (+{day_hours:.0f}ч)"
                            )

                    total_hours += day_hours
                    working_days += 1

        return (
            total_hours,
            night_hours,
            holiday_hours,
            night_holiday_hours,
            working_days,
            days_worked,
        )

    @classmethod
    async def calculate_salary(
        cls, user: Employee, premium_data, current_month: Optional[str] = None
    ) -> SalaryCalculationResult:
        """Считаем общую зарплату сотрудника"""
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5)))
        current_month_name = current_month or russian_months[now.month]

        # Получаем ЧТС
        pay_rate = PayRateService.get_pay_rate(user.division, user.position)
        if pay_rate == 0.0:
            raise ValueError(
                f"Не найдено ЧТС для '{user.division}' на позиции '{user.position}'"
            )

        # Get schedule data
        schedule_parser = ScheduleParser()
        try:
            schedule_data, additional_shifts_data = (
                schedule_parser.get_user_schedule_with_additional_shifts(
                    user.fullname, current_month_name, user.division
                )
            )
        except Exception as e:
            raise Exception(f"Произошла ошибка при расчете: {e}")

        (
            total_working_hours,
            night_hours,
            holiday_hours,
            night_holiday_hours,
            working_days,
            holiday_days_worked,
        ) = await cls._process_schedule_data(
            schedule_data, now, is_additional_shift=False
        )

        # Процессим дополнительные смены
        (
            additional_shift_hours,
            additional_shift_night_hours,
            additional_shift_holiday_hours,
            additional_shift_night_holiday_hours,
            _,
            additional_shift_days_worked,
        ) = await cls._process_schedule_data(
            additional_shifts_data, now, is_additional_shift=True
        )

        # Считаем обычные часы (исключая ночные часы и праздники их расчета)
        regular_hours = (
            total_working_hours - holiday_hours - night_hours - night_holiday_hours
        )
        regular_additional_shift_hours = (
            additional_shift_hours
            - additional_shift_holiday_hours
            - additional_shift_night_hours
            - additional_shift_night_holiday_hours
        )

        # Считаем базовую зарплату
        base_salary = (
            (regular_hours * pay_rate)
            + (holiday_hours * pay_rate * PayRateService.get_holiday_multiplier())
            + (night_hours * pay_rate * PayRateService.get_night_multiplier())
            + (
                night_holiday_hours
                * pay_rate
                * PayRateService.get_night_holiday_multiplier()
            )
        )

        # Считаем зарплату за дополнительные смены
        additional_shift_rate = (
            pay_rate * PayRateService.get_additional_shift_multiplier()
        )
        additional_shift_holiday_rate = (
            additional_shift_rate * PayRateService.get_holiday_multiplier()
        )
        additional_shift_night_rate = (
            additional_shift_rate * PayRateService.get_night_multiplier()
        )
        additional_shift_night_holiday_rate = (
            additional_shift_rate * PayRateService.get_night_holiday_multiplier()
        )

        additional_shift_salary = (
            (regular_additional_shift_hours * additional_shift_rate)
            + (additional_shift_holiday_hours * additional_shift_holiday_rate)
            + (additional_shift_night_hours * additional_shift_night_rate)
            + (
                additional_shift_night_holiday_hours
                * additional_shift_night_holiday_rate
            )
        )

        # Считаем индивидуальную сумму для каждого показателя премии (основываясь на базовой зарплате)
        # Проверяем тип премиум данных (HeadPremium vs SpecPremium)
        is_head_premium = hasattr(premium_data, "head_adjust") and not hasattr(
            premium_data, "csi_premium"
        )

        if is_head_premium:
            # Для руководителей - только FLR, GOK, цель и корректировка руководителя
            csi_premium_amount = 0
            flr_premium_amount = base_salary * ((premium_data.flr_premium or 0) / 100)
            gok_premium_amount = base_salary * ((premium_data.gok_premium or 0) / 100)
            target_premium_amount = base_salary * (
                (premium_data.target_premium or 0) / 100
            )
            discipline_premium_amount = 0
            tests_premium_amount = 0
            thanks_premium_amount = 0
            tutors_premium_amount = 0
            head_adjust_premium_amount = base_salary * (
                (premium_data.head_adjust or 0) / 100
            )
        else:
            # Для специалистов - все показатели
            csi_premium_amount = base_salary * ((premium_data.csi_premium or 0) / 100)
            flr_premium_amount = base_salary * ((premium_data.flr_premium or 0) / 100)
            gok_premium_amount = base_salary * ((premium_data.gok_premium or 0) / 100)
            target_premium_amount = base_salary * (
                (premium_data.target_premium or 0) / 100
            )
            discipline_premium_amount = base_salary * (
                (premium_data.discipline_premium or 0) / 100
            )
            tests_premium_amount = base_salary * (
                (premium_data.tests_premium or 0) / 100
            )
            thanks_premium_amount = base_salary * (
                (premium_data.thanks_premium or 0) / 100
            )
            tutors_premium_amount = base_salary * (
                (premium_data.tutors_premium or 0) / 100
            )
            head_adjust_premium_amount = base_salary * (
                (premium_data.head_adjust_premium or 0) / 100
            )

        # Считаем общую сумму премии
        premium_multiplier = (premium_data.total_premium or 0) / 100
        premium_amount = base_salary * premium_multiplier
        total_salary = base_salary + premium_amount + additional_shift_salary

        return SalaryCalculationResult(
            user=user,
            current_month_name=current_month_name,
            current_year=now.year,
            pay_rate=pay_rate,
            working_days=working_days,
            total_working_hours=total_working_hours,
            regular_hours=regular_hours,
            night_hours=night_hours,
            holiday_hours=holiday_hours,
            night_holiday_hours=night_holiday_hours,
            holiday_days_worked=holiday_days_worked,
            additional_shift_hours=additional_shift_hours,
            additional_shift_holiday_hours=additional_shift_holiday_hours,
            additional_shift_night_hours=additional_shift_night_hours,
            additional_shift_night_holiday_hours=additional_shift_night_holiday_hours,
            additional_shift_days_worked=additional_shift_days_worked,
            base_salary=base_salary,
            additional_shift_salary=additional_shift_salary,
            additional_shift_rate=additional_shift_rate,
            additional_shift_holiday_rate=additional_shift_holiday_rate,
            additional_shift_night_rate=additional_shift_night_rate,
            additional_shift_night_holiday_rate=additional_shift_night_holiday_rate,
            csi_premium_amount=csi_premium_amount,
            flr_premium_amount=flr_premium_amount,
            gok_premium_amount=gok_premium_amount,
            target_premium_amount=target_premium_amount,
            discipline_premium_amount=discipline_premium_amount,
            tests_premium_amount=tests_premium_amount,
            thanks_premium_amount=thanks_premium_amount,
            tutors_premium_amount=tutors_premium_amount,
            head_adjust_premium_amount=head_adjust_premium_amount,
            premium_amount=premium_amount,
            total_salary=total_salary,
            calculation_time=now,
            premium_updated_at=getattr(premium_data, "updated_at", None),
        )
