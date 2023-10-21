import logging
from telegram import ForceReply, Update
from telegram.ext import Application, Updater, CommandHandler, MessageHandler, filters
from config import API_TOKEN
from handlers import start, process_video

def main():
    logging.basicConfig(level=logging.INFO)

    dp = Application.builder().token(API_TOKEN).build()

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(filters.VIDEO, process_video))

    dp.run_polling(allowed_updates=Update.ALL_TYPES, stop_signals=None)

if __name__ == "__main__":
    main()
