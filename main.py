# main.py
import logging
from telegram import Update
# Импортируем ParseMode и CallbackQueryHandler
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler,
    Defaults # Defaults все еще нужен для parse_mode
)
from config import API_TOKEN
from handlers import start, process_media, button_handler
import asyncio

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Обработчик ошибок
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Исключение при обработке обновления {update}:", exc_info=context.error)

def main():
    """Запускает бота."""
    logger.info("Запуск бота...")

    # --- Установка настроек по умолчанию (только parse_mode) ---
    bot_defaults = Defaults(
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    # --- Создание Application с таймаутами ---
    # Таймауты задаются через методы builder'а
    application = (
        Application.builder()
        .token(API_TOKEN)
        .defaults(bot_defaults)
        .read_timeout(30)  # Время ожидания ответа от сервера (секунды)
        .write_timeout(30) # Время ожидания при отправке данных (секунды)
        .connect_timeout(10)# Время ожидания установки соединения (секунды)
        # Можно также задать общий таймаут для пулинга, если нужно
        # .pool_timeout(10)
        .build()
    )

    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.VIDEO | filters.ANIMATION, process_media))
    application.add_handler(CallbackQueryHandler(button_handler))

    application.add_error_handler(error_handler)

    logger.info("Бот запущен и слушает обновления...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
