import datetime

from .salary_calculator import SalaryCalculationResult


class SalaryFormatter:
    """Утилита для форматирования результатов расчета заработной платы в сообщения"""

    @staticmethod
    def format_value(value, suffix=""):
        """Форматирует значение с суффиксом, вернет — если None"""
        return f"{value}{suffix}" if value is not None else "—"

    @staticmethod
    def format_percentage(value):
        """Форматирует процентное значение, вернет '—' если None"""
        return f"{value}%" if value is not None else "—"

    @classmethod
    def format_salary_message(
        cls, result: SalaryCalculationResult, premium_data
    ) -> str:
        """Форматирует полное сообщение о расчете зарплаты"""
        # Форматирование блока рабочих часов
        hours_details = []
        if result.regular_hours > 0:
            hours_details.append(
                f"Обычные часы: {round(result.regular_hours)}ч × {result.pay_rate} ₽ = {round(result.regular_hours * result.pay_rate)} ₽"
            )
        if result.night_hours > 0:
            hours_details.append(
                f"Ночные часы: {round(result.night_hours)}ч × {round(result.pay_rate * 1.2, 2)} ₽ = {round(result.night_hours * result.pay_rate * 1.2)} ₽"
            )
        if result.holiday_hours > 0:
            hours_details.append(
                f"Праздничные часы: {round(result.holiday_hours)}ч × {result.pay_rate * 2} ₽ = {round(result.holiday_hours * result.pay_rate * 2)} ₽"
            )
        if result.night_holiday_hours > 0:
            hours_details.append(
                f"Ночные праздничные часы: {round(result.night_holiday_hours)}ч × {round(result.pay_rate * 2.4, 2)} ₽ = {round(result.night_holiday_hours * result.pay_rate * 2.4)} ₽"
            )

        # Форматирование блока дополнительных смен
        additional_shifts_details = []
        regular_additional_shift_hours = (
            result.additional_shift_hours
            - result.additional_shift_holiday_hours
            - result.additional_shift_night_hours
            - result.additional_shift_night_holiday_hours
        )

        if regular_additional_shift_hours > 0:
            additional_shifts_details.append(
                f"Обычные доп. смены: {round(regular_additional_shift_hours)}ч × {result.additional_shift_rate:.2f} ₽ = {round(regular_additional_shift_hours * result.additional_shift_rate)} ₽"
            )
        if result.additional_shift_night_hours > 0:
            additional_shifts_details.append(
                f"Ночные доп. смены: {round(result.additional_shift_night_hours)}ч × {result.additional_shift_night_rate:.2f} ₽ = {round(result.additional_shift_night_hours * result.additional_shift_night_rate)} ₽"
            )
        if result.additional_shift_holiday_hours > 0:
            additional_shifts_details.append(
                f"Праздничные доп. смены: {round(result.additional_shift_holiday_hours)}ч × {result.additional_shift_holiday_rate:.2f} ₽ = {round(result.additional_shift_holiday_hours * result.additional_shift_holiday_rate)} ₽"
            )
        if result.additional_shift_night_holiday_hours > 0:
            additional_shifts_details.append(
                f"Ночные праздничные доп. смены: {round(result.additional_shift_night_holiday_hours)}ч × {result.additional_shift_night_holiday_rate:.2f} ₽ = {round(result.additional_shift_night_holiday_hours * result.additional_shift_night_holiday_rate)} ₽"
            )

        message_text = f"""💰 <b>Расчет зарплаты</b>

📅 <b>Период:</b> {result.current_month_name} {result.current_year}

⏰ <b>Рабочие часы:</b>
<blockquote>Рабочих дней: {result.working_days}
Всего часов: {round(result.total_working_hours)}{
            f'''

🎉 Праздничные дни (x2): {round(result.holiday_hours)}ч
{chr(10).join(result.holiday_days_worked)}'''
            if result.holiday_days_worked
            else ""
        }{
            f'''

⭐ Доп. смены: {round(result.additional_shift_hours)}ч
{chr(10).join(result.additional_shift_days_worked)}'''
            if result.additional_shift_days_worked
            else ""
        }</blockquote>

💵 <b>Оклад:</b>
<blockquote>Ставка в час: {cls.format_value(result.pay_rate, " ₽")}

{chr(10).join(hours_details)}

Сумма оклада: {cls.format_value(round(result.base_salary), " ₽")}</blockquote>{
            f'''

⭐ <b>Доп. смены:</b>
<blockquote>{chr(10).join(additional_shifts_details)}

Сумма доп. смен: {cls.format_value(round(result.additional_shift_salary), " ₽")}</blockquote>'''
            if result.additional_shift_salary > 0
            else ""
        }

🎁 <b>Премия:</b>
<blockquote expandable>Общий процент премии: {
            cls.format_percentage(premium_data.total_premium)
        }
Общая сумма премии: {cls.format_value(round(result.premium_amount), " ₽")}
Стоимость 1% премии: ~{
            round(result.premium_amount / premium_data.total_premium)
            if premium_data.total_premium and premium_data.total_premium > 0
            else 0
        } ₽

🌟 Показатели:"""

        # Определяем тип премиум данных (HeadPremium vs SpecPremium)
        is_head_premium = hasattr(premium_data, "head_adjust") and not hasattr(
            premium_data, "csi_premium"
        )

        if is_head_premium:
            # Для руководителей - только FLR, GOK, цель и корректировка руководителя
            message_text += f"""
FLR: {cls.format_percentage(premium_data.flr_premium)} = {
                cls.format_value(round(result.flr_premium_amount), " ₽")
            }
ГОК: {cls.format_percentage(premium_data.gok_premium)} = {
                cls.format_value(round(result.gok_premium_amount), " ₽")
            }
Цель: {cls.format_percentage(premium_data.target_premium)} = {
                cls.format_value(round(result.target_premium_amount), " ₽")
            }

💼 Дополнительно:
Корректировка руководителя: {cls.format_percentage(premium_data.head_adjust)} = {
                cls.format_value(round(result.head_adjust_premium_amount), " ₽")
            }"""
        else:
            # Для специалистов - все показатели
            message_text += f"""
Оценка: {cls.format_percentage(premium_data.csi_premium)} = {
                cls.format_value(round(result.csi_premium_amount), " ₽")
            }
FLR: {cls.format_percentage(premium_data.flr_premium)} = {
                cls.format_value(round(result.flr_premium_amount), " ₽")
            }
ГОК: {cls.format_percentage(premium_data.gok_premium)} = {
                cls.format_value(round(result.gok_premium_amount), " ₽")
            }
Цель: {cls.format_percentage(premium_data.target_premium)} = {
                cls.format_value(round(result.target_premium_amount), " ₽")
            }

💼 Дополнительно:
Дисциплина: {cls.format_percentage(premium_data.discipline_premium)} = {
                cls.format_value(round(result.discipline_premium_amount), " ₽")
            }
Тестирование: {cls.format_percentage(premium_data.tests_premium)} = {
                cls.format_value(round(result.tests_premium_amount), " ₽")
            }
Благодарности: {cls.format_percentage(premium_data.thanks_premium)} = {
                cls.format_value(round(result.thanks_premium_amount), " ₽")
            }
Наставничество: {cls.format_percentage(premium_data.tutors_premium)} = {
                cls.format_value(round(result.tutors_premium_amount), " ₽")
            }
Ручная правка: {cls.format_percentage(premium_data.head_adjust_premium)} = {
                cls.format_value(round(result.head_adjust_premium_amount), " ₽")
            }"""

        message_text += f"""</blockquote>

💰 <b>Итого к выплате:</b>
~<b>{cls.format_value(round(result.total_salary, 1), " ₽")}</b>

<blockquote expandable>⚠️ <b>Важное</b>

Расчет представляет <b>примерную</b> сумму после вычета НДФЛ
Районный коэффициент <b>не участвует в расчете</b>, т.к. примерно покрывает НДФЛ

🧪 <b>Формулы</b>
Обычные часы: часы × ставка
Праздничные часы: часы × ставка × 2
Ночные часы: часы × ставка × 1.2
Ночные праздничные часы: часы × ставка × 2.4
Доп. смены: часы × (ставка × 2.63)

Ночными часами считается локальное время 22:00 - 6:00
Праздничные дни считаются по производственному <a href='https://www.consultant.ru/law/ref/calendar/proizvodstvennye/'>календарю</a></blockquote>

<i>Расчет от: {result.calculation_time.strftime("%d.%m.%y %H:%M")}</i>
<i>Данные премии от: {
            result.premium_updated_at.replace(tzinfo=datetime.timezone.utc)
            .astimezone(datetime.timezone(datetime.timedelta(hours=5)))
            .strftime("%d.%m.%y %H:%M")
            if result.premium_updated_at
            else "—"
        }</i>"""

        return message_text
