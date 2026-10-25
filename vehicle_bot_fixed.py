import logging
import re
import json
import os
import requests
from datetime import datetime
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes
)

# ========== CONFIG ==========
BOT_TOKEN = ("8996653971:AAEkaE5HFsQi-i9oOoTVYwjxKj8kF9NoT1U")
API_BASE = "https://api.sarkariallupdates.com/api"
API_KEY = "demo"

ADMIN_IDS = {8147130832}

# ========== CREDITS / PAYMENT CONFIG ==========
UPI_ID = "riteshgiri7930@okhdfcbank"
UPI_NAME = "Ritesh Giri"
WELCOME_CREDITS = 5
DB_FILE = "users_db.json"
PENDING_FILE = "pending_payments.json"

# ========== 5 CREDIT PLANS ==========
CREDIT_PLANS = [
    (1, 50,  10),
    (2, 100, 30),
    (3, 150, 50),
    (4, 200, 100),
    (5, 300, 180),
]
# ==============================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

WELCOME_TEXT = (
    "🙏🏻 Swagat hai!\n"
    "🎀 Me Ritesh Ka AI Assistant 🎀"
)

FOOTER = "\n\n━━━━━━━━━━━━━━\n⚡ Powered by Ritesh Goswami"

SENSITIVE_KEYS = {
    "username", "user", "user_name", "name", "owner", "owner_name",
    "father_name", "mother_name",
    "contact", "email", "address", "full_name", "first_name", "last_name"
}

# ========== VEHICLE NUMBER VALIDATION ==========
# Indian vehicle number format:
# - 2 letters (state code) + 1-2 digits (RTO) + 1-3 letters (series) + 4 digits (number)
# - Total 8-11 characters, no spaces
VEHICLE_REGEX = re.compile(
    r"^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}$"
)
# Optional: allow BH (Bharat) series like 22BH1234A
BH_REGEX = re.compile(
    r"^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$"
)


def is_valid_vehicle_number(text: str) -> bool:
    """Sirf valid Indian vehicle numbers accept karega."""
    cleaned = re.sub(r"[\s\-]", "", text).upper()
    if not (8 <= len(cleaned) <= 11):
        return False
    return bool(VEHICLE_REGEX.match(cleaned) or BH_REGEX.match(cleaned))


def normalize_vehicle_number(text: str) -> str:
    """Spaces aur hyphens hata ke uppercase karta hai."""
    return re.sub(r"[\s\-]", "", text).upper()
# ==============================================


# ========== DB HELPERS ==========
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


def load_pending():
    if os.path.exists(PENDING_FILE):
        try:
            with open(PENDING_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_pending(p):
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(p, f, indent=2, ensure_ascii=False)


def get_user(uid: int):
    db = load_db()
    key = str(uid)
    if key not in db:
        db[key] = {
            "credits": WELCOME_CREDITS,
            "joined": datetime.now().isoformat(),
            "total_searches": 0,
            "selected_plan": None,
        }
        save_db(db)
    return db[key]


def update_user(uid: int, **kwargs):
    db = load_db()
    key = str(uid)
    if key not in db:
        db[key] = {"credits": WELCOME_CREDITS, "joined": datetime.now().isoformat(), "total_searches": 0}
    db[key].update(kwargs)
    save_db(db)
    return db[key]


def deduct_credit(uid: int) -> bool:
    if is_admin(uid):
        db = load_db()
        key = str(uid)
        if key not in db:
            db[key] = {"credits": 999999, "joined": datetime.now().isoformat(), "total_searches": 0}
        db[key]["total_searches"] = db[key].get("total_searches", 0) + 1
        save_db(db)
        return True

    db = load_db()
    key = str(uid)
    if key not in db:
        return False
    if db[key].get("credits", 0) <= 0:
        return False
    db[key]["credits"] -= 1
    db[key]["total_searches"] = db[key].get("total_searches", 0) + 1
    save_db(db)
    return True


# ========== CLEANING HELPERS ==========
def clean_json(obj):
    if isinstance(obj, dict):
        return {
            k: clean_json(v)
            for k, v in obj.items()
            if k.lower() not in SENSITIVE_KEYS
        }
    elif isinstance(obj, list):
        return [clean_json(item) for item in obj]
    return obj


def strip_usernames(text: str) -> str:
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        if re.search(r"(?i)\b(mobile|phone)\b", line):
            cleaned_lines.append(line)
            continue
        line = re.sub(r"@\w+", "", line)
        line = re.sub(
            r"(?i)\b(username|user|owner|owner_name|name|father_name|"
            r"contact|email|address)\s*[:=]\s*\S+",
            "",
            line
        )
        cleaned_lines.append(line)
    text = "\n".join(cleaned_lines)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def get_plan_by_no(plan_no: int):
    for p in CREDIT_PLANS:
        if p[0] == plan_no:
            return p
    return None


# ========== KEYBOARD ==========
def get_keyboard(user_id: int = None) -> ReplyKeyboardMarkup:
    row1 = [
        KeyboardButton("🔍 Vehicle Info"),
        KeyboardButton("💳 Buy Credits"),
    ]
    row2 = [KeyboardButton("💰 My Balance")]

    if user_id is not None and is_admin(user_id):
        row2.append(KeyboardButton("⚙️ Admin Panel"))

    keyboard = [row1, row2]
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Vehicle number likhein..."
    )


