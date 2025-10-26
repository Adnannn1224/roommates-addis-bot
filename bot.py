import os
import logging
import sqlite3
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)
from photo_handler import save_photo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Conversation states ===
(NAME, PHOTO, LOCATION, NUM, GENDER,
 RELIGION, AGE, BUDGET, BIO) = range(9)

TOKEN = os.getenv('BOT_TOKEN')   # Railway will set this

# === DB helper ===
def get_conn():
    return sqlite3.connect('/app/roommates.db')

# === Handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🇪🇹 *Roommates Addis* – Find your perfect roommate!\n"
        "Let's start with your *full name*:",
        parse_mode='Markdown'
    )
    context.user_data['user_id'] = update.effective_user.id
    return NAME

async def name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text("Send your *profile picture*:")
    return PHOTO

async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    path = save_photo(update.message.photo, context.user_data['user_id'], context.bot)
    context.user_data['photo'] = path
    await update.message.reply_text("Where in Addis? (e.g. Bole, Piassa)")
    return LOCATION

async def location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['location'] = update.message.text
    await update.message.reply_text("How many roommates? (1–5)")
    return NUM

async def num(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = int(update.message.text)
        if 1 <= n <= 5:
            context.user_data['num'] = n
            kb = [['Male', 'Female', 'Other']]
            await update.message.reply_text(
                "Your gender:", reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True)
            )
            return GENDER
        else:
            await update.message.reply_text("Enter 1–5")
            return NUM
    except:
        await update.message.reply_text("Numbers only")
        return NUM

async def gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['gender'] = update.message.text
    await update.message.reply_text("Religion (or 'Prefer not to say')")
    return RELIGION

async def religion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['religion'] = update.message.text
    await update.message.reply_text("Your age:")
    return AGE

async def age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        a = int(update.message.text)
        if 18 <= a <= 60:
            context.user_data['age'] = a
            await update.message.reply_text("Monthly budget in ETB (e.g. 5000):")
            return BUDGET
        else:
            await update.message.reply_text("18–60 only")
            return AGE
    except:
        await update.message.reply_text("Numbers only")
        return AGE

async def budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['budget'] = float(update.message.text)
        await update.message.reply_text("Short bio (max 200 chars):")
        return BIO
    except:
        await update.message.reply_text("Numbers only")
        return BUDGET

async def bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bio = update.message.text[:200]
    data = context.user_data
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
    INSERT OR REPLACE INTO users VALUES (?,?,?,?,?,?,?,?,?,?)
    ''', (
        data['user_id'], data['name'], data['photo'], data['location'],
        data['num'], data['gender'], data['religion'],
        data['age'], data['budget'], bio
    ))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        "Profile saved! Use /match to find roommates.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (uid,))
    row = c.fetchone()
    if not row:
        await update.message.reply_text("Register first with /start")
        return

    user = dict(zip([d[0] for d in c.description], row))
    c.execute('''
    SELECT name, age, location, budget, bio FROM users
    WHERE user_id != ? AND location = ? AND gender = ?
      AND ABS(budget - ?) <= ? * 0.2
      AND ABS(age - ?) <= 5
    LIMIT 3
    ''', (uid, user['location'], user['gender'],
          user['budget'], user['budget'], user['age']))

    matches = c.fetchall()
    conn.close()

    if matches:
        txt = "Potential roommates:\n\n"
        for m in matches:
            txt += f"• {m[0]}, {m[1]}y – {m[2]}\n  Budget: {m[3]} ETB\n  {m[4][:50]}...\n\n"
        await update.message.reply_text(txt)
    else:
        await update.message.reply_text("No matches yet. Invite friends!")

def main():
    from database import init_db
    init_db()   # ensure DB exists

    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name)],
            PHOTO: [MessageHandler(filters.PHOTO, photo)],
            LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, location)],
            NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, num)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, gender)],
            RELIGION: [MessageHandler(filters.TEXT & ~filters.COMMAND, religion)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, age)],
            BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, budget)],
            BIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, bio)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler('match', match))

    print("Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()