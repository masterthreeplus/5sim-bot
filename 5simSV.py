import telebot
import requests
import time
import threading
import os
import certifi
import logging
import csv
from flask import Flask
from telebot import types
from pymongo import MongoClient
from datetime import datetime
from telebot.apihelper import ApiTelegramException

# ---------------- LOGGING SETUP ----------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ---------------- SECURITY CHECK & CONFIG ----------------
def get_env_var(name):
    val = os.environ.get(name)
    if not val:
        logger.critical(f"❌ Missing Environment Variable: {name}")
        raise ValueError(f"Missing {name}")
    return val

BOT_TOKEN = get_env_var('BOT_TOKEN')
API_KEY   = get_env_var('SIM_API_KEY')
MONGO_URI = get_env_var('MONGO_URI')

ADMIN_ID       = 5127528224
PORT           = int(os.environ.get('PORT', 8080))
PROFIT_PERCENT = 25

BASE_URL = "https://5sim.net/v1"
HEADERS  = {'Authorization': 'Bearer ' + API_KEY, 'Accept': 'application/json'}

# ---------------- THREAD LOCK & CACHE ----------------
db_lock      = threading.Lock()
price_cache  = {}
CACHE_DURATION = 600

# ---------------- DATABASE SETUP ----------------
try:
    client            = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db                = client['5sim_reseller_db']
    users_collection  = db['users']
    orders_collection = db['orders']
    logger.info("✅ Connected to MongoDB")
except Exception as e:
    logger.critical(f"❌ Database Connection Failed: {e}")
    raise e

# ---------------- DATABASE FUNCTIONS ----------------
def get_user(user_id):
    return users_collection.find_one({'_id': user_id})

def register_or_update_user(user, status="active"):
    user_id    = user.id
    username   = f"@{user.username}" if user.username else "N/A"
    first_name = user.first_name
    existing   = users_collection.find_one({'_id': user_id})
    if not existing:
        users_collection.insert_one({
            '_id': user_id, 'username': username, 'name': first_name,
            'balance': 0.0, 'status': status, 'joined_at': time.time()
        })
    else:
        users_collection.update_one(
            {'_id': user_id},
            {'$set': {'name': first_name, 'username': username, 'status': status}}
        )

def update_balance(user_id, amount):
    with db_lock:
        user = get_user(user_id)
        if not user: return False
        new_balance = float(user.get('balance', 0.0)) + float(amount)
        if new_balance < 0: return False
        users_collection.update_one({'_id': user_id}, {'$set': {'balance': new_balance}})
        return True

def get_all_users_list():
    return list(users_collection.find())

def save_order(user_id, order_id, phone, country, service, cost, status="PENDING"):
    orders_collection.insert_one({
        '_id': order_id, 'user_id': user_id, 'phone': phone,
        'country': country, 'service': service, 'cost': cost,
        'status': status, 'sms': None, 'timestamp': datetime.now()
    })

def update_order_status(order_id, status, sms_text=None):
    update_data = {'status': status}
    if sms_text: update_data['sms'] = sms_text
    orders_collection.update_one({'_id': order_id}, {'$set': update_data})

def get_user_history(user_id, limit=5):
    return list(orders_collection.find({'user_id': user_id}).sort('timestamp', -1).limit(limit))

