import time
import json
import telebot
import sqlite3
from telebot import types
import schedule
import datetime
from multiprocessing import Process
with open('config.json') as f:
    service_data = json.load(f)
    bot = telebot.TeleBot(service_data['token'])
    CHAT_ID = service_data['chat_id']
    CHANNEL_ID = service_data['channel_id']
    DATABASE = service_data['database']

def send_message_recursive(chat, msg, counter=5):
    if counter > 0:
        try:
            bot.send_message(chat, msg, parse_mode='MarkdownV2')
        except:
            time.sleep(10)
            send_message_recursive(chat, msg, counter - 1)
    else:
        raise KeyboardInterrupt

def get_description_write(description):
    description_sym = '◻️'
    if description and len(description) > 0:
        description = description.replace('.', '\.').replace(',', '\,')
        return f'||{13 * description_sym}\n{description}\n{13 * description_sym}||\n\n'
    else:
        return ''

def create_pre_msg(tasks, symbol):
    return ''.join([f'{num + 1}\) {task[0]} {symbol}\n{get_description_write(task[1])}' for num, task in enumerate(tasks)])


@bot.message_handler(commands=["create_task"])
def handle_text(message):
    keyboard = types.ReplyKeyboardMarkup(row_width=2)
    button_today = types.KeyboardButton(text="сегодня")
    button_tomorrow = types.KeyboardButton(text="завтра")
    keyboard.add(button_today, button_tomorrow)
    send = bot.reply_to(message, "Задача на сегодня или на завтра?", reply_markup=keyboard)
    bot.register_next_step_handler(send, get_date_for_task)

def get_date_for_task(message):
    send = bot.send_message(message.chat.id, "Введите задачу")
    bot.register_next_step_handler(send, create_task, day=message.text)

def create_task(message, day):
    now = datetime.datetime.now()
    conn = sqlite3.connect(DATABASE)
    if day == 'сегодня':
        date = now
    elif day == 'завтра':
        date = now + datetime.timedelta(days=1)
    else:
        send_message_recursive(message.chat.id, 'ERROR')
    cursor = conn.cursor()
    sqlite_insert_query = """INSERT INTO projects
                          (name, date, status)
                          VALUES
                          (?, ?, ?);"""
    cursor.execute(sqlite_insert_query, (message.text, f'{date.year}-{date.month}-{date.day}', 'не выполнено'))
    conn.commit()
    cursor.close()
    send_message_recursive(message.chat.id, 'принято')

@bot.message_handler(commands=["close_task"])
def handle_text(message):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    date = datetime.datetime.now()
    sqlite_update_query = """SELECT name FROM projects WHERE status = 'не выполнено' AND date = ?"""
    unmade_tasks = cursor.execute(sqlite_update_query, ([f'{date.year}-{date.month}-{date.day}'])).fetchall()
    unmade_tasks = [item[0] for item in unmade_tasks]
    keyboard = types.ReplyKeyboardMarkup(row_width=4)
    buttons = []
    for task in unmade_tasks:
        buttons.append(types.KeyboardButton(text=task))
    keyboard.add(*buttons)
    send = bot.reply_to(message, "Выберите задачу, которую хотите закрыть", reply_markup=keyboard)
    bot.register_next_step_handler(send, close_task)

def close_task(message):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    date = datetime.datetime.now()
    sqlite_update_query = """UPDATE projects SET status = 'выполнено' WHERE name = ? AND date = ?"""
    cursor.execute(sqlite_update_query, (message.text, f'{date.year}-{date.month}-{date.day}'))
    conn.commit()
    cursor.close()
    send_message_recursive(message.chat.id, 'принято')

@bot.message_handler(commands=["add_description"])
def handle_text(message):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    date = datetime.datetime.now()
    sqlite_update_query = """SELECT name FROM projects WHERE date = ?"""
    tasks = cursor.execute(sqlite_update_query, ([f'{date.year}-{date.month}-{date.day}'])).fetchall()
    tasks = [item[0] for item in tasks]
    keyboard = types.ReplyKeyboardMarkup(row_width=4)
    buttons = []
    for task in tasks:
        buttons.append(types.KeyboardButton(text=task))
    keyboard.add(*buttons)
    send = bot.reply_to(message, "Выберите задачу, к которой хотите добавить описание", reply_markup=keyboard)
    bot.register_next_step_handler(send, get_description)

