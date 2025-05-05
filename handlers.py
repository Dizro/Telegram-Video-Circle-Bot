# handlers.py
import logging
import os
import re
from moviepy.editor import VideoFileClip
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import BadRequest, TimedOut
from telegram.ext import CallbackContext
from telegram.constants import ChatAction, ParseMode

# --- Константы ---
MAX_DURATION_SECONDS = 60  # Максимальная длительность кружка в секундах
MAX_FILE_SIZE_BYTES = 12 * 1024 * 1024 # Максимальный размер файла кружка (12 MB)
CIRCLE_SIZE = 360 # Размер стороны квадратного видеокружка
INPUT_FILENAME_TPL = "input_media_{}.tmp" # Шаблон имени входного файла
OUTPUT_FILENAME_TPL = "output_video_{}.mp4" # Шаблон имени выходного файла

# --- Вспомогательные функции ---
def get_temp_filenames(user_id: int) -> tuple[str, str]:
    """Генерирует уникальные временные имена файлов для пользователя."""
    return INPUT_FILENAME_TPL.format(user_id), OUTPUT_FILENAME_TPL.format(user_id)

def escape_markdown_v2(text: str) -> str:
    """Экранирует специальные символы MarkdownV2 для безопасной вставки текста."""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

async def cleanup_files(*filenames):
    """Безопасно удаляет указанные временные файлы."""
    for filename in filenames:
        if filename and os.path.exists(filename):
            try:
                os.remove(filename)
                logging.info(f"Временный файл {filename} удален.")
            except OSError as e:
                logging.error(f"Не удалось удалить временный файл {filename}: {e}")

# --- Обработчики Telegram ---
async def start(update: Update, context: CallbackContext):
    """Отправляет приветственное сообщение /start."""
    user = update.effective_user
    user_name = escape_markdown_v2(user.first_name) if user and user.first_name else "Пользователь"

    # Приветственное сообщение с форматированием MarkdownV2
    start_message = (
        f"Привет, {user_name}\\! 👋\n\n"
        "Я помогу тебе превратить обычное видео или GIF в классный Telegram\\-кружок\\.\n\n"
        "Просто отправь мне видеофайл или GIF\\-анимацию, и я сделаю магию\\! ✨\n\n"
        "📌 **Важные моменты:**\n"
        "▪️ **Длительность:** Видео/GIF должно быть не длиннее 60 секунд \\(если длиннее, я предложу обрезать\\)\\.\n"
        "▪️ **Звук:** Я спрошу, нужно ли оставить звук\\.\n"
        "▪️ **Формат:** Я принимаю медиа с любым соотношением сторон и автоматически обрежу его до квадрата из центра\\.\n"
        "▪️ **Совет:** Для наилучшего результата подготовьте материал в квадратном формате \\(1:1\\)\\."
    )

    await update.message.reply_text(start_message, parse_mode=ParseMode.MARKDOWN_V2)