# ---------------- PRICE CALCULATION ----------------
def get_cached_prices(product):
    current_time = time.time()
    if product in price_cache:
        if current_time - price_cache[product]['timestamp'] < CACHE_DURATION:
            return price_cache[product]['data']
    try:
        resp = requests.get(f"{BASE_URL}/guest/prices?product={product}", headers=HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            price_cache[product] = {'timestamp': current_time, 'data': data}
            return data
    except Exception as e:
        logger.error(f"API Error: {e}")
    return {}

def calculate_display_price(api_price, user_id):
    base = float(api_price)
    if user_id == ADMIN_ID:
        return round(base, 3)
    return round(base * (1 + PROFIT_PERCENT / 100), 3)

def get_server_balance_raw():
    try:
        resp = requests.get(f"{BASE_URL}/user/profile", headers=HEADERS).json()
        return float(resp.get('balance', 0))
    except:
        return 0.0

bot = telebot.TeleBot(BOT_TOKEN)

POPULAR_SERVICES = [
    'telegram', 'whatsapp', 'facebook', 'google', 'tiktok', 'viber',
    'steam', 'discord', 'amazon', 'openai', 'shopee', 'lazada', 'netflix', 'signal'
]

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
    return FLAG_MAP.get(country_name.lower().replace(" ", ""), '🏳️')

# ── All-services cache ───────────────────────────────────────────────────────
_all_svc_cache = {'data': [], 'ts': 0}

def get_all_services():
    if time.time() - _all_svc_cache['ts'] < CACHE_DURATION and _all_svc_cache['data']:
        return _all_svc_cache['data']
    try:
        resp = requests.get(f"{BASE_URL}/guest/products/any/any", headers=HEADERS).json()
        svcs = sorted([k for k, v in resp.items() if v.get('Qty', 0) > 0])
        _all_svc_cache['data'] = svcs
        _all_svc_cache['ts']   = time.time()
        return svcs
    except:
        return []

# ---------------- BROADCAST ----------------
broadcast_data = {}

@bot.message_handler(commands=['broadcast'])
def cmd_broadcast(message):
    if message.from_user.id != ADMIN_ID: return
    msg = bot.reply_to(message, "📢 **Broadcast Setup**\n\nSend Text or Photo.\nType /cancel to stop.", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_broadcast_content)

def process_broadcast_content(message):
    if message.from_user.id != ADMIN_ID: return
    if message.text == '/cancel':
        bot.reply_to(message, "❌ Broadcast cancelled.")
        return
    content_type, content, caption = 'text', message.text, None
    if message.content_type == 'photo':
        content_type, content, caption = 'photo', message.photo[-1].file_id, message.caption
    broadcast_data[ADMIN_ID] = {'type': content_type, 'content': content, 'caption': caption}
    user_count = users_collection.count_documents({})
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton(f"✅ Send to {user_count} Users", callback_data="confirm_broadcast"),
        types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_broadcast")
    )
    bot.reply_to(message, f"📢 **Confirm Broadcast**\nTarget: {user_count} Users", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data in ['confirm_broadcast', 'cancel_broadcast'])
def handle_broadcast_callback(call):
    if call.data == 'cancel_broadcast':
        bot.delete_message(call.message.chat.id, call.message.message_id)
        broadcast_data.pop(ADMIN_ID, None)
    elif call.data == 'confirm_broadcast':
        data = broadcast_data.get(ADMIN_ID)
        if not data: return
        bot.delete_message(call.message.chat.id, call.message.message_id)
        threading.Thread(target=run_broadcast_thread, args=(call.message.chat.id, data)).start()

def run_broadcast_thread(admin_chat_id, data):
    users = get_all_users_list()
    total, sent, failed, blocked = len(users), 0, 0, 0
    status_msg = bot.send_message(admin_chat_id, "🚀 Broadcasting...")
    for index, user in enumerate(users):
        try:
            if data['type'] == 'text':   bot.send_message(user['_id'], data['content'], parse_mode="Markdown")
            elif data['type'] == 'photo': bot.send_photo(user['_id'], data['content'], caption=data['caption'], parse_mode="Markdown")
            if user.get('status') == 'blocked':
                users_collection.update_one({'_id': user['_id']}, {'$set': {'status': 'active'}})
            sent += 1
        except ApiTelegramException as e:
            if e.result_json['error_code'] == 403:
                blocked += 1
                users_collection.update_one({'_id': user['_id']}, {'$set': {'status': 'blocked'}})
            else: failed += 1
        except: failed += 1
        if index % 20 == 0:
            try: bot.edit_message_text(f"🚀 Progress: {index}/{total}\n✅: {sent} | 🚫: {blocked}", admin_chat_id, status_msg.message_id)
            except: pass
        time.sleep(0.05)
    bot.send_message(admin_chat_id, f"✅ Done!\nTotal: {total}\nSent: {sent}\nBlocked: {blocked}\nFailed: {failed}")

