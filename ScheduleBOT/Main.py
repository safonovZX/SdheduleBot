import telebot
from db import *
from datetime import datetime, timedelta
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from Config import *
import time

# Инициализация базы данных
init_db()

# Создание экземпляра бота
bot = telebot.TeleBot(BOT_TOKEN)

notification_cache = {}

def check_time_to_next_lesson(user_id, current_time, lesson_end_time, next_lesson_start_time):   
    current_timestamp = time.time()
    
    # Проверяем, не отправляли ли мы уже уведомление в последние 5 минут
    if user_id in notification_cache:
        if current_timestamp - notification_cache[user_id] < 300:  # 300 секунд = 5 минут
            return
    
    try:
        # Проверяем, осталось ли 5 минут до конца урока
        if lesson_end_time - current_time <= 5 * 60:
            msg = bot.send_message(user_id, "⚠️ Внимание: до конца урока осталось 5 минут!")
            notification_cache[user_id] = current_timestamp

        # Проверяем, осталось ли 5 минут до начала следующего урока
        if next_lesson_start_time - current_time <= 5 * 60:
            msg = bot.send_message(user_id, "⚠️ Внимание: до начала следующего урока осталось 5 минут!")
            notification_cache[user_id] = current_timestamp
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления: {e}")

def start_time_checker():
    while True:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT user_id FROM lessons")
            users = cursor.fetchall()
            
            current_time = datetime.now().time()
            current_seconds = current_time.hour * 3600 + current_time.minute * 60
            
            for user in users:
                user_id = user[0]
                lessons = get_sorted_lessons(user_id)
                
                if lessons:
                    for i in range(len(lessons)):
                        lesson_end = datetime.strptime(lessons[i][2], "%H:%M").time()
                        lesson_end_seconds = lesson_end.hour * 3600 + lesson_end.minute * 60
                        
                        if i < len(lessons) - 1:
                            next_lesson = datetime.strptime(lessons[i+1][1], "%H:%M").time()
                            next_lesson_seconds = next_lesson.hour * 3600 + next_lesson.minute * 60
                            
                            check_time_to_next_lesson(
                                user_id,
                                current_seconds,
                                lesson_end_seconds,
                                next_lesson_seconds
                            )
            
            conn.close()
            time.sleep(60)
            
        except Exception as e:
            logger.error(f"Ошибка в time_checker: {e}")
            time.sleep(60)

# Хендлер команды /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username

    # Добавляем пользователя в базу данных
    add_user(user_id, username)

    # Главное меню
    main_key = ReplyKeyboardMarkup(resize_keyboard=True)
    main_key.add(KeyboardButton("🌵 Расписание"), KeyboardButton("🕒 Изменить"), KeyboardButton("⚙️ Настройки"))
    bot.reply_to(message, f"{start_msg}", reply_markup=main_key)


# Хендлер для отображения расписания
@bot.message_handler(func=lambda message: message.text == "🌵 Расписание")
def send_schedule(message):
    user_id = message.from_user.id
    lessons = get_lessons(user_id)

    if not lessons:
        bot.reply_to(message, "✖️ Ваше расписание пусто.")
        return

    schedule = "✔️ Ваше расписание:\n"
    for lesson in lessons:
        schedule += f"{lesson[0]}: {lesson[1]} - {lesson[2]} | {lesson[3]}\n"
    bot.reply_to(message, schedule)


# Хендлер для изменения расписания
@bot.message_handler(func=lambda message: message.text == "🕒 Изменить")
def set_schedule(message):
    lesson_set = InlineKeyboardMarkup()
    lesson_set.add(
        InlineKeyboardButton("➕ Добавить урок", callback_data="addlesson"),
        InlineKeyboardButton("✖️ Удалить урок", callback_data="dellesson"),
        InlineKeyboardButton("↩️ Вернуться", callback_data="menureturn")
    )
    bot.reply_to(message, "✔️ Выберите действие:", reply_markup=lesson_set)


@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    if call.data == "addlesson":
        bot.send_message(call.message.chat.id, "✔️ Введите время начала урока (ЧЧ:ММ):")
        bot.register_next_step_handler(call.message, process_start_time)
    elif call.data == "dellesson":
        delete_lesson(call.message)
    elif call.data == "menureturn":
        send_welcome(call.message)


def process_start_time(message):
    start_time = message.text.strip()
    if not validate_time_format(start_time):
        bot.reply_to(message, "✖️ Неверный формат времени. Попробуйте снова.")
        return
    bot.send_message(message.chat.id, "✔️ Введите время окончания урока (ЧЧ:ММ):")
    bot.register_next_step_handler(message, process_end_time, start_time)


def process_end_time(message, start_time):
    end_time = message.text.strip()
    if not validate_time_format(end_time) or start_time >= end_time:
        bot.reply_to(message, "✖️ Неверный формат или время окончания раньше начала. Попробуйте снова.")
        return
    bot.send_message(message.chat.id, "✔️ Введите название предмета:")
    bot.register_next_step_handler(message, process_subject, start_time, end_time)


def process_subject(message, start_time, end_time):
    subject = message.text.strip()
    if not subject:
        bot.reply_to(message, "✖️ Название предмета не может быть пустым.")
        return
    add_lesson(message.from_user.id, start_time, end_time, subject)
    bot.reply_to(message, f"✔️ Урок '{subject}' добавлен в расписание с {start_time} до {end_time}.")


def delete_lesson(message):
    user_id = message.chat.id  # Получаем ID пользователя
    lessons = get_lessons(user_id)  # Получаем уроки конкретного пользователя

    if not lessons:
        bot.reply_to(message, "✖️ У вас нет уроков для удаления.")
        return set_schedule

    schedule = "✔️ Выберите урок для удаления:\n"
    for lesson in lessons:
        schedule += f"{lesson[0]}: {lesson[1]} - {lesson[2]} | {lesson[3]}\n"
    bot.reply_to(message, schedule + "\nВведите ID урока для удаления:")
    bot.register_next_step_handler(message, confirm_delete_lesson)


def confirm_delete_lesson(message):
    try:
        lesson_id = int(message.text.strip())
        user_id = message.chat.id  # Получаем ID пользователя

        # Проверяем, принадлежит ли урок этому пользователю
        lessons = get_lessons(user_id)
        lesson_ids = [lesson[0] for lesson in lessons]

        if lesson_id not in lesson_ids:
            bot.reply_to(message, "✖️ Урок с таким ID не найден в вашем расписании.")
            return set_schedule

        delete_lesson_by_id(lesson_id)
        bot.reply_to(message, "✔️ Урок успешно удалён.")
    except ValueError:
        bot.reply_to(message, "✖️ Неверный ID. Попробуйте снова.")
        return set_schedule


def validate_time_format(time_str):
    try:
        datetime.strptime(time_str, "%H:%M")
        return True
    except ValueError:
        return False    

# Запуск бота
bot.polling(none_stop=True)