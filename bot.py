import logging
from moviepy.editor import VideoFileClip
from telegram import Update, InputMediaVideo
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# Замените следующую строку на ваш токен API
API_TOKEN = "YOUR_API_TOKEN"

def start(update: Update, context: CallbackContext) -> None:
    """Отправляет приветственное сообщение и помощь при команде /start."""
    update.message.reply_text("Привет! Отправьте мне видео, и я преобразую его в видеокружок.")

def process_video(update: Update, context: CallbackContext) -> None:
    """Обрабатывает видео, преобразует его в видеокружок и отправляет обратно."""
    try:
        video_file = context.bot.getFile(update.message.video.file_id)
        video_file.download("input_video.mp4")

        # Преобразование видео в видеокружок
        input_video = VideoFileClip("input_video.mp4")
        w, h = input_video.size
        output_video = input_video.crop(x_center=w/2, y_center=h/2, width=min(w, h), height=min(w, h))
        output_video.write_videofile("output_video.mp4", codec="libx264", audio_codec="aac")

        # Отправка видеокружка в чат
        with open("output_video.mp4", "rb") as video:
            context.bot.send_video_note(chat_id=update.message.chat_id, video_note=video, duration=int(output_video.duration), length=min(w, h))
    except Exception as e:
        logging.error(f"Произошла ошибка при обработке видео: {e}")
        update.message.reply_text("Произошла ошибка при обработке вашего видео. Пожалуйста, попробуйте еще раз.")

def main() -> None:
    """Запускает бота."""
    logging.basicConfig(level=logging.INFO)

    updater = Updater(API_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.video, process_video))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
