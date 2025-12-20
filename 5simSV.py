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
# Render Environment Variables (Setup လုပ်ရပါမယ်)
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8534849448:AAHc6uG2QYrrZI46-oNl1EKlZbMqTd6wDTM') 
API_KEY = os.environ.get('SIM_API_KEY', 'eyJhbGciOiJSUzUxMiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3OTc2NDYwMTIsImlhdCI6MTc2NjExMDAxMiwicmF5IjoiM2RlZDBiNTExNDc3ZjRkMzk4ZGM4NjA4MjYwMTM2NGQiLCJzdWIiOjM2NzEwNTF9.yo5lYq1tDiZklFRfR1_EeIT8bRVO6ZyO4DdsM-7AnNioVq7HVK28LPPjqEMPuk9Wm5qpPvUwhrJYR2hxyW1-1qMoCO3o633jsGTjzKElRd3cbBT4MizeCLyYaOvWgEh3-JnQBpZz-5WkKBVxKognLzsrilhQT6-fZzDMdfcNlrPRiOiXFdNGTE6ZGMk_0H2faINZ8U2mc6WZVLocB41EmuL3gp7Ra7jZ8PWfmD4-mnttLiRU9y0GxNslaQvnWBphvbN2g-Z_oMhyMPCrTx6DwD39Xnx1vyBc-UbQeAGGDCs50G-jNwSDPHLjss6yNQrryOQbKKMSE5bmBum4fWPEdg')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '5127528224'))
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb+srv://kntdb:dbKnt2Sim@5simdb.mtxe58u.mongodb.net/?appName=5simDB')

# စီးပွားရေး ဆက်တင်များ
RUB_TO_MMK = 57.38  # 1 RUB = ? MMK (အရင်း)
PROFIT_PERCENT = 20 # အမြတ် ၂၀ ရာခိုင်နှုန်း တင်ရောင်းမယ်

# 5sim API
BASE_URL = "https://5sim.net/v1"
HEADERS = {'Authorization': 'Bearer ' + API_KEY, 'Accept': 'application/json'}

# ---------------- DATABASE SETUP (MongoDB) ----------------
# SSL certificate error မတက်အောင် certifi သုံးပါတယ်
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['5sim_reseller_db']
users_collection = db['users']

# Database Helpers
def get_user(user_id):
    return users_collection.find_one({'_id': user_id})

def register_user(user_id, first_name):
    if not get_user(user_id):
        users_collection.insert_one({
            '_id': user_id,
            'name': first_name,
            'balance': 0, # User ဖွင့်စမှာ ပိုက်ဆံ ၀ ကျပ်
            'joined_at': time.time()
        })

def update_balance(user_id, amount):
    # amount က အပေါင်းဆို ပိုက်ဆံတိုး၊ အနှုတ်ဆို ပိုက်ဆံလျော့
    users_collection.update_one({'_id': user_id}, {'$inc': {'balance': amount}})

# ---------------- FLASK SERVER ----------------
app = Flask(__name__)
@app.route('/')
def home(): return "Reseller Bot is Running!"
def run_web(): app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
def keep_alive(): threading.Thread(target=run_web).start()

bot = telebot.TeleBot(BOT_TOKEN)

# Popular Services List
POPULAR_SERVICES = ['telegram', 'whatsapp', 'facebook', 'google', 'tiktok', 'viber']

# ---------------- ADMIN COMMANDS (ပိုက်ဆံဖြည့်ရန်) ----------------

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID: return
    
    msg = (
        "👑 **Admin Panel Commands:**\n\n"
        "`/add [UserID] [Amount]` - ပိုက်ဆံဖြည့်ပေးရန်\n"
        "`/cut [UserID] [Amount]` - ပိုက်ဆံပြန်နုတ်ရန်\n"
        "`/info [UserID]` - User လက်ကျန်စစ်ရန်\n"
        "`/my_stats` - Bot အခြေအနေ ကြည့်ရန်"
    )
    bot.reply_to(message, msg, parse_mode="Markdown")

