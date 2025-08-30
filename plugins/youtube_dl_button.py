#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# (c) Shrimadhav U K | @Tellybots

import logging
import asyncio
import json
import os
import shutil
from datetime import datetime
from pyrogram import Client
from pyrogram.enums import ParseMode  # اضافه‌شده: برای ParseMode
from pyrogram.types import InputMediaPhoto
from functions.help_Nekmo_ffmpeg import generate_screen_shots
from plugins.config import Config
from plugins.translation import Translation
from plugins.custom_thumbnail import Gthumb01, Gthumb02, Mdata01, Mdata02, Mdata03
from functions.display_progress import progress_for_pyrogram, humanbytes
from plugins.database.database import db
from PIL import Image
from functions.ran_text import random_char

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

async def youtube_dl_call_back(bot, update):
    cb_data = update.data
    tg_send_type, youtube_dl_format, youtube_dl_ext, ranom = cb_data.split("|")
    logger.info(f"Callback data: {cb_data}")
    random1 = random_char(5)
    
    save_ytdl_json_path = os.path.join(Config.DOWNLOAD_LOCATION, f"{update.from_user.id}_{ranom}.json")
    thumbnail = os.path.join(Config.DOWNLOAD_LOCATION, f"{update.from_user.id}_{ranom}.jpg")
    
    try:
        with open(save_ytdl_json_path, "r", encoding="utf8") as f:
            response_json = json.load(f)
    except FileNotFoundError as e:
        logger.error(f"JSON file not found: {e}")
        await bot.delete_messages(
            chat_id=update.message.chat.id,
            message_ids=update.message.id,  # تغییر: message_id به id
            revoke=True
        )
        return False

    youtube_dl_url = update.message.reply_to_message.text
    custom_file_name = f"{response_json.get('title')}_{youtube_dl_format}.{youtube_dl_ext}"
    youtube_dl_username = None
    youtube_dl_password = None

    if "|" in youtube_dl_url:
        url_parts = youtube_dl_url.split("|")
        if len(url_parts) == 2:
            youtube_dl_url, custom_file_name = url_parts
        elif len(url_parts) == 4:
            youtube_dl_url, custom_file_name, youtube_dl_username, youtube_dl_password = url_parts
        else:
            for entity in update.message.reply_to_message.entities:
                if entity.type == "text_link":
                    youtube_dl_url = entity.url
                elif entity.type == "url":
                    o, l = entity.offset, entity.length
                    youtube_dl_url = youtube_dl_url[o:o + l]
        youtube_dl_url = youtube_dl_url.strip() if youtube_dl_url else None
        custom_file_name = custom_file_name.strip() if custom_file_name else None
        youtube_dl_username = youtube_dl_username.strip() if youtube_dl_username else None
        youtube_dl_password = youtube_dl_password.strip() if youtube_dl_password else None
        logger.info(f"URL: {youtube_dl_url}, File name: {custom_file_name}")
    
    await bot.edit_message_text(
        text=Translation.DOWNLOAD_START,
        chat_id=update.message.chat.id,
        message_id=update.message.id  # تغییر: message_id به id
    )
    
    description = Translation.CUSTOM_CAPTION_UL_FILE
    if "fulltitle" in response_json:
        description = response_json["fulltitle"][:1021]
    
    tmp_directory_for_each_user = os.path.join(Config.DOWNLOAD_LOCATION, f"{update.from_user.id}_{random1}")
    os.makedirs(tmp_directory_for_each_user, exist_ok=True)
    download_directory = os.path.join(tmp_directory_for_each_user, custom_file_name)

    command_to_exec = []
    if tg_send_type == "audio":
        command_to_exec = [
            "yt-dlp",
            "-c",
            "--max-filesize", str(Config.TG_MAX_FILE_SIZE),
            "--prefer-ffmpeg",
            "--extract-audio",
            "--audio-format", youtube_dl_ext,
            "--audio-quality", youtube_dl_format,
            youtube_dl_url,
            "-o", download_directory
        ]
    else:
        minus_f_format = youtube_dl_format
        if "youtu" in youtube_dl_url:
            minus_f_format = f"{youtube_dl_format}+bestaudio"
        command_to_exec = [
            "yt-dlp",
            "-c",
            "--max-filesize", str(Config.TG_MAX_FILE_SIZE),
            "--embed-subs",
            "-f", minus_f_format,
            "--hls-prefer-ffmpeg",
            youtube_dl_url,
            "-o", download_directory,
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"  # اضافه‌شده: User-Agent
        ]
        # پشتیبانی از کوکی‌ها برای Rumble و Instagram
        if "instagram.com" in youtube_dl_url or "rumble.com" in youtube_dl_url:
            command_to_exec.extend(["--cookies", "/app/cookies.txt"])  # تنظیم مسیر کوکی‌ها

    if Config.HTTP_PROXY:
        command_to_exec.extend(["--proxy", Config.HTTP_PROXY])
    if youtube_dl_username:
        command_to_exec.extend(["--username", youtube_dl_username])
    if youtube_dl_password:
        command_to_exec.extend(["--password", youtube_dl_password])
    command_to_exec.append("--no-warnings")

    logger.info(f"Executing command: {command_to_exec}")
    
    start = datetime.now()
    try:
        process = await asyncio.create_subprocess_exec(
            *command_to_exec,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate(timeout=60)  # اضافه‌شده: محدودیت زمانی
        e_response = stderr.decode().strip()
        t_response = stdout.decode().strip()
        logger.info(f"yt-dlp stdout: {t_response}")
        logger.info(f"yt-dlp stderr: {e_response}")

        if e_response:
            ad_string_to_replace = "please report this issue on https://yt-dl.org/bug . Make sure you are using the latest version; see  https://yt-dl.org/update  on how to update. Be sure to call youtube-dl with the --verbose flag and include its complete output."
            error_message = e_response.replace(ad_string_to_replace, "")
            await bot.edit_message_text(
                chat_id=update.message.chat.id,
                message_id=update.message.id,  # تغییر: message_id به id
                text=f"❌ خطا در دانلود: {error_message[:100]}...",
                parse_mode=ParseMode.HTML  # تغییر: استفاده از ParseMode.HTML
            )
            return False

        if not os.path.exists(download_directory):
            await bot.edit_message_text(
                chat_id=update.message.chat.id,
                message_id=update.message.id,  # تغییر: message_id به id
                text="❌ فایل دانلود نشد! لطفاً لینک را بررسی کنید.",
                parse_mode=ParseMode.HTML
            )
            return False

        end_one = datetime.now()
        time_taken_for_download = (end_one - start).seconds
        file_size = os.stat(download_directory).st_size

        if file_size > Config.TG_MAX_FILE_SIZE:
            await bot.edit_message_text(
                chat_id=update.message.chat.id,
                text=Translation.RCHD_TG_API_LIMIT.format(time_taken_for_download, humanbytes(file_size)),
                message_id=update.message.id,  # تغییر: message_id به id
                parse_mode=ParseMode.HTML
            )
            return False

        # تولید اسکرین‌شات‌ها
        images = None
        if Config.SCREENSHOTS:
            is_w_f = False
            try:
                images = await generate_screen_shots(
                    download_directory,
                    tmp_directory_for_each_user,
                    is_w_f,
                    Config.DEF_WATER_MARK_FILE,
                    300,
                    9
                )
            except Exception as e:
                logger.error(f"Error generating screenshots: {e}")

        # آماده‌سازی تامبنیل
        thumbnail_path = await Gthumb01(bot, update)
        if not thumbnail_path or not os.path.exists(thumbnail_path):
            thumbnail_path = await Gthumb02(bot, update, (await Mdata03(download_directory)), download_directory)

        await bot.edit_message_text(
            text=Translation.UPLOAD_START,
            chat_id=update.message.chat.id,
            message_id=update.message.id  # تغییر: message_id به id
        )

        start_time = time.time()
        if await db.get_upload_as_doc(update.from_user.id):
            width, height, duration = await Mdata01(download_directory)
            await bot.send_document(
                chat_id=update.message.chat.id,
                document=download_directory,
                thumb=thumbnail_path,
                caption=description,
                reply_to_message_id=update.message.reply_to_message.id,  # تغییر: message_id به id
                progress=progress_for_pyrogram,
                progress_args=(Translation.UPLOAD_START, update.message, start_time),
                parse_mode=ParseMode.HTML  # تغییر: ParseMode.HTML
            )
        elif tg_send_type == "audio":
            duration = await Mdata03(download_directory)
            await bot.send_audio(
                chat_id=update.message.chat.id,
                audio=download_directory,
                caption=description,
                duration=duration,
                thumb=thumbnail_path,
                reply_to_message_id=update.message.reply_to_message.id,  # تغییر: message_id به id
                progress=progress_for_pyrogram,
                progress_args=(Translation.UPLOAD_START, update.message, start_time),
                parse_mode=ParseMode.HTML
            )
        elif tg_send_type == "vm":
            width, duration = await Mdata02(download_directory)
            await bot.send_video_note(
                chat_id=update.message.chat.id,
                video_note=download_directory,
                duration=duration,
                length=width,
                thumb=thumbnail_path,
                reply_to_message_id=update.message.reply_to_message.id,  # تغییر: message_id به id
                progress=progress_for_pyrogram,
                progress_args=(Translation.UPLOAD_START, update.message, start_time)
            )
        else:
            width, height, duration = await Mdata01(download_directory)
            await bot.send_video(
                chat_id=update.message.chat.id,
                video=download_directory,
                caption=description,
                duration=duration,
                width=width,
                height=height,
                supports_streaming=True,
                thumb=thumbnail_path,
                reply_to_message_id=update.message.reply_to_message.id,  # تغییر: message_id به id
                progress=progress_for_pyrogram,
                progress_args=(Translation.UPLOAD_START, update.message, start_time),
                parse_mode=ParseMode.HTML
            )

        # ارسال اسکرین‌شات‌ها
        if (await db.get_generate_ss(update.from_user.id)) and images:
            media_album_p = []
            for i, image in enumerate(images):
                if os.path.exists(image):
                    media_album_p.append(
                        InputMediaPhoto(
                            media=image,
                            caption=description if i == 0 else "",
                            parse_mode=ParseMode.HTML  # تغییر: ParseMode.HTML
                        )
                    )
            if media_album_p:
                await bot.send_media_group(
                    chat_id=update.message.chat.id,
                    disable_notification=True,
                    reply_to_message_id=update.message.id,  # تغییر: message_id به id
                    media=media_album_p
                )

        end_two = datetime.now()
        time_taken_for_upload = (end_two - end_one).seconds

        # پاکسازی فایل‌ها
        try:
            shutil.rmtree(tmp_directory_for_each_user, ignore_errors=True)
            os.remove(download_directory)
            if thumbnail_path and os.path.exists(thumbnail_path):
                os.remove(thumbnail_path)
            os.remove(save_ytdl_json_path)
        except Exception as e:
            logger.error(f"Error cleaning up files: {e}")

        await bot.edit_message_text(
            text=Translation.AFTER_SUCCESSFUL_UPLOAD_MSG_WITH_TS.format(time_taken_for_download, time_taken_for_upload),
            chat_id=update.message.chat.id,
            message_id=update.message.id,  # تغییر: message_id به id
            disable_web_page_preview=True,
            parse_mode=ParseMode.HTML  # تغییر: ParseMode.HTML
        )

    except asyncio.TimeoutError:
        logger.error("yt-dlp timed out")
        await bot.edit_message_text(
            chat_id=update.message.chat.id,
            message_id=update.message.id,  # تغییر: message_id به id
            text="❌ زمان دانلود به اتمام رسید! لطفاً دوباره تلاش کنید.",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Error in youtube_dl_call_back: {e}")
        await bot.edit_message_text(
            chat_id=update.message.chat.id,
            message_id=update.message.id,  # تغییر: message_id به id
            text="⚠️ خطایی در دانلود یا آپلود رخ داد. لطفاً دوباره تلاش کنید.",
            parse_mode=ParseMode.HTML
        )
