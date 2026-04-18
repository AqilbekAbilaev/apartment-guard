import logging
import os
import aiosqlite
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

DB_PATH = "apartment.db"

logging.basicConfig(level=logging.INFO)


# --- DATABASE ---

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS state (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS members (
                user_id INTEGER PRIMARY KEY,
                username TEXT
            )
        """)
        await db.execute("INSERT OR IGNORE INTO state VALUES ('trash_index', '0')")
        await db.commit()


async def get_state(key: str) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM state WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def set_state(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO state VALUES (?, ?)", (key, value))
        await db.commit()


async def register_member(user_id: int, username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO members VALUES (?, ?)",
            (user_id, username)
        )
        await db.commit()


async def get_members() -> list[tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id, username FROM members") as cursor:
            return await cursor.fetchall()


async def get_member_count() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM members") as cursor:
            row = await cursor.fetchone()
            return row[0]


# --- ACTIVATION CHECK ---

async def is_activated(context, chat_id: int) -> bool:
    total = await context.bot.get_chat_member_count(chat_id)
    registered = await get_member_count()
    # subtract 1 for the bot itself
    return registered >= (total - 1)


# --- COMMANDS ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id

    await register_member(user.id, user.username or user.first_name)

    total = await context.bot.get_chat_member_count(chat_id)
    registered = await get_member_count()
    remaining = (total - 1) - registered  # subtract bot

    if remaining > 0:
        await update.message.reply_text(
            f"✅ @{user.username or user.first_name} registered!\n"
            f"Waiting for {remaining} more member(s) to /start before the bot activates."
        )
    else:
        members = await get_members()
        names = ", ".join(f"@{m[1]}" for m in members)
        await update.message.reply_text(
            f"🎉 All members registered! Bot is now active.\nMembers: {names}"
        )


async def trash_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if not await is_activated(context, chat_id):
        registered = await get_member_count()
        total = await context.bot.get_chat_member_count(chat_id)
        remaining = (total - 1) - registered
        await update.message.reply_text(
            f"⏳ Bot not activated yet. Waiting for {remaining} more member(s) to /start."
        )
        return

    members = await get_members()
    trash_index = int(await get_state("trash_index"))
    current_person = members[trash_index % len(members)][1]

    keyboard = [[InlineKeyboardButton("🙋 I took out the trash!", callback_data="trash_claim")]]
    await update.message.reply_text(
        f"🗑️ The trash is full!\nIt's @{current_person}'s turn.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def trash_claim_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    presser = (query.from_user.username or "").lower()
    members = await get_members()
    trash_index = int(await get_state("trash_index"))
    current_person = members[trash_index % len(members)][1]

    if presser != current_person.lower():
        await query.answer("It's not your turn!", show_alert=True)
        return

    await query.answer()

    others = [f"@{m[1]}" for m in members if m[1].lower() != current_person.lower()]
    keyboard = [[InlineKeyboardButton("✅ Confirm!", callback_data="trash_confirm")]]
    await query.edit_message_text(
        text=f"@{current_person} says the trash is out! {' '.join(others)} can you confirm?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def trash_confirm_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    presser = (query.from_user.username or "").lower()
    members = await get_members()
    trash_index = int(await get_state("trash_index"))
    current_person = members[trash_index % len(members)][1]

    if presser == current_person.lower():
        await query.answer("You can't confirm your own trash duty!", show_alert=True)
        return

    await query.answer()

    new_index = (trash_index + 1) % len(members)
    await set_state("trash_index", str(new_index))
    next_person = members[new_index][1]

    await query.edit_message_text(
        text=f"✅ Confirmed by @{presser}! Thanks @{current_person}!\nNext: @{next_person}"
    )


# --- SETUP ---

async def post_init(application: Application):
    await init_db()


def main():
    application = Application.builder().token(TOKEN).post_init(post_init).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("trash", trash_command))
    application.add_handler(CallbackQueryHandler(trash_claim_button, pattern="trash_claim"))
    application.add_handler(CallbackQueryHandler(trash_confirm_button, pattern="trash_confirm"))

    application.run_polling()


if __name__ == "__main__":
    main()