# ========== HANDLERS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid)

    if is_admin(uid):
        admin_note = "\n👑 *Admin:* Aapko unlimited free credits hain."
    else:
        admin_note = f"\n💳 Aapke credits: *{user['credits']}*"

    await update.message.reply_text(
        WELCOME_TEXT + "\n\n"
        "🚗 Vehicle number bhejein (jaise: HR55AL0051)\n"
        "Main aapko uski information dunga.\n"
        + admin_note + FOOTER,
        parse_mode="Markdown",
        reply_markup=get_keyboard(uid)
    )


async def my_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid)

    if is_admin(uid):
        credit_line = "💳 Credits : *UNLIMITED* 👑 (Admin)"
    else:
        credit_line = f"💳 Credits : *{user['credits']}*"

    await update.message.reply_text(
        f"💰 *Aapka Balance*\n"
        f"━━━━━━━━━━━━━━\n"
        f"👤 User ID : `{uid}`\n"
        f"{credit_line}\n"
        f"🔍 Total Searches : {user.get('total_searches', 0)}\n"
        f"━━━━━━━━━━━━━━\n"
        f"Credits kharidne ke liye '💳 Buy Credits' dabayein."
        + FOOTER,
        parse_mode="Markdown",
        reply_markup=get_keyboard(uid)
    )


