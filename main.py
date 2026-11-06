import logging
import re
import json
import os
import io
import requests
from datetime import datetime, timedelta
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes
)

# ========== PDF LIBRARIES ==========
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logging.warning("reportlab not installed. PDF feature disabled. Install: pip install reportlab")

# ========== CONFIG ==========
BOT_TOKEN = ("8811516200:AAHGviaM13QMw9ejl4KSchL7_tfEM6pog1A")

# ---------- ALLPRINTHUB API ----------
API_BASE = "https://api.allprinthub.in/api"
API_KEY = "7day"
# -------------------------------------

ADMIN_IDS = {8147130832}

# ========== CREDITS / PAYMENT CONFIG ==========
UPI_ID = "riteshgiri7930@okhdfcbank"
UPI_NAME = "Ritesh Giri"
WELCOME_CREDITS = 5
DB_FILE = "users_db.json"
PENDING_FILE = "pending_payments.json"

# ========== CREDIT PLANS ==========
CREDIT_PLANS = [
    (1, 50,  10),
    (2, 100, 30),
    (3, 150, 50),
    (4, 200, 100),
    (5, 300, 180),
    (6, 500, -1),
]

PREMIUM_PLAN_NO = 6
PREMIUM_DAYS = 180

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

WELCOME_TEXT = (
    "🙏🏻 Swagat hai!\n"
    "🎀 Me Ritesh Ka AI Assistant 🎀"
)

FOOTER = "\n\n━━━━━━━━━━━━━━\n⚡ Powered by Ritesh Goswami"

# Sensitive keys: hide real user data from raw JSON
SENSITIVE_KEYS = {
    "username", "user", "user_name",
    "father_name", "mother_name",
    "contact", "email", "address", "full_name", "first_name", "last_name"
}

STRIP_META_KEYS = {
    "response_time", "response time", "powered_by", "powered by",
    "support", "premium_bot", "premium bot", "premium", "developer", "dev",
    "credit", "credits", "api", "bot", "channel", "join", "telegram",
    "owner", "powered", "support_group", "support group",
    "response", "time", "ms", "latency",
    "premium_bot_username", "support_username", "developer_username",
    "api_provider", "provider", "powered", "power",
    "verification status", "data status", "response time", "powered by",
    "credit_left", "credits_left", "credit used", "credits used",
    "quota", "quota_left", "remaining", "plan", "plan_name",
    "trx", "trxedition", "trx_edition",
}

PROVIDER_BLACKLIST = (
    "ronakapi", "ronak api", "ronak_api",
    "xrosint", "xrosintpremium", "xrosintpremiumbot", "xrosint_support",
    "xrosint support", "xrosint_premium",
    "@ronakapi", "@xrosint", "@xrosintpremiumbot", "@xrosint support",
    "@trx", "@trxedition", "@trx_edition", "trxedition", "trx edition",
    "trx_edition", "trx.api", "trx api",
    "powered by", "powered_by", "telegram.me", "t.me/",
)

MOBILE_REGEX = re.compile(r"^[6-9][0-9]{9}$")


def is_valid_mobile(text: str) -> bool:
    cleaned = re.sub(r"[\s\-]", "", text)
    if cleaned.startswith("+91"):
        cleaned = cleaned[3:]
    elif cleaned.startswith("91") and len(cleaned) == 12:
        cleaned = cleaned[2:]
    return bool(MOBILE_REGEX.match(cleaned))


def normalize_mobile(text: str) -> str:
    cleaned = re.sub(r"[\s\-]", "", text)
    if cleaned.startswith("+91"):
        cleaned = cleaned[3:]
    elif cleaned.startswith("91") and len(cleaned) == 12:
        cleaned = cleaned[2:]
    return cleaned


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
            "premium_until": None,
        }
        save_db(db)
    return db[key]


def update_user(uid: int, **kwargs):
    db = load_db()
    key = str(uid)
    if key not in db:
        db[key] = {
            "credits": WELCOME_CREDITS,
            "joined": datetime.now().isoformat(),
            "total_searches": 0,
            "premium_until": None,
        }
    db[key].update(kwargs)
    save_db(db)
    return db[key]


def is_premium_active(uid: int) -> bool:
    if is_admin(uid):
        return True
    db = load_db()
    key = str(uid)
    if key not in db:
        return False
    until = db[key].get("premium_until")
    if not until:
        return False
    try:
        return datetime.fromisoformat(until) > datetime.now()
    except Exception:
        return False


