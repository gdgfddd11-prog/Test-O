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
BOT_TOKEN = ("8811516200:AAEJIltjhpG2msdqAnS1OH48fR0j1JwP0jA")
API_BASE = "https://api.allprinthub.in/api"
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
VEHICLE_REGEX = re.compile(
    r"^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}$"
)
BH_REGEX = re.compile(
    r"^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$"
)

# ========== MOBILE NUMBER VALIDATION ==========
MOBILE_REGEX = re.compile(r"^[6-9][0-9]{9}$")

# ========== AADHAAR VALIDATION ==========
AADHAAR_REGEX = re.compile(r"^[2-9][0-9]{11}$")


def is_valid_vehicle_number(text: str) -> bool:
    cleaned = re.sub(r"[\s\-]", "", text).upper()
    if not (8 <= len(cleaned) <= 11):
        return False
    return bool(VEHICLE_REGEX.match(cleaned) or BH_REGEX.match(cleaned))


def normalize_vehicle_number(text: str) -> str:
    return re.sub(r"[\s\-]", "", text).upper()


def is_valid_mobile(text: str) -> bool:
    """10-digit Indian mobile number check."""
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


def is_valid_aadhaar(text: str) -> bool:
    """12-digit Aadhaar number check (no spaces)."""
    cleaned = re.sub(r"[\s\-]", "", text)
    return bool(AADHAAR_REGEX.match(cleaned))


def normalize_aadhaar(text: str) -> str:
    return re.sub(r"[\s\-]", "", text)
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
        KeyboardButton("📱 Number Info"),
    ]
    row2 = [
        KeyboardButton("🆔 Aadhaar Info"),
        KeyboardButton("💳 Buy Credits"),
    ]
    row3 = [KeyboardButton("💰 My Balance")]

    if user_id is not None and is_admin(user_id):
        row3.append(KeyboardButton("⚙️ Admin Panel"))

    keyboard = [row1, row2, row3]
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Vehicle / Mobile / Aadhaar number likhein..."
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
        "📱 Mobile number bhejein (jaise: 9162516577)\n"
        "🆔 Aadhaar number bhejein (jaise: 677531893455)\n\n"
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
        "`/broadcast <message>`\n"
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
                "Ab aap vehicle/number/aadhaar search kar sakte hain." + FOOTER
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
        await update.message.reply_text("❌ Data base me koi users nahi hain.")
        return

    status_msg = await update.message.reply_text("📢 Broadcast shuru ho raha hai...")

    success = 0
    failed = 0
    total = len(db)

    # Check if broadcast is via reply or text argument
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
def fetch_vehicle_info(vehicle_no: str) -> str:
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
    return result_text


def fetch_number_info(mobile: str) -> str:
    url = f"{API_BASE}?=num_info&key=30day&num={mobile}"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    try:
        data = resp.json()
    except ValueError:
        return resp.text or "Koi details available nahi hain."

    if not isinstance(data, dict):
        return json.dumps(data, indent=2, ensure_ascii=False)

    if data.get("status") != "success" or not data.get("data"):
        return f"❌ Koi record nahi mila.\n{data.get('message', '')}"

    records = data["data"]
    lines = [f"📊 *{len(records)} record(s) mile*", "━━━━━━━━━━━━━━"]

    for i, rec in enumerate(records, 1):
        lines.append(f"\n*#{i}*")
        if rec.get("mobile"):
            lines.append(f"📱 Mobile: `{rec['mobile']}`")
        if rec.get("name"):
            lines.append(f"👤 Name: {rec['name']}")
        if rec.get("fname"):
            lines.append(f"👨 Father: {rec['fname']}")
        if rec.get("alt"):
            lines.append(f"📞 Alt: `{rec['alt']}`")
        if rec.get("circle"):
            lines.append(f"🔵 Circle: {rec['circle']}")
        if rec.get("address"):
            lines.append(f"🏠 Address: {rec['address']}")
        if rec.get("email"):
            lines.append(f"📧 Email: {rec['email']}")
        if rec.get("id"):
            lines.append(f"🆔 ID: `{rec['id']}`")

    return "\n".join(lines)


