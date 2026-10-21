import aiohttp
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters,
)

# ================= CONFIG =================
BOT_TOKEN = "8983990219:AAE7dNEPI6F2Ta6jy35x_lX7DCWGrR6g5mY"
API_KEY = "KEY"                              # api.osintxc.com key
API_URL = "https://api.osintxc.com/num"

ADMIN_IDS = [8147130832]
BOT_USERNAME = "@OSINT_SAD_AURA_BOT"

# 🔴 FORCE JOIN CHANNEL
FORCE_CHANNEL = "@OSINTchannelv1"
FORCE_CHANNEL_LINK = "https://t.me/OSINTchannelv1"
# ==========================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

USERS = set()
STATS = {"lookups": 0}


# ---------- Keyboards ----------
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Number Lookup", callback_data="lookup")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")],
    ])


def back_keyboard():
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔙 Back", callback_data="back")]]
    )


def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Bot Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("👥 User Count", callback_data="admin_users")],
        [InlineKeyboardButton("🔙 Back", callback_data="back")],
    ])


def join_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=FORCE_CHANNEL_LINK)],
        [InlineKeyboardButton("✅ Joined — Verify", callback_data="verify_join")],
    ])


# ---------- Force Join Check ----------
async def is_joined(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(FORCE_CHANNEL, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        logger.warning(f"Force-join check failed: {e}")
        return False


async def force_join_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🚫 <b>Access Denied</b>\n\n"
        "Pehle aapko hamara channel join karna hoga! 👇\n\n"
        f"📢 Channel: {FORCE_CHANNEL}\n\n"
        "Join karne ke baad <b>✅ Joined — Verify</b> button dabaiye."
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, parse_mode="HTML", reply_markup=join_keyboard()
        )
    else:
        await update.message.reply_text(
            text, parse_mode="HTML", reply_markup=join_keyboard()
        )


# ---------- API ----------
async def fetch_number_info(number: str):
    params = {"number": number, "key": API_KEY}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL, params=params, timeout=20) as resp:
                if resp.status != 200:
                    return {"error": f"HTTP {resp.status}"}
                return await resp.json(content_type=None)
    except Exception as e:
        logger.exception("API error")
        return {"error": str(e)}


# ---------- Formatter ----------
def format_result(data: dict) -> str:
    if not data:
        return "❌ No data found."
    if "error" in data:
        return f"❌ Error: {data['error']}"

    emoji_map = {
        "name": "👤", "father_name": "👨", "mother_name": "👩",
        "address": "🏠", "pincode": "📍", "pin_code": "📍",
        "aadhar": "🆔", "aadhar_number": "🆔",
        "alt_number": "📞", "alternate_number": "📞", "alternate number": "📞",
        "mobile": "📱", "number": "📱", "email": "📧",
        "dob": "🎂", "date_of_birth": "🎂", "gender": "⚧",
        "age": "🎈", "circle": "🌐", "operator": "📡",
        "state": "🗺️", "district": "🏙️", "village": "🏘️",
        "photo": "🖼️", "image": "🖼️",
    }

    order = [
        "name", "father_name", "mother_name",
        "address", "pincode", "pin_code",
        "aadhar", "aadhar_number",
        "alt_number", "alternate_number", "alternate number",
        "mobile", "number", "email", "dob", "date_of_birth",
        "gender", "age", "circle", "operator", "state", "district", "village",
    ]

    lines = ["✨ <b>Number Lookup Result</b> ✨\n"]
    processed = set()

    def add_line(k, v):
        k_clean = str(k).lower().strip()
        if any(x in k_clean for x in ("credit", "limit", "used")):
            return
        key_title = str(k).replace("_", " ").title()
        if isinstance(v, (dict, list)):
            v = str(v)
        emoji = emoji_map.get(k_clean, "🔹")
        lines.append(f"{emoji} <b>{key_title}</b>\n   ↳ <code>{v}</code>")
        processed.add(k)

    for desired in order:
        for k, v in data.items():
            if k in processed:
                continue
            if str(k).lower().strip() == desired:
                add_line(k, v)

    for k, v in data.items():
        if k not in processed:
            add_line(k, v)

    lines.append("\n✅ <i>Unlimited free lookups — no credit limit!</i>")
    return "\n".join(lines)


