import telebot
import requests
import json
import os
import time
import random
import string
from telebot import types

# ==========================================
# CONFIGURATION
# ==========================================
BOT_TOKEN = "8689112558:AAENvZ_G7kA5oasvEbRs6raTVQIn5rv7oBM"
ADMIN_ID = 8147130832

CONFIG_FILE = "bot_config.json"
USERS_FILE = "users.json"
REFERRAL_FILE = "referrals.json"

# ==========================================
# DYNAMIC CONFIGURATION MANAGER
# ==========================================
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {
        "force_join_channel": "",
        "force_join_link": "",
        "credit_plans": {
            "num_info": 2,
            "vehicle_full": 2,
            "vehicle_to_number": 2,
            "pan2dob_name": 3,
            "ifse": 2
        },
        "upi_id": "riteshgiri7930@okhdfcbank",
        "upi_name": "Ritesh Giri",
        "credit_packages": {
            "25": 30,
            "45": 75,
            "100": 200,
            "280": 500,
            "600": 1000
        },
        "referral_credits": 2
    }

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

config = load_config()

# ==========================================
# USER DATABASE (Persistent)
# ==========================================
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=4)

def load_referrals():
    if os.path.exists(REFERRAL_FILE):
        with open(REFERRAL_FILE, "r") as f:
            return json.load(f)
    return {}

def save_referrals(refs):
    with open(REFERRAL_FILE, "w") as f:
        json.dump(refs, f, indent=4)

users = load_users()          # {user_id: {"credits": int, "referred_by": str|None, "referral_code": str}}
referrals = load_referrals()  # {referral_code: user_id}
user_states = {}              # {user_id: state_name}

def generate_ref_code(user_id):
    """Generates a unique referral code."""
    while True:
        code = "REF" + str(user_id)[-4:] + "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        if code not in referrals:
            return code

def register_user(user_id, referred_by=None):
    """Register a new user if not already present."""
    uid = str(user_id)
    if uid in users:
        return False
    
    ref_code = generate_ref_code(user_id)
    users[uid] = {
        "credits": 5,
        "referred_by": referred_by,
        "referral_code": ref_code
    }
    referrals[ref_code] = uid
    
    # Credit referrer with 2 credits
    if referred_by and referred_by in referrals:
        referrer_id = referrals[referred_by]
        if referrer_id in users:
            users[referrer_id]["credits"] += config.get("referral_credits", 2)
            try:
                bot.send_message(int(referrer_id), 
                    f"🎉 New referral! You earned **{config.get('referral_credits', 2)}** credits.\n"
                    f"New balance: **{users[referrer_id]['credits']}** credits", 
                    parse_mode="Markdown")
            except:
                pass
    
    save_users(users)
    save_referrals(referrals)
    return True

def get_user_credits(user_id):
    if user_id == ADMIN_ID:
        return float('inf')  # Admin unlimited
    uid = str(user_id)
    if uid not in users:
        register_user(user_id)
    return users[uid]["credits"]

def deduct_credit(user_id, amount):
    if user_id == ADMIN_ID:
        return True  # Admin unlimited
    uid = str(user_id)
    if uid not in users:
        register_user(user_id)
    if users[uid]["credits"] >= amount:
        users[uid]["credits"] -= amount
        save_users(users)
        return True
    return False

def add_credit(user_id, amount):
    uid = str(user_id)
    if uid not in users:
        register_user(user_id)
    users[uid]["credits"] += amount
    save_users(users)

