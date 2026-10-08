import requests
import sqlite3
import os
from datetime import datetime
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ==================== CONFIG ====================
BOT_TOKEN = "8880466315:AAF6ZSAnayY3sy-7gHfXIo0h9bI2zKV2kaQ"
API_URL   = "https://reuters-memorabilia-insulin-disclose.trycloudflare.com/num"
AADHAAR_API_URL = "https://reuters-memorabilia-insulin-disclose.trycloudflare.com/aadhaar"
API_KEY   = "DADDY"

ADMIN_IDS = [8147130832]
UPI_ID    = "riteshgiri7930@okhdfcbank"
UPI_NAME  = "Ritesh Giri"
SUPPORT   = "@Sadaura4u"

QR_IMAGE = "qr.png"

FREE_CREDITS    = 5
COST_PER_SEARCH = 1
DB_FILE         = "bot_data.db"
# ================================================
# ==================== CHANNEL CONFIG ====================
CHANNEL_USERNAME = "@Sadaura4u"
CHANNEL_LINK     = f"https://t.me/SAD_CONFIG{'SAD_CONFIG'}"
# =========================================================

# ==================== KEYBOARD BUTTONS ====================
BTN_NUM      = "📱 Number Information"
BTN_AADHAAR  = "🆔 Aadhaar Information"
BTN_HELP     = "❓ Help"
BTN_BUY      = "💎 Buy Credits"
BTN_MYCREDITS= "💳 My Credits"
BTN_REFER    = "🎁 Refer & Earn"

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton(BTN_NUM), KeyboardButton(BTN_AADHAAR)],
        [KeyboardButton(BTN_BUY), KeyboardButton(BTN_MYCREDITS)],
        [KeyboardButton(BTN_REFER), KeyboardButton(BTN_HELP)],
    ],
    resize_keyboard=True,
    is_persistent=True,
)
# =========================================================


# ==================== DATABASE ====================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id      INTEGER PRIMARY KEY,
            username     TEXT,
            first_name   TEXT,
            credits      INTEGER DEFAULT 0,
            banned       INTEGER DEFAULT 0,
            referred_by  INTEGER,
            joined_at    TEXT,
            total_search INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            amount     INTEGER,
            credits    INTEGER,
            utr        TEXT,
            status     TEXT DEFAULT 'pending',
            created_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS search_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            search_type TEXT,
            query       TEXT,
            searched_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def get_user(user_id):
    conn = db()
    u = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return u


