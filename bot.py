import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from config import BOT_TOKEN, ADMIN_USER_ID
from database import Database

# راه‌اندازی دیتابیس
db = Database()

# تنظیمات لاگ
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(name)

# ================ توابع عمومی ================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """این تابع هم برای خوش‌آمدگویی و هم برای دریافت کد از لینک استفاده میشه"""
    user = update.effective_user

    # اگه کاربر با لینک اختصاصی اومده باشه
    if context.args:
        unique_code = context.args[0]  # کدی که بعد از start= اومده
        file_data = db.get_file_by_code(unique_code)

        if file_data:
            # ارسال فایل
            _, code, file_id, file_name, caption, views, _ = file_data
            final_caption = f"🎬 {caption}\n\n👁 بازدید: {views}"
            try:
                await update.message.reply_video(video=file_id, caption=final_caption, supports_streaming=True)
            except:
                # اگه ویدیو نبود، به عنوان سند عادی بفرست
                await update.message.reply_document(document=file_id, caption=final_caption, filename=file_name)
            return
        else:
            await update.message.reply_text("❌ فایل مورد نظر یافت نشد یا لینک منقضی شده است.")
            return

    # اگه کاربر عادی /start زده بود
    welcome = (
        f"👋 سلام {user.first_name} به ربات اشتراک‌گذاری فایل خوش اومدی!\n\n"
        "برای دریافت فایل، روی لینکی که ادمین برات فرستاده کلیک کن."
    )
    await update.message.reply_text(welcome)

# ================ توابع مخصوص ادمین ================

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پنل اصلی مدیریت (فقط برای ادمین)"""
    user_id = update.effective_user.id
    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("⛔ شما اجازه دسترسی به این بخش را ندارید!")
        return

    keyboard = [
        [InlineKeyboardButton("📤 آپلود فایل جدید", callback_data="upload")],
        [InlineKeyboardButton("📋 لیست فایل‌ها", callback_data="list_files")],
        [InlineKeyboardButton("📊 آمار", callback_data="stats")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🔧 پنل مدیریت:", reply_markup=reply_markup)

async def admin_upload_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """شروع فرآیند آپلود (وقتی روی دکمه کلیک میشه)"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if user_id != ADMIN_USER_ID:
        await query.edit_message_text("⛔ شما اجازه دسترسی به این بخش را ندارید!")
        return

    context.user_data['upload_step'] = 'waiting_for_file'
    await query.edit_message_text(
        "📤 لطفاً فایل مورد نظرت رو آپلود کن.\n"
        "(هر نوع فایلی می‌تونه باشه: ویدیو، عکس، سند و ...)"
    )

