"""
Этот модуль отвечает за прослушивание сообщений в VK (ВКонтакте) и их пересылку в Telegram.
Он устанавливает соединения с API VK и Telegram и управляет процессом пересылки сообщений из VK в Telegram.

Функции:
- listen_vk(vk_token, vk_group_id, VK_CHAT_ID, tg_token, TG_CHAT_ID):
  Прослушивает сообщения в указанном чате VK и пересылает их в чат Telegram. Требует токены API и ID группы/чата для обеих платформ.

Использование:
- Укажите необходимые токены API, ID группы/чата для VK и Telegram.
- Вызовите функцию listen_vk для начала процесса прослушивания и пересылки.
"""

import io
import logging
import requests
import telebot
import vk_api
from vk_api.bot_longpoll import VkBotEventType, VkBotLongPoll
from telebot.apihelper import ApiException
from vk_api import VkApiError
import urllib3
import time
from http.client import RemoteDisconnected
from requests.exceptions import ConnectionError, Timeout

def listen_vk(vk_token: str, vk_group_id: int, VK_CHAT_ID: int, tg_token: str, TG_CHAT_ID: int) -> None:
    """
    Прослушивает сообщения в VK и пересылает их в Telegram.

    Параметры:
        vk_token (str): Токен для VK.
        vk_group_id (int): ID группы VK.
        VK_CHAT_ID (int): ID чата VK.
        tg_token (str): Токен бота Telegram.
        TG_CHAT_ID (int): ID чата Telegram.

    Возвращает:
        None
    """
    try:
        telegram_bot = telebot.TeleBot(tg_token, parse_mode=None)
        vk_session = vk_api.VkApi(token=vk_token)
        longpoll = VkBotLongPoll(vk_session, vk_group_id)
    except VkApiError as vk_api_error:
        logging.error(
            f"Невозможно доставить сообщение об ошибке пользователю. Тип ошибки: {type(vk_api_error)}, Описание: {vk_api_error}"
        )
        exit(1)
    retries = 0
    while retries < 10:
        try:
            for event in longpoll.listen():
                try:
                    # если есть новые сообщения
                    if (
                        event.type == VkBotEventType.MESSAGE_NEW
                        and event.object.message["peer_id"] == VK_CHAT_ID
                    ):
                        send_to_tg(event.message, vk_session, telegram_bot, TG_CHAT_ID)
                except VkApiError as vk_api_error:
                    try:
                        telegram_bot.send_message(TG_CHAT_ID, f"ERROR: {vk_api_error}")
                    except Exception as e:
                        logging.error(
                            f"Невозможно доставить сообщение об ошибке пользователю. Тип ошибки: {type(vk_api_error)}, Описание: {vk_api_error}"
                        )
                except ApiException as tg_api_exception:
                    try:
                        telegram_bot.send_message(TG_CHAT_ID, f"ERROR: {tg_api_exception}")
                    except Exception as e:
                        logging.error(
                            f"Невозможно доставить сообщение об ошибке пользователю. Тип ошибки: {type(tg_api_exception)}, Описание: {tg_api_exception}"
                        )
                except Exception as e:
                    logging.error(f"Непредвиденная ошибка: {e}, {type(e)}")
                    exit(1)
        except (urllib3.exceptions.ProtocolError, RemoteDisconnected, ConnectionError, Timeout):
            logging.warning("Проблемы сетью, попытка повторного подключения....")
            time.sleep(30)
            retries += 1


def send_to_tg(message, vk_session: vk_api.VkApi, telegram_bot: telebot.TeleBot, TG_CHAT_ID: int) -> None:
    """
    Отправляет сообщение вк в телеграм.

    Параметры:
        message: Объект сообщения.
        vk_session (vk_api.VkApi): Объект сессии.
        telegram_bot (telebot.TeleBot): Объект телеграм бота.
        TG_CHAT_ID (int): ID чата Telegram.

    Возвращает:
        None
    """
    # TODO обработка видео и аудио

    text_to_send = get_forward_tree(message, 0, vk_session)
    telegram_bot.send_message(chat_id=TG_CHAT_ID, text=text_to_send)
    media_dict = {}
    get_all_attachments(message, media_dict)
    if media_dict:
        for media_key in media_dict:
            telegram_bot.send_media_group(
                chat_id=TG_CHAT_ID, media=media_dict[media_key]
            )


