import os
import logging
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, InputMediaPhoto
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
    return sqlite3.connect('roommates.db')

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

# === Handlers ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        "*Roommates Addis* – Find your perfect roommate!\n\n"
        "Let's build your profile.\n"
        "Start with your *full name*:",
        parse_mode='Markdown'
    )
    context.user_data['user_id'] = user.id
    return NAME

async def name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text("Send your *profile picture*:")
    return PHOTO

async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    path = await save_photo(update.message.photo, context.user_data['user_id'], context.bot)
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
            kb = [['Male', 'Female']]
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
    kb = [['Male', 'Female']]
    await update.message.reply_text(
        "Who are you *looking for*?", reply_markup=ReplyKeyboardMarkup(kb, one_time_keyboard=True)
    )
    return LOOKING_FOR

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
    
    keyboard = [
        [InlineKeyboardButton("Explore Roommates", callback_data="explore_start")],
        [InlineKeyboardButton("My Profile", callback_data="my_profile")],
        [InlineKeyboardButton("Find Matches", callback_data="find_matches")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Profile complete!\n\n"
        "What would you like to do?",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# === /match ===
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
            [InlineKeyboardButton("Next", callback_data="next")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"<b>{name}</b>, {age}y\n"
            f"{loc} | {budget} ETB\n"
            f"{bio[:100]}...\n\n"
            f"Send a match request?",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return

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

        pending = set(target['pending_requests'].split(",") if target['pending_requests'] else [])
        pending.add(str(sender['user_id']))
        target['pending_requests'] = ",".join(pending)
        save_user(target)

        keyboard = [
            [InlineKeyboardButton("Accept", callback_data=f"accept_{sender['user_id']}")],
            [InlineKeyboardButton("Reject", callback_data=f"reject_{sender['user_id']}")]
        ]
        await context.bot.send_message(
            chat_id=target_id,
            text=f"@{update.effective_user.username or sender['name']} wants to match!\n"
                 f"Location: {sender['location']} | Budget: {sender['budget']} ETB",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await query.edit_message_text("Request sent! Waiting for response...")

    elif data.startswith("accept_"):
        sender_id = int(data.split("_")[1])
        receiver = get_user(update.effective_user.id)
        sender = get_user(sender_id)

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

# === EXPLORE SYSTEM ===
current_explore_index = {}

async def get_potential_roommates(user):
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
    SELECT user_id, name, age, location, budget, bio, photo_path 
    FROM users 
    WHERE user_id != ? AND location = ? AND gender = ?
      AND ABS(budget - ?) <= ? * 0.2
      AND ABS(age - ?) <= 5
    ''', (user['user_id'], user['location'], user['looking_for'],
          user['budget'], user['budget'], user['age']))
    results = c.fetchall()
    conn.close()
    return [dict(zip(['user_id', 'name', 'age', 'location', 'budget', 'bio', 'photo_path'], r)) for r in results]

async def explore_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    user = get_user(user_id)

    if data == "explore_start":
        roommates = await get_potential_roommates(user)
        if not roommates:
            await query.edit_message_text("No one to explore yet. Invite friends!")
            return
        context.user_data['explore_list'] = roommates
        current_explore_index[user_id] = 0
        await show_roommate(query, context, user_id)

    elif data == "explore_next":
        idx = current_explore_index.get(user_id, 0) + 1
        if idx >= len(context.user_data['explore_list']):
            await query.edit_message_text("No more profiles. Try /match later!")
            return
        current_explore_index[user_id] = idx
        await show_roommate(query, context, user_id, edit=True)

    elif data == "explore_prev":
        idx = current_explore_index.get(user_id, 0) - 1
        if idx < 0:
            idx = 0
        current_explore_index[user_id] = idx
        await show_roommate(query, context, user_id, edit=True)

    elif data.startswith("request_"):
        target_id = int(data.split("_")[1])
        await send_match_request(context.bot, user_id, target_id, query)

    elif data == "back_to_explore":
        await show_roommate(query, context, user_id, edit=True)

async def show_roommate(query, context, user_id, edit=False):
    idx = current_explore_index[user_id]
    roommate = context.user_data['explore_list'][idx]
    total = len(context.user_data['explore_list'])

    keyboard = [
        [InlineKeyboardButton("Send Request", callback_data=f"request_{roommate['user_id']}")],
        [InlineKeyboardButton("Previous", callback_data="explore_prev"),
         InlineKeyboardButton("Next", callback_data="explore_next")],
        [InlineKeyboardButton("Back to Menu", callback_data="find_matches")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    caption = (
        f"<b>{roommate['name']}</b>, {roommate['age']}y\n"
        f"Location: {roommate['location']}\n"
        f"Budget: {roommate['budget']} ETB\n"
        f"Bio: {roommate['bio'][:100]}...\n\n"
        f"<i>{idx+1} of {total}</i>"
    )

    if edit:
        if roommate['photo_path'] and os.path.exists(roommate['photo_path']):
            with open(roommate['photo_path'], 'rb') as photo:
                await query.edit_message_media(
                    media=InputMediaPhoto(photo, caption=caption, parse_mode='HTML'),
                    reply_markup=reply_markup
                )
        else:
            await query.edit_message_text(caption, parse_mode='HTML', reply_markup=reply_markup)
    else:
        if roommate['photo_path'] and os.path.exists(roommate['photo_path']):
            with open(roommate['photo_path'], 'rb') as photo:
                await query.message.reply_photo(
                    photo, caption=caption, parse_mode='HTML', reply_markup=reply_markup
                )
        else:
            await query.message.reply_text(caption, parse_mode='HTML', reply_markup=reply_markup)

async def my_profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = get_user(update.effective_user.id)
    if not user:
        await query.edit_message_text("No profile found. Use /start")
        return

    caption = (
        f"<b>Your Profile</b>\n\n"
        f"Name: {user['name']}\n"
        f"Location: {user['location']}\n"
        f"Gender: {user['gender']} | Looking for: {user['looking_for']}\n"
        f"Age: {user['age']} | Budget: {user['budget']} ETB\n"
        f"Bio: {user['bio']}\n\n"
        f"Use /match or Explore to find roommates!"
    )
    keyboard = [[InlineKeyboardButton("Back to Menu", callback_data="find_matches")]]
    if user['photo_path'] and os.path.exists(user['photo_path']):
        with open(user['photo_path'], 'rb') as photo:
            await query.edit_message_media(
                media=InputMediaPhoto(photo, caption=caption, parse_mode='HTML'),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    else:
        await query.edit_message_text(caption, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def find_matches_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await match(update, context)

async def send_match_request(bot, sender_id, target_id, query):
    sender = get_user(sender_id)
    target = get_user(target_id)

    pending = set(target['pending_requests'].split(",") if target['pending_requests'] else [])
    pending.add(str(sender['user_id']))
    target['pending_requests'] = ",".join(pending)
    save_user(target)

    keyboard = [
        [InlineKeyboardButton("Accept", callback_data=f"accept_{sender['user_id']}_explore")],
        [InlineKeyboardButton("Reject", callback_data=f"reject_{sender['user_id']}_explore")]
    ]
    await bot.send_message(
        chat_id=target_id,
        text=f"@{query.from_user.username or sender['name']} wants to match!\n"
             f"Location: {sender['location']} | Budget: {sender['budget']} ETB",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    await query.edit_message_text("Request sent!")

# === Main ===
def main():
    from database import init_db
    init_db()

    app = Application.builder().token(TOKEN).build()

    # CLEAR OLD STATE
    async def clear_old_state():
        try:
            await app.bot.delete_webhook(drop_pending_updates=True)
            print("Old webhook/polling cleared")
        except Exception as e:
            print(f"Clear failed: {e}")

    app.job_queue.run_once(lambda _: app.create_task(clear_old_state()), 0)

    # Handlers
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
    app.add_handler(CallbackQueryHandler(explore_handler, pattern="^(explore_start|explore_next|explore_prev|request_|back_to_explore)$"))
    app.add_handler(CallbackQueryHandler(my_profile_handler, pattern="^my_profile$"))
    app.add_handler(CallbackQueryHandler(find_matches_handler, pattern="^find_matches$"))

    print("Bot is running with MATCHING SYSTEM...")
    app.run_polling()

if __name__ == '__main__':
    main()