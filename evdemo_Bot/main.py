import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler

# ========== تنظیمات ==========
TOKEN = "8389739043:AAEbpGgRiQmCS8bb_BKeu6HJ6YcxXRUXspA"
GROUP_ID = -5136704878
ADMIN_IDS = [1621910796]

# قیمت‌های پیش‌فرض
DEFAULT_PRICES = {
    ("ضربدری سه نفره", "بخش بافنده"): 1200,
    ("ضربدری سه نفره", "بخش سارمازن"): 450,
    ("ضربدری سه نفره", "بخش گیس‌زن"): 450,
    ("ضربدری سه نفره", "بخش پوف‌زن"): 115,
    ("لوزی سه نفره", "بخش بافنده"): 1300,
    ("لوزی سه نفره", "بخش سارمازن"): 450,
    ("لوزی سه نفره", "بخش گیس‌زن"): 450,
    ("لوزی سه نفره", "بخش پوف‌زن"): 115,
    ("ضربدری دونفره", "بخش بافنده"): 1050,
    ("ضربدری دونفره", "بخش سارمازن"): 400,
    ("ضربدری دونفره", "بخش گیس‌زن"): 400,
    ("لوزی دونفره", "بخش بافنده"): 1200,
    ("لوزی دونفره", "بخش سارمازن"): 350,
    ("لوزی دونفره", "بخش گیس‌زن"): 350,
}

