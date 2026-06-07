import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://kslmvv.github.io/bos-course/")

# ── СПИСОК РАЗРЕШЁННЫХ НОМЕРОВ ──────────────────────
# Формат: международный без + и пробелов
# Пример: 998901234567
ALLOWED_PHONES = os.environ.get("ALLOWED_PHONES", "").split(",")
# Убираем пробелы и пустые строки
ALLOWED_PHONES = [p.strip().lstrip("+") for p in ALLOWED_PHONES if p.strip()]

def is_allowed(phone: str) -> bool:
    """Проверяем номер — убираем + и пробелы перед сравнением"""
    clean = phone.strip().lstrip("+").replace(" ", "").replace("-", "")
    return clean in ALLOWED_PHONES or len(ALLOWED_PHONES) == 0

# ── ПРИВЕТСТВЕННОЕ СООБЩЕНИЕ ─────────────────────────
WELCOME_TEXT = """👋 Добро пожаловать!

📚 *Курс «Бизнес Операционная Система»*
_от Александра Высоцкого_

Для получения доступа к курсу нажмите кнопку ниже и поделитесь своим номером телефона."""

GRANTED_TEXT = """✅ *Доступ подтверждён!*

Добро пожаловать на курс *«Бизнес Операционная Система»* от Александра Высоцкого.

Нажмите кнопку ниже чтобы начать обучение 👇"""

DENIED_TEXT = """🔒 *Доступ закрыт*

К сожалению, ваш номер телефона не найден в списке участников курса.

Если вы считаете что это ошибка — обратитесь к организатору курса."""

# ── HANDLERS ─────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start — запрашиваем контакт"""
    # Если список пустой — открываем всем (режим разработки)
    if not ALLOWED_PHONES:
        await send_course_button(update, context)
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
    logger.info(f"Contact received: {phone}, user_id: {update.effective_user.id}")

    # Убираем клавиатуру
    await update.message.reply_text(
        "Проверяю доступ...",
        reply_markup=ReplyKeyboardRemove()
    )

    if is_allowed(phone):
        # Доступ разрешён
        keyboard = [[InlineKeyboardButton(
            "📚 Открыть курс",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )]]
        await update.message.reply_text(
            GRANTED_TEXT,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        # Доступ закрыт
        await update.message.reply_text(
            DENIED_TEXT,
            parse_mode="Markdown"
        )

async def send_course_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляем кнопку открытия курса"""
    keyboard = [[InlineKeyboardButton(
        "📚 Открыть курс",
        web_app=WebAppInfo(url=WEBAPP_URL)
    )]]
    await update.message.reply_text(
        GRANTED_TEXT,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 *БОС Курс*\n\nНапишите /start чтобы получить доступ к курсу.",
        parse_mode="Markdown"
    )

def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не задан!")

    logger.info(f"Запуск бота. Разрешённых номеров: {len(ALLOWED_PHONES)}")
    if ALLOWED_PHONES:
        logger.info(f"Номера: {ALLOWED_PHONES}")
    else:
        logger.info("Список номеров пустой — доступ открыт всем (режим разработки)")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.CONTACT, contact_handler))

    logger.info("Бот запущен...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
