import json
import datetime
import asyncio
import os

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io import BytesIO

import threading
import pyrogram
from pyrogram import Client
import telebot
from telebot import types
import numpy as np
import matplotlib.dates as mdates


async def check_user_online(app, user_id, filename):
    try:
        user = await app.get_users(user_id)
        is_online = 0

        if str(user.status) == "UserStatus.ONLINE":
            is_online = 1
        print(is_online, "is_online", user.username)
        with (open(filename, 'r+') as f):
            data = json.load(f)
            for tracker_id, tracker_data in data.get("trackers", {}).items():
                if user_id in tracker_data.get("users", {}):
                    if tracker_data["users"][str(user_id)] != []:
                        if tracker_data["users"][str(user_id)][-1]["online"] != is_online:
                            if is_online == 0:
                                time = str(user.last_online_date)
                                data["trackers"][tracker_id]["users"][str(user_id)].append(
                                    {"time": time, "online": is_online})

                            else:
                                current_datetime = datetime.datetime.now()
                                time = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
                                data["trackers"][tracker_id]["users"][str(user_id)].append(
                                    {"time": time, "online": is_online})
                    else:
                        current_datetime = datetime.datetime.now()
                        time = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
                        data["trackers"][tracker_id]["users"][str(user_id)].append({"time": time, "online": is_online})
            f.seek(0)
            json.dump(data, f, indent=4)
            f.truncate()
    except pyrogram.errors.UserNotParticipant:
        print(f"User {user_id} not found or not in a chat.")
    except Exception as e:
        print(f"Error checking user {user_id}: {e}")


async def run_internal_bot(app_id, api_hash, bot_token):
    async with Client("my_internal_bot", app_id, api_hash) as app:  # Разное имя сессии
        print("внутрянка работает")
        while True:
            with open('id.json', 'r') as f:
                user_data = json.load(f)

            tasks = []
            for tracker_id, tracker_data in user_data.get("trackers", {}).items():
                for user_id in tracker_data.get("users", {}):
                    tasks.append(check_user_online(app, user_id, 'id.json'))
                    tasks.append(asyncio.sleep(5))  # Задержка 5 секунд для каждого пользователя

            if tasks:
                await asyncio.gather(*tasks)


