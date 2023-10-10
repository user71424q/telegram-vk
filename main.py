import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
import telebot
import requests
import io
# токены
#TODO получение данных переменных из конфиг файла
vk_group_token = "5d1cd3d8fa732ab7937cbdb3d5180d0503d762dfa4c9c9c958633579e213bbdec3a4dc98caa92718fc80e"
vk_group_id = 212374607
vk_dialog_id = 2000000003
tg_token = "2093683385:AAGUNx1HIerU8PHMw_zURSl3K2Ev7r1tHn8"
tg_chat_id = -4005498383

# подключаемся к ВК
vk_session = vk_api.VkApi(token=vk_group_token)
longpoll = VkBotLongPoll(vk_session, vk_group_id)

# подключаемся к Телеграм
bot = telebot.TeleBot(token=tg_token)


def listen_vk():
    """ Функция для прослушивания ВК """
    for event in longpoll.listen():
        # если есть новые сообщения
        if event.type == VkBotEventType.MESSAGE_NEW and event.object.message['peer_id'] == vk_dialog_id:
            print(event.object.message)
            send_to_tg(event.message)


def send_to_tg(message):
    """ Функция для отправки сообщений в телеграм """
    #TODO обработка ошибок api, подпись автора сообщения и другой информации, обработка видео и аудио
    print('Sending to TG')
    if not message.attachments:
        bot.send_message(chat_id=tg_chat_id, text=str(message))
    else:
        media = []
        for attachment in message.attachments:
            if attachment['type'] == 'photo':
                image_url = attachment['photo']['sizes'][-1]['url']
                media.append(telebot.types.InputMediaPhoto(media=image_url))
            if attachment['type'] == 'doc':
                doc_info = attachment['doc']
                doc_url = doc_info['url']
                response = requests.get(doc_url)
                file_data = io.BytesIO(response.content)
                file_data.name = doc_info['title']
                media.append(telebot.types.InputMediaDocument(media=file_data))
        if message['text'] != '':
            bot.send_message(chat_id=tg_chat_id, text=message['text'])
        if media:
            bot.send_media_group(chat_id=tg_chat_id, media=media)


if __name__ == "__main__":
    print('BOT started')
    listen_vk()