def create_user(user_id, username, first_name, referred_by=None):
    conn = db()
    credits = FREE_CREDITS
    if referred_by and referred_by != user_id and get_user(referred_by):
        credits += 2
        conn.execute("UPDATE users SET credits = credits + 2 WHERE user_id=?", (referred_by,))
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name, credits, referred_by, joined_at) "
        "VALUES (?,?,?,?,?,?)",
        (user_id, username, first_name, credits, referred_by, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def update_credits(user_id, delta):
    conn = db()
    conn.execute("UPDATE users SET credits = credits + ? WHERE user_id=?", (delta, user_id))
    conn.commit()
    conn.close()


def set_banned(user_id, banned):
    conn = db()
    conn.execute("UPDATE users SET banned=? WHERE user_id=?", (1 if banned else 0, user_id))
    conn.commit()
    conn.close()


def inc_search(user_id):
    conn = db()
    conn.execute("UPDATE users SET total_search = total_search + 1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def log_search(user_id, search_type, query):
    conn = db()
    conn.execute(
        "INSERT INTO search_logs (user_id, search_type, query, searched_at) VALUES (?,?,?,?)",
        (user_id, search_type, query, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def recent_searches(limit=30):
    conn = db()
    rows = conn.execute(
        "SELECT * FROM search_logs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return rows


def all_users():
    conn = db()
    rows = conn.execute("SELECT * FROM users ORDER BY joined_at DESC").fetchall()
    conn.close()
    return rows


def add_payment(user_id, amount, credits, utr):
    conn = db()
    conn.execute(
        "INSERT INTO payments (user_id, amount, credits, utr, created_at) VALUES (?,?,?,?,?)",
        (user_id, amount, credits, utr, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def pending_payments():
    conn = db()
    rows = conn.execute("SELECT * FROM payments WHERE status='pending' ORDER BY id DESC").fetchall()
    conn.close()
    return rows


def approve_payment(pay_id):
    conn = db()
    p = conn.execute("SELECT * FROM payments WHERE id=?", (pay_id,)).fetchone()
    if p and p["status"] == "pending":
        conn.execute("UPDATE payments SET status='approved' WHERE id=?", (pay_id,))
        conn.execute("UPDATE users SET credits = credits + ? WHERE user_id=?", (p["credits"], p["user_id"]))
        conn.commit()
        conn.close()
        return p
    conn.close()
    return None


# ==================== HELPERS ====================
def is_admin(user_id):
    return user_id in ADMIN_IDS


def is_banned(user_id):
    u = get_user(user_id)
    return bool(u and u["banned"])


def format_result(data: dict) -> str:
    if not data.get("success"):
        return "❌ API se response nahi mila."
    if not data.get("found") or not data.get("result"):
        return (
            "🔍 *Koi information nahi mili is number ke liye.*\n\n"
            f"📊 Total results: `{data.get('count', 0)}`"
        )
    text = "✅ *Number Information Found*\n"
    text += f"📊 Total Records: `{data.get('count', 0)}`\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    for idx, record in enumerate(data["result"], start=1):
        text += f"*📌 Record #{idx}*\n"
        if isinstance(record, dict):
            for key, value in record.items():
                val_str = str(value)
                if len(val_str) > 200:
                    val_str = val_str[:200] + "..."
                text += f"• *{key}*: `{val_str}`\n"
        else:
            text += f"`{record}`\n"
        text += "\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n"
    text += f"🔹 Powered by {SUPPORT}"
    return text


def format_aadhaar_result(data: dict) -> str:
    if not isinstance(data, dict):
        return f"📄 *Aadhaar Response:*\n`{str(data)[:3000]}`"

    if not data.get("success", True):
        return f"❌ Aadhaar API error: `{data.get('error', 'Unknown error')}`"

    if data.get("found") is False or not data.get("result"):
        return (
            "🔍 *Aadhaar se koi information nahi mili.*\n\n"
            f"📊 Count: `{data.get('count', 0)}`"
        )

    text = "✅ *Aadhaar Information Found*\n"
    if "count" in data:
        text += f"📊 Total Records: `{data.get('count')}`\n"
    text += "━━━━━━━━━━━━━━━━━━━━\n\n"

    result = data.get("result")
    records = result if isinstance(result, list) else [result]

    for idx, record in enumerate(records, start=1):
        text += f"*📌 Record #{idx}*\n"
        if isinstance(record, dict):
            for key, value in record.items():
                val_str = str(value)
                if len(val_str) > 300:
                    val_str = val_str[:300] + "..."
                text += f"• *{key}*: `{val_str}`\n"
        else:
            text += f"`{record}`\n"
        text += "\n"

    text += "━━━━━━━━━━━━━━━━━━━━\n"
    text += f"🔹 Powered by {SUPPORT}"
    return text


def fetch_number_info(number: str) -> dict:
    try:
        resp = requests.get(API_URL, params={"number": number, "key": API_KEY}, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Request timeout ho gaya."}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"Network error: {e}"}
    except ValueError:
        return {"success": False, "error": "Invalid JSON response."}


def fetch_aadhaar_info(aadhaar: str) -> dict:
    try:
        resp = requests.get(
            AADHAAR_API_URL,
            params={"value": aadhaar, "key": API_KEY},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Aadhaar request timeout ho gaya."}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"Network error: {e}"}
    except ValueError:
        return {"success": False, "error": "Invalid JSON response."}


async def notify_admins(context, user, search_type, query):
    uname = f"@{user.username}" if user.username else "_(no username)_"
    now = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    live_msg = (
        f"🔍 *LIVE {search_type.upper()} SEARCH*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Name: {user.full_name}\n"
        f"🔗 Username: {uname}\n"
        f"🆔 User ID: `{user.id}`\n"
        f"🔎 Query: `{query}`\n"
        f"🕐 Time: {now}\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, live_msg, parse_mode="Markdown")
        except Exception as e:
            print(f"Live notify failed ({admin_id}): {e}")


# ==================== QR SENDER ====================
async def send_qr(message):
    caption = (
        f"📲 *Scan & Pay*\n\n"
        f"👤 Name: {UPI_NAME}\n"
        f"💳 UPI ID: `{UPI_ID}`\n\n"
        f"💎 *Plans:*\n"
        f"• ₹25 → 25 lookups\n"
        f"• ₹50 → 75 lookups\n"
        f"• ₹100 → 150 lookups\n\n"
        f"✅ Payment ke baad `/pay <amount> <utr>` bhejein."
    )

    if os.path.exists(QR_IMAGE):
        try:
            with open(QR_IMAGE, "rb") as f:
                await message.reply_photo(photo=f, caption=caption, parse_mode="Markdown")
        except Exception as e:
            await message.reply_text(f"⚠️ QR bhejne me error: {e}\n\n{caption}", parse_mode="Markdown")
    else:
        await message.reply_text(
            f"📲 *Scan & Pay*\n\n"
            f"👤 Name: {UPI_NAME}\n"
            f"💳 UPI ID: `{UPI_ID}`\n\n"
            f"💎 *Plans:*\n"
            f"• ₹25 → 25 lookups\n"
            f"• ₹50 → 75 lookups\n"
            f"• ₹100 → 150 lookups\n\n"
            f"• ₹300 → 100000000 lookups\n\n"
            f"✅ Payment ke baad `/pay <amount> <utr>` bhejein.\n\n"
            f"⚠️ _(QR image `{QR_IMAGE}` folder me nahi mili)_",
            parse_mode="Markdown",
        )


# ==================== USER COMMANDS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args or []
    referred_by = None
    if args and args[0].startswith("ref_"):
        try:
            referred_by = int(args[0].split("_")[1])
        except ValueError:
            referred_by = None

    existing = get_user(user.id)
    if not existing:
        create_user(user.id, user.username, user.first_name, referred_by)
        welcome_extra = f"\n🎁 *Aapko {FREE_CREDITS} free credits mile hain!*"
    else:
        welcome_extra = ""

    u = get_user(user.id)
    await update.message.reply_text(
        f"👋 *Welcome {user.first_name}!*\n\n"
        f"💳 Aapke credits: `{u['credits']}`\n"
        f"{welcome_extra}\n\n"
        "👇 Neeche diye gaye buttons se kaam karein:",
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD,
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Help & Commands:*\n"
        "• 📱 *Number Information* — Mobile number info (1 credit)\n"
        "• 🆔 *Aadhaar Information* — Aadhaar info (1 credit)\n"
        "• 💎 *Buy Credits* — Credits kharidein\n"
        "• 💳 *My Credits* — Balance dekhein\n"
        "• 🎁 *Refer & Earn* — Referral link\n\n"
        "🔧 *Extra Commands:*\n"
        "• `/num <number>` — Direct number search\n"
        "• `/aadhaar <number>` — Direct aadhaar search\n"
        "• `/pay <amount> <utr>` — Payment submit\n\n"
        f"*Support:* {SUPPORT}",
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD,
    )


async def mycredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    if not u:
        await update.message.reply_text("Pehle /start karein.", reply_markup=MAIN_KEYBOARD)
        return
    await update.message.reply_text(
        f"💳 *Your Credits:* `{u['credits']}`\n"
        f"🔍 *Total Searches:* `{u['total_search']}`",
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD,
    )


async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start=ref_{update.effective_user.id}"
    await update.message.reply_text(
        f"🎁 *Referral Program*\n\n"
        f"Apne dost ko invite karein, har successful referral par *+2 credits* payein.\n\n"
        f"🔗 Aapka link:\n`{link}`",
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD,
    )


# ==================== CREDIT CHECK HELPER ====================
async def check_and_charge(update, context, user):
    if is_banned(user.id):
        await update.message.reply_text("🚫 Aapko ban kiya gaya hai.", reply_markup=MAIN_KEYBOARD)
        return False

    if not is_admin(user.id):
        u = get_user(user.id)
        if not u:
            await update.message.reply_text("Pehle /start karein.", reply_markup=MAIN_KEYBOARD)
            return False
        if u["credits"] < COST_PER_SEARCH:
            await update.message.reply_text(
                f"❌ *Aapke paas {COST_PER_SEARCH} credit nahi hai.*\n"
                f"💳 Balance: `{u['credits']}`\n\n"
                "👉 *Buy Credits* button dabayein.",
                parse_mode="Markdown",
                reply_markup=MAIN_KEYBOARD,
            )
            return False
    return True


# ==================== NUMBER SEARCH ====================
async def num_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not context.args:
        await update.message.reply_text(
            "⚠️ *Mobile number bhejein.*\nExample: `9876543210`",
            parse_mode="Markdown",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    if not await check_and_charge(update, context, user):
        return

    number = context.args[0].strip()
    msg = await update.message.reply_text("⏳ *Searching...*", parse_mode="Markdown")

    await notify_admins(context, user, "mobile", number)

    data = fetch_number_info(number)

    if "error" in data and not data.get("success"):
        await msg.edit_text(f"❌ {data['error']}")
        return

    if not is_admin(user.id):
        update_credits(user.id, -COST_PER_SEARCH)
    inc_search(user.id)
    log_search(user.id, "mobile", number)

    try:
        result_text = format_result(data)
        u = get_user(user.id)
        result_text += f"\n\n💳 *Remaining Credits:* `{u['credits']}`"
        await msg.edit_text(result_text, parse_mode="Markdown")
    except Exception as e:
        await msg.edit_text(f"⚠️ Error: {e}\n\nRaw: {str(data)[:1000]}")


# ==================== AADHAAR SEARCH ====================
async def aadhaar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if not context.args:
        await update.message.reply_text(
            "⚠️ *Aadhaar number bhejein.*\nExample: `123456789012`",
            parse_mode="Markdown",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    if not await check_and_charge(update, context, user):
        return

    aadhaar = context.args[0].strip()
    digits = "".join(c for c in aadhaar if c.isdigit())
    if len(digits) != 12:
        await update.message.reply_text(
            "❌ *Aadhaar number 12 digits ka hona chahiye.*\n"
            "Example: `123456789012`",
            parse_mode="Markdown",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    msg = await update.message.reply_text("⏳ *Aadhaar searching...*", parse_mode="Markdown")

    await notify_admins(context, user, "aadhaar", digits)

    data = fetch_aadhaar_info(digits)

    if "error" in data and not data.get("success", True):
        await msg.edit_text(f"❌ {data['error']}")
        return

    if not is_admin(user.id):
        update_credits(user.id, -COST_PER_SEARCH)
    inc_search(user.id)
    log_search(user.id, "aadhaar", digits)

    try:
        result_text = format_aadhaar_result(data)
        u = get_user(user.id)
        result_text += f"\n\n💳 *Remaining Credits:* `{u['credits']}`"
        await msg.edit_text(result_text, parse_mode="Markdown")
    except Exception as e:
        await msg.edit_text(f"⚠️ Error: {e}\n\nRaw: {str(data)[:1000]}")


# ==================== TEXT HANDLER ====================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()

    # ---- Keyboard button handling ----
    if text == BTN_NUM:
        await update.message.reply_text(
            "📱 *Mobile Number bhejein:*\nExample: `9876543210`",
            parse_mode="Markdown",
            reply_markup=MAIN_KEYBOARD,
        )
        return
    if text == BTN_AADHAAR:
        await update.message.reply_text(
            "🆔 *Aadhaar Number bhejein:*\nExample: `123456789012`",
            parse_mode="Markdown",
            reply_markup=MAIN_KEYBOARD,
        )
        return
    if text == BTN_HELP:
        await help_cmd(update, context)
        return
    if text == BTN_BUY:
        await buy(update, context)
        return
    if text == BTN_MYCREDITS:
        await mycredits(update, context)
        return
    if text == BTN_REFER:
        await refer(update, context)
        return

    # ---- Auto-detect number / aadhaar ----
    digits = "".join(c for c in text if c.isdigit())

    if len(digits) == 12:
        context.args = [digits]
        await aadhaar_command(update, context)
    elif len(digits) >= 10:
        context.args = [digits]
        await num_command(update, context)
    else:
        await update.message.reply_text(
            "❓ 10-digit mobile number ya 12-digit Aadhaar bhejein.\n"
            "Ya neeche ke buttons use karein.",
            parse_mode="Markdown",
            reply_markup=MAIN_KEYBOARD,
        )


# ==================== BUY / PAYMENT ====================
PLANS = [
    {"credits": 25,  "price": 25,  "label": "Starter"},
    {"credits": 75,  "price": 50,  "label": "Basic"},
    {"credits": 150, "price": 100, "label": "Popular"},
    {"credits": 300, "price": 100000000, "label": "Popular"},
]


async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "💎 *Credits Plans*\n\n"
    for p in PLANS:
        text += f"• {p['label']}: *{p['credits']} lookups* — ₹{p['price']}\n"
    text += "\n👉 Payment ke liye `/pay <amount> <utr>` bhejein.\n"
    text += f"📲 UPI: `{UPI_ID}`\n"
    text += f"🆘 Support: {SUPPORT}"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)
    await send_qr(update.message)


async def pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ *Usage:* `/pay <amount> <utr>`\n"
            f"Example: `/pay 50 123456789012`\n\n"
            f"📲 UPI: `{UPI_ID}`",
            parse_mode="Markdown",
            reply_markup=MAIN_KEYBOARD,
        )
        await send_qr(update.message)
        return

    try:
        amount = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Amount number me dein.", reply_markup=MAIN_KEYBOARD)
        return

    utr = context.args[1].strip()

    plan = next((p for p in PLANS if p["price"] == amount), None)
    if not plan:
        await update.message.reply_text(
            "❌ Is amount ka koi plan nahi hai. *Buy Credits* button dabayein.",
            parse_mode="Markdown",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    user = update.effective_user
    add_payment(user.id, amount, plan["credits"], utr)

    await update.message.reply_text(
        f"✅ *Payment submitted!*\n\n"
        f"💰 Amount: ₹{amount}\n"
        f"💎 Credits: {plan['credits']}\n"
        f"🧾 UTR: `{utr}`\n\n"
        "⏳ Admin approve karega, phir credits add ho jayenge.",
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD,
    )

    uname = f"@{user.username}" if user.username else "_(no username)_"
    full_name = user.full_name or "-"
    now = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    notif = (
        "🔔 *NEW PAYMENT RECEIVED!*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *Name:* {full_name}\n"
        f"🔗 *Username:* {uname}\n"
        f"🆔 *User ID:* `{user.id}`\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 *Amount:* ₹{amount}\n"
        f"💎 *Credits:* {plan['credits']}\n"
        f"📦 *Plan:* {plan['label']}\n"
        f"🧾 *UTR:* `{utr}`\n"
        f"🕐 *Time:* {now}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Approve karne ke liye:\n"
        f"`/approve {user.id} {plan['credits']}`"
    )

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, notif, parse_mode="Markdown")
        except Exception as e:
            print(f"Admin notify failed ({admin_id}): {e}")


# ==================== ADMIN PANEL ====================
def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not is_admin(update.effective_user.id):
            await update.message.reply_text("🚫 Admin only.")
            return
        return await func(update, context)
    return wrapper


@admin_only
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = db()
    total = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    banned = conn.execute("SELECT COUNT(*) c FROM users WHERE banned=1").fetchone()["c"]
    searches = conn.execute("SELECT COALESCE(SUM(total_search),0) s FROM users").fetchone()["s"]
    pend = conn.execute("SELECT COUNT(*) c FROM payments WHERE status='pending'").fetchone()["c"]
    conn.close()

    text = (
        "🛠️ *ADMIN PANEL*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Total Users: `{total}`\n"
        f"🚫 Banned: `{banned}`\n"
        f"🔍 Total Searches: `{searches}`\n"
        f"⏳ Pending Payments: `{pend}`\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "*Commands:*\n"
        "• `/users` — user list\n"
        "• `/logs` — recent searches live\n"
        "• `/addcredits <id> <n>`\n"
        "• `/removecredits <id> <n>`\n"
        "• `/ban <id>` / `/unban <id>`\n"
        "• `/broadcast <msg>`\n"
        "• `/pending` — pending payments\n"
        "• `/approve <id> <credits>`\n"
        "• `/userinfo <id>`"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


@admin_only
async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = recent_searches(30)
    if not rows:
        await update.message.reply_text("Koi search log nahi.")
        return
    text = "📜 *Recent Searches (latest 30)*\n\n"
    for r in rows:
        u = get_user(r["user_id"])
        name = u["first_name"] if u else "?"
        icon = "📱" if r["search_type"] == "mobile" else "🆔"
        text += (
            f"{icon} `{r['query']}` — {name} (`{r['user_id']}`)\n"
            f"   🕐 {r['searched_at'][:19]}\n"
        )
    await update.message.reply_text(text, parse_mode="Markdown")


@admin_only
async def users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = all_users()[:50]
    if not rows:
        await update.message.reply_text("Koi user nahi.")
        return
    text = "👥 *Users (latest 50)*\n\n"
    for u in rows:
        flag = "🚫" if u["banned"] else "✅"
        text += (
            f"{flag} `{u['user_id']}` | {u['first_name'] or '-'} | "
            f"💳 {u['credits']} | 🔍 {u['total_search']}\n"
        )
    await update.message.reply_text(text, parse_mode="Markdown")


@admin_only
async def userinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/userinfo <id>`", parse_mode="Markdown")
        return
    try:
        uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid id.")
        return
    u = get_user(uid)
    if not u:
        await update.message.reply_text("User nahi mila.")
        return
    await update.message.reply_text(
        f"👤 *User Info*\n\n"
        f"🆔 ID: `{u['user_id']}`\n"
        f"👤 Name: {u['first_name'] or '-'}\n"
        f"🔗 Username: @{u['username'] or '-'}\n"
        f"💳 Credits: `{u['credits']}`\n"
        f"🔍 Searches: `{u['total_search']}`\n"
        f"🚫 Banned: `{bool(u['banned'])}`\n"
        f"📅 Joined: `{u['joined_at']}`",
        parse_mode="Markdown",
    )


@admin_only
async def addcredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: `/addcredits <id> <n>`", parse_mode="Markdown")
        return
    try:
        uid, n = int(context.args[0]), int(context.args[1])
    except ValueError:
        await update.message.reply_text("Invalid args.")
        return
    if not get_user(uid):
        await update.message.reply_text("User nahi mila.")
        return
    update_credits(uid, n)
    u = get_user(uid)
    await update.message.reply_text(
        f"✅ `{n}` credits added to `{uid}`.\n💳 New balance: `{u['credits']}`",
        parse_mode="Markdown",
    )
    try:
        await context.bot.send_message(
            uid,
            f"🎁 Admin ne aapko `{n}` credits diye!\n💳 Balance: `{u['credits']}`",
            parse_mode="Markdown",
        )
    except Exception:
        pass


@admin_only
async def removecredits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: `/removecredits <id> <n>`", parse_mode="Markdown")
        return
    try:
        uid, n = int(context.args[0]), int(context.args[1])
    except ValueError:
        await update.message.reply_text("Invalid args.")
        return
    update_credits(uid, -n)
    u = get_user(uid)
    await update.message.reply_text(
        f"✅ `{n}` credits removed from `{uid}`.\n💳 New balance: `{u['credits']}`",
        parse_mode="Markdown",
    )


@admin_only
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/ban <id>`", parse_mode="Markdown")
        return
    try:
        uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid id.")
        return
    set_banned(uid, True)
    await update.message.reply_text(f"🚫 Banned `{uid}`", parse_mode="Markdown")


@admin_only
async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/unban <id>`", parse_mode="Markdown")
        return
    try:
        uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid id.")
        return
    set_banned(uid, False)
    await update.message.reply_text(f"✅ Unbanned `{uid}`", parse_mode="Markdown")


@admin_only
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/broadcast <msg>`", parse_mode="Markdown")
        return
    msg = " ".join(context.args)
    rows = all_users()
    ok, fail = 0, 0
    for u in rows:
        try:
            await context.bot.send_message(
                u["user_id"], f"📢 *Broadcast*\n\n{msg}", parse_mode="Markdown"
            )
            ok += 1
        except Exception:
            fail += 1
    await update.message.reply_text(f"✅ Sent: {ok}, ❌ Failed: {fail}")


@admin_only
async def pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = pending_payments()
    if not rows:
        await update.message.reply_text("Koi pending payment nahi.")
        return
    text = "⏳ *Pending Payments*\n\n"
    for p in rows[:30]:
        text += (
            f"#{p['id']} | 👤 `{p['user_id']}` | ₹{p['amount']} | "
            f"💎 {p['credits']} | UTR `{p['utr']}`\n"
            f"Approve: `/approve {p['user_id']} {p['credits']}`\n\n"
        )
    await update.message.reply_text(text, parse_mode="Markdown")


@admin_only
async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: `/approve <user_id> <credits>`", parse_mode="Markdown")
        return
    try:
        uid, credits = int(context.args[0]), int(context.args[1])
    except ValueError:
        await update.message.reply_text("Invalid args.")
        return

    conn = db()
    p = conn.execute(
        "SELECT * FROM payments WHERE user_id=? AND credits=? AND status='pending' ORDER BY id LIMIT 1",
        (uid, credits),
    ).fetchone()
    conn.close()

    if not p:
        await update.message.reply_text("Koi matching pending payment nahi mila.")
        return

    approve_payment(p["id"])
    u = get_user(uid)

    await update.message.reply_text(
        f"✅ Payment approved for `{uid}`.\n💳 New balance: `{u['credits']}`",
        parse_mode="Markdown",
    )

    try:
        await context.bot.send_message(
            uid,
            f"🎉 *Payment Approved!*\n\n💎 {credits} credits added.\n💳 Balance: `{u['credits']}`",
            parse_mode="Markdown",
        )
    except Exception:
        pass


# ==================== MAIN ====================
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    # User commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("num", num_command))
    app.add_handler(CommandHandler("aadhaar", aadhaar_command))
    app.add_handler(CommandHandler("mycredits", mycredits))
    app.add_handler(CommandHandler("refer", refer))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("pay", pay))

    # Admin commands
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("logs", logs))
    app.add_handler(CommandHandler("users", users_cmd))
    app.add_handler(CommandHandler("userinfo", userinfo))
    app.add_handler(CommandHandler("addcredits", addcredits))
    app.add_handler(CommandHandler("removecredits", removecredits))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("pending", pending))
    app.add_handler(CommandHandler("approve", approve))

    # Text handler (keyboard + auto-detect)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("🤖 Bot is running... (Ctrl+C to stop)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()