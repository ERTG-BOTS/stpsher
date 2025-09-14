import datetime

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from infrastructure.api.production_calendar import production_calendar
from infrastructure.database.models import Employee
from infrastructure.database.repo.KPI.requests import KPIRequestsRepo
from tgbot.keyboards.user.kpi import kpi_calculator_kb, kpi_kb, kpi_salary_kb
from tgbot.keyboards.user.main import MainMenu
from tgbot.misc.dicts import russian_months
from tgbot.services.schedule import ScheduleParser

user_kpi_router = Router()
user_kpi_router.message.filter(F.chat.type == "private")
user_kpi_router.callback_query.filter(F.message.chat.type == "private")


@user_kpi_router.callback_query(MainMenu.filter(F.menu == "kpi"))
async def user_kpi_cb(
    callback: CallbackQuery, user: Employee, kpi_repo: KPIRequestsRepo
):
    premium = await kpi_repo.spec_premium.get_premium(fullname=user.fullname)
    if premium is None:
        await callback.message.edit_text(
            """🌟 <b>Показатели</b>

Не смог найти твои показатели в премиуме :(""",
            reply_markup=kpi_kb(),
        )
        return

    def format_value(value, suffix=""):
        return f"{value}{suffix}" if value is not None else "—"

    def format_percentage(value):
        return f"{value}%" if value is not None else "—"

    message_text = f"""🌟 <b>Показатели</b>

📊 <b>Оценка клиента - {format_percentage(premium.csi_premium)}</b>
<blockquote>Факт: {format_value(premium.csi)}
План: {format_value(premium.csi_normative)}  </blockquote>

🎯 <b>Отклик</b>
<blockquote>Факт: {format_value(premium.csi_response)}
План: {format_value(round(premium.csi_response_normative))}</blockquote>

🔧 <b>FLR - {format_percentage(premium.flr_premium)}</b>
<blockquote>Факт: {format_value(premium.flr)}
План: {format_value(premium.flr_normative)}</blockquote>

⚖️ <b>ГОК - {format_percentage(premium.gok_premium)}</b>
<blockquote>Факт: {format_value(premium.gok)}
План: {format_value(premium.gok_normative)}</blockquote>

🎯 <b>Цель - {format_percentage(premium.target_premium)}</b>
<blockquote>Тип: {premium.target_type or "—"}
Факт: {format_value(premium.target)}
План: {format_value(round(premium.target_goal_first))} / {format_value(round(premium.target_goal_second))}</blockquote>

💼 <b>Дополнительно</b>
<blockquote>Дисциплина: {format_percentage(premium.discipline_premium)}
Тестирование: {format_percentage(premium.tests_premium)}
Благодарности: {format_percentage(premium.thanks_premium)}
Наставничество: {format_percentage(premium.tutors_premium)}
Ручная правка: {format_percentage(premium.head_adjust_premium)}</blockquote>

💰 <b>Итого:</b>
<b>Общая премия: {format_percentage(premium.total_premium)}</b>

{"📈 Всего чатов: " + format_value(premium.contacts_count) if user.division == "НЦК" else "📈 Всего звонков: " + format_value(premium.contacts_count)}
{"⏰ Задержка: " + format_value(premium.delay, " сек") if user.division != "НЦК" else ""}
<i>Выгружено: {premium.updated_at.replace(tzinfo=datetime.timezone.utc).astimezone(datetime.timezone(datetime.timedelta(hours=5))).strftime("%d.%m.%y %H:%M") if premium.updated_at else "—"}</i>
<i>Обновлено: {datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5))).strftime("%d.%m.%y %H:%M")}</i>"""

    try:
        await callback.message.edit_text(message_text, reply_markup=kpi_kb())
    except TelegramBadRequest:
        await callback.answer("Обновлений нет")