# ========== دیتابیس ==========
class Database:
    def __init__(self, db_file="stats.db"):
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                is_approved BOOLEAN DEFAULT 0,
                approved_by INTEGER,
                approved_at TIMESTAMP,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                date TEXT NOT NULL,
                section TEXT NOT NULL,
                model TEXT,
                sarma TEXT,
                count INTEGER,
                unit_price INTEGER,
                total_price INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model TEXT NOT NULL,
                section TEXT NOT NULL,
                price INTEGER NOT NULL,
                UNIQUE(model, section)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pending_requests (
                user_id INTEGER PRIMARY KEY,
                name TEXT,
                requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute("SELECT COUNT(*) FROM prices")
        if cursor.fetchone()[0] == 0:
            for (model, section), price in DEFAULT_PRICES.items():
                cursor.execute("INSERT INTO prices (model, section, price) VALUES (?, ?, ?)", (model, section, price))
        
        self.conn.commit()
    
    def add_pending_request(self, user_id, name):
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO pending_requests (user_id, name) VALUES (?, ?)", (user_id, name))
        self.conn.commit()
    
    def remove_pending_request(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM pending_requests WHERE user_id = ?", (user_id,))
        self.conn.commit()
    
    def get_pending_requests(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_id, name, requested_at FROM pending_requests")
        return cursor.fetchall()
    
    def approve_user(self, user_id, admin_id):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE users SET is_approved = 1, approved_by = ?, approved_at = CURRENT_TIMESTAMP WHERE user_id = ?", (admin_id, user_id))
        self.conn.commit()
        self.remove_pending_request(user_id)
    
    def reject_user(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        self.conn.commit()
        self.remove_pending_request(user_id)
    
    def add_user(self, user_id, name):
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (user_id, name, is_approved) VALUES (?, ?, 0)", (user_id, name))
        self.conn.commit()
    
    def is_user_approved(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT is_approved FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result and result[0] == 1
    
    def user_exists(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchone() is not None
    
    def get_user_name(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    
    def add_stat(self, user_id, date, section, model, sarma, count, unit_price, total_price):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO stats (user_id, date, section, model, sarma, count, unit_price, total_price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, date, section, model, sarma, count, unit_price, total_price))
        self.conn.commit()
        return cursor.lastrowid
    
    def get_user_stats(self, user_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, date, section, model, sarma, count, unit_price, total_price FROM stats WHERE user_id = ? ORDER BY id DESC", (user_id,))
        return cursor.fetchall()
    
    def get_user_today_total(self, user_id):
        today = datetime.now().strftime("%Y-%m-%d")
        cursor = self.conn.cursor()
        cursor.execute("SELECT SUM(total_price) FROM stats WHERE user_id = ? AND date LIKE ?", (user_id, f"{today}%"))
        result = cursor.fetchone()[0]
        return result or 0
    
    def get_price(self, model, section):
        cursor = self.conn.cursor()
        cursor.execute("SELECT price FROM prices WHERE model = ? AND section = ?", (model, section))
        result = cursor.fetchone()
        return result[0] if result else 115 if section == "بخش پوف‌زن" else 0
    
    def update_price(self, model, section, price):
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO prices (model, section, price) VALUES (?, ?, ?)", (model, section, price))
        self.conn.commit()
    
    def get_all_users(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_id, name, registered_at FROM users WHERE is_approved = 1")
        return cursor.fetchall()
    
    def get_all_stats(self, start_date=None, end_date=None):
        cursor = self.conn.cursor()
        if start_date and end_date:
            cursor.execute('''
                SELECT s.*, u.name FROM stats s
                JOIN users u ON s.user_id = u.user_id
                WHERE date BETWEEN ? AND ?
                ORDER BY s.id DESC
            ''', (start_date, end_date))
        else:
            cursor.execute('''
                SELECT s.*, u.name FROM stats s
                JOIN users u ON s.user_id = u.user_id
                ORDER BY s.id DESC
            ''')
        return cursor.fetchall()
    
    def close(self):
        self.conn.close()

# ========== توابع کمکی ==========
db = Database()
NAME, MENU, SECTION, SARMA, COUNT, MODEL, CONFIRM, EDIT_DATE = range(8)

def get_now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def get_today_date():
    return datetime.now().strftime("%Y-%m-%d")

def is_admin(user_id):
    return user_id in ADMIN_IDS

def get_model_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("ضربدری سه نفره", callback_data="model_ضربدری سه نفره"),
         InlineKeyboardButton("ضربدری دونفره", callback_data="model_ضربدری دونفره")],
        [InlineKeyboardButton("لوزی سه نفره", callback_data="model_لوزی سه نفره"),
         InlineKeyboardButton("لوزی دونفره", callback_data="model_لوزی دونفره")]
    ])

async def send_to_group(context, text, keyboard=None):
    await context.bot.send_message(chat_id=GROUP_ID, text=text, reply_markup=keyboard)

def export_to_text():
    stats = db.get_all_stats()
    if not stats:
        return None
    text = "📊 گزارش کامل آمار:\n\n"
    for stat in stats:
        text += f"📅 {stat[2]} | {stat[10]} | {stat[3]} | تعداد: {stat[6]} | {stat[8]:,} لیر\n"
    return text

# ========== منوی اصلی ==========
async def show_main_menu(update):
    user_id = update.effective_user.id
    today_total = db.get_user_today_total(user_id)
    
    keyboard = [
        ['➕ ثبت آمار جدید'],
        ['📊 مشاهده آمار گذشته'],
        ['💰 لیست قیمت‌ها'],
        ['🚪 انصراف']
    ]
    if is_admin(user_id):
        keyboard.append(['🔧 پنل ادمین'])
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    msg = f"🏠 صفحه اصلی\n\n💰 جمع دستمزد امروز شما: {today_total:,} لیر\n\nیکی از گزینه‌ها را انتخاب کنید:"
    
    if update.message:
        await update.message.reply_text(msg, reply_markup=reply_markup)
    else:
        await update.callback_query.message.reply_text(msg, reply_markup=reply_markup)
    return MENU

# ========== شروع و ثبت نام ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if db.user_exists(user_id):
        if db.is_user_approved(user_id):
            await update.message.reply_text(f"خوش برگشتی {db.get_user_name(user_id)} عزیز! 🎉")
            return await show_main_menu(update)
        else:
            await update.message.reply_text("⏳ درخواست شما در حال بررسی توسط مدیران است. لطفاً صبر کنید...")
            return ConversationHandler.END
    
    await update.message.reply_text("👋 سلام! به بات ثبت آمار خوش آمدی.\n\nلطفاً نام و نام خانوادگی خود را بنویسید:")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.message.text
    
    db.add_user(user_id, name)
    db.add_pending_request(user_id, name)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تأیید", callback_data=f"approve_{user_id}"),
         InlineKeyboardButton("❌ رد", callback_data=f"reject_{user_id}")]
    ])
    
    await send_to_group(
        context,
        f"🆕 درخواست عضویت جدید:\n\n👤 نام: {name}\n🆔 آیدی: {user_id}\n@{update.effective_user.username or 'ندارد'}\n\nلطفاً تصمیم بگیرید:",
        keyboard
    )
    
    await update.message.reply_text("✅ درخواست شما به مدیران ارسال شد. پس از تأیید، می‌توانید از بات استفاده کنید.\nلطفاً چند دقیقه دیگر مجدداً /start را بزنید.")
    return ConversationHandler.END

async def handle_admin_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.edit_message_text("⛔ شما دسترسی ندارید!")
        return
    
    data = query.data
    user_id = int(data.split('_')[1])
    
    if data.startswith("approve"):
        db.approve_user(user_id, query.from_user.id)
        await query.edit_message_text(f"✅ کاربر {db.get_user_name(user_id)} تأیید شد.")
        try:
            await context.bot.send_message(user_id, "🎬 درخواست شما تأیید شد! حالا می‌توانید از بات استفاده کنید. دوباره /start بزنید.")
        except:
            pass
    else:
        db.reject_user(user_id)
        await query.edit_message_text(f"❌ کاربر رد شد.")

# ========== منوی اصلی و مدیریت ==========
async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if text == '➕ ثبت آمار جدید':
        keyboard = [
            [InlineKeyboardButton("بخش سارمازن", callback_data="بخش سارمازن"),
             InlineKeyboardButton("بخش بافنده", callback_data="بخش بافنده")],
            [InlineKeyboardButton("بخش گیس‌زن", callback_data="بخش گیس‌زن"),
             InlineKeyboardButton("بخش پوف‌زن", callback_data="بخش پوف‌زن")]
        ]
        await update.message.reply_text("کدوم بخش کار کردی؟", reply_markup=InlineKeyboardMarkup(keyboard))
        return SECTION
        
    elif text == '📊 مشاهده آمار گذشته':
        stats = db.get_user_stats(user_id)
        if not stats:
            await update.message.reply_text("📭 هنوز هیچ آماری ثبت نکردی!")
            return MENU
        
        report = "📜 سوابق آمار شما:\n\n"
        for stat in stats[:10]:
            report += f"🆔 #{stat[0]}\n📅 {stat[1]}\n📍 {stat[2]}\n"
            if stat[4]:
                report += f"🎨 {stat[3]}\n🔖 {stat[4]}\n"
            report += f"🔢 {stat[5]} عدد\n💰 {stat[7]:,} لیر\n➖➖➖➖➖➖\n"
        
        report += f"\n📊 مجموع کل: {sum(s[7] for s in stats):,} لیر"
        keyboard = [[InlineKeyboardButton("🏠 برگشت", callback_data="back_to_main")]]
        await update.message.reply_text(report, reply_markup=InlineKeyboardMarkup(keyboard))
        return MENU
        
    elif text == '💰 لیست قیمت‌ها':
        price_list = "💰 لیست قیمت‌ها (لیر)\n\n"
        price_list += "🔸 ضربدری سه نفره: بافت ۱۲۰۰ | سارما ۴۵۰ | گیس ۴۵۰\n"
        price_list += "🔸 لوزی سه نفره: بافت ۱۳۰۰ | سارما ۴۵۰ | گیس ۴۵۰\n"
        price_list += "🔸 ضربدری دونفره: بافت ۱۰۵۰ | سارما ۴۰۰ | گیس ۴۰۰\n"
        price_list += "🔸 لوزی دونفره: بافت ۱۲۰۰ | سارما ۳۵۰ | گیس ۳۵۰\n"
        price_list += "🔸 پوف (همه مدل‌ها): ۱۱۵"
        await update.message.reply_text(price_list)
        return MENU
        
    elif text == '🔧 پنل ادمین' and is_admin(user_id):
        keyboard = [
            [InlineKeyboardButton("👥 لیست کاربران", callback_data="admin_users")],
            [InlineKeyboardButton("⏳ درخواست‌ها", callback_data="admin_pending")],
            [InlineKeyboardButton("📊 گزارش امروز", callback_data="admin_today")],
            [InlineKeyboardButton("📈 گزارش هفته", callback_data="admin_week")],
            [InlineKeyboardButton("📅 گزارش ماه", callback_data="admin_month")],
            [InlineKeyboardButton("📎 خروجی متن", callback_data="admin_export")],
            [InlineKeyboardButton("🏠 برگشت", callback_data="back_to_main")]
        ]
        await update.message.reply_text("🔧 پنل مدیریت:", reply_markup=InlineKeyboardMarkup(keyboard))
        return MENU
        
    elif text == '🚪 انصراف':
        await update.message.reply_text("👋 خداحافظ! برای استفاده مجدد /start بزن.")
        return ConversationHandler.END
    
    else:
        await update.message.reply_text("لطفاً از دکمه‌های منو استفاده کنید!")
        return MENU

async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if query.data == "back_to_main":
        return await show_main_menu(update)
    
    elif query.data == "admin_users" and is_admin(user_id):
        users = db.get_all_users()
        text = "👥 لیست کاربران:\n\n" + "\n".join([f"🆔 {u[0]} | {u[1]}" for u in users]) if users else "هیچ کاربری نیست"
        await query.message.reply_text(text)
        return MENU
    
    elif query.data == "admin_pending" and is_admin(user_id):
        pending = db.get_pending_requests()
        text = "⏳ درخواست‌ها:\n\n" + "\n".join([f"🆔 {p[0]} | {p[1]}" for p in pending]) if pending else "هیچ درخواستی نیست"
        await query.message.reply_text(text)
        return MENU
    
    elif query.data in ["admin_today", "admin_week", "admin_month"] and is_admin(user_id):
        today = get_today_date()
        if query.data == "admin_today":
            start_date = end_date = today
            title = "گزارش امروز"
        elif query.data == "admin_week":
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            end_date = today
            title = "گزارش این هفته"
        else:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            end_date = today
            title = "گزارش این ماه"
        
        stats = db.get_all_stats(start_date, end_date)
        if not stats:
            await query.message.reply_text(f"{title}: آماری وجود ندارد.")
        else:
            total_money = sum(s[8] for s in stats)
            total_count = sum(s[6] for s in stats)
            text = f"{title}\n\nتعداد گزارش‌ها: {len(stats)}\nکل تولید: {total_count} عدد\nکل دستمزد: {total_money:,} لیر"
            await query.message.reply_text(text)
        return MENU
    
    elif query.data == "admin_export" and is_admin(user_id):
        text_report = export_to_text()
        if text_report:
            if len(text_report) > 4000:
                parts = [text_report[i:i+4000] for i in range(0, len(text_report), 4000)]
                for part in parts:
                    await query.message.reply_text(part)
            else:
                await query.message.reply_text(text_report)
        else:
            await query.message.reply_text("آماری وجود ندارد.")
        return MENU

# ========== ثبت آمار ==========
async def section_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['current_section'] = query.data
    
    if query.data == "بخش پوف‌زن":
        context.user_data['current_model'] = None
        context.user_data['current_sarma'] = None
        await query.edit_message_text(f"📍 {query.data} انتخاب شد.\n\nچند تا کار انجام دادی؟ (عدد بفرست)")
        return COUNT
    
    if query.data in ("بخش سارمازن", "بخش گیس‌زن"):
        context.user_data['current_sarma'] = None
        await query.edit_message_text(f"📍 {query.data} انتخاب شد.\n\nچند تا تاکیم زدی؟ (عدد بفرست)")
        return COUNT
    
    keyboard = [[InlineKeyboardButton("✅ سارما شده", callback_data="sarma_شده"), InlineKeyboardButton("❌ سارما نشده", callback_data="sarma_نشده")]]
    await query.edit_message_text(f"📍 {query.data} انتخاب شد.\n\nتاکیم‌ها سارما شده یا نشده؟", reply_markup=InlineKeyboardMarkup(keyboard))
    return SARMA

async def sarma_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['current_sarma'] = "سارما شده" if query.data == "sarma_شده" else "سارما نشده"
    await query.edit_message_text(f"📍 {context.user_data['current_section']}\n🔖 {context.user_data['current_sarma']}\n\nچند تا تاکیم زدی؟ (عدد بفرست)")
    return COUNT

async def get_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.text.isdigit():
        await update.message.reply_text("بی‌زحمت فقط عدد بفرست!")
        return COUNT
    
    context.user_data['temp_count'] = int(update.message.text)
    section = context.user_data['current_section']
    
    if section == "بخش پوف‌زن":
        total_price = 115 * int(update.message.text)
        keyboard = [[InlineKeyboardButton("✅ تایید", callback_data="confirm_all")], [InlineKeyboardButton("✏️ اصلاح عدد", callback_data="edit_count")], [InlineKeyboardButton("📅 تغییر تاریخ", callback_data="edit_date")]]
        await update.message.reply_text(f"📋 خلاصه:\n📍 {section}\n🔢 {update.message.text} عدد\n💰 جمع: {total_price:,} لیر\n\nتایید می‌کنی؟", reply_markup=InlineKeyboardMarkup(keyboard))
        return CONFIRM
    
    await update.message.reply_text(f"✅ تعداد {update.message.text} تاکیم ثبت شد.\n\nحالا مدل رو انتخاب کن:", reply_markup=get_model_keyboard())
    return MODEL

async def model_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    model = query.data.replace("model_", "")
    context.user_data['current_model'] = model
    
    count = context.user_data['temp_count']
    section = context.user_data['current_section']
    sarma = context.user_data.get('current_sarma', '')
    unit_price = db.get_price(model, section)
    total_price = unit_price * count
    sarma_line = f"\n🔖 {sarma}" if sarma else ""
    
    keyboard = [[InlineKeyboardButton("✅ تایید", callback_data="confirm_all")], [InlineKeyboardButton("✏️ اصلاح عدد", callback_data="edit_count")], [InlineKeyboardButton("🔄 تغییر مدل", callback_data="change_model")], [InlineKeyboardButton("📅 تغییر تاریخ", callback_data="edit_date")]]
    await query.edit_message_text(f"📋 خلاصه:\n📍 {section}{sarma_line}\n🔢 {count}\n🎨 {model}\n💰 جمع: {total_price:,} لیر\n\nتایید می‌کنی؟", reply_markup=InlineKeyboardMarkup(keyboard))
    return CONFIRM

async def edit_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📅 تاریخ را به فرمت YYYY-MM-DD وارد کن:\nمثال: 2024-01-15")
    return EDIT_DATE

async def get_edited_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        datetime.strptime(update.message.text.strip(), "%Y-%m-%d")
        context.user_data['edited_date'] = update.message.text.strip()
        await update.message.reply_text(f"✅ تاریخ تغییر کرد. دوباره تایید کن:")
        
        count = context.user_data['temp_count']
        section = context.user_data['current_section']
        model = context.user_data.get('current_model')
        unit_price = db.get_price(model or '', section) if model else 115
        total_price = unit_price * count
        
        keyboard = [[InlineKeyboardButton("✅ تایید نهایی", callback_data="confirm_all")]]
        await update.message.reply_text(f"📋 خلاصه با تاریخ جدید:\n📍 {section}\n🔢 {count}\n💰 جمع: {total_price:,} لیر", reply_markup=InlineKeyboardMarkup(keyboard))
        return CONFIRM
    except:
        await update.message.reply_text("❌ فرمت اشتباه! مثلاً: 2024-01-15")
        return EDIT_DATE

async def confirm_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if query.data == "confirm_all":
        count = context.user_data['temp_count']
        section = context.user_data['current_section']
        model = context.user_data.get('current_model')
        sarma = context.user_data.get('current_sarma')
        
        if context.user_data.get('edited_date'):
            now = context.user_data['edited_date'] + datetime.now().strftime(" %H:%M:%S")
        else:
            now = get_now()
        
        unit_price = db.get_price(model or '', section)
        total_price = unit_price * count
        db.add_stat(user_id, now, section, model, sarma, count, unit_price, total_price)
        
        sarma_line = f"\n🔖 {sarma}" if sarma else ""
        model_line = f"\n🎨 {model}" if model else ""
        
        await query.edit_message_text(f"✅ ثبت شد!\n📍 {section}{sarma_line}{model_line}\n🔢 {count}\n💰 {total_price:,} لیر\n⏰ {now}\n\nخسته نباشی 🌹", reply_markup=None)
        
        report = f"🔔 گزارش جدید:\n👤 {db.get_user_name(user_id)}\n📍 {section}{sarma_line}{model_line}\n🔢 {count}\n💰 {total_price:,} لیر\n⏰ {now}"
        await context.bot.send_message(chat_id=GROUP_ID, text=report)
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=admin_id, text=report)
            except:
                pass
        
        keyboard = [[InlineKeyboardButton("🏠 منوی اصلی", callback_data="back_to_main")]]
        await query.message.reply_text("برای ادامه:", reply_markup=InlineKeyboardMarkup(keyboard))
        context.user_data.clear()
        return MENU
    
    elif query.data == "edit_count":
        await query.edit_message_text("✏️ عدد درست رو بفرست:")
        return COUNT
    elif query.data == "change_model":
        await query.edit_message_text("🔄 مدل رو دوباره انتخاب کن:", reply_markup=get_model_keyboard())
        return MODEL
    elif query.data == "edit_date":
        await query.edit_message_text("📅 تاریخ جدید رو وارد کن:")
        return EDIT_DATE

# ========== دستورات ادمین ==========
async def admin_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ دسترسی ندارید!")
        return
    
    text = update.message.text.lower()
    if text == "/users":
        users = db.get_all_users()
        await update.message.reply_text("\n".join([f"{u[0]} | {u[1]}" for u in users]) if users else "هیچ کاربری نیست")
    elif text.startswith("/setprice"):
        try:
            parts = update.message.text.split()
            if len(parts) != 4:
                await update.message.reply_text("فرمت: /setprice <مدل> <بخش> <قیمت>\nمثال: /setprice ضربدری سه نفره بخش بافنده 1300")
                return
            db.update_price(parts[1], parts[2], int(parts[3]))
            await update.message.reply_text(f"✅ قیمت تغییر کرد.")
        except:
            await update.message.reply_text("❌ خطا!")

# ========== اجرای اصلی ==========
def main():
    app = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu), CallbackQueryHandler(handle_menu_callback, pattern="^(back_to_main|admin_.*)$")],
            SECTION: [CallbackQueryHandler(section_choice)],
            SARMA: [CallbackQueryHandler(sarma_choice, pattern="^sarma_")],
            COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_count)],
            MODEL: [CallbackQueryHandler(model_choice, pattern="^model_")],
            CONFIRM: [CallbackQueryHandler(confirm_stats, pattern="^(confirm_all|edit_count|change_model|edit_date)$")],
            EDIT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_edited_date)],
        },
        fallbacks=[CommandHandler('start', start)],
    )
    
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(handle_admin_approval, pattern="^(approve|reject)_"))
    app.add_handler(CommandHandler("users", admin_commands))
    app.add_handler(CommandHandler("setprice", admin_commands))
    
    print("✅ بات روشن شد!")
    app.run_polling()

if __name__ == '__main__':
    main()