import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://kslmvv.github.io/bos-course/")

# Ваш Telegram ID — только вы можете добавлять/удалять пользователей
# Узнать свой ID: написать @userinfobot
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

# Файл для хранения разрешённых пользователей
USERS_FILE = "/tmp/allowed_users.json"

# ── БАЗА ПОЛЬЗОВАТЕЛЕЙ ────────────────────────────────
def load_users() -> dict:
    """Загружаем базу пользователей"""
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки users: {e}")
    return {"phones": [], "telegram_ids": []}

def save_users(data: dict):
    """Сохраняем базу пользователей"""
    try:
        with open(USERS_FILE, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения users: {e}")

def is_admin(user_id: int) -> bool:
    return ADMIN_ID != 0 and user_id == ADMIN_ID

def is_allowed_id(telegram_id: int) -> bool:
    """Проверяем Telegram ID"""
    if ADMIN_ID != 0 and telegram_id == ADMIN_ID:
        return True
    data = load_users()
    return telegram_id in data.get("telegram_ids", [])

def is_allowed_phone(phone: str) -> bool:
    """Проверяем номер телефона"""
    clean = phone.strip().lstrip("+").replace(" ", "").replace("-", "")
    data = load_users()
    return clean in [p.lstrip("+").replace(" ", "") for p in data.get("phones", [])]

# ── ТЕКСТЫ ────────────────────────────────────────────
WELCOME_TEXT = """👋 *Добро пожаловать!*

📚 *Курс «Бизнес Операционная Система»*
_от Александра Высоцкого_

Для получения доступа поделитесь своим номером телефона 👇"""

GRANTED_TEXT = """✅ *Доступ открыт!*

Добро пожаловать на курс *«Бизнес Операционная Система»* от Александра Высоцкого.

Нажмите кнопку ниже чтобы начать обучение 👇"""

DENIED_TEXT = """🔒 *Доступ закрыт*

Ваш номер не найден в списке участников курса.

Если это ошибка — обратитесь к организатору."""

# ── КОМАНДЫ ПОЛЬЗОВАТЕЛЯ ─────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Проверяем по Telegram ID сразу
    if is_allowed_id(user_id):
        await send_course_button(update)
        return

    # Запрашиваем номер телефона
    keyboard = [[KeyboardButton("📱 Поделиться номером", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        WELCOME_TEXT,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получили контакт — проверяем доступ"""
    contact = update.message.contact
    if not contact:
        return

    phone = contact.phone_number
    user_id = update.effective_user.id
    logger.info(f"Контакт: {phone}, user_id: {user_id}")

    await update.message.reply_text("🔍 Проверяю доступ...", reply_markup=ReplyKeyboardRemove())

    if is_allowed_phone(phone) or is_allowed_id(user_id):
        # Добавляем Telegram ID чтобы в следующий раз не спрашивать номер
        data = load_users()
        if user_id not in data["telegram_ids"]:
            data["telegram_ids"].append(user_id)
            save_users(data)
        await send_course_button(update)
    else:
        await update.message.reply_text(DENIED_TEXT, parse_mode="Markdown")

async def send_course_button(update: Update):
    keyboard = [[InlineKeyboardButton("📚 Открыть курс", web_app=WebAppInfo(url=WEBAPP_URL))]]
    await update.message.reply_text(
        GRANTED_TEXT,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ── КОМАНДЫ АДМИНИСТРАТОРА ────────────────────────────
async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавить пользователя: /add +998901234567 или /add @username"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав администратора.")
        return

    if not context.args:
        await update.message.reply_text(
            "Использование:\n"
            "/add +998901234567 — добавить по номеру\n"
            "/add 123456789 — добавить по Telegram ID\n\n"
            "Чтобы узнать Telegram ID пользователя — попросите их переслать сообщение боту @userinfobot"
        )
        return

    arg = context.args[0].strip()
    data = load_users()

    # Определяем что добавляем — номер или ID
    if arg.startswith("+") or (arg.isdigit() and len(arg) > 10):
        # Это номер телефона
        clean = arg.lstrip("+").replace(" ", "").replace("-", "")
        if clean not in data["phones"]:
            data["phones"].append(clean)
            save_users(data)
            await update.message.reply_text(f"✅ Номер +{clean} добавлен.\nВсего номеров: {len(data['phones'])}")
        else:
            await update.message.reply_text(f"ℹ️ Номер +{clean} уже в списке.")
    elif arg.isdigit():
        # Это Telegram ID
        tid = int(arg)
        if tid not in data["telegram_ids"]:
            data["telegram_ids"].append(tid)
            save_users(data)
            await update.message.reply_text(f"✅ Telegram ID {tid} добавлен.\nВсего ID: {len(data['telegram_ids'])}")
        else:
            await update.message.reply_text(f"ℹ️ ID {tid} уже в списке.")
    else:
        await update.message.reply_text("❌ Неверный формат.\nИспользуйте: /add +998901234567 или /add 123456789")

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удалить пользователя: /remove +998901234567"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав администратора.")
        return

    if not context.args:
        await update.message.reply_text("Использование: /remove +998901234567 или /remove 123456789")
        return

    arg = context.args[0].strip()
    data = load_users()

    if arg.startswith("+") or (arg.isdigit() and len(arg) > 10):
        clean = arg.lstrip("+").replace(" ", "")
        if clean in data["phones"]:
            data["phones"].remove(clean)
            save_users(data)
            await update.message.reply_text(f"✅ Номер +{clean} удалён.")
        else:
            await update.message.reply_text(f"ℹ️ Номер +{clean} не найден.")
    elif arg.isdigit():
        tid = int(arg)
        if tid in data["telegram_ids"]:
            data["telegram_ids"].remove(tid)
            save_users(data)
            await update.message.reply_text(f"✅ ID {tid} удалён.")
        else:
            await update.message.reply_text(f"ℹ️ ID {tid} не найден.")

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/list — показать всех пользователей"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ У вас нет прав администратора.")
        return

    data = load_users()
    phones = data.get("phones", [])
    tids = data.get("telegram_ids", [])

    text = f"📋 *Список доступа*\n\n"
    text += f"📱 *Номера телефонов* ({len(phones)}):\n"
    for p in phones:
        text += f"  +{p}\n"
    text += f"\n🆔 *Telegram ID* ({len(tids)}):\n"
    for t in tids:
        text += f"  {t}\n"

    if not phones and not tids:
        text += "_Список пуст — доступ открыт всем_"

    await update.message.reply_text(text, parse_mode="Markdown")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_admin(update.effective_user.id):
        text = (
            "🛠 *Команды администратора:*\n\n"
            "/add +998901234567 — добавить по номеру\n"
            "/add 123456789 — добавить по Telegram ID\n"
            "/remove +998901234567 — удалить\n"
            "/list — список всех пользователей\n"
            "/start — открыть курс\n"
        )
    else:
        text = "📚 Напишите /start чтобы получить доступ к курсу."
    await update.message.reply_text(text, parse_mode="Markdown")

def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не задан!")
    if ADMIN_ID == 0:
        logger.warning("ADMIN_ID не задан — команды /add /remove недоступны!")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("add", add_user))
    app.add_handler(CommandHandler("remove", remove_user))
    app.add_handler(CommandHandler("list", list_users))
    app.add_handler(MessageHandler(filters.CONTACT, contact_handler))

    logger.info(f"Бот запущен. Admin ID: {ADMIN_ID}")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
