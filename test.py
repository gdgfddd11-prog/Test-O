import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# ================== CONFIG ==================
BOT_TOKEN = "8888778986:AAFG2g11YI545NpjVQl_MbjlMB-_7Zy_-vE"   # BotFather se lein
API_KEY = "cybershrfreedemo_9cc8ad86ccdcd8cc53"
BASE_URL = "https://t.me/SAD_CONFIG"

# 👇 CHANNEL LINK ONLY
CHANNEL_LINK = "https://t.me/SAD_CONFIG"      # e.g. https://t.me/SAD_CONFIG

# 👇 DEVELOPER USERNAME ONLY
DEVELOPER_USERNAME = "@Sadaura4u"                # e.g. @SAD_OWNER


# ================== HELPER: API CALL ==================
def call_api(endpoint: str, params: dict) -> dict:
    """Generic API caller with error handling"""
    params["key"] = API_KEY
    url = f"{BASE_URL}/{endpoint}"
    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            try:
                return {"success": True, "data": response.json()}
            except ValueError:
                return {"success": False, "error": "Invalid JSON response", "raw": response.text}
        return {"success": False, "error": f"HTTP {response.status_code}", "raw": response.text}
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Request timed out. Server busy hai, baad mein try karein."}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e)}


# ================== API FUNCTIONS ==================
def get_family_info(aadhaar: str) -> dict:
    return call_api("family-info", {"aadhar": aadhaar})


def get_number_info(mobile: str) -> dict:
    return call_api("number-info", {"mobile": mobile})


def get_aadhaar_info(aadhaar: str) -> dict:
    return call_api("aadhaar", {"id": aadhaar})


def get_vehicle_info(vehicle_number: str) -> dict:
    return call_api("vehicle-info", {"number": vehicle_number})


# ================== FORMAT RESPONSE ==================
def format_response(title: str, result: dict) -> str:
    if result.get("success"):
        data = result["data"]
        import json
        return f"*{title}*\n\n```json\n{json.dumps(data, indent=2, ensure_ascii=False)}\n```"
    else:
        err = result.get("error", "Unknown error")
        raw = result.get("raw", "")
        return f"❌ *{title} failed*\n\nError: `{err}`\nRaw: `{raw[:300]}`"


# ================== BOT HANDLERS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("👨‍👩‍👧‍👦 Family Info", callback_data="family")],
        [InlineKeyboardButton("☎️ Mobile Info", callback_data="number")],
        [InlineKeyboardButton("🪪 Aadhaar Info", callback_data="aadhaar")],
        [InlineKeyboardButton("🚕 Vehicle Info", callback_data="vehicle")],
        # 👇 Channel + Developer buttons
        [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)],
        [InlineKeyboardButton("👨‍💻 Developer", url=f"https://t.me/{DEVELOPER_USERNAME.lstrip('@')}")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🙏 *Welcome to Info Bot*\n\n"
        f"📢 *Channel:* [Join Here]({CHANNEL_LINK})\n"
        f"👨‍💻 *Developer:* {DEVELOPER_USERNAME}\n\n"
        "Neeche se koi service chunein:\n\n"
        "⚠️ *Disclaimer:* Yeh sirf demo/educational purpose ke liye hai. "
        "Kisi ki personal info bina permission access karna illegal hai.",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data

    prompts = {
        "family": "👨‍👩‍👧‍👦 *Family Info*\n\n12-digit Aadhaar number bhejein:",
        "number": "☎️ *Mobile Info*\n\n10-digit mobile number bhejein:",
        "aadhaar": "🪪 *Aadhaar Info*\n\n12-digit Aadhaar number bhejein:",
        "vehicle": "🚕 *Vehicle Info*\n\nVehicle number bhejein (e.g. UP33BH4112):",
    }
    context.user_data["mode"] = choice
    await query.edit_message_text(prompts[choice], parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mode = context.user_data.get("mode")
    text = update.message.text.strip()

    if not mode:
        await update.message.reply_text("Pehle /start command dein aur service chunein.")
        return

    msg = await update.message.reply_text("⏳ Fetching data, please wait...")

    if mode == "family":
        result = get_family_info(text)
        reply = format_response("Family Info", result)

    elif mode == "number":
        result = get_number_info(text)
        reply = format_response("Mobile Info", result)

    elif mode == "aadhaar":
        result = get_aadhaar_info(text)
        reply = format_response("Aadhaar Info", result)

    elif mode == "vehicle":
        result = get_vehicle_info(text.upper())
        reply = format_response("Vehicle Info", result)

    else:
        reply = "❌ Invalid mode. /start karein."

    # 👇 Channel + Developer footer
    reply += (
        f"\n\n📢 *Channel:* [Join Here]({CHANNEL_LINK})"
        f"\n👨‍💻 *Developer:* {DEVELOPER_USERNAME}"
    )

    await msg.edit_text(reply, parse_mode="Markdown")

    context.user_data["mode"] = None


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = None
    await update.message.reply_text("✅ Cancelled. /start karein.")


# ================== MAIN ==================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot chal raha hai... Ctrl+C se band karein.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()