def fetch_aadhaar_info(aadhaar: str) -> str:
    url = f"{API_BASE}?=addhaar2num&key=30day&q={aadhaar}"
    resp= requests.get(url, timeout=15)
    resp.raise_for_status()
    try:
        data = resp.json()
    except ValueError:
        return resp.text or "Koi details available nahi hain."

    if not isinstance(data, dict):
        return json.dumps(data, indent=2, ensure_ascii=False)

    if data.get("status") != "success":
        return f"❌ Koi record nahi mila.\n{data.get('message', '')}"

    lines = ["🆔 *Aadhaar Info*", "━━━━━━━━━━━━━━"]

    # Try common data structures
    records = data.get("data") or data.get("result") or []
    if isinstance(records, dict):
        records = [records]

    if not records:
        # Fallback: show whatever fields exist
        for k, v in data.items():
            if k in ("status", "message"):
                continue
            if v is not None and v != "":
                lines.append(f"*{k}*: {v}")
        return "\n".join(lines)

    for i, rec in enumerate(records, 1):
        lines.append(f"\n*#{i}*")
        if isinstance(rec, dict):
            for k, v in rec.items():
                if v is None or v == "":
                    continue
                lines.append(f"*{k.title()}*: {v}")
        else:
            lines.append(str(rec))

    return "\n".join(lines)


def make_remaining_text(uid: int, user: dict) -> str:
    if is_admin(uid):
        return "UNLIMITED 👑 (Admin)"
    return f"*{user.get('credits', 0)}*"


def truncate(text: str, limit: int = 3500) -> str:
    if len(text) > limit:
        return text[:limit] + "\n\n...(truncated)"
    return text
# ==============================================


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
    if text_input == "🔍 Vehicle Info":
        await message.reply_text(
            "🚗 Vehicle number bhejein (jaise: HR55AL0051)" + FOOTER,
            reply_markup=get_keyboard(uid)
        )
        return

    if text_input == "📱 Number Info":
        await message.reply_text(
            "📱 Mobile number bhejein (10 digit, jaise: 9162516577)" + FOOTER,
            reply_markup=get_keyboard(uid)
        )
        return

    if text_input == "🆔 Aadhaar Info":
        await message.reply_text(
            "🆔 Aadhaar number bhejein (12 digit, jaise: 677531893455)" + FOOTER,
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

    # ---- Plan selection (only while in Buy Credits flow) ----
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

    # ---- Detect search type ----
    vehicle_no = normalize_vehicle_number(text_input)
    mobile_no = normalize_mobile(text_input)
    aadhaar_no = normalize_aadhaar(text_input)

    search_type = None
    identifier = None

    if is_valid_vehicle_number(vehicle_no):
        search_type = "vehicle"
        identifier = vehicle_no
    elif is_valid_mobile(mobile_no):
        search_type = "mobile"
        identifier = mobile_no
    elif is_valid_aadhaar(aadhaar_no):
        search_type = "aadhaar"
        identifier = aadhaar_no
    else:
        # Silently ignore random text
        return

    # ---- Credit check ----
    if not is_admin(uid) and user.get("credits", 0) <= 0:
        await message.reply_text(
            "❌ *Aapke paas credits nahi hain!*\n\n"
            "💳 'Buy Credits' dabakar credits kharidein.\n"
            f"💰 Aapka balance: *{user.get('credits', 0)}*" + FOOTER,
            parse_mode="Markdown",
            reply_markup=get_keyboard(uid)
        )
        return

    # ---- Fetch ----
    type_labels = {
        "vehicle": ("🚗", "Vehicle"),
        "mobile": ("📱", "Mobile"),
        "aadhaar": ("🆔", "Aadhaar"),
    }
    emoji, label = type_labels[search_type]

    fetching_msg = await message.reply_text(
        f"🔍 `{identifier}` Details Nikal raha hu...",
        parse_mode="Markdown"
    )

    try:
        if search_type == "vehicle":
            result_text = fetch_vehicle_info(identifier)
        elif search_type == "mobile":
            result_text = fetch_number_info(identifier)
        else:
            result_text = fetch_aadhaar_info(identifier)

        deduct_credit(uid)
        user = get_user(uid)
        remaining_display = make_remaining_text(uid, user)
        result_text = truncate(result_text)

        try:
            await fetching_msg.delete()
        except Exception:
            pass

        # For mobile/aadhaar we already formatted as Markdown text
        if search_type == "vehicle":
            body = f"```\n{result_text}\n```"
        else:
            body = result_text

        await message.reply_text(
            f"{emoji} *{label}: {identifier}*\n\n{body}\n\n"
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
