import datetime

from infrastructure.database.models import Employee
from infrastructure.database.models.KPI.head_premium import HeadPremium
from infrastructure.database.models.KPI.spec_premium import SpecPremium
from infrastructure.database.repo.KPI.requests import KPIRequestsRepo
from tgbot.dialogs.getters.common.db_getters import db_getter
from tgbot.services.salary import KPICalculator, SalaryCalculator, SalaryFormatter


async def base_kpi_data(**kwargs):
    base_data = await db_getter(**kwargs)
    user: Employee = base_data.get("user")
    kpi_repo: KPIRequestsRepo = base_data.get("kpi_repo")

    if user.role == 2:
        premium: HeadPremium = await kpi_repo.head_premium.get_premium(
            fullname=user.fullname
        )
    else:
        premium: SpecPremium = await kpi_repo.spec_premium.get_premium(
            fullname=user.fullname
        )

    return {**base_data, "premium": premium}


async def kpi_getter(**kwargs):
    base_data = await base_kpi_data(**kwargs)
    user: Employee = base_data.get("user")
    premium: HeadPremium | SpecPremium = base_data.get("premium")

    if not premium:
        return {
            **base_data,
            "kpi_text": "🌟 <b>Показатели</b>\n\nНе смог найти твои показатели в премиуме :(",
        }

    # Format dates
    updated_at_str = "—"
    if premium.updated_at:
        updated_at_str = (
            premium.updated_at.replace(tzinfo=datetime.timezone.utc)
            .astimezone(datetime.timezone(datetime.timedelta(hours=5)))
            .strftime("%d.%m.%y %H:%M")
        )

    current_time_str = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=5))
    ).strftime("%d.%m.%y %H:%M")

    if user.role == 2:
        kpi_text = f"""🌟 <b>Показатели</b>

🔧 <b>FLR - {SalaryFormatter.format_percentage(premium.flr_premium)}</b>
<blockquote>Факт: {SalaryFormatter.format_value(premium.flr)}
План: {SalaryFormatter.format_value(premium.flr_normative)}</blockquote>

⚖️ <b>ГОК - {SalaryFormatter.format_percentage(premium.gok_premium)}</b>
<blockquote>Факт: {SalaryFormatter.format_value(premium.gok)}
План: {SalaryFormatter.format_value(premium.gok_normative)}</blockquote>

🎯 <b>Цель - {SalaryFormatter.format_percentage(premium.target_premium)}</b>
<blockquote>Тип: {premium.target_type or "—"}
Факт: {SalaryFormatter.format_value(premium.target)}
План: {SalaryFormatter.format_value(round(premium.target_goal_first))} / {SalaryFormatter.format_value(round(premium.target_goal_second))}</blockquote>

💰 <b>Итого:</b>
<b>Общая премия: {SalaryFormatter.format_percentage(premium.total_premium)}</b>

{"📈 Всего чатов: " + SalaryFormatter.format_value(premium.contacts_count) if user.division == "НЦК" else "📈 Всего звонков: " + SalaryFormatter.format_value(premium.contacts_count)}

<i>Выгружено: {premium.updated_at.replace(tzinfo=datetime.timezone.utc).astimezone(datetime.timezone(datetime.timedelta(hours=5))).strftime("%d.%m.%y %H:%M") if premium.updated_at else "—"}</i>
<i>Обновлено: {datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5))).strftime("%d.%m.%y %H:%M")}</i>"""

    else:
        # Conditional contact type text
        contacts_text = (
            f"📈 Всего чатов: {SalaryFormatter.format_value(premium.contacts_count)}"
            if user.division == "НЦК"
            else f"📈 Всего звонков: {SalaryFormatter.format_value(premium.contacts_count)}"
        )

        delay_text = (
            f"⏰ Задержка: {SalaryFormatter.format_value(premium.delay, ' сек')}"
            if user.division != "НЦК"
            else ""
        )

        kpi_text = f"""🌟 <b>Показатели</b>
    
📊 <b>Оценка клиента - {SalaryFormatter.format_percentage(premium.csi_premium)}</b>
<blockquote>Факт: {SalaryFormatter.format_value(premium.csi)}
План: {SalaryFormatter.format_value(premium.csi_normative)}  </blockquote>
    
🎯 <b>Отклик</b>
<blockquote>Факт: {SalaryFormatter.format_value(premium.csi_response)}
План: {SalaryFormatter.format_value(round(premium.csi_response_normative))}</blockquote>
    
🔧 <b>FLR - {SalaryFormatter.format_percentage(premium.flr_premium)}</b>
<blockquote>Факт: {SalaryFormatter.format_value(premium.flr)}
План: {SalaryFormatter.format_value(premium.flr_normative)}</blockquote>
    
⚖️ <b>ГОК - {SalaryFormatter.format_percentage(premium.gok_premium)}</b>
<blockquote>Факт: {SalaryFormatter.format_value(premium.gok)}
План: {SalaryFormatter.format_value(premium.gok_normative)}</blockquote>
    
🎯 <b>Цель - {SalaryFormatter.format_percentage(premium.target_premium)}</b>
<blockquote>Тип: {premium.target_type or "—"}
Факт: {SalaryFormatter.format_value(premium.target)}
План: {SalaryFormatter.format_value(round(premium.target_goal_first))} / {SalaryFormatter.format_value(round(premium.target_goal_second))}</blockquote>
    
💼 <b>Дополнительно</b>
<blockquote>Дисциплина: {SalaryFormatter.format_percentage(premium.discipline_premium)}
Тестирование: {SalaryFormatter.format_percentage(premium.tests_premium)}
Благодарности: {SalaryFormatter.format_percentage(premium.thanks_premium)}
Наставничество: {SalaryFormatter.format_percentage(premium.tutors_premium)}
Ручная правка: {SalaryFormatter.format_percentage(premium.head_adjust_premium)}</blockquote>
    
💰 <b>Итого:</b>
<b>Общая премия: {SalaryFormatter.format_percentage(premium.total_premium)}</b>
    
{contacts_text}
{delay_text}
<i>Выгружено: {updated_at_str}</i>
<i>Обновлено: {current_time_str}</i>"""

    return {**base_data, "kpi_text": kpi_text}


async def kpi_requirements_getter(**kwargs):
    base_data = await base_kpi_data(**kwargs)
    user: Employee = base_data.get("user")
    premium = base_data.get("premium")

    if not premium:
        return {
            **base_data,
            "requirements_text": "🌟 <b>Показатели</b>\n\nНе смог найти твои показатели в премиуме :(",
        }

    requirements_text = KPICalculator.format_requirements_message(
        user=user, premium=premium, is_head=True if user.role == 2 else False
    )

    return {**base_data, "requirements_text": requirements_text}


async def salary_getter(**kwargs):
    base_data = await base_kpi_data(**kwargs)
    user: Employee = base_data.get("user")
    premium = base_data.get("premium")

    if not premium:
        return {
            **base_data,
            "salary_text": "🌟 <b>Показатели</b>\n\nНе смог найти твои показатели в премиуме :(",
        }

    salary_result = await SalaryCalculator.calculate_salary(
        user=user, premium_data=premium
    )

    salary_text = SalaryFormatter.format_salary_message(salary_result, premium)

    return {**base_data, "salary_text": salary_text}
