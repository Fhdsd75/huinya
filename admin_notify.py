# admin_notify.py
from telegram import Bot
from config import TOKEN, ADMIN_CHAT_ID

async def send_admin_notification(message: str):
    admin_bot = Bot(token=TOKEN)
    await admin_bot.send_message(chat_id=ADMIN_CHAT_ID, text=message)

async def send_reminder_user(user_chat_id: int, booking_date: str, time_slot: str):
    """
    Отправляет пользователю напоминание о записи.
    Параметры:
      user_chat_id - Telegram ID пользователя,
      booking_date - дата записи (например, "2025-03-27"),
      time_slot - время записи (например, "10:00-11:30").
    """
    bot = Bot(token=TOKEN)
    message = f"Напоминание: у вас запись на {booking_date} в {time_slot} завтра."
    await bot.send_message(chat_id=user_chat_id, text=message)

async def send_reminder_admin(date: str, bookings: list):
    """
    Отправляет администратору напоминание о записях на заданный день.
    Параметры:
      date - дата записей (например, "2025-03-27"),
      bookings - список кортежей вида (time_slot, user_name, user_phone).
    Пример сообщения:
      Напоминание: на 2025-03-27 записаны:
      на время 10:00-11:30 записан Арман Шайхиев +77066186255
      на время 11:30-13:00 записан Иван Иванов +79991234567
    """
    message = f"Напоминание: на {date} записаны:\n"
    for time_slot, user_name, user_phone in bookings:
        message += f"на время {time_slot} записан {user_name} {user_phone}\n"
    await send_admin_notification(message)