@bot.message_handler(commands=['add'])
def add_money(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        _, user_id, amount = message.text.split()
        user_id = int(user_id)
        amount = int(amount)
        
        update_balance(user_id, amount)
        bot.reply_to(message, f"✅ User `{user_id}` သို့ `{amount} Ks` ဖြည့်သွင်းပြီးပါပြီ။", parse_mode="Markdown")
        
        # User ဆီ Message လှမ်းပို့
        try:
            bot.send_message(user_id, f"💰 သင့်အကောင့်ထဲသို့ `{amount} Ks` ဖြည့်သွင်းလိုက်ပါပြီ။", parse_mode="Markdown")
        except: pass
            
    except:
        bot.reply_to(message, "⚠️ Format မှားနေသည်။\nUse: `/add 123456 1000`")

@bot.message_handler(commands=['info'])
def check_user_info(message):
    if message.from_user.id != ADMIN_ID: return
    try:
        user_id = int(message.text.split()[1])
        user = get_user(user_id)
        if user:
            bot.reply_to(message, f"👤 Name: {user['name']}\n💰 Balance: {user['balance']} Ks")
        else:
            bot.reply_to(message, "User not found.")
    except:
        bot.reply_to(message, "Use: `/info 123456`")

# ---------------- USER COMMANDS ----------------

@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    register_user(user_id, message.from_user.first_name)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add('🛒 Buy Number', '👤 My Profile', '💎 Top-up', '📞 Support')
    
    welcome_text = (f"မင်္ဂလာပါ {message.from_user.first_name}! 👋\n"
                    f"OTP ဝန်ဆောင်မှုမှ ကြိုဆိုပါတယ်။\n\n"
                    f"သင့် User ID: `{user_id}`\n"
                    f"(ငွေဖြည့်လိုပါက User ID ကို Admin ထံပေးပို့ပါ)")
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(func=lambda msg: True)
def main_menu(message):
    user_id = message.from_user.id
    text = message.text
    
    if text == '👤 My Profile':
        user = get_user(user_id)
        bal = user['balance'] if user else 0
        bot.reply_to(message, f"🆔 ID: `{user_id}`\n💰 လက်ကျန်ငွေ: `{bal} Ks`", parse_mode="Markdown")
        
    elif text == '💎 Top-up':
        bot.reply_to(message, f"💸 ငွေဖြည့်ရန်အတွက် Admin သို့ ဆက်သွယ်ပါ:\n\nContact: @YourAdminUsername\nYour ID: `{user_id}`", parse_mode="Markdown")
        
    elif text == '🛒 Buy Number':
        show_services(user_id, 0)

    elif text == '📞 Support':
        bot.reply_to(message, "Admin Contact: @YourAdminUsername")

# ---------------- ORDER LOGIC ----------------

def calculate_price(rub_price):
    # ဈေးနှုန်းတွက်နည်း: (Rub * Rate) + 20% Profit
    cost_mmk = float(rub_price) * RUB_TO_MMK
    final_price = cost_mmk + (cost_mmk * PROFIT_PERCENT / 100)
    return int(final_price)

def show_services(chat_id, page=0, msg_id=None):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    
    # Popular List (Page 0)
    if page == 0:
        for s in POPULAR_SERVICES:
            buttons.append(types.InlineKeyboardButton(f"📱 {s.capitalize()}", callback_data=f"srv|{s}"))
        markup.add(*buttons)
        markup.add(types.InlineKeyboardButton("See All ⤵️", callback_data="page|1"))
        text = "🔥 လူကြိုက်များသော ဝန်ဆောင်မှုများ:"
    else:
        # All Services Logic (Shortened for brevity)
        text = "🌐 All Services:"
        markup.add(types.InlineKeyboardButton("⬅️ Back", callback_data="page|0"))

    if msg_id:
        bot.edit_message_text(text, chat_id, msg_id, reply_markup=markup)
    else:
        bot.send_message(chat_id, text, reply_markup=markup)

def show_countries(chat_id, service, msg_id=None):
    try:
        resp = requests.get(f"{BASE_URL}/guest/prices?product={service}", headers=HEADERS).json()
        if service not in resp: 
            bot.send_message(chat_id, "Stock မရှိပါ")
            return

        countries = []
        for c_name, ops in resp[service].items():
            min_price = float('inf')
            stock = 0
            for op, det in ops.items():
                if det['count'] > 0:
                    stock += det['count']
                    if det['cost'] < min_price: min_price = det['cost']
            
            if stock > 0:
                # ဈေးနှုန်းကို User မြင်မယ့်ဈေး (အမြတ်ပေါင်းပြီး) ပြမယ်
                user_price = calculate_price(min_price)
                countries.append({'n': c_name, 'p': user_price, 'raw_p': min_price, 's': stock})
        
        countries.sort(key=lambda x: x['p'])
        
        markup = types.InlineKeyboardMarkup(row_width=1)
        for c in countries[:15]:
            # buy|country|service|RAW_PRICE
            # RAW_PRICE ကိုမှတ်ထားမှ ဝယ်တဲ့အခါ ပြန်ချိန်ကိုက်လို့ရမယ် (သို့) ဒီတိုင်း User Price ဖြတ်မယ်
            btn_txt = f"🏳️ {c['n'].upper()} - {c['p']} Ks"
            markup.add(types.InlineKeyboardButton(btn_txt, callback_data=f"op|{c['n']}|{service}"))
            
        bot.edit_message_text(f"🌍 **{service.upper()}** နိုင်ငံရွေးပါ:", chat_id, msg_id, reply_markup=markup, parse_mode="Markdown")
        
    except Exception as e:
        bot.send_message(chat_id, "Error fetching countries")

def show_operators(chat_id, country, service, msg_id):
    # Operator Logic (Similar to previous code but simplified)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🎲 Auto (Any Operator)", callback_data=f"buy|{country}|any|{service}"))
    bot.edit_message_text(f"📶 Choose Operator for {country}:", chat_id, msg_id, reply_markup=markup)

# ---------------- BUY HANDLER (CRITICAL: BALANCE CHECK) ----------------

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    user_id = call.message.chat.id
    data = call.data.split('|')
    action = data[0]
    
    if action == 'page': show_services(user_id, int(data[1]), call.message.message_id)
    elif action == 'srv': show_countries(user_id, data[1], call.message.message_id)
    elif action == 'op': show_operators(user_id, data[1], data[2], call.message.message_id)
    
    elif action == 'buy':
        country, operator, service = data[1], data[2], data[3]
        
        # 1. ဈေးနှုန်း ပြန်စစ်မယ် (API ကနေ လက်ရှိဈေးပြန်ဆွဲ)
        try:
            p_url = f"{BASE_URL}/guest/prices?product={service}"
            prices = requests.get(p_url, headers=HEADERS).json()[service][country]
            
            # Operator 'any' အတွက် အနည်းဆုံးဈေးရှာ
            real_cost_rub = float('inf')
            if operator == 'any':
                for op, det in prices.items():
                    if det['count'] > 0 and det['cost'] < real_cost_rub:
                        real_cost_rub = det['cost']
            else:
                real_cost_rub = prices[operator]['cost']
            
            # User ပေးရမည့်ဈေး (Profit ပေါင်းပြီး)
            user_pay_mmk = calculate_price(real_cost_rub)
            
            # 2. User ပိုက်ဆံ လောက်မလောက် စစ်မယ် (Database Check)
            user = get_user(user_id)
            if user['balance'] < user_pay_mmk:
                bot.answer_callback_query(call.id, "❌ လက်ကျန်ငွေ မလုံလောက်ပါ!", show_alert=True)
                return

            # 3. ပိုက်ဆံလောက်ရင် 5sim မှာ ဝယ်မယ်
            bot.edit_message_text("🔄 Buying...", user_id, call.message.message_id)
            
            buy_url = f"{BASE_URL}/user/buy/activation/{country}/{operator}/{service}"
            order = requests.get(buy_url, headers=HEADERS).json()
            
            if 'phone' in order:
                # 4. ဝယ်လို့ရပြီဆိုတာနဲ့ User ပိုက်ဆံ ဖြတ်မယ် (Deduct Balance)
                update_balance(user_id, -user_pay_mmk)
                
                oid = order['id']
                phone = order['phone']
                
                # Success Msg
                msg = (f"✅ **Success!**\n"
                       f"📱 Phone: `{phone}`\n"
                       f"💰 Cost: {user_pay_mmk} Ks\n"
                       f"⏳ SMS စောင့်နေပါ...")
                
                # Cancel Button
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("❌ Cancel (Refund)", callback_data=f"cancel|{oid}|{user_pay_mmk}"))
                
                bot.send_message(user_id, msg, reply_markup=markup, parse_mode="Markdown")
                threading.Thread(target=check_sms_thread, args=(user_id, oid, user_pay_mmk)).start()
                
            else:
                bot.send_message(user_id, "❌ Out of Stock.")
                
        except Exception as e:
            bot.send_message(user_id, f"Error: {e}")

    elif action == 'cancel':
        oid, amount = data[1], int(data[2])
        # Cancel API Call
        resp = requests.get(f"{BASE_URL}/user/cancel/{oid}", headers=HEADERS).json()
        if resp.get('status') == 'CANCELED':
            # 5. Cancel အောင်မြင်ရင် ပိုက်ဆံပြန်အမ်း (Refund)
            update_balance(user_id, amount)
            bot.send_message(user_id, f"✅ Order Canceled. {amount} Ks has been refunded.")
        else:
            bot.send_message(user_id, "⚠️ Cannot cancel (SMS received or expired).")

# ---------------- SMS CHECKER (Auto Refund on Timeout) ----------------

def check_sms_thread(user_id, order_id, cost_mmk):
    for i in range(180): # 15 mins
        time.sleep(5)
        try:
            data = requests.get(f"{BASE_URL}/user/check/{order_id}", headers=HEADERS).json()
            status = data.get('status')
            
            if status == 'RECEIVED':
                code = data['sms'][0]['code']
                bot.send_message(user_id, f"📩 **SMS CODE:** `{code}`", parse_mode="Markdown")
                return
            elif status == 'CANCELED':
                return # Already handled manually
        except: pass
    
    # Timeout -> Cancel & Refund
    requests.get(f"{BASE_URL}/user/cancel/{order_id}", headers=HEADERS)
    update_balance(user_id, cost_mmk)
    bot.send_message(user_id, f"⚠️ Timeout! Order canceled and {cost_mmk} Ks refunded.")

if __name__ == "__main__":
    keep_alive()
    bot.infinity_polling()