# ==========================================
# BOT INITIALIZATION
# ==========================================
bot = telebot.TeleBot(BOT_TOKEN)

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def check_force_join(user_id):
    channel = config.get("force_join_channel")
    if not channel:
        return True
    try:
        member = bot.get_chat_member(channel, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
        return False
    except Exception as e:
        print(f"Error checking membership: {e}")
        return False

def send_force_join_message(chat_id):
    markup = types.InlineKeyboardMarkup()
    link = config.get("force_join_link", "https://t.me/telegram")
    btn_join = types.InlineKeyboardButton("Join Channel ✅", url=link)
    btn_check = types.InlineKeyboardButton("Check Again 🔄", callback_data="check_join")
    markup.add(btn_join, btn_check)
    
    bot.send_message(chat_id, 
        "🚫 **Access Denied**\n\n"
        "You must join our channel to use this bot.\n"
        f"Channel: {config.get('force_join_channel')}", 
        reply_markup=markup, parse_mode="Markdown")

def make_api_request(endpoint, params):
    base_url = "https://api.sarkariallupdates.com/api"
    params['key'] = '30day'
    try:
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        url = f"{base_url}?={endpoint}&{query_string}"
        response = requests.get(url, timeout=20)
        return response.text
    except Exception as e:
        return f"Error: {str(e)}"

# ==========================================
# KEYBOARD BUILDERS
# ==========================================
def get_main_menu():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton("📞 Num Info")
    btn2 = types.KeyboardButton("🚗 Vehicle Info")
    btn3 = types.KeyboardButton("🔗 Vehicle to Num")
    btn4 = types.KeyboardButton("🆔 PAN to Name/DOB")
    btn5 = types.KeyboardButton("🏦 IFSC Info")
    btn6 = types.KeyboardButton("💰 My Credits")
    btn7 = types.KeyboardButton("💳 Buy Credits")
    btn8 = types.KeyboardButton("🎁 Refer & Earn")
    btn9 = types.KeyboardButton("👥 My Referrals")
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn8, btn9)
    return markup

