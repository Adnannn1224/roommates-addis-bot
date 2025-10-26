import os
import logging
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler, CallbackQueryHandler
)
from photo_handler import save_photo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === States ===
(NAME, PHOTO, LOCATION, NUM, GENDER, LOOKING_FOR,
 RELIGION, AGE, BUDGET, BIO) = range(10)

TOKEN = os.getenv('BOT_TOKEN')

# === DB ===
def get_conn():
    return sqlite3.connect('/data/roommates.db')
    
def get_user(uid):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (uid,))
    row = c.fetchone()
    conn.close()
    return dict(zip([d[0] for d in c.description], row)) if row else None

def save_user(data):
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
    INSERT OR REPLACE INTO users VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    ''', (
        data['user_id'], data['name'], data['photo'], data['location'],
        data['num'], data['gender'], data['looking_for'], data['religion'],
        data['age'], data['budget'], data['bio'],
        data.get('pending_requests', ''), data.get('matches', '')
    ))
    conn.commit()
    conn.close()

# === Start ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"🇪🇹 *Roommates Addis* – Find your perfect roommate!\n\n"
        "Let's build your profile.\n"
        "Start with your *full name*:",
        parse_mode='Markdown'
    )
    context.user_data['user_id'] = user.id
    return NAME

# === Handlers (same as before until LOOKING_FOR) ===
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
            await update.message.reply_text("Your gender:", reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True))
            return GENDER
        else:
            await update.message.reply_text("Enter 1–5")
            return NUM
    except:
        await update.message.reply_text("Numbers only")
        return NUM

async def gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['gender'] = update.message.text
    kb = [['Male', 'Female', 'Other']]
    await update.message.reply_text("Who are you *looking for*?", reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True))
    return LOOKING_FOR

# === NEW: Looking For ===
async def looking_for(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['looking_for'] = update.message.text
    await update.message.reply_text("Your religion (or 'Prefer not to say'):")
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
    context.user_data['bio'] = update.message.text[:200]
    save_user(context.user_data)
    await update.message.reply_text(
        "Profile complete! Use /match to find roommates.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# === /match Command ===
async def match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid)
    if not user:
        await update.message.reply_text("Complete your profile with /start first!")
        return

    conn = get_conn()
    c = conn.cursor()
    c.execute('''
    SELECT user_id, name, age, location, budget, bio FROM users
    WHERE user_id != ? AND location = ? AND gender = ?
      AND looking_for = ?
      AND ABS(budget - ?) <= ? * 0.2
      AND ABS(age - ?) <= 5
    LIMIT 3
    ''', (uid, user['location'], user['looking_for'], user['gender'],
          user['budget'], user['budget'], user['age']))
    suggestions = c.fetchall()
    conn.close()

    if not suggestions:
        await update.message.reply_text("No matches yet. Try adjusting your preferences!")
        return

    for sug in suggestions:
        sid, name, age, loc, budget, bio = sug
        keyboard = [
            [InlineKeyboardButton("Send Match Request", callback_data=f"request_{sid}")],
            [InlineKeyboardButton("Next →", callback_data="next")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"<b>{name}</b>, {age}y\n"
            f"📍 {loc} | 💰 {budget} ETB\n"
            f"📝 {bio[:100]}...\n\n"
            f"Send a match request?",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return  # Show one at a time

# === Button Handler ===
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "next":
        await query.edit_message_text("No more suggestions. Try /match again later!")
        return

    if data.startswith("request_"):
        target_id = int(data.split("_")[1])
        sender = get_user(update.effective_user.id)
        target = get_user(target_id)

        # Add to target's pending
        pending = set(target['pending_requests'].split(",") if target['pending_requests'] else [])
        pending.add(str(sender['user_id']))
        target['pending_requests'] = ",".join(pending)
        save_user(target)

        # Notify target
        keyboard = [
            [InlineKeyboardButton("Accept", callback_data=f"accept_{sender['user_id']}")],
            [InlineKeyboardButton("Reject", callback_data=f"reject_{sender['user_id']}")]
        ]
        await context.bot.send_message(
            chat_id=target_id,
            text=f"@{update.effective_user.username or sender['name']} wants to match!\n"
                 f"Location: {sender['location']} | Budget: {sender['budget']} ETB\n"
                 f"Send request back?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await query.edit_message_text("Request sent! Waiting for response...")

    elif data.startswith("accept_"):
        sender_id = int(data.split("_")[1])
        receiver = get_user(update.effective_user.id)
        sender = get_user(sender_id)

        # Add to both matches
        sender_matches = set(sender['matches'].split(",") if sender['matches'] else [])
        receiver_matches = set(receiver['matches'].split(",") if receiver['matches'] else [])
        sender_matches.add(str(receiver['user_id']))
        receiver_matches.add(str(sender['user_id']))
        sender['matches'] = ",".join(sender_matches)
        receiver['matches'] = ",".join(receiver_matches)
        save_user(sender)
        save_user(receiver)

        await context.bot.send_message(sender_id, f"Match confirmed! Contact @{update.effective_user.username}")
        await context.bot.send_message(update.effective_user.id, f"Match confirmed! Contact @{sender.get('name', 'User')}")

    elif data.startswith("reject_"):
        await query.edit_message_text("You rejected the request.")

# === Main ===
def main():
    from database import init_db
    init_db()

    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name)],
            PHOTO: [MessageHandler(filters.PHOTO, photo)],
            LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, location)],
            NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, num)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, gender)],
            LOOKING_FOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, looking_for)],
            RELIGION: [MessageHandler(filters.TEXT & ~filters.COMMAND, religion)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, age)],
            BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, budget)],
            BIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, bio)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler('match', match))
    app.add_handler(CallbackQueryHandler(button))

    print("Bot is running with MATCHING SYSTEM...")
    app.run_polling()

if __name__ == '__main__':
    main()