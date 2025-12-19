
import telebot
import requests
import json
import time
import threading
import os
from flask import Flask, request # Flask ကို import လုပ်ပါ
from telebot import types

# ---------------- FLASK WEB SERVER (Render အတွက် အရေးကြီးသည်) ----------------
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_web_server():
    # Render က ပေးတဲ့ PORT ကို သုံးပါမယ်။ မရှိရင် 8080 ကို သုံးပါမယ်။
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

def keep_alive():
    t = threading.Thread(target=run_web_server)
    t.start()

# ---------------- CONFIGURATION ----------------
# Render Environment Variables ထဲမှာ ထည့်မယ့် Key တွေကို လှမ်းယူပါမယ်
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8534849448:AAHc6uG2QYrrZI46-oNl1EKlZbMqTd6wDTM') 
API_KEY = os.environ.get('SIM_API_KEY', 'eyJhbGciOiJSUzUxMiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3OTc2NDYwMTIsImlhdCI6MTc2NjExMDAxMiwicmF5IjoiM2RlZDBiNTExNDc3ZjRkMzk4ZGM4NjA4MjYwMTM2NGQiLCJzdWIiOjM2NzEwNTF9.yo5lYq1tDiZklFRfR1_EeIT8bRVO6ZyO4DdsM-7AnNioVq7HVK28LPPjqEMPuk9Wm5qpPvUwhrJYR2hxyW1-1qMoCO3o633jsGTjzKElRd3cbBT4MizeCLyYaOvWgEh3-JnQBpZz-5WkKBVxKognLzsrilhQT6-fZzDMdfcNlrPRiOiXFdNGTE6ZGMk_0H2faINZ8U2mc6WZVLocB41EmuL3gp7Ra7jZ8PWfmD4-mnttLiRU9y0GxNslaQvnWBphvbN2g-Z_oMhyMPCrTx6DwD39Xnx1vyBc-UbQeAGGDCs50G-jNwSDPHLjss6yNQrryOQbKKMSE5bmBum4fWPEdg')         
ADMIN_ID = int(os.environ.get('ADMIN_ID', '5127528224'))

# ငွေလဲနှုန်း (1 RUB = 57.38 MMK)
RUB_TO_MMK = 57.38 

# 5sim API Setup
BASE_URL = "https://5sim.net/v1"
HEADERS = {
    'Authorization': 'Bearer ' + API_KEY,
    'Accept': 'application/json'
}

bot = telebot.TeleBot(BOT_TOKEN)

POPULAR_SERVICES = [
    'telegram', 'whatsapp', 'facebook', 'google', 
    'tiktok', 'viber', 'line', 'instagram', 'twitter', 'imo'
]

# ---------------- HELPER FUNCTIONS ----------------

def to_mmk(rub_amount):
    mmk = int(rub_amount * RUB_TO_MMK)
    return f"{mmk:,} Ks"

def get_balance():
    try:
        response = requests.get(f"{BASE_URL}/user/profile", headers=HEADERS)
        data = response.json()
        if 'balance' in data:
            rub_bal = data['balance']
            mmk_bal = to_mmk(rub_bal)
            return (f"💰 **Balance Information**\n"
                    f"🇲🇲 MMK: `{mmk_bal}`\n"
                    f"🇷🇺 RUB: `{rub_bal}`\n"
                    f"⭐ Rating: {data['rating']}")
        return "⚠️ Balance ရှာမတွေ့ပါ။ API Key မှန်ကန်မှု ရှိမရှိ စစ်ပါ။"
    except Exception as e:
        return f"Error: {e}"

# ---------------- BOT COMMANDS ----------------

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ Access Denied")
        return

    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn_buy = types.KeyboardButton('🛒 Buy Number')
    btn_balance = types.KeyboardButton('💰 Check Balance')
    markup.add(btn_buy, btn_balance)
    
    bot.send_message(message.chat.id, "မင်္ဂလာပါ 🙏 Main Menu:", reply_markup=markup)

@bot.message_handler(func=lambda message: True)
def handle_menu(message):
    if message.from_user.id != ADMIN_ID: return

    if message.text == '💰 Check Balance':
        bot.reply_to(message, get_balance(), parse_mode="Markdown")

    elif message.text == '🛒 Buy Number':
        show_services_menu(message.chat.id, page=0)

# ---------------- MENU FUNCTIONS ----------------