def add_premium_days(uid: int, days: int) -> str:
    db = load_db()
    key = str(uid)
    if key not in db:
        db[key] = {"credits": WELCOME_CREDITS, "joined": datetime.now().isoformat(),
                   "total_searches": 0, "premium_until": None}
    current = db[key].get("premium_until")
    base = datetime.now()
    if current:
        try:
            cur_dt = datetime.fromisoformat(current)
            if cur_dt > base:
                base = cur_dt
        except Exception:
            pass
    new_until = (base + timedelta(days=days)).isoformat()
    db[key]["premium_until"] = new_until
    save_db(db)
    return new_until


def deduct_credit(uid: int) -> bool:
    if is_admin(uid):
        db = load_db()
        key = str(uid)
        if key not in db:
            db[key] = {"credits": 999999, "joined": datetime.now().isoformat(),
                       "total_searches": 0, "premium_until": None}
        db[key]["total_searches"] = db[key].get("total_searches", 0) + 1
        save_db(db)
        return True

    if is_premium_active(uid):
        db = load_db()
        key = str(uid)
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


def _is_provider_string(v: str) -> bool:
    if not isinstance(v, str):
        return False
    low = v.lower()
    return any(bad in low for bad in PROVIDER_BLACKLIST)


def strip_metadata(obj):
    if isinstance(obj, dict):
        new = {}
        for k, v in obj.items():
            key_lower = k.lower().replace("_", " ").strip()
            key_norm = k.lower().strip()
            if key_norm in STRIP_META_KEYS or key_lower in STRIP_META_KEYS:
                continue
            if isinstance(v, str) and _is_provider_string(v):
                continue
            cleaned = strip_metadata(v)
            if cleaned in (None, "", [], {}):
                continue
            new[k] = cleaned
        return new
    elif isinstance(obj, list):
        return [
            strip_metadata(item) for item in obj
            if not (isinstance(item, str) and _is_provider_string(item))
        ]
    return obj


def strip_usernames(text: str) -> str:
    lines = text.splitlines()
    cleaned_lines = []
    in_verif_block = False

    for line in lines:
        raw = line
        low = line.lower()

        if "verification status" in low:
            in_verif_block = True
            continue
        if in_verif_block:
            if line.strip() == "":
                in_verif_block = False
            continue

        if any(tag in low for tag in (
            "powered by", "powered_by", "support :", "support:",
            "premium bot", "premium_bot", "response time", "data status",
            "ronakapi", "xrosint", "xrosintpremium", "telegram.me", "t.me/",
            "trxedition", "trx edition", "trx_edition", "trx.api",
            "@trx", "@trxedition", "credit left", "credits left",
            "credit used", "credits used", "quota",
        )):
            continue

        line = re.sub(r"@[A-Za-z0-9_]{2,}", "", line)
        line = re.sub(
            r"(?i)\b(username|user|support|premium bot|powered by|developer|channel|"
            r"join|contact|owner|credit|credits|api provider)\s*[:=]\s*\S*",
            "",
            line
        )
        line = re.sub(r"(?i)\btrx[_ ]?edition\b", "", line)
        line = re.sub(r"(?i)\btrx[_ ]?api\b", "", line)

        stripped = line.strip()
        if stripped in ("", ":", "-", "—", "=", "*", "**", "┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈"):
            if raw.strip() == "":
                cleaned_lines.append("")
            continue
        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def get_plan_by_no(plan_no: int):
    for p in CREDIT_PLANS:
        if p[0] == plan_no:
            return p
    return None


def is_premium_plan(plan_no) -> bool:
    return plan_no == PREMIUM_PLAN_NO


# ========== KEYBOARD ==========
def get_keyboard(user_id: int = None) -> ReplyKeyboardMarkup:
    row1 = [
        KeyboardButton("📱 Number Info"),
    ]
    row2 = [
        KeyboardButton("💳 Buy Credits"),
    ]
    row3 = [
        KeyboardButton("💰 My Balance"),
    ]

    if user_id is not None and is_admin(user_id):
        row3.append(KeyboardButton("⚙️ Admin Panel"))

    keyboard = [row1, row2, row3]
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Mobile number likhein..."
    )