async def handle_admin_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت فایل از ادمین و ذخیره موقت"""
    user_id = update.effective_user.id
    
    # چک کردن ادمین بودن و مرحله درست
    if user_id != ADMIN_USER_ID:
        return
    
    if context.user_data.get('upload_step') != 'waiting_for_file':
        # اگه کاربر عادی فایل فرستاد یا ادمین در مرحله اشتباه، بیخیال
        return

    # تشخیص نوع فایل و گرفتن file_id
    file_id = None
    file_name = None
    
    if update.message.video:
        file_id = update.message.video.file_id
        file_name = update.message.video.file_name or f"video_{file_id}.mp4"
    elif update.message.document:
        file_id = update.message.document.file_id
        file_name = update.message.document.file_name
    elif update.message.audio:
        file_id = update.message.audio.file_id
        file_name = update.message.audio.file_name or f"audio_{file_id}.mp3"
    elif update.message.photo:
        # عکس‌ها معمولاً توی لیست هستن، آخرین رو می‌گیریم
        file_id = update.message.photo[-1].file_id
        file_name = f"photo_{file_id}.jpg"
    elif update.message.animation:  # گیف
        file_id = update.message.animation.file_id
        file_name = f"gif_{file_id}.gif"
    else:
        await update.message.reply_text("❌ لطفاً یه فایل معتبر ارسال کن!")
        return

    # ذخیره اطلاعات فایل توی context
    context.user_data['temp_file_id'] = file_id
    context.user_data['temp_file_name'] = file_name
    context.user_data['upload_step'] = 'waiting_for_caption'

    await update.message.reply_text(
        "✅ فایل با موفقیت دریافت شد.\n"
        "✏️ حالا یه توضیح (کپشن) برای فایل بنویس. (مثلاً نام فیلم، کیفیت و ...)\n"
        "اگه نمی‌خوای کپشنی داشته باشی، /skip رو بزن."
    )

async def handle_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دریافت کپشن و نهایی‌سازی"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_USER_ID:
        return
    
    if context.user_data.get('upload_step') != 'waiting_for_caption':
        return

    caption = update.message.text

    # نهایی‌سازی و ذخیره در دیتابیس
    file_id = context.user_data.get('temp_file_id')
    file_name = context.user_data.get('temp_file_name')

    if not file_id or not file_name:
        await update.message.reply_text("❌ خطا: اطلاعات فایل پیدا نشد! دوباره از اول تلاش کن.")
        context.user_data.clear()
        return

    try:
        unique_code = db.add_file(file_id, file_name, caption)

        # ساخت لینک اختصاصی
        bot_username = (await context.bot.get_me()).username
        file_link = f"https://t.me/{bot_username}?start={unique_code}"

        # پاک کردن اطلاعات موقت
        context.user_data.clear()

# ارسال نتیجه به ادمین
        await update.message.reply_text(
            f"✅ فایل با موفقیت ذخیره شد!\n\n"
            f"🔗 لینک اختصاصی فایل:\n{file_link}\n\n"
            f"📝 کپشن: {caption}\n"
            f"📁 نام فایل: {file_name}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ خطا در ذخیره فایل: {str(e)}")
        context.user_data.clear()

async def skip_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رد شدن از مرحله کپشن"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_USER_ID:
        return
    
    if context.user_data.get('upload_step') != 'waiting_for_caption':
        return

    # ذخیره با کپشن خالی
    file_id = context.user_data.get('temp_file_id')
    file_name = context.user_data.get('temp_file_name')

    if not file_id or not file_name:
        await update.message.reply_text("❌ خطا: اطلاعات فایل پیدا نشد! دوباره از اول تلاش کن.")
        context.user_data.clear()
        return

    try:
        unique_code = db.add_file(file_id, file_name, "")

        bot_username = (await context.bot.get_me()).username
        file_link = f"https://t.me/{bot_username}?start={unique_code}"

        context.user_data.clear()

        await update.message.reply_text(
            f"✅ فایل بدون کپشن ذخیره شد!\n\n"
            f"🔗 لینک اختصاصی فایل:\n{file_link}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ خطا در ذخیره فایل: {str(e)}")
        context.user_data.clear()

async def list_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش لیست فایل‌های آپلود شده به ادمین"""
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_USER_ID:
        await query.edit_message_text("⛔ شما اجازه دسترسی به این بخش را ندارید!")
        return

    files = db.get_all_files()
    if not files:
        await query.edit_message_text("📭 هنوز هیچ فایلی آپلود نشده.")
        return

    message = "📋 لیست فایل‌های آپلود شده:\n\n"
    for file in files[:10]:  # فقط 10 تای آخر
        code, name, views, date = file
        # کوتاه کردن اسم اگه طولانی بود
        short_name = name[:30] + "..." if len(name) > 30 else name
        message += f"• {short_name}\n  کد: {code} | 👁 {views} | 📅 {date[:10]}\n\n"

    await query.edit_message_text(message, parse_mode="Markdown")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """آمار کلی"""
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_USER_ID:
        await query.edit_message_text("⛔ شما اجازه دسترسی به این بخش را ندارید!")
        return

    # اینجا باید کانکشن دیتابیس رو دوباره تعریف کنی یا از db استفاده کنی
    import sqlite3
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), SUM(views) FROM files")
    result = cursor.fetchone()
    total_files = result[0] or 0
    total_views = result[1] or 0
    conn.close()

    stats_text = (
        f"📊 آمار کلی:\n\n"
        f"📁 تعداد فایل‌ها: {total_files}\n"
        f"👁 کل بازدیدها: {total_views}"
    )
    await query.edit_message_text(stats_text)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مدیریت کلیک روی دکمه‌های پنل ادمین"""
    query = update.callback_query
    await query.answer()

    if query.data == "upload":
        await admin_upload_callback(update, context)
    elif query.data == "list_files":
        await list_files(update, context)
    elif query.data == "stats":
        await stats(update, context)
# ================ راه‌اندازی ربات ================

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # دستورات عمومی
    application.add_handler(CommandHandler("start", start))

    # دستورات ادمین
    application.add_handler(CommandHandler("admin", admin_panel))

    # هندلر دکمه‌ها (این باید قبل از MessageHandlerها بیاد)
    application.add_handler(CallbackQueryHandler(button_handler))

    # هندلرهای مرحله‌ای آپلود (ترتیب مهمه!)
    # اول هندلر دریافت فایل
    application.add_handler(MessageHandler(
        filters.VIDEO | filters.Document.ALL | filters.PHOTO | filters.AUDIO | filters.ANIMATION, 
        handle_admin_file
    ))
    
    # بعد هندلر دریافت متن (کپشن)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_caption))
    
    # هندلر دستور /skip
    application.add_handler(CommandHandler("skip", skip_caption))

    print("🤖 ربات با موفقیت راه‌اندازی شد...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)