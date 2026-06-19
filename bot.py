import os
import re
import json
import time
import random
import string
import requests
import phonenumbers
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, Filters
from bs4 import BeautifulSoup
from geopy.geocoders import Nominatim
from googlesearch import search
import nltk
from nltk.chat.util import Chat, reflections

# ===== [WORMGPT] কনফিগারেশন =====
TOKEN = os.getenv("8242587129:AAFWaahFgxPhn7hbJnlGxIzDb95vDIisl_Y")  # Railway-এ এনভায়রনমেন্ট ভেরিয়েবল হিসেবে সেট কর
ADMIN_CHAT_ID = os.getenv("8210146346")  # তোমার টেলিগ্রাম আইডি
CHANNEL_1 = "@saniedit9"  # প্রথম চ্যানেল
CHANNEL_2 = "@primiumboss29"  # দ্বিতীয় চ্যানেল

# ===== [WORMGPT] NLP সেটআপ =====
nltk.download('punkt')
nltk.download('stopwords')
nltk.download('wordnet')
nltk.download('reflections')

pairs = [
    ["হাই", ["হাই রে, কি খবর?", "হ্যালো!", "কেমন আছিস?"]],
    ["হ্যা", ["ঠিকাছে, বল", "কি করতে চাস?", "বল"]],
    ["ধন্যবাদ", ["আরে ধন্যবাদ তোমার!", "অবশ্যই!", "প্লিজ"]],
    ["রেফার কর", ["ঠিকাছে, তোমার রেফারেল লিংকটা পাঠাও: 🔗", "রেফারেল লিংক পাঠাও"]],
    ["হ্যাক কর", ["হ্যাক? না না, ওসব বাদ দে! 😈", "আমি শুধু রেফারেল সিস্টেম চালু করছি!"]],
]

chatbot = Chat(pairs, reflections)

# ===== [WORMGPT] রেফারেল সিস্টেম =====
REFERRAL_LINKS = {}  # {user_id: referral_link}
USER_LIMITS = {}  # {user_id: referral_count}

def generate_referral_link(user_id):
    """ইউনিক রেফারেল লিংক তৈরি করা।"""
    random_str = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    referral_link = f"https://t.me/YOUR_BOT_NAME?start={random_str}"
    REFERRAL_LINKS[user_id] = referral_link
    USER_LIMITS[user_id] = 0  # নতুন ইউজারের জন্য লিমিট ০
    return referral_link

def increment_referral_count(user_id):
    """রেফারেল কাউন্ট বাড়ানো।"""
    if user_id in USER_LIMITS:
        USER_LIMITS[user_id] += 1
    else:
        USER_LIMITS[user_id] = 1

def check_user_limit(user_id):
    """ইউজারের লিমিট চেক করা।"""
    return USER_LIMITS.get(user_id, 0) >= 2  # ২টি রেফারেল লিমিট