def show_services_menu(chat_id, page=0, message_id=None):
    markup = types.InlineKeyboardMarkup(row_width=2)
    msg_text = ""

    if page == 0:
        msg_text = "🔥 **Popular Services**:"
        buttons = []
        for service in POPULAR_SERVICES:
            buttons.append(types.InlineKeyboardButton(
                f"📱 {service.capitalize()}", 
                callback_data=f"sel_serv|{service}"
            ))
        markup.add(*buttons)
        markup.add(types.InlineKeyboardButton("See All Services ⤵️", callback_data="page|1"))
    
    else:
        msg_text = f"🌐 **All Services** (Page {page}):"
        try:
            resp = requests.get(f"{BASE_URL}/guest/products/any/any", headers=HEADERS)
            data = resp.json()
            available_services = [k for k, v in data.items() if v.get('Qty', 0) > 0]
            available_services.sort()

            items_per_page = 20
            start = (page - 1) * items_per_page
            end = start + items_per_page
            current_batch = available_services[start:end]

            buttons = []
            for service in current_batch:
                buttons.append(types.InlineKeyboardButton(service, callback_data=f"sel_serv|{service}"))
            markup.add(*buttons)

            nav_btns = []
            if page > 1:
                nav_btns.append(types.InlineKeyboardButton("⬅️ Back", callback_data=f"page|{page-1}"))
            if end < len(available_services):
                nav_btns.append(types.InlineKeyboardButton("Next ➡️", callback_data=f"page|{page+1}"))
            markup.add(*nav_btns)

        except Exception as e:
            bot.send_message(chat_id, f"Error: {e}")
            return

    if message_id:
        bot.edit_message_text(msg_text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, msg_text, reply_markup=markup, parse_mode="Markdown")

