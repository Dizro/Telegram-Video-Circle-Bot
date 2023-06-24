import logging
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from config import API_TOKEN
from handlers import start, process_video

def main():
    logging.basicConfig(level=logging.INFO)

    updater = Updater(API_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.video, process_video))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
