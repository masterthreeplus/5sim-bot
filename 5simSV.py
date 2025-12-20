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

# ---------------- FLASK SERVER ----------------
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Running!"
def run_web(): app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
def keep_alive(): threading.Thread(target=run_web).start()

bot = telebot.TeleBot(BOT_TOKEN)

# Popular Services (Quick Access)
POPULAR_SERVICES = ['telegram', 'whatsapp', 'facebook', 'google', 'tiktok', 'viber', 'line', 'instagram']

# ---------------- HELPER FUNCTIONS ----------------

# ဈေးနှုန်းတွက်ချက်မှု (Admin နဲ့ User ခွဲခြားခြင်း)
def calculate_display_price(rub_price, user_id):
    rub_price = float(rub_price)
    base_mmk = rub_price * RUB_TO_MMK
    
    if user_id == ADMIN_ID:
        # Admin sees raw price
        return int(base_mmk)
    else:
        # User sees price + 25%
        marked_up = base_mmk * (1 + PROFIT_PERCENT / 100)
        return int(marked_up)

def get_server_balance():
    try:
        resp = requests.get(f"{BASE_URL}/user/profile", headers=HEADERS).json()
        return resp.get('balance', 0)
    except:
        return 0

# ---------------- ADMIN COMMANDS ----------------

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID: return
    msg = (
        "👑 **Admin Panel:**\n\n"
        "`/add [ID] [Amount]` - Add Balance\n"
        "`/cut [ID] [Amount]` - Deduct Balance\n"
        "`/info [ID]` - Check User"
    )
    bot.reply_to(message, msg, parse_mode="Markdown")

