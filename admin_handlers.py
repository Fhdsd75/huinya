# admin_handlers.py
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from config import ADMIN_CHAT_ID, MONTH_NAMES
from db import get_all_users, update_user_profile, cancel_booking, delete_user_profile

# Глобальная переменная для админского списка месяцев – изначально пустая
admin_available_months = []

async def admin_menu(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("Нет доступа.")
        return
    keyboard = [
        [InlineKeyboardButton("Добавить месяц для записей", callback_data="admin_add_month")],
        [InlineKeyboardButton("Удалить месяц для записей", callback_data="admin_del_month")],
        [InlineKeyboardButton("Редактировать профиль пользователя", callback_data="admin_edit_profile")],
        [InlineKeyboardButton("Отменить запись", callback_data="admin_cancel_booking")],
        [InlineKeyboardButton("Удалить профиль", callback_data="admin_delete_profile")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Админ меню:", reply_markup=reply_markup)

async def admin_callback_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    if update.effective_user.id != ADMIN_CHAT_ID:
        await query.edit_message_text("Нет доступа.")
        return
    data = query.data
    if data == "admin_add_month":
        # Выводим клавиатуру с именами месяцев от 1 до 12
        keyboard = []
        for m in range(1, 13):
            month_name = MONTH_NAMES.get(m, str(m))
            keyboard.append([InlineKeyboardButton(month_name, callback_data=f"admin_add_{m}")])
        keyboard.append([InlineKeyboardButton("Отмена", callback_data="admin_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Выберите месяц для добавления:", reply_markup=reply_markup)
    elif data.startswith("admin_add_"):
        try:
            m = int(data.split("_")[2])
        except ValueError:
            await query.edit_message_text("Ошибка в данных.")
            return
        if m not in admin_available_months:
            admin_available_months.append(m)
            admin_available_months.sort()
            month_name = MONTH_NAMES.get(m, str(m))
            await query.edit_message_text(f"Месяц {month_name} добавлен.")
        else:
            await query.edit_message_text("Этот месяц уже добавлен.")
        await query.message.reply_text("Возврат в меню...")
        return await admin_menu(update, context)
    elif data == "admin_del_month":
        if not admin_available_months:
            await query.edit_message_text("Список месяцев пуст.")
            return await admin_menu(update, context)
        keyboard = []
        for m in admin_available_months:
            month_name = MONTH_NAMES.get(m, str(m))
            keyboard.append([InlineKeyboardButton(month_name, callback_data=f"admin_del_{m}")])
        keyboard.append([InlineKeyboardButton("Отмена", callback_data="admin_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Выберите месяц для удаления:", reply_markup=reply_markup)
    elif data.startswith("admin_del_"):
        try:
            m = int(data.split("_")[2])
        except ValueError:
            await query.edit_message_text("Ошибка в данных.")
            return
        if m in admin_available_months:
            admin_available_months.remove(m)
            month_name = MONTH_NAMES.get(m, str(m))
            await query.edit_message_text(f"Месяц {month_name} удален.")
        else:
            await query.edit_message_text("Такой месяц не найден.")
        await query.message.reply_text("Возврат в меню...")
        return await admin_menu(update, context)
    elif data == "admin_edit_profile":
        users = get_all_users()
        keyboard = []
        for user in users:
            uid, uname = user
            keyboard.append([InlineKeyboardButton(uname, callback_data=f"admin_edit_{uid}")])
        keyboard.append([InlineKeyboardButton("Отмена", callback_data="admin_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Выберите пользователя для редактирования профиля:", reply_markup=reply_markup)
    elif data.startswith("admin_edit_"):
        try:
            uid = int(data.split("_")[2])
        except ValueError:
            await query.edit_message_text("Ошибка в данных.")
            return
        context.user_data['edit_user_id'] = uid
        keyboard = [
            [InlineKeyboardButton("Изменить имя", callback_data="admin_field_name")],
            [InlineKeyboardButton("Изменить группу", callback_data="admin_field_group")],
            [InlineKeyboardButton("Изменить телефон", callback_data="admin_field_phone")],
            [InlineKeyboardButton("Изменить возможности записи", callback_data="admin_field_lessons_remaining")],
            [InlineKeyboardButton("Отмена", callback_data="admin_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Выберите поле для редактирования:", reply_markup=reply_markup)
    elif data.startswith("admin_field_"):
        # Собираем все части после "admin_field_" чтобы получить корректное имя столбца
        field = "_".join(data.split("_")[2:])
        context.user_data['edit_field'] = field
        await query.edit_message_text(f"Введите новое значение для {field} (для lessons_remaining вводите число):")
    elif data == "admin_delete_profile":
        # Вывод списка пользователей для удаления профиля
        users = get_all_users()
        keyboard = []
        for user in users:
            uid, uname = user
            keyboard.append([InlineKeyboardButton(uname, callback_data=f"admin_delprofile_{uid}")])
        keyboard.append([InlineKeyboardButton("Отмена", callback_data="admin_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Выберите пользователя для удаления профиля:", reply_markup=reply_markup)
    elif data.startswith("admin_delprofile_"):
        try:
            uid = int(data.split("_")[2])
        except ValueError:
            await query.edit_message_text("Ошибка в данных.")
            return
        from db import delete_user_profile
        delete_user_profile(uid)
        await query.edit_message_text("Профиль пользователя удалён.")
        return await admin_menu(update, context)
    elif data == "admin_cancel_booking":
        users = get_all_users()
        keyboard = []
        for user in users:
            uid, uname = user
            keyboard.append([InlineKeyboardButton(uname, callback_data=f"admin_cancel_{uid}")])
        keyboard.append([InlineKeyboardButton("Отмена", callback_data="admin_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Выберите пользователя, у которого нужно отменить запись:", reply_markup=reply_markup)
    elif data.startswith("admin_cancel_"):
        try:
            uid = int(data.split("_")[2])
        except ValueError:
            await query.edit_message_text("Ошибка в данных.")
            return
        context.user_data['cancel_user_id'] = uid
        from db import get_bookings_by_user_id
        bookings = get_bookings_by_user_id(uid)
        if not bookings:
            await query.edit_message_text("У выбранного пользователя нет записей.")
            return await admin_menu(update, context)
        keyboard = []
        for b in bookings:
            bid, b_date, b_time = b
            keyboard.append([InlineKeyboardButton(f"{b_date} {b_time}", callback_data=f"admin_cancel_booking_{str(bid).strip()}")])
        keyboard.append([InlineKeyboardButton("Отмена", callback_data="admin_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Выберите запись для отмены:", reply_markup=reply_markup)
    elif data.startswith("admin_cancel_booking_"):
        try:
            bid = int(data.split("_")[-1].strip())
        except ValueError:
            await query.edit_message_text("Ошибка в данных.")
            return
        from db import cancel_booking, get_booking_by_id, get_user_by_id
        if cancel_booking(bid):
            booking = get_booking_by_id(bid)
            if booking:
                user = get_user_by_id(booking[1])
                if user:
                    context.bot.send_message(chat_id=user[1], text="Ваша запись отменена. Возможность записи увеличена на 1.")
            await query.edit_message_text("Запись успешно отменена.")
        else:
            await query.edit_message_text("Ошибка при отмене записи.")
        return await admin_menu(update, context)
    elif data == "admin_menu":
        return await admin_menu(update, context)
    else:
        await query.edit_message_text("Неизвестная команда.")

async def admin_message_handler(update: Update, context: CallbackContext):
    if 'edit_field' in context.user_data:
        new_value = update.message.text.strip()
        uid = context.user_data.get('edit_user_id')
        field = context.user_data.get('edit_field')
        if field == "lessons_remaining" and not new_value.isdigit():
            await update.message.reply_text("Введите число для изменения возможностей записи.")
            return
        if uid and field and new_value:
            update_user_profile(uid, **{field: new_value})
            await update.message.reply_text("Профиль обновлён.")
        else:
            await update.message.reply_text("Ошибка обновления.")
        context.user_data['edit_field'] = None
        context.user_data['edit_user_id'] = None
        await update.message.reply_text("Возврат в меню...")
        return await admin_menu(update, context)
    else:
        await update.message.reply_text("Неизвестная команда.")
