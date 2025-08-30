# Copyright @Tellybots | @Shrimadhav Uk
import logging
import asyncio
import aiohttp
import os
import shutil
from datetime import datetime
from pyrogram import Client
from pyrogram.enums import ParseMode  # اضافه‌شده: برای ParseMode
from plugins.config import Config
from plugins.translation import Translation
from plugins.custom_thumbnail import Gthumb01, Gthumb02, Mdata01, Mdata02, Mdata03
from plugins.database.database import db
from functions.display_progress import progress_for_pyrogram, humanbytes, TimeFormatter
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from PIL import Image

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

async def ddl_call_back(bot, update):
    logger.info(update)
    cb_data = update.data
    tg_send_type, youtube_dl_format, youtube_dl_ext = cb_data.split("=")
    thumb_image_path = os.path.join(Config.DOWNLOAD_LOCATION, f"{update.from_user.id}.jpg")
    
    youtube_dl_url = update.message.reply_to_message.text
    custom_file_name = os.path.basename(youtube_dl_url)
    if "|" in youtube_dl_url:
        url_parts = youtube_dl_url.split("|")
        if len(url_parts) == 2:
            youtube_dl_url, custom_file_name = url_parts
        else:
            for entity in update.message.reply_to_message.entities:
                if entity.type == "text_link":
                    youtube_dl_url = entity.url
                elif entity.type == "url":
                    o, l = entity.offset, entity.length
                    youtube_dl_url = youtube_dl_url[o:o + l]
        youtube_dl_url = youtube_dl_url.strip() if youtube_dl_url else None
        custom_file_name = custom_file_name.strip() if custom_file_name else None
        logger.info(f"URL: {youtube_dl_url}, File name: {custom_file_name}")
    
    user = await bot.get_me()
    mention = user["mention"]
    description = Translation.CUSTOM_CAPTION_UL_FILE.format(mention)
    
    start = datetime.now()
    await bot.edit_message_text(
        text=Translation.DOWNLOAD_START,
        chat_id=update.message.chat.id,
        message_id=update.message.id  # تغییر: message_id به id
    )
    
    tmp_directory_for_each_user = os.path.join(Config.DOWNLOAD_LOCATION, str(update.from_user.id))
    os.makedirs(tmp_directory_for_each_user, exist_ok=True)
    download_directory = os.path.join(tmp_directory_for_each_user, custom_file_name)

    async with aiohttp.ClientSession() as session:
        c_time = time.time()
        try:
            await download_coroutine(
                bot,
                session,
                youtube_dl_url,
                download_directory,
                update.message.chat.id,
                update.message.id,  # تغییر: message_id به id
                c_time
            )
        except asyncio.TimeoutError:
            await bot.edit_message_text(
                text=Translation.SLOW_URL_DECED,
                chat_id=update.message.chat.id,
                message_id=update.message.id,  # تغییر: message_id به id
                parse_mode=ParseMode.HTML  # تغییر: ParseMode.HTML
            )
            return False
        except Exception as e:
            logger.error(f"Error in download_coroutine: {e}")
            await bot.edit_message_text(
                text=f"❌ خطا در دانلود: {str(e)[:100]}...",
                chat_id=update.message.chat.id,
                message_id=update.message.id,  # تغییر: message_id به id
                parse_mode=ParseMode.HTML
            )
            return False

    if os.path.exists(download_directory):
        end_one = datetime.now()
        await bot.edit_message_text(
            text=Translation.UPLOAD_START,
            chat_id=update.message.chat.id,
            message_id=update.message.id  # تغییر: message_id به id
        )
        
        file_size = os.stat(download_directory).st_size
        if file_size > Config.TG_MAX_FILE_SIZE:
            await bot.edit_message_text(
                chat_id=update.message.chat.id,
                text=Translation.RCHD_TG_API_LIMIT.format(humanbytes(file_size)),
                message_id=update.message.id,  # تغییر: message_id به id
                parse_mode=ParseMode.HTML
            )
            return False

        start_time = time.time()
        if await db.get_upload_as_doc(update.from_user.id):
            width, height, duration = await Mdata01(download_directory)
            thumb_image_path = await Gthumb02(bot, update, duration, download_directory)
            await bot.send_video(
                chat_id=update.message.chat.id,
                video=download_directory,
                caption=description,
                duration=duration,
                width=width,
                height=height,
                supports_streaming=True,
                thumb=thumb_image_path,
                reply_to_message_id=update.message.reply_to_message.id,  # تغییر: message_id به id
                progress=progress_for_pyrogram,
                progress_args=(Translation.UPLOAD_START, update.message, start_time),
                parse_mode=ParseMode.HTML
            )
        elif tg_send_type == "audio":
            duration = await Mdata03(download_directory)
            thumbnail = await Gthumb01(bot, update)
            await bot.send_audio(
                chat_id=update.message.chat.id,
                audio=download_directory,
                caption=description,
                duration=duration,
                thumb=thumbnail,
                reply_to_message_id=update.message.reply_to_message.id,  # تغییر: message_id به id
                progress=progress_for_pyrogram,
                progress_args=(Translation.UPLOAD_START, update.message, start_time),
                parse_mode=ParseMode.HTML  # تغییر: ParseMode.HTML
            )
        elif tg_send_type == "vm":
            width, duration = await Mdata02(download_directory)
            thumbnail = await Gthumb02(bot, update, duration, download_directory)
            await bot.send_video_note(
                chat_id=update.message.chat.id,
                video_note=download_directory,
                duration=duration,
                length=width,
                thumb=thumbnail,
                reply_to_message_id=update.message.reply_to_message.id,  # تغییر: message_id به id
                progress=progress_for_pyrogram,
                progress_args=(Translation.UPLOAD_START, update.message, start_time)
            )
        else:
            thumbnail = await Gthumb01(bot, update)
            await bot.send_document(
                chat_id=update.message.chat.id,
                document=download_directory,
                thumb=thumbnail,
                caption=description,
                reply_to_message_id=update.message.reply_to_message.id,  # تغییر: message_id به id
                progress=progress_for_pyrogram,
                progress_args=(Translation.UPLOAD_START, update.message, start_time),
                parse_mode=ParseMode.HTML
            )

        end_two = datetime.now()
        time_taken_for_download = (end_one - start).seconds
        time_taken_for_upload = (end_two - end_one).seconds
        
        try:
            os.remove(download_directory)
            if thumb_image_path and os.path.exists(thumb_image_path):
                os.remove(thumb_image_path)
            shutil.rmtree(tmp_directory_for_each_user, ignore_errors=True)
        except Exception as e:
            logger.error(f"Error cleaning up files: {e}")

        await bot.edit_message_text(
            text=Translation.AFTER_SUCCESSFUL_UPLOAD_MSG_WITH_TS.format(time_taken_for_download, time_taken_for_upload),
            chat_id=update.message.chat.id,
            message_id=update.message.id,  # تغییر: message_id به id
            disable_web_page_preview=True,
            parse_mode=ParseMode.HTML
        )
    else:
        await bot.edit_message_text(
            text=Translation.NO_VOID_FORMAT_FOUND.format("لینک نامعتبر است"),
            chat_id=update.message.chat.id,
            message_id=update.message.id,  # تغییر: message_id به id
            disable_web_page_preview=True,
            parse_mode=ParseMode.HTML
        )