def get_description(message):
    send = bot.send_message(message.chat.id, 'Введите описание')
    bot.register_next_step_handler(send, add_description, task_to_describe=message.text)

def add_description(message, task_to_describe):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    date = datetime.datetime.now()
    sqlite_update_query = """UPDATE projects SET description = ? WHERE name = ? AND date = ?"""
    cursor.execute(sqlite_update_query, (message.text, task_to_describe, f'{date.year}-{date.month}-{date.day}'))
    conn.commit()
    cursor.close()
    send_message_recursive(message.chat.id, 'принято')

@bot.message_handler(commands=["get_tasks"])
def handle_text(message):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    date = datetime.datetime.now()
    sqlite_update_query = """SELECT name, status FROM projects WHERE status = 'выполнено' AND date = ?"""
    made_tasks = cursor.execute(sqlite_update_query, ([f'{date.year}-{date.month}-{date.day}'])).fetchall()
    sqlite_update_query = """SELECT name, status FROM projects WHERE status = 'не выполнено' AND date = ?"""
    unmade_tasks = cursor.execute(sqlite_update_query, ([f'{date.year}-{date.month}-{date.day}'])).fetchall()
    made_tasks = [item[0] for item in made_tasks]
    unmade_tasks = [item[0] for item in unmade_tasks]
    if len(made_tasks) > 0:
        pre_msg_made_task = ''.join([f'{str(num + 1)}\) {task}\n' for num, task in enumerate(made_tasks)])
        msg_made_task = f"Выполнены задачи: \n{pre_msg_made_task}"
    else:
        msg_made_task = f"Нет выполненных задач\n"
    if len(unmade_tasks) > 0:
        pre_msg_unmade_task = ''.join([f'{str(num + 1)}\) {task}\n' for num, task in enumerate(unmade_tasks)])
        msg_unmade_task = f"Не выполнены задачи: \n{pre_msg_unmade_task}"
    else:
        msg_unmade_task = f"Нет невыполненных задач\n"
    send_message_recursive(message.chat.id, f'{msg_made_task}\n{msg_unmade_task}')

def daily_report():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    date = datetime.datetime.now()
    sqlite_select_query = """SELECT name, description FROM projects WHERE status = 'выполнено' AND date = ?"""
    made_tasks = cursor.execute(sqlite_select_query, ([f'{date.year}-{date.month}-{date.day}'])).fetchall()
    sqlite_select_query = """SELECT name, description FROM projects WHERE status = 'не выполнено' AND date = ?"""
    unmade_tasks = cursor.execute(sqlite_select_query, ([f'{date.year}-{date.month}-{date.day}'])).fetchall()
    if len(made_tasks) > 0:
        pre_msg_made_task = create_pre_msg(made_tasks, '✅')
        msg_made_task = f"Выполнены задачи: \n{pre_msg_made_task}"
    else:
        msg_made_task = f"Нет выполненных задач\n"
    if len(unmade_tasks) > 0:
        pre_msg_unmade_task = create_pre_msg(unmade_tasks, '❌')
        msg_unmade_task = f"Не выполнены задачи: \n{pre_msg_unmade_task}"
    else:
        msg_unmade_task = f"Нет невыполненных задач\n"
    date_format = "%d\.%m\.%Y"
    intro_msg = f'🌟Отчёт за {date.strftime(date_format)}🌟'
    send_message_recursive(
        CHANNEL_ID, 
        f'{intro_msg}\n\n{msg_made_task}\n{msg_unmade_task}\nВыполнено {100 * (len(made_tasks) / max(len(made_tasks) + len(unmade_tasks), 1)):.0f}% задач'
    )

def say_i_am_alive():
    now = datetime.datetime.now()
    if now.hour > 8:
        send_message_recursive(
            CHAT_ID, 
            'Я жив'
        )
    
def report_schedule():
    say_i_am_alive()
    schedule.every(2).hours.at("09:00").do(say_i_am_alive)
    schedule.every().day.at("23:59").do(daily_report)
    while True:
        schedule.run_pending()
        time.sleep(1)

def poll():
    bot.infinity_polling()

if __name__ == '__main__':
    proc1 = Process(target=report_schedule)
    proc1.start()
    proc2 = Process(target=poll)
    proc2.start()
    proc1.join()
    proc2.join()
