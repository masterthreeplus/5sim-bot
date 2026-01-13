import telebot
import requests
import time
import threading
import os
import certifi
import logging
from threading import Thread
from flask import Flask
from telebot import types
from pymongo import MongoClient
from datetime import datetime

# ---------------- LOGGING SETUP ----------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ---------------- SECURITY CHECK & CONFIG ----------------
def get_env_var(name):
    val = os.environ.get(name)
    if not val:
        # ဒီနေရာမှာ Error တက်ရင် Render > Environment မှာ variable နာမည်မှန်မမှန် ပြန်စစ်ပါ
        logger.critical(f"❌ Missing Environment Variable: {name}")
        raise ValueError(f"Missing {name}")
    return val

# [FIXED HERE] ဒီနေရာမှာ Token အစစ် မထည့်ရပါ၊ နာမည်ပဲ ထည့်ရပါမယ်
BOT_TOKEN = get_env_var('BOT_TOKEN')
API_KEY = get_env_var('SIM_API_KEY')
MONGO_URI = get_env_var('MONGO_URI')

# Optional vars
ADMIN_ID = int(os.environ.get('ADMIN_ID', '0')) 
PORT = int(os.environ.get('PORT', 8080))

# Economics
RUB_TO_MMK = 57.38
PROFIT_PERCENT = 25

# 5sim API
BASE_URL = "https://5sim.net/v1"
HEADERS = {'Authorization': 'Bearer ' + API_KEY, 'Accept': 'application/json'}

# ---------------- THREAD LOCK & CACHE ----------------
db_lock = threading.Lock() 
price_cache = {} 
CACHE_DURATION = 600 

# ---------------- DATABASE SETUP ----------------
try:
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client['5sim_reseller_db']
    users_collection = db['users']
    orders_collection = db['orders']
    logger.info("✅ Connected to MongoDB")
except Exception as e:
    logger.critical(f"❌ Database Connection Failed: {e}")
    raise e

# ---------------- DATABASE FUNCTIONS ----------------

def get_user(user_id):
    return users_collection.find_one({'_id': user_id})

def register_user(user_id, first_name):
    if not get_user(user_id):
        users_collection.insert_one({
            '_id': user_id,
            'name': first_name,
            'balance': 0,
            'joined_at': time.time()
        })

def update_balance(user_id, amount):
    with db_lock:
        user = get_user(user_id)
        if not user: return False
        
        new_balance = user.get('balance', 0) + amount
        if new_balance < 0:
            return False 
            
        users_collection.update_one({'_id': user_id}, {'$inc': {'balance': amount}})
        return True

def get_all_users_list():
    return list(users_collection.find())

# --- ORDER HISTORY ---
def save_order(user_id, order_id, phone, country, service, cost, status="PENDING"):
    orders_collection.insert_one({
        '_id': order_id,
        'user_id': user_id,
        'phone': phone,
        'country': country,
        'service': service,
        'cost': cost,
        'status': status,
        'sms': None,
        'timestamp': datetime.now()
    })

def update_order_status(order_id, status, sms_text=None):
    update_data = {'status': status}
    if sms_text:
        update_data['sms'] = sms_text
    orders_collection.update_one({'_id': order_id}, {'$set': update_data})

def get_user_history(user_id, limit=5):
    return list(orders_collection.find({'user_id': user_id}).sort('timestamp', -1).limit(limit))