@bot.message_handler(commands=['add'])
def add_money(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        _, user_id, amount = message.text.split()
        update_balance(int(user_id), int(amount))
        bot.reply_to(message, f"✅ Added `{amount} Ks` to User `{user_id}`.", parse_mode="Markdown")
        try: bot.send_message(int(user_id), f"💰 Deposit Received: `{amount} Ks`", parse_mode="Markdown")
        except: pass
    except: bot.reply_to(message, "Error. Use: `/add 123456 1000`")

@bot.message_handler(commands=['info'])
def user_info(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        uid = int(message.text.split()[1])
        u = get_user(uid)
        bot.reply_to(message, f"👤 {u['name']}\n💰 Bal: {u['balance']} Ks")
    except: pass

# ---------------- USER COMMANDS ----------------

@bot.message_handler(commands=['start'])
def start(message):
    register_user(message.from_user.id, message.from_user.first_name)
    # Removed Support Button
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add('🛒 Buy Number', '👤 My Profile', '💎 Top-up')
    
    bot.send_message(message.chat.id, f"Welcome {message.from_user.first_name}! 🌍\nSelect an option below:", reply_markup=markup)

@bot.message_handler(func=lambda msg: True)
def main_menu(message):
    user_id = message.from_user.id
    text = message.text
    
    if text == '👤 My Profile':
        user = get_user(user_id)
        bal = user['balance'] if user else 0
        
        msg_text = f"👤 **User Profile**\n🆔 ID: `{user_id}`\n💰 Wallet Balance: `{bal} Ks`"
        
        # If Admin, show Server Balance
        if user_id == ADMIN_ID:
            server_bal = get_server_balance()
            msg_text += f"\n\n⚙️ **Admin View:**\nSrvr Bal: `{server_bal} RUB`"
            
        bot.reply_to(message, msg_text, parse_mode="Markdown")
        
    elif text == '💎 Top-up':
        bot.reply_to(message, f"💸 To top-up your wallet, please contact Admin.\n\nYour ID: `{user_id}`", parse_mode="Markdown")
        
    elif text == '🛒 Buy Number':
        show_services(user_id, 0)

# ---------------- SERVICE MENU ----------------

def show_services(chat_id, page=0, msg_id=None):
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    if page == 0:
        # Popular Services
        buttons = [types.InlineKeyboardButton(f"📱 {s.capitalize()}", callback_data=f"srv|{s}") for s in POPULAR_SERVICES]
        markup.add(*buttons)
        markup.add(types.InlineKeyboardButton("See All Services ⤵️", callback_data="page|1"))
        text = "🔥 **Popular Services:**"
    else:
        # All Services (Fetched from API)
        try:
            resp = requests.get(f"{BASE_URL}/guest/products/any/any", headers=HEADERS).json()
            # Filter services with Stock > 0
            services = [k for k, v in resp.items() if v.get('Qty', 0) > 0]
            services.sort()
            
            # Pagination Logic (30 items per page)
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
        except:
            text = "Error fetching services."

    if msg_id: bot.edit_message_text(text, chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    else: bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")

# ---------------- COUNTRY MENU ----------------

def show_countries(chat_id, service, msg_id=None):
    bot.send_chat_action(chat_id, 'typing')
    try:
        resp = requests.get(f"{BASE_URL}/guest/prices?product={service}", headers=HEADERS).json()
        
        # Structure check: The API returns {"service_name": {"country": ...}} OR just {"country": ...} depending on endpoint
        # Using /guest/prices?product=x usually returns {"product": {"country":...}}
        data_source = resp.get(service, {}) if service in resp else resp
            
        countries = []
        for c_name, ops in data_source.items():
            if not isinstance(ops, dict): continue # Skip invalid data

            min_price_rub = float('inf')
            total_stock = 0
            
            for op, det in ops.items():
                qty = det.get('count', 0)
                cost = det.get('cost', 0)
                if qty > 0:
                    total_stock += qty
                    if cost < min_price_rub: min_price_rub = cost
            
            if total_stock > 0:
                # Calculate "From Price" based on user role
                display_price = calculate_display_price(min_price_rub, chat_id)
                countries.append({'n': c_name, 'p': display_price, 's': total_stock})
        
        countries.sort(key=lambda x: x['p']) # Sort by price
        
        if not countries:
            bot.send_message(chat_id, "❌ No stock available for this service.")
            return

        markup = types.InlineKeyboardMarkup(row_width=1)
        for c in countries[:20]: # Show top 20 cheapest
            btn_txt = f"🏳️ {c['n'].upper()} - from {c['p']} Ks ({c['s']})"
            markup.add(types.InlineKeyboardButton(btn_txt, callback_data=f"op|{c['n']}|{service}"))
        
        # Back Button added
        markup.add(types.InlineKeyboardButton("⬅️ Back to Services", callback_data="page|0"))
        
        text = f"🌍 **{service.upper()}** - Select Country:"
        if msg_id: bot.edit_message_text(text, chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
        else: bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
        
    except Exception as e:
        print(e)
        bot.send_message(chat_id, "Error loading countries.")

# ---------------- OPERATOR MENU ----------------

def show_operators(chat_id, country, service, msg_id):
    try:
        resp = requests.get(f"{BASE_URL}/guest/prices?product={service}", headers=HEADERS).json()
        data_source = resp.get(service, {}).get(country, {})
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        # Filter and sort operators
        valid_ops = []
        for op, det in data_source.items():
            if det['count'] > 0:
                valid_ops.append({'name': op, 'cost': det['cost'], 'count': det['count']})
        
        valid_ops.sort(key=lambda x: x['cost'])
        
        # 1. Any Operator (Auto) Option
        if valid_ops:
            best_price_rub = valid_ops[0]['cost']
            display_price = calculate_display_price(best_price_rub, chat_id)
            markup.add(types.InlineKeyboardButton(
                f"🎲 Any Operator (Auto) - {display_price} Ks", 
                callback_data=f"buy|{country}|any|{service}"
            ))

        # 2. Specific Operators
        for op in valid_ops:
            d_price = calculate_display_price(op['cost'], chat_id)
            btn_text = f"📶 {op['name'].upper()} - {d_price} Ks ({op['count']})"
            markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"buy|{country}|{op['name']}|{service}"))

        # Back Button to Country List
        markup.add(types.InlineKeyboardButton("⬅️ Back to Countries", callback_data=f"srv|{service}"))
        
        bot.edit_message_text(f"📶 Select Operator for **{country.upper()}**:", chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
    except:
        bot.send_message(chat_id, "Error loading operators.")

# ---------------- BUY HANDLER & SMS ----------------

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.message.chat.id
    data = call.data.split('|')
    action = data[0]
    
    if action == 'page': show_services(user_id, int(data[1]), call.message.message_id)
    elif action == 'srv': show_countries(user_id, data[1], call.message.message_id)
    elif action == 'op': show_operators(user_id, data[1], data[2], call.message.message_id)
    
    elif action == 'buy':
        country, operator, service = data[1], data[2], data[3]
        
        # Re-check Price & Stock
        try:
            p_data = requests.get(f"{BASE_URL}/guest/prices?product={service}", headers=HEADERS).json()
            ops = p_data.get(service, {}).get(country, {})
            
            real_rub_cost = float('inf')
            if operator == 'any':
                # Find min price among available
                for k, v in ops.items():
                    if v['count'] > 0 and v['cost'] < real_rub_cost: real_rub_cost = v['cost']
            else:
                if operator in ops and ops[operator]['count'] > 0:
                    real_rub_cost = ops[operator]['cost']
            
            if real_rub_cost == float('inf'):
                bot.answer_callback_query(call.id, "❌ Stock changed or unavailable.", show_alert=True)
                return

            # Calculate Final Deduct Amount
            final_mmk = calculate_display_price(real_rub_cost, user_id)
            
            # Check Balance
            user = get_user(user_id)
            if user['balance'] < final_mmk:
                bot.answer_callback_query(call.id, "❌ Insufficient Balance!", show_alert=True)
                return

            # Execute Buy
            bot.edit_message_text("🔄 Processing Purchase...", user_id, call.message.message_id)
            
            buy_resp = requests.get(f"{BASE_URL}/user/buy/activation/{country}/{operator}/{service}", headers=HEADERS).json()
            
            if 'phone' in buy_resp:
                # Deduct Money
                update_balance(user_id, -final_mmk)
                
                phone = buy_resp['phone']
                oid = buy_resp['id']
                
                # Create Order Message
                msg = (f"✅ **Order Successful!**\n"
                       f"📱 Phone: `{phone}`\n"
                       f"🌍 Country: {country.upper()}\n"
                       f"💰 Deducted: {final_mmk} Ks\n"
                       f"⏳ Waiting for SMS...")
                
                markup = types.InlineKeyboardMarkup()
                # User only sees Cancel (No Ban)
                markup.add(types.InlineKeyboardButton("❌ Cancel Order", callback_data=f"cancel|{oid}|{final_mmk}"))
                
                bot.send_message(user_id, msg, reply_markup=markup, parse_mode="Markdown")
                
                # Start SMS Thread
                threading.Thread(target=check_sms_thread, args=(user_id, oid, final_mmk)).start()
            else:
                bot.send_message(user_id, "❌ Purchase Failed. Try a different operator.")
                
        except Exception as e:
            bot.send_message(user_id, f"Error: {e}")

    elif action == 'cancel':
        oid, amount = data[1], int(data[2])
        resp = requests.get(f"{BASE_URL}/user/cancel/{oid}", headers=HEADERS).json()
        if resp.get('status') == 'CANCELED':
            update_balance(user_id, amount)
            bot.send_message(user_id, f"✅ Order Canceled.\n💰 `{amount} Ks` has been refunded to your wallet.", parse_mode="Markdown")
        else:
            bot.send_message(user_id, "⚠️ Unable to cancel (Maybe SMS arrived or expired).")

# ---------------- SMS LOGIC (ENGLISH & AUTO REFUND) ----------------

def check_sms_thread(user_id, order_id, cost_mmk):
    # Check for 15 minutes (180 checks * 5 sec)
    for i in range(180):
        time.sleep(5)
        try:
            res = requests.get(f"{BASE_URL}/user/check/{order_id}", headers=HEADERS).json()
            status = res.get('status')
            
            if status == 'RECEIVED':
                code = res['sms'][0]['code']
                msg_body = res['sms'][0].get('text', '')
                bot.send_message(user_id, f"📩 **SMS RECEIVED!**\n\nCode: `{code}`\n\nMsg: {msg_body}", parse_mode="Markdown")
                return # Job done
            
            elif status == 'CANCELED' or status == 'TIMEOUT':
                return # Handled elsewhere or finished
        except:
            pass
            
    # If 15 minutes pass with no SMS -> Auto Cancel
    requests.get(f"{BASE_URL}/user/cancel/{order_id}", headers=HEADERS)
    update_balance(user_id, cost_mmk)
    
    # English Timeout Message with Suggestion
    timeout_msg = (
        f"⚠️ **Order Timeout**\n\n"
        f"SMS code was not received within 15 minutes.\n"
        f"✅ The order has been cancelled automatically.\n"
        f"💰 `{cost_mmk} Ks` has been refunded to your balance.\n\n"
        f"💡 **Suggestion:** Please try selecting a different country or choose a higher-priced operator for better quality."
    )
    bot.send_message(user_id, timeout_msg, parse_mode="Markdown")

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
