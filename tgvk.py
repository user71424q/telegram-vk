"""
Этот модуль содержит функционал для прослушивания сообщений в Telegram и их пересылки в VK (ВКонтакте).
Он настраивает соединения с API Telegram и VK и управляет процессом пересылки сообщений.

Функции:
- listen_telegram(tg_token, chat_id, vk_token, vk_chat_id):
  Прослушивает сообщения в указанном чате Telegram и пересылает их в чат VK. Требует токены API и ID чатов обеих платформ.

Использование:
- Укажите необходимые токены API и ID чатов для Telegram и VK.
- Вызовите функцию listen_telegram для начала прослушивания и пересылки сообщений.
"""

import io
import os
from vk_api import VkApiError
import telebot
import vk_api
from vk_api.utils import get_random_id
import logging
from telebot.apihelper import ApiException
import urllib3
import time
from http.client import RemoteDisconnected
from requests.exceptions import ConnectionError, Timeout

def listen_telegram(tg_token: str, chat_id: int, vk_token: str, vk_chat_id: int) -> None:
    """
    Прослушивает сообщения в Telegram и пересылает их в VK.

    Параметры:
        tg_token (str): Токен бота Telegram.
        chat_id (int): ID чата Telegram.
        vk_token (str): Токен для VK.
        vk_chat_id (int): ID чата VK.

    Возвращает:
        None
    """
    try:
        bot = telebot.TeleBot(tg_token, parse_mode=None)
        vk_session = vk_api.VkApi(token=vk_token)
    except VkApiError as vk_api_error:
        logging.error(
            f"Невозможно доставить сообщение об ошибке пользователю. Тип ошибки: {type(vk_api_error)}, Описание: {vk_api_error}"
        )
        exit(1)

    @bot.message_handler(
        func=lambda message: message.chat.type == "group"
        and message.chat.id == chat_id,
        content_types=["text", "photo", "audio", "video", "document", "sticker"],
    )
    def handle_message(message):
        try:
            vk_message = process_telegram_message(bot, message)
            send_vk_message(vk_session, vk_message, vk_chat_id)
        except VkApiError as vk_api_error:
            try:
                send_vk_message(
                    vk_session, {"text": f"ERROR: {vk_api_error}"}, vk_chat_id
                )
            except Exception as e:
                logging.error(
                    f"Невозможно доставить сообщение об ошибке пользователю. Тип ошибки: {type(vk_api_error)}, Описание: {vk_api_error}"
                )
        except ApiException as tg_api_exception:
            try:
                send_vk_message(
                    vk_session, {"text": f"ERROR: {tg_api_exception}"}, vk_chat_id
                )
            except Exception as e:
                logging.error(
                    f"Невозможно доставить сообщение об ошибке пользователю. Тип ошибки: {type(tg_api_exception)}, Описание: {tg_api_exception}"
                )
        except Exception as e:
            logging.error(f"Непредвиденная ошибка: {e}")
    retries = 0
    while retries < 10:
        try:
            bot.polling(non_stop=True, skip_pending=True)
        except ApiException as tg_api_exception:
            try:
                send_vk_message(
                    vk_session, {"text": f"ERROR: {tg_api_exception}"}, vk_chat_id
                )
            except Exception as e:
                logging.error(
                    f"Невозможно доставить сообщение об ошибке пользователю. Тип ошибки: {type(tg_api_exception)}, Описание: {tg_api_exception}"
                )
        except (urllib3.exceptions.ProtocolError, RemoteDisconnected, ConnectionError, Timeout):
            logging.warning("Проблемы сетью, попытка повторного подключения....")
            time.sleep(30)
            retries += 1
        except Exception as e:
            logging.error(f"Непредвиденная ошибка: {e}")