async def buy_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    context.user_data["awaiting_plan"] = True

    plans_text = ""
    for p in CREDIT_PLANS:
        plan_no, price, credits = p
        plans_text += f"*{plan_no}.* ₹{price} → *{credits} Credits*\n"

    text = (
        "💳 *CREDITS KHARIDEIN*\n"
        "━━━━━━━━━━━━━━\n"
        "📦 *Available Plans:*\n\n"
        f"{plans_text}"
        "━━━━━━━━━━━━━━\n"
        "🏦 UPI ID : `" + UPI_ID + "`\n"
        f"👤 Name : {UPI_NAME}\n"
        "━━━━━━━━━━━━━━\n\n"
        "📌 *Kaise kharidein?*\n"
        "1️⃣ Upar se plan choose karein — *plan number* bhejein\n"
        "   (jaise `1` bhejein 50₹/10 credits ke liye)\n"
        "2️⃣ UPI ID par payment karein\n"
        "3️⃣ Payment ka *screenshot* yahan bhejein\n"
        "4️⃣ Admin verify karke credits add karega\n\n"
        f"⚠️ Screenshot ke saath apna User ID likhein: `{uid}`\n"
        "━━━━━━━━━━━━━━\n"
        "👉 Ab apna *plan number* (1-5) bhejein."
        + FOOTER
    )
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_keyboard(uid)
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid)

    if is_admin(uid):
        await update.message.reply_text(
            "ℹ️ Aap admin hain. Payment approve karne ke liye `/approve <user_id> <credits>` use karein."
            + FOOTER,
            reply_markup=get_keyboard(uid)
        )
        return

    photo = update.message.photo[-1]
    caption = update.message.caption or ""

    selected = user.get("selected_plan")
    plan_info = ""
    if selected:
        plan = get_plan_by_no(selected)
        if plan:
            _, price, credits = plan
            plan_info = f"📦 Plan : #{plan[0]} (₹{price} → {credits} credits)"

    pending = load_pending()
    pending[str(uid)] = {
        "file_id": photo.file_id,
        "caption": caption,
        "time": datetime.now().isoformat(),
        "username": update.effective_user.username or "",
        "name": update.effective_user.full_name or "",
        "selected_plan": selected,
    }
    save_pending(pending)

    admin_text = (
        "🔔 *NAYA PAYMENT SCREENSHOT*\n"
        "━━━━━━━━━━━━━━\n"
        f"👤 User ID : `{uid}`\n"
        f"📛 Name : {update.effective_user.full_name}\n"
        f"🔗 Username : @{update.effective_user.username or 'N/A'}\n"
        f"💳 Current Credits : {user.get('credits', 0)}\n"
        f"{plan_info}\n"
        f"📝 Caption : {caption or 'N/A'}\n"
        "━━━━━━━━━━━━━━\n"
        f"✅ Approve : `/approve {uid} <credits>`\n"
        f"❌ Reject  : `/reject {uid}`"
    )

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=photo.file_id,
                caption=admin_text,
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.warning(f"Admin {admin_id} ko forward nahi hua: {e}")

    await update.message.reply_text(
        "✅ Aapka screenshot admin ko bhej diya gaya hai.\n"
        "⏳ Verify hone ke baad credits add ho jayenge.\n"
        "Aap '💰 My Balance' se check kar sakte hain." + FOOTER,
        reply_markup=get_keyboard(uid)
    )


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text(
            "⛔ Aap admin nahi hain." + FOOTER,
            reply_markup=get_keyboard(uid)
        )
        return

    db = load_db()
    pending = load_pending()
    total_users = len(db)
    total_credits = sum(u.get("credits", 0) for u in db.values())
    pending_count = len(pending)

    text = (
        "⚙️ *ADMIN PANEL*\n"
        "━━━━━━━━━━━━━━\n"
        f"👤 Admin ID : `{uid}`\n"
        f"🌐 API      : `{API_BASE}`\n"
        f"🔑 API Key  : `{API_KEY}`\n"
        f"💳 UPI ID   : `{UPI_ID}`\n"
        "━━━━━━━━━━━━━━\n"
        f"👥 Total Users    : *{total_users}*\n"
        f"💰 Total Credits  : *{total_credits}*\n"
        f"⏳ Pending Payments : *{pending_count}*\n"
        "━━━━━━━━━━━━━━\n"
        "👑 *Aapko unlimited free credits hain.*\n"
        "━━━━━━━━━━━━━━\n"
        "*Commands:*\n"
        "`/addcredits <user_id> <credits>`\n"
        "`/approve <user_id> <credits>`\n"
        "`/reject <user_id>`\n"
        "`/balance <user_id>`\n"
        "`/pending`\n"
        + FOOTER
    )
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_keyboard(uid)
    )


async def cmd_addcredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        return
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Usage: `/addcredits <user_id> <credits>`", parse_mode="Markdown")
        return
    try:
        target = int(args[0])
        amount = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid numbers.")
        return

    user = get_user(target)
    new_credits = user.get("credits", 0) + amount
    update_user(target, credits=new_credits)

    await update.message.reply_text(
        f"✅ `{target}` ko *{amount}* credits add ho gaye.\n"
        f"💳 New balance: *{new_credits}*",
        parse_mode="Markdown"
    )
    try:
        await context.bot.send_message(
            chat_id=target,
            text=f"✅ Aapke account me *{amount}* credits add ho gaye!\n💳 New balance: *{new_credits}*" + FOOTER,
            parse_mode="Markdown"
        )
    except Exception:
        pass


