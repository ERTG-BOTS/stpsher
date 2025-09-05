import logging
import smtplib
import ssl
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from infrastructure.database.models import Product, Employee
from infrastructure.database.models.STP.purchase import Purchase
from tgbot.config import load_config

config = load_config(".env")

logger = logging.getLogger(__name__)


async def send_email(
    to_addrs: list[str] | str, subject: str, body: str, html: bool = True
):
    """
    Отправка email

    Args:
        to_addrs: Список адресов для отправки письма
        subject: Заголовок письма
        body: Тело письма
        html: Использовать ли HTML для форматирования
    """
    context = ssl.create_default_context()

    msg = MIMEMultipart()
    msg["From"] = config.mail.user
    msg["To"] = ", ".join(to_addrs) if isinstance(to_addrs, list) else to_addrs
    msg["Subject"] = Header(subject, "utf-8")

    content_type = "html" if html else "plain"
    msg.attach(MIMEText(body, content_type, "utf-8"))

    try:
        with smtplib.SMTP_SSL(
            host=config.mail.host, port=config.mail.port, context=context
        ) as server:
            server.login(user=config.mail.user, password=config.mail.password)
            server.sendmail(
                from_addr=config.mail.user, to_addrs=to_addrs, msg=msg.as_string()
            )
    except smtplib.SMTPException as e:
        logger.error(f"[Email] Ошибка отправки письма: {e}")


async def send_auth_email(code: str, email: str, bot_username: str):
    email_subject = "Авторизация в боте"
    email_content = f"""Добрый день<br><br>
    
Код для авторизации: <b>{code}</b><br>
Введите код в бота @{bot_username} для завершения авторизации"""

    await send_email(to_addrs=email, subject=email_subject, body=email_content)
    logger.info(
        f"[Авторизация] Письмо с кодом авторизации {code} отправлено на {email}"
    )


async def send_activation_product_email(
    user: Employee,
    user_head: Employee | None,
    current_duty: Employee | None,
    product: Product,
    purchase: Purchase,
):
    email_subject = "Активация предмета"
    email_content = f"""Добрый день!<br><br>

<b>{user.fullname}</b>{f" (https://t.me/{user.username})" if user.username else ""} отправил запрос на активацию <b>{product.name}</b><br>
📝 Описание: {product.description}<br>
📍 Активаций: <b>{purchase.usage_count + 1}</b> из <b>{product.count}</b><br><br>

Для активации перейдите в СТПшера"""

    email = []
    if user.division == "НЦК":
        email.append(config.mail.nck_email_addr)
    else:
        email.append(config.mail.ntp_email_addr)

    if user_head and user_head.email:
        email.append(user_head.email)

    if current_duty and current_duty.email:
        email.append(current_duty.email)

    await send_email(to_addrs=email, subject=email_subject, body=email_content)
    logger.info(
        f"[Активация предмета] Уведомление об активации {product.name} пользователем {user.fullname} отправлено на {email}"
    )


async def send_cancel_product_email(
    user: Employee,
    user_head: Employee | None,
    current_duty: Employee | None,
    product: Product,
    purchase: Purchase,
):
    email_subject = "Отмена покупки"
    email_content = f"""Добрый день!<br><br>

<b>{user.fullname}</b>{f" (https://t.me/{user.username})" if user.username else ""} отменил использование <b>{product.name}</b><br>
📝 Описание: {product.description}<br>
📍 Активаций: <b>{purchase.usage_count}</b> из <b>{product.count}</b>"""

    email = []
    if user.division == "НЦК":
        email.append(config.mail.nck_email_addr)
    else:
        email.append(config.mail.ntp_email_addr)

    if user_head and user_head.email:
        email.append(user_head.email)

    if current_duty and current_duty.email:
        email.append(current_duty.email)

    await send_email(to_addrs=email, subject=email_subject, body=email_content)
    logger.info(
        f"[Активация предмета] Уведомление об отмене активации {product.name} пользователем {user.fullname} отправлено на {email}"
    )
