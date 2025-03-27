import logging
import asyncio
import threading
from datetime import datetime, timedelta
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackQueryHandler,
    filters
)
from handlers import (
    start, register_name, register_group, register_phone, register_purchased, register_remaining,
    cancel, show_main_menu, profile_change_request, booking_callback_handler,
    REGISTER_NAME, REGISTER_GROUP, REGISTER_PHONE, REGISTER_PURCHASED, REGISTER_REMAINING, PROFILE_CHANGE,
    SWAP_SELECT
)
from admin_handlers import admin_menu, admin_callback_handler, admin_message_handler
from db import init_db, conn, get_user_by_id
from admin_notify import send_reminder_user, send_reminder_admin
from config import TOKEN
from apscheduler.schedulers.asyncio import AsyncIOScheduler

async def check_reminders():
    """
    Проверяет записи на завтрашний день и отправляет напоминания:
      - Пользователю: индивидуальное напоминание.
      - Администратору: сводное сообщение по всем записям.
    """
    tomorrow = (datetime.now() + timedelta(days=1)).date().isoformat()
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_id, booking_date, time_slot FROM bookings WHERE booking_date = ?", (tomorrow,))
    bookings = cursor.fetchall()
    # Отправляем напоминание каждому пользователю
    for booking in bookings:
        booking_id, user_id, booking_date, time_slot = booking
        user = get_user_by_id(user_id)
        if user:
            user_chat_id = user[1]  # Предполагается, что telegram_id хранится в столбце с индексом 1
            await send_reminder_user(user_chat_id, booking_date, time_slot)
    if bookings:
        summary = []
        for booking in bookings:
            booking_id, user_id, booking_date, time_slot = booking
            user = get_user_by_id(user_id)
            if user:
                user_name = user[2]
                user_phone = user[4]
                summary.append((time_slot, user_name, user_phone))
        await send_reminder_admin(tomorrow, summary)

def start_scheduler():
    # Создаем отдельный цикл событий для планировщика в новом потоке
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    scheduler = AsyncIOScheduler(event_loop=loop)
    # Планируем напоминание каждый день в 8:00
    scheduler.add_job(check_reminders, 'cron', hour=8, minute=0)
    scheduler.start()
    loop.run_forever()

def main():
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
    )
    init_db()
    application = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            REGISTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_name)],
            REGISTER_GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_group)],
            REGISTER_PHONE: [MessageHandler(filters.CONTACT, register_phone)],
            REGISTER_PURCHASED: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_purchased)],
            REGISTER_REMAINING: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_remaining)],
            PROFILE_CHANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_change_request)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    application.add_handler(conv_handler)
    
    # Админский функционал
    application.add_handler(CommandHandler("admin", admin_menu))
    application.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^admin_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_message_handler))
    
    # Основной обработчик callback-запросов для остальных команд
    application.add_handler(CallbackQueryHandler(booking_callback_handler, pattern="^(?!admin_).*"))
    
    # Запускаем планировщик в отдельном потоке
    threading.Thread(target=start_scheduler, daemon=True).start()
    
    application.run_polling()

if __name__ == '__main__':
    main()
