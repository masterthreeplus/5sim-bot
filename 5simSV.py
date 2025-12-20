import telebot
import requests
import time
import threading
import os
import certifi
from flask import Flask
from telebot import types
from pymongo import MongoClient

# ---------------- CONFIGURATION ----------------
# Render Environment Variables
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8534849448:AAHc6uG2QYrrZI46-oNl1EKlZbMqTd6wDTM') 
API_KEY = os.environ.get('SIM_API_KEY', 'eyJhbGciOiJSUzUxMiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3OTc2NDYwMTIsImlhdCI6MTc2NjExMDAxMiwicmF5IjoiM2RlZDBiNTExNDc3ZjRkMzk4ZGM4NjA4MjYwMTM2NGQiLCJzdWIiOjM2NzEwNTF9.yo5lYq1tDiZklFRfR1_EeIT8bRVO6ZyO4DdsM-7AnNioVq7HVK28LPPjqEMPuk9Wm5qpPvUwhrJYR2hxyW1-1qMoCO3o633jsGTjzKElRd3cbBT4MizeCLyYaOvWgEh3-JnQBpZz-5WkKBVxKognLzsrilhQT6-fZzDMdfcNlrPRiOiXFdNGTE6ZGMk_0H2faINZ8U2mc6WZVLocB41EmuL3gp7Ra7jZ8PWfmD4-mnttLiRU9y0GxNslaQvnWBphvbN2g-Z_oMhyMPCrTx6DwD39Xnx1vyBc-UbQeAGGDCs50G-jNwSDPHLjss6yNQrryOQbKKMSE5bmBum4fWPEdg')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '5127528224'))
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb+srv://kntdb:dbKnt2Sim@5simdb.mtxe58u.mongodb.net/?appName=5simDB')

# Economics
RUB_TO_MMK = 57.38 
PROFIT_PERCENT = 25  # User gets +25% price markup

# 5sim API
BASE_URL = "https://5sim.net/v1"
HEADERS = {'Authorization': 'Bearer ' + API_KEY, 'Accept': 'application/json'}

# ---------------- DATABASE SETUP ----------------
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['5sim_reseller_db']
users_collection = db['users']

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
    users_collection.update_one({'_id': user_id}, {'$inc': {'balance': amount}})

def get_all_users_list():
    return list(users_collection.find())

# ---------------- FLASK SERVER ----------------
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Running!"
def run_web(): app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
def keep_alive(): threading.Thread(target=run_web).start()

bot = telebot.TeleBot(BOT_TOKEN)

POPULAR_SERVICES = ['telegram', 'whatsapp', 'facebook', 'google', 'tiktok', 'viber', 'line', 'instagram']

