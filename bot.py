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

# ── БАЗА ДАННЫХ ───────────────────────────────────────
def load_data() -> dict:
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки: {e}")
    return {"phones": [], "telegram_ids": [], "admins": []}

def save_data(data: dict):
    try:
        with open(USERS_FILE, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")

def is_super_admin(uid): return SUPER_ADMIN_ID != 0 and uid == SUPER_ADMIN_ID
def is_admin(uid):
    if is_super_admin(uid): return True
    return uid in load_data().get("admins", [])
def is_allowed(uid, phone=None):
    if is_admin(uid): return True
    data = load_data()
    if uid in data.get("telegram_ids", []): return True
    if phone:
        clean = phone.strip().lstrip("+").replace(" ","").replace("-","")
        return clean in [p.lstrip("+").replace(" ","") for p in data.get("phones",[])]
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

Для получения доступа нажмите кнопку ниже 👇\
"""

GRANTED_TEXT = """\
✅ *Доступ открыт!*

━━━━━━━━━━━━━━━━━━━━━━
🎓 *Курс «Бизнес Операционная Система»*
👤 *Александр Высоцкий*
━━━━━━━━━━━━━━━━━━━━━━

Нажмите кнопку ниже чтобы начать обучение 👇\
"""

DENIED_TEXT = """\
🔒 *Доступ закрыт*

━━━━━━━━━━━━━━━━━━━━━━

Ваш номер не найден в списке участников курса.

Если это ошибка — обратитесь к организатору.\
"""

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

# ── КОМАНДЫ АДМИНИСТРАТОРА ────────────────────────────
async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав администратора.")
        return
    if not context.args:
        await update.message.reply_text(
            "Использование:\n"
            "/add +998901234567 — по номеру телефона\n"
            "/add 123456789 — по Telegram ID"
        )
        return
    arg = context.args[0].strip()
    data = load_data()
    if arg.startswith("+") or (arg.isdigit() and len(arg) > 10):
        clean = arg.lstrip("+").replace(" ","").replace("-","")
        if clean not in data["phones"]:
            data["phones"].append(clean)
            save_data(data)
            await update.message.reply_text(f"✅ Номер +{clean} добавлен. Всего: {len(data['phones'])}")
        else:
            await update.message.reply_text(f"ℹ️ Номер +{clean} уже в списке.")
    elif arg.isdigit():
        tid = int(arg)
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
    if not context.args:
        await update.message.reply_text("Использование: /remove +998901234567 или /remove 123456789")
        return
    arg = context.args[0].strip()
    data = load_data()
    if arg.startswith("+") or (arg.isdigit() and len(arg) > 10):
        clean = arg.lstrip("+").replace(" ","")
        if clean in data["phones"]:
            data["phones"].remove(clean)
            save_data(data)
            await update.message.reply_text(f"✅ Номер +{clean} удалён.")
        else:
            await update.message.reply_text(f"ℹ️ Номер +{clean} не найден.")
    elif arg.isdigit():
        tid = int(arg)
        if tid in data["telegram_ids"]:
            data["telegram_ids"].remove(tid)
            save_data(data)
            await update.message.reply_text(f"✅ ID {tid} удалён.")
        else:
            await update.message.reply_text(f"ℹ️ ID {tid} не найден.")

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав администратора.")
        return
    data = load_data()
    phones = data.get("phones", [])
    tids = data.get("telegram_ids", [])
    admins = data.get("admins", [])
    text = "📋 *Список доступа*\n\n"
    text += f"📱 *Номера* ({len(phones)}):\n"
    for p in phones: text += f"  +{p}\n"
    text += f"\n🆔 *Telegram ID* ({len(tids)}):\n"
    for t in tids: text += f"  {t}\n"
    text += f"\n👑 *Администраторы* ({len(admins)+1}):\n"
    text += f"  {SUPER_ADMIN_ID} (главный)\n"
    for a in admins: text += f"  {a}\n"
    if not phones and not tids:
        text += "\n_Участников нет_"
    await update.message.reply_text(text, parse_mode="Markdown")

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_super_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только главный администратор может добавлять админов.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Использование: /addadmin 123456789")
        return
    tid = int(context.args[0])
    data = load_data()
    if tid not in data["admins"]:
        data["admins"].append(tid)
        save_data(data)
        await update.message.reply_text(f"✅ ID {tid} назначен администратором.")
    else:
        await update.message.reply_text(f"ℹ️ ID {tid} уже администратор.")

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_super_admin(update.effective_user.id):
        await update.message.reply_text("❌ Только главный администратор может удалять админов.")
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Использование: /removeadmin 123456789")
        return
    tid = int(context.args[0])
    data = load_data()
    if tid in data["admins"]:
        data["admins"].remove(tid)
        save_data(data)
        await update.message.reply_text(f"✅ ID {tid} удалён из администраторов.")
    else:
        await update.message.reply_text(f"ℹ️ ID {tid} не найден.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_super_admin(uid):
        text = (
            "👑 *Команды главного администратора:*\n\n"
            "/add +998XXXXXXXXX — добавить по номеру\n"
            "/add 123456789 — добавить по Telegram ID\n"
            "/remove +998XXXXXXXXX — удалить участника\n"
            "/list — список участников и админов\n"
            "/addadmin 123456789 — назначить администратора\n"
            "/removeadmin 123456789 — снять администратора\n"
            "/start — открыть курс\n"
        )
    elif is_admin(uid):
        text = (
            "🛠 *Команды администратора:*\n\n"
            "/add +998XXXXXXXXX — добавить по номеру\n"
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