# ========== HANDLERS ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid)

    if is_admin(uid):
        status_note = "\n👑 *Admin:* Unlimited free credits."
    elif is_premium_active(uid):
        until = user.get("premium_until", "")
        try:
            until_dt = datetime.fromisoformat(until).strftime("%d %b %Y")
        except Exception:
            until_dt = until
        status_note = f"\n💎 *Premium Active* (till {until_dt}) — Unlimited searches!"
    else:
        status_note = f"\n💳 Aapke credits: *{user['credits']}*"

    await update.message.reply_text(
        WELCOME_TEXT + "\n\n"
        "📱 Mobile number bhejein (jaise: 9162516577)\n\n"
        "Main aapko uski information dunga.\n"
        + status_note + FOOTER,
        parse_mode="Markdown",
        reply_markup=get_keyboard(uid)
    )


async def my_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid)

    if is_admin(uid):
        credit_line = "💳 Credits : *UNLIMITED* 👑 (Admin)"
        premium_line = ""
    elif is_premium_active(uid):
        until = user.get("premium_until", "")
        try:
            until_dt = datetime.fromisoformat(until).strftime("%d %b %Y, %I:%M %p")
        except Exception:
            until_dt = until
        credit_line = f"💳 Credits : *{user.get('credits', 0)}* (Premium me hold)"
        premium_line = f"💎 Premium Active till : *{until_dt}*\n"
    else:
        credit_line = f"💳 Credits : *{user.get('credits', 0)}*"
        premium_line = ""

    await update.message.reply_text(
        f"💰 *Aapka Balance*\n"
        f"━━━━━━━━━━━━━━\n"
        f"👤 User ID : `{uid}`\n"
        f"{credit_line}\n"
        f"{premium_line}"
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
        if credits == -1:
            plans_text += f"*{plan_no}.* ₹{price} → *💎 PREMIUM (6 Months Unlimited)*\n"
        else:
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
        "   (jaise `1` = 10 credits | `6` = Premium 6 months)\n"
        "2️⃣ UPI ID par payment karein\n"
        "3️⃣ Payment ka *screenshot* yahan bhejein\n"
        "4️⃣ Admin verify karke credits/premium add karega\n\n"
        f"⚠️ Screenshot ke saath apna User ID likhein: `{uid}`\n"
        "━━━━━━━━━━━━━━\n"
        "👉 Ab apna *plan number* (1-6) bhejein."
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
            "ℹ️ Aap admin hain. Payment approve karne ke liye `/approve <user_id> <credits>` "
            "ya premium ke liye `/grantpremium <user_id>` use karein."
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
            if credits == -1:
                plan_info = f"📦 Plan : #{plan[0]} (₹{price} → 💎 PREMIUM 6 Months)"
            else:
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
        f"✅ Approve (credits) : `/approve {uid} <credits>`\n"
        f"💎 Grant Premium    : `/grantpremium {uid}`\n"
        f"❌ Reject           : `/reject {uid}`"
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
        "⏳ Verify hone ke baad credits/premium add ho jayega.\n"
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
    premium_count = sum(
        1 for u in db.values()
        if u.get("premium_until") and _safe_premium_check(u.get("premium_until"))
    )

    text = (
        "⚙️ *ADMIN PANEL*\n"
        "━━━━━━━━━━━━━━\n"
        f"👤 Admin ID : `{uid}`\n"
        f"🌐 API      : `{API_BASE}`\n"
        f"💳 UPI ID   : `{UPI_ID}`\n"
        "━━━━━━━━━━━━━━\n"
        f"👥 Total Users    : *{total_users}*\n"
        f"💰 Total Credits  : *{total_credits}*\n"
        f"💎 Premium Users  : *{premium_count}*\n"
        f"⏳ Pending Payments : *{pending_count}*\n"
        "━━━━━━━━━━━━━━\n"
        "👑 *Aapko unlimited free credits hain.*\n"
        "━━━━━━━━━━━━━━\n"
        "*Commands:*\n"
        "`/addcredits <user_id> <credits>`\n"
        "`/approve <user_id> <credits>`\n"
        "`/grantpremium <user_id> [days]`\n"
        "`/revokepremium <user_id>`\n"
        "`/reject <user_id>`\n"
        "`/balance <user_id>`\n"
        "`/pending`\n"
        "`/broadcast <message>`\n"
        + FOOTER
    )
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_keyboard(uid)
    )