def process_telegram_message(bot: telebot.TeleBot, message) -> dict:
    """
    Преобразует объект сообщения телеграма в формат для ВК

    Параметры:
        bot (telebot.TeleBot): Объект бота Telegram.
        message: Объект сообщения телеграм.

    Возвращает:
        dict - словарь, подобный вк сообщению во структуре
    """
    vk_message = {}

    # Функция для обработки фотографий
    def handle_photo(photo):
        file_info = bot.get_file(photo.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        return io.BytesIO(downloaded_file)

    # Функция для обработки документов
    def handle_document(document):
        file_info = bot.get_file(document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        local_file_path = f"./{document.file_name}"
        with open(local_file_path, "wb") as file:
            file.write(downloaded_file)
        return local_file_path

    # Функция для создания текста ответа
    def create_reply_text(reply_message):
        reply_author_tag = (
            (
                reply_message.from_user.first_name
                if reply_message.from_user.first_name
                else f"@{reply_message.from_user.username}"
            )
            if not reply_message.json["from"]["is_bot"]
            else ""
        )
        reply_text = f"{reply_author_tag}{':' if reply_author_tag != '' else ''} "
        if reply_message.content_type in ["photo", "document"]:
            content_type = (
                "Фотография" if reply_message.content_type == "photo" else "Документ"
            )
            reply_text += f"[{content_type}]" + (
                " " + reply_message.caption if reply_message.caption else ""
            )
        else:
            reply_text += reply_message.text if reply_message.text else "[Без текста]"

        return reply_text

    author_tag = (
        message.from_user.first_name
        if message.from_user.first_name
        else f"@{message.from_user.username}"
    )
    # Обработка текстовых сообщений
    if message.content_type == "text":
        text = f"{author_tag}: {message.text}"

        # Если это пересланное сообщение
        if message.forward_from:
            forward_author_tag = (
                (
                    message.forward_from.first_name
                    if message.forward_from.first_name
                    else f"@{message.forward_from.username}"
                )
                if not message.json["forward_from"]["is_bot"]
                else ""
            )
            forward_text = f"{author_tag}: [Пересланное сообщение]"
            text = f"{forward_text}\n|{forward_author_tag}{':' if forward_author_tag != '' else ''} {message.text}"

        # Если это ответ
        if message.reply_to_message:
            reply_text = create_reply_text(message.reply_to_message)
            text = f"{text}\n|{reply_text}"
            # Если ответ на фотографию или документ
            if message.reply_to_message.content_type in ["photo", "document"]:
                reply_content_key = (
                    "reply_photo"
                    if message.reply_to_message.content_type == "photo"
                    else "reply_document"
                )
                handle_reply_content = (
                    handle_photo
                    if message.reply_to_message.content_type == "photo"
                    else handle_document
                )
                reply_content = (
                    message.reply_to_message.photo[-1]
                    if message.reply_to_message.content_type == "photo"
                    else message.reply_to_message.document
                )
                vk_message[reply_content_key] = handle_reply_content(reply_content)

        vk_message["text"] = text

    # Обработка фотографий и документов
    if message.content_type in ["photo", "document"]:
        content_key = "photo" if message.content_type == "photo" else "document"
        handle_content = (
            handle_photo if message.content_type == "photo" else handle_document
        )
        vk_message[content_key] = handle_content(
            message.photo[-1] if message.content_type == "photo" else message.document
        )

        # Добавляем текст, если это ответ на сообщение
        if message.reply_to_message:
            reply_text = create_reply_text(message.reply_to_message)
            vk_message[
                "text"
            ] = f"{author_tag}: {message.caption if message.caption else ''}\n[В ответ на: {reply_text}]"

            # Если ответ на фотографию или документ
            if message.reply_to_message.content_type in ["photo", "document"]:
                reply_content_key = (
                    "reply_photo"
                    if message.reply_to_message.content_type == "photo"
                    else "reply_document"
                )
                handle_reply_content = (
                    handle_photo
                    if message.reply_to_message.content_type == "photo"
                    else handle_document
                )
                reply_content = (
                    message.reply_to_message.photo[-1]
                    if message.reply_to_message.content_type == "photo"
                    else message.reply_to_message.document
                )
                vk_message[reply_content_key] = handle_reply_content(reply_content)
            # Если это пересланное сообщение
        if message.forward_from:
            forward_author_tag = (
                message.forward_from.first_name
                if message.forward_from.first_name
                else f"@{message.forward_from.username}"
            )
            forward_text = f"{author_tag}: [Пересланное сообщение]"
            vk_message[
                "text"
            ] = f"{forward_text}\n|{forward_author_tag}: {message.caption if message.caption else ''}"

    return vk_message


def send_vk_message(vk_session: vk_api.VkApi, vk_message: dict, chat_id: int) -> None:
    """
    Отправляет сообщение вк в нужный чат.

    Параметры:
        vk_session (vk_api.VkApi): Объект сессии.
        vk_message (dict): Словарь с полями текста и вложений сообщения вк.
        chat_id (int): ID чата VK.

    Возвращает:
        None
    """
    vk = vk_session.get_api()

    # Отправка текстового сообщения
    if "text" in vk_message:
        vk.messages.send(
            peer_id=chat_id, message=vk_message["text"], random_id=get_random_id()
        )

    # Функция для отправки фотографий
    def send_photo(photo):
        upload = vk_api.VkUpload(vk_session)
        photo_info = upload.photo_messages(photos=photo)[0]
        vk.messages.send(
            peer_id=chat_id,
            attachment=f"photo{photo_info['owner_id']}_{photo_info['id']}",
            random_id=get_random_id(),
        )

    # Функция для отправки документов
    def send_document(doc_path):
        upload = vk_api.VkUpload(vk_session)
        doc_info = upload.document_message(
            doc=doc_path, title=os.path.basename(doc_path), peer_id=chat_id
        )
        vk.messages.send(
            peer_id=chat_id,
            attachment=f"doc{doc_info['doc']['owner_id']}_{doc_info['doc']['id']}",
            random_id=get_random_id(),
        )
        os.remove(doc_path)  # Удаление локального файла после отправки

    # Отправка ответа в виде фотографии
    if "reply_photo" in vk_message:
        send_photo(vk_message["reply_photo"])

    # Отправка ответа в виде документа
    if "reply_document" in vk_message:
        send_document(vk_message["reply_document"])

    # Отправка фотографии
    if "photo" in vk_message:
        send_photo(vk_message["photo"])

    # Отправка документа
    if "document" in vk_message:
        send_document(vk_message["document"])
