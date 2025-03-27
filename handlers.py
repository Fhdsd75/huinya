# handlers.py
# Асинхронные обработчики команд и диалогов основного Telegram-бота

import re
import calendar
import sqlite3
from datetime import datetime, date
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton,
    ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.ext import CallbackContext
from db import (add_user, get_user_by_telegram_id, get_user_by_id, add_booking,
                get_bookings_by_telegram_id, add_profile_change_request, decrement_remaining,
                get_all_users, get_bookings_by_user_id, get_booking_by_id, swap_bookings)
from admin_notify import send_admin_notification
from config import HOLIDAYS, TIME_SLOTS, MONTH_NAMES, WEEKDAY_NAMES, TOKEN
# Импортируем админский список месяцев, который заполняется через админ-функционал
from admin_handlers import admin_available_months

# Состояния для ConversationHandler
REGISTER_NAME, REGISTER_GROUP, REGISTER_PHONE, REGISTER_PURCHASED, REGISTER_REMAINING = range(5)
# Состояния для обмена записями и запроса изменения профиля
SWAP_SELECT = 100  
SWAP_DATE = 101  # Не используется, выбор записи происходит через inline кнопки
PROFILE_CHANGE = 200

def normalize_phone(phone: str) -> str:
    return ''.join(filter(str.isdigit, phone))

