import json
import logging
import os
import re
import sys
import asyncio
import subprocess
import threading
import time
import datetime
import http.server
import socketserver
from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, MenuButtonWebApp
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Setup Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# CONFIGURATION
BOT_TOKEN = "7983069353:AAFe7d9h3Ap_5Km84RCKZepdKddKb8Ci0Ws"
PORT = 8000
ORDERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "orders.json")
PRODUCTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "products.json")
INVENTORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "inventory.json")
FINANCIALS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "financials.json")
USERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.json")
TANDOOR_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tandoor_config.json")
TANDOOR_BAKES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tandoor_bakes.json")
AUTHORIZED_USERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "authorized_users.json")
LANGUAGES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_languages.json")
ADMIN_ID = 5699488314

# User language storage helpers
user_languages_lock = threading.Lock()

def load_user_languages():
    with user_languages_lock:
        if not os.path.exists(LANGUAGES_FILE):
            return {}
        try:
            with open(LANGUAGES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading user_languages.json: {e}")
            return {}

def save_user_language(chat_id, lang):
    with user_languages_lock:
        langs = {}
        if os.path.exists(LANGUAGES_FILE):
            try:
                with open(LANGUAGES_FILE, "r", encoding="utf-8") as f:
                    langs = json.load(f)
            except Exception:
                pass
        langs[str(chat_id)] = lang
        try:
            with open(LANGUAGES_FILE, "w", encoding="utf-8") as f:
                json.dump(langs, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving user_languages.json: {e}")

MESSAGES = {
    "uz": {
        "welcome": "Assalomu alaykum, {username}! 🍽\n\n**POLVON somsa** rasmiy Telegram botiga xush kelibsiz!\n\nBuyurtma berish uchun pastdagi 🍽 **Menyu** tugmasini bosing yoki to'g'ridan-to'g'ri buyurtma bering.\n\n📞 Bog'lanish: +998 95 108 00 93\n📸 Instagram: @polvon_somsa_ku",
        "open_menu": "🍽 Menyuni ochish",
        "select_lang": "Iltimos, muloqot tilini tanlang:",
        "lang_selected": "O'zbek tili muvaffaqiyatli tanlandi! 🇺🇿\nEndi botni to'liq o'zbek tilida ishlatishingiz mumkin.",
        "menu_instruction": "Pastdagi 🍽 **Menyu** tugmasini bosib buyurtma berishingiz mumkin👇",
        "status_pending": "Kutilmoqda ⏳",
        "status_preparing": "Tayyorlanmoqda 👨‍🍳",
        "status_ready": "Tayyor! Buyurtmangizni olishingiz mumkin. 🍽😋",
        "status_completed": "Yakunlandi. Tashrifingiz uchun rahmat! 🤝",
        "status_ready_delivery": "Yo'lga chiqdi! Kuryer tez orada yetkazib beradi. 🚴‍♂️💨",
        "order_received": "📋 **Yangi buyurtma qabul qilindi!**\nBuyurtma ID: `#{order_id}`\n\n**Somsalar ro'yxati:**\n{items_text}\n\n🛒 **Buyurtma turi:** {fulfillment_text}\n💰 **Jami summa:** {total_price:,} SO'M\n\n🟢 **Status:** Kutilmoqda\n\nBuyurtmangiz tez orada tayyorlanadi. Yoqimli ishtaha! 😋",
        "status_changed": "🔔 **Buyurtmangiz statusi o'zgardi!**\n\nBuyurtma ID: `#{order_id}`\nYangi status: **{status_str}**"
    },
    "ru": {
        "welcome": "Здравствуйте, {username}! 🍽\n\nДобро пожаловать в официальный Telegram-бот **POLVON somsa**!\n\nДля совершения заказа нажмите кнопку 🍽 **Меню** ниже или сделайте заказ напрямую.\n\n📞 Контакты: +998 95 108 00 93\n📸 Instagram: @polvon_somsa_ku",
        "open_menu": "🍽 Открыть меню",
        "select_lang": "Пожалуйста, выберите язык общения:",
        "lang_selected": "Выбран русский язык! 🇷🇺\nТеперь вы можете использовать бот на русском языке.",
        "menu_instruction": "Вы можете сделать заказ, нажав на кнопку 🍽 **Меню** ниже 👇",
        "status_pending": "В ожидании ⏳",
        "status_preparing": "Готовится 👨‍🍳",
        "status_ready": "Готов! Можете забирать заказ. 🍽😋",
        "status_completed": "Завершен. Спасибо за визит! 🤝",
        "status_ready_delivery": "В пути! Курьер скоро доставит ваш заказ. 🚴‍♂️💨",
        "order_received": "📋 **Новый заказ принят!**\nID заказа: `#{order_id}`\n\n**Список самсы:**\n{items_text}\n\n🛒 **Тип заказа:** {fulfillment_text}\n💰 **Итоговая сумма:** {total_price:,} СУМ\n\n🟢 **Статус:** В ожидании\n\nВаш заказ скоро будет готов. Приятного аппетита! 😋",
        "status_changed": "🔔 **Статус вашего заказа изменился!**\n\nID заказа: `#{order_id}`\nНовый статус: **{status_str}**"
    }
}


# Global state for WebApp URL & dynamic thread callbacks
WEBAPP_URL = None
ssh_process = None
bot_app = None
bot_loop = None
orders_lock = threading.Lock()
products_lock = threading.Lock()
inventory_lock = threading.Lock()
financials_lock = threading.Lock()
users_lock = threading.Lock()
tandoor_config_lock = threading.Lock()
tandoor_bakes_lock = threading.Lock()
authorized_users_lock = threading.Lock()
user_states = {}

# 1. DATABASE ACCESS CONTROLLERS
def load_tandoor_config():
    with tandoor_config_lock:
        if not os.path.exists(TANDOOR_CONFIG_FILE):
            return {
                "somsa_names": {
                    "5000": "Kartoshkali somsa",
                    "8000": "Mol go'shtli o'rta somsa",
                    "10000": "Mol go'shtli katta somsa",
                    "15000": "Qo'y go'shtli o'rta somsa",
                    "20000": "Qo'y go'shtli katta somsa",
                    "25000": "Polvon somsa"
                },
                "google_sheets": {
                    "enabled": False,
                    "spreadsheet_id": "",
                    "credentials_file": "google_credentials.json",
                    "sheet_name": "Tandir Hisoboti"
                }
            }
        try:
            with open(TANDOOR_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading tandoor_config.json: {e}")
            return {}

def save_tandoor_config(config):
    with tandoor_config_lock:
        try:
            with open(TANDOOR_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving tandoor_config.json: {e}")

def load_tandoor_bakes():
    with tandoor_bakes_lock:
        if not os.path.exists(TANDOOR_BAKES_FILE):
            return []
        try:
            with open(TANDOOR_BAKES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading tandoor_bakes.json: {e}")
            return []

def save_tandoor_bakes(bakes):
    with tandoor_bakes_lock:
        try:
            with open(TANDOOR_BAKES_FILE, "w", encoding="utf-8") as f:
                json.dump(bakes, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving tandoor_bakes.json: {e}")

def load_authorized_users():
    with authorized_users_lock:
        if not os.path.exists(AUTHORIZED_USERS_FILE):
            return []
        try:
            with open(AUTHORIZED_USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading authorized_users.json: {e}")
            return []

def save_authorized_users(users):
    with authorized_users_lock:
        try:
            with open(AUTHORIZED_USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(users, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving authorized_users.json: {e}")

# 1. DATABASE ACCESS CONTROLLERS
def load_orders():
    with orders_lock:
        if not os.path.exists(ORDERS_FILE):
            return []
        try:
            with open(ORDERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading orders.json: {e}")
            return []

def save_order(order):
    with orders_lock:
        orders = []
        if os.path.exists(ORDERS_FILE):
            try:
                with open(ORDERS_FILE, "r", encoding="utf-8") as f:
                    orders = json.load(f)
            except Exception as e:
                logger.error(f"Error reading orders.json: {e}")
        
        # Check if this ID already exists, if so update it, else append
        exists = False
        for idx, o in enumerate(orders):
            if o.get("id") == order.get("id"):
                orders[idx] = order
                exists = True
                break
        if not exists:
            orders.append(order)
            
        try:
            with open(ORDERS_FILE, "w", encoding="utf-8") as f:
                json.dump(orders, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error writing orders.json: {e}")

def load_products():
    with products_lock:
        if not os.path.exists(PRODUCTS_FILE):
            return []
        try:
            with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading products.json: {e}")
            return []

def save_products(products):
    with products_lock:
        try:
            with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
                json.dump(products, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error writing products.json: {e}")

def load_inventory():
    with inventory_lock:
        if not os.path.exists(INVENTORY_FILE):
            return {"stock": {}, "logs": [], "waste_logs": []}
        try:
            with open(INVENTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading inventory.json: {e}")
            return {"stock": {}, "logs": [], "waste_logs": []}

def save_inventory(inventory):
    with inventory_lock:
        try:
            with open(INVENTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(inventory, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error writing inventory.json: {e}")

def load_financials():
    with financials_lock:
        if not os.path.exists(FINANCIALS_FILE):
            return {"transactions": [], "manual_expenses": []}
        try:
            with open(FINANCIALS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading financials.json: {e}")
            return {"transactions": [], "manual_expenses": []}

def save_financials(financials):
    with financials_lock:
        try:
            with open(FINANCIALS_FILE, "w", encoding="utf-8") as f:
                json.dump(financials, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error writing financials.json: {e}")

def load_users():
    with users_lock:
        if not os.path.exists(USERS_FILE):
            return []
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading users.json: {e}")
            return []

def deduct_inventory_for_order(order):
    inventory = load_inventory()
    stock = inventory.get("stock", {})
    logs = inventory.get("logs", [])
    
    recipes = {
        "qoy_katta_uchburchak": { "xamir": 0.08, "qiyme_qoy": 0.10 },
        "mol_katta_oval": { "xamir": 0.08, "qiyme_mol": 0.09 },
        "mol_orta_tomchi": { "xamir": 0.06, "qiyme_mol": 0.06 },
        "mol_standart_uchburchak": { "xamir": 0.05, "qiyme_mol": 0.05 },
        "kartoshka_tortburchak": { "xamir": 0.05, "qiyme_kartoshka": 0.07 }
    }
    
    items = order.get("items", [])
    deductions = []
    
    for item in items:
        prod_id = item.get("id")
        qty = item.get("quantity", 0)
        if prod_id in recipes:
            recipe = recipes[prod_id]
            for ingredient, amount_per_unit in recipe.items():
                total_needed = amount_per_unit * qty
                if ingredient in stock:
                    stock[ingredient]["qty"] = round(max(0.0, stock[ingredient]["qty"] - total_needed), 3)
                    deductions.append(f"{stock[ingredient]['name']}: -{total_needed:.3f} {stock[ingredient]['unit']}")
                else:
                    logger.warning(f"Ingredient {ingredient} not found in inventory stock!")
                    
    if deductions:
        log_entry = {
            "timestamp": int(time.time() * 1000),
            "action": "deduction",
            "description": f"Buyurtma #{order.get('id')} tayyorlashga olinganda sarflandi: " + ", ".join(deductions)
        }
        logs.append(log_entry)
        save_inventory(inventory)
        logger.info(f"Deducted inventory for order {order.get('id')}")

def record_order_income(order):
    financials = load_financials()
    transactions = financials.get("transactions", [])
    
    order_id = order.get("id")
    # Avoid duplicates
    for tx in transactions:
        if tx.get("type") == "income" and f"#{order_id}" in tx.get("description", ""):
            return
            
    order_type = order.get("orderType")
    table_num = order.get("tableNumber")
    fulfillment = 'Saboy' if order_type == 'saboy' else f'{table_num}-Stol'
    tx_entry = {
        "id": int(time.time() * 1000) + int(hash(str(order_id)) % 1000),
        "timestamp": int(time.time() * 1000),
        "type": "income",
        "amount": order.get("totalPrice", 0),
        "description": f"Buyurtma #{order_id} yopildi ({fulfillment})"
    }
    transactions.append(tx_entry)
    save_financials(financials)
    logger.info(f"Recorded income for order {order_id}")

def update_order_status_in_db(order_id, new_status):
    with orders_lock:
        orders = []
        updated_order = None
        if os.path.exists(ORDERS_FILE):
            try:
                with open(ORDERS_FILE, "r", encoding="utf-8") as f:
                    orders = json.load(f)
            except Exception as e:
                logger.error(f"Error reading orders.json: {e}")
        
        for order in orders:
            if order.get("id") == order_id:
                order["status"] = new_status
                
                # Check for inventory deduction state
                if new_status == "preparing" and not order.get("inventory_deducted"):
                    deduct_inventory_for_order(order)
                    order["inventory_deducted"] = True
                
                # Check for financial recording state
                if new_status == "completed" and not order.get("financial_recorded"):
                    record_order_income(order)
                    order["financial_recorded"] = True
                    
                updated_order = order
                break
        
        if updated_order:
            try:
                with open(ORDERS_FILE, "w", encoding="utf-8") as f:
                    json.dump(orders, f, ensure_ascii=False, indent=2)
            except Exception as e:
                logger.error(f"Error writing orders.json: {e}")
        return updated_order

# 2. WEB SERVER WITH REST API ENDPOINTS
class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        directory = os.path.dirname(os.path.abspath(__file__))
        super().__init__(*args, directory=directory, **kwargs)

    def do_GET(self):
        if self.path == "/api/orders":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            orders = load_orders()
            self.wfile.write(json.dumps(orders, ensure_ascii=False).encode("utf-8"))
        elif self.path == "/api/products":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            products = load_products()
            self.wfile.write(json.dumps(products, ensure_ascii=False).encode("utf-8"))
        elif self.path == "/api/inventory":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            inventory = load_inventory()
            self.wfile.write(json.dumps(inventory, ensure_ascii=False).encode("utf-8"))
        elif self.path == "/api/financials":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            financials = load_financials()
            self.wfile.write(json.dumps(financials, ensure_ascii=False).encode("utf-8"))
        elif self.path == "/api/users":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            users = load_users()
            self.wfile.write(json.dumps(users, ensure_ascii=False).encode("utf-8"))
        elif self.path == "/api/tandoors/config":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            config = load_tandoor_config()
            self.wfile.write(json.dumps(config, ensure_ascii=False).encode("utf-8"))
        elif self.path == "/api/tandoors/logs":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            logs = load_tandoor_bakes()
            self.wfile.write(json.dumps(logs, ensure_ascii=False).encode("utf-8"))
        else:
            # Fallback to standard static file server (for index.html, admin.html and assets)
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/orders/update":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                order_id = int(data.get("id"))
                new_status = data.get("status")
                
                # Update database
                updated_order = update_order_status_in_db(order_id, new_status)
                
                if updated_order:
                    # Notify user asynchronously through the asyncio loop
                    user_id = updated_order.get("user_id")
                    if user_id and bot_loop and bot_app:
                        asyncio.run_coroutine_threadsafe(
                            send_status_notification(bot_app, user_id, order_id, new_status),
                            bot_loop
                        )
                    
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "success", "order": updated_order}).encode("utf-8"))
                else:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Order not found"}).encode("utf-8"))
            except Exception as e:
                logger.error(f"Error updating order: {e}")
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        elif self.path == "/api/orders/new":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                order = json.loads(post_data.decode("utf-8"))
                
                # Save to database
                save_order(order)
                
                # Dynamic client notification
                user_id = order.get("user_id")
                order_id = order.get("id")
                items_desc = order.get("itemsDescription", "")
                total_price = order.get("totalPrice", 0)
                order_type = order.get("orderType")
                table_number = order.get("tableNumber")
                address = order.get("address", "")
                lat = order.get("latitude")
                lng = order.get("longitude")
                
                # Load client language
                user_langs = load_user_languages()
                lang = user_langs.get(str(user_id), "uz") if user_id else "uz"
                
                # Format fulfillment text in user's language
                if order_type == "saboy":
                    fulfillment_text = "Olib ketish (Saboy)" if lang == "uz" else "На вынос (С собой)"
                elif order_type == "dostavka":
                    fulfillment_text = f"Yetkazib berish (Dostavka) 🚚" if lang == "uz" else "Доставка 🚚"
                else:
                    fulfillment_text = f"Shu yerda ({table_number}-Stol)" if lang == "uz" else f"В заведении ({table_number}-Стол)"
                
                # Format client message
                invoice_items_text = f"• {items_desc}"
                if order_type == "dostavka" and address:
                    manzil_label = "Manzil" if lang == "uz" else "Адрес"
                    invoice_items_text += f"\n📍 **{manzil_label}:** {address}"
                
                msg_template = MESSAGES.get(lang, MESSAGES["uz"])["order_received"]
                invoice_text = msg_template.format(
                    order_id=order_id,
                    items_text=invoice_items_text,
                    fulfillment_text=fulfillment_text,
                    total_price=total_price
                )
                
                if user_id and user_id > 0 and bot_loop and bot_app:
                    asyncio.run_coroutine_threadsafe(
                        bot_app.bot.send_message(
                            chat_id=user_id,
                            text=invoice_text,
                            parse_mode="Markdown"
                        ),
                        bot_loop
                    )
                
                # Notify Admin of the new order
                if ADMIN_ID and bot_loop and bot_app:
                    admin_fulfillment_text = "Olib ketish (Saboy)"
                    if order_type == "dostavka":
                        admin_fulfillment_text = "Yetkazib berish (Dostavka) 🚚"
                    elif order_type == "dine-in":
                        admin_fulfillment_text = f"Shu yerda ({table_number}-Stol)"
                        
                    admin_msg = (
                        f"🔔 **Yangi buyurtma!**\n"
                        f"Buyurtma ID: `#{order_id}`\n"
                        f"Mijoz: {order.get('username', 'Mehmon')}\n\n"
                        f"**Somsalar:**\n• {items_desc}\n\n"
                        f"🛒 **Turi:** {admin_fulfillment_text}\n"
                        f"💰 **Jami:** {total_price:,} SO'M\n"
                    )
                    if order_type == "dostavka":
                        admin_msg += f"📍 **Manzil:** {address}\n"
                        if lat and lng:
                            admin_msg += f"🗺 **Geolokatsiya:** [Google Maps-da ko'rish](https://maps.google.com/?q={lat},{lng})\n"
                    
                    asyncio.run_coroutine_threadsafe(
                        bot_app.bot.send_message(
                            chat_id=ADMIN_ID,
                            text=admin_msg,
                            parse_mode="Markdown",
                            disable_web_page_preview=True
                        ),
                        bot_loop
                    )
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "order": order}).encode("utf-8"))
            except Exception as e:
                logger.error(f"Error creating order: {e}")
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        elif self.path == "/api/products/update":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                products = json.loads(post_data.decode("utf-8"))
                save_products(products)
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success"}).encode("utf-8"))
            except Exception as e:
                logger.error(f"Error updating products: {e}")
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        elif self.path == "/api/inventory/update":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                item_id = data.get("id")
                add_qty = float(data.get("qty", 0))
                price_per_unit = float(data.get("price_per_unit", 0))
                
                inventory = load_inventory()
                stock = inventory.get("stock", {})
                logs = inventory.get("logs", [])
                
                if item_id in stock:
                    stock[item_id]["qty"] = round(stock[item_id]["qty"] + add_qty, 3)
                    if price_per_unit > 0:
                        stock[item_id]["price_per_unit"] = price_per_unit
                    
                    logs.append({
                        "timestamp": int(time.time() * 1000),
                        "action": "purchase",
                        "description": f"Omborga yuk kiritildi: {stock[item_id]['name']} +{add_qty} {stock[item_id]['unit']}"
                    })
                    save_inventory(inventory)
                    
                    total_cost = int(add_qty * price_per_unit)
                    if total_cost > 0:
                        financials = load_financials()
                        financials.get("transactions", []).append({
                            "id": int(time.time() * 1000),
                            "timestamp": int(time.time() * 1000),
                            "type": "expense",
                            "amount": total_cost,
                            "description": f"Xom-ashyo xarid qilindi: {stock[item_id]['name']} ({add_qty} {stock[item_id]['unit']})"
                        })
                        save_financials(financials)
                        
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "success"}).encode("utf-8"))
                else:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": f"Item {item_id} not found"}).encode("utf-8"))
            except Exception as e:
                logger.error(f"Error updating inventory: {e}")
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        elif self.path == "/api/inventory/convert":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                output_id = data.get("output_id")
                output_qty = float(data.get("qty", 0))
                
                conversion_recipes = {
                    "xamir": {
                        "un": 0.65,
                        "suv": 0.35,
                        "tuz": 0.02
                    },
                    "qiyme_qoy": {
                        "gosht_qoy": 0.50,
                        "piyoz": 0.48,
                        "tuz": 0.02
                    },
                    "qiyme_mol": {
                        "gosht_mol": 0.50,
                        "piyoz": 0.48,
                        "tuz": 0.02
                    },
                    "qiyme_kartoshka": {
                        "kartoshka": 0.80,
                        "piyoz": 0.18,
                        "tuz": 0.02
                    }
                }
                
                if output_id not in conversion_recipes:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": f"Invalid semi-finished item: {output_id}"}).encode("utf-8"))
                    return
                
                inventory = load_inventory()
                stock = inventory.get("stock", {})
                logs = inventory.get("logs", [])
                
                recipe = conversion_recipes[output_id]
                
                insufficient = []
                for ing_id, ratio in recipe.items():
                    req_qty = ratio * output_qty
                    if ing_id not in stock or stock[ing_id]["qty"] < req_qty:
                        available = stock[ing_id]["qty"] if ing_id in stock else 0
                        insufficient.append(f"{stock[ing_id]['name'] if ing_id in stock else ing_id} (Kerak: {req_qty:.2f}, Mavjud: {available:.2f})")
                
                if insufficient:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Omborda yetarli xom-ashyo yo'q: " + ", ".join(insufficient)}).encode("utf-8"))
                    return
                
                deductions_desc = []
                for ing_id, ratio in recipe.items():
                    req_qty = ratio * output_qty
                    stock[ing_id]["qty"] = round(stock[ing_id]["qty"] - req_qty, 3)
                    deductions_desc.append(f"{stock[ing_id]['name']}: -{req_qty:.2f} {stock[ing_id]['unit']}")
                
                stock[output_id]["qty"] = round(stock[output_id]["qty"] + output_qty, 3)
                
                logs.append({
                    "timestamp": int(time.time() * 1000),
                    "action": "conversion",
                    "description": f"Tayyorlandi: {stock[output_id]['name']} +{output_qty} kg. Sarflangan xom-ashyolar: {', '.join(deductions_desc)}"
                })
                save_inventory(inventory)
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success"}).encode("utf-8"))
            except Exception as e:
                logger.error(f"Error in inventory conversion: {e}")
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        elif self.path == "/api/inventory/waste":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                item_id = data.get("id")
                waste_qty = float(data.get("qty", 0))
                reason = data.get("reason", "Muddati o'tgan / Yaroqsiz")
                
                inventory = load_inventory()
                stock = inventory.get("stock", {})
                waste_logs = inventory.get("waste_logs", [])
                logs = inventory.get("logs", [])
                
                if item_id in stock:
                    actual_waste = min(stock[item_id]["qty"], waste_qty)
                    stock[item_id]["qty"] = round(stock[item_id]["qty"] - actual_waste, 3)
                    
                    price_per = stock[item_id].get("price_per_unit", 0)
                    financial_loss = int(actual_waste * price_per)
                    
                    waste_entry = {
                        "timestamp": int(time.time() * 1000),
                        "id": item_id,
                        "name": stock[item_id]["name"],
                        "qty": actual_waste,
                        "unit": stock[item_id]["unit"],
                        "loss": financial_loss,
                        "reason": reason
                    }
                    waste_logs.append(waste_entry)
                    
                    logs.append({
                        "timestamp": int(time.time() * 1000),
                        "action": "waste",
                        "description": f"Yaroqsiz deb topildi: {stock[item_id]['name']} {actual_waste} {stock[item_id]['unit']}. Sabab: {reason}"
                    })
                    save_inventory(inventory)
                    
                    if financial_loss > 0:
                        financials = load_financials()
                        financials.get("transactions", []).append({
                            "id": int(time.time() * 1000),
                            "timestamp": int(time.time() * 1000),
                            "type": "expense",
                            "amount": financial_loss,
                            "description": f"Buzilgan mahsulot hisobidan zarar: {stock[item_id]['name']} ({actual_waste} {stock[item_id]['unit']})"
                        })
                        save_financials(financials)
                        
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "success", "loss": financial_loss}).encode("utf-8"))
                else:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": f"Item {item_id} not found"}).encode("utf-8"))
            except Exception as e:
                logger.error(f"Error logging inventory waste: {e}")
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        elif self.path == "/api/financials/expense":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                amount = int(data.get("amount", 0))
                description = data.get("description", "Boshqa xarajat")
                
                financials = load_financials()
                expense_entry = {
                    "id": int(time.time() * 1000),
                    "timestamp": int(time.time() * 1000),
                    "type": "expense",
                    "amount": amount,
                    "description": description
                }
                financials.get("transactions", []).append(expense_entry)
                save_financials(financials)
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success"}).encode("utf-8"))
            except Exception as e:
                logger.error(f"Error recording expense: {e}")
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

def run_web_server():
    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.TCPServer(("127.0.0.1", PORT), CustomHTTPRequestHandler) as httpd:
            logger.info(f"Local web server started at http://127.0.0.1:{PORT}")
            httpd.serve_forever()
    except Exception as e:
        logger.error(f"Error starting local web server: {e}")

# 3. LOCALHOST.RUN TUNNEL MANAGER & FILE OVERRIDE CHECKER
def check_webapp_url_file():
    global WEBAPP_URL
    url_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp_url.txt")
    last_file_content = None
    while True:
        if os.path.exists(url_file):
            try:
                with open(url_file, "r", encoding="utf-8") as f:
                    url = f.read().strip()
                    if url and url != last_file_content:
                        last_file_content = url
                        WEBAPP_URL = url
                        logger.info(f"✨ WebApp URL loaded/updated from webapp_url.txt: {WEBAPP_URL}")
                        
                        # Dynamically update default menu button globally for all users
                        if bot_app and bot_loop:
                            async def update_global_button():
                                try:
                                    await bot_app.bot.set_chat_menu_button(
                                        menu_button=MenuButtonWebApp(
                                            text="🍽 Menyu",
                                            web_app=WebAppInfo(url=url)
                                        )
                                    )
                                    logger.info("✨ Updated global default WebApp menu button URL on Telegram.")
                                except Exception as err:
                                    logger.error(f"Failed to update default menu button: {err}")
                            
                            asyncio.run_coroutine_threadsafe(update_global_button(), bot_loop)
            except Exception as e:
                logger.error(f"Error reading webapp_url.txt: {e}")
        time.sleep(2)

def run_tunnel():
    global WEBAPP_URL, ssh_process
    url_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp_url.txt")
    providers = [
        {"cmd": ["ssh", "-tt", "-o", "StrictHostKeyChecking=no", "-R", f"80:127.0.0.1:{PORT}", "nokey@localhost.run"], "name": "localhost.run"},
        {"cmd": ["ssh", "-tt", "-o", "StrictHostKeyChecking=no", "-R", f"80:127.0.0.1:{PORT}", "serveo.net"], "name": "serveo.net"}
    ]
    
    provider_idx = 0
    
    while True:
        provider = providers[provider_idx]
        logger.info(f"Starting tunnel ({provider['name']}): {' '.join(provider['cmd'])}")
        
        try:
            ssh_process = subprocess.Popen(
                provider['cmd'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            start_time = time.time()
            while True:
                line = ssh_process.stdout.readline()
                if not line:
                    break
                
                clean_line = line.strip()
                if clean_line and "welcome to localhost" not in clean_line.lower():
                    logger.info(f"[{provider['name']}] {clean_line}")
                
                match = re.search(r"([a-zA-Z0-9\-]+\.(lhr\.life|serveousercontent\.com))", line)
                if match:
                    domain = match.group(1)
                    new_webapp_url = f"https://{domain}/index.html"
                    if new_webapp_url != WEBAPP_URL:
                        # Only update if current WEBAPP_URL is not a custom override
                        is_custom = False
                        if WEBAPP_URL:
                            is_custom = not any(d in WEBAPP_URL for d in ["lhr.life", "serveo.net", "serveousercontent.com"])
                        
                        if not is_custom:
                            WEBAPP_URL = new_webapp_url
                            logger.info(f"🎉 Tunnel connected/updated successfully via {provider['name']}!")
                            logger.info(f"Mini App URL: {WEBAPP_URL}")
                            logger.info(f"Admin Panel URL: https://{domain}/admin.html")
                            
                            # Write back to webapp_url.txt to prevent check_webapp_url_file override
                            try:
                                with open(url_file, "w", encoding="utf-8") as f:
                                    f.write(new_webapp_url)
                            except Exception as e:
                                logger.error(f"Error writing to webapp_url.txt: {e}")
                        else:
                            logger.info(f"Automatic tunnel connected to {new_webapp_url}, but ignored because WEBAPP_URL is custom: {WEBAPP_URL}")
                        
                if not WEBAPP_URL and (time.time() - start_time > 20):
                    logger.warning(f"Tunnel {provider['name']} connection handshake timed out. Trying next provider...")
                    ssh_process.terminate()
                    try:
                        ssh_process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        ssh_process.kill()
                    break
                    
            logger.warning(f"Tunnel ({provider['name']}) process exited. Switching provider and retrying in 5 seconds...")
        except Exception as e:
            logger.error(f"Error executing SSH tunnel: {e}")
            
        provider_idx = (provider_idx + 1) % len(providers)
        time.sleep(5)

# --- TANDOOR ACCOUNTING AUTH AND WIZARD FLOWS ---
def is_user_authorized(chat_id, required_roles=None):
    """
    Checks if a user is authorized. ADMIN_ID is always authorized.
    """
    if chat_id == ADMIN_ID:
        return True, "admin", "Bakhrom Polvon (Admin)"
        
    auth_users = load_authorized_users()
    for user in auth_users:
        if user.get("chat_id") == chat_id:
            role = user.get("role")
            name = user.get("name", "Noma'lum")
            if required_roles is None or role in required_roles:
                return True, role, name
                
    return False, None, None

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
        
    chat_id = update.effective_chat.id
    args = context.args
    
    if not args:
        await update.message.reply_text(
            "Tizimga kirish uchun PIN-kodni kiriting. Masalan: `/login 1111`",
            parse_mode="Markdown"
        )
        return
        
    pin = args[0].strip()
    
    users = load_users()
    matched_user = None
    for u in users:
        if u.get("pin") == pin:
            matched_user = u
            break
            
    if not matched_user:
        await update.message.reply_text(
            "❌ Xato PIN-kod! Iltimos, qaytadan tekshirib kiriting."
        )
        return
        
    role = matched_user.get("role")
    name = matched_user.get("name")
    
    auth_users = load_authorized_users()
    for user in auth_users:
        if user.get("chat_id") == chat_id:
            user["role"] = role
            user["name"] = name
            user["pin"] = pin
            save_authorized_users(auth_users)
            await update.message.reply_text(
                f"✅ Tizimga qayta kirdingiz!\n\n**Xodim**: {name}\n**Lavozim**: {role.capitalize()}",
                parse_mode="Markdown"
            )
            await update_keyboard(update, context, chat_id, role)
            return
            
    new_auth = {
        "chat_id": chat_id,
        "name": name,
        "role": role,
        "pin": pin
    }
    auth_users.append(new_auth)
    save_authorized_users(auth_users)
    
    await update.message.reply_text(
        f"✅ Muvaffaqiyatli kirdingiz!\n\n**Xodim**: {name}\n**Lavozim**: {role.capitalize()}",
        parse_mode="Markdown"
    )
    await update_keyboard(update, context, chat_id, role)

async def update_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, role: str) -> None:
    if not WEBAPP_URL:
        await context.bot.send_message(chat_id, "Tizim yuklanmoqda... Bir necha soniyadan so'ng /start buyrug'ini yuboring.")
        return
        
    admin_url = WEBAPP_URL.replace("index.html", "admin.html")
    
    if role == "admin":
        reply_keyboard = [
            [
                KeyboardButton(text="⚙ Admin Panel", web_app=WebAppInfo(url=admin_url)),
                KeyboardButton(text="🍽 Menyu", web_app=WebAppInfo(url=WEBAPP_URL))
            ],
            [
                KeyboardButton(text="🗳 Tandir Hisoblagichi")
            ]
        ]
        reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
        await context.bot.send_message(
            chat_id,
            "Boshqaruv menyusi faollashtirildi 👇",
            reply_markup=reply_markup
        )
    elif role == "oshpaz":
        reply_keyboard = [
            [
                KeyboardButton(text="🗳 Tandir Hisoblagichi"),
                KeyboardButton(text="🍽 Menyu", web_app=WebAppInfo(url=WEBAPP_URL))
            ]
        ]
        reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
        await context.bot.send_message(
            chat_id,
            "Tandirchi boshqaruv menyusi faollashtirildi 👇",
            reply_markup=reply_markup
        )
    else:
        reply_keyboard = [
            [
                KeyboardButton(text="🍽 Menyu", web_app=WebAppInfo(url=WEBAPP_URL))
            ]
        ]
        reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
        await context.bot.send_message(
            chat_id,
            "Mijoz menyusi faollashtirildi 👇",
            reply_markup=reply_markup
        )

async def show_tandoor_main_menu(update, context, is_message=False, chat_id=None):
    if chat_id is None:
        chat_id = update.effective_chat.id
        
    text = (
        "🗳 **Tandir Hisoblagichi boshqaruv bo'limi**\n\n"
        "Quyidagi bo'limlardan birini tanlang:"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("🗳 Yangi Tandir", callback_data="t_new"),
            InlineKeyboardButton("📊 Hisobotlar", callback_data="t_stats")
        ],
        [
            InlineKeyboardButton("➕ Tandirlarni qo'shish", callback_data="t_add_menu"),
            InlineKeyboardButton("⚙️ Sozlamalar", callback_data="t_config_menu")
        ],
        [
            InlineKeyboardButton("❌ Chiqish", callback_data="t_close")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if is_message:
        await context.bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        query = update.callback_query
        if query:
            await query.answer()
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def show_tandoor_edit_board(update, context, chat_id, query=None):
    state_data = user_states.get(chat_id)
    if not state_data:
        return
        
    tandoor_name = state_data["tandoor_name"]
    counts = state_data["counts"]
    config = load_tandoor_config()
    somsa_names = config.get("somsa_names", {})
    
    total_count = 0
    total_revenue = 0
    
    lines = []
    for price_str, name in somsa_names.items():
        price = int(price_str)
        count = counts.get(price_str, 0)
        subtotal = count * price
        total_count += count
        total_revenue += subtotal
        lines.append(f"• **{name}** ({price:,} so'm): `{count}` ta ➡️ `{subtotal:,}` so'm")
        
    state_data["totals"] = {
        "count": total_count,
        "revenue": total_revenue
    }
    
    text = (
        f"🔥 **Tandir: {tandoor_name}**\n"
        f"📅 Sana: {state_data['date']}\n\n"
        f"**Somsalar soni va summasi:**\n" + "\n".join(lines) + f"\n\n"
        f"📦 **Jami somsa**: `{total_count}` ta\n"
        f"💰 **Jami summa**: `{total_revenue:,}` so'm\n\n"
        f"Kerakli turdagi somsani tanlab, sonini o'zgartiring:"
    )
    
    keyboard = []
    prices = list(somsa_names.keys())
    for i in range(0, len(prices), 2):
        row = []
        p1 = prices[i]
        n1 = somsa_names[p1].split()[0]
        row.append(InlineKeyboardButton(f"✏️ {n1} ({int(p1)//1000}k)", callback_data=f"t_edit_item:{p1}"))
        if i + 1 < len(prices):
            p2 = prices[i+1]
            n2 = somsa_names[p2].split()[0]
            row.append(InlineKeyboardButton(f"✏️ {n2} ({int(p2)//1000}k)", callback_data=f"t_edit_item:{p2}"))
        keyboard.append(row)
        
    keyboard.append([
        InlineKeyboardButton("✅ Saqlash (Tandirni yopish)", callback_data="t_save"),
        InlineKeyboardButton("❌ Bekor qilish", callback_data="t_cancel")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await context.bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode="Markdown")

async def show_count_adjustment_panel(query, chat_id, price):
    state_data = user_states.get(chat_id)
    if not state_data:
        return
        
    config = load_tandoor_config()
    somsa_names = config.get("somsa_names", {})
    name = somsa_names.get(price, f"{price} so'mlik somsa")
    current_count = state_data["counts"].get(price, 0)
    
    text = (
        f"✏️ **Somsani tahrirlash**:\n"
        f"Turi: **{name}** ({int(price):,} so'm)\n"
        f"Hozirgi soni: `{current_count}` ta\n\n"
        f"Quyidagi tezkor tugmalar orqali sonini o'zgartiring yoki chatga to'g'ridan-to'g'ri sonini yozib yuboring (masalan: `150`):"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("+10", callback_data=f"t_adj_item:{price}:10"),
            InlineKeyboardButton("+20", callback_data=f"t_adj_item:{price}:20"),
            InlineKeyboardButton("+50", callback_data=f"t_adj_item:{price}:50"),
            InlineKeyboardButton("+100", callback_data=f"t_adj_item:{price}:100")
        ],
        [
            InlineKeyboardButton("-10", callback_data=f"t_adj_item:{price}:-10"),
            InlineKeyboardButton("-20", callback_data=f"t_adj_item:{price}:-20"),
            InlineKeyboardButton("-50", callback_data=f"t_adj_item:{price}:-50"),
            InlineKeyboardButton("Tozalash (0)", callback_data=f"t_adj_item:{price}:0")
        ],
        [
            InlineKeyboardButton("🔙 Orqaga", callback_data="t_edit_board")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    state_data["state"] = "AWAITING_COUNT"
    state_data["editing_price"] = price
    
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def show_tandoor_addition_menu(update, context, chat_id, query=None):
    bakes = load_tandoor_bakes()
    today_str = datetime.date.today().isoformat()
    today_bakes = [b for b in bakes if b.get("date") == today_str]
    
    if not today_bakes:
        text = "❌ Bugun hali birorta ham tandir yopilmagan. Avval tandir yozuvlarini qo'shing."
        keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="t_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if query:
            await query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await context.bot.send_message(chat_id, text, reply_markup=reply_markup)
        return
        
    state_data = user_states.get(chat_id)
    if not state_data or "addition_selection" not in state_data:
        if not state_data:
            user_states[chat_id] = {}
            state_data = user_states[chat_id]
        state_data["addition_selection"] = [True] * len(today_bakes)
        state_data["addition_bakes"] = today_bakes
        
    selection = state_data["addition_selection"]
    if len(selection) != len(today_bakes):
        state_data["addition_selection"] = [True] * len(today_bakes)
        state_data["addition_bakes"] = today_bakes
        selection = state_data["addition_selection"]
        
    text = (
        "🧮 **Tandirlarni qo'shib hisoblash**\n\n"
        "Qo'shishmoqchi bo'lgan tandirlarni tanlang va **Hisoblash** tugmasini bosing:"
    )
    
    keyboard = []
    for idx, bake in enumerate(today_bakes):
        chk = "✅" if selection[idx] else "⬜️"
        t_name = bake.get("tandoor_name", f"Tandir #{idx+1}")
        t_count = bake.get("totals", {}).get("count", 0)
        t_rev = bake.get("totals", {}).get("revenue", 0)
        keyboard.append([
            InlineKeyboardButton(f"{chk} {t_name} ({t_count} ta, {t_rev:,} so'm)", callback_data=f"t_add_toggle:{idx}")
        ])
        
    keyboard.append([
        InlineKeyboardButton("🧮 Hisoblash", callback_data="t_add_calc")
    ])
    keyboard.append([
        InlineKeyboardButton("🔙 Orqaga", callback_data="t_menu")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    if query:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await context.bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode="Markdown")

async def show_tandoor_addition_result(query, chat_id):
    state_data = user_states.get(chat_id)
    if not state_data or "addition_selection" not in state_data:
        return
        
    selection = state_data["addition_selection"]
    bakes = state_data["addition_bakes"]
    
    config = load_tandoor_config()
    somsa_names = config.get("somsa_names", {})
    
    selected_bakes = [b for idx, b in enumerate(bakes) if selection[idx]]
    
    if not selected_bakes:
        await query.answer("Iltimos, kamida bitta tandirni belgilang!", show_alert=True)
        return
        
    grand_counts = {p: 0 for p in somsa_names.keys()}
    grand_count = 0
    grand_revenue = 0
    tandoor_names = []
    
    for bake in selected_bakes:
        tandoor_names.append(bake.get("tandoor_name", ""))
        counts = bake.get("counts", {})
        for price_str in grand_counts.keys():
            cnt = counts.get(price_str, 0)
            grand_counts[price_str] += cnt
            
        t_totals = bake.get("totals", {})
        grand_count += t_totals.get("count", 0)
        grand_revenue += t_totals.get("revenue", 0)
        
    tandoor_list_str = ", ".join(tandoor_names)
    
    lines = []
    for price_str, name in somsa_names.items():
        price = int(price_str)
        cnt = grand_counts[price_str]
        subtotal = cnt * price
        lines.append(f"• **{name}** ({price:,} so'm): `{cnt}` ta ➡️ `{subtotal:,}` so'm")
        
    text = (
        f"🧮 **Tandirlar yig'indisi hisoboti**\n\n"
        f"📋 **Qo'shilgan tandirlar**: {tandoor_list_str}\n"
        f"📅 Sana: {selected_bakes[0].get('date', '')}\n\n"
        f"**Somsalar bo'yicha jami:**\n" + "\n".join(lines) + f"\n\n"
        f"📦 **Jami somsa soni**: `{grand_count}` ta\n"
        f"💰 **Jami pul summasi**: `{grand_revenue:,}` so'm"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔙 Orqaga", callback_data="t_add_menu")],
        [InlineKeyboardButton("🏠 Asosiy menyu", callback_data="t_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

def get_tandoor_statistics(period):
    bakes = load_tandoor_bakes()
    today = datetime.date.today()
    filtered_bakes = []
    
    for bake in bakes:
        bake_date_str = bake.get("date")
        if not bake_date_str:
            continue
        try:
            bake_date = datetime.date.fromisoformat(bake_date_str)
        except ValueError:
            continue
            
        if period == "day":
            if bake_date == today:
                filtered_bakes.append(bake)
        elif period == "week":
            start_of_week = today - datetime.timedelta(days=today.weekday())
            if start_of_week <= bake_date <= today:
                filtered_bakes.append(bake)
        elif period == "month":
            if bake_date.year == today.year and bake_date.month == today.month:
                filtered_bakes.append(bake)
        elif period == "year":
            if bake_date.year == today.year:
                filtered_bakes.append(bake)
                
    config = load_tandoor_config()
    somsa_names = config.get("somsa_names", {})
    totals = {p: 0 for p in somsa_names.keys()}
    total_count = 0
    total_revenue = 0
    tandoors_count = len(filtered_bakes)
    
    for bake in filtered_bakes:
        counts = bake.get("counts", {})
        for p in totals.keys():
            totals[p] += counts.get(p, 0)
        total_count += bake.get("totals", {}).get("count", 0)
        total_revenue += bake.get("totals", {}).get("revenue", 0)
        
    return {
        "period": period,
        "tandoors_count": tandoors_count,
        "somsa_names": somsa_names,
        "totals": totals,
        "total_count": total_count,
        "total_revenue": total_revenue
    }

async def show_tandoor_stats_menu(query, chat_id):
    text = (
        "📊 **Tandir Hisobotlari bo'limi**\n\n"
        "Qaysi davr uchun hisobotlarni ko'rmoqchisiz?"
    )
    keyboard = [
        [
            InlineKeyboardButton("📅 Bugun", callback_data="t_stats_period:day"),
            InlineKeyboardButton("📅 Shu hafta", callback_data="t_stats_period:week")
        ],
        [
            InlineKeyboardButton("📅 Shu oy", callback_data="t_stats_period:month"),
            InlineKeyboardButton("📅 Shu yil", callback_data="t_stats_period:year")
        ],
        [
            InlineKeyboardButton("🔙 Orqaga", callback_data="t_menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def show_tandoor_stats_period(query, chat_id, period):
    stats = get_tandoor_statistics(period)
    
    period_names = {
        "day": "Bugungi",
        "week": "Haftalik (shu hafta)",
        "month": "Oylik (shu oy)",
        "year": "Yillik (shu yil)"
    }
    
    p_name = period_names.get(period, period)
    somsa_names = stats["somsa_names"]
    totals = stats["totals"]
    
    lines = []
    for price_str, name in somsa_names.items():
        price = int(price_str)
        cnt = totals.get(price_str, 0)
        subtotal = cnt * price
        lines.append(f"• **{name}** ({price:,} so'm): `{cnt}` ta ➡️ `{subtotal:,}` so'm")
        
    text = (
        f"📊 **{p_name} Tandir Yig'indisi Hisoboti**\n\n"
        f"🔥 **Jami yopilgan tandirlar**: `{stats['tandoors_count']}` ta\n\n"
        f"**Somsalar bo'yicha jami:**\n" + "\n".join(lines) + f"\n\n"
        f"📦 **Jami somsa soni**: `{stats['total_count']}` ta\n"
        f"💰 **Jami pul summasi**: `{stats['total_revenue']:,}` so'm"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔙 Orqaga", callback_data="t_stats")],
        [InlineKeyboardButton("🏠 Asosiy menyu", callback_data="t_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def show_config_main_menu(query, chat_id):
    text = (
        "⚙️ **Tandir Hisoblagich Sozlamalari**\n\n"
        "Quyidagi sozlamalardan birini tanlang:"
    )
    keyboard = [
        [InlineKeyboardButton("✏️ Somsa nomlarini tahrirlash", callback_data="t_config_somsa")],
        [InlineKeyboardButton("📊 Google Sheets Integratsiyasi", callback_data="t_config_gs")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="t_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def show_config_somsa_menu(update, context, chat_id, is_message=False):
    config = load_tandoor_config()
    somsa_names = config.get("somsa_names", {})
    
    text = (
        "✏️ **Somsa nomlarini o'zgartirish**\n\n"
        "Nomini o'zgartirmoqchi bo'lgan somsa narxini tanlang:"
    )
    
    keyboard = []
    prices = list(somsa_names.keys())
    for i in range(0, len(prices), 2):
        row = []
        p1 = prices[i]
        row.append(InlineKeyboardButton(f"{int(p1):,} so'm", callback_data=f"t_config_somsa_select:{p1}"))
        if i + 1 < len(prices):
            p2 = prices[i+1]
            row.append(InlineKeyboardButton(f"{int(p2):,} so'm", callback_data=f"t_config_somsa_select:{p2}"))
        keyboard.append(row)
        
    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="t_config_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if is_message:
        await context.bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        query = update.callback_query
        if query:
            await query.answer()
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def show_gs_config_menu(update, context, chat_id, is_message=False):
    config = load_tandoor_config()
    gs_config = config.get("google_sheets", {})
    
    status_str = "🟢 Yoqilgan" if gs_config.get("enabled", False) else "🔴 O'chirilgan"
    sheet_id = gs_config.get("spreadsheet_id", "Kiritilmagan")
    sheet_name = gs_config.get("sheet_name", "Tandir Hisoboti")
    creds_file = gs_config.get("credentials_file", "google_credentials.json")
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    creds_exist = os.path.exists(os.path.join(base_dir, creds_file))
    creds_status = "✅ Mavjud" if creds_exist else "❌ topilmadi (google_credentials.json faylini bot papkasiga yuklang)"
    
    text = (
        f"📊 **Google Sheets Integratsiyasi Sozlamalari**\n\n"
        f"Statistika va yopilgan tandirlar Google Sheets jadvaliga sinxronizatsiya qilinishi mumkin.\n\n"
        f"• **Holati**: {status_str}\n"
        f"• **Spreadsheet ID**: `{sheet_id}`\n"
        f"• **Varaq nomi**: `{sheet_name}`\n"
        f"• **Kalit fayl (Credentials status)**: {creds_status}\n\n"
        f"Sinxronizatsiyani yoqishdan oldin spreadsheet ID ni kiriting va credentials.json faylini joylashtiring."
    )
    
    toggle_text = "🔴 O'chirish" if gs_config.get("enabled", False) else "🟢 Yoqish"
    keyboard = [
        [InlineKeyboardButton(toggle_text, callback_data="t_config_gs_toggle")],
        [InlineKeyboardButton("✏️ Spreadsheet ID kiritish", callback_data="t_config_gs_set_id")],
        [InlineKeyboardButton("✏️ Varaq nomini kiritish", callback_data="t_config_gs_set_name")],
        [InlineKeyboardButton("🔄 Barcha yozuvlarni yuklash", callback_data="t_config_gs_sync")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="t_config_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if is_message:
        await context.bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        query = update.callback_query
        if query:
            await query.answer()
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def handle_tandoor_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
        
    chat_id = update.effective_chat.id
    data = query.data
    logger.info(f"📞 Callback query received: chat_id={chat_id}, data={data}")
    
    if data.startswith("lang:"):
        if not WEBAPP_URL:
            await query.answer("⏳ Tizim yuklanmoqda, iltimos 5 soniyadan so'ng qayta urinib ko'ring... / Система загружается, пожалуйста, попробуйте еще раз через 5 секунд...", show_alert=True)
            return
        await query.answer()
        selected_lang = data.split(":")[1]
        save_user_language(chat_id, selected_lang)
        
        msg_template = MESSAGES.get(selected_lang, MESSAGES["uz"])
        await query.edit_message_text(
            text=msg_template["lang_selected"],
            parse_mode="Markdown"
        )
        
        username = update.effective_user.first_name if update.effective_user else "Mehmon"
        welcome_text = msg_template["welcome"].format(username=username)
        
        inline_keyboard = [[InlineKeyboardButton(text=msg_template["open_menu"], web_app=WebAppInfo(url=WEBAPP_URL))]]
        inline_markup = InlineKeyboardMarkup(inline_keyboard)

        reply_keyboard = [[KeyboardButton(text=msg_template["open_menu"].split()[-1], web_app=WebAppInfo(url=WEBAPP_URL))]]
        reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)

        try:
            await context.bot.set_chat_menu_button(
                chat_id=chat_id,
                menu_button=None
            )
        except Exception as e:
            logger.error(f"Error resetting client chat menu button: {e}")

        await context.bot.send_message(
            chat_id=chat_id,
            text=welcome_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=msg_template["menu_instruction"],
            reply_markup=inline_markup,
            parse_mode="Markdown"
        )
        return
        
    if data != "t_close":
        is_auth, role, name = is_user_authorized(chat_id)
        if not is_auth:
            await query.answer("⚠️ Kechirasiz, sizda kirish ruxsati yo'q. Avval /login command orqali kiring.", show_alert=True)
            return
            
    if data == "t_menu":
        await show_tandoor_main_menu(update, context)
        
    elif data == "t_close":
        await query.answer()
        await query.edit_message_text("Tandir Hisoblagich bo'limi yopildi. Ishingizda rivoj tilaymiz!")
        
    elif data == "t_new":
        await query.answer()
        text = "Qaysi tandir yopilmoqda? Tanlang yoki pastga yozib yuboring (masalan: `Tandir 4`):"
        keyboard = [
            [
                InlineKeyboardButton("Tandir 1", callback_data="t_sel_name:Tandir 1"),
                InlineKeyboardButton("Tandir 2", callback_data="t_sel_name:Tandir 2")
            ],
            [
                InlineKeyboardButton("Tandir 3", callback_data="t_sel_name:Tandir 3"),
                InlineKeyboardButton("Boshqa ✏️", callback_data="t_sel_custom")
            ],
            [
                InlineKeyboardButton("🔙 Bekor qilish", callback_data="t_menu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        user_states[chat_id] = {
            "state": "SELECT_TANDIR",
            "tandoor_name": None,
            "counts": {
                "5000": 0,
                "8000": 0,
                "10000": 0,
                "15000": 0,
                "20000": 0,
                "25000": 0
            },
            "date": datetime.date.today().isoformat(),
            "timestamp": int(time.time() * 1000)
        }
        await query.edit_message_text(text, reply_markup=reply_markup)
        
    elif data.startswith("t_sel_name:"):
        await query.answer()
        t_name = data.split(":", 1)[1]
        user_states[chat_id]["tandoor_name"] = t_name
        user_states[chat_id]["state"] = "EDITING_TANDIR"
        await show_tandoor_edit_board(update, context, chat_id, query)
        
    elif data == "t_sel_custom":
        await query.answer()
        user_states[chat_id]["state"] = "AWAITING_CUSTOM_NAME"
        await query.edit_message_text("Tandir nomini kiriting (masalan: `Tandir #4`):")
        
    elif data == "t_edit_board":
        await query.answer()
        user_states[chat_id]["state"] = "EDITING_TANDIR"
        user_states[chat_id]["editing_price"] = None
        await show_tandoor_edit_board(update, context, chat_id, query)
        
    elif data.startswith("t_edit_item:"):
        await query.answer()
        price = data.split(":", 1)[1]
        await show_count_adjustment_panel(query, chat_id, price)
        
    elif data.startswith("t_adj_item:"):
        parts = data.split(":")
        price = parts[1]
        delta = int(parts[2])
        
        state_data = user_states.get(chat_id)
        if state_data:
            if delta == 0:
                state_data["counts"][price] = 0
            else:
                curr = state_data["counts"].get(price, 0)
                state_data["counts"][price] = max(0, curr + delta)
                
            await query.answer("Miqdor o'zgardi")
            await show_count_adjustment_panel(query, chat_id, price)
            
    elif data == "t_save":
        state_data = user_states.get(chat_id)
        if not state_data or state_data.get("state") != "EDITING_TANDIR":
            await query.answer("Xatolik! Yozish jarayoni faol emas.", show_alert=True)
            return
            
        await query.answer()
        bakes = load_tandoor_bakes()
        
        is_auth, role, name = is_user_authorized(chat_id)
        state_data["creator_name"] = name
        state_data["creator_id"] = chat_id
        
        bakes.append(state_data)
        save_tandoor_bakes(bakes)
        
        user_states[chat_id] = None
        
        success_text = (
            f"✅ **Tandir yozuvi saqlandi!**\n\n"
            f"• Tandir: **{state_data['tandoor_name']}**\n"
            f"• Jami somsalar: `{state_data['totals']['count']}` ta\n"
            f"• Jami summa: `{state_data['totals']['revenue']:,}` so'm\n"
            f"• Kiritdi: **{name}**\n\n"
        )
        
        config = load_tandoor_config()
        if config.get("google_sheets", {}).get("enabled", False):
            success_text += "⏳ Google Sheets varag'iga yuklanmoqda..."
            await query.edit_message_text(success_text, parse_mode="Markdown")
            
            def run_sync():
                from google_sheets_client import sync_tandoor_to_sheets
                somsa_names = config.get("somsa_names", {})
                success, msg = sync_tandoor_to_sheets(config, state_data, somsa_names)
                if success:
                    asyncio.run_coroutine_threadsafe(
                        context.bot.send_message(chat_id, "✅ Google Sheets-ga yozildi!"),
                        bot_loop
                    )
                else:
                    asyncio.run_coroutine_threadsafe(
                        context.bot.send_message(chat_id, f"⚠️ Google Sheets xatosi: {msg}"),
                        bot_loop
                    )
            threading.Thread(target=run_sync, daemon=True).start()
        else:
            success_text += "ℹ️ Google Sheets sinxronizatsiyasi o'chirilgan."
            await query.edit_message_text(success_text, parse_mode="Markdown")
            
        await show_tandoor_main_menu(update, context, is_message=True)
        
    elif data == "t_cancel":
        await query.answer("Bekor qilindi")
        user_states[chat_id] = None
        await show_tandoor_main_menu(update, context)
        
    elif data == "t_stats":
        await query.answer()
        await show_tandoor_stats_menu(query, chat_id)
        
    elif data.startswith("t_stats_period:"):
        await query.answer()
        period = data.split(":", 1)[1]
        await show_tandoor_stats_period(query, chat_id, period)
        
    elif data == "t_add_menu":
        await query.answer()
        if chat_id in user_states:
            user_states[chat_id] = None
        await show_tandoor_addition_menu(update, context, chat_id, query)
        
    elif data.startswith("t_add_toggle:"):
        await query.answer()
        idx = int(data.split(":", 1)[1])
        state_data = user_states.get(chat_id)
        if state_data and "addition_selection" in state_data:
            state_data["addition_selection"][idx] = not state_data["addition_selection"][idx]
        await show_tandoor_addition_menu(update, context, chat_id, query)
        
    elif data == "t_add_calc":
        await query.answer()
        await show_tandoor_addition_result(query, chat_id)
        
    elif data == "t_config_menu":
        await query.answer()
        await show_config_main_menu(query, chat_id)
        
    elif data == "t_config_somsa":
        await query.answer()
        await show_config_somsa_menu(update, context, chat_id)
        
    elif data.startswith("t_config_somsa_select:"):
        await query.answer()
        price = data.split(":", 1)[1]
        user_states[chat_id] = {
            "state": "EDITING_SOMSA_NAME",
            "editing_price": price
        }
        await query.edit_message_text(f"✏️ **{int(price):,} so'mlik** somsa uchun yangi nom yuboring:")
        
    elif data == "t_config_gs":
        await query.answer()
        await show_gs_config_menu(update, context, chat_id)
        
    elif data == "t_config_gs_toggle":
        config = load_tandoor_config()
        gs_config = config.get("google_sheets", {})
        gs_config["enabled"] = not gs_config.get("enabled", False)
        save_tandoor_config(config)
        await query.answer(f"Sinxronizatsiya {'yoqildi' if gs_config['enabled'] else 'ochirildi'}")
        await show_gs_config_menu(update, context, chat_id)
        
    elif data == "t_config_gs_set_id":
        await query.answer()
        user_states[chat_id] = {
            "state": "AWAITING_SHEET_ID"
        }
        await query.edit_message_text("✏️ **Google Spreadsheet ID** ni yuboring:")
        
    elif data == "t_config_gs_set_name":
        await query.answer()
        user_states[chat_id] = {
            "state": "AWAITING_SHEET_TAB"
        }
        await query.edit_message_text("✏️ **Varaq nomini** yuboring (Masalan: `Tandir Hisoboti`):")
        
    elif data == "t_config_gs_sync":
        config = load_tandoor_config()
        gs_config = config.get("google_sheets", {})
        if not gs_config.get("enabled", False):
            await query.answer("Google Sheets o'chirilgan! Avval integratsiyani yoqing.", show_alert=True)
            return
            
        await query.answer()
        await query.edit_message_text("⏳ Barcha yozuvlarni Google Sheets-ga yuklash boshlandi...")
        
        def run_bulk_sync():
            from google_sheets_client import sync_tandoor_to_sheets
            bakes = load_tandoor_bakes()
            somsa_names = config.get("somsa_names", {})
            success_count = 0
            failed_count = 0
            last_err = ""
            
            for bake in bakes:
                success, msg = sync_tandoor_to_sheets(config, bake, somsa_names)
                if success:
                    success_count += 1
                else:
                    failed_count += 1
                    last_err = msg
                    
            status_msg = f"🔄 **Sinxronizatsiya yakunlandi:**\n\n• Yuklandi: `{success_count}` ta yozuv\n• Xatolik: `{failed_count}` ta yozuv"
            if failed_count > 0:
                status_msg += f"\n• Xatolik sababi: `{last_err}`"
                
            asyncio.run_coroutine_threadsafe(
                context.bot.send_message(chat_id, status_msg, parse_mode="Markdown"),
                bot_loop
            )
            asyncio.run_coroutine_threadsafe(
                show_gs_config_menu(update, context, chat_id, is_message=True),
                bot_loop
            )
            
        threading.Thread(target=run_bulk_sync, daemon=True).start()

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
        
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    
    if text == "🗳 Tandir Hisoblagichi":
        is_auth, role, name = is_user_authorized(chat_id)
        if not is_auth:
            await update.message.reply_text("⚠️ Kechirasiz, sizda kirish ruxsati yo'q. PIN-kod orqali tizimga kiring. Masalan: `/login 1111`", parse_mode="Markdown")
            return
        await show_tandoor_main_menu(update, context, is_message=True)
        return
        
    state_data = user_states.get(chat_id)
    if not state_data or not state_data.get("state"):
        return
        
    state = state_data["state"]
    
    if state == "AWAITING_CUSTOM_NAME":
        state_data["tandoor_name"] = text
        state_data["state"] = "EDITING_TANDIR"
        await show_tandoor_edit_board(update, context, chat_id)
        
    elif state == "AWAITING_COUNT":
        price = state_data.get("editing_price")
        try:
            count = int(text)
            if count < 0:
                raise ValueError()
            state_data["counts"][price] = count
            state_data["state"] = "EDITING_TANDIR"
            state_data["editing_price"] = None
            await show_tandoor_edit_board(update, context, chat_id)
        except ValueError:
            await update.message.reply_text("❌ Xato! Iltimos, faqat musbat butun son kiriting:")
            
    elif state == "EDITING_SOMSA_NAME":
        price = state_data.get("editing_price")
        config = load_tandoor_config()
        config["somsa_names"][price] = text
        save_tandoor_config(config)
        
        state_data["state"] = None
        state_data["editing_price"] = None
        
        await update.message.reply_text(f"✅ {int(price):,} so'mlik somsa nomi '{text}' deb o'zgartirildi.")
        await show_config_somsa_menu(update, context, chat_id, is_message=True)
        
    elif state == "AWAITING_SHEET_ID":
        config = load_tandoor_config()
        config["google_sheets"]["spreadsheet_id"] = text
        save_tandoor_config(config)
        
        state_data["state"] = None
        await update.message.reply_text("✅ Google Spreadsheet ID muvaffaqiyatli saqlandi.")
        await show_gs_config_menu(update, context, chat_id, is_message=True)
        
    elif state == "AWAITING_SHEET_TAB":
        config = load_tandoor_config()
        config["google_sheets"]["sheet_name"] = text
        save_tandoor_config(config)
        
        state_data["state"] = None
        await update.message.reply_text(f"✅ Varaq nomi '{text}' deb saqlandi.")
        await show_gs_config_menu(update, context, chat_id, is_message=True)

# 4. TELEGRAM BOT NOTIFICATION & LOGIC
async def send_status_notification(application, chat_id, order_id, new_status):
    # Load user language
    user_langs = load_user_languages()
    lang = user_langs.get(str(chat_id), "uz")
    
    status_msg_template = MESSAGES.get(lang, MESSAGES["uz"])["status_changed"]
    
    status_label_key = f"status_{new_status}"
    status_str = MESSAGES.get(lang, MESSAGES["uz"]).get(status_label_key, new_status)
    
    # Custom status for delivery
    if new_status == "ready":
        try:
            orders = load_orders()
            for o in orders:
                if o.get("id") == order_id:
                    if o.get("orderType") == "dostavka":
                        status_str = MESSAGES.get(lang, MESSAGES["uz"]).get("status_ready_delivery", status_str)
                    break
        except Exception:
            pass
            
    notification_text = status_msg_template.format(
        order_id=order_id,
        status_str=status_str
    )
    
    try:
        await application.bot.send_message(
            chat_id=chat_id,
            text=notification_text,
            parse_mode="Markdown"
        )
        logger.info(f"Sent status notification to user {chat_id} for order {order_id}")
    except Exception as e:
        logger.error(f"Failed to send status notification: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    username = user.first_name if user else "Mehmon"
    user_id = user.id if user else 0
    
    if not WEBAPP_URL:
        instructions = (
            "⏳ **Tizim yuklanmoqda yoki SSH tunnel ulanmagan...**\n\n"
            "Avtomatik tunnel ulana olmasa, quyidagi ko'rsatmalardan foydalaning:\n\n"
            "1. Bir necha soniya kutib, `/start` buyrug'ini qaytadan yuboring.\n"
            "2. Agar `ngrok` yoki muqobil tunnel yoqilgan bo'lsa, uning URL manzilini bot papkasidagi **`webapp_url.txt`** fayliga yozib saqlang.\n\n"
            "Masalan, fayl tarkibi: `https://xxxx.ngrok-free.app/index.html` ko'rinishida bo'lsin."
        )
        await update.message.reply_text(
            text=instructions,
            parse_mode="Markdown"
        )
        return

    admin_url = WEBAPP_URL.replace("index.html", "admin.html")
    is_auth, role, full_name = is_user_authorized(user_id)

    # Check user language
    user_langs = load_user_languages()
    lang = user_langs.get(str(user_id))
    
    if not lang:
        # Prompt language selection
        keyboard = [
            [
                InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="lang:uz"),
                InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:ru")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            text="Iltimos, muloqot tilini tanlang / Пожалуйста, выберите язык общения:",
            reply_markup=reply_markup
        )
        return

    # AUTHORIZED LAYOUT (for admin/staff)
    if is_auth:
        if role == "admin":
            welcome_text = (
                f"Assalomu alaykum, Admin! 👑\n\n"
                f"**POLVON somsa** boshqaruv tizimiga muvaffaqiyatli avtorizatsiyadan o'tdingiz.\n\n"
                f"Buyurtmalarni real-vaqt rejimida qabul qilish va boshqarish uchun pastdagi **⚙ Admin Panel** yoki yopilgan somsalarni hisoblash uchun **🗳 Tandir Hisoblagichi** tugmasidan foydalaning."
            )
            
            inline_keyboard = [
                [
                    InlineKeyboardButton(text="⚙ Admin Boshqaruv Paneli", web_app=WebAppInfo(url=admin_url))
                ],
                [
                    InlineKeyboardButton(text="🍽 Menyuni ochish (Mijoz sifatida)", web_app=WebAppInfo(url=WEBAPP_URL))
                ]
            ]
            inline_markup = InlineKeyboardMarkup(inline_keyboard)

            reply_keyboard = [
                [
                    KeyboardButton(text="⚙ Admin Panel", web_app=WebAppInfo(url=admin_url)),
                    KeyboardButton(text="🍽 Menyu", web_app=WebAppInfo(url=WEBAPP_URL))
                ],
                [
                    KeyboardButton(text="🗳 Tandir Hisoblagichi")
                ]
            ]
            reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)

            try:
                await context.bot.set_chat_menu_button(
                    chat_id=update.effective_chat.id,
                    menu_button=None
                )
            except Exception as e:
                logger.error(f"Error resetting admin chat menu button: {e}")

            await update.message.reply_text(
                text=welcome_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            
            await update.message.reply_text(
                text="Boshqaruv panelini ochish uchun quyidagi tugmani bosing👇",
                reply_markup=inline_markup,
                parse_mode="Markdown"
            )
            return

    # CLIENT LAYOUT
    msg_template = MESSAGES.get(lang, MESSAGES["uz"])
    welcome_text = msg_template["welcome"].format(username=username)
    
    inline_keyboard = [[InlineKeyboardButton(text=msg_template["open_menu"], web_app=WebAppInfo(url=WEBAPP_URL))]]
    inline_markup = InlineKeyboardMarkup(inline_keyboard)

    reply_keyboard = [[KeyboardButton(text=msg_template["open_menu"].split()[-1], web_app=WebAppInfo(url=WEBAPP_URL))]]
    reply_markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)

    try:
        await context.bot.set_chat_menu_button(
            chat_id=update.effective_chat.id,
            menu_button=None
        )
    except Exception as e:
        logger.error(f"Error resetting client chat menu button: {e}")

    await update.message.reply_text(
        text=welcome_text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    
    await update.message.reply_text(
        text=msg_template["menu_instruction"],
        reply_markup=inline_markup,
        parse_mode="Markdown"
    )

async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    raw_data = update.message.web_app_data.data
    logger.info(f"Received WebApp data: {raw_data}")
    
    chat_id = update.message.chat_id
    user_langs = load_user_languages()
    lang = user_langs.get(str(chat_id), "uz")
    
    try:
        order = json.loads(raw_data)
        order_id = order.get("id")
        items = order.get("items", [])
        total_price = order.get("totalPrice")
        order_type = order.get("orderType")
        table_number = order.get("tableNumber")
        address = order.get("address", "")
        lat = order.get("latitude")
        lng = order.get("longitude")
        
        # Enforce user metadata bindings to save in db
        user = update.effective_user
        order["user_id"] = chat_id
        if user:
            name_parts = [user.first_name, user.last_name]
            order["username"] = " ".join([p for p in name_parts if p])
            if user.username:
                order["username"] += f" (@{user.username})"
        else:
            order["username"] = "Polvon Mehmon"
            
        # Save to local db
        save_order(order)
        
        # Format the invoice
        invoice_items = []
        for item in items:
            invoice_items.append(
                f"• **{item['name']}** ({item['attribute']})\n"
                f"  Soni: {item['quantity']} ta x {item['unitPrice']:,} SO'M = {item['totalPrice']:,} SO'M" if lang == "uz" else
                f"  Кол-во: {item['quantity']} шт x {item['unitPrice']:,} СУМ = {item['totalPrice']:,} СУМ"
            )
        
        items_text = "\n".join(invoice_items)
        
        # Format fulfillment text
        if order_type == "saboy":
            fulfillment_text = "Olib ketish (Saboy)" if lang == "uz" else "На вынос (С собой)"
        elif order_type == "dostavka":
            fulfillment_text = f"Yetkazib berish (Dostavka) 🚚" if lang == "uz" else "Доставка 🚚"
        else:
            fulfillment_text = f"Shu yerda ({table_number}-Stol)" if lang == "uz" else f"В заведении ({table_number}-Стол)"
            
        if order_type == "dostavka" and address:
            manzil_label = "Manzil" if lang == "uz" else "Адрес"
            items_text += f"\n\n📍 **{manzil_label}:** {address}"
            
        msg_template = MESSAGES.get(lang, MESSAGES["uz"])["order_received"]
        invoice_text = msg_template.format(
            order_id=order_id,
            items_text=items_text,
            fulfillment_text=fulfillment_text,
            total_price=total_price
        )
        
        await update.message.reply_text(
            text=invoice_text,
            parse_mode="Markdown"
        )
        
        # Notify Admin of the new order
        if ADMIN_ID and bot_loop and bot_app:
            admin_fulfillment_text = "Olib ketish (Saboy)"
            if order_type == "dostavka":
                admin_fulfillment_text = "Yetkazib berish (Dostavka) 🚚"
            elif order_type == "dine-in":
                admin_fulfillment_text = f"Shu yerda ({table_number}-Stol)"
                
            admin_msg = (
                f"🔔 **Yangi buyurtma!**\n"
                f"Buyurtma ID: `#{order_id}`\n"
                f"Mijoz: {order.get('username', 'Mehmon')}\n\n"
                f"**Somsalar:**\n{items_text}\n\n"
                f"🛒 **Turi:** {admin_fulfillment_text}\n"
                f"💰 **Jami:** {total_price:,} SO'M\n"
            )
            if order_type == "dostavka":
                admin_msg += f"📍 **Manzil:** {address}\n"
                if lat and lng:
                    admin_msg += f"🗺 **Geolokatsiya:** [Google Maps-da ko'rish](https://maps.google.com/?q={lat},{lng})\n"
            
            asyncio.run_coroutine_threadsafe(
                bot_app.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=admin_msg,
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                ),
                bot_loop
            )
            
    except Exception as e:
        logger.error(f"Error parsing order payload: {e}")
        err_msg = "Tizimda xatolik yuz berdi. Iltimos, buyurtmangizni qayta yuboring." if lang == "uz" else "Произошла ошибка в системе. Пожалуйста, отправьте заказ заново."
        await update.message.reply_text(
            text=err_msg
        )

def main():
    global bot_app, bot_loop
    
    # Clear old webapp_url.txt content on startup to prevent stale URL usage
    url_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp_url.txt")
    if os.path.exists(url_file):
        try:
            with open(url_file, "w", encoding="utf-8") as f:
                f.write("")
            logger.info("Base folder: Cleared stale webapp_url.txt on startup.")
        except Exception as e:
            logger.error(f"Error clearing webapp_url.txt: {e}")
            
    # Initialize the Telegram Application
    bot_app = Application.builder().token(BOT_TOKEN).build()
    
    # Start Python Web Server in a daemon thread
    server_thread = threading.Thread(target=run_web_server, daemon=True)
    server_thread.start()
    
    # Start Tunnel Thread
    tunnel_thread = threading.Thread(target=run_tunnel, daemon=True)
    tunnel_thread.start()

    # Start URL file checker thread
    checker_thread = threading.Thread(target=check_webapp_url_file, daemon=True)
    checker_thread.start()

    # Commands & handlers
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("login", login))
    bot_app.add_handler(CallbackQueryHandler(handle_tandoor_callback))
    bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    bot_app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))

    # Python 3.12+ compatibility: Ensure event loop exists in MainThread
    try:
        bot_loop = asyncio.get_event_loop()
    except RuntimeError:
        bot_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(bot_loop)

    logger.info("Polvon Somsa Telegram Bot is starting...")
    
    try:
        # Start bot polling (blocking), requesting all update types including callback_query
        bot_app.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        logger.info("Stopping bot...")
    finally:
        # Clean up tunnel process on exit
        if ssh_process:
            logger.info("Terminating tunnel process...")
            ssh_process.terminate()
            ssh_process.kill()

if __name__ == "__main__":
    main()
