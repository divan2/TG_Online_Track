import json
import datetime
import asyncio
import os
from random import sample

import matplotlib.pyplot as plt
from io import BytesIO
import base64
import threading
import pyrogram
from pyrogram import Client
import telebot


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
        bot.reply_to(message,
                     "Привет! Отправь мне ID пользователя Telegram, чтобы начать отслеживать его онлайн-статус.")

    @bot.message_handler(func=lambda message: True)  # Обработчик для всех сообщений, не являющихся командами
    def handle_message(message):
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
                plt.plot(times, online_times)
                plt.xlabel("Время")
                plt.ylabel("Онлайн")
                plt.title(f"Статистика пользователя {user_id}")
                buf = BytesIO()
                plt.savefig(buf, format='png')
                buf.seek(0)
                plt.close()
                image_b64 = base64.b64encode(buf.read()).decode('utf-8')
                bot.send_photo(message.chat.id, f"data:image/png;base64,{image_b64}")

    bot.infinity_polling()


async def main():
    with open('config.json', 'r') as f:
        config = json.load(f)

    app_id = config['app_id']
    api_hash = config['api_hash']
    bot_token = config['bot_token']

    # Запуск внутреннего бота в отдельном потоке
    internal_bot_thread = threading.Thread(target=lambda: asyncio.run(run_internal_bot(app_id, api_hash, bot_token)))
    internal_bot_thread.start()

    # Запуск внешнего бота
    run_external_bot(bot_token)


asyncio.run(main())
current_datetime = datetime.datetime.now()
formatted_datetime = current_datetime.strftime("%Y-%m-%d %H:%M:%S")
print(formatted_datetime)
