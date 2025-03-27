# db.py
# Модуль работы с базой данных SQLite

import sqlite3
from datetime import datetime

conn = sqlite3.connect('bot.db', check_same_thread=False)
cursor = conn.cursor()

def init_db():
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        name TEXT,
        group_code TEXT,
        phone TEXT,
        lessons_purchased INTEGER,
        lessons_remaining INTEGER,
        registration_date TEXT
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        booking_date TEXT,
        time_slot TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS profile_change_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        request_text TEXT,
        timestamp TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    ''')
    conn.commit()

def add_user(telegram_id, name, group_code, phone, lessons_purchased, lessons_remaining):
    cursor.execute('''
    INSERT OR REPLACE INTO users (telegram_id, name, group_code, phone, lessons_purchased, lessons_remaining, registration_date)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (telegram_id, name, group_code, phone, lessons_purchased, lessons_remaining, datetime.now().isoformat()))
    conn.commit()

def get_user_by_telegram_id(telegram_id):
    cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    return cursor.fetchone()

def get_user_by_id(user_id):
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    return cursor.fetchone()

def add_booking(user_id, booking_date, time_slot):
    cursor.execute("INSERT INTO bookings (user_id, booking_date, time_slot) VALUES (?, ?, ?)",
                   (user_id, booking_date, time_slot))
    conn.commit()

def get_bookings_by_telegram_id(telegram_id):
    cursor.execute('''
    SELECT b.id, b.booking_date, b.time_slot FROM bookings b
    JOIN users u ON b.user_id = u.id WHERE u.telegram_id = ?
    ''', (telegram_id,))
    return cursor.fetchall()

def add_profile_change_request(user_id, request_text):
    cursor.execute("INSERT INTO profile_change_requests (user_id, request_text, timestamp) VALUES (?, ?, ?)",
                   (user_id, request_text, datetime.now().isoformat()))
    conn.commit()

def decrement_remaining(user_id):
    """Уменьшает счетчик оставшихся занятий на 1 и возвращает новое значение."""
    cursor.execute("UPDATE users SET lessons_remaining = lessons_remaining - 1 WHERE id = ?", (user_id,))
    conn.commit()
    cursor.execute("SELECT lessons_remaining FROM users WHERE id = ?", (user_id,))
    return cursor.fetchone()[0]

def get_all_users(exclude_telegram_id=None):
    """Возвращает список всех пользователей (id и name). Если указан exclude_telegram_id, исключает данного пользователя."""
    if exclude_telegram_id:
        cursor.execute("SELECT id, name FROM users WHERE telegram_id != ?", (exclude_telegram_id,))
    else:
        cursor.execute("SELECT id, name FROM users")
    return cursor.fetchall()

def get_bookings_by_user_id(user_id):
    """Возвращает список записей для пользователя по его id."""
    cursor.execute("SELECT id, booking_date, time_slot FROM bookings WHERE user_id = ?", (user_id,))
    return cursor.fetchall()

def get_booking_by_id(booking_id):
    """Возвращает запись по её id."""
    cursor.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,))
    return cursor.fetchone()

def swap_bookings(booking_id1, booking_id2):
    cursor.execute("SELECT user_id, booking_date, time_slot FROM bookings WHERE id = ?", (booking_id1,))
    booking1 = cursor.fetchone()
    cursor.execute("SELECT user_id, booking_date, time_slot FROM bookings WHERE id = ?", (booking_id2,))
    booking2 = cursor.fetchone()
    if booking1 and booking2:
        cursor.execute("UPDATE bookings SET user_id = ? WHERE id = ?", (booking2[0], booking_id1))
        cursor.execute("UPDATE bookings SET user_id = ? WHERE id = ?", (booking1[0], booking_id2))
        conn.commit()
        return True
    return False

def update_user_profile(user_id, **kwargs):
    """Обновляет профиль пользователя по его id.
    Параметры должны соответствовать названиям столбцов (например, name, group_code, phone, lessons_remaining)."""
    for key, value in kwargs.items():
        cursor.execute(f"UPDATE users SET {key} = ? WHERE id = ?", (value, user_id))
    conn.commit()

def cancel_booking(booking_id):
    """Отменяет запись и увеличивает количество оставшихся занятий у пользователя на 1."""
    booking = get_booking_by_id(booking_id)
    if booking:
        user_id = booking[1]
        cursor.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
        cursor.execute("UPDATE users SET lessons_remaining = lessons_remaining + 1 WHERE id = ?", (user_id,))
        conn.commit()
        return True
    return False

def delete_user_profile(user_id):
    """Удаляет профиль пользователя и все связанные данные из базы."""
    cursor.execute("DELETE FROM bookings WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM profile_change_requests WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