async def process_media(update: Update, context: CallbackContext):
    """Обрабатывает получение видео/GIF: скачивает, проверяет и предлагает опции."""
    message = update.message
    user_id = message.from_user.id
    chat_id = message.chat_id
    media_file_id = None
    file_unique_id = None
    media_type = ""

    # Определяем тип медиафайла
    if message.video:
        media_file_id = message.video.file_id
        file_unique_id = message.video.file_unique_id
        media_type = 'video'
        logging.info(f"User {user_id}: Получено видео (ID: {media_file_id}, UniqueID: {file_unique_id})")
    elif message.animation:
        media_file_id = message.animation.file_id
        file_unique_id = message.animation.file_unique_id
        media_type = 'animation'
        logging.info(f"User {user_id}: Получена анимация (ID: {media_file_id}, UniqueID: {file_unique_id})")
    else:
        await message.reply_text("Пожалуйста, отправь видеофайл или GIF-анимацию.", parse_mode=None)
        return

    input_filename, output_filename = get_temp_filenames(user_id)
    # Предварительная очистка старых файлов для этого пользователя
    await cleanup_files(input_filename, output_filename)

    status_message = await message.reply_text("Скачиваю и анализирую медиа...", parse_mode=None)
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    input_clip = None
    try:
        # Скачивание файла
        try:
            media_file = await context.bot.get_file(media_file_id)
            await media_file.download_to_drive(input_filename)
            logging.info(f"User {user_id}: Медиафайл скачан в {input_filename}")
        except BadRequest as e:
            logging.error(f"User {user_id}: Ошибка BadRequest при скачивании файла {file_unique_id}: {e}")
            await status_message.edit_text("Не удалось скачать файл. Возможно, он устарел или недоступен. Попробуйте отправить его снова.", parse_mode=None)
            return
        except Exception as e:
            logging.error(f"User {user_id}: Ошибка при скачивании файла {file_unique_id}: {e}", exc_info=True)
            await status_message.edit_text("Произошла ошибка при скачивании файла.", parse_mode=None)
            return

        # Анализ длительности с помощью MoviePy
        await status_message.edit_text("Анализирую длительность...", parse_mode=None)
        input_clip = VideoFileClip(input_filename)
        actual_duration = input_clip.duration

        # Проверка корректности определения длительности
        if actual_duration is None or actual_duration <= 0:
             logging.warning(f"User {user_id}: Не удалось определить длительность для {input_filename}. Прерывание.")
             await status_message.edit_text("Не удалось определить длительность файла. Попробуйте другой.", parse_mode=None)
             await cleanup_files(input_filename)
             if input_clip: input_clip.close()
             return

        logging.info(f"User {user_id}: Фактическая длительность {input_filename}: {actual_duration:.2f} сек.")

        # Предложение опций пользователю через Inline кнопки
        needs_trim = actual_duration > MAX_DURATION_SECONDS
        duration_text = f"Длительность: {actual_duration:.1f} сек."
        options_text_base = f"{duration_text}\n\nВыберите опции:"
        if needs_trim:
             options_text_base = f"{duration_text} (слишком длинное!)\n\nОбрезать до {MAX_DURATION_SECONDS} сек и выбрать опции:"

        options_text_esc = escape_markdown_v2(options_text_base) # Экранируем для MarkdownV2

        keyboard_buttons = []
        # Используем file_unique_id для связи данных кнопки с конкретным файлом
        base_data = f"{file_unique_id.replace(':', '_')}"

        if not needs_trim:
            # Кнопки без обрезки
            keyboard_buttons.append([
                InlineKeyboardButton("✅ Оставить звук", callback_data=f"process:keep_audio:no_trim:{base_data}"),
                InlineKeyboardButton("🔇 Убрать звук", callback_data=f"process:mute_audio:no_trim:{base_data}"),
            ])
        else:
            # Кнопки с предложением обрезки
             keyboard_buttons.append([
                 InlineKeyboardButton("✂️+✅ Обрезать и оставить звук", callback_data=f"process:keep_audio:trim:{base_data}"),
                 InlineKeyboardButton("✂️+🔇 Обрезать и убрать звук", callback_data=f"process:mute_audio:trim:{base_data}"),
             ])

        keyboard_buttons.append([InlineKeyboardButton("❌ Отмена", callback_data=f"cancel:na:na:{base_data}")])
        reply_markup = InlineKeyboardMarkup(keyboard_buttons)

        # Сохраняем контекст для обработчика кнопок
        context.user_data[f"media_{file_unique_id}"] = {
            'input_filename': input_filename,
            'media_type': media_type,
            'chat_id': chat_id,
            'status_message_id': status_message.message_id
        }
        logging.info(f"User {user_id}: Сохранены данные для {file_unique_id}")

        # Отправляем сообщение с кнопками и разметкой MarkdownV2
        await status_message.edit_text(options_text_esc, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)

    except Exception as e:
        # Обработка общих ошибок на этапе подготовки
        logging.error(f"User {user_id}: Ошибка на этапе подготовки ({file_unique_id}): {e}", exc_info=True)
        try:
            await status_message.edit_text("Произошла ошибка при подготовке файла. Попробуйте еще раз.", parse_mode=None)
        except Exception as edit_err:
            logging.warning(f"User {user_id}: Не удалось отредактировать сообщение об ошибке подготовки: {edit_err}")
        await cleanup_files(input_filename) # Очистка при ошибке
    finally:
        # Гарантированно закрываем клип MoviePy, если он был открыт
         if input_clip:
             try:
                 input_clip.close()
             except Exception as close_err:
                 logging.error(f"User {user_id}: Ошибка при закрытии input_clip в process_media: {close_err}")