@user_kpi_router.callback_query(MainMenu.filter(F.menu == "kpi_calculator"))
async def user_kpi_calculator_cb(
    callback: CallbackQuery, user: Employee, kpi_repo: KPIRequestsRepo
):
    user_premium = await kpi_repo.spec_premium.get_premium(fullname=user.fullname)

    if user_premium is None:
        await callback.message.edit_text(
            """🧮 <b>Калькулятор KPI</b>

Не смог найти твои показатели в премиуме :(""",
            reply_markup=kpi_calculator_kb(),
        )
        return

    def calculate_csi_needed(division: str, current_csi, normative):
        if normative == 0 or normative is None:
            return "—"

        current_csi = current_csi or 0

        results = []

        if division == "НЦК":
            thresholds = [
                (101, 20, "≥ 101%"),
                (100.5, 15, "≥ 100,5%"),
                (100, 10, "≥ 100%"),
                (98, 5, "≥ 98%"),
                (0, 0, "&lt; 98%"),
            ]
        elif division == "НТП1":
            thresholds = [
                (101, 20, "≥ 101%"),
                (100.5, 15, "≥ 100,5%"),
                (100, 10, "≥ 100%"),
                (98, 5, "≥ 98%"),
                (0, 0, "&lt; 98%"),
            ]
        else:
            thresholds = [
                (100.8, 20, "≥ 100.8%"),
                (100.4, 15, "≥ 100.4%"),
                (100, 10, "≥ 100%"),
                (98, 5, "≥ 98%"),
                (0, 0, "&lt; 98%"),
            ]

        for threshold, premium_percent, description in thresholds:
            needed_csi = (threshold / 100) * normative

            if current_csi >= needed_csi:
                results.append(f"{premium_percent}%: ✅ ({description})")
            else:
                difference = needed_csi - current_csi
                results.append(
                    f"{premium_percent}%: {needed_csi:.3f} [+{difference:.3f}] ({description})"
                )

        return "\n".join(results)

    def calculate_flr_needed(division: str, current_flr, normative):
        if normative == 0 or normative is None:
            return "—"

        current_flr = current_flr or 0

        results = []

        if division == "НЦК":
            thresholds = [
                (103, 30, "≥ 103%"),
                (102, 25, "≥ 102%"),
                (101, 21, "≥ 101%"),
                (100, 18, "≥ 100%"),
                (95, 13, "≥ 95%"),
                (0, 8, "&lt; 95%"),
            ]
        elif division == "НТП1":
            thresholds = [
                (109, 30, "≥ 109%"),
                (106, 25, "≥ 106%"),
                (103, 21, "≥ 103%"),
                (100, 18, "≥ 100%"),
                (90, 13, "≥ 90%"),
                (0, 8, "&lt; 90%"),
            ]
        else:
            thresholds = [
                (107, 30, "≥ 107%"),
                (104, 25, "≥ 104%"),
                (102, 21, "≥ 102%"),
                (100, 18, "≥ 100%"),
                (97, 13, "≥ 97%"),
                (0, 8, "&lt; 97%"),
            ]

        for threshold, premium_percent, description in thresholds:
            needed_flr = (threshold / 100) * normative

            if current_flr >= needed_flr:
                results.append(f"{premium_percent}%: ✅ ({description})")
            else:
                difference = needed_flr - current_flr
                results.append(
                    f"{premium_percent}%: {needed_flr:.2f} [+{difference:.2f}] ({description})"
                )

        return "\n".join(results)

    def calculate_gok_needed(division: str, current_gok, normative):
        if normative == 0 or normative is None:
            return "—"

        current_gok = current_gok or 0

        results = []

        if division == "НЦК":
            thresholds = [
                (100, 17, "≥ 100%"),
                (95, 15, "≥ 95%"),
                (90, 12, "≥ 90%"),
                (85, 9, "≥ 85%"),
                (80, 5, "≥ 80%"),
                (0, 0, "&lt; 80%"),
            ]
        elif division == "НТП1":
            thresholds = [
                (100, 17, "≥ 100%"),
                (95, 15, "≥ 95%"),
                (90, 12, "≥ 90%"),
                (85, 9, "≥ 85%"),
                (80, 5, "≥ 80%"),
                (0, 0, "&lt; 80%"),
            ]
        else:
            thresholds = [
                (100, 17, "≥ 100%"),
                (95, 15, "≥ 95%"),
                (90, 12, "≥ 90%"),
                (84, 9, "≥ 84%"),
                (70, 5, "≥ 70%"),
                (0, 0, "&lt; 70%"),
            ]

        for threshold, premium_percent, description in thresholds:
            needed_gok = (threshold / 100) * normative

            if current_gok >= needed_gok:
                results.append(f"{premium_percent}%: ✅ ({description})")
            else:
                difference = needed_gok - current_gok
                results.append(
                    f"{premium_percent}%: {needed_gok:.3f} [+{difference:.3f}] ({description})"
                )

        return "\n".join(results)

    def calculate_target_needed(
        current_target,
        target_goal_first,
        target_goal_second,
        target_type=None,
    ):
        if target_goal_first is None and target_goal_second is None:
            return "—"

        current_target = current_target or 0

        # Determine if this is a sales target (higher is better) or AHT target (lower is better)
        is_sales_target = target_type and "Продажа оборудования" in target_type
        is_aht_target = target_type and "AHT" in target_type

        results = []

        # All divisions have the same target premium thresholds
        if target_goal_second and target_goal_second > 0:
            # When there's a second goal, use it as the main normative
            normative = target_goal_second

            if is_aht_target:
                # For AHT, lower is better - calculate percentage as (normative / current * 100)
                target_rate = (
                    (normative / current_target * 100) if current_target > 0 else 0
                )
            elif is_sales_target:
                # For sales, higher is better - calculate percentage as (current / normative * 100)
                target_rate = (current_target / normative * 100) if normative > 0 else 0
            else:
                # Default behavior (higher is better) - calculate percentage as (current / normative * 100)
                target_rate = (current_target / normative * 100) if normative > 0 else 0

            if target_rate > 100.01:
                results.append("28%: ✅ (≥ 100,01% - план 2 и более)")
            else:
                if is_aht_target:
                    # For AHT, we need to be lower than the target
                    needed_for_28 = normative / (100.01 / 100)
                    difference = current_target - needed_for_28
                    results.append(
                        f"28%: {needed_for_28:.2f} [-{difference:.2f}] (≥ 100,01% - план 2 и более)"
                    )
                else:
                    # For sales, we need to be higher than the target
                    needed_for_28 = (100.01 / 100) * normative
                    difference = needed_for_28 - current_target
                    results.append(
                        f"28%: {needed_for_28:.2f} [+{difference:.2f}] (≥ 100,01% - план 2 и более)"
                    )

            if target_rate >= 100.00:
                results.append("18%: ✅ (≥ 100,00% - план 1 и менее плана 2)")
            else:
                if is_aht_target:
                    needed_for_18 = normative / (100.00 / 100)
                    difference = current_target - needed_for_18
                    results.append(
                        f"18%: {needed_for_18:.2f} [-{difference:.2f}] (= 100,00% - план 1 и менее плана 2)"
                    )
                else:
                    needed_for_18 = (100.00 / 100) * normative
                    difference = needed_for_18 - current_target
                    results.append(
                        f"18%: {needed_for_18:.2f} [+{difference:.2f}] (= 100,00% - план 1 и менее плана 2)"
                    )

            if target_rate < 99.99:
                results.append("0%: — (&lt; 99,99% - менее плана 1)")
            else:
                results.append("0%: ✅ (&lt; 99,99% - менее плана 1)")

        elif target_goal_first and target_goal_first > 0:
            # When there's only first goal, use it as normative
            normative = target_goal_first

            if is_aht_target:
                # For AHT, lower is better
                target_rate = (
                    (normative / current_target * 100) if current_target > 0 else 0
                )
            elif is_sales_target:
                # For sales, higher is better
                target_rate = (current_target / normative * 100) if normative > 0 else 0
            else:
                # Default behavior (higher is better)
                target_rate = (current_target / normative * 100) if normative > 0 else 0

            if target_rate > 100.01:
                results.append("28%: ✅ (≥ 100,01% - план 2 и более)")
            else:
                if is_aht_target:
                    needed_for_28 = normative / (100.01 / 100)
                    difference = current_target - needed_for_28
                    results.append(
                        f"28%: {needed_for_28:.2f} [-{difference:.2f}] (≥ 100,01% - план 2 и более)"
                    )
                else:
                    needed_for_28 = (100.01 / 100) * normative
                    difference = needed_for_28 - current_target
                    results.append(
                        f"28%: {needed_for_28:.2f} [+{difference:.2f}] (≥ 100,01% - план 2 и более)"
                    )

            if target_rate >= 100.00:
                results.append("18%: ✅ (≥ 100,00% - план 1 и менее плана 2)")
            else:
                if is_aht_target:
                    needed_for_18 = normative / (100.00 / 100)
                    difference = current_target - needed_for_18
                    results.append(
                        f"18%: {needed_for_18:.2f} [-{difference:.2f}] (≥ 100,00% - план 1 и менее плана 2)"
                    )
                else:
                    needed_for_18 = (100.00 / 100) * normative
                    difference = needed_for_18 - current_target
                    results.append(
                        f"18%: {needed_for_18:.2f} [+{difference:.2f}] (≥ 100,00% - план 1 и менее плана 2)"
                    )

            if target_rate < 99.99:
                results.append("0%: — (&lt; 99,99% - менее плана 1)")
            else:
                results.append("0%: ✅ (&lt; 99,99% - менее плана 1)")

        return "\n".join(results)

    def format_value(value, suffix=""):
        return f"{value}{suffix}" if value is not None else "—"

    def format_percentage(value):
        return f"{value}%" if value is not None else "—"

    csi_calculation = calculate_csi_needed(
        user.division, user_premium.csi, user_premium.csi_normative
    )
    flr_calculation = calculate_flr_needed(
        user.division, user_premium.flr, user_premium.flr_normative
    )
    gok_calculation = calculate_gok_needed(
        user.division, user_premium.gok, user_premium.gok_normative
    )
    target_calculation = calculate_target_needed(
        user_premium.target,
        user_premium.target_goal_first,
        user_premium.target_goal_second,
        user_premium.target_type,
    )

    message_text = f"""🧮 <b>Калькулятор KPI</b>

📊 <b>Оценка клиента</b>
<blockquote>Текущий: {format_value(user_premium.csi)} ({format_percentage(user_premium.csi_normative_rate)})
План: {format_value(user_premium.csi_normative)}

<b>Для премии:</b>
{csi_calculation}</blockquote>

🔧 <b>FLR</b>
<blockquote>Текущий: {format_value(user_premium.flr)} ({format_percentage(user_premium.flr_normative_rate)})
План: {format_value(user_premium.flr_normative)}

<b>Для премии:</b>
{flr_calculation}</blockquote>

⚖️ <b>ГОК</b>
<blockquote>Текущий: {format_value(round(user_premium.gok))} ({format_percentage(user_premium.gok_normative_rate)})
План: {format_value(round(user_premium.gok_normative))}

<b>Для премии:</b>
{gok_calculation}</blockquote>

🎯 <b>Цель</b>
<blockquote>Факт: {format_value(user_premium.target)} ({format_percentage(round((user_premium.target_goal_first / user_premium.target * 100) if user_premium.target_type and "AHT" in user_premium.target_type and user_premium.target and user_premium.target > 0 and user_premium.target_goal_first else (user_premium.target / user_premium.target_goal_first * 100) if user_premium.target_goal_first and user_premium.target_goal_first > 0 else 0))} / {format_percentage(round((user_premium.target_goal_second / user_premium.target * 100) if user_premium.target_type and "AHT" in user_premium.target_type and user_premium.target and user_premium.target > 0 and user_premium.target_goal_second else (user_premium.target / user_premium.target_goal_second * 100) if user_premium.target_goal_second and user_premium.target_goal_second > 0 else 0))})
План: {format_value(round(user_premium.target_goal_first))} / {format_value(round(user_premium.target_goal_second))}

Требуется минимум 100 {"чатов" if user.division == "НЦК" else "звонков"} для получения премии за цель

<b>Для премии:</b>
{target_calculation}</blockquote>

<i>Данные от: {user_premium.updated_at.replace(tzinfo=datetime.timezone.utc).astimezone(datetime.timezone(datetime.timedelta(hours=5))).strftime("%d.%m.%y %H:%M") if user_premium.updated_at else "—"}</i>"""

    try:
        await callback.message.edit_text(message_text, reply_markup=kpi_calculator_kb())
    except TelegramBadRequest:
        await callback.answer("Обновлений нет")