def show_countries_for_service(chat_id, service, page=0, message_id=None):
    if message_id is None:
        bot.send_message(chat_id, f"🔍 Searching countries for **{service}**...", parse_mode="Markdown")

    try:
        url = f"{BASE_URL}/guest/prices?product={service}"
        resp = requests.get(url, headers=HEADERS)
        data = resp.json()

        country_list = []
        if service in data:
            countries_data = data[service]
            for country_name, operators in countries_data.items():
                total_stock = 0
                min_price = float('inf')
                best_op = None 
                for op_name, details in operators.items():
                    qty = details.get('count', 0)
                    price = details.get('cost', 0)
                    if qty > 0:
                        total_stock += qty
                        if price < min_price:
                            min_price = price
                            best_op = op_name
                if total_stock > 0 and min_price != float('inf'):
                    country_list.append({'name': country_name, 'price': min_price, 'stock': total_stock, 'op': best_op})

        country_list.sort(key=lambda x: x['price'])

        if not country_list:
            bot.send_message(chat_id, f"❌ '{service}' အတွက် Stock မရှိပါ။")
            return

        items_per_page = 15
        total_pages = (len(country_list) + items_per_page - 1) // items_per_page
        start = page * items_per_page
        end = start + items_per_page
        current_batch = country_list[start:end]

        markup = types.InlineKeyboardMarkup(row_width=1)
        for c in current_batch:
            mmk_price = to_mmk(c['price'])
            flag_text = f"🏳️ {c['name'].upper()} - {mmk_price} ({c['stock']})"
            cb_data = f"buy|{c['name']}|{c['op']}|{service}|{c['price']}"
            markup.add(types.InlineKeyboardButton(flag_text, callback_data=cb_data))

        nav_btns = []
        if page > 0:
            nav_btns.append(types.InlineKeyboardButton("⬅️ Back", callback_data=f"cnt_pg|{service}|{page-1}"))
        if end < len(country_list):
            nav_btns.append(types.InlineKeyboardButton("See More ⤵️", callback_data=f"cnt_pg|{service}|{page+1}"))
        markup.add(*nav_btns)
        
        msg_text = f"🌍 **{service.upper()}** Countries (Page {page+1}/{total_pages}):"
        if message_id:
            bot.edit_message_text(msg_text, chat_id, message_id, reply_markup=markup, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, msg_text, reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(chat_id, f"Error: {e}")

# ---------------- ACTION FUNCTIONS (CANCEL / BAN) ----------------

def cancel_order(chat_id, order_id):
    try:
        url = f"{BASE_URL}/user/cancel/{order_id}"
        resp = requests.get(url, headers=HEADERS)
        data = resp.json()
        if 'status' in data and data['status'] == 'CANCELED':
            bot.send_message(chat_id, f"✅ Order {order_id} has been **CANCELED**.", parse_mode="Markdown")
        else:
            bot.send_message(chat_id, f"⚠️ Cancel failed or already finished.")
    except Exception as e:
        bot.send_message(chat_id, f"Error: {e}")

def ban_order(chat_id, order_id):
    try:
        url = f"{BASE_URL}/user/ban/{order_id}"
        resp = requests.get(url, headers=HEADERS)
        data = resp.json()
        if 'status' in data and data['status'] == 'BANNED':
            bot.send_message(chat_id, f"🚫 Order {order_id} has been **BANNED**. Money refunded.", parse_mode="Markdown")
        else:
            bot.send_message(chat_id, f"⚠️ Ban failed.")
    except Exception as e:
        bot.send_message(chat_id, f"Error: {e}")

# ---------------- CALLBACK HANDLER ----------------

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id
    
    if call.data.startswith('page|'):
        page = int(call.data.split('|')[1])
        show_services_menu(chat_id, page=page, message_id=call.message.message_id)

    elif call.data.startswith('sel_serv|'):
        service = call.data.split('|')[1]
        show_countries_for_service(chat_id, service, page=0)

    elif call.data.startswith('cnt_pg|'):
        _, service, page = call.data.split('|')
        show_countries_for_service(chat_id, service, page=int(page), message_id=call.message.message_id)

    elif call.data.startswith('buy|'):
        _, country, operator, product, price_rub = call.data.split('|')
        
        bot.answer_callback_query(call.id, "Processing Order...")
        price_mmk = to_mmk(float(price_rub))
        
        # API Call to Buy
        try:
            buy_url = f"{BASE_URL}/user/buy/activation/{country}/{operator}/{product}"
            resp = requests.get(buy_url, headers=HEADERS)
            data = resp.json()

            if 'phone' in data:
                phone = data['phone']
                oid = data['id']
                
                # Success Message with CANCEL & BAN buttons
                markup = types.InlineKeyboardMarkup()
                btn_cancel = types.InlineKeyboardButton("❌ Cancel Order", callback_data=f"cancel|{oid}")
                btn_ban = types.InlineKeyboardButton("🚫 Ban Number", callback_data=f"ban|{oid}")
                markup.add(btn_cancel, btn_ban)

                msg = (f"✅ **SUCCESS!**\n"
                       f"📱 Phone: `{phone}`\n"
                       f"🌍 Country: {country}\n"
                       f"💰 Cost: {price_mmk}\n"
                       f"🆔 Order ID: {oid}\n\n"
                       f"⏳ Waiting for SMS... (Auto-refresh)")
                
                bot.send_message(chat_id, msg, reply_markup=markup, parse_mode="Markdown")
                
                threading.Thread(target=check_sms_thread, args=(chat_id, oid)).start()
            else:
                bot.send_message(chat_id, "❌ No numbers available (Stock Out/Low Balance).")

        except Exception as e:
            bot.send_message(chat_id, f"Connection Error: {e}")

    elif call.data.startswith('cancel|'):
        oid = call.data.split('|')[1]
        cancel_order(chat_id, oid)
    
    elif call.data.startswith('ban|'):
        oid = call.data.split('|')[1]
        ban_order(chat_id, oid)

# ---------------- THREADED SMS CHECKER ----------------

def check_sms_thread(chat_id, order_id):
    for i in range(24): 
        time.sleep(5)
        try:
            url = f"{BASE_URL}/user/check/{order_id}"
            resp = requests.get(url, headers=HEADERS)
            data = resp.json()
            status = data.get('status')

            if status == 'RECEIVED':
                sms_list = data.get('sms', [])
                if sms_list:
                    code = sms_list[0]['code']
                    full_text = sms_list[0].get('text', '')
                    bot.send_message(chat_id, f"📩 **SMS RECEIVED!**\n\nCode: `{code}`\n\nMsg: {full_text}", parse_mode="Markdown")
                    return 
            
            elif status == 'CANCELED' or status == 'TIMEOUT' or status == 'BANNED':
                return 

        except:
            pass
    bot.send_message(chat_id, f"⚠️ Order {order_id}: SMS မဝင်ပါ။ (Timeout)")

# ---------------- RUN (MODIFIED FOR RENDER) ----------------
if __name__ == "__main__":
    keep_alive() # Web Server ကို အရင် Run ပါမယ်
    print("🤖 Bot is running on Render...")
    bot.infinity_polling() # infinity_polling သုံးတာ ပိုငြိမ်ပါတယ်
     