async def button_handler(update: Update, context: CallbackContext):
    """Обрабатывает нажатия на inline-кнопки выбора опций."""
    query = update.callback_query
    await query.answer() # Отвечаем на callback для снятия "часиков"

    user_id = query.from_user.id
    try:
        # Парсим данные из callback_data (формат: action:audio_choice:trim_choice:file_unique_id)
        data_parts = query.data.split(':')
        action = data_parts[0]
        file_unique_id = data_parts[-1] if len(data_parts) > 1 else None
        # Восстанавливаем ':' если он был заменен при создании base_data
        file_unique_id = file_unique_id.replace('_', ':') if file_unique_id else None

    except Exception as e:
        logging.error(f"User {user_id}: Ошибка парсинга callback_data '{query.data}': {e}")
        await query.edit_message_text("Ошибка обработки данных кнопки.", parse_mode=None)
        return

    if not file_unique_id:
        logging.warning(f"User {user_id}: Получен callback без file_unique_id: {query.data}")
        await query.edit_message_text("Произошла ошибка (нет ID файла). Попробуйте отправить медиа заново.", parse_mode=None)
        return

    # Извлекаем сохраненные данные о медиафайле
    user_key = f"media_{file_unique_id}"
    media_data = context.user_data.pop(user_key, None) # pop удаляет данные после извлечения

    # Проверка, существуют ли еще данные (могли устареть или быть удалены)
    if not media_data:
        logging.warning(f"User {user_id}: Не найдены данные для {file_unique_id} в user_data (возможно, устарели).")
        await query.edit_message_text("Не могу найти информацию об этом файле. Возможно, прошло слишком много времени или произошла ошибка. Пожалуйста, отправьте медиа заново.", parse_mode=None)
        input_filename, _ = get_temp_filenames(user_id)
        # Пытаемся очистить старый файл, если он остался
        await cleanup_files(input_filename)
        return

    input_filename = media_data.get('input_filename')
    chat_id = media_data.get('chat_id')
    status_message_id = media_data.get('status_message_id')

    # Обработка кнопки "Отмена"
    if action == 'cancel':
        logging.info(f"User {user_id}: Отмена операции для {file_unique_id}.")
        await query.edit_message_text("Операция отменена.", parse_mode=None)
        await cleanup_files(input_filename)
        return

    # Обработка кнопок "process"
    if action == 'process':
        # Проверка корректности callback_data
        if len(data_parts) < 4:
             logging.error(f"User {user_id}: Некорректный callback_data для process: {query.data}")
             await query.edit_message_text("Ошибка в данных кнопки. Попробуйте снова.", parse_mode=None)
             await cleanup_files(input_filename)
             return

        # Определяем выбор пользователя
        audio_choice = data_parts[1] # 'keep_audio' or 'mute_audio'
        trim_choice = data_parts[2] # 'no_trim' or 'trim'
        mute = (audio_choice == 'mute_audio')
        trim = (trim_choice == 'trim')

        logging.info(f"User {user_id}: Запрос на обработку {file_unique_id}. Обрезка: {trim}, Звук: {'убрать' if mute else 'оставить'}")

        # Обновляем статусное сообщение
        status_text = f"Начинаю конвертацию {'с обрезкой' if trim else ''} {'и без звука' if mute else ''}..."
        try:
            await query.edit_message_text(status_text, parse_mode=None)
        except BadRequest as e: # Ошибка, если сообщение не изменилось
             logging.warning(f"User {user_id}: Не удалось изменить текст кнопки (возможно, текст тот же): {e}")
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.RECORD_VIDEO_NOTE)

        # Запускаем основную функцию конвертации
        await _perform_conversion(input_filename, mute, trim, update, context, file_unique_id, chat_id, status_message_id)

    else:
        # Обработка неизвестного действия
        logging.warning(f"User {user_id}: Неизвестное действие в callback: {action}")
        await query.edit_message_text("Неизвестная команда.", parse_mode=None)
        await cleanup_files(input_filename)