def _safe_premium_check(until_iso: str) -> bool:
    try:
        return datetime.fromisoformat(until_iso) > datetime.now()
    except Exception:
        return False


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
                "Ab aap number search kar sakte hain." + FOOTER
            ),
            parse_mode="Markdown"
        )
    except Exception:
        pass


async def cmd_grant_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        return
    args = context.args
    if len(args) not in (1, 2):
        await update.message.reply_text(
            "Usage: `/grantpremium <user_id> [days]`\n(default days = 180)", parse_mode="Markdown"
        )
        return
    try:
        target = int(args[0])
        days = int(args[1]) if len(args) == 2 else PREMIUM_DAYS
    except ValueError:
        await update.message.reply_text("❌ Invalid input.")
        return

    new_until = add_premium_days(target, days)
    try:
        until_disp = datetime.fromisoformat(new_until).strftime("%d %b %Y, %I:%M %p")
    except Exception:
        until_disp = new_until

    pending = load_pending()
    pending.pop(str(target), None)
    save_pending(pending)

    update_user(target, selected_plan=None)

    await update.message.reply_text(
        f"💎 *Premium granted!*\n"
        f"👤 User: `{target}`\n"
        f"📅 Days added: *{days}*\n"
        f"⏳ Valid till: *{until_disp}*",
        parse_mode="Markdown"
    )
    try:
        await context.bot.send_message(
            chat_id=target,
            text=(
                "💎 *PREMIUM ACTIVATED!*\n"
                f"📅 Duration: *{days} days*\n"
                f"⏳ Valid till: *{until_disp}*\n\n"
                "✨ Ab aap *UNLIMITED* searches kar sakte hain — koi credit nahi katega!"
                + FOOTER
            ),
            parse_mode="Markdown"
        )
    except Exception:
        pass


async def cmd_revoke_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        return
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Usage: `/revokepremium <user_id>`", parse_mode="Markdown")
        return
    try:
        target = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
        return
    update_user(target, premium_until=None)
    await update.message.reply_text(f"✅ `{target}` ka premium revoke kar diya.", parse_mode="Markdown")
    try:
        await context.bot.send_message(
            chat_id=target,
            text="⚠️ Aapka premium plan revoke kar diya gaya hai." + FOOTER,
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
    update_user(target, selected_plan=None)

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
    if is_admin(target):
        credit_display = "UNLIMITED 👑 (Admin)"
    elif is_premium_active(target):
        until = user.get("premium_until", "")
        try:
            until_dt = datetime.fromisoformat(until).strftime("%d %b %Y, %I:%M %p")
        except Exception:
            until_dt = until
        credit_display = f"UNLIMITED 💎 (till {until_dt})"
    else:
        credit_display = user.get('credits', 0)

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
                if plan[2] == -1:
                    plan_str = f" | Plan #{plan[0]} (₹{plan[1]}→💎 PREMIUM)"
                else:
                    plan_str = f" | Plan #{plan[0]} (₹{plan[1]}→{plan[2]}cr)"
        lines.append(
            f"👤 `{user_id}` — {info.get('name', '')} "
            f"(@{info.get('username', 'N/A')}){plan_str}"
        )
    lines.append("\nApprove: `/approve <user_id> <credits>`")
    lines.append("Premium: `/grantpremium <user_id>`")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        return

    if not context.args and not update.message.reply_to_message:
        await update.message.reply_text(
            "⚠️ Usage: `/broadcast <message>` ya kisi message ka reply karke `/broadcast` likhein.",
            parse_mode="Markdown"
        )
        return

    db = load_db()
    if not db:
        await update.message.reply_text("❌ Database me koi users nahi hain.")
        return

    status_msg = await update.message.reply_text("📢 Broadcast shuru ho raha hai...")

    success = 0
    failed = 0
    total = len(db)

    reply_msg = update.message.reply_to_message
    broadcast_text = " ".join(context.args) if context.args else ""

    for user_id_str in db.keys():
        try:
            target_id = int(user_id_str)
            if reply_msg:
                await context.bot.copy_message(
                    chat_id=target_id,
                    from_chat_id=update.effective_chat.id,
                    message_id=reply_msg.message_id
                )
            else:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=f"📢 *Announcement* 📢\n━━━━━━━━━━━━━━\n\n{broadcast_text}" + FOOTER,
                    parse_mode="Markdown"
                )
            success += 1
        except Exception:
            failed += 1

    await status_msg.edit_text(
        f"📢 *Broadcast Complete!*\n"
        f"━━━━━━━━━━━━━━\n"
        f"👥 Total Users: *{total}*\n"
        f"✅ Success: *{success}*\n"
        f"❌ Failed: *{failed}*",
        parse_mode="Markdown"
    )


