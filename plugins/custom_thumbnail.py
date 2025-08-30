# FarshidBand

import logging
import os
from PIL import Image
import random
import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from functions.forcesub import handle_force_subscribe
from plugins.database.database import db
from plugins.config import Config
from plugins.translation import Translation
from plugins.database.add import add_user_to_database
from plugins.settings.settings import OpenSettings

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

@Client.on_message(filters.private & filters.photo)
async def photo_handler(bot: Client, event: Message):
    if not event.from_user:
        return await event.reply_text("❌ نمی‌تونم شما رو شناسایی کنم!")
    
    await add_user_to_database(bot, event)
    
    if Config.UPDATES_CHANNEL:
        fsub = await handle_force_subscribe(bot, event)
        if fsub == 400:
            return
    
    editable = await event.reply_text("**👀 در حال بررسی ...**")
    try:
        await db.set_thumbnail(event.from_user.id, thumbnail=event.photo.file_id)
        await editable.edit("**✅ عکس تامبنیل با موفقیت ذخیره شد.**")
    except Exception as e:
        logger.error(f"Error saving thumbnail: {e}")
        await editable.edit("⚠️ خطایی در ذخیره تامبنیل رخ داد!")

@Client.on_message(filters.private & filters.command(["delthumb", "deletethumbnail"]))
async def delete_thumb_handler(bot: Client, event: Message):
    if not event.from_user:
        return await event.reply_text("❌ نمی‌تونم شما رو شناسایی کنم!")
    
    await add_user_to_database(bot, event)
    
    if Config.UPDATES_CHANNEL:
        fsub = await handle_force_subscribe(bot, event)
        if fsub == 400:
            return
    
    try:
        await db.set_thumbnail(event.from_user.id, thumbnail=None)
        await event.reply_text(
            "**✅ عکس تامبنیل با موفقیت حذف شد.**",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("تنظیم عکس تامبنیل جدید ⚡", callback_data="OpenSettings")]
            ])
        )
    except Exception as e:
        logger.error(f"Error deleting thumbnail: {e}")
        await event.reply_text("⚠️ خطایی در حذف تامبنیل رخ داد!")

@Client.on_message(filters.private & filters.command("showthumb"))
async def viewthumbnail(bot: Client, update: Message):
    if not update.from_user:
        return await update.reply_text("❌ نمی‌تونم شما رو شناسایی کنم!")
    
    await add_user_to_database(bot, update)
    
    if Config.UPDATES_CHANNEL:
        fsub = await handle_force_subscribe(bot, update)
        if fsub == 400:
            return
    
    try:
        thumbnail = await db.get_thumbnail(update.from_user.id)
        if thumbnail:
            await bot.send_photo(
                chat_id=update.chat.id,
                photo=thumbnail,
                caption="🔚 عکس تامبنیل ذخیره شده شما 👆",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🗑️ حذف عکس تامبنیل", callback_data="deleteThumbnail")]
                ]),
                reply_to_message_id=update.id  # تغییر: message_id به id
            )
        else:
            await update.reply_text(
                text="❌ هیچ عکس تامبنیل یافت نشد 🤒",
                parse_mode="html",
                reply_to_message_id=update.id  # تغییر: message_id به id
            )
    except Exception as e:
        logger.error(f"Error showing thumbnail: {e}")
        await update.reply_text(
            text="⚠️ خطایی در نمایش تامبنیل رخ داد!",
            parse_mode="html",
            reply_to_message_id=update.id  # تغییر: message_id به id
        )

async def Gthumb01(bot: Client, update: Message):
    thumb_image_path = os.path.join(Config.DOWNLOAD_LOCATION, f"{update.from_user.id}.jpg")
    os.makedirs(Config.DOWNLOAD_LOCATION, exist_ok=True)
    
    try:
        db_thumbnail = await db.get_thumbnail(update.from_user.id)
        if db_thumbnail:
            thumbnail = await bot.download_media(message=db_thumbnail, file_name=thumb_image_path)
            with Image.open(thumbnail) as img:
                img = img.convert("RGB").resize((100, 100), Image.LANCZOS)
                img.save(thumbnail, "JPEG", quality=95)
            return thumbnail
        return None
    except Exception as e:
        logger.error(f"Error in Gthumb01: {e}")
        return None

async def Gthumb02(bot: Client, update: Message, duration: int, download_directory: str):
    thumb_image_path = os.path.join(Config.DOWNLOAD_LOCATION, f"{update.from_user.id}.jpg")
    os.makedirs(Config.DOWNLOAD_LOCATION, exist_ok=True)
    
    try:
        db_thumbnail = await db.get_thumbnail(update.from_user.id)
        if db_thumbnail:
            thumbnail = await bot.download_media(message=db_thumbnail, file_name=thumb_image_path)
        else:
            if not os.path.exists(download_directory):
                logger.error(f"Download directory not found: {download_directory}")
                return None
            thumbnail = await take_screen_shot(download_directory, os.path.dirname(download_directory), random.randint(0, max(0, duration - 1)))
        return thumbnail
    except Exception as e:
        logger.error(f"Error in Gthumb02: {e}")
        return None

async def Mdata01(download_directory: str):
    try:
        if not os.path.exists(download_directory):
            logger.error(f"File not found: {download_directory}")
            return 0, 0, 0
        
        metadata = extractMetadata(createParser(download_directory))
        width = metadata.get("width", 0) if metadata else 0
        height = metadata.get("height", 0) if metadata else 0
        duration = metadata.get("duration").seconds if metadata and metadata.has("duration") else 0
        return width, height, duration
    except Exception as e:
        logger.error(f"Error in Mdata01: {e}")
        return 0, 0, 0

async def Mdata02(download_directory: str):
    try:
        if not os.path.exists(download_directory):
            logger.error(f"File not found: {download_directory}")
            return 0, 0
        
        metadata = extractMetadata(createParser(download_directory))
        width = metadata.get("width", 0) if metadata else 0
        duration = metadata.get("duration").seconds if metadata and metadata.has("duration") else 0
        return width, duration
    except Exception as e:
        logger.error(f"Error in Mdata02: {e}")
        return 0, 0

async def Mdata03(download_directory: str):
    try:
        if not os.path.exists(download_directory):
            logger.error(f"File not found: {download_directory}")
            return 0
        
        metadata = extractMetadata(createParser(download_directory))
        duration = metadata.get("duration").seconds if metadata and metadata.has("duration") else 0
        return duration
    except Exception as e:
        logger.error(f"Error in Mdata03: {e}")
        return 0