async def _perform_conversion(input_filename: str, mute: bool, trim: bool, update: Update, context: CallbackContext, file_unique_id: str, chat_id: int, status_message_id: int):
    """Выполняет конвертацию медиафайла в видеокружок и отправляет его."""
    user_id = update.effective_user.id if update.effective_user else "unknown_user"
    _, output_filename = get_temp_filenames(user_id)
    input_clip = None
    output_clip = None
    final_duration = 0

    async def edit_status(text: str, use_markdown: bool = False):
        """Вспомогательная функция для обновления статус-сообщения в чате."""
        if chat_id and status_message_id:
            mode = ParseMode.MARKDOWN_V2 if use_markdown else None
            processed_text = escape_markdown_v2(text) if use_markdown else text
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=status_message_id,
                    text=processed_text, parse_mode=mode
                )
            except BadRequest as e:
                # Игнорируем ошибку "Message is not modified"
                if "Message is not modified" not in str(e):
                    logging.warning(f"User {user_id}: Не удалось обновить статусное сообщение ({status_message_id}) до '{text}': {e}")
            except Exception as e:
                 logging.warning(f"User {user_id}: Не удалось обновить статусное сообщение ({status_message_id}) до '{text}': {e}")

    try:
        await edit_status("Загружаю медиа для обработки...")
        input_clip = VideoFileClip(input_filename)

        # 1. Обрезка до MAX_DURATION_SECONDS (если выбрано)
        if trim:
            await edit_status("Обрезаю видео...")
            logging.info(f"User {user_id}: Обрезка {file_unique_id} до {MAX_DURATION_SECONDS} сек.")
            duration_to_trim = min(input_clip.duration, MAX_DURATION_SECONDS)
            current_clip = input_clip.subclip(0, duration_to_trim)
        else:
            current_clip = input_clip

        # 2. Удаление звука (если выбрано или его нет)
        if mute:
            await edit_status("Удаляю звук...")
            logging.info(f"User {user_id}: Удаление звука из {file_unique_id}.")
            current_clip = current_clip.without_audio()
        elif current_clip.audio is None:
             # Если звука нет изначально (например, GIF), считаем что mute=True для кодеков
             mute = True

        # 3. Изменение размера и обрезка до квадрата
        await edit_status("Изменяю размер и обрезаю кадр...")
        w, h = current_clip.size
        target_size = CIRCLE_SIZE
        # Ресайз по меньшей стороне до target_size
        if w > h:
            resized_clip = current_clip.resize(height=target_size)
        elif h > w:
            resized_clip = current_clip.resize(width=target_size)
        else: # Уже квадратное
            resized_clip = current_clip.resize(width=target_size)

        # Обрезка из центра до квадрата target_size x target_size
        output_clip = resized_clip.crop(x_center=resized_clip.w / 2,
                                        y_center=resized_clip.h / 2,
                                        width=target_size,
                                        height=target_size)
        final_duration = int(output_clip.duration) if output_clip.duration else 0
        logging.info(f"User {user_id}: Ресайз/кроп {file_unique_id} до {target_size}x{target_size}, длительность {final_duration} сек.")

        # 4. Запись финального видеофайла MP4
        await edit_status("Сохраняю финальное видео...")
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.RECORD_VIDEO_NOTE)

        # Параметры для совместимости с Telegram и уменьшения размера
        output_clip.write_videofile(
            output_filename,
            codec="libx264",
            # Убираем аудиокодек/битрейт если звук отключен или его нет
            audio_codec="aac" if not mute and output_clip.audio is not None else None,
            bitrate="800k", # Основной параметр для контроля размера файла
            audio_bitrate="96k" if not mute and output_clip.audio is not None else None,
            preset='medium', # Баланс скорости и качества
            threads=os.cpu_count() or 4, # Используем доступные ядра CPU
            logger=None, # Отключаем логгер MoviePy в консоли
            ffmpeg_params=[ # Дополнительные параметры ffmpeg для совместимости
                "-profile:v", "baseline", "-level", "3.0",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart"
            ]
        )
        logging.info(f"User {user_id}: Файл {output_filename} для {file_unique_id} успешно создан.")

        # 5. Проверка размера итогового файла
        final_size = os.path.getsize(output_filename)
        if final_size > MAX_FILE_SIZE_BYTES:
            logging.warning(f"User {user_id}: Финальный файл {output_filename} ({file_unique_id}) слишком большой: {final_size} байт.")
            await edit_status(f"Не удалось сжать видео до нужного размера ({final_size // 1024 // 1024} МБ). Попробуйте файл покороче.")
            return # Прерываем выполнение, оставляем файлы для анализа

        # 6. Отправка готового видеокружка
        await edit_status("Загружаю кружок в Telegram...")
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_VIDEO_NOTE)

        try:
            # Отправляем видеокружок
            with open(output_filename, "rb") as video_note_file:
                await context.bot.send_video_note(
                    chat_id=chat_id, video_note=video_note_file,
                    duration=final_duration, length=target_size
                )
            logging.info(f"User {user_id}: Видеокружок {file_unique_id} успешно отправлен.")
            # Удаляем статусное сообщение после успешной отправки
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=status_message_id)
            except Exception as del_err:
                 logging.warning(f"User {user_id}: Не удалось удалить статусное сообщение {status_message_id}: {del_err}")

        except TimedOut as e:
            # Обработка таймаута при отправке
            logging.error(f"User {user_id}: TimedOut при отправке видеокружка {file_unique_id}: {e}")
            await edit_status("Отправка заняла слишком много времени. Видео могло отправиться, проверьте чат!", use_markdown=False)
            # Не прерываем, чтобы finally очистил файлы

        except Exception as send_err:
             # Обработка других ошибок отправки
             logging.error(f"User {user_id}: Ошибка при отправке видеокружка {file_unique_id}: {send_err}", exc_info=True)
             await edit_status("Произошла ошибка при отправке кружка в Telegram.", use_markdown=False)
             # Не прерываем, чтобы finally очистил файлы

    except Exception as e:
        # Обработка общих ошибок конвертации
        logging.error(f"User {user_id}: Ошибка во время конвертации/отправки {file_unique_id}: {e}", exc_info=True)
        await edit_status("Произошла ошибка во время финальной обработки. Попробуйте другой файл.", use_markdown=False)

    finally:
        # Гарантированное закрытие клипов MoviePy
        if input_clip:
            try: input_clip.close()
            except Exception as e: logging.error(f"User {user_id}: Ошибка при закрытии input_clip в conversion: {e}")
        if output_clip:
             try: output_clip.close()
             except Exception as e: logging.error(f"User {user_id}: Ошибка при закрытии output_clip в conversion: {e}")
        # Гарантированная очистка временных файлов
        await cleanup_files(input_filename, output_filename)