# ==========================================
# USER HANDLERS
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    
    # Check for referral parameter: /start REFxxxx
    referred_by = None
    parts = message.text.split()
    if len(parts) > 1:
        ref_arg = parts[1].strip()
        if ref_arg in referrals and referrals[ref_arg] != str(user_id):
            referred_by = ref_arg
    
    # Register new user
    is_new = register_user(user_id, referred_by)
    
    if not check_force_join(user_id):
        send_force_join_message(message.chat.id)
        return

    credits_display = "♾️ Unlimited (Admin)" if user_id == ADMIN_ID else get_user_credits(user_id)
    
    welcome_text = (
        f"👋 **Welcome to All-in-One Info Bot!**\n\n"
        f"💰 Your Credits: **{credits_display}**\n\n"
        f"Select a service from the menu below 👇"
    )
    if is_new and referred_by:
        welcome_text += f"\n\n🎁 You joined via referral! You'll earn bonus credits later."
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=get_main_menu(), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "check_join")
def callback_check_join(call):
    if check_force_join(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ Verified! You can use the bot now.")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except:
            pass
        send_welcome(call.message)
    else:
        bot.answer_callback_query(call.id, "❌ You still haven't joined.", show_alert=True)

@bot.message_handler(func=lambda message: message.text == "💰 My Credits")
def show_credits(message):
    if not check_force_join(message.from_user.id):
        send_force_join_message(message.chat.id)
        return
    user_id = message.from_user.id
    if user_id == ADMIN_ID:
        bot.reply_to(message, "💳 You have **♾️ Unlimited** credits (Admin).", parse_mode="Markdown")
    else:
        credits = get_user_credits(user_id)
        bot.reply_to(message, f"💳 You have **{credits}** credits left.", parse_mode="Markdown")

# ==========================================
# API SERVICE HANDLERS
# ==========================================
@bot.message_handler(func=lambda message: message.text == "📞 Num Info")
def ask_num_info(message):
    if not check_force_join(message.from_user.id):
        send_force_join_message(message.chat.id)
        return
    user_states[message.from_user.id] = "num_info"
    bot.reply_to(message, "📞 Enter the 10-digit mobile number (e.g., 9162516577):")

@bot.message_handler(func=lambda message: message.text == "🚗 Vehicle Info")
def ask_vehicle_full(message):
    if not check_force_join(message.from_user.id):
        send_force_join_message(message.chat.id)
        return
    user_states[message.from_user.id] = "vehicle_full"
    bot.reply_to(message, "🚗 Enter Vehicle Number (e.g., KL41V3504):")

@bot.message_handler(func=lambda message: message.text == "🔗 Vehicle to Num")
def ask_vehicle_to_num(message):
    if not check_force_join(message.from_user.id):
        send_force_join_message(message.chat.id)
        return
    user_states[message.from_user.id] = "vehicle_to_number"
    bot.reply_to(message, "🔗 Enter Vehicle Number (e.g., KL41V3504):")

@bot.message_handler(func=lambda message: message.text == "🆔 PAN to Name/DOB")
def ask_pan(message):
    if not check_force_join(message.from_user.id):
        send_force_join_message(message.chat.id)
        return
    user_states[message.from_user.id] = "pan2dob_name"
    bot.reply_to(message, "🆔 Enter PAN Number (e.g., cnkpk7230d):")

@bot.message_handler(func=lambda message: message.text == "🏦 IFSC Info")
def ask_ifse(message):
    if not check_force_join(message.from_user.id):
        send_force_join_message(message.chat.id)
        return
    user_states[message.from_user.id] = "ifse"
    bot.reply_to(message, "🏦 Enter IFSC Code:")

# ==========================================
# PROCESSING USER INPUT (CONSUMING CREDITS)
# ==========================================
@bot.message_handler(func=lambda message: message.from_user.id in user_states)
def process_input(message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    text = message.text.strip()
    
    del user_states[user_id]
    
    endpoint_map = {
        "num_info": ("num_info", "num", "num_info"),
        "vehicle_full": ("vehicle_full", "xr", "vehicle_full"),
        "vehicle_to_number": ("vehicle_to_number", "xr", "vehicle_to_number"),
        "pan2dob_name": ("pan2dob_name", "pan2dob_name", "pan2dob_name"),
        "ifse": ("ifse", "ifse", "ifse")
    }
    
    if state not in endpoint_map:
        bot.reply_to(message, "Unknown state.")
        return

    api_endpoint, param_key, cost_key = endpoint_map[state]
    cost = config["credit_plans"].get(cost_key, 1)
    
    # Check credits
    if not deduct_credit(user_id, cost):
        bot.reply_to(message, f"❌ **Insufficient Credits!**\n\nYou need **{cost}** credits but have **{get_user_credits(user_id)}**.\n\nUse 💳 Buy Credits to top up.", parse_mode="Markdown")
        return

    # === SEARCHING INDICATOR ===
    searching_msg = bot.reply_to(message, "🔍 **Searching...**\n\n details...", parse_mode="Markdown")
    bot.send_chat_action(message.chat.id, 'typing')
    
    # Simulate processing time so user sees the searching message
    time.sleep(1.5)
    bot.send_chat_action(message.chat.id, 'typing')
    
    params = {param_key: text}
    response_text = make_api_request(api_endpoint, params)
    response_text = response_text.replace('"powered by": "@Ronakapi"', '')
    # Update searching message to show results
    if len(response_text) > 4000:
        response_text = response_text[:4000] + "\n...(truncated)"
    
    result_text = f"✅ **Result Found!**\n\n{response_text}\n\n"
    if user_id == ADMIN_ID:
        result_text += "💰 Admin: ♾️ Unlimited"
    else:
        result_text += f"💰 Remaining Credits: **{get_user_credits(user_id)}**"
        result_text += f"\n💸 Cost: {cost} credits"
    
    try:
        bot.edit_message_text(result_text, chat_id=searching_msg.chat.id, message_id=searching_msg.message_id, parse_mode="Markdown")
    except:
        bot.reply_to(message, result_text, parse_mode="Markdown")

# ==========================================
# UPI PAYMENT SYSTEM
# ==========================================
@bot.message_handler(func=lambda message: message.text == "💳 Buy Credits")
def buy_credits_menu(message):
    if not check_force_join(message.from_user.id):
        send_force_join_message(message.chat.id)
        return
    
    packages = config.get("credit_packages", {})
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for amount, credits in packages.items():
        buttons.append(types.InlineKeyboardButton(
            f"₹{amount} → {credits} Credits", 
            callback_data=f"buy_{amount}_{credits}"
        ))
    markup.add(*buttons)
    
    upi = config.get("upi_id", "not set")
    upi_name = config.get("upi_name", "Bot Owner")
    
    text = (
        f"💳 **Buy Credits**\n\n"
        f"💸 **Payment via UPI:**\n"
        f"`{upi}`\n"
        f"Name: {upi_name}\n\n"
        f"👇 **Select a package:**"
    )
    bot.reply_to(message, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def handle_buy(call):
    parts = call.data.split("_")
    amount = parts[1]
    credits = parts[2]
    user_id = call.from_user.id
    
    upi = config.get("upi_id", "not set")
    upi_name = config.get("upi_name", "Bot Owner")
    
    # Generate order ID
    order_id = f"ORDER{user_id}{int(time.time())}"
    
    text = (
        f"💳 **Payment Details**\n\n"
        f"📦 Package: **{credits} Credits**\n"
        f"💵 Amount: **₹{amount}**\n"
        f"🆔 Order ID: `{order_id}`\n\n"
        f"**UPI Payment:**\n"
        f"UPI ID: `{upi}`\n"
        f"Name: {upi_name}\n\n"
        f"⚠️ **Instructions:**\n"
        f"1. Pay ₹{amount} to the UPI above\n"
        f"2. Send the **screenshot** here\n"
        f"3. Send the **UTR/Transaction ID**\n"
        f"4. Admin will verify & add credits\n\n"
        f"Click the button below after payment:"
    )
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ I've Paid - Send Proof", callback_data=f"paid_{amount}_{credits}_{order_id}"))
    
    bot.edit_message_text(text, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("paid_"))
def handle_paid(call):
    parts = call.data.split("_")
    amount = parts[1]
    credits = parts[2]
    order_id = parts[3]
    user_id = call.from_user.id
    
    bot.answer_callback_query(call.id, "Please send payment proof.")
    
    # Notify admin
    admin_msg = (
        f"💰 **New Payment Request**\n\n"
        f"👤 User: `{user_id}`\n"
        f"📦 Credits: {credits}\n"
        f"💵 Amount: ₹{amount}\n"
        f"🆔 Order ID: `{order_id}`\n\n"
        f"Reply with: `/approve {user_id} {credits}` to add credits\n"
        f"Or: `/reject {user_id}`"
    )
    try:
        bot.send_message(ADMIN_ID, admin_msg, parse_mode="Markdown")
    except:
        pass
    
    bot.send_message(call.message.chat.id, 
        f"✅ **Payment request sent to admin!**\n\n"
        f"🆔 Order ID: `{order_id}`\n"
        f"📦 Credits: {credits}\n"
        f"💵 Amount: ₹{amount}\n\n"
        f"⏳ Please wait for admin approval. You'll be notified once credits are added.",
        parse_mode="Markdown")

# ==========================================
# REFERRAL SYSTEM
# ==========================================
@bot.message_handler(func=lambda message: message.text == "🎁 Refer & Earn")
def refer_earn(message):
    if not check_force_join(message.from_user.id):
        send_force_join_message(message.chat.id)
        return
    
    user_id = message.from_user.id
    uid = str(user_id)
    
    if uid not in users:
        register_user(user_id)
    
    ref_code = users[uid]["referral_code"]
    bot_info = bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={ref_code}"
    reward = config.get("referral_credits", 2)
    
    text = (
        f"🎁 **Refer & Earn**\n\n"
        f"Share your referral link with friends.\n"
        f"For every friend who joins, you get **{reward} credits**! 🎉\n\n"
        f"🔗 **Your Referral Link:**\n"
        f"`{ref_link}`\n\n"
        f"🎫 **Your Referral Code:** `{ref_code}`\n\n"
        f"💡 Just send the link to your friends.\n"
        f"💸 Each successful referral = {reward} Credits!"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "👥 My Referrals")
def my_referrals(message):
    if not check_force_join(message.from_user.id):
        send_force_join_message(message.chat.id)
        return
    
    user_id = message.from_user.id
    uid = str(user_id)
    
    if uid not in users:
        register_user(user_id)
    
    ref_code = users[uid]["referral_code"]
    count = sum(1 for u in users.values() if u.get("referred_by") == ref_code)
    reward = config.get("referral_credits", 2)
    
    text = (
        f"👥 **My Referrals**\n\n"
        f"🎫 Your Code: `{ref_code}`\n"
        f"👤 Total Referrals: **{count}**\n"
        f"💰 Earned from referrals: **{count * reward}** credits\n\n"
        f"Use 🎁 Refer & Earn to get your link!"
    )
    bot.reply_to(message, text, parse_mode="Markdown")

# ==========================================
# ADMIN PANEL
# ==========================================
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn1 = types.InlineKeyboardButton("⚙️ Set Force Join Channel", callback_data="admin_set_channel")
    btn2 = types.InlineKeyboardButton("🔗 Set Force Join Link", callback_data="admin_set_link")
    btn3 = types.InlineKeyboardButton("💳 Set Credit Costs", callback_data="admin_set_costs")
    btn4 = types.InlineKeyboardButton("👤 Add Credits to User", callback_data="admin_add_credits")
    btn5 = types.InlineKeyboardButton("🏦 Set UPI ID", callback_data="admin_set_upi")
    btn6 = types.InlineKeyboardButton("🎁 Set Referral Reward", callback_data="admin_set_ref")
    btn7 = types.InlineKeyboardButton("📊 View Current Config", callback_data="admin_view_config")
    btn8 = types.InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast")
    
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn8)
    
    bot.send_message(message.chat.id, "🛠 **Admin Panel**\nSelect an option:", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def admin_callback(call):
    if call.from_user.id != ADMIN_ID:
        return
    
    action = call.data.replace("admin_", "")
    
    if action == "view_config":
        txt = (
            f"**Current Config:**\n"
            f"Channel: {config.get('force_join_channel')}\n"
            f"Link: {config.get('force_join_link')}\n"
            f"UPI: {config.get('upi_id')}\n"
            f"UPI Name: {config.get('upi_name')}\n"
            f"Referral Reward: {config.get('referral_credits')}\n"
            f"Costs: {config['credit_plans']}\n"
            f"Packages: {config.get('credit_packages')}\n"
            f"Total Users: {len(users)}"
        )
        bot.send_message(call.message.chat.id, txt)
        
    elif action == "set_channel":
        msg = bot.send_message(call.message.chat.id, "Send the channel username (e.g., @MyChannel):")
        bot.register_next_step_handler(msg, save_channel)
        
    elif action == "set_link":
        msg = bot.send_message(call.message.chat.id, "Send the channel link (e.g., https://t.me/MyChannel):")
        bot.register_next_step_handler(msg, save_link)
        
    elif action == "set_costs":
        msg = bot.send_message(call.message.chat.id, 
            "Send costs in format: `num_info,vehicle_full,vehicle_to_number,pan2dob_name,ifse`\nExample: `1,2,2,5,3`")
        bot.register_next_step_handler(msg, save_costs)
        
    elif action == "add_credits":
        msg = bot.send_message(call.message.chat.id, "Send: `USER_ID AMOUNT`\nExample: `123456789 50`")
        bot.register_next_step_handler(msg, admin_add_credits_process)
    
    elif action == "set_upi":
        msg = bot.send_message(call.message.chat.id, "Send in format: `UPI_ID,NAME`\nExample: `myupi@paytm,John Doe`")
        bot.register_next_step_handler(msg, save_upi)
    
    elif action == "set_ref":
        msg = bot.send_message(call.message.chat.id, "Send the referral reward amount (e.g., 2):")
        bot.register_next_step_handler(msg, save_ref)
    
    elif action == "broadcast":
        msg = bot.send_message(call.message.chat.id, "Send the message you want to broadcast to all users:")
        bot.register_next_step_handler(msg, broadcast_message)

def save_channel(message):
    config["force_join_channel"] = message.text.strip()
    save_config(config)
    bot.reply_to(message, f"✅ Channel set to: {config['force_join_channel']}")

def save_link(message):
    config["force_join_link"] = message.text.strip()
    save_config(config)
    bot.reply_to(message, f"✅ Link set to: {config['force_join_link']}")

def save_costs(message):
    try:
        parts = message.text.split(',')
        keys = ["num_info", "vehicle_full", "vehicle_to_number", "pan2dob_name", "ifse"]
        for i, key in enumerate(keys):
            config["credit_plans"][key] = int(parts[i])
        save_config(config)
        bot.reply_to(message, f"✅ Costs updated: {config['credit_plans']}")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}. Use format: 1,2,2,5,3")

def admin_add_credits_process(message):
    try:
        uid, amount = message.text.split()
        add_credit(int(uid), int(amount))
        bot.reply_to(message, f"✅ Added {amount} credits to {uid}")
        try:
            bot.send_message(int(uid), f"🎉 **{amount} credits** added to your account by admin!\n💰 New balance: **{get_user_credits(int(uid))}**", parse_mode="Markdown")
        except:
            pass
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}. Use format: USER_ID AMOUNT")

def save_upi(message):
    try:
        upi, name = message.text.split(',')
        config["upi_id"] = upi.strip()
        config["upi_name"] = name.strip()
        save_config(config)
        bot.reply_to(message, f"✅ UPI set: `{config['upi_id']}` ({config['upi_name']})", parse_mode="Markdown")
    except:
        bot.reply_to(message, "❌ Use format: UPI_ID,NAME")

def save_ref(message):
    try:
        config["referral_credits"] = int(message.text.strip())
        save_config(config)
        bot.reply_to(message, f"✅ Referral reward set to: {config['referral_credits']} credits")
    except:
        bot.reply_to(message, "❌ Send a valid number.")

def broadcast_message(message):
    if message.text == "/cancel":
        bot.reply_to(message, "❌ Broadcast cancelled.")
        return
    
    text = message.text
    success = 0
    failed = 0
    for uid in list(users.keys()):
        try:
            bot.send_message(int(uid), f"📢 **Broadcast:**\n\n{text}", parse_mode="Markdown")
            success += 1
            time.sleep(0.05)
        except:
            failed += 1
    bot.reply_to(message, f"✅ Broadcast done!\n✅ Sent: {success}\n❌ Failed: {failed}")

# Admin approve/reject via commands
@bot.message_handler(commands=['approve'])
def approve_payment(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split()
        uid = int(parts[1])
        credits = int(parts[2])
        add_credit(uid, credits)
        bot.reply_to(message, f"✅ Approved! {credits} credits added to {uid}")
        bot.send_message(uid, f"🎉 **Payment Approved!**\n\n💰 {credits} credits added.\n💳 New Balance: **{get_user_credits(uid)}**", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}\nFormat: /approve USER_ID CREDITS")

@bot.message_handler(commands=['reject'])
def reject_payment(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split()
        uid = int(parts[1])
        bot.reply_to(message, f"❌ Payment rejected for {uid}")
        bot.send_message(uid, "❌ **Payment Rejected**\n\nPlease contact admin for support.", parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}\nFormat: /reject USER_ID")

# ==========================================
# START BOT
# ==========================================
if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling()