def get_username(vk_session: vk_api.VkApi, id=0) -> str:
    """
    Отправляет сообщение вк в телеграм.
    
    Параметры:
        vk_session (vk_api.VkApi): Объект сессии.
        id (int): id пользователя или группы.

    Возвращает:
        Фамилия Имя (str) 
    """
    api = vk_session.get_api()
    if id > 0:
        user_get = api.users.get(user_ids=id)[0]
        name = str(user_get["first_name"]) + " " + str(user_get["last_name"])
    elif id < 0:
        group_get = api.groups.get_by_id(group_id=abs(id))
        name = group_get[0]["name"]
    else:
        name = api.groups.get_by_id()[0]["name"]
    return name


def get_forward_tree(message, depth: int, vk_session: vk_api.VkApi) -> str:
    """
    Функция возвращает дерево вложенных сообщений в текстовом формате

    Параметры:
        message: Объект сообщения.
        depth (int): Текущая глубина рекурсии.
        vk_session (vk_api.VkApi): Объект сессии.

    Пример:
    Я пересылаю сообщение
    |А это пересланое сообщение
    ||Более глубокая вложенность

    Возвращает:
        str
    """
    # date_str = datetime.fromtimestamp(message["date"]).strftime("%d %b %Y")
    # time_str = datetime.fromtimestamp(message["date"]).strftime("%H:%M:%S")
    username = get_username(vk_session, message["from_id"])
    author = (
        "|" * depth
        + (f"{username}: " if username != get_username(vk_session) else "")
        # + " "
        # + localized_text("fwd_written_at", BOT_LANGUAGE)[0]
        # + " "
        # + date_str
        # + " "
        # + localized_text("fwd_written_at", BOT_LANGUAGE)[1]
        # + " "
        # + time_str
    )
    tree = author
    if message["text"]:
        tree += message["text"] + "\n"
    if message["attachments"]:
        tree += f'<{len(message["attachments"])} вложений>' + "\n"
    for forwarded in message.get("fwd_messages", []):
        tree += get_forward_tree(forwarded, depth + 1, vk_session)
    if message.get("reply_message"):
        tree += get_forward_tree(message["reply_message"], depth + 1, vk_session)
    return tree


def get_all_attachments(message, attachments_dict: dict) -> None:
    """
    Функция получает фото, видео и стикеры из всех вложенных сообщений, они динамически добавляются в attachments_array

    Параметры:
        message: Объект сообщения.
        attachments_dict (dict): Словарь, в который будут добавлены вложения.
    Возвращает:
        None
    """
    if message["attachments"]:
        for attachment in message["attachments"]:
            if attachment["type"] == "photo":
                image_url = attachment["photo"]["sizes"][-1]["url"]
                attachments_dict.setdefault("photo", []).append(
                    telebot.types.InputMediaPhoto(media=image_url)
                )
            if attachment["type"] == "doc":
                doc_info = attachment["doc"]
                doc_url = doc_info["url"]
                response = requests.get(doc_url)
                file_data = io.BytesIO(response.content)
                file_data.name = doc_info["title"]
                attachments_dict.setdefault("doc", []).append(
                    telebot.types.InputMediaDocument(media=file_data)
                )
            if attachment["type"] == "sticker":
                sticker_url = attachment["sticker"]["images"][-1]["url"]
                attachments_dict.setdefault("sticker", []).append(
                    telebot.types.InputMediaPhoto(media=sticker_url)
                )

    for forwarded in message.get("fwd_messages", []):
        get_all_attachments(forwarded, attachments_dict)
    if message.get("reply_message"):
        get_all_attachments(message["reply_message"], attachments_dict)