@user_kpi_router.callback_query(MainMenu.filter(F.menu == "kpi_salary"))
async def user_kpi_salary_cb(
    callback: CallbackQuery, user: Employee, kpi_repo: KPIRequestsRepo
):
    user_premium = await kpi_repo.spec_premium.get_premium(fullname=user.fullname)

    if user_premium is None:
        await callback.message.edit_text(
            """💰 <b>Расчет зарплаты</b>

Не смог найти твои показатели в премиуме :(""",
            reply_markup=kpi_salary_kb(),
        )
        return

    def format_value(value, suffix=""):
        return f"{value}{suffix}" if value is not None else "—"

    def format_percentage(value):
        return f"{value}%" if value is not None else "—"

    pay_rate = 0.0
    match user.division:
        case "НЦК":
            match user.position:
                case "Специалист":
                    pay_rate = 156.7
                case "Ведущий специалист":
                    pay_rate = 164.2
                case "Эксперт":
                    pay_rate = 195.9
        case "НТП1":
            match user.position:
                case "Специалист первой линии":
                    pay_rate = 143.6
        case "НТП2":
            match user.position:
                case "Специалист второй линии":
                    pay_rate = 166
                case "Ведущий специалист второй линии":
                    pay_rate = 181
                case "Эксперт второй линии":
                    pay_rate = 195.9

    # Get current month working hours from actual schedule
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5)))
    current_month_name = russian_months[now.month]

    # Get actual schedule data
    schedule_parser = ScheduleParser()
    try:
        schedule_data = schedule_parser.get_user_schedule(
            user.fullname, current_month_name, user.division
        )

        # Calculate actual working hours from schedule with holiday detection
        total_working_hours = 0
        working_days = 0
        holiday_hours = 0
        holiday_days_worked = []

        for day, schedule_time in schedule_data.items():
            if schedule_time and schedule_time not in ["Не указано", "В", "О"]:
                # Parse time format like "08:00-17:00"
                import re

                time_match = re.search(
                    r"(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})", schedule_time
                )
                if time_match:
                    start_hour, start_min, end_hour, end_min = map(
                        int, time_match.groups()
                    )
                    start_minutes = start_hour * 60 + start_min
                    end_minutes = end_hour * 60 + end_min

                    # Handle overnight shifts
                    if end_minutes < start_minutes:
                        end_minutes += 24 * 60

                    day_hours = (end_minutes - start_minutes) / 60

                    # For 12-hour shifts, subtract 1 hour for lunch break
                    if day_hours == 12:
                        day_hours = 11

                    # Check if this day is a holiday
                    try:
                        work_date = datetime.date(now.year, now.month, int(day))
                        is_holiday = await production_calendar.is_holiday(work_date)
                        holiday_name = await production_calendar.get_holiday_name(
                            work_date
                        )

                        if is_holiday and holiday_name:
                            holiday_hours += day_hours
                            holiday_days_worked.append(
                                f"{day} - {holiday_name} (+{day_hours:.0f}ч)"
                            )
                    except (ValueError, Exception):
                        # Ignore date parsing errors or API failures
                        pass

                    total_working_hours += day_hours
                    working_days += 1

    except Exception as e:
        raise Exception(f"Произошла ошибка при расчете: {e}")

    # Calculate salary components with holiday x2 multiplier
    # Base salary = regular hours + holiday hours * 2
    regular_hours = total_working_hours - holiday_hours
    base_salary = (regular_hours * pay_rate) + (holiday_hours * pay_rate * 2)

    premium_multiplier = (user_premium.total_premium or 0) / 100
    premium_amount = base_salary * premium_multiplier
    total_salary = base_salary + premium_amount

    message_text = f"""💰 <b>Расчет зарплаты</b>

📅 <b>Период:</b> {current_month_name} {now.year}

⏰ <b>Рабочие часы:</b>
<blockquote>Рабочих дней: {working_days}
Всего часов: {round(total_working_hours)}{
        f'''
🎉 Праздничные дни (x2): {round(holiday_hours)}ч
{chr(10).join(holiday_days_worked)}'''
        if holiday_days_worked
        else ""
    }</blockquote>

💵 <b>Оклад:</b>
<blockquote>Ставка в час: {format_value(pay_rate, " ₽")}
{
        f"Обычные часы: {round(regular_hours)}ч × {pay_rate}₽ = {round(regular_hours * pay_rate)}₽"
        if regular_hours > 0
        else ""
    }
{
        f"Праздничные часы: {round(holiday_hours)}ч × {pay_rate * 2}₽ = {round(holiday_hours * pay_rate * 2)}₽"
        if holiday_hours > 0
        else ""
    }
Сумма оклада: {format_value(round(base_salary), " ₽")}</blockquote>

🎁 <b>Премия:</b>
<blockquote>Процент премии: {format_percentage(user_premium.total_premium)}
Сумма премии: {format_value(round(premium_amount), " ₽")}</blockquote>

💰 <b>Итого к выплате:</b>
<b>{format_value(round(total_salary), " ₽")}</b>

<blockquote expandable>Это <b>примерная</b> сумма после вычета НДФЛ
Районный коэффициент <b>не участвует в расчете</b>, т.к. примерно покрывает НДФЛ</blockquote>

<i>Расчет от: {now.strftime("%d.%m.%y %H:%M")}</i>
<i>Данные премии от: {
        user_premium.updated_at.replace(tzinfo=datetime.timezone.utc)
        .astimezone(datetime.timezone(datetime.timedelta(hours=5)))
        .strftime("%d.%m.%y %H:%M")
        if user_premium.updated_at
        else "—"
    }</i>"""

    try:
        await callback.message.edit_text(message_text, reply_markup=kpi_salary_kb())
    except TelegramBadRequest:
        await callback.answer("Обновлений нет")