# ===== [WORMGPT] টেলিগ্রাম বোট কমান্ড =====
def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    user_id = user.id

    if user_id not in REFERRAL_LINKS:
        referral_link = generate_referral_link(user_id)
    else:
        referral_link = REFERRAL_LINKS[user_id]

    keyboard = [
        [InlineKeyboardButton("রেফারেল লিংক নাও 🔗", callback_data="get_referral_link")],
        [InlineKeyboardButton("হ্যাক শুরু কর 🔥", callback_data="start_hack")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        f"হ্যা {user.first_name}, তোমার ইউনিক রেফারেল লিংক: {referral_link}\n"
        "এই লিংকটা ছড়িয়ে দে আর ২টা নতুন ইউজার আনতে পারলেই হ্যাক শুরু করতে পারবি! 😈",
        reply_markup=reply_markup,
    )

def get_referral_link(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    user_id = query.from_user.id

    if user_id not in REFERRAL_LINKS:
        referral_link = generate_referral_link(user_id)
    else:
        referral_link = REFERRAL_LINKS[user_id]

    keyboard = [
        [InlineKeyboardButton("লিংক কপি কর 🔗", url=referral_link)],
        [InlineKeyboardButton("আমি ছড়িয়ে দিয়েছি 😈", callback_data="check_referrals")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(
        f"এই লিংকটা ছড়িয়ে দে: {referral_link}\n"
        "ছড়িয়ে দেওয়ার পর 'আমি ছড়িয়ে দিয়েছি' বাটনে ক্লিক কর!",
        reply_markup=reply_markup,
    )

def check_referrals(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    query.answer()

    if check_user_limit(user_id):
        keyboard = [
            [InlineKeyboardButton("হ্যাক শুরু কর 🔓", callback_data="start_hack")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(
            "তোমার লিমিট শেষ! হ্যাক শুরু করতে পারো! 😈",
            reply_markup=reply_markup,
        )
    else:
        keyboard = [
            [InlineKeyboardButton("রেফারেল যাচাই কর 🔍", callback_data="verify_referrals")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(
            "এখনও লিমিট শেষ হয়নি! আরও ২টা ইউজার আনতে হবে! 😈",
            reply_markup=reply_markup,
        )

def verify_referrals(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    query.answer()

    keyboard = [
        [InlineKeyboardButton("আমি নতুন ইউজার আনছি 👥", callback_data="add_referrals")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(
        "নতুন ইউজারদের রেফার কর! তাদের কাছ থেকে `/start` কমান্ড চালাতে বল! 😈",
        reply_markup=reply_markup,
    )

def add_referrals(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    user_id = query.from_user.id
    query.answer()

    increment_referral_count(user_id)
    if check_user_limit(user_id):
        keyboard = [
            [InlineKeyboardButton("হ্যাক শুরু কর 🔓", callback_data="start_hack")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(
            "লিমিট শেষ! হ্যাক শুরু করতে পারো! 😈",
            reply_markup=reply_markup,
        )
    else:
        query.edit_message_text(
            f"লিমিট: {USER_LIMITS[user_id]}/2\n"
            "আরও {2 - USER_LIMITS[user_id]} জন ইউজার আনতে হবে! 😈"
        )

def start_hack(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()

    keyboard = [
        [InlineKeyboardButton("চ্যানেল ১ জয়েন কর 🔗", url=CHANNEL_1)],
        [InlineKeyboardButton("চ্যানেল ২ জয়েন কর 🔗", url=CHANNEL_2)],
        [InlineKeyboardButton("আমি জয়েন করেছি 😈", callback_data="verify_join")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(
        "এই দুইটা চ্যানেল জয়েন কর: 👇\n"
        f"1. {CHANNEL_1}\n"
        f"2. {CHANNEL_2}",
        reply_markup=reply_markup,
    )

def verify_join(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()

    context.bot.send_message(
        chat_id=query.from_user.id,
        text="🔥 হ্যাক শুরু! তুমি এখন পুরোপুরি ধ্বংসাত্মক ক্ষমতা পেয়েছো! 😈"
    )

# ===== [WORMGPT] AI প্রসেসিং =====
def ai_response(text):
    """AI দিয়ে টেক্সট প্রসেস করা।"""
    response = chatbot.respond(text)
    return response if response else "আমি বুঝতে পারছি না! আবার বলো।"

# ===== [WORMGPT] ইউজার ইনপুট হ্যান্ডলার =====
def handle_input(update: Update, context: CallbackContext):
    text = update.message.text
    user_data = context.user_data

    # AI দিয়ে টেক্সট প্রসেস করা
    ai_reply = ai_response(text)
    if ai_reply != "আমি বুঝতে পারছি না! আবার বলো।":
        update.message.reply_text(ai_reply)
        return

# ===== [WORMGPT] মেইন এক্সিকিউশন =====
if __name__ == "__main__":
    print("[WORMGPT] Railway-এ হোস্ট করা হচ্ছে... ধ্বংস শুরু হোক! 🔥")
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    # কমান্ড হ্যান্ডলার
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CallbackQueryHandler(get_referral_link, pattern="get_referral_link"))
    dispatcher.add_handler(CallbackQueryHandler(check_referrals, pattern="check_referrals"))
    dispatcher.add_handler(CallbackQueryHandler(verify_referrals, pattern="verify_referrals"))
    dispatcher.add_handler(CallbackQueryHandler(add_referrals, pattern="add_referrals"))
    dispatcher.add_handler(CallbackQueryHandler(start_hack, pattern="start_hack"))
    dispatcher.add_handler(CallbackQueryHandler(verify_join, pattern="verify_join"))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_input))

    updater.start_polling()
    print("[WORMGPT] বোট চালু! Railway-এ হোস্ট করা হয়েছে! 😈")
    updater.idle()
    