# --- Регистрация пользователя ---
async def start(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    user = get_user_by_telegram_id(user_id)
    if user:
        await update.message.reply_text("Добро пожаловать обратно!")
        return await show_main_menu(update, context)
    else:
        await update.message.reply_text("Привет! Вы еще не зарегистрированы.\nВведите, пожалуйста, ваше имя и фамилию:")
        return REGISTER_NAME

async def register_name(update: Update, context: CallbackContext):
    context.user_data['name'] = update.message.text.strip()
    await update.message.reply_text("Введите название группы (например, КБ0425):")
    return REGISTER_GROUP

async def register_group(update: Update, context: CallbackContext):
    group_code = update.message.text.strip()
    if not re.match(r'^[А-ЯЁ]+[0-9]{4,}$', group_code):
        await update.message.reply_text("Неверный формат группы. Попробуйте ещё раз. Пример: КБ0425")
        return REGISTER_GROUP
    context.user_data['group_code'] = group_code
    contact_button = KeyboardButton("Отправить контакт", request_contact=True)
    reply_markup = ReplyKeyboardMarkup([[contact_button]], one_time_keyboard=True)
    await update.message.reply_text("Отправьте, пожалуйста, ваш номер телефона:", reply_markup=reply_markup)
    return REGISTER_PHONE

async def register_phone(update: Update, context: CallbackContext):
    contact = update.message.contact
    if not contact:
        await update.message.reply_text("Пожалуйста, используйте кнопку 'Отправить контакт'.")
        return REGISTER_PHONE
    normalized_phone = normalize_phone(contact.phone_number)
    context.user_data['phone'] = normalized_phone
    await update.message.reply_text("Сколько занятий было куплено? (максимум 5)", reply_markup=ReplyKeyboardRemove())
    return REGISTER_PURCHASED

async def register_purchased(update: Update, context: CallbackContext):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("Пожалуйста, введите число.")
        return REGISTER_PURCHASED
    lessons_purchased = int(text)
    if lessons_purchased > 5:
        await update.message.reply_text("Если занятий больше 5, свяжитесь с администратором для подтверждения.\nВведите временно 5.")
        lessons_purchased = 5
    context.user_data['lessons_purchased'] = lessons_purchased
    await update.message.reply_text("Сколько занятий осталось? (не может быть больше купленного и не менее 1)")
    return REGISTER_REMAINING

async def register_remaining(update: Update, context: CallbackContext):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("Пожалуйста, введите число.")
        return REGISTER_REMAINING
    lessons_remaining = int(text)
    if lessons_remaining < 1 or lessons_remaining > context.user_data['lessons_purchased']:
        await update.message.reply_text("Введено некорректное значение. Количество оставшихся занятий не может быть больше купленного и должно быть не менее 1.\nВведите ещё раз:")
        return REGISTER_REMAINING
    context.user_data['lessons_remaining'] = lessons_remaining
    user_id = update.message.from_user.id
    add_user(user_id, context.user_data['name'], context.user_data['group_code'],
             context.user_data['phone'], context.user_data['lessons_purchased'],
             context.user_data['lessons_remaining'])
    await update.message.reply_text("Регистрация завершена!", reply_markup=ReplyKeyboardRemove())
    return await show_main_menu(update, context)

async def cancel(update: Update, context: CallbackContext):
    await update.message.reply_text("Операция отменена.", reply_markup=ReplyKeyboardRemove())
    return -1

# --- Главное меню и профиль пользователя ---
async def show_main_menu(update: Update, context: CallbackContext):
    user = get_user_by_telegram_id(update.effective_user.id)
    if user and user[6] <= 0:
        menu_text = "Меню:\nУ вас закончились возможности записи, купите еще возможности на запись."
    else:
        menu_text = "Меню:"
    keyboard = [
        [InlineKeyboardButton("Мой профиль", callback_data="menu_profile")],
        [InlineKeyboardButton("Записаться", callback_data="menu_booking")],
        [InlineKeyboardButton("Мои записи", callback_data="menu_my_bookings")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text(menu_text, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text(menu_text, reply_markup=reply_markup)
    return -1

async def show_profile(update: Update, context: CallbackContext):
    user_id = update.callback_query.from_user.id
    user = get_user_by_telegram_id(user_id)
    if user:
        profile_text = (f"Ваш профиль:\n"
                        f"{user[2]}\nТелефон: {user[4]}\nГруппа: {user[3]}\n"
                        f"Записи: {user[6]}/{user[5]}")
        keyboard = [
            [InlineKeyboardButton("Назад", callback_data="profile_back")],
            [InlineKeyboardButton("Запросить изменение профиля", callback_data="profile_change")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text(profile_text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text("Профиль не найден.")
    return -1

async def profile_change_request(update: Update, context: CallbackContext):
    request_text = update.message.text.strip()
    if not request_text:
        await update.message.reply_text("Пожалуйста, введите запрос.")
        return PROFILE_CHANGE
    user_id = update.message.from_user.id
    user = get_user_by_telegram_id(user_id)
    if user:
        add_profile_change_request(user[0], request_text)
        msg = (f"Имя: {user[2]}\n"
               f"Группа: {user[3]}\n"
               f"Телефон: {user[4]}\n"
               f"Текст запроса: {request_text}")
        from admin_notify import send_admin_notification
        await send_admin_notification(msg)
    await update.message.reply_text("Ваша заявка была отправлена, ожидайте.", reply_markup=ReplyKeyboardRemove())
    return await show_main_menu(update, context)

# --- Запись на занятия ---
async def start_booking(update: Update, context: CallbackContext):
    if not admin_available_months:
        await update.callback_query.edit_message_text("Запись недоступна. Нет доступных месяцев. Обратитесь к администратору.")
        return await show_main_menu(update, context)
    user = get_user_by_telegram_id(update.callback_query.from_user.id)
    if user and user[6] <= 0:
        await update.callback_query.edit_message_text("У вас закончились возможности записи, купите еще возможности на запись.")
        return await show_main_menu(update, context)
    keyboard = []
    for m in admin_available_months:
        button = InlineKeyboardButton(MONTH_NAMES.get(m, str(m)), callback_data=f"booking_month_{m}")
        keyboard.append([button])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text("Выберите месяц для записи:", reply_markup=reply_markup)
    return -1

async def show_weeks(update: Update, context: CallbackContext, month: int):
    query = update.callback_query
    year = datetime.now().year
    weeks = list(calendar.Calendar(firstweekday=0).monthdayscalendar(year, month))
    keyboard = []
    week_num = 1
    conn = sqlite3.connect('bot.db', check_same_thread=False)
    cur = conn.cursor()
    for week in weeks:
        available_slots = 0
        for day in week:
            if day == 0:
                continue
            d = date(year, month, day)
            if d.weekday() == 4 or d.isoformat() in HOLIDAYS:
                continue
            total = len(TIME_SLOTS)
            cur.execute("SELECT COUNT(*) FROM bookings WHERE booking_date = ?", (d.isoformat(),))
            booked = cur.fetchone()[0]
            free = total - booked
            available_slots += free
        button_text = f"Неделя {week_num} (свободно {available_slots} записей)"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"booking_week_{month}_{week_num-1}")])
        week_num += 1
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"Выберите неделю в {MONTH_NAMES.get(month, month)}:", reply_markup=reply_markup)
    return -1

async def show_days(update: Update, context: CallbackContext, month: int, week_index: int):
    query = update.callback_query
    year = datetime.now().year
    weeks = list(calendar.Calendar(firstweekday=0).monthdayscalendar(year, month))
    if week_index >= len(weeks):
        await query.edit_message_text("Неделя не найдена.")
        return -1
    week = weeks[week_index]
    keyboard = []
    for day in week:
        if day == 0:
            continue
        d = date(year, month, day)
        day_name = WEEKDAY_NAMES.get(d.weekday(), "")
        status = "свободно"
        if d.weekday() == 4 or d.isoformat() in HOLIDAYS:
            status = "выходной"
        button_text = f"{day} ({day_name}) - {status}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"booking_day_{year}_{month}_{day}")])
    keyboard.append([InlineKeyboardButton("Назад", callback_data="menu_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Выберите день для записи:", reply_markup=reply_markup)
    return -1

async def show_time_slots(update: Update, context: CallbackContext, year: int, month: int, day: int):
    query = update.callback_query
    d = date(year, month, day)
    if d.weekday() == 4 or d.isoformat() in HOLIDAYS:
        await query.edit_message_text("На выбранный день запись невозможна (выходной).")
        return await show_main_menu(update, context)
    keyboard = []
    conn = sqlite3.connect('bot.db', check_same_thread=False)
    cur = conn.cursor()
    # Получаем записи для данного дня с user_id
    cur.execute("SELECT time_slot, user_id FROM bookings WHERE booking_date = ?", (d.isoformat(),))
    bookings_data = cur.fetchall()
    # Строим словарь: time_slot -> user_id
    booked_dict = {row[0]: row[1] for row in bookings_data}
    from db import get_user_by_id
    for idx, slot in enumerate(TIME_SLOTS):
        if slot in booked_dict:
            # Получаем имя пользователя, который записан
            booked_user = get_user_by_id(booked_dict[slot])
            if booked_user:
                name = booked_user[2]
                button_text = f"{slot} ({name})"
            else:
                button_text = f"{slot} (занято)"
            keyboard.append([InlineKeyboardButton(button_text, callback_data="dummy")])
        else:
            button_text = f"{slot} (свободно)"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"booking_slot_{year}_{month}_{day}_{idx}")])
    keyboard.append([InlineKeyboardButton("Назад", callback_data="menu_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(f"Выберите время для {d}:", reply_markup=reply_markup)
    return -1

async def booking_callback_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "menu_back":
        return await show_main_menu(update, context)
    elif data.startswith("menu_profile"):
        return await show_profile(update, context)
    elif data.startswith("menu_booking"):
        return await start_booking(update, context)
    elif data.startswith("menu_my_bookings"):
        return await show_my_bookings(update, context)
    elif data.startswith("profile_back"):
        return await show_main_menu(update, context)
    elif data.startswith("profile_change"):
        await query.edit_message_text("Введите кратко, что хотите изменить и причину:")
        return PROFILE_CHANGE
    elif data.startswith("booking_month_"):
        month = int(data.split("_")[-1])
        return await show_weeks(update, context, month)
    elif data.startswith("booking_week_"):
        parts = data.split("_")
        month = int(parts[2])
        week_index = int(parts[3])
        return await show_days(update, context, month, week_index)
    elif data.startswith("booking_day_"):
        parts = data.split("_")
        year = int(parts[2])
        month = int(parts[3])
        day = int(parts[4])
        return await show_time_slots(update, context, year, month, day)
    elif data.startswith("booking_slot_"):
        parts = data.split("_")
        year = int(parts[2])
        month = int(parts[3])
        day = int(parts[4])
        time_index = int(parts[5])
        selected_time = TIME_SLOTS[time_index]
        d = date(year, month, day)
        user = get_user_by_telegram_id(update.callback_query.from_user.id)
        if user and user[6] <= 0:
            await update.callback_query.edit_message_text("У вас закончились возможности записи, купите еще возможности на запись.")
            return await show_main_menu(update, context)
        context.user_data['booking_date'] = d.isoformat()
        context.user_data['time_slot'] = selected_time
        keyboard = [
            [InlineKeyboardButton("СОГЛАСЕН", callback_data="confirm_booking_agree")],
            [InlineKeyboardButton("НЕ СОГЛАСЕН", callback_data="confirm_booking_decline")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"Вы хотите записаться на {d} {selected_time}?\n"
            "Принимаете условия: если не придёте или откажетесь менее чем за 24 часа до занятия – запись не возвращается.\n"
            "Запись отменить нельзя, можно только поменяться с кем-то.\nСогласны?",
            reply_markup=reply_markup
        )
        return -1
    elif data == "confirm_booking_agree":
        user_id = update.callback_query.from_user.id
        user = get_user_by_telegram_id(user_id)
        if not user:
            await update.callback_query.edit_message_text("Ошибка: пользователь не найден.")
            return -1
        if user[6] <= 0:
            await update.callback_query.edit_message_text("У вас закончились возможности записи, купите еще возможности на запись.")
            return await show_main_menu(update, context)
        add_booking(user[0], context.user_data['booking_date'], context.user_data['time_slot'])
        new_remaining = decrement_remaining(user[0])
        msg = (f"Пользователь {user[2]} (Группа: {user[3]}, Телефон: {user[4]}) записался на занятие: "
               f"{context.user_data['booking_date']} {context.user_data['time_slot']}. Осталось: {new_remaining}")
        await send_admin_notification(msg)
        await context.bot.delete_message(chat_id=update.callback_query.message.chat_id,
                                           message_id=update.callback_query.message.message_id)
        await context.bot.send_message(chat_id=update.callback_query.message.chat_id,
                                       text=f"Вы успешно записались на {context.user_data['booking_date']} {context.user_data['time_slot']}")
        menu_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Мой профиль", callback_data="menu_profile")],
            [InlineKeyboardButton("Записаться", callback_data="menu_booking")],
            [InlineKeyboardButton("Мои записи", callback_data="menu_my_bookings")]
        ])
        await context.bot.send_message(chat_id=update.callback_query.message.chat_id,
                                       text="Меню:", reply_markup=menu_keyboard)
        return -1
    elif data == "confirm_booking_decline":
        await update.callback_query.edit_message_text("Запись не подтверждена. Возврат в меню.")
        return await show_main_menu(update, context)
    elif data.startswith("mybooking_"):
        booking_id = int(data.split("_")[1])
        keyboard = [
            [InlineKeyboardButton("Поменяться с кем-то", callback_data=f"swap_request_{booking_id}")],
            [InlineKeyboardButton("Назад", callback_data="menu_back")]
        ]
        await update.callback_query.edit_message_text(f"Бронирование ID {booking_id}", reply_markup=InlineKeyboardMarkup(keyboard))
        return -1
    elif data.startswith("swap_request_"):
        booking_id = int(data.split("_")[2])
        context.user_data['swap_booking_id'] = booking_id
        return await show_user_list_for_swap(update, context)
    elif data.startswith("swap_select_"):
        parts = data.split("_")
        try:
            my_booking_id = int(parts[2])
            partner_id = int(parts[3])
        except ValueError:
            await update.callback_query.edit_message_text("Ошибка в данных обмена.")
            return -1
        context.user_data['swap_booking_id'] = my_booking_id
        context.user_data['swap_partner_id'] = partner_id
        partner_bookings = get_bookings_by_user_id(partner_id)
        if not partner_bookings:
            await update.callback_query.edit_message_text("У выбранного пользователя нет записей для обмена.")
            return await show_main_menu(update, context)
        keyboard = []
        for pb in partner_bookings:
            pb_id, pb_date, pb_time = pb
            button_text = f"{pb_date} {pb_time}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"swap_partner_{pb_id}")])
        keyboard.append([InlineKeyboardButton("Отмена", callback_data="menu_back")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text("Выберите запись партнёра для обмена:", reply_markup=reply_markup)
        return SWAP_SELECT
    elif data.startswith("swap_partner_"):
        parts = data.split("_")
        try:
            partner_booking_id = int(parts[2])
        except ValueError:
            await update.callback_query.edit_message_text("Ошибка: неверный формат данных.")
            return -1
        my_booking_id = context.user_data.get('swap_booking_id')
        partner_id = context.user_data.get('swap_partner_id')
        if not my_booking_id or not partner_id:
            await update.callback_query.edit_message_text("Ошибка: данные обмена отсутствуют.")
            return -1
        my_booking = get_booking_by_id(my_booking_id)
        partner_booking = get_booking_by_id(partner_booking_id)
        initiator = get_user_by_telegram_id(update.callback_query.from_user.id)
        partner = get_user_by_id(partner_id)
        confirmation_text = (f"Пользователь {initiator[2]} (Группа: {initiator[3]}) предлагает обмен:\n"
                             f"Ваша запись: {partner_booking[2]} {partner_booking[3]}\n"
                             f"на его запись: {my_booking[2]} {my_booking[3]}\n"
                             "Вы согласны?")
        confirmation_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Согласен", callback_data=f"swap_confirm_{my_booking_id}_{partner_booking_id}")],
            [InlineKeyboardButton("Отмена", callback_data=f"swap_decline_{my_booking_id}_{partner_booking_id}")]
        ])
        await context.bot.send_message(chat_id=partner[1], text=confirmation_text, reply_markup=confirmation_keyboard)
        await update.callback_query.edit_message_text("Запрос на обмен отправлен. Ожидайте подтверждения.")
        return await show_main_menu(update, context)
    elif data.startswith("swap_confirm_"):
        parts = data.split("_")
        try:
            my_booking_id = int(parts[2])
            partner_booking_id = int(parts[3])
        except ValueError:
            await update.callback_query.edit_message_text("Ошибка: неверные данные подтверждения обмена.")
            return -1
        if swap_bookings(my_booking_id, partner_booking_id):
            booking1 = get_booking_by_id(my_booking_id)
            booking2 = get_booking_by_id(partner_booking_id)
            user1 = get_user_by_id(booking1[1])
            user2 = get_user_by_id(booking2[1])
            admin_msg = (f"Обмен записей произведен:\n"
                         f"Пользователь {user1[2]} (Группа: {user1[3]}, Телефон: {user1[4]}) обменял запись {booking1[2]} {booking1[3]} "
                         f"с пользователем {user2[2]} (Группа: {user2[3]}, Телефон: {user2[4]}), запись {booking2[2]} {booking2[3]}.")
            await send_admin_notification(admin_msg)
            await update.callback_query.edit_message_text("Обмен записей успешно произведён.")
        else:
            await update.callback_query.edit_message_text("Ошибка при обмене записей.")
        return await show_main_menu(update, context)
    elif data.startswith("swap_decline_"):
        await update.callback_query.edit_message_text("Обмен отменён.")
        return await show_main_menu(update, context)
    else:
        await update.callback_query.edit_message_text("Неизвестная команда.")
        return -1

async def show_my_bookings(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = update.callback_query.from_user.id
    bookings = get_bookings_by_telegram_id(user_id)
    if not bookings:
        await query.edit_message_text("У вас нет записей.")
        return await show_main_menu(update, context)
    keyboard = []
    for booking in bookings:
        bid, booking_date, time_slot = booking
        button_text = f"{booking_date} {time_slot}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"mybooking_{bid}")])
    keyboard.append([InlineKeyboardButton("Назад", callback_data="menu_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Ваши записи:", reply_markup=reply_markup)
    return -1

async def show_user_list_for_swap(update: Update, context: CallbackContext):
    current_id = update.callback_query.from_user.id
    users = get_all_users(exclude_telegram_id=current_id)
    if not users:
        await update.callback_query.edit_message_text("Нет доступных пользователей для обмена.")
        return await show_main_menu(update, context)
    keyboard = []
    for user in users:
        uid, uname = user
        keyboard.append([InlineKeyboardButton(uname, callback_data=f"swap_select_{context.user_data['swap_booking_id']}_{uid}")])
    keyboard.append([InlineKeyboardButton("Отмена", callback_data="menu_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text("Выберите пользователя для обмена:", reply_markup=reply_markup)
    return SWAP_SELECT
