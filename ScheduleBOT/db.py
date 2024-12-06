# db.py
import sqlite3
import logging

DB_PATH = 'schedule.db'

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='bot_log.log'
)
logger = logging.getLogger(__name__)

def get_db_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Инициализация таблиц
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lessons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        subject TEXT NOT NULL
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT NOT NULL
    )
    """)
    conn.commit()
    conn.close()

def add_user(user_id, username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    conn.close()

def get_lessons(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, start_time, end_time, subject FROM lessons WHERE user_id = ?", (user_id,))
    lessons = cursor.fetchall()
    conn.close()
    return lessons

def add_lesson(user_id, start_time, end_time, subject):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO lessons (user_id, start_time, end_time, subject) VALUES (?, ?, ?, ?)",
                   (user_id, start_time, end_time, subject))
    conn.commit()
    conn.close()

def delete_lesson_by_id(lesson_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM lessons WHERE id = ?", (lesson_id,))
    conn.commit()
    conn.close()

def get_sorted_lessons(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, start_time, end_time, subject 
            FROM lessons 
            WHERE user_id = ? 
            ORDER BY time(start_time)
        """, (user_id,))
        lessons = cursor.fetchall()
        return lessons
    except Exception as e:
        logger.error(f"Ошибка при получении уроков: {e}")
        return []
    finally:
        conn.close()