async def download_coroutine(bot, session, url, file_name, chat_id, message_id, start):
    try:
        async with session.get(url, timeout=Config.PROCESS_MAX_TIMEOUT) as response:
            if response.status != 200:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=f"❌ خطا در دسترسی به لینک: وضعیت {response.status}",
                    parse_mode=ParseMode.HTML
                )
                return

            total_length = response.headers.get("Content-Length")
            total_length = int(total_length) if total_length else None
            content_type = response.headers.get("Content-Type", "")

            if total_length and "text" in content_type and total_length < 500:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="❌ لینک حاوی محتوای غیرقابل دانلود است",
                    parse_mode=ParseMode.HTML
                )
                return

            downloaded = 0
            display_message = ""
            if total_length:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="""**شروع دانلود**
**🔗 لینک:** `{}`
**🗂️ حجم:** {}""".format(url, humanbytes(total_length)),
                    parse_mode=ParseMode.HTML
                )

            with open(file_name, "wb") as f_handle:
                while True:
                    chunk = await response.content.read(Config.CHUNK_SIZE)
                    if not chunk:
                        break
                    f_handle.write(chunk)
                    downloaded += len(chunk)
                    now = time.time()
                    diff = now - start
                    if total_length and (round(diff % 5.00) == 0 or downloaded >= total_length):
                        percentage = downloaded * 100 / total_length
                        speed = downloaded / diff
                        elapsed_time = round(diff) * 1000
                        time_to_completion = round((total_length - downloaded) / speed) * 1000
                        estimated_total_time = elapsed_time + time_to_completion
                        try:
                            current_message = """**در حال دانلود**
**🔗 لینک:** `{}`
**🗂️ حجم:** {}
**✅ انجام شده:** {}
**⏱️ زمان باقی‌مانده:** {}""".format(
                                url,
                                humanbytes(total_length),
                                humanbytes(downloaded),
                                TimeFormatter(estimated_total_time)
                            )
                            if current_message != display_message:
                                await bot.edit_message_text(
                                    chat_id=chat_id,
                                    message_id=message_id,
                                    text=current_message,
                                    parse_mode=ParseMode.HTML
                                )
                                display_message = current_message
                        except Exception as e:
                            logger.info(f"Error updating download progress: {e}")
    except Exception as e:
        logger.error(f"Error in download_coroutine: {e}")
        raise