# ---------------- ADMIN COMMANDS ----------------
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID: return
    all_users      = get_all_users_list()
    total_holdings = sum(float(u.get('balance', 0)) for u in all_users)
    msg = (
        "👑 **Admin Control Panel**\n\n"
        f"👥 Total Users: `{len(all_users)}`\n"
        f"💰 Total User Holdings: `${round(total_holdings, 2)}`\n\n"
        "**Commands:**\n"
        "`/users` - Download Advanced User CSV\n"
        "`/add [ID] [Amount]` - Add Balance ($)\n"
        "`/cut [ID] [Amount]` - Deduct Balance ($)\n"
        "`/info [ID]` - Check User\n"
        "`/broadcast` - Announcement"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📥 Download Advanced CSV", callback_data="admin_download_csv"))
    bot.reply_to(message, msg, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(commands=['users'])
def cmd_download_users(message):
    if message.from_user.id != ADMIN_ID: return
    send_users_csv(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data == 'admin_download_csv')
def handle_csv_callback(call):
    if call.message.chat.id != ADMIN_ID: return
    bot.answer_callback_query(call.id, "Generating Advanced CSV...")
    send_users_csv(call.message.chat.id)

def send_users_csv(chat_id):
    users = get_all_users_list()
    if not users:
        bot.send_message(chat_id, "No users found.")
        return
    filename = f"users_data_{int(time.time())}.csv"
    try:
        pipeline  = [{"$match": {"status": "COMPLETED"}}, {"$group": {"_id": "$user_id", "total_spent": {"$sum": "$cost"}}}]
        spend_map = {item['_id']: item['total_spent'] for item in orders_collection.aggregate(pipeline)}
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['User ID', 'Username', 'Name', 'Balance ($)', 'Total Spend ($)', 'Status', 'Joined Date'])
            for u in users:
                uid    = u['_id']
                joined = datetime.fromtimestamp(u.get('joined_at', 0)).strftime('%Y-%m-%d %H:%M:%S')
                writer.writerow([uid, u.get('username', 'N/A'), u.get('name', 'Unknown'),
                                  u.get('balance', 0), round(spend_map.get(uid, 0.0), 3),
                                  u.get('status', 'active').upper(), joined])
        with open(filename, 'rb') as f:
            bot.send_document(chat_id, f, caption=f"📋 Advanced User Data\n👥 Total Users: {len(users)}")
    except Exception as e:
        bot.send_message(chat_id, f"Error generating CSV: {e}")
    finally:
        if os.path.exists(filename): os.remove(filename)

@bot.message_handler(commands=['add'])
def add_money(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split()
        if len(parts) != 3: raise ValueError
        user_id, amount = int(parts[1]), float(parts[2])
        if update_balance(user_id, amount):
            bot.reply_to(message, f"✅ Added `${amount}` to User `{user_id}`.", parse_mode="Markdown")
            try: bot.send_message(user_id, f"💰 Deposit Received: `${amount}`", parse_mode="Markdown")
            except: pass
        else: bot.reply_to(message, "❌ User ID not found.")
    except: bot.reply_to(message, "Error. Use: `/add 123456 1.50`")

@bot.message_handler(commands=['cut'])
def cut_money(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split()
        if len(parts) != 3: raise ValueError
        user_id, amount = int(parts[1]), float(parts[2])
        if update_balance(user_id, -amount):
            bot.reply_to(message, f"✂️ Deducted `${amount}` from User `{user_id}`.", parse_mode="Markdown")
            try: bot.send_message(user_id, f"📉 Balance Deducted: `${amount}`", parse_mode="Markdown")
            except: pass
        else: bot.reply_to(message, "❌ User ID not found or Insufficient Balance.")
    except: bot.reply_to(message, "Error. Use: `/cut 123456 1.50`")

@bot.message_handler(commands=['info'])
def user_info(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        parts = message.text.split()
        if len(parts) != 2: raise ValueError
        uid = int(parts[1])
        u   = get_user(uid)
        if u:
            si_map = {'COMPLETED': '✅', 'CANCELED': '❌', 'TIMEOUT': '⚠️'}
            msg = (f"👤 **User Info**\nID: `{uid}`\nUser: {u.get('username','N/A')}\n"
                   f"Name: {u.get('name')}\nStat: `{u.get('status','active').upper()}`\n"
                   f"Bal: `${float(u.get('balance',0))}`\n\n")
            history = get_user_history(uid, limit=5)
            if history:
                msg += "📜 **Last 5 Orders:**\n"
                for order in history:
                    si   = si_map.get(order['status'], '⏳')
                    flag = get_flag(order['country'])
                    sms  = f"\n📩 SMS: `{order['sms']}`" if order.get('sms') else ""
                    msg += (f"━━━━━━━━━━━━━━━━\n🆔 `{order['_id']}` | {si} {order['status']}\n"
                            f"{flag} {order['country'].upper()} | {order['service'].upper()}\n"
                            f"📱 `{order['phone']}` | 💰 ${order['cost']}{sms}\n")
            else: msg += "📜 **History:** No orders yet."
            bot.reply_to(message, msg, parse_mode="Markdown")
        else: bot.reply_to(message, "❌ User not found.")
    except: bot.reply_to(message, "Error. Use: `/info 123456`")

# ---------------- USER COMMANDS ----------------
@bot.message_handler(commands=['start'])
def start(message):
    register_or_update_user(message.from_user)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add('🛒 Buy Number', '👤 My Profile', '💳 Top-up')
    bot.send_message(message.chat.id,
                     f"👋 Welcome, *{message.from_user.first_name}*! 🌍\n\nChoose an option below:",
                     reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: True)
def main_menu(message):
    user_id = message.from_user.id
    register_or_update_user(message.from_user)
    text = message.text

    if text == '👤 My Profile':
        user = get_user(user_id)
        if user_id == ADMIN_ID:
            server_bal = get_server_balance_raw()
            all_u      = get_all_users_list()
            total_user = sum(float(u.get('balance', 0)) for u in all_u)
            msg_text = (
                f"👤 **User Profile**\n\n🆔 ID: `{user_id}`\n👤 Name: {user.get('name')}\n"
                f"💰 **Wallet Balance: ${server_bal}**\n\n"
                f"⚙️ **Admin Dashboard:**\n━━━━━━━━━━━━━━━━━━\n"
                f"🔌 **Server Balance:** `${server_bal}`\n"
                f"👥 Total User Funds: `${round(total_user, 2)}`"
            )
        else:
            bal      = float(user.get('balance', 0))
            msg_text = (f"👤 **User Profile**\n\n🆔 ID: `{user_id}`\n"
                        f"👤 Name: {user.get('name')}\n💰 **Wallet Balance: ${bal}**")
        bot.reply_to(message, msg_text, parse_mode="Markdown")

    elif text == '💳 Top-up':
        msg = (f"💸 **Top-Up Your Wallet**\n\n📌 Contact Admin to deposit:\n"
               f"👤 Admin: @gloryme777\n🆔 Your ID: `{user_id}`\n\n"
               f"━━━━━━━━━━━━━━━━━━\n💵 **Accepted Payment:**\n\n"
               f"🟡 **USDT (TRC-20 / ERC-20)**\n━━━━━━━━━━━━━━━━━━")
        bot.reply_to(message, msg, parse_mode="Markdown")

    elif text == '🛒 Buy Number':
        show_services(user_id, 0)

# ─────────────────────────────────────────────────────────────────
# SERVICE MENU
#   page == 0   → popular services
#   page == -1  → alphabet / number filter (calendar-style table)
#   page >= 1   → filtered list by letter (from alpha|X)
# ─────────────────────────────────────────────────────────────────
def show_services(chat_id, page=0, msg_id=None):
    markup = types.InlineKeyboardMarkup(row_width=2)

    if page == 0:
        # ── Popular ──────────────────────────────────────────────
        buttons = [types.InlineKeyboardButton(f"📱 {s.capitalize()}", callback_data=f"srv|{s}")
                   for s in POPULAR_SERVICES]
        markup.add(*buttons)
        markup.add(types.InlineKeyboardButton("🔍 See All Services", callback_data="page|-1"))
        markup.add(types.InlineKeyboardButton("❌ Close", callback_data="close_menu"))
        text = "🔥 **Popular Services:**\nSelect a service to buy a number."

    elif page == -1:
        # ── Alphabet / digit filter table ────────────────────────
        services = get_all_services()
        active = set()
        for s in services:
            ch = s[0].upper()
            active.add(ch if ch.isalpha() else '#')

        # Row 0: number group
        has_num = '#' in active
        markup.row(
            types.InlineKeyboardButton("🔢  0 – 9" if has_num else "·",
                                       callback_data="alpha|#" if has_num else "noop")
        )

        # Rows 1–5: A–Z in rows of 5 (fits nicely on mobile)
        alphabet = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        for i in range(0, len(alphabet), 5):
            row_ltrs = alphabet[i:i + 5]
            btns = []
            for ltr in row_ltrs:
                if ltr in active:
                    btns.append(types.InlineKeyboardButton(ltr, callback_data=f"alpha|{ltr}"))
                else:
                    btns.append(types.InlineKeyboardButton("·", callback_data="noop"))
            markup.row(*btns)

        markup.add(types.InlineKeyboardButton("⬅️ Back to Popular", callback_data="page|0"))
        markup.add(types.InlineKeyboardButton("❌ Close", callback_data="close_menu"))
        text = "🔤 **All Services**\nTap a letter (or 🔢) to filter:"

    if msg_id:
        bot.edit_message_text(text, chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")


def show_services_by_letter(chat_id, letter, msg_id):
    """Show all services that start with *letter* (or digit if '#')."""
    services = get_all_services()
    if letter == '#':
        filtered = [s for s in services if not s[0].isalpha()]
    else:
        filtered = [s for s in services if s[0].upper() == letter]

    if not filtered:
        bot.answer_callback_query(msg_id, "No services for this letter.")
        return

    markup  = types.InlineKeyboardMarkup(row_width=2)
    buttons = [types.InlineKeyboardButton(s.capitalize(), callback_data=f"srv|{s}") for s in filtered]
    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton("⬅️ Back to Filter", callback_data="page|-1"))
    markup.add(types.InlineKeyboardButton("❌ Close", callback_data="close_menu"))

    label = "0–9" if letter == '#' else letter
    text  = f"📋 **Services — {label}** ({len(filtered)} found):"
    bot.edit_message_text(text, chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")

# ---------------- COUNTRY MENU ----------------
def show_countries(chat_id, service, page=0, msg_id=None):
    bot.send_chat_action(chat_id, 'typing')
    try:
        resp        = get_cached_prices(service)
        data_source = resp.get(service, {}) if service in resp else resp
        countries   = []
        for c_name, ops in data_source.items():
            if not isinstance(ops, dict): continue
            min_price, total_stock = float('inf'), 0
            for op, det in ops.items():
                if det['count'] > 0:
                    total_stock += det['count']
                    if det['cost'] < min_price: min_price = det['cost']
            if total_stock > 0:
                countries.append({'n': c_name, 'p': calculate_display_price(min_price, chat_id), 's': total_stock})
        countries.sort(key=lambda x: x['p'])
        if not countries:
            bot.send_message(chat_id, "❌ No stock available.")
            return

        PER_PAGE    = 20
        total_pages = max(1, (len(countries) + PER_PAGE - 1) // PER_PAGE)
        page        = max(0, min(page, total_pages - 1))
        start, end  = page * PER_PAGE, (page + 1) * PER_PAGE

        markup = types.InlineKeyboardMarkup(row_width=1)
        for c in countries[start:end]:
            flag = get_flag(c['n'])
            markup.add(types.InlineKeyboardButton(
                f"{flag} {c['n'].upper()} — from ${c['p']} ({c['s']})",
                callback_data=f"op|{c['n']}|{service}"
            ))
        nav = []
        if page > 0:           nav.append(types.InlineKeyboardButton("⬅️ Back",   callback_data=f"cnt_pg|{service}|{page-1}"))
        if end < len(countries): nav.append(types.InlineKeyboardButton("Next ➡️", callback_data=f"cnt_pg|{service}|{page+1}"))
        if nav: markup.add(*nav)
        markup.add(types.InlineKeyboardButton("⬅️ Back to Services", callback_data="page|0"))
        markup.add(types.InlineKeyboardButton("❌ Close", callback_data="close_menu"))

        text = f"🌍 **{service.upper()}** — Select Country (Page {page+1}/{total_pages}):"
        if msg_id:
            bot.edit_message_text(text, chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error loading countries: {e}")
        bot.send_message(chat_id, "❌ Error loading countries.")

# ---------------- OPERATOR MENU ----------------
def show_operators(chat_id, country, service, msg_id):
    try:
        resp      = get_cached_prices(service)
        data_ops  = resp.get(service, {}).get(country, {})
        valid_ops = sorted(
            [{'name': op, 'cost': det['cost'], 'count': det['count']} for op, det in data_ops.items() if det['count'] > 0],
            key=lambda x: x['cost']
        )
        flag   = get_flag(country)
        markup = types.InlineKeyboardMarkup(row_width=1)
        if valid_ops:
            markup.add(types.InlineKeyboardButton(
                f"🎲 Any Operator (Auto) — ${calculate_display_price(valid_ops[0]['cost'], chat_id)}",
                callback_data=f"buy|{country}|any|{service}"
            ))
            for op in valid_ops:
                markup.add(types.InlineKeyboardButton(
                    f"📶 {op['name'].upper()} — ${calculate_display_price(op['cost'], chat_id)} ({op['count']})",
                    callback_data=f"buy|{country}|{op['name']}|{service}"
                ))
        markup.add(types.InlineKeyboardButton("⬅️ Back to Countries", callback_data=f"cnt_pg|{service}|0"))
        markup.add(types.InlineKeyboardButton("❌ Close", callback_data="close_menu"))
        bot.edit_message_text(
            f"📶 **Operator for {flag} {country.upper()}:**\n_{service.upper()}_",
            chat_id, msg_id, reply_markup=markup, parse_mode="Markdown"
        )
    except:
        bot.send_message(chat_id, "❌ Error loading operators.")

# ---------------- CALLBACK HANDLER ----------------
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.message.chat.id
    data    = call.data.split('|')
    action  = data[0]

    if action == 'noop':
        bot.answer_callback_query(call.id)
        return

    if action == 'close_menu':
        try: bot.delete_message(user_id, call.message.message_id)
        except: pass
        bot.answer_callback_query(call.id)
        return

    if action == 'page':
        show_services(user_id, int(data[1]), call.message.message_id)

    elif action == 'alpha':
        # data[1] is letter or '#'
        show_services_by_letter(user_id, data[1], call.message.message_id)

    elif action == 'srv':
        show_countries(user_id, data[1], page=0, msg_id=call.message.message_id)

    elif action == 'cnt_pg':
        show_countries(user_id, data[1], page=int(data[2]), msg_id=call.message.message_id)

    elif action == 'op':
        show_operators(user_id, data[1], data[2], call.message.message_id)

    elif action == 'admin_download_csv' and user_id == ADMIN_ID:
        send_users_csv(user_id)

    # ──────────────────────── BUY ────────────────────────────────
    elif action == 'buy':
        country, operator, service = data[1], data[2], data[3]
        is_admin = (user_id == ADMIN_ID)
        try:
            p_data    = requests.get(f"{BASE_URL}/guest/prices?product={service}", headers=HEADERS).json()
            ops       = p_data.get(service, {}).get(country, {})
            real_cost = float('inf')
            if operator == 'any':
                for k, v in ops.items():
                    if v['count'] > 0 and v['cost'] < real_cost: real_cost = v['cost']
            else:
                if operator in ops and ops[operator]['count'] > 0: real_cost = ops[operator]['cost']

            if real_cost == float('inf'):
                bot.answer_callback_query(call.id, "❌ Stock unavailable.", show_alert=True)
                return

            final_cost = calculate_display_price(real_cost, user_id)

            # Non-admin: check wallet balance
            if not is_admin:
                user = get_user(user_id)
                if float(user.get('balance', 0)) < final_cost:
                    bot.answer_callback_query(call.id, "❌ Insufficient Balance!", show_alert=True)
                    return

            bot.edit_message_text("🔄 Processing your order...", user_id, call.message.message_id)
            buy_resp = requests.get(f"{BASE_URL}/user/buy/activation/{country}/{operator}/{service}", headers=HEADERS).json()

            if 'phone' in buy_resp:
                phone, oid = buy_resp['phone'], buy_resp['id']
                flag = get_flag(country)

                if is_admin:
                    # Admin charges from 5sim server balance directly — no local wallet touch
                    sms_cost  = real_cost
                    cost_line = f"💰 Cost: `${real_cost}` _(server)_"
                    save_order(user_id, oid, phone, country, service, real_cost, "PENDING")
                else:
                    update_balance(user_id, -final_cost)
                    sms_cost  = final_cost
                    cost_line = f"💰 Deducted: `${final_cost}`"
                    save_order(user_id, oid, phone, country, service, final_cost, "PENDING")

                msg = (
                    f"✅ **Order Successful!**\n\n"
                    f"📱 Phone: `{phone}`\n"
                    f"🌍 Country: {flag} {country.upper()}\n"
                    f"🔧 Service: **{service.upper()}**\n"
                    f"{cost_line}\n\n"
                    f"⏳ _Waiting for SMS..._\n"
                    f"_(If SMS is delayed, try a higher-priced operator for better quality.)_"
                )
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton(
                    "❌ Cancel Order",
                    callback_data=f"cancel|{oid}|{sms_cost}|{is_admin}"
                ))
                sent_msg = bot.send_message(user_id, msg, reply_markup=markup, parse_mode="Markdown")
                threading.Thread(
                    target=check_sms_thread,
                    args=(user_id, oid, sms_cost, sent_msg.message_id, phone, country, is_admin)
                ).start()
            else:
                bot.send_message(user_id, "❌ Purchase Failed. Try a different operator.")

        except Exception as e:
            logger.error(f"Buy Error: {e}")
            bot.send_message(user_id, "❌ Error during purchase.")

    # ──────────────────────── CANCEL ─────────────────────────────
    elif action == 'cancel':
        oid          = data[1]
        amount       = float(data[2])
        is_admin_ord = (len(data) > 3 and data[3] == 'True')
        resp = requests.get(f"{BASE_URL}/user/cancel/{oid}", headers=HEADERS).json()
        if resp.get('status') == 'CANCELED':
            update_order_status(oid, "CANCELED")
            try: bot.delete_message(user_id, call.message.message_id)
            except: pass
            if is_admin_ord:
                bot.send_message(user_id,
                    f"✅ **Order Cancelled**\n\n💰 `${amount}` refunded to server balance.",
                    parse_mode="Markdown")
            else:
                update_balance(user_id, amount)
                bot.send_message(user_id,
                    f"✅ **Order Cancelled**\n\n💰 `${amount}` has been refunded to your wallet.",
                    parse_mode="Markdown")
        else:
            bot.answer_callback_query(call.id, "⚠️ Cannot cancel — SMS may have been sent.", show_alert=True)

# ---------------- SMS POLLING THREAD ----------------
def check_sms_thread(user_id, order_id, cost, message_id, phone, country, is_admin=False):
    flag = get_flag(country)
    for _ in range(180):
        time.sleep(5)
        try:
            res    = requests.get(f"{BASE_URL}/user/check/{order_id}", headers=HEADERS).json()
            status = res.get('status')

            if status == 'RECEIVED':
                code     = res['sms'][0]['code']
                msg_text = res['sms'][0].get('text', '')
                update_order_status(order_id, "COMPLETED", sms_text=f"{code} - {msg_text}")
                try:
                    bot.edit_message_text(
                        f"✅ **Order Completed!**\n\n📱 Phone: `{phone}`\n"
                        f"🌍 Country: {flag} {country.upper()}\n"
                        f"💰 Cost: `${cost}`\n📩 **SMS Code Received.**",
                        user_id, message_id, reply_markup=None, parse_mode="Markdown"
                    )
                except: pass
                bot.send_message(user_id,
                    f"📩 **SMS RECEIVED!**\n\n🔑 Code: `{code}`\n📝 Msg: {msg_text}",
                    parse_mode="Markdown")
                return

            elif status == 'CANCELED':
                update_order_status(order_id, "CANCELED")
                if not is_admin: update_balance(user_id, cost)
                try:
                    refund_note = "refunded to server." if is_admin else "refunded to wallet."
                    bot.edit_message_text(
                        f"❌ **Order Cancelled**\n\n📱 Phone: `{phone}`\n"
                        f"🌍 {flag} {country.upper()}\n💰 `${cost}` {refund_note}",
                        user_id, message_id, reply_markup=None, parse_mode="Markdown"
                    )
                except: pass
                bot.send_message(user_id,
                    f"⚠️ **Order Cancelled by Server**\n\nPhone `{phone}` was cancelled.\n"
                    f"💰 `${cost}` {'refunded to server balance.' if is_admin else 'has been refunded to your wallet.'}",
                    parse_mode="Markdown")
                return

            elif status == 'TIMEOUT':
                update_order_status(order_id, "TIMEOUT")
                if not is_admin: update_balance(user_id, cost)
                try:
                    refund_note = "refunded to server." if is_admin else "refunded to wallet."
                    bot.edit_message_text(
                        f"⚠️ **Order Timed Out**\n\n📱 Phone: `{phone}`\n"
                        f"🌍 {flag} {country.upper()}\n💰 `${cost}` {refund_note}",
                        user_id, message_id, reply_markup=None, parse_mode="Markdown"
                    )
                except: pass
                bot.send_message(user_id,
                    f"⏰ **Order Timed Out**\n\nNo SMS was received for `{phone}`.\n"
                    f"💰 `${cost}` {'refunded to server balance.' if is_admin else 'has been automatically refunded.'}",
                    parse_mode="Markdown")
                return
        except: pass

    # 15-min exhausted → force cancel
    requests.get(f"{BASE_URL}/user/cancel/{order_id}", headers=HEADERS)
    if not is_admin: update_balance(user_id, cost)
    update_order_status(order_id, "TIMEOUT")
    try:
        refund_note = "refunded to server." if is_admin else "refunded to wallet."
        bot.edit_message_text(
            f"⚠️ **Order Timed Out**\n\n📱 Phone: `{phone}`\n"
            f"🌍 {flag} {country.upper()}\n💰 `${cost}` {refund_note}",
            user_id, message_id, reply_markup=None, parse_mode="Markdown"
        )
    except: pass
    bot.send_message(user_id,
        f"⏰ **Order Timed Out**\n\nNo SMS received. Order cancelled automatically.\n"
        f"💰 `${cost}` {'refunded to server balance.' if is_admin else 'has been refunded to your wallet.'}",
        parse_mode="Markdown")

# ---------------- FLASK SERVER ----------------
app = Flask(__name__)

@app.route('/')
def home(): return "Bot is Running Securely!"

def run_web():    app.run(host='0.0.0.0', port=PORT)
def keep_alive(): threading.Thread(target=run_web, daemon=True).start()

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