# ---------------- PRICE CACHING SYSTEM ----------------
def get_cached_prices(product):
    current_time = time.time()
    if product in price_cache:
        cached_data = price_cache[product]
        if current_time - cached_data['timestamp'] < CACHE_DURATION:
            return cached_data['data']
    try:
        resp = requests.get(f"{BASE_URL}/guest/prices?product={product}", headers=HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            price_cache[product] = {
                'timestamp': current_time,
                'data': data
            }
            return data
    except Exception as e:
        logger.error(f"API Error: {e}")
    return {}

# ---------------- FLASK SERVER ----------------
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Running Securely!"
def run_web(): app.run(host='0.0.0.0', port=PORT)
def keep_alive(): threading.Thread(target=run_web, daemon=True).start()

bot = telebot.TeleBot(BOT_TOKEN)

# Popular Services
POPULAR_SERVICES = [
    'telegram', 'whatsapp', 'facebook', 'google', 'tiktok', 'viber', 
    'steam', 'discord', 'amazon', 'openai', 'shopee', 'lazada', 'netflix'
]

# ---------------- FULL FLAG MAPPING ----------------
FLAG_MAP = {
    'afghanistan': '🇦🇫', 'albania': '🇦🇱', 'algeria': '🇩🇿', 'angola': '🇦🇴', 'argentina': '🇦🇷',
    'armenia': '🇦🇲', 'australia': '🇦🇺', 'austria': '🇦🇹', 'azerbaijan': '🇦🇿', 'bahrain': '🇧🇭',
    'bangladesh': '🇧🇩', 'belarus': '🇧🇾', 'belgium': '🇧🇪', 'benin': '🇧🇯', 'bolivia': '🇧🇴',
    'bosnia': '🇧🇦', 'brazil': '🇧🇷', 'bulgaria': '🇧🇬', 'burkinafaso': '🇧🇫', 'burundi': '🇧🇮',
    'cambodia': '🇰🇭', 'cameroon': '🇨🇲', 'canada': '🇨🇦', 'chad': '🇹🇩', 'chile': '🇨🇱',
    'china': '🇨🇳', 'colombia': '🇨🇴', 'congo': '🇨🇬', 'croatia': '🇭🇷', 'cyprus': '🇨🇾',
    'czech': '🇨🇿', 'denmark': '🇩🇰', 'djibouti': '🇩🇯', 'dominican': '🇩🇴', 'ecuador': '🇪🇨',
    'egypt': '🇪🇬', 'england': '🇬🇧', 'equatorialguinea': '🇬🇶', 'estonia': '🇪🇪', 'ethiopia': '🇪🇹',
    'finland': '🇫🇮', 'france': '🇫🇷', 'gabon': '🇬🇦', 'gambia': '🇬🇲', 'georgia': '🇬🇪',
    'germany': '🇩🇪', 'ghana': '🇬🇭', 'greece': '🇬🇷', 'guatemala': '🇬🇹', 'guinea': '🇬🇳',
    'guineabissau': '🇬🇼', 'guyana': '🇬🇾', 'haiti': '🇭🇹', 'honduras': '🇭🇳', 'hongkong': '🇭🇰',
    'hungary': '🇭🇺', 'india': '🇮🇳', 'indonesia': '🇮🇩', 'iran': '🇮🇷', 'iraq': '🇮🇶',
    'ireland': '🇮🇪', 'israel': '🇮🇱', 'italy': '🇮🇹', 'ivorycoast': '🇨🇮', 'jamaica': '🇯🇲',
    'japan': '🇯🇵', 'jordan': '🇯🇴', 'kazakhstan': '🇰🇿', 'kenya': '🇰🇪', 'kuwait': '🇰🇼',
    'kyrgyzstan': '🇰🇬', 'laos': '🇱🇦', 'latvia': '🇱🇻', 'lebanon': '🇱🇧', 'lesotho': '🇱🇸',
    'liberia': '🇱🇷', 'libya': '🇱🇾', 'lithuania': '🇱🇹', 'luxembourg': '🇱🇺', 'macau': '🇲🇴',
    'madagascar': '🇲🇬', 'malawi': '🇲🇼', 'malaysia': '🇲🇾', 'maldives': '🇲🇻', 'mali': '🇲🇱',
    'mauritania': '🇲🇷', 'mauritius': '🇲🇺', 'mexico': '🇲🇽', 'moldova': '🇲🇩', 'mongolia': '🇲🇳',
    'montenegro': '🇲🇪', 'morocco': '🇲🇦', 'mozambique': '🇲🇿', 'myanmar': '🇲🇲', 'namibia': '🇳🇦',
    'nepal': '🇳🇵', 'netherlands': '🇳🇱', 'newzealand': '🇳🇿', 'nicaragua': '🇳🇮', 'niger': '🇳🇪',
    'nigeria': '🇳🇬', 'northmacedonia': '🇲🇰', 'norway': '🇳🇴', 'oman': '🇴🇲', 'pakistan': '🇵🇰',
    'palestine': '🇵🇸', 'panama': '🇵🇦', 'papuanewguinea': '🇵🇬', 'paraguay': '🇵🇾', 'peru': '🇵🇪',
    'philippines': '🇵🇭', 'poland': '🇵🇱', 'portugal': '🇵🇹', 'qatar': '🇶🇦', 'romania': '🇷🇴',
    'russia': '🇷🇺', 'rwanda': '🇷🇼', 'saudiarabia': '🇸🇦', 'senegal': '🇸🇳', 'serbia': '🇷🇸',
    'sierraleone': '🇸🇱', 'singapore': '🇸🇬', 'slovakia': '🇸🇰', 'slovenia': '🇸🇮', 'somalia': '🇸🇴',
    'southafrica': '🇿🇦', 'spain': '🇪🇸', 'srilanka': '🇱🇰', 'sudan': '🇸🇩', 'suriname': '🇸🇷',
    'swaziland': '🇸🇿', 'sweden': '🇸🇪', 'switzerland': '🇨🇭', 'syria': '🇸🇾', 'taiwan': '🇹🇼',
    'tajikistan': '🇹🇯', 'tanzania': '🇹🇿', 'thailand': '🇹🇭', 'timorleste': '🇹🇱', 'togo': '🇹🇬',
    'tunisia': '🇹🇳', 'turkey': '🇹🇷', 'turkmenistan': '🇹🇲', 'uganda': '🇺🇬', 'ukraine': '🇺🇦',
    'uae': '🇦🇪', 'uk': '🇬🇧', 'usa': '🇺🇸', 'uruguay': '🇺🇾', 'uzbekistan': '🇺🇿',
    'venezuela': '🇻🇪', 'vietnam': '🇻🇳', 'yemen': '🇾🇪', 'zambia': '🇿🇲', 'zimbabwe': '🇿🇼'
}

def get_flag(country_name):
    clean_name = country_name.lower().replace(" ", "")
    return FLAG_MAP.get(clean_name, '🏳️')

# ---------------- HELPER FUNCTIONS ----------------

def calculate_display_price(rub_price, user_id):
    rub_price = float(rub_price)
    base_mmk = rub_price * RUB_TO_MMK
    if user_id == ADMIN_ID:
        return int(base_mmk)
    else:
        marked_up = base_mmk * (1 + PROFIT_PERCENT / 100)
        return int(marked_up)

def get_server_balance():
    try:
        resp = requests.get(f"{BASE_URL}/user/profile", headers=HEADERS).json()
        return float(resp.get('balance', 0))
    except:
        return 0.0

# ---------------- ADMIN COMMANDS ----------------

# ---------------- BROADCAST SYSTEM (NEW) ----------------

from telebot.apihelper import ApiTelegramException

# Admin State for Broadcast
broadcast_data = {}

@bot.message_handler(commands=['broadcast'])
def cmd_broadcast(message):
    if message.from_user.id != ADMIN_ID: return
    
    msg = bot.reply_to(message, "📢 **Broadcast Setup**\n\nPlease send the message (Text or Photo) you want to send to all users.\n\nType /cancel to stop.", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_broadcast_content)

def process_broadcast_content(message):
    if message.from_user.id != ADMIN_ID: return
    if message.text == '/cancel':
        bot.reply_to(message, "❌ Broadcast cancelled.")
        return

    content_type = 'text'
    content = message.text
    caption = None
    
    if message.content_type == 'photo':
        content_type = 'photo'
        content = message.photo[-1].file_id # Get highest quality photo
        caption = message.caption

    # Confirm Dialog
    broadcast_data[ADMIN_ID] = {
        'type': content_type,
        'content': content,
        'caption': caption
    }
    
    user_count = users_collection.count_documents({})
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(f"✅ Send to {user_count} Users", callback_data="confirm_broadcast"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_broadcast")
    )
    
    preview_text = "photo" if content_type == 'photo' else content[:50] + "..."
    bot.reply_to(message, f"📢 **Confirm Broadcast**\n\nType: {content_type.upper()}\nPreview: {preview_text}\n\nTarget: {user_count} Users", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data in ['confirm_broadcast', 'cancel_broadcast'])
def handle_broadcast_callback(call):
    if call.data == 'cancel_broadcast':
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "Cancelled")
        broadcast_data.pop(ADMIN_ID, None)
    
    elif call.data == 'confirm_broadcast':
        data = broadcast_data.get(ADMIN_ID)
        if not data:
            bot.answer_callback_query(call.id, "Session expired.")
            return

        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "Broadcasting started...")
        
        # Start Thread
        threading.Thread(target=run_broadcast_thread, args=(call.message.chat.id, data)).start()