# ========== API CALL HELPERS ==========

def _safe_json(resp):
    try:
        return resp.json(), None
    except ValueError:
        return None, resp.text


def _records_from(data):
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in ("data", "result", "response", "records", "family", "details",
                  "vehicle", "vehicle_info", "rc", "challan", "challans", "response_data",
                  "info", "result_data"):
            v = data.get(k)
            if isinstance(v, list):
                return v
            if isinstance(v, dict):
                inner = _records_from(v)
                if inner is not None:
                    return inner
                return [v]
        record_fields = {"reg_no", "vehicle_no", "owner", "maker", "model", "challan_no",
                         "challan_date", "amount", "status", "name", "mobile", "aadhaar",
                         "pan", "full_name", "father_name", "dob", "address"}
        if record_fields.intersection(set(data.keys())):
            return [data]
    return None


# ---------- NUMBER INFO (ALLPRINTHUB) ----------
def fetch_number_info(mobile: str) -> str:
    url = f"{API_BASE}?=num_info_767&key={API_KEY}&%40Ronak_api={mobile}"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()

    data, raw = _safe_json(resp)
    if data is None:
        text = strip_usernames(raw or "")
        return text or "Koi details available nahi hain."

    data = strip_metadata(data)

    if isinstance(data, dict):
        status = str(data.get("status", "")).lower()
        if status and status not in ("success", "ok", "1", "true"):
            msg = data.get("message") or data.get("msg") or ""
            return f"❌ Koi record nahi mila.\n{msg}".strip()

    records = _records_from(data)
    if records is None:
        lines = [f"📱 *Number Info* — `{mobile}`", "━━━━━━━━━━━━━━"]
        if isinstance(data, dict):
            for k, v in data.items():
                if k.lower() in ("status", "message", "success", "code"):
                    continue
                if v is None or v == "":
                    continue
                if isinstance(v, str) and _is_provider_string(v):
                    continue
                lines.append(f"*{k.replace('_', ' ').title()}*: {v}")
        else:
            lines.append(json.dumps(data, indent=2, ensure_ascii=False))
        return "\n".join(lines)

    if not records:
        msg = ""
        if isinstance(data, dict):
            msg = data.get("message") or data.get("msg") or ""
        return f"❌ Koi record nahi mila.\n{msg}".strip()

    lines = [f"📊 *{len(records)} record(s) mile*", "━━━━━━━━━━━━━━"]
    for i, rec in enumerate(records, 1):
        lines.append(f"\n*#{i}*")
        if isinstance(rec, dict):
            ordered = [
                ("mobile",   "📱 Mobile"),
                ("number",   "📱 Number"),
                ("name",     "👤 Name"),
                ("full_name","👤 Name"),
                ("fname",    "👨 Father"),
                ("father_name","👨 Father"),
                ("alt",      "📞 Alt"),
                ("circle",   "🔵 Circle"),
                ("operator", "📶 Operator"),
                ("address",  "🏠 Address"),
                ("email",    "📧 Email"),
                ("id",       "🆔 ID"),
            ]
            shown = set()
            for key, label in ordered:
                v = rec.get(key)
                if v not in (None, "", []):
                    if isinstance(v, str) and _is_provider_string(v):
                        continue
                    val = f"`{v}`" if key in ("mobile", "number", "alt", "id") else f"{v}"
                    lines.append(f"{label}: {val}")
                    shown.add(key)
            for k, v in rec.items():
                if k in shown or k.lower() in ("status", "message", "oid"):
                    continue
                if v in (None, "", [], {}):
                    continue
                if isinstance(v, str) and _is_provider_string(v):
                    continue
                lines.append(f"*{k.replace('_', ' ').title()}*: {v}")
        else:
            lines.append(str(rec))

    return "\n".join(lines)


