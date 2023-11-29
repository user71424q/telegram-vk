"""
Этот модуль предназначен для запуска бота, который прослушивает сообщения как с платформы Telegram, так и VK (ВКонтакте).
Он инициализирует бота, настраивает необходимое окружение и запускает потоки прослушивания для Telegram и VK.

Функции:
- В этом модуле не определены публичные функции.

Использование:
- Установите необходимые переменные окружения для токенов и ID Telegram и VK.
- Запустите этот модуль для запуска бота.
"""

import logging
import os
import threading
import time
from dotenv import load_dotenv

from tgvk import listen_telegram
from vktg import listen_vk

load_dotenv()
# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger().setLevel(logging.WARNING)
required_values = [
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "VK_GROUP_TOKEN",
    "VK_GROUP_ID",
    "VK_CHAT_ID",
]
missing_values = [value for value in required_values if os.environ.get(value) is None]
if len(missing_values) > 0:
    logging.error(
        f'The following environment values are missing in your .env: {", ".join(missing_values)}'
    )
    exit(1)

VK_GROUP_TOKEN = os.environ.get("VK_GROUP_TOKEN")
VK_GROUP_ID = int(os.environ.get("VK_GROUP_ID"))
VK_CHAT_ID = int(os.environ.get("VK_CHAT_ID"))
TG_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TG_CHAT_ID = int(os.environ.get("TELEGRAM_CHAT_ID"))
# BOT_LANGUAGE = os.environ.get("BOT_LANG", "ru")
TG_TO_VK = os.environ.get("TG_TO_VK", "True") == "True"
VK_TO_TG = os.environ.get("VK_TO_TG", "True") == "True"


if __name__ == "__main__":
    # print("BOT started")
    # Запуск потоков
    if VK_TO_TG:
        thread_vk = threading.Thread(
            target=listen_vk,
            args=(VK_GROUP_TOKEN, VK_GROUP_ID, VK_CHAT_ID, TG_TOKEN, TG_CHAT_ID),
        )
        thread_vk.start()
    if TG_TO_VK:
        thread_telegram = threading.Thread(
            target=listen_telegram,
            args=(TG_TOKEN, TG_CHAT_ID, VK_GROUP_TOKEN, VK_CHAT_ID),
        )
        thread_telegram.start()

    while True:
        time.sleep(1)  # Бесконечный цикл с паузой, чтобы не загружать процессор