# ---------------- EXTENDED FLAG MAPPING ----------------
FLAG_MAP = {
    'afghanistan': '🇦🇫', 'albania': '🇦🇱', 'algeria': '🇩🇿', 'angola': '🇦🇴', 'argentina': '🇦🇷',
    'armenia': '🇦🇲', 'australia': '🇦🇺', 'austria': '🇦🇹', 'azerbaijan': '🇦🇿', 'bahrain': '🇧🇭',
    'bangladesh': '🇧🇩', 'belarus': '🇧🇾', 'belgium': '🇧🇪', 'benin': '🇧🇯', 'bolivia': '🇧🇴',
    'bosnia': '🇧🇦', 'brazil': '🇧🇷', 'bulgaria': '🇧🇬', 'burkinafaso': '🇧e🇫', 'burundi': '🇧🇮',
    'cambodia': '🇰🇭', 'cameroon': '🇨🇲', 'canada': '🇨e🇦', 'chad': '🇹🇩', 'chile': '🇨🇱',
    'china': '🇨🇳', 'colombia': '🇨🇴', 'congo': '🇨🇬', 'croatia': '🇭🇷', 'cyprus': '🇨🇾',
    'czech': '🇨🇿', 'denmark': '🇩🇰', 'djibouti': '🇩🇯', 'dominican': '🇩🇴', 'ecuador': '🇪🇨',
    'egypt': '🇪🇬', 'england': '🇬🇧', 'equatorialguinea': '🇬e🇶', 'estonia': '🇪🇪', 'ethiopia': '🇪🇹',
    'finland': '🇫🇮', 'france': '🇫🇷', 'gabon': '🇬🇦', 'gambia': '🇬🇲', 'georgia': '🇬🇪',
    'germany': '🇩🇪', 'ghana': '🇬🇭', 'greece': '🇬🇷', 'guatemala': '🇬🇹', 'guinea': '🇬🇳',
    'guineabissau': '🇬🇼', 'guyana': '🇬🇾', 'haiti': '🇭🇹', 'honduras': '🇭🇳', 'hongkong': '🇭🇰',
    'hungary': '🇭🇺', 'india': '🇮🇳', 'indonesia': '🇮🇩', 'iran': '🇮🇷', 'iraq': '🇮🇶',
    'ireland': '🇮🇪', 'israel': '🇮🇱', 'italy': '🇮🇹', 'ivorycoast': '🇨🇮', 'jamaica': '🇯🇲',
    'japan': '🇯🇵', 'jordan': '🇯🇴', 'kazakhstan': '🇰🇿', 'kenya': '🇰🇪', 'kuwait': '🇰🇼',
    'kyrgyzstan': '🇰🇬', 'laos': '🇱🇦', 'latvia': '🇱🇻', 'lebanon': '🇱🇧', 'lesotho': '🇱🇸',
    'liberia': '🇱🇷', 'libya': '🇱🇾', 'lithuania': '🇱🇹', 'luxembourg': '🇱🇺', 'macau': '🇲🇴',
    'madagascar': '🇲🇬', 'malawi': '🇲e🇼', 'malaysia': '🇲🇾', 'maldives': '🇲🇻', 'mali': '🇲🇱',
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
    # Remove spaces and convert to lower case to match keys (e.g., "Saudi Arabia" -> "saudiarabia")
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
        "`/info [ID]` - Check Specific User"
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
        
        if get_user(user_id):
            update_balance(user_id, amount)
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
        
        user = get_user(user_id)
        if user:
            update_balance(user_id, -amount)
            bot.reply_to(message, f"✂️ Deducted `{amount} Ks` from User `{user_id}`.", parse_mode="Markdown")
            try: bot.send_message(user_id, f"📉 Balance Deducted: `{amount} Ks`", parse_mode="Markdown")
            except: pass
        else:
            bot.reply_to(message, "❌ User ID not found.")
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
            bot.reply_to(message, f"👤 **User Info**\nID: `{uid}`\nName: {u.get('name')}\nBalance: `{u.get('balance')} Ks`", parse_mode="Markdown")
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
            
            msg_text += (
                f"\n\n⚙️ **Admin Dashboard:**\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🔌 **Server Balance:**\n"
                f"   🇷🇺 `{server_bal_rub} RUB`\n"
                f"   🇲🇲 `~{server_bal_mmk} MMK`\n\n"
                f"👥 Total User Funds: `{total_user_mmk} Ks`"
            )
        bot.reply_to(message, msg_text, parse_mode="Markdown")
        
    elif text == '💳 Top-up':
        msg = (
            f"💸 **To top-up your wallet, please contact Admin.**\n\n"
            f"👤 Admin: @Shake0098\n"
            f"🆔 Your ID: `{user_id}`\n\n"
            f"💰 **Payment Methods:**\n\n"
            f"🇲🇲 **Myanmar:**\n"
            f"• KBZ Pay\n"
            f"• Wave Pay\n"
            f"• AYA Pay\n"
            f"• UAB Pay\n\n"
            f"🌍 **Global:**\n"  # Fixed Emoji here
            f"• Binance\n"
            f"• Bybit\n"
            f"• Any Crypto (USDT)"
        )
        bot.reply_to(message, msg, parse_mode="Markdown")
        
    elif text == '🛒 Buy Number':
        show_services(user_id, 0)

# ---------------- SERVICE MENU ----------------

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

# ---------------- COUNTRY MENU ----------------

def show_countries(chat_id, service, page=0, msg_id=None):
    bot.send_chat_action(chat_id, 'typing')
    try:
        resp = requests.get(f"{BASE_URL}/guest/prices?product={service}", headers=HEADERS).json()
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
            bot.send_message(chat_id, "❌ No stock available.")
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
        if page > 0:
            nav_btns.append(types.InlineKeyboardButton("⬅️ Back", callback_data=f"cnt_pg|{service}|{page-1}"))
        if end < len(countries):
            nav_btns.append(types.InlineKeyboardButton("Next ➡️", callback_data=f"cnt_pg|{service}|{page+1}"))
        markup.add(*nav_btns)
        
        markup.add(types.InlineKeyboardButton("⬅️ Back to Services", callback_data="page|0"))
        
        text = f"🌍 **{service.upper()}** - Select Country (Page {page+1}/{total_pages}):"
        if msg_id: bot.edit_message_text(text, chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
        else: bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        
    except: bot.send_message(chat_id, "Error loading countries.")

# ---------------- OPERATOR MENU ----------------

def show_operators(chat_id, country, service, msg_id):
    try:
        resp = requests.get(f"{BASE_URL}/guest/prices?product={service}", headers=HEADERS).json()
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

# ---------------- BUY HANDLER ----------------

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
            if user['balance'] < final_mmk:
                bot.answer_callback_query(call.id, "❌ Insufficient Balance!", show_alert=True)
                return

            bot.edit_message_text("🔄 Processing...", user_id, call.message.message_id)
            buy_resp = requests.get(f"{BASE_URL}/user/buy/activation/{country}/{operator}/{service}", headers=HEADERS).json()
            
            if 'phone' in buy_resp:
                update_balance(user_id, -final_mmk)
                phone, oid = buy_resp['phone'], buy_resp['id']
                flag = get_flag(country)
                
                msg = (f"✅ **Order Successful!**\n"
                       f"📱 Phone: `{phone}`\n"
                       f"🌍 Country: {flag} {country.upper()}\n"
                       f"💰 Deducted: {final_mmk} Ks\n"
                       f"⏳ Waiting for SMS...\n\n"
                       f"_(If SMS is delayed or does not arrive, please try selecting a higher-priced operator for better quality.)_")
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("❌ Cancel Order", callback_data=f"cancel|{oid}|{final_mmk}"))
                bot.send_message(user_id, msg, reply_markup=markup, parse_mode="Markdown")
                threading.Thread(target=check_sms_thread, args=(user_id, oid, final_mmk)).start()
            else:
                bot.send_message(user_id, "❌ Purchase Failed. Try a different operator.")
        except Exception as e: bot.send_message(user_id, f"Error: {e}")

    elif action == 'cancel':
        oid, amount = data[1], int(data[2])
        resp = requests.get(f"{BASE_URL}/user/cancel/{oid}", headers=HEADERS).json()
        if resp.get('status') == 'CANCELED':
            update_balance(user_id, amount)
            bot.send_message(user_id, f"✅ Order Canceled.\n💰 `{amount} Ks` refunded.", parse_mode="Markdown")
        else:
            bot.send_message(user_id, "⚠️ Unable to cancel (SMS may be received).")

def check_sms_thread(user_id, order_id, cost_mmk):
    for i in range(180):
        time.sleep(5)
        try:
            res = requests.get(f"{BASE_URL}/user/check/{order_id}", headers=HEADERS).json()
            status = res.get('status')
            if status == 'RECEIVED':
                code = res['sms'][0]['code']
                msg = res['sms'][0].get('text', '')
                bot.send_message(user_id, f"📩 **SMS RECEIVED!**\n\nCode: `{code}`\nMsg: {msg}", parse_mode="Markdown")
                return
            elif status == 'CANCELED' or status == 'TIMEOUT': return
        except: pass
    
    requests.get(f"{BASE_URL}/user/cancel/{order_id}", headers=HEADERS)
    update_balance(user_id, cost_mmk)
    bot.send_message(user_id, f"⚠️ **Timeout**\nOrder cancelled automatically.\n💰 `{cost_mmk} Ks` refunded.\n💡 Suggestion: Try higher price operator.", parse_mode="Markdown")

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
