#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# (c) Shrimadhav U K | @Tellybots 

import logging
import asyncio
import json
import os
from pyrogram import Client, filters
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
                quote=True
            )
        except Exception as error:
            logger.error(f"Error forwarding to log channel: {error}")

    if not update.from_user:
        return await update.reply_text("❌ نمی‌تونم شما رو شناسایی کنم!")

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
        return await update.reply_text("❌ لینک معتبر نیست!")

    # آماده‌سازی دستور yt-dlp
    command_to_exec = ["yt-dlp", "--no-warnings", "--youtube-skip-dash-manifest", "-j", url]
    if Config.HTTP_PROXY:
        command_to_exec.extend(["--proxy", Config.HTTP_PROXY])
    if youtube_dl_username:
        command_to_exec.extend(["--username", youtube_dl_username])
    if youtube_dl_password:
        command_to_exec.extend(["--password", youtube_dl_password])

    logger.info(f"Executing command: {command_to_exec}")

    # ارسال پیام در حال پردازش
    chk = await bot.send_message(
        chat_id=update.chat.id,
        text="**🔄 در حال بررسی لینک ... ⚡**",
        disable_web_page_preview=True,
        reply_to_message_id=update.id  # تغییر: message_id به id
    )

    try:
        process = await asyncio.create_subprocess_exec(
            *command_to_exec,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        e_response = stderr.decode().strip()
        t_response = stdout.decode().strip()

        if e_response and "nonnumeric port" not in e_response:
            error_message = e_response.replace(
                "please report this issue on https://yt-dl.org/bug . Make sure you are using the latest version; see  https://yt-dl.org/update  on how to update. Be sure to call youtube-dl with the --verbose flag and include its complete output.", ""
            )
            if "This video is only available for registered users." in error_message:
                error_message += Translation.SET_CUSTOM_USERNAME_PASSWORD
            await chk.delete()
            await bot.send_message(
                chat_id=update.chat.id,
                text=Translation.NO_VOID_FORMAT_FOUND.format(error_message),
                reply_to_message_id=update.id,  # تغییر: message_id به id
                parse_mode="html",
                disable_web_page_preview=True
            )
            return

        if not t_response:
            await chk.delete()
            await bot.send_message(
                chat_id=update.chat.id,
                text="❌ خطایی در دریافت اطلاعات ویدئو رخ داد!",
                reply_to_message_id=update.id  # تغییر: message_id به id
            )
            return

        try:
            response_json = json.loads(t_response.split("\n")[0] if "\n" in t_response else t_response)
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            await chk.delete()
            await bot.send_message(
                chat_id=update.chat.id,
                text="❌ خطا در پردازش اطلاعات ویدئو!",
                reply_to_message_id=update.id  # تغییر: message_id به id
            )
            return

        # ذخیره JSON
        randem = random_char(5)
        save_ytdl_json_path = os.path.join(Config.DOWNLOAD_LOCATION, f"{update.from_user.id}_{randem}.json")
        os.makedirs(Config.DOWNLOAD_LOCATION, exist_ok=True)
        with open(save_ytdl_json_path, "w", encoding="utf8") as outfile:
            json.dump(response_json, outfile, ensure_ascii=False)

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
            parse_mode="html",
            reply_to_message_id=update.id  # تغییر: message_id به id
        )

    except Exception as e:
        logger.error(f"Error in processing: {e}")
        await chk.delete()
        await bot.send_message(
            chat_id=update.chat.id,
            text="⚠️ خطایی رخ داد. لطفاً دوباره تلاش کنید.",
            reply_to_message_id=update.id  # تغییر: message_id به id
        )