async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        return
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Usage: `/approve <user_id> <credits>`", parse_mode="Markdown")
        return
    try:
        target = int(args[0])
        amount = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid numbers.")
        return

    user = get_user(target)
    new_credits = user.get("credits", 0) + amount
    update_user(target, credits=new_credits, selected_plan=None)

    pending = load_pending()
    pending.pop(str(target), None)
    save_pending(pending)

    await update.message.reply_text(
        f"✅ Payment approved!\n"
        f"👤 User: `{target}`\n"
        f"💳 +{amount} credits (New: *{new_credits}*)",
        parse_mode="Markdown"
    )
    try:
        await context.bot.send_message(
            chat_id=target,
            text=(
                "✅ *Payment Approved!*\n"
                f"💰 *{amount}* credits add ho gaye.\n"
                f"💳 New balance: *{new_credits}*\n"
                "Ab aap vehicle search kar sakte hain." + FOOTER
            ),
            parse_mode="Markdown"
        )
    except Exception:
        pass


async def cmd_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        return
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Usage: `/reject <user_id>`", parse_mode="Markdown")
        return
    try:
        target = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
        return

    pending = load_pending()
    pending.pop(str(target), None)
    save_pending(pending)

    await update.message.reply_text(f"❌ `{target}` ka payment reject kar diya.", parse_mode="Markdown")
    try:
        await context.bot.send_message(
            chat_id=target,
            text=(
                "❌ *Payment Rejected*\n"
                "Aapka payment verify nahi ho paya.\n"
                "Sahi screenshot ke saath dobara bhejein ya support se contact karein."
                + FOOTER
            ),
            parse_mode="Markdown"
        )
    except Exception:
        pass


async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        return
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Usage: `/balance <user_id>`", parse_mode="Markdown")
        return
    try:
        target = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
        return
    user = get_user(target)
    credit_display = "UNLIMITED 👑" if is_admin(target) else user.get('credits', 0)
    await update.message.reply_text(
        f"👤 User `{target}`\n"
        f"💳 Credits: *{credit_display}*\n"
        f"🔍 Searches: {user.get('total_searches', 0)}",
        parse_mode="Markdown"
    )


