import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://kslmvv.github.io/bos-course/")
SUPER_ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
USERS_FILE = "/tmp/allowed_users.json"

def load_data():
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки: {e}")
    return {"phones": [], "telegram_ids": [], "admins": [], "admin_phones": []}

def save_data(data):
    try:
        with open(USERS_FILE, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")

def clean_phone(raw):
    """Очищаем номер от пробелов, тире, плюса"""
    return raw.replace(" ", "").replace("-", "").lstrip("+")

def is_phone(raw):
    """Это номер телефона или ID?"""
    c = clean_phone(raw)
    return c.isdigit() and len(c) >= 7 and (raw.strip().startswith("+") or len(c) > 10)

def is_super_admin(uid):
    return SUPER_ADMIN_ID != 0 and uid == SUPER_ADMIN_ID

def is_admin(uid):
    if is_super_admin(uid): return True
    data = load_data()
    return uid in data.get("admins", [])

def is_admin_phone(phone):
    clean = clean_phone(phone)
    data = load_data()
    return clean in [clean_phone(p) for p in data.get("admin_phones", [])]

def is_allowed(uid, phone=None):
    if is_admin(uid): return True
    data = load_data()
    if uid in data.get("telegram_ids", []): return True
    if phone:
        c = clean_phone(phone)
        return c in [clean_phone(p) for p in data.get("phones", [])]
    return False

# ── ТЕКСТЫ ────────────────────────────────────────────
WELCOME_TEXT = """\
🎓 *Добро пожаловать!*

━━━━━━━━━━━━━━━━━━━━━━
📚 *Курс «Бизнес Операционная Система»*
👤 *Автор:* Александр Высоцкий
━━━━━━━━━━━━━━━━━━━━━━

Этот курс поможет вам:
✅ Выстроить систему управления бизнесом
✅ Освободиться от операционки
✅ Масштабировать компанию без хаоса

Для получения доступа нажмите кнопку ниже 👇"""

GRANTED_TEXT = """\
✅ *Доступ открыт!*

━━━━━━━━━━━━━━━━━━━━━━
🎓 *Курс «Бизнес Операционная Система»*
👤 *Александр Высоцкий*
━━━━━━━━━━━━━━━━━━━━━━

Нажмите кнопку ниже чтобы начать обучение 👇"""

DENIED_TEXT = """\
🔒 *Доступ закрыт*

━━━━━━━━━━━━━━━━━━━━━━

Ваш номер не найден в списке участников курса.

Если это ошибка — обратитесь к организатору."""

# ── ПОЛЬЗОВАТЕЛЬ ─────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_allowed(uid):
        await send_course_button(update)
        return
    keyboard = [[KeyboardButton("📱 Поделиться номером", request_contact=True)]]
    await update.message.reply_text(
        WELCOME_TEXT, parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    )

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    if not contact: return
    phone = contact.phone_number
    uid = update.effective_user.id
    await update.message.reply_text("🔍 Проверяю доступ...", reply_markup=ReplyKeyboardRemove())
    if is_allowed(uid, phone):
        data = load_data()
        # Если номер в admin_phones — даём права админа
        if is_admin_phone(phone) and uid not in data.get("admins", []):
            if "admins" not in data: data["admins"] = []
            data["admins"].append(uid)
        if uid not in data["telegram_ids"]:
            data["telegram_ids"].append(uid)
        save_data(data)
        await send_course_button(update)
    else:
        await update.message.reply_text(DENIED_TEXT, parse_mode="Markdown")

async def send_course_button(update: Update):
    keyboard = [[InlineKeyboardButton("📚 Открыть курс", web_app=WebAppInfo(url=WEBAPP_URL))]]
    await update.message.reply_text(
        GRANTED_TEXT, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ── ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ───────────────────────────
def parse_arg(context):
    """Склеиваем все аргументы — для номеров с пробелами"""
    if not context.args:
        return None
    return "".join(context.args).strip()

# ── КОМАНДЫ АДМИНИСТРАТОРА ────────────────────────────
async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав администратора.")
        return
    arg = parse_arg(context)
    if not arg:
        await update.message.reply_text(
            "Использование:\n"
            "/add +998901234567 — по номеру\n"
            "/add 123456789 — по Telegram ID"
        )
        return
    data = load_data()
    if is_phone(arg):
        c = clean_phone(arg)
        if c not in data["phones"]:
            data["phones"].append(c)
            save_data(data)
            await update.message.reply_text(f"✅ Номер +{c} добавлен. Всего: {len(data['phones'])}")
        else:
            await update.message.reply_text(f"ℹ️ Номер +{c} уже в списке.")
    else:
        c = clean_phone(arg)
        if c.isdigit():
            tid = int(c)
            if tid not in data["telegram_ids"]:
                data["telegram_ids"].append(tid)
                save_data(data)
                await update.message.reply_text(f"✅ ID {tid} добавлен. Всего: {len(data['telegram_ids'])}")
            else:
                await update.message.reply_text(f"ℹ️ ID {tid} уже в списке.")
        else:
            await update.message.reply_text("❌ Формат: /add +998901234567 или /add 123456789")

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав администратора.")
        return
    arg = parse_arg(context)
    if not arg:
        await update.message.reply_text("Использование: /remove +998901234567 или /remove 123456789")
        return
    data = load_data()
    if is_phone(arg):
        c = clean_phone(arg)
        if c in data["phones"]:
            data["phones"].remove(c)
            save_data(data)
            await update.message.reply_text(f"✅ Номер +{c} удалён.")
        else:
            await update.message.reply_text(f"ℹ️ Номер +{c} не найден.")
    else:
        c = clean_phone(arg)
        if c.isdigit():
            tid = int(c)
            if tid in data["telegram_ids"]:
                data["telegram_ids"].remove(tid)
                save_data(data)
                await update.message.reply_text(f"✅ ID {tid} удалён.")
            else:
                await update.message.reply_text(f"ℹ️ ID {tid} не найден.")
        else:
            await update.message.reply_text("❌ Формат: /remove +998901234567 или /remove 123456789")

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав администратора.")
        return
    data = load_data()
    phones = data.get("phones", [])
    tids = data.get("telegram_ids", [])
    admins = data.get("admins", [])
    admin_phones = data.get("admin_phones", [])
    text = "📋 *Список доступа*\n\n"
    text += f"📱 *Участники по номеру* ({len(phones)}):\n"
    for p in phones: text += f"  +{p}\n"
    text += f"\n🆔 *Участники по ID* ({len(tids)}):\n"
    for t in tids: text += f"  {t}\n"
    text += f"\n👑 *Администраторы* ({len(admins)+len(admin_phones)+1}):\n"
    text += f"  {SUPER_ADMIN_ID} (главный)\n"
    for a in admins: text += f"  {a}\n"
    for p in admin_phones: text += f"  +{p} (по номеру)\n"
    if not phones and not tids:
        text += "\n_Участников нет_"
    await update.message.reply_text(text, parse_mode="Markdown")

# ── КОМАНДЫ ТОЛЬКО ДЛЯ СУПЕР-АДМИНА ─────────────────
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_super_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только главный администратор может добавлять админов.")
        return
    arg = parse_arg(context)
    if not arg:
        await update.message.reply_text(
            "Использование:\n"
            "/addadmin +998901234567 — по номеру телефона\n"
            "/addadmin 123456789 — по Telegram ID"
        )
        return
    data = load_data()
    if "admin_phones" not in data: data["admin_phones"] = []
    if "admins" not in data: data["admins"] = []

    if is_phone(arg):
        c = clean_phone(arg)
        if c not in data["admin_phones"]:
            data["admin_phones"].append(c)
            save_data(data)
            await update.message.reply_text(
                f"✅ Номер +{c} назначен администратором.\n"
                f"Когда пользователь войдёт — получит права админа."
            )
        else:
            await update.message.reply_text(f"ℹ️ Номер +{c} уже администратор.")
    else:
        c = clean_phone(arg)
        if c.isdigit():
            tid = int(c)
            if tid not in data["admins"]:
                data["admins"].append(tid)
                save_data(data)
                await update.message.reply_text(f"✅ ID {tid} назначен администратором.")
            else:
                await update.message.reply_text(f"ℹ️ ID {tid} уже администратор.")
        else:
            await update.message.reply_text("❌ Формат: /addadmin +998901234567 или /addadmin 123456789")

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_super_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только главный администратор может удалять админов.")
        return
    arg = parse_arg(context)
    if not arg:
        await update.message.reply_text(
            "Использование:\n"
            "/removeadmin +998901234567 — по номеру\n"
            "/removeadmin 123456789 — по Telegram ID"
        )
        return
    data = load_data()
    if is_phone(arg):
        c = clean_phone(arg)
        admin_phones = data.get("admin_phones", [])
        if c in admin_phones:
            admin_phones.remove(c)
            data["admin_phones"] = admin_phones
            save_data(data)
            await update.message.reply_text(f"✅ Номер +{c} удалён из администраторов.")
        else:
            await update.message.reply_text(f"ℹ️ Номер +{c} не найден в администраторах.")
    else:
        c = clean_phone(arg)
        if c.isdigit():
            tid = int(c)
            if tid in data.get("admins", []):
                data["admins"].remove(tid)
                save_data(data)
                await update.message.reply_text(f"✅ ID {tid} удалён из администраторов.")
            else:
                await update.message.reply_text(f"ℹ️ ID {tid} не найден.")
        else:
            await update.message.reply_text("❌ Формат: /removeadmin +998901234567 или /removeadmin 123456789")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_super_admin(uid):
        text = (
            "👑 *Команды главного администратора:*\n\n"
            "/add +998XXXXXXXXX — добавить участника по номеру\n"
            "/add 123456789 — добавить по Telegram ID\n"
            "/remove +998XXXXXXXXX — удалить участника\n"
            "/list — список участников и админов\n"
            "/addadmin +998XXXXXXXXX — назначить админа по номеру\n"
            "/addadmin 123456789 — назначить админа по ID\n"
            "/removeadmin +998XXXXXXXXX — снять админа\n"
            "/start — открыть курс\n"
        )
    elif is_admin(uid):
        text = (
            "🛠 *Команды администратора:*\n\n"
            "/add +998XXXXXXXXX — добавить участника по номеру\n"
            "/add 123456789 — добавить по Telegram ID\n"
            "/remove +998XXXXXXXXX — удалить участника\n"
            "/list — список участников\n"
            "/start — открыть курс\n"
        )
    else:
        text = "📚 Напишите /start чтобы получить доступ к курсу."
    await update.message.reply_text(text, parse_mode="Markdown")

def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не задан!")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("add", add_user))
    app.add_handler(CommandHandler("remove", remove_user))
    app.add_handler(CommandHandler("list", list_users))
    app.add_handler(CommandHandler("addadmin", add_admin))
    app.add_handler(CommandHandler("removeadmin", remove_admin))
    app.add_handler(MessageHandler(filters.CONTACT, contact_handler))
    logger.info(f"Бот запущен. Super Admin: {SUPER_ADMIN_ID}")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
