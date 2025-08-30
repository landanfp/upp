#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# (c) Shrimadhav U K | @Tellybots 

import logging
import asyncio
import json
import os
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.errors import UserNotParticipant, FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from functions.forcesub import handle_force_subscribe
from functions.display_progress import humanbytes
from functions.help_uploadbot import DownLoadFile
from functions.display_progress import TimeFormatter
from plugins.config import Config
from plugins.translation import Translation
from plugins.database.add import add_user_to_database
from functions.ran_text import random_char

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

@Client.on_message(filters.private & filters.regex(pattern=".*http.*"))
async def echo(bot, update):
    # لاگ پیام در کانال
    if Config.LOG_CHANNEL:
        try:
            log_message = await update.forward(Config.LOG_CHANNEL)
            log_info = (
                "Message Sender Information\n"
                f"\nFirst Name: {update.from_user.first_name}"
                f"\nUser ID: {update.from_user.id}"
                f"\nUsername: @{update.from_user.username if update.from_user.username else ''}"
                f"\nUser Link: {update.from_user.mention}"
            )
            await log_message.reply_text(
                text=log_info,
                disable_web_page_preview=True,
                quote=True,
                parse_mode=ParseMode.HTML
            )
        except Exception as error:
            logger.error(f"Error forwarding to log channel: {error}")

    if not update.from_user:
        return await update.reply_text("❌ نمی‌تونم شما رو شناسایی کنم!", parse_mode=ParseMode.HTML)

    await add_user_to_database(bot, update)

    # بررسی عضویت در کانال
    if Config.UPDATES_CHANNEL:
        fsub = await handle_force_subscribe(bot, update)
        if fsub == 400:
            return

    url = update.text.strip()
    youtube_dl_username = None
    youtube_dl_password = None
    file_name = None

    # پردازش URL و پارامترهای اضافی
    if "|" in url:
        url_parts = url.split("|")
        if len(url_parts) == 2:
            url, file_name = url_parts
        elif len(url_parts) == 4:
            url, file_name, youtube_dl_username, youtube_dl_password = url_parts
        else:
            for entity in update.entities:
                if entity.type == "text_link":
                    url = entity.url
                elif entity.type == "url":
                    o, l = entity.offset, entity.length
                    url = url[o:o + l]
        url = url.strip() if url else None
        file_name = file_name.strip() if file_name else None
        youtube_dl_username = youtube_dl_username.strip() if youtube_dl_username else None
        youtube_dl_password = youtube_dl_password.strip() if youtube_dl_password else None
    else:
        for entity in update.entities:
            if entity.type == "text_link":
                url = entity.url
            elif entity.type == "url":
                o, l = entity.offset, entity.length
                url = url[o:o + l]

    if not url:
        return await update.reply_text("❌ لینک معتبر نیست!", parse_mode=ParseMode.HTML)

    # آماده‌سازی دستور yt-dlp
    command_to_exec = [
        "yt-dlp",
        "--no-warnings",
        "--youtube-skip-dash-manifest",
        "-j",
        url,
        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "--verbose"
    ]
    if Config.HTTP_PROXY:
        command_to_exec.extend(["--proxy", Config.HTTP_PROXY])
    if youtube_dl_username:
        command_to_exec.extend(["--username", youtube_dl_username])
    if youtube_dl_password:
        command_to_exec.extend(["--password", youtube_dl_password])
    if "instagram.com" in url or "rumble.com" in url or "ok.ru" in url or "xhamster.com" in url:
        cookies_path = "/app/cookies.txt"
        if not os.path.exists(cookies_path):
            logger.error(f"Cookies file not found: {cookies_path}")
            await update.reply_text(
                "❌ فایل کوکی‌ها یافت نشد! لطفاً فایل cookies.txt را تنظیم کنید.",
                parse_mode=ParseMode.HTML,
                reply_to_message_id=update.id
            )
            return
        command_to_exec.extend(["--cookies", cookies_path])

    logger.info(f"Executing command: {command_to_exec}")

    # ارسال پیام در حال پردازش
    chk = await bot.send_message(
        chat_id=update.chat.id,
        text="**🔄 در حال بررسی لینک ... ⚡**",
        disable_web_page_preview=True,
        reply_to_message_id=update.id,
        parse_mode=ParseMode.HTML
    )

    try:
        process = await asyncio.create_subprocess_exec(
            *command_to_exec,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        # استفاده از asyncio.wait_for برای اعمال محدودیت زمانی
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60.0)
        except asyncio.TimeoutError:
            logger.error("yt-dlp process timed out")
            process.kill()
            await chk.delete()
            await bot.send_message(
                chat_id=update.chat.id,
                text="❌ زمان پردازش لینک به اتمام رسید! لطفاً دوباره تلاش کنید یا لینک دیگری امتحان کنید.",
                reply_to_message_id=update.id,
                parse_mode=ParseMode.HTML
            )
            return

        e_response = stderr.decode().strip()
        t_response = stdout.decode().strip()

        logger.info(f"yt-dlp stdout: {t_response}")
        logger.info(f"yt-dlp stderr: {e_response}")

        # بررسی خطاهای yt-dlp
        if e_response:
            logger.error(f"yt-dlp error: {e_response}")
            await chk.delete()
            if "nonnumeric port" in e_response:
                await bot.send_message(
                    chat_id=update.chat.id,
                    text="❌ خطای سرور در پردازش لینک. لطفاً لینک دیگری امتحان کنید.",
                    reply_to_message_id=update.id,
                    parse_mode=ParseMode.HTML
                )
            elif "This video is only available for registered users" in e_response:
                await bot.send_message(
                    chat_id=update.chat.id,
                    text=Translation.NO_VOID_FORMAT_FOUND.format("این ویدئو نیاز به نام کاربری و رمز عبور دارد.") + Translation.SET_CUSTOM_USERNAME_PASSWORD,
                    reply_to_message_id=update.id,
                    parse_mode=ParseMode.HTML
                )
            elif "ERROR: unable to download video data" in e_response:
                await bot.send_message(
                    chat_id=update.chat.id,
                    text="❌ خطا در دانلود اطلاعات ویدئو. لطفاً مطمئن شوید که لینک معتبر است یا فایل کوکی‌ها را بررسی کنید.",
                    reply_to_message_id=update.id,
                    parse_mode=ParseMode.HTML
                )
            elif "ERROR: unsupported URL" in e_response:
                await bot.send_message(
                    chat_id=update.chat.id,
                    text="❌ لینک پشتیبانی نمی‌شود. لطفاً لینک دیگری امتحان کنید یا فایل کوکی‌ها را بررسی کنید.",
                    reply_to_message_id=update.id,
                    parse_mode=ParseMode.HTML
                )
            else:
                await bot.send_message(
                    chat_id=update.chat.id,
                    text=f"❌ خطا در پردازش لینک: {e_response[:100]}...",
                    reply_to_message_id=update.id,
                    parse_mode=ParseMode.HTML
                )
            return

        if not t_response:
            await chk.delete()
            await bot.send_message(
                chat_id=update.chat.id,
                text="❌ هیچ اطلاعاتی از ویدئو دریافت نشد! لطفاً لینک را بررسی کنید.",
                reply_to_message_id=update.id,
                parse_mode=ParseMode.HTML
            )
            return

        # تجزیه JSON
        try:
            response_json = json.loads(t_response.split("\n")[0] if "\n" in t_response else t_response)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            await chk.delete()
            await bot.send_message(
                chat_id=update.chat.id,
                text=f"❌ خطا در تجزیه اطلاعات ویدئو: {str(e)[:100]}...",
                reply_to_message_id=update.id,
                parse_mode=ParseMode.HTML
            )
            return

        # ذخیره JSON
        randem = random_char(5)
        save_ytdl_json_path = os.path.join(Config.DOWNLOAD_LOCATION, f"{update.from_user.id}_{randem}.json")
        try:
            os.makedirs(Config.DOWNLOAD_LOCATION, exist_ok=True)
            with open(save_ytdl_json_path, "w", encoding="utf8") as outfile:
                json.dump(response_json, outfile, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving JSON file: {e}")
            await chk.delete()
            await bot.send_message(
                chat_id=update.chat.id,
                text=f"❌ خطا در ذخیره فایل JSON: {str(e)[:100]}...",
                reply_to_message_id=update.id,
                parse_mode=ParseMode.HTML
            )
            return

        # ایجاد دکمه‌های اینلاین
        inline_keyboard = []
        duration = response_json.get("duration")

        if "formats" in response_json:
            for fmt in response_json["formats"]:
                format_id = fmt.get("format_id")
                format_string = fmt.get("format_note", fmt.get("format", "N/A"))
                format_ext = fmt.get("ext")
                approx_file_size = humanbytes(fmt.get("filesize", 0)) if fmt.get("filesize") else "N/A"
                cb_string_video = f"video|{format_id}|{format_ext}|{randem}"
                cb_string_file = f"file|{format_id}|{format_ext}|{randem}"

                if format_string and "audio only" not in format_string:
                    inline_keyboard.append([
                        InlineKeyboardButton(
                            f"🎬 {format_string} {format_ext} ({approx_file_size})",
                            callback_data=cb_string_video.encode("UTF-8")
                        )
                    ])
                else:
                    inline_keyboard.append([
                        InlineKeyboardButton(
                            f"🎵 {format_string} {format_ext} ({approx_file_size})",
                            callback_data=cb_string_file.encode("UTF-8")
                        )
                    ])

            if duration:
                inline_keyboard.extend([
                    [
                        InlineKeyboardButton("🎵 MP3 (64 kbps)", callback_data=f"audio|64k|mp3|{randem}".encode("UTF-8")),
                        InlineKeyboardButton("🎵 MP3 (128 kbps)", callback_data=f"audio|128k|mp3|{randem}".encode("UTF-8"))
                    ],
                    [InlineKeyboardButton("🎵 MP3 (320 kbps)", callback_data=f"audio|320k|mp3|{randem}".encode("UTF-8"))],
                    [InlineKeyboardButton("× لغو ×", callback_data="close")]
                ])
        else:
            format_id = response_json.get("format_id")
            format_ext = response_json.get("ext")
            cb_string_video = f"video|{format_id}|{format_ext}|{randem}"
            inline_keyboard.append([
                InlineKeyboardButton("🎬 ویدئو", callback_data=cb_string_video.encode("UTF-8"))
            ])
            inline_keyboard.append([InlineKeyboardButton("× لغو ×", callback_data="close")])

        await chk.delete()
        await bot.send_message(
            chat_id=update.chat.id,
            text=Translation.FORMAT_SELECTION.format(""),
            reply_markup=InlineKeyboardMarkup(inline_keyboard),
            parse_mode=ParseMode.HTML,
            reply_to_message_id=update.id
        )

    except FileNotFoundError as e:
        logger.error(f"FileNotFoundError: {e}")
        await chk.delete()
        await bot.send_message(
            chat_id=update.chat.id,
            text=f"❌ خطای دسترسی به فایل: {str(e)[:100]}...",
            reply_to_message_id=update.id,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Error in processing: {str(e)}")
        await chk.delete()
        await bot.send_message(
            chat_id=update.chat.id,
            text=f"⚠️ خطایی رخ داد: {str(e)[:100]}... لطفاً لینک را بررسی کنید یا دوباره تلاش کنید.",
            reply_to_message_id=update.id,
            parse_mode=ParseMode.HTML
        )
