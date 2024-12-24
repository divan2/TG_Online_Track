import json
import datetime
import asyncio
import os
from random import sample

import matplotlib

matplotlib.use('Agg')  # Добавляем эту строку
import matplotlib.pyplot as plt
from io import BytesIO
import base64
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
            if str(user_id) not in data["users"]:
                data["users"][str(user_id)] = []

            if data["users"][str(user_id)] != []:
                if data["users"][str(user_id)][-1]["online"] != is_online:
                    if is_online == 0:
                        time = str(user.last_online_date)
                        data["users"][str(user_id)].append({"time": time, "online": is_online})

                    else:
                        current_datetime = datetime.datetime.now()
                        time = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
                        data["users"][str(user_id)].append({"time": time, "online": is_online})
            else:
                current_datetime = datetime.datetime.now()
                time = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
                data["users"][str(user_id)].append({"time": time, "online": is_online})
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
            for user_id in user_data["users"]:
                tasks.append(check_user_online(app, user_id, 'id.json'))
                tasks.append(asyncio.sleep(5))  # Задержка 5 секунд для каждого пользователя

            if tasks:
                await asyncio.gather(*tasks)


def run_external_bot(bot_token):
    # Внешний бот(telebot)
    print("Внешний работает", bot_token)
    bot = telebot.TeleBot(bot_token)

    @bot.message_handler(commands=['start'])
    def start_message(message):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        btn_add_user = types.KeyboardButton("Добавить пользователя")
        btn_check_online = types.KeyboardButton("Посмотреть онлайн")
        markup.add(btn_add_user, btn_check_online)
        bot.send_message(message.chat.id,
                         "Привет! Нажмите кнопку, чтобы добавить пользователя для отслеживания или посмотреть его онлайн-статус.",
                         reply_markup=markup)

    @bot.message_handler(func=lambda message: message.text == "Добавить пользователя")
    def add_user_button_handler(message):
        bot.send_message(message.chat.id, "Отправьте ID пользователя Telegram для отслеживания.")
        bot.register_next_step_handler(message, handle_add_user)

    def handle_add_user(message):
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

            # Если ключа 'users' нет, то создаем его

            if "users" not in data:
                data["users"] = {}

            if user_id in data["users"]:
                bot.reply_to(message, f"Пользователь уже отслеживается {user_id}")
            else:
                bot.reply_to(message, f"Начал отслеживать пользователя {user_id}")
            # Если такого пользователя нет, то создаем для него новый ключ-список
            if str(user_id) not in data["users"]:
                data["users"][str(user_id)] = []

            # Записываем обновленные данные в файл
            with open('id.json', 'w') as f:
                json.dump(data, f, indent=4)
                bot.reply_to(message, f"Начал отслеживать пользователя {user_id}")
        except ValueError:
            bot.reply_to(message, "Неверный формат ID.  Пожалуйста, введите число.")
        except Exception as e:
            bot.reply_to(message, f"Ошибка: {e}")

    @bot.message_handler(func=lambda message: message.text == "Посмотреть онлайн")
    def check_online_button_handler(message):
        bot.send_message(message.chat.id, "Отправьте ID пользователя Telegram, чтобы посмотреть его статистику.")
        bot.register_next_step_handler(message, handle_check_online)

    def handle_check_online(message):
        try:
            user_id = message.text
            with open('id.json', 'r') as f:
                data = json.load(f)
                if str(user_id) not in data["users"]:
                    bot.reply_to(message, "Пользователь не отслеживается.")
                    return
                user_data = data["users"].get(str(user_id), [])

                now = datetime.datetime.now()
                hours_24_ago = now - datetime.timedelta(hours=24)

                hourly_online_times = np.zeros(24)
                if user_data:
                    for i in range(24):
                        start_time = hours_24_ago + datetime.timedelta(hours=i)
                        end_time = hours_24_ago + datetime.timedelta(hours=i + 1)

                        for j in range(len(user_data)):
                            if j + 1 < len(user_data):
                                entry_time_str = user_data[j]["time"]
                                next_entry_time_str = user_data[j + 1]["time"]

                                entry_time = datetime.datetime.strptime(entry_time_str, "%Y-%m-%d %H:%M:%S")
                                next_entry_time = datetime.datetime.strptime(next_entry_time_str, "%Y-%m-%d %H:%M:%S")
                            else:
                                entry_time_str = user_data[j]["time"]
                                entry_time = datetime.datetime.strptime(entry_time_str, "%Y-%m-%d %H:%M:%S")
                                next_entry_time = datetime.datetime.now()

                            if entry_time < end_time and entry_time >= start_time:
                                if user_data[j]["online"] == 1:
                                    if next_entry_time <= end_time:
                                        online_duration = (next_entry_time - entry_time).total_seconds() / 3600
                                        hourly_online_times[i] += online_duration
                                    else:
                                        online_duration = (end_time - entry_time).total_seconds() / 3600
                                        hourly_online_times[i] += online_duration

                fig, ax = plt.subplots(figsize=(10, 5))

                hours = [hours_24_ago + datetime.timedelta(hours=i) for i in range(24)]

                ax.bar(hours, hourly_online_times, width=0.04, align='edge')

                ax.set_xlabel("Время")
                ax.set_ylabel("Время онлайн (часы)")
                ax.set_title(f"Активность пользователя {user_id} за последние 24 часа")
                ax.xaxis.set_major_locator(mdates.HourLocator(interval=3))
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                fig.autofmt_xdate()

                buf = BytesIO()
                plt.savefig(buf, format='png')
                buf.seek(0)
                plt.close()

                bot.send_photo(message.chat.id, photo=buf)
        except ValueError:
            bot.reply_to(message, "Неверный формат ID.  Пожалуйста, введите число.")
        except Exception as e:
            bot.reply_to(message, f"Ошибка: {e}")

    @bot.message_handler(commands=['stats'])
    def send_stats(message):
        with open('id.json', 'r') as f:
            data = json.load(f)
            if not data["users"]:
                bot.reply_to(message, "Нет данных для отображения.")
                return
            for user_id, user_data in data['users'].items():
                online_times = [entry["online"] for entry in user_data]
                times = [entry["time"] for entry in user_data]
                bot.reply_to(message, f"online_times: {online_times}")

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