# ========== PDF GENERATION ==========
def generate_pdf(title: str, identifier: str, records: list, search_type: str) -> bytes:
    if not PDF_AVAILABLE:
        raise RuntimeError("PDF library not installed")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=title,
    )

    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle(
        "CustomTitle", parent=styles["Title"],
        fontName="Helvetica-Bold", fontSize=20, leading=24,
        textColor=HexColor("#1a1a2e"), alignment=TA_CENTER, spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "SubTitle", parent=styles["Normal"],
        fontName="Helvetica", fontSize=11, leading=14,
        textColor=HexColor("#555555"), alignment=TA_CENTER, spaceAfter=2,
    )
    section_style = ParagraphStyle(
        "Section", parent=styles["Heading2"],
        fontName="Helvetica-Bold", fontSize=14, leading=18,
        textColor=HexColor("#16213e"), spaceBefore=12, spaceAfter=6,
    )
    label_style = ParagraphStyle(
        "Label", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=10, leading=14,
        textColor=HexColor("#333333"),
    )
    value_style = ParagraphStyle(
        "Value", parent=styles["Normal"],
        fontName="Helvetica", fontSize=10, leading=14,
        textColor=HexColor("#111111"),
    )
    footer_style = ParagraphStyle(
        "Footer", parent=styles["Normal"],
        fontName="Helvetica-Oblique", fontSize=8, leading=12,
        textColor=HexColor("#888888"), alignment=TA_CENTER,
    )

    story.append(Paragraph(title, title_style))
    story.append(Paragraph(f"ID: {identifier}", subtitle_style))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
        subtitle_style
    ))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1.5, color=HexColor("#0f3460")))
    story.append(Spacer(1, 8))

    if not records:
        story.append(Paragraph("No records found.", label_style))
    else:
        for idx, rec in enumerate(records, 1):
            if isinstance(rec, dict):
                story.append(Paragraph(f"Record #{idx}", section_style))

                table_data = []
                for k, v in rec.items():
                    if v in (None, "", [], {}):
                        continue
                    if k.lower() in ("status", "message", "code", "success"):
                        continue
                    if isinstance(v, str) and _is_provider_string(v):
                        continue
                    key_label = k.replace("_", " ").title()
                    if isinstance(v, (dict, list)):
                        v = json.dumps(v, ensure_ascii=False)
                    table_data.append([
                        Paragraph(str(key_label), label_style),
                        Paragraph(str(v), value_style),
                    ])

                if table_data:
                    table = Table(table_data, colWidths=[55 * mm, 110 * mm])
                    table.setStyle(TableStyle([
                        ("BACKGROUND", (0, 0), (0, -1), HexColor("#eef2f7")),
                        ("TEXTCOLOR", (0, 0), (-1, -1), HexColor("#1a1a2e")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#c9d6e3")),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]))
                    story.append(table)
                else:
                    story.append(Paragraph("No details available.", value_style))

                story.append(Spacer(1, 10))
            else:
                story.append(Paragraph(f"Record #{idx}: {rec}", value_style))
                story.append(Spacer(1, 6))

    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=0.8, color=HexColor("#cccccc")))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Powered by Ritesh Goswami", footer_style))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def build_pdf_from_result(result_text: str, title: str, identifier: str, search_type: str) -> bytes:
    records = []
    current = {}

    for line in result_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("━━") or stripped.startswith("┈"):
            continue
        if stripped.startswith("📱") or stripped.startswith("📊"):
            continue
        if stripped.startswith("*#"):
            if current:
                records.append(current)
                current = {}
            continue
        if _is_provider_string(stripped):
            continue
        m= re.match(r"^\*([^*]+)\*:\s*(.*)$", stripped)
        if m:
            key = m.group(1).strip()
            value = m.group(2).strip().replace("`", "")
            if value and not value.startswith("{"):
                current[key] = value
            continue
        m2 = re.match(r"^([^:]{1,40}):\s*(.+)$", stripped)
        if m2:
            key = m2.group(1).strip()
            value = m2.group(2).strip().replace("`", "")
            if value and not value.startswith("{"):
                current[key] = value

    if current:
        records.append(current)

    return generate_pdf(title, identifier, records, search_type)


def make_remaining_text(uid: int, user: dict) -> str:
    if is_admin(uid):
        return "UNLIMITED👑 (Admin)"
    if is_premium_active(uid):
        until = user.get("premium_until", "")
        try:
            until_dt = datetime.fromisoformat(until).strftime("%d %b %Y")
        except Exception:
            until_dt = until
        return f"UNLIMITED 💎 (Premium till {until_dt})"
    return f"*{user.get('credits', 0)}*"


def truncate(text: str, limit: int = 3800) -> str:
    if len(text) > limit:
        return text[:limit] + "\n\n...(truncated)"
    return text


# ========== UNIFIED SEARCH HANDLER ==========
async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return

    text_input = message.text.strip()
    if not text_input:
        return

    uid = update.effective_user.id
    user = get_user(uid)

    # ---- Menu buttons ----
    if text_input == "📱 Number Info":
        await message.reply_text(
            "📱 Mobile number bhejein (10 digit, jaise: 9162516577)" + FOOTER,
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

    # ---- Plan selection ----
    if context.user_data.get("awaiting_plan") and text_input.isdigit():
        plan_no = int(text_input)
        if 1 <= plan_no <= len(CREDIT_PLANS):
            plan = get_plan_by_no(plan_no)
            if plan:
                _, price, credits = plan
                update_user(uid, selected_plan=plan_no)
                context.user_data["awaiting_plan"] = False

                if credits == -1:
                    plan_desc = "💎*PREMIUM — 6 Months Unlimited*"
                else:
                    plan_desc = f"💳 *{credits} Credits*"

                await message.reply_text(
                    f"✅ *Plan #{plan_no} Selected*\n"
                    f"━━━━━━━━━━━━━━\n"
                    f"💵 Price : ₹{price}\n"
                    f"📦 Plan  : {plan_desc}\n"
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

    # ---- Detect search type ----
    mobile_no = normalize_mobile(text_input)

    search_type = None
    identifier = None

    if is_valid_mobile(mobile_no):
        search_type = "mobile"
        identifier = mobile_no
    else:
        return

    # ---- Credit check ----
    premium_or_admin = is_admin(uid) or is_premium_active(uid)
    if not premium_or_admin and user.get("credits", 0) <= 0:
        await message.reply_text(
            "❌ *Aapke paas credits nahi hain!*\n\n"
            "💳 'Buy Credits' dabakar credits kharidein.\n"
            "💎 Ya Premium Plan (₹500 / 6 Months Unlimited) lein!\n"
            f"💰 Aapka balance: *{user.get('credits', 0)}*" + FOOTER,
            parse_mode="Markdown",
            reply_markup=get_keyboard(uid)
        )
        return

    # ---- Fetch ----
    type_labels = {
        "mobile": ("📱", "Mobile"),
    }
    emoji, label = type_labels[search_type]

    fetching_msg = await message.reply_text(
        f"🔍 `{identifier}` Details Nikal raha hu...",
        parse_mode="Markdown"
    )

    try:
        result_text = fetch_number_info(identifier)

        deduct_credit(uid)
        user = get_user(uid)
        remaining_display = make_remaining_text(uid, user)

        result_text = strip_usernames(result_text)
        result_text = truncate(result_text)

        try:
            await fetching_msg.delete()
        except Exception:
            pass

        body = result_text

        await message.reply_text(
            f"{emoji} *{label}: {identifier}*\n\n{body}\n\n"
            f"💳 Remaining Credits: {remaining_display}" + FOOTER,
            parse_mode="Markdown",
            reply_markup=get_keyboard(uid)
        )

        # ---- PDF (safe) ----
        if PDF_AVAILABLE:
            try:
                pdf_bytes = build_pdf_from_result(
                    result_text,
                    title=f"{label} Information",
                    identifier=identifier,
                    search_type=search_type,
                )
                pdf_file = io.BytesIO(pdf_bytes)
                pdf_file.name = f"{label}_{identifier}.pdf"
                await message.reply_document(
                    document=pdf_file,
                    filename=f"{label}_{identifier}.pdf",
                    caption=f"📄 {label} report — `{identifier}`\n⚡ Powered by Ritesh Goswami",
                    parse_mode="Markdown",
                )
            except Exception as pdf_err:
                logging.warning(f"PDF generation failed (non-critical): {pdf_err}")

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
    except Exception as e:
        logging.exception("Search failed")
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
    app.add_handler(CommandHandler("grantpremium", cmd_grant_premium))
    app.add_handler(CommandHandler("revokepremium", cmd_revoke_premium))
    app.add_handler(CommandHandler("reject", cmd_reject))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("pending", cmd_pending))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))

    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))

    print("Bot chal raha hai...")
    app.run_polling()


if __name__ == "__main__":
    main()
     