def run_external_bot(bot_token):
    # Внешний бот(telebot)
    print("Внешний работает", bot_token)
    bot = telebot.TeleBot(bot_token)

    def create_keyboard():
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn_add_user = types.KeyboardButton("Добавить пользователя")
        btn_check_online = types.KeyboardButton("Посмотреть онлайн")
        btn_delete_user = types.KeyboardButton("Удалить пользователя")
        markup.add(btn_add_user, btn_check_online, btn_delete_user)
        return markup

    def create_stats_type_keyboard():
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn_graph = types.KeyboardButton("График")
        btn_text = types.KeyboardButton("Текст")
        markup.add(btn_graph, btn_text)
        return markup

    def create_period_keyboard():
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn_month = types.KeyboardButton("Месяц")
        btn_day = types.KeyboardButton("День")
        btn_hour = types.KeyboardButton("Час")
        markup.add(btn_month, btn_day, btn_hour)
        return markup

    def create_back_keyboard():
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn_back = types.KeyboardButton("Назад")
        markup.add(btn_back)
        return markup

    @bot.message_handler(commands=['start'])
    def start_message(message):
        markup = create_keyboard()
        bot.send_message(message.chat.id,
                         "Здравствуйте!\n"
                         "Это бот позволяет отслеживать онлайн-активность пользователей в Telegram.\n"
                        "Для корректной работы бота необходимо, чтобы у пользователя была включена видимость онлайна."
                         " Нажмите кнопку, чтобы добавить пользователя для отслеживания, посмотреть его онлайн-статус или удалить пользователя.",
                         reply_markup=markup)

    @bot.message_handler(func=lambda message: message.text == "Добавить пользователя")
    def add_user_button_handler(message):
        bot.send_message(message.chat.id, "Отправьте ID пользователя Telegram для отслеживания.",
                         reply_markup=create_back_keyboard())
        bot.register_next_step_handler(message, lambda msg: handle_add_user(msg, message.from_user.id))

    @bot.message_handler(func=lambda message: message.text == "Назад")
    def back_button_handler(message):
        markup = create_keyboard()
        bot.send_message(message.chat.id, "Вы вернулись в основное меню", reply_markup=markup)

    def handle_add_user(message, tracker_id):
        if message.text == "Назад":
            back_button_handler(message)
            return
        try:
            user_id = message.text
            data = {}

            # Проверяем, существует ли файл
            if os.path.exists('id.json'):
                # Если файл существует, пытаемся прочитать его содержимое
                try:
                    with open('id.json', 'r') as f:
                        data = json.load(f)
                except json.JSONDecodeError:
                    # Если файл пустой или невалидный JSON, то начинаем с пустого словаря
                    data = {}
            if "trackers" not in data:
                data["trackers"] = {}

            if str(tracker_id) not in data["trackers"]:
                data["trackers"][str(tracker_id)] = {"tracked_users": [], "users": {}}
            if user_id in data["trackers"][str(tracker_id)]["tracked_users"]:
                bot.reply_to(message, f"Пользователь уже отслеживается {user_id}", reply_markup=create_keyboard())
            else:
                data["trackers"][str(tracker_id)]["tracked_users"].append(user_id)
                bot.reply_to(message, f"Начал отслеживать пользователя {user_id}", reply_markup=create_keyboard())

                # Если такого пользователя нет, то создаем для него новый ключ-список
                if str(user_id) not in data["trackers"][str(tracker_id)]["users"]:
                    data["trackers"][str(tracker_id)]["users"][str(user_id)] = []

            # Записываем обновленные данные в файл
            with open('id.json', 'w') as f:
                json.dump(data, f, indent=4)
        except ValueError:
            bot.reply_to(message, "Неверный формат ID.  Пожалуйста, введите число.", reply_markup=create_keyboard())
        except Exception as e:
            bot.reply_to(message, f"Ошибка: {e}", reply_markup=create_keyboard())

    @bot.message_handler(func=lambda message: message.text == "Посмотреть онлайн")
    def check_online_button_handler(message):
        tracker_id = message.from_user.id
        with open('id.json', 'r') as f:
            data = json.load(f)
            if str(tracker_id) not in data.get("trackers", {}):
                bot.reply_to(message, "У вас нет отслеживаемых пользователей.", reply_markup=create_keyboard())
                return
            tracked_users = data["trackers"][str(tracker_id)].get("tracked_users", [])
            if not tracked_users:
                bot.send_message(message.chat.id, "Вы пока не добавили пользователей для отслеживания.",
                                 reply_markup=create_keyboard())
            else:
                user_ids_str = ", ".join(str(user_id) for user_id in tracked_users)
                bot.send_message(message.chat.id, f"Список отслеживаемых пользователей: {user_ids_str}",
                                 reply_markup=create_keyboard())

        markup = create_stats_type_keyboard()
        bot.send_message(message.chat.id, "Выберите тип отображения статистики.", reply_markup=markup)

    @bot.message_handler(func=lambda message: message.text == "Удалить пользователя")
    def delete_user_button_handler(message):
        bot.send_message(message.chat.id, "Отправьте ID пользователя Telegram для удаления.",
                         reply_markup=create_back_keyboard())
        bot.register_next_step_handler(message, lambda msg: handle_delete_user(msg, message.from_user.id))

    def handle_delete_user(message, tracker_id):
        if message.text == "Назад":
            back_button_handler(message)
            return
        try:
            user_id_to_delete = message.text
            with open('id.json', 'r+') as f:
                data = json.load(f)
                if str(tracker_id) not in data.get("trackers", {}):
                    bot.reply_to(message, "У вас нет отслеживаемых пользователей.", reply_markup=create_keyboard())
                    return

                tracker_data = data["trackers"].get(str(tracker_id), {})
                if user_id_to_delete in tracker_data.get("tracked_users", []):

                    tracker_data["tracked_users"].remove(user_id_to_delete)
                    if str(user_id_to_delete) in tracker_data.get("users", {}):
                        del tracker_data["users"][str(user_id_to_delete)]

                    f.seek(0)
                    json.dump(data, f, indent=4)
                    f.truncate()
                    bot.reply_to(message, f"Пользователь {user_id_to_delete} больше не отслеживается.",
                                 reply_markup=create_keyboard())
                else:
                    bot.reply_to(message, f"Пользователь {user_id_to_delete} не отслеживается.",
                                 reply_markup=create_keyboard())
        except ValueError:
            bot.reply_to(message, "Неверный формат ID. Пожалуйста, введите число.", reply_markup=create_keyboard())
        except Exception as e:
            bot.reply_to(message, f"Ошибка: {e}", reply_markup=create_keyboard())

    @bot.message_handler(func=lambda message: message.text == "График")
    def handle_graph_stats_button(message):
        global otobr
        markup = create_period_keyboard()
        otobr = "graph"
        bot.send_message(message.chat.id, "Выберите период для просмотра статистики.", reply_markup=markup)

    @bot.message_handler(func=lambda message: message.text == "Текст")
    def handle_text_stats_button(message):
        global otobr
        markup = create_period_keyboard()
        otobr = "text"
        bot.send_message(message.chat.id, "Выберите период для просмотра статистики.", reply_markup=markup)

    @bot.message_handler(func=lambda message: message.text == "Месяц", )
    def handle_month_stats_graph(message):
        global otobr
        bot.send_message(message.chat.id,
                         "Отправьте ID пользователя Telegram, чтобы посмотреть его статистику за месяц.",
                         reply_markup=create_back_keyboard())
        bot.register_next_step_handler(message, lambda msg: handle_stats(msg, period='month', mode=otobr,
                                                                         tracker_id=message.from_user.id))

    @bot.message_handler(func=lambda message: message.text == "День", )
    def handle_day_stats_graph(message):
        global otobr
        bot.send_message(message.chat.id,
                         "Отправьте ID пользователя Telegram и дату (формат: YYYY-MM-DD), чтобы посмотреть его статистику за этот день. (Пример: @user123 2024-12-20)",
                         reply_markup=create_back_keyboard())
        bot.register_next_step_handler(message, lambda msg: handle_stats(msg, period='day', mode=otobr,
                                                                         tracker_id=message.from_user.id))

    @bot.message_handler(func=lambda message: message.text == "Час", )
    def handle_hour_stats_graph(message):
        global otobr
        bot.send_message(message.chat.id,
                         "Отправьте ID пользователя Telegram и час (формат: HH), чтобы посмотреть его статистику за этот час. (Пример: @user123 14)",
                         reply_markup=create_back_keyboard())
        bot.register_next_step_handler(message, lambda msg: handle_stats(msg, period='hour', mode=otobr,
                                                                         tracker_id=message.from_user.id))

    def handle_stats(message, period, mode, tracker_id):
        if message.text == "Назад":
            back_button_handler(message)
            return
        try:
            user_id = message.text.split(' ')[0] if period != 'month' else message.text
            with open('id.json', 'r') as f:
                data = json.load(f)
                if str(tracker_id) not in data.get("trackers", {}):
                    bot.reply_to(message, "У вас нет отслеживаемых пользователей.", reply_markup=create_keyboard())
                    return
                if str(user_id) not in data["trackers"][str(tracker_id)].get("users", {}):
                    bot.reply_to(message, "Пользователь не отслеживается.", reply_markup=create_keyboard())
                    return
                user_data = data["trackers"][str(tracker_id)]["users"].get(str(user_id), [])
                if mode == "graph":
                    if period == 'month':
                        end_date = datetime.datetime.now()
                        start_date = end_date - datetime.timedelta(days=30)

                        daily_online_times = np.zeros(30)
                        days = [start_date + datetime.timedelta(days=i) for i in range(30)]
                        if user_data:
                            for i in range(30):
                                current_day = start_date + datetime.timedelta(days=i)
                                start_of_day = current_day.replace(hour=0, minute=0, second=0, microsecond=0)
                                end_of_day = current_day.replace(hour=23, minute=59, second=59, microsecond=999999)
                                total_online_seconds = 0

                                for j in range(len(user_data)):
                                    if j + 1 < len(user_data):
                                        entry_time_str = user_data[j]["time"]
                                        next_entry_time_str = user_data[j + 1]["time"]

                                        entry_time = datetime.datetime.strptime(entry_time_str, "%Y-%m-%d %H:%M:%S")
                                        next_entry_time = datetime.datetime.strptime(next_entry_time_str,
                                                                                     "%Y-%m-%d %H:%M:%S")

                                    else:
                                        entry_time_str = user_data[j]["time"]
                                        entry_time = datetime.datetime.strptime(entry_time_str, "%Y-%m-%d %H:%M:%S")
                                        next_entry_time = end_date

                                    if entry_time < end_of_day and entry_time >= start_of_day:
                                        if user_data[j]["online"] == 1:
                                            online_start = max(entry_time, start_of_day)
                                            online_end = min(next_entry_time, end_of_day)
                                            total_online_seconds += (online_end - online_start).total_seconds()
                                daily_online_times[i] = total_online_seconds / 3600

                        fig, ax = plt.subplots(figsize=(15, 5))
                        ax.bar(days, daily_online_times, width=0.8, align='edge')
                        ax.set_xlabel("Дата")
                        ax.set_ylabel("Время онлайн (часы)")
                        ax.set_title(f"Активность пользователя {user_id} за последние 30 дней")
                        ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
                        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                        fig.autofmt_xdate()

                    elif period == 'day':
                        date_str = message.text.split(' ')[1]
                        date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
                        end_of_day = date.replace(hour=23, minute=59, second=59, microsecond=999999)

                        hourly_online_times = np.zeros(24)

                        if user_data:
                            for i in range(24):
                                start_time = start_of_day + datetime.timedelta(hours=i)
                                end_time = start_of_day + datetime.timedelta(hours=i + 1)
                                for j in range(len(user_data)):
                                    if j + 1 < len(user_data):
                                        entry_time_str = user_data[j]["time"]
                                        next_entry_time_str = user_data[j + 1]["time"]

                                        entry_time = datetime.datetime.strptime(entry_time_str, "%Y-%m-%d %H:%M:%S")
                                        next_entry_time = datetime.datetime.strptime(next_entry_time_str,
                                                                                     "%Y-%m-%d %H:%M:%S")
                                    else:
                                        entry_time_str = user_data[j]["time"]
                                        entry_time = datetime.datetime.strptime(entry_time_str, "%Y-%m-%d %H:%M:%S")
                                        next_entry_time = end_of_day

                                    if entry_time < end_time and entry_time >= start_time:
                                        if user_data[j]["online"] == 1:
                                            if next_entry_time <= end_time:
                                                online_duration = (next_entry_time - entry_time).total_seconds() / 60
                                                hourly_online_times[i] += online_duration
                                            else:
                                                online_duration = (end_time - entry_time).total_seconds() / 60
                                                hourly_online_times[i] += online_duration

                        fig, ax = plt.subplots(figsize=(10, 5))
                        hours = [start_of_day + datetime.timedelta(hours=i) for i in range(24)]
                        ax.bar(hours, hourly_online_times, width=0.04, align='edge')
                        ax.set_xlabel("Время")
                        ax.set_ylabel("Время онлайн (минуты)")
                        ax.set_title(f"Активность пользователя {user_id} за {date.strftime('%Y-%m-%d')}")
                        ax.xaxis.set_major_locator(mdates.HourLocator(interval=3))
                        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                        fig.autofmt_xdate()

                    elif period == 'hour':
                        hour_str = message.text.split(' ')[1]
                        hour = int(hour_str)
                        now = datetime.datetime.now()
                        start_of_hour = now.replace(hour=hour, minute=0, second=0, microsecond=0)
                        end_of_hour = now.replace(hour=hour, minute=59, second=59, microsecond=999999)

                        num_intervals = 12
                        hourly_online_times = np.zeros(num_intervals)

                        if user_data:
                            for i in range(num_intervals):
                                start_time = start_of_hour + datetime.timedelta(minutes=i * 5)
                                end_time = start_of_hour + datetime.timedelta(minutes=(i + 1) * 5)
                                for j in range(len(user_data)):
                                    if j + 1 < len(user_data):
                                        entry_time_str = user_data[j]["time"]
                                        next_entry_time_str = user_data[j + 1]["time"]

                                        entry_time = datetime.datetime.strptime(entry_time_str, "%Y-%m-%d %H:%M:%S")
                                        next_entry_time = datetime.datetime.strptime(next_entry_time_str,
                                                                                     "%Y-%m-%d %H:%M:%S")
                                    else:
                                        entry_time_str = user_data[j]["time"]
                                        entry_time = datetime.datetime.strptime(entry_time_str, "%Y-%m-%d %H:%M:%S")
                                        next_entry_time = end_of_hour

                                    if entry_time < end_time and entry_time >= start_time:
                                        if user_data[j]["online"] == 1:
                                            if next_entry_time <= end_time:
                                                online_duration = (next_entry_time - entry_time).total_seconds() / 60
                                                hourly_online_times[i] += online_duration
                                            else:
                                                online_duration = (end_time - entry_time).total_seconds() / 60
                                                hourly_online_times[i] += online_duration

                        fig, ax = plt.subplots(figsize=(10, 5))
                        intervals = [start_of_hour + datetime.timedelta(minutes=i * 5) for i in range(num_intervals)]
                        ax.bar(intervals, hourly_online_times, width=0.004, align='edge')
                        ax.set_xlabel("Время")
                        ax.set_ylabel("Время онлайн (минуты)")
                        ax.set_title(f"Активность пользователя {user_id} за {hour} час")
                        ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=10))
                        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                        fig.autofmt_xdate()

                    buf = BytesIO()
                    plt.savefig(buf, format='png')
                    buf.seek(0)
                    plt.close()
                    bot.send_photo(message.chat.id, photo=buf, reply_markup=create_keyboard())
                elif mode == "text":
                    text_stats = f"Статистика для пользователя {user_id}:\n"
                    if period == 'month':
                        end_date = datetime.datetime.now()
                        start_date = end_date - datetime.timedelta(days=30)

                        if user_data:
                            for entry in user_data:
                                entry_time = datetime.datetime.strptime(entry["time"], "%Y-%m-%d %H:%M:%S")
                                if start_date <= entry_time <= end_date:
                                    status = "онлайн" if entry["online"] == 1 else "оффлайн"
                                    text_stats += f"- {entry['time']}: {status}\n"
                    elif period == 'day':
                        date_str = message.text.split(' ')[1]
                        date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
                        end_of_day = date.replace(hour=23, minute=59, second=59, microsecond=999999)
                        if user_data:
                            for entry in user_data:
                                entry_time = datetime.datetime.strptime(entry["time"], "%Y-%m-%d %H:%M:%S")
                                if start_of_day <= entry_time <= end_of_day:
                                    status = "онлайн" if entry["online"] == 1 else "оффлайн"
                                    text_stats += f"- {entry['time']}: {status}\n"
                    elif period == 'hour':
                        hour_str = message.text.split(' ')[1]
                        hour = int(hour_str)
                        now = datetime.datetime.now()
                        start_of_hour = now.replace(hour=hour, minute=0, second=0, microsecond=0)
                        end_of_hour = now.replace(hour=hour, minute=59, second=59, microsecond=999999)
                        if user_data:
                            for entry in user_data:
                                entry_time = datetime.datetime.strptime(entry["time"], "%Y-%m-%d %H:%M:%S")
                                if start_of_hour <= entry_time <= end_of_hour:
                                    status = "онлайн" if entry["online"] == 1 else "оффлайн"
                                    text_stats += f"- {entry['time']}: {status}\n"
                    if len(text_stats) > 4096:
                        bot.send_message(message.chat.id,
                                         f"сообщение слишком длинное, отправлю часть. Воспользуйтесь статистикой за час.")
                        text_stats = text_stats[:4095]
                    bot.send_message(message.chat.id, text_stats, reply_markup=create_keyboard())
        except ValueError:
            bot.reply_to(message, "Неверный формат ID, даты или часа. Пожалуйста, проверьте введенные данные.",
                         reply_markup=create_keyboard())
        except Exception as e:
            bot.reply_to(message, f"Ошибка: {e}", reply_markup=create_keyboard())

    @bot.message_handler(commands=['stats'])
    def send_stats(message):
        with open('config1.json', 'r') as f:
            data = json.load(f)
            if not data.get("trackers", {}):
                bot.reply_to(message, "Нет данных для отображения.", reply_markup=create_keyboard())
                return
            for tracker_id, tracker_data in data['trackers'].items():
                for user_id, user_data in tracker_data.get('users', {}).items():
                    online_times = [entry["online"] for entry in user_data]
                    times = [entry["time"] for entry in user_data]
                    bot.reply_to(message, f"online_times: {online_times}", reply_markup=create_keyboard())

    bot.infinity_polling()


async def main():
    with open('config.json', 'r') as f:
        config = json.load(f)

    app_id = config['app_id']
    api_hash = config['api_hash']
    bot_token = config['bot_token']
    try:
        # Запуск внутреннего бота в отдельном потоке
        internal_bot_thread = threading.Thread(
            target=lambda: asyncio.run(run_internal_bot(app_id, api_hash, bot_token)))
        internal_bot_thread.start()
    except:
        print("не запустилчя internal_bot_thread")
    # Запуск внешнего бота
    run_external_bot(bot_token)


asyncio.run(main())
current_datetime = datetime.datetime.now()
formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
print(formatted_datetime)
