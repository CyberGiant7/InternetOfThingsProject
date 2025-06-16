import os
import json
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import BadRequest
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
STATUS_FILE = "hvac_status.json"
authorized_chat_ids = []

def read_hvac_status():
    """Read HVAC status from file."""
    try:
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, 'r') as f:
                data = json.load(f)
                return data.get('hvac_status', False)
    except Exception:
        pass
    return False

def write_hvac_status(status):
    """Write HVAC status to file."""
    try:
        data = {'hvac_status': status}
        with open(STATUS_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        print(f"Error writing status: {e}")

def get_main_keyboard():
    """Create main keyboard with HVAC controls."""
    status = read_hvac_status()
    keyboard = [
        [
            InlineKeyboardButton("🔥 Turn ON HVAC" if not status else "✅ HVAC ON", 
                               callback_data="hvac_on"),
            InlineKeyboardButton("❄️ Turn OFF HVAC" if status else "✅ HVAC OFF", 
                               callback_data="hvac_off")
        ],
        [InlineKeyboardButton("📊 Check Status", callback_data="status")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="refresh")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if chat_id not in authorized_chat_ids:
        authorized_chat_ids.append(chat_id)
    
    status = "ON" if read_hvac_status() else "OFF"
    message = (
        f'🏠 <b>HVAC Control Bot</b>\n\n'
        f'Current Status: <b>{status}</b>\n\n'
        f'Use the buttons below to control your HVAC system:'
    )
    
    await update.message.reply_text(
        message,
        parse_mode='HTML',
        reply_markup=get_main_keyboard()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button presses."""
    query = update.callback_query
    chat_id = query.from_user.id
    
    if chat_id not in authorized_chat_ids:
        await query.answer("❌ Not authorized!")
        return
    
    current_status = read_hvac_status()
    
    if query.data == "hvac_on":
        if current_status:
            await query.answer("✅ HVAC is already ON!")
            return
        write_hvac_status(True)
        message = "✅ <b>HVAC System turned ON</b>\n🔥 Energy waste detection enabled"
        await query.answer("🔥 HVAC turned ON!")
        
    elif query.data == "hvac_off":
        if not current_status:
            await query.answer("✅ HVAC is already OFF!")
            return
        write_hvac_status(False)
        message = "✅ <b>HVAC System turned OFF</b>\n❄️ Energy waste detection disabled"
        await query.answer("❄️ HVAC turned OFF!")
        
    elif query.data == "status":
        status = "ON" if current_status else "OFF"
        emoji = "🔥" if current_status else "❄️"
        message = f"📊 <b>HVAC Status</b>\n{emoji} System is currently <b>{status}</b>"
        await query.answer(f"{emoji} HVAC is {status}")
        
    elif query.data == "refresh":
        status = "ON" if current_status else "OFF"
        message = (
            f'🏠 <b>HVAC Control Bot</b>\n\n'
            f'Current Status: <b>{status}</b>\n\n'
            f'Use the buttons below to control your HVAC system:'
        )
        await query.answer("🔄 Refreshed!")
    
    try:
        await query.edit_message_text(
            message,
            parse_mode='HTML',
            reply_markup=get_main_keyboard()
        )
    except BadRequest as e:
        if "Message is not modified" in str(e):
            # Message content is the same, just acknowledge the button press
            pass
        else:
            print(f"Error updating message: {e}")

# Legacy command handlers (still work with text commands)
async def hvac_on(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if chat_id not in authorized_chat_ids:
        return
    
    write_hvac_status(True)
    await update.message.reply_text(
        '✅ HVAC system turned ON - Energy waste detection enabled',
        reply_markup=get_main_keyboard()
    )

async def hvac_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if chat_id not in authorized_chat_ids:
        return
    
    write_hvac_status(False)
    await update.message.reply_text(
        '✅ HVAC system turned OFF - Energy waste detection disabled',
        reply_markup=get_main_keyboard()
    )

async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if chat_id not in authorized_chat_ids:
        return
    
    status = "ON" if read_hvac_status() else "OFF"
    emoji = "🔥" if read_hvac_status() else "❄️"
    await update.message.reply_text(
        f'📊 HVAC system is currently {emoji} {status}',
        reply_markup=get_main_keyboard()
    )

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN not found")
        return
    
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("hvac_on", hvac_on))
    application.add_handler(CommandHandler("hvac_off", hvac_off))
    application.add_handler(CommandHandler("status", check_status))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("Telegram bot started with buttons...")
    application.run_polling()

if __name__ == '__main__':
    main()