async def cmd_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        return
    pending = load_pending()
    if not pending:
        await update.message.reply_text("✅ Koi pending payment nahi hai.")
        return

    lines = ["⏳ *Pending Payments*\n━━━━━━━━━━━━━━"]
    for user_id, info in pending.items():
        plan_str = ""
        if info.get("selected_plan"):
            plan = get_plan_by_no(info["selected_plan"])
            if plan:
                plan_str = f" | Plan #{plan[0]} (₹{plan[1]}→{plan[2]}cr)"
        lines.append(
            f"👤 `{user_id}` — {info.get('name', '')} "
            f"(@{info.get('username', 'N/A')}){plan_str}"
        )
    lines.append("\nApprove: `/approve <user_id> <credits>`")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def handle_vehicle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return

    text_input = message.text.strip()
    if not text_input:
        return

    uid = update.effective_user.id
    user = get_user(uid)

    # Menu buttons
    if text_input == "🔍 Vehicle Info":
        await message.reply_text(
            "🚗 Vehicle number bhejein (jaise: HR55AL0051)" + FOOTER,
            reply_markup=get_keyboard(uid)
        )
        return
    if text_input == "💳 Buy Credits":
        await buy_credits(update, context)
        return
    if text_input == "💰 My Balance":
        await my_balance(update, context)
        return
    if text_input == "⚙️ Admin Panel":
        await admin_panel(update, context)
        return

    # Payment plan selection: only while the user is in the Buy Credits flow.
    # This prevents a random "1", "2", etc. from being treated as a plan.
    if context.user_data.get("awaiting_plan") and text_input.isdigit():
        plan_no = int(text_input)
        if 1 <= plan_no <= len(CREDIT_PLANS):
            plan = get_plan_by_no(plan_no)
            if plan:
                _, price, credits = plan
                update_user(uid, selected_plan=plan_no)
                context.user_data["awaiting_plan"] = False
                await message.reply_text(
                    f"✅ *Plan #{plan_no} Selected*\n"
                    f"━━━━━━━━━━━━━━\n"
                    f"💵 Price : ₹{price}\n"
                    f"💳 Credits : {credits}\n"
                    f"━━━━━━━━━━━━━━\n\n"
                    f"Ab is UPI ID par *₹{price}* payment karein:\n"
                    f"🏦 `{UPI_ID}`\n"
                    f"👤 {UPI_NAME}\n\n"
                    f"⚠️ Payment ke baad *screenshot* yahan bhejein.\n"
                    f"(Caption me apna User ID likhein: `{uid}`)"
                    + FOOTER,
                    parse_mode="Markdown",
                    reply_markup=get_keyboard(uid)
                )
                return

    # Silently ignore usernames, Telegram IDs, arbitrary text, and malformed input.
    # Only messages matching a vehicle registration format proceed to the API.
    vehicle_no = normalize_vehicle_number(text_input)
    if not is_valid_vehicle_number(vehicle_no):
        return

    if not is_admin(uid) and user.get("credits", 0) <= 0:
        await message.reply_text(
            "❌ *Aapke paas credits nahi hain!*\n\n"
            "💳 'Buy Credits' dabakar credits kharidein.\n"
            f"💰 Aapka balance: *{user.get('credits', 0)}*" + FOOTER,
            parse_mode="Markdown",
            reply_markup=get_keyboard(uid)
        )
        return

    fetching_msg = await message.reply_text(
        f"🔍 `{vehicle_no}` ki information fetch ho rahi hai...",
        parse_mode="Markdown"
    )

    try:
        url = f"{API_BASE}?=ultra_vehicle&key={API_KEY}&xr={vehicle_no}"
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()

        try:
            data = clean_json(resp.json())
            result_text = json.dumps(data, indent=2, ensure_ascii=False)
        except ValueError:
            result_text = resp.text

        result_text = strip_usernames(result_text)
        if not result_text.strip():
            result_text = "Koi details available nahi hain."

        deduct_credit(uid)
        user = get_user(uid)
        remaining_display = (
            "UNLIMITED 👑 (Admin)"
            if is_admin(uid)
            else f"*{user.get('credits', 0)}*"
        )
        if len(result_text) > 3500:
            result_text = result_text[:3500] + "\n\n...(truncated)"

        try:
            await fetching_msg.delete()
        except Exception:
            pass

        await message.reply_text(
            f"📋 *Vehicle: {vehicle_no}*\n\n```\n{result_text}\n```\n\n"
            f"💳 Remaining Credits: {remaining_display}" + FOOTER,
            parse_mode="Markdown",
            reply_markup=get_keyboard(uid)
        )

    except requests.exceptions.Timeout:
        try:
            await fetching_msg.delete()
        except Exception:
            pass
        await message.reply_text(
            "⏰ API timeout. Thodi der baad try karein.\n(❌ Koi credit nahi kata)" + FOOTER,
            reply_markup=get_keyboard(uid)
        )
    except requests.exceptions.RequestException:
        try:
            await fetching_msg.delete()
        except Exception:
            pass
        await message.reply_text(
            "❌ API se connect nahi ho paya.\n(❌ Koi credit nahi kata)" + FOOTER,
            reply_markup=get_keyboard(uid)
        )
    except Exception:
        logging.exception("Vehicle lookup failed")
        try:
            await fetching_msg.delete()
        except Exception:
            pass
        await message.reply_text(
            "❌ Kuch galat ho gaya. Thodi der baad try karein." + FOOTER,
            reply_markup=get_keyboard(uid)
        )


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addcredits", cmd_addcredits))
    app.add_handler(CommandHandler("approve", cmd_approve))
    app.add_handler(CommandHandler("reject", cmd_reject))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("pending", cmd_pending))

    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_vehicle))

    print("Bot chal raha hai...")
    app.run_polling()


if __name__ == "__main__":
    main()
  