def run_broadcast_thread(admin_chat_id, data):
    users = get_all_users_list()
    total = len(users)
    sent = 0
    failed = 0
    blocked = 0
    
    status_msg = bot.send_message(admin_chat_id, f"🚀 **Broadcasting Started...**\n\nTotal: {total}\n✅ Sent: 0\n❌ Failed/Blocked: 0")
    
    start_time = time.time()
    
    for index, user in enumerate(users):
        try:
            if data['type'] == 'text':
                bot.send_message(user['_id'], data['content'], parse_mode="Markdown")
            elif data['type'] == 'photo':
                bot.send_photo(user['_id'], data['content'], caption=data['caption'], parse_mode="Markdown")
            
            sent += 1
        except ApiTelegramException as e:
            if e.result_json['error_code'] == 403: # User blocked bot
                blocked += 1
            else:
                failed += 1
        except Exception:
            failed += 1
            
        # Update Progress every 20 users (to avoid spamming API)
        if index % 20 == 0:
            try:
                bot.edit_message_text(
                    f"🚀 **Broadcasting in Progress...**\n\n"
                    f"📊 Progress: {index}/{total}\n"
                    f"✅ Sent: {sent}\n"
                    f"🚫 Blocked: {blocked}\n"
                    f"❌ Failed: {failed}",
                    admin_chat_id, status_msg.message_id, parse_mode="Markdown"
                )
            except: pass
        
        # Rate Limit Safety (20 msgs per second max)
        time.sleep(0.05)

    # Final Report
    duration = round(time.time() - start_time, 2)
    final_text = (
        f"✅ **Broadcast Completed!**\n\n"
        f"⏱ Time: {duration}s\n"
        f"👥 Total Users: {total}\n"
        f"✅ Success: {sent}\n"
        f"🚫 Blocked (Skipped): {blocked}\n"
        f"❌ Failed: {failed}"
    )
    
    try:
        bot.edit_message_text(final_text, admin_chat_id, status_msg.message_id, parse_mode="Markdown")
    except:
        bot.send_message(admin_chat_id, final_text, parse_mode="Markdown")

# ---------------- END BROADCAST SYSTEM ----------------


@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID: return
    
    all_users = get_all_users_list()
    total_holdings = sum(u.get('balance', 0) for u in all_users)
    
    msg = (
        "👑 **Admin Control Panel**\n\n"
        f"👥 Total Users: `{len(all_users)}`\n"
        f"💰 Total User Holdings: `{total_holdings} Ks`\n\n"
        "**Commands:**\n"
        "`/users` - Get User List\n"
        "`/add [ID] [Amount]` - Add Balance\n"
        "`/cut [ID] [Amount]` - Deduct Balance\n"
        "`/info [ID]` - Check User History"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("👥 Get User List", callback_data="admin_get_users"))
    bot.reply_to(message, msg, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=['users'])
def cmd_get_users(message):
    if message.from_user.id != ADMIN_ID: return
    send_user_list(message.chat.id)

def send_user_list(chat_id):
    users = get_all_users_list()
    if not users:
        bot.send_message(chat_id, "No users found.")
        return

    msg_chunk = "📋 **User List:**\n\n"
    for u in users:
        line = f"🆔 `{u['_id']}` | {u.get('name', 'Unknown')} | 💰 `{u.get('balance', 0)} Ks`\n"
        if len(msg_chunk) + len(line) > 3500:
            bot.send_message(chat_id, msg_chunk, parse_mode="Markdown")
            msg_chunk = ""
        msg_chunk += line
    if msg_chunk: bot.send_message(chat_id, msg_chunk, parse_mode="Markdown")

@bot.message_handler(commands=['add'])
def add_money(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split()
        if len(parts) != 3: raise ValueError
        user_id = int(parts[1])
        amount = int(parts[2])
        
        if update_balance(user_id, amount):
            bot.reply_to(message, f"✅ Added `{amount} Ks` to User `{user_id}`.", parse_mode="Markdown")
            try: bot.send_message(user_id, f"💰 Deposit Received: `{amount} Ks`", parse_mode="Markdown")
            except: pass
        else:
            bot.reply_to(message, "❌ User ID not found.")
    except: bot.reply_to(message, "Error. Use: `/add 123456 1000`")

@bot.message_handler(commands=['cut'])
def cut_money(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split()
        if len(parts) != 3: raise ValueError
        user_id = int(parts[1])
        amount = int(parts[2])
        
        if update_balance(user_id, -amount):
            bot.reply_to(message, f"✂️ Deducted `{amount} Ks` from User `{user_id}`.", parse_mode="Markdown")
            try: bot.send_message(user_id, f"📉 Balance Deducted: `{amount} Ks`", parse_mode="Markdown")
            except: pass
        else:
            bot.reply_to(message, "❌ User ID not found or Insufficient Balance.")
    except: bot.reply_to(message, "Error. Use: `/cut 123456 1000`")

@bot.message_handler(commands=['info'])
def user_info(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split()
        if len(parts) != 2: raise ValueError
        uid = int(parts[1])
        u = get_user(uid)
        
        if u:
            msg = f"👤 **User Info**\nID: `{uid}`\nName: {u.get('name')}\nBalance: `{u.get('balance')} Ks`\n\n"
            history = get_user_history(uid, limit=5)
            if history:
                msg += "📜 **Last 5 Orders:**\n"
                for order in history:
                    status_icon = "⏳"
                    if order['status'] == 'COMPLETED': status_icon = "✅"
                    elif order['status'] == 'CANCELED': status_icon = "❌"
                    elif order['status'] == 'TIMEOUT': status_icon = "⚠️"
                    flag = get_flag(order['country'])
                    sms_info = f"\n📩 SMS: `{order['sms']}`" if order.get('sms') else ""
                    msg += (f"━━━━━━━━━━━━━━━━\n"
                            f"🆔 `{order['_id']}` | {status_icon} {order['status']}\n"
                            f"{flag} {order['country'].upper()} | {order['service'].upper()}\n"
                            f"📱 `{order['phone']}` | 💰 {order['cost']} Ks"
                            f"{sms_info}\n")
            else:
                msg += "📜 **History:** No orders yet."
            bot.reply_to(message, msg, parse_mode="Markdown")
        else:
            bot.reply_to(message, "❌ User not found.")
    except: bot.reply_to(message, "Error. Use: `/info 123456`")

# ---------------- USER COMMANDS ----------------

@bot.message_handler(commands=['start'])
def start(message):
    register_user(message.from_user.id, message.from_user.first_name)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add('🛒 Buy Number', '👤 My Profile', '💳 Top-up')
    bot.send_message(message.chat.id, f"Welcome {message.from_user.first_name}! 🌍\nSelect an option below:", reply_markup=markup)

@bot.message_handler(func=lambda msg: True)
def main_menu(message):
    user_id = message.from_user.id
    text = message.text
    
    if text == '👤 My Profile':
        register_user(user_id, message.from_user.first_name)
        user = get_user(user_id)
        bal = user.get('balance', 0)
        
        msg_text = f"👤 **User Profile**\n\n🆔 ID: `{user_id}`\n👤 Name: {user.get('name')}\n💰 **Wallet Balance: {bal} Ks**"
        
        if user_id == ADMIN_ID:
            server_bal_rub = get_server_balance()
            server_bal_mmk = int(server_bal_rub * RUB_TO_MMK)
            all_u = get_all_users_list()
            total_user_mmk = sum(u.get('balance', 0) for u in all_u)
            msg_text += (f"\n\n⚙️ **Admin Dashboard:**\n━━━━━━━━━━━━━━━━━━\n"
                         f"🔌 **Server Balance:**\n   🇷🇺 `{server_bal_rub} RUB`\n   🇲🇲 `~{server_bal_mmk} MMK`\n\n"
                         f"👥 Total User Funds: `{total_user_mmk} Ks`")
        bot.reply_to(message, msg_text, parse_mode="Markdown")
        
    elif text == '💳 Top-up':
        msg = (f"💸 **To top-up your wallet, please contact Admin.**\n\n👤 Admin: @Shake0098\n🆔 Your ID: `{user_id}`\n\n"
               f"💰 **Payment Methods:**\n\n🇲🇲 **Myanmar:**\n• KBZ Pay\n• Wave Pay\n• AYA Pay\n• UAB Pay\n\n"
               f"🌍 **Global:**\n• Binance\n• Bybit\n• Any Crypto (USDT)")
        bot.reply_to(message, msg, parse_mode="Markdown")
        
    elif text == '🛒 Buy Number':
        show_services(user_id, 0)

# ---------------- SERVICE MENU (CACHED) ----------------

def show_services(chat_id, page=0, msg_id=None):
    markup = types.InlineKeyboardMarkup(row_width=2)
    if page == 0:
        buttons = [types.InlineKeyboardButton(f"📱 {s.capitalize()}", callback_data=f"srv|{s}") for s in POPULAR_SERVICES]
        markup.add(*buttons)
        markup.add(types.InlineKeyboardButton("See All Services ⤵️", callback_data="page|1"))
        text = "🔥 **Popular Services:**"
    else:
        try:
            resp = requests.get(f"{BASE_URL}/guest/products/any/any", headers=HEADERS).json()
            services = [k for k, v in resp.items() if v.get('Qty', 0) > 0]
            services.sort()
            PER_PAGE = 30
            total_pages = (len(services) + PER_PAGE - 1) // PER_PAGE
            start = (page - 1) * PER_PAGE
            end = start + PER_PAGE
            current_batch = services[start:end]
            buttons = [types.InlineKeyboardButton(s, callback_data=f"srv|{s}") for s in current_batch]
            markup.add(*buttons)
            nav = []
            if page > 1: nav.append(types.InlineKeyboardButton("⬅️ Back", callback_data=f"page|{page-1}"))
            if end < len(services): nav.append(types.InlineKeyboardButton("Next ➡️", callback_data=f"page|{page+1}"))
            markup.add(*nav)
            markup.add(types.InlineKeyboardButton("⬅️ Back to Popular", callback_data="page|0"))
            text = f"🌐 **All Services** (Page {page}/{total_pages}):"
        except: text = "Error fetching services."
    if msg_id: bot.edit_message_text(text, chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    else: bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

# ---------------- COUNTRY MENU (CACHED) ----------------

def show_countries(chat_id, service, page=0, msg_id=None):
    bot.send_chat_action(chat_id, 'typing')
    try:
        resp = get_cached_prices(service)
        data_source = resp.get(service, {}) if service in resp else resp
        countries = []
        for c_name, ops in data_source.items():
            if not isinstance(ops, dict): continue
            min_price_rub = float('inf')
            total_stock = 0
            for op, det in ops.items():
                if det['count'] > 0:
                    total_stock += det['count']
                    if det['cost'] < min_price_rub: min_price_rub = det['cost']
            if total_stock > 0:
                display_price = calculate_display_price(min_price_rub, chat_id)
                countries.append({'n': c_name, 'p': display_price, 's': total_stock})
        
        countries.sort(key=lambda x: x['p'])
        if not countries:
            bot.send_message(chat_id, "❌ No stock available (Wait for refresh).")
            return

        PER_PAGE = 20
        total_pages = (len(countries) + PER_PAGE - 1) // PER_PAGE
        if page < 0: page = 0
        if page >= total_pages: page = total_pages - 1
        start = page * PER_PAGE
        end = start + PER_PAGE
        current_batch = countries[start:end]

        markup = types.InlineKeyboardMarkup(row_width=1)
        for c in current_batch:
            flag = get_flag(c['n'])
            btn_txt = f"{flag} {c['n'].upper()} - from {c['p']} Ks ({c['s']})"
            markup.add(types.InlineKeyboardButton(btn_txt, callback_data=f"op|{c['n']}|{service}"))
        
        nav_btns = []
        if page > 0: nav_btns.append(types.InlineKeyboardButton("⬅️ Back", callback_data=f"cnt_pg|{service}|{page-1}"))
        if end < len(countries): nav_btns.append(types.InlineKeyboardButton("Next ➡️", callback_data=f"cnt_pg|{service}|{page+1}"))
        markup.add(*nav_btns)
        markup.add(types.InlineKeyboardButton("⬅️ Back to Services", callback_data="page|0"))
        
        text = f"🌍 **{service.upper()}** - Select Country (Page {page+1}/{total_pages}):"
        if msg_id: bot.edit_message_text(text, chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
        else: bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error loading countries: {e}")
        bot.send_message(chat_id, "Error loading countries.")

# ---------------- OPERATOR MENU (CACHED) ----------------

def show_operators(chat_id, country, service, msg_id):
    try:
        resp = get_cached_prices(service)
        data_source = resp.get(service, {}).get(country, {})
        markup = types.InlineKeyboardMarkup(row_width=1)
        valid_ops = []
        for op, det in data_source.items():
            if det['count'] > 0: valid_ops.append({'name': op, 'cost': det['cost'], 'count': det['count']})
        valid_ops.sort(key=lambda x: x['cost'])
        flag = get_flag(country)
        if valid_ops:
            best_price_rub = valid_ops[0]['cost']
            display_price = calculate_display_price(best_price_rub, chat_id)
            markup.add(types.InlineKeyboardButton(f"🎲 Any Operator (Auto) - {display_price} Ks", callback_data=f"buy|{country}|any|{service}"))
        for op in valid_ops:
            d_price = calculate_display_price(op['cost'], chat_id)
            markup.add(types.InlineKeyboardButton(f"📶 {op['name'].upper()} - {d_price} Ks ({op['count']})", callback_data=f"buy|{country}|{op['name']}|{service}"))
        
        markup.add(types.InlineKeyboardButton("⬅️ Back to Countries", callback_data=f"cnt_pg|{service}|0"))
        bot.edit_message_text(f"📶 Operator for **{flag} {country.upper()}**:", chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    except: bot.send_message(chat_id, "Error loading operators.")

# ---------------- BUY HANDLER (SECURE & LOCKED) ----------------

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.message.chat.id
    data = call.data.split('|')
    action = data[0]
    
    if action == 'page': show_services(user_id, int(data[1]), call.message.message_id)
    elif action == 'srv': show_countries(user_id, data[1], page=0, msg_id=call.message.message_id)
    elif action == 'cnt_pg': show_countries(user_id, data[1], page=int(data[2]), msg_id=call.message.message_id)
    elif action == 'op': show_operators(user_id, data[1], data[2], call.message.message_id)
    elif action == 'admin_get_users' and user_id == ADMIN_ID: send_user_list(user_id)
    
    elif action == 'buy':
        country, operator, service = data[1], data[2], data[3]
        try:
            # Re-fetch LIVE price
            p_data = requests.get(f"{BASE_URL}/guest/prices?product={service}", headers=HEADERS).json()
            ops = p_data.get(service, {}).get(country, {})
            real_rub_cost = float('inf')
            
            if operator == 'any':
                for k, v in ops.items():
                    if v['count'] > 0 and v['cost'] < real_rub_cost: real_rub_cost = v['cost']
            else:
                if operator in ops and ops[operator]['count'] > 0: real_rub_cost = ops[operator]['cost']
            
            if real_rub_cost == float('inf'):
                bot.answer_callback_query(call.id, "❌ Stock unavailable.", show_alert=True)
                return

            final_mmk = calculate_display_price(real_rub_cost, user_id)
            user = get_user(user_id)
            
            if user.get('balance', 0) < final_mmk:
                bot.answer_callback_query(call.id, "❌ Insufficient Balance!", show_alert=True)
                return

            bot.edit_message_text("🔄 Processing...", user_id, call.message.message_id)
            
            buy_resp = requests.get(f"{BASE_URL}/user/buy/activation/{country}/{operator}/{service}", headers=HEADERS).json()
            
            if 'phone' in buy_resp:
                if update_balance(user_id, -final_mmk):
                    phone, oid = buy_resp['phone'], buy_resp['id']
                    flag = get_flag(country)
                    
                    save_order(user_id, oid, phone, country, service, final_mmk, "PENDING")
                    
                    msg = (f"✅ **Order Successful!**\n"
                           f"📱 Phone: `{phone}`\n"
                           f"🌍 Country: {flag} {country.upper()}\n"
                           f"💰 Deducted: {final_mmk} Ks\n"
                           f"⏳ Waiting for SMS...\n\n"
                           f"_(If SMS is delayed or does not arrive, please try selecting a higher-priced operator for better quality.)_")
                    
                    markup = types.InlineKeyboardMarkup()
                    markup.add(types.InlineKeyboardButton("❌ Cancel Order", callback_data=f"cancel|{oid}|{final_mmk}"))
                    
                    sent_msg = bot.send_message(user_id, msg, reply_markup=markup, parse_mode="Markdown")
                    threading.Thread(target=check_sms_thread, args=(user_id, oid, final_mmk, sent_msg.message_id, phone, country)).start()
                else:
                    bot.send_message(user_id, "❌ Transaction Failed.")
            else:
                bot.send_message(user_id, "❌ Purchase Failed. Try a different operator.")
        except Exception as e:
            logger.error(f"Buy Error: {e}")
            bot.send_message(user_id, "Error during purchase.")

    elif action == 'cancel':
        oid, amount = data[1], int(data[2])
        resp = requests.get(f"{BASE_URL}/user/cancel/{oid}", headers=HEADERS).json()
        if resp.get('status') == 'CANCELED':
            update_balance(user_id, amount)
            update_order_status(oid, "CANCELED")
            bot.send_message(user_id, f"✅ Order Canceled.\n💰 `{amount} Ks` refunded.", parse_mode="Markdown")
        else:
            bot.send_message(user_id, "⚠️ Unable to cancel (SMS may be received).")

def check_sms_thread(user_id, order_id, cost_mmk, message_id, phone, country):
    flag = get_flag(country)
    for i in range(180): # 15 mins
        time.sleep(5)
        try:
            res = requests.get(f"{BASE_URL}/user/check/{order_id}", headers=HEADERS).json()
            status = res.get('status')
            if status == 'RECEIVED':
                code = res['sms'][0]['code']
                msg = res['sms'][0].get('text', '')
                
                update_order_status(order_id, "COMPLETED", sms_text=f"{code} - {msg}")
                bot.send_message(user_id, f"📩 **SMS RECEIVED!**\n\nCode: `{code}`\nMsg: {msg}", parse_mode="Markdown")
                
                # Remove Cancel Button & Show Completed
                try:
                    completed_msg = (f"✅ **Order Completed!**\n"
                                     f"📱 Phone: `{phone}`\n"
                                     f"🌍 Country: {flag} {country.upper()}\n"
                                     f"💰 Deducted: {cost_mmk} Ks\n"
                                     f"📩 SMS Code Received.")
                    bot.edit_message_text(completed_msg, user_id, message_id, reply_markup=None, parse_mode="Markdown")
                except: pass
                return
            elif status == 'CANCELED':
                update_order_status(order_id, "CANCELED")
                return
            elif status == 'TIMEOUT':
                update_order_status(order_id, "TIMEOUT")
                return
        except: pass
    
    requests.get(f"{BASE_URL}/user/cancel/{order_id}", headers=HEADERS)
    update_balance(user_id, cost_mmk)
    update_order_status(order_id, "TIMEOUT")
    bot.send_message(user_id, f"⚠️ **Timeout**\nOrder cancelled automatically.\n💰 `{cost_mmk} Ks` refunded.\n💡 Suggestion: Try higher price operator.", parse_mode="Markdown")

# --- ဒီနေရာကစပြီး ကူးထည့်ပါ ---
# Flask Web Server Setup for Koyeb

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    # Web Server ကို သီးသန့် Thread နဲ့ run မယ်
    t = Thread(target=run_web_server)
    t.start()
    
    # Bot ကို run မယ် (မိတ်ဆွေ မူလ settings အတိုင်း)
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