# ---------- Handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    USERS.add(user.id)
    # reset state on fresh start
    context.user_data["awaiting_number"] = False
    context.user_data["awaiting_broadcast"] = False

    if not await is_joined(context, user.id):
        return await force_join_prompt(update, context)

    text = (
        f"👋 <b>Welcome to {BOT_USERNAME}</b> 🎉\n\n"
        f"🌟 Hello <b>{user.first_name}</b>!\n"
        f"🆔 Your ID: <code>{user.id}</code>\n\n"
        "💫 Yeh bot aapko number lookup ki suvidha deta hai.\n"
        "✅ <b>100% Free</b> — koi credit limit nahi! 🆓\n"
        "♾️ <b>Unlimited Lookups</b> — jitna chahein use karein.\n\n"
        "👇 Neeche button dabaiye:"
    )
    await update.message.reply_text(
        text, parse_mode="HTML", reply_markup=main_menu_keyboard()
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    # Verify join button
    if data == "verify_join":
        if await is_joined(context, user_id):
            context.user_data["awaiting_number"] = False
            await query.edit_message_text(
                "✅ <b>Verified!</b>\n\nAb aap bot use kar sakte hain. 👇",
                parse_mode="HTML",
                reply_markup=main_menu_keyboard(),
            )
        else:
            await query.answer("❌ Pehle channel join karein!", show_alert=True)
        return

    # Force join check for all other buttons
    if not await is_joined(context, user_id):
        return await force_join_prompt(update, context)

    if data == "lookup":
        context.user_data["awaiting_number"] = True
        context.user_data["awaiting_broadcast"] = False
        await query.edit_message_text(
            "📱 <b>Number Lookup</b>\n\n"
            "Apna number bhejiye (example <code>9876543210</code>):\n"
            "♾️ <i>No credit limit — unlimited free lookups!</i>",
            parse_mode="HTML",
            reply_markup=back_keyboard(),
        )
        return

    if data == "help":
        context.user_data["awaiting_number"] = False
        await query.edit_message_text(
            "ℹ️ <b>Help</b>\n\n"
            "🔹 <b>Number Lookup</b> — kisi bhi number ki info nikaalein\n"
            "🔹 Sab kuch <b>free</b> hai 🆓\n"
            "🔹 <b>Koi credit limit nahi</b> — unlimited lookups ♾️\n\n"
            "❓ Support ke liye admin se contact karein.",
            parse_mode="HTML",
            reply_markup=back_keyboard(),
        )
        return

    if data == "back":
        context.user_data["awaiting_number"] = False
        context.user_data["awaiting_broadcast"] = False
        await query.edit_message_text(
            "🏠 <b>Main Menu</b>\n\nKya karna chahte hain? 👇",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )
        return

    # Admin panel
    if data.startswith("admin_"):
        if user_id not in ADMIN_IDS:
            await query.answer("⛔ Access Denied", show_alert=True)
            return

        context.user_data["awaiting_number"] = False

        if data == "admin_stats":
            await query.edit_message_text(
                f"📊 <b>Bot Stats</b>\n\n"
                f"👥 Total Users: <b>{len(USERS)}</b>\n"
                f"🔍 Total Lookups: <b>{STATS['lookups']}</b>",
                parse_mode="HTML",
                reply_markup=admin_keyboard(),
            )
        elif data == "admin_users":
            await query.edit_message_text(
                f"👥 <b>Total Users:</b> {len(USERS)}\n\n"
                + ("\n".join(f"• <code>{u}</code>" for u in list(USERS)[:50])
                   or "No users yet."),
                parse_mode="HTML",
                reply_markup=admin_keyboard(),
            )
        elif data == "admin_broadcast":
            context.user_data["awaiting_broadcast"] = True
            await query.edit_message_text(
                "📢 <b>Broadcast</b>\n\nMessage bhejiye jo sab users ko jaana hai:",
                parse_mode="HTML",
                reply_markup=back_keyboard(),
            )
        return


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    USERS.add(user.id)
    text = (update.message.text or "").strip()

    # Admin broadcast skip force-join
    if context.user_data.get("awaiting_broadcast") and user.id in ADMIN_IDS:
        context.user_data["awaiting_broadcast"] = False
        sent = 0
        for uid in list(USERS):
            try:
                await context.bot.send_message(uid, text, parse_mode="HTML")
                sent += 1
            except Exception:
                pass
        await update.message.reply_text(
            f"✅ Broadcast sent to {sent}/{len(USERS)} users."
        )
        return

    # Force join check
    if not await is_joined(context, user.id):
        return await force_join_prompt(update, context)

    # Number lookup
    if context.user_data.get("awaiting_number"):
        context.user_data["awaiting_number"] = False
        if not (text.isdigit() and 7 <= len(text) <= 15):
            await update.message.reply_text(
                "❌ Invalid number. Sirf digits (7-15) bhejiye.",
                reply_markup=back_keyboard(),
            )
            return

        msg = await update.message.reply_text("🔎 Searching... ⏳")
        result = await fetch_number_info(text)
        STATS["lookups"] += 1
        await msg.edit_text(
            format_result(result),
            parse_mode="HTML",
            reply_markup=back_keyboard(),
        )
        return

    # ⚠️ FIX: fallback — dobara menu na bhejein, sirf hint bhejein
    await update.message.reply_text(
        "👇 Pehle menu se <b>🔍 Number Lookup</b> option chuniye,\n"
        "phir apna number bhejiye.",
        parse_mode="HTML",
        reply_markup=back_keyboard(),
    )


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Access Denied")
        return
    context.user_data["awaiting_number"] = False
    context.user_data["awaiting_broadcast"] = False
    await update.message.reply_text(
        "🛠 <b>Admin Panel</b>",
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    print("🤖 Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
