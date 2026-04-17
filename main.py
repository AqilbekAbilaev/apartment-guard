import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# --- CONFIGURATION ---
TOKEN = "8721227164:AAHq7H7IWUof4rUr3P2xYvCaoR7rCYmHFio"
# Add your Telegram handles (without the @)
users = ["devalyus", "jurttin_balasi", "haylike"]

# This keeps track of whose turn it is for trash (0, 1, or 2)
trash_index = 0

# --- DISHES (SCHEDULED) ---
async def daily_dishes(context: ContextTypes.DEFAULT_TYPE):
    # This logic rotates dishes based on the day of the year
    # Example: Simple rotation
    import datetime
    day_of_year = datetime.datetime.now().timetuple().tm_yday
    person_on_duty = users[day_of_year % 3]

    await context.bot.send_message(
        chat_id="YOUR_GROUP_CHAT_ID",
        text=f"☀️ Good morning! @{person_on_duty} is on Dish Duty today. Let's keep the sink clear!"
    )

# --- TRASH (ON-DEMAND) ---
async def trash_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_person = users[trash_index]

    keyboard = [[InlineKeyboardButton("🙋 I took out the trash!", callback_data='trash_claim')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🗑️ The trash is full!\nIt's @{current_person}'s turn to handle the kitchen and toilet bins.",
        reply_markup=reply_markup
    )

async def trash_claim_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    presser = (query.from_user.username or "").lower()

    if presser != users[trash_index].lower():
        await query.answer("It's not your turn!", show_alert=True)
        return

    await query.answer()

    keyboard = [[InlineKeyboardButton("✅ Confirm!", callback_data='trash_confirm')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    others = [f"@{u}" for u in users if u.lower() != users[trash_index].lower()]
    others_str = " ".join(others)

    await query.edit_message_text(
        text=f"@{users[trash_index]} says the trash is out! {others_str} can you confirm?",
        reply_markup=reply_markup
    )

async def trash_confirm_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global trash_index
    query = update.callback_query
    presser = (query.from_user.username or "").lower()

    if presser == users[trash_index].lower():
        await query.answer("You can't confirm your own trash duty!", show_alert=True)
        return

    await query.answer()

    finished_person = users[trash_index]
    trash_index = (trash_index + 1) % len(users)
    next_person = users[trash_index]

    await query.edit_message_text(
        text=f"✅ Confirmed by @{presser}! Thanks @{finished_person}!\nNext in line for trash: @{next_person}"
    )

# --- SETUP ---
def main():
    application = Application.builder().token(TOKEN).build()

    # Commands
    application.add_handler(CommandHandler("trash", trash_command))
    application.add_handler(CallbackQueryHandler(trash_claim_button, pattern='trash_claim'))
    application.add_handler(CallbackQueryHandler(trash_confirm_button, pattern='trash_confirm'))

    # Start the bot
    application.run_polling()

if __name__ == "__main__":
    main()
