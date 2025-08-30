import asyncio
from pyrogram import types, errors
from pyrogram.enums import ParseMode  # اضافه‌شده: import برای ParseMode
from plugins.config import Config
from plugins.database.database import db

async def OpenSettings(m: "types.Message"):
    usr_id = m.chat.id
    user_data = await db.get_user_data(usr_id)
    if not user_data:
        await m.reply("❌ Failed to fetch your data from database!")  # تغییر به reply برای جلوگیری از مشکلات edit
        return

    upload_as_doc = user_data.get("upload_as_doc", False)
    thumbnail = user_data.get("thumbnail", None)
    generate_ss = user_data.get("generate_ss", False)

    # تعریف ثابت‌ها برای رشته‌ها
    UPLOAD_MODE_TEXT = {
        True: "🎬 ویدیو",
        False: "📂 فایل"
    }
    SS_STATUS_TEXT = {
        True: "✅ فعال",
        False: "✖️ غیرفعال"
    }

    buttons_markup = [
        [types.InlineKeyboardButton(f"📤 آپلود بصورت: {UPLOAD_MODE_TEXT[upload_as_doc]}",
                                    callback_data="triggerUploadMode")],
        [types.InlineKeyboardButton(f"📸 گرفتن اسکرین شات: {SS_STATUS_TEXT[generate_ss]}",
                                    callback_data="triggerGenSS")],
        [types.InlineKeyboardButton(f"{'🌃 ثبت' if thumbnail else '🌃 ثبت'} عکس تامبنیل",
                                    callback_data="setThumbnail")]
    ]

    if thumbnail:
        buttons_markup.append([types.InlineKeyboardButton("🌆 نمایش عکس تامبنیل شما",
                                                         callback_data="showThumbnail")])
    buttons_markup.append([types.InlineKeyboardButton("𝘅 بستن 𝘅",
                                                     callback_data="close")])

    try:
        await m.edit(
            text="**• جهت تغییر تنظیمات کلیک کنید 👇**",
            reply_markup=types.InlineKeyboardMarkup(buttons_markup),
            disable_web_page_preview=True,
            parse_mode=ParseMode.MARKDOWN  # تغییر: از ParseMode.MARKDOWN استفاده شد
        )
    except errors.MessageNotModified:
        pass
    except errors.FloodWait as e:
        await asyncio.sleep(e.value)
        await OpenSettings(m)
    except Exception as err:
        Config.LOGGER.getLogger(__name__).error(f"Error in OpenSettings: {err}")
        await m.reply("⚠️ خطایی رخ داد. لطفاً دوباره تلاش کنید.")
