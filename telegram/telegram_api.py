import telegram
import datetime

TELEGRAM_BOT_TOKEN = 'your_telegram_bot_token'
TELEGRAM_CHAT_ID = 'your_chat_id'

if __name__ == "__main__":
    telegram_bot = telegram.Bot(TELEGRAM_BOT_TOKEN)

    telegram_message_list_1 = [str(datetime.datetime.now()), 'Program Started!']
    telegram_bot.sendMessage(chat_id=TELEGRAM_CHAT_ID, text=' '.join(telegram_message_list_1))

    telegram_message_list_2 = [str(datetime.datetime.now()), '------ buy signal occured! -----------']
    telegram_bot.sendMessage(chat_id=TELEGRAM_CHAT_ID, text=' '.join(telegram_message_list_2))