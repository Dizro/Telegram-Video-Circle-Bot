from moviepy.editor import *
from telegram import Update, InputMediaVideo
from telegram.ext import CallbackContext

def start(update: Update, context: CallbackContext):
    update.message.reply_text("Отправьте мне видео, и я преобразую его в видеокружок.")

def process_video(update: Update, context: CallbackContext):
    video_file = context.bot.getFile(update.message.video.file_id)
    video_file.download("input_video.mp4")

    # Преобразование видео в видеокружок
    input_video = VideoFileClip("input_video.mp4")
    w, h = input_video.size
    circle_size = 360
    aspect_ratio = float(w) / float(h)
    
    if w > h:
        new_w = int(circle_size * aspect_ratio)
        new_h = circle_size
    else:
        new_w = circle_size
        new_h = int(circle_size / aspect_ratio)
        
    resized_video = input_video.resize((new_w, new_h))
    output_video = resized_video.crop(x_center=resized_video.w/2, y_center=resized_video.h/2, width=circle_size, height=circle_size)
    output_video.write_videofile("output_video.mp4", codec="libx264", audio_codec="aac")

    # Отправка видеокружка в чат
    with open("output_video.mp4", "rb") as video:
        context.bot.send_video_note(chat_id=update.message.chat_id, video_note=video, duration=int(output_video.duration), length=circle_size)
