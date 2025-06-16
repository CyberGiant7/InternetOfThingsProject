# Import necessary libraries for Telegram bot functionality and file operations
import os
import json
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import BadRequest
from dotenv import load_dotenv

# Load environment variables from .env file (contains bot token)
load_dotenv()

# Configuration constants
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Bot token from environment variables
STATUS_FILE = "hvac_status.json"  # File to store HVAC system status persistently
authorized_chat_ids = []  # List to store authorized user chat IDs for security

def read_hvac_status():
    """
    Read HVAC status from JSON file.
    
    Returns:
        bool: True if HVAC is active, False otherwise
        
    This function safely reads the HVAC status from a JSON file,
    handling cases where the file doesn't exist or is corrupted.
    """
    try:
        # Check if status file exists before attempting to read
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, 'r') as f:
                # Load JSON data and extract HVAC status
                data = json.load(f)
                return data.get('hvac_status', False)
    except Exception:
        # Silently handle any file read errors (corrupted JSON, permission issues, etc.)
        pass
    # Return False as default state if file doesn't exist or error occurs
    return False

def write_hvac_status(status):
    """
    Write HVAC status to JSON file.
    
    Args:
        status (bool): True to turn HVAC on, False to turn off
        
    This function persists the HVAC system state to a file so the
    status is maintained across bot restarts and system reboots.
    """
    try:
        # Create data structure with HVAC status
        data = {'hvac_status': status}
        # Write status to JSON file with proper formatting
        with open(STATUS_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        # Log any errors that occur during file writing
        print(f"Error writing status: {e}")

def get_main_keyboard():
    """
    Create inline keyboard with HVAC control buttons.
    
    Returns:
        InlineKeyboardMarkup: Telegram inline keyboard with context-aware buttons
        
    This function dynamically creates buttons based on current HVAC status.
    Button text and emojis change to reflect the current system state.
    """
    # Get current HVAC status to determine button states
    status = read_hvac_status()
    
    # Create keyboard layout with context-aware button labels
    keyboard = [
        [
            # First row: ON/OFF buttons with dynamic text based on current status
            InlineKeyboardButton("🔥 Turn ON HVAC" if not status else "✅ HVAC ON", 
                               callback_data="hvac_on"),
            InlineKeyboardButton("❄️ Turn OFF HVAC" if status else "✅ HVAC OFF", 
                               callback_data="hvac_off")
        ],
        # Second row: Status check button
        [InlineKeyboardButton("📊 Check Status", callback_data="status")],
        # Third row: Refresh button to update display
        [InlineKeyboardButton("🔄 Refresh", callback_data="refresh")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /start command - initialize bot interaction and show main menu.
    
    Args:
        update (Update): Telegram update object containing message data
        context (ContextTypes.DEFAULT_TYPE): Bot context for handling the update
        
    This function is called when users first interact with the bot or use /start.
    It automatically authorizes the user and displays the main control interface.
    """
    # Get chat ID for user authorization
    chat_id = update.effective_chat.id
    
    # Automatically authorize new users (add to authorized list)
    if chat_id not in authorized_chat_ids:
        authorized_chat_ids.append(chat_id)
    
    # Get current HVAC status for display
    status = "ON" if read_hvac_status() else "OFF"
    
    # Create welcome message with current status
    message = (
        f'🏠 <b>HVAC Control Bot</b>\n\n'
        f'Current Status: <b>{status}</b>\n\n'
        f'Use the buttons below to control your HVAC system:'
    )
    
    # Send welcome message with inline keyboard
    await update.message.reply_text(
        message,
        parse_mode='HTML',  # Enable HTML formatting for bold text
        reply_markup=get_main_keyboard()  # Attach control buttons
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle inline keyboard button presses.
    
    Args:
        update (Update): Telegram update object containing callback query
        context (ContextTypes.DEFAULT_TYPE): Bot context for handling the update
        
    This function processes all button clicks from the inline keyboard,
    including HVAC control commands and status queries.
    """
    # Extract callback query from update
    query = update.callback_query
    chat_id = query.from_user.id
    
    # Security check: verify user is authorized
    if chat_id not in authorized_chat_ids:
        await query.answer("❌ Not authorized!")
        return
    
    # Get current HVAC status for comparison
    current_status = read_hvac_status()
    
    # Handle HVAC ON button press
    if query.data == "hvac_on":
        # Check if HVAC is already on to avoid redundant operations
        if current_status:
            await query.answer("✅ HVAC is already ON!")
            return
        # Turn on HVAC system
        write_hvac_status(True)
        message = "✅ <b>HVAC System turned ON</b>\n🔥 Energy waste detection enabled"
        await query.answer("🔥 HVAC turned ON!")  # Show popup notification
        
    # Handle HVAC OFF button press
    elif query.data == "hvac_off":
        # Check if HVAC is already off to avoid redundant operations
        if not current_status:
            await query.answer("✅ HVAC is already OFF!")
            return
        # Turn off HVAC system
        write_hvac_status(False)
        message = "✅ <b>HVAC System turned OFF</b>\n❄️ Energy waste detection disabled"
        await query.answer("❄️ HVAC turned OFF!")  # Show popup notification
        
    # Handle status check button press
    elif query.data == "status":
        # Get current status and appropriate emoji
        status = "ON" if current_status else "OFF"
        emoji = "🔥" if current_status else "❄️"
        message = f"📊 <b>HVAC Status</b>\n{emoji} System is currently <b>{status}</b>"
        await query.answer(f"{emoji} HVAC is {status}")  # Show popup notification
        
    # Handle refresh button press
    elif query.data == "refresh":
        # Display updated status information
        status = "ON" if current_status else "OFF"
        message = (
            f'🏠 <b>HVAC Control Bot</b>\n\n'
            f'Current Status: <b>{status}</b>\n\n'
            f'Use the buttons below to control your HVAC system:'
        )
        await query.answer("🔄 Refreshed!")  # Show popup notification
    
    # Update the message with new content and refreshed keyboard
    try:
        await query.edit_message_text(
            message,
            parse_mode='HTML',  # Enable HTML formatting
            reply_markup=get_main_keyboard()  # Update keyboard with current status
        )
    except BadRequest as e:
        # Handle case where message content hasn't changed
        if "Message is not modified" in str(e):
            # Message content is the same, just acknowledge the button press
            pass
        else:
            # Log other errors for debugging
            print(f"Error updating message: {e}")

# Legacy command handlers for text-based commands (backwards compatibility)

async def hvac_on(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /hvac_on text command (legacy support).
    
    Args:
        update (Update): Telegram update object containing message data
        context (ContextTypes.DEFAULT_TYPE): Bot context for handling the update
        
    This function provides backwards compatibility for users who prefer
    typing commands instead of using inline buttons.
    """
    # Check user authorization
    chat_id = update.effective_chat.id
    if chat_id not in authorized_chat_ids:
        return
    
    # Turn on HVAC system
    write_hvac_status(True)
    await update.message.reply_text(
        '✅ HVAC system turned ON - Energy waste detection enabled',
        reply_markup=get_main_keyboard()  # Show control buttons
    )

async def hvac_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /hvac_off text command (legacy support).
    
    Args:
        update (Update): Telegram update object containing message data
        context (ContextTypes.DEFAULT_TYPE): Bot context for handling the update
        
    This function provides backwards compatibility for users who prefer
    typing commands instead of using inline buttons.
    """
    # Check user authorization
    chat_id = update.effective_chat.id
    if chat_id not in authorized_chat_ids:
        return
    
    # Turn off HVAC system
    write_hvac_status(False)
    await update.message.reply_text(
        '✅ HVAC system turned OFF - Energy waste detection disabled',
        reply_markup=get_main_keyboard()  # Show control buttons
    )

async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /status text command (legacy support).
    
    Args:
        update (Update): Telegram update object containing message data
        context (ContextTypes.DEFAULT_TYPE): Bot context for handling the update
        
    This function provides backwards compatibility for users who prefer
    typing commands instead of using inline buttons.
    """
    # Check user authorization
    chat_id = update.effective_chat.id
    if chat_id not in authorized_chat_ids:
        return
    
    # Get current status and display with emoji
    status = "ON" if read_hvac_status() else "OFF"
    emoji = "🔥" if read_hvac_status() else "❄️"
    await update.message.reply_text(
        f'📊 HVAC system is currently {emoji} {status}',
        reply_markup=get_main_keyboard()  # Show control buttons
    )

def main():
    """
    Main function to initialize and start the Telegram bot.
    
    This function sets up the bot application, registers all command handlers
    and callback handlers, then starts the polling loop to listen for messages.
    """
    # Check if bot token is available
    if not TELEGRAM_BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN not found")
        return
    
    # Create bot application with the provided token
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Register command handlers for text-based commands
    application.add_handler(CommandHandler("start", start))          # /start command
    application.add_handler(CommandHandler("hvac_on", hvac_on))      # /hvac_on command
    application.add_handler(CommandHandler("hvac_off", hvac_off))    # /hvac_off command
    application.add_handler(CommandHandler("status", check_status))  # /status command
    
    # Register callback handler for inline keyboard button presses
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Start the bot and begin listening for messages
    print("Telegram bot started with buttons...")
    application.run_polling()  # Start polling for updates from Telegram servers

# Application entry point
if __name__ == '__main__':
    # Start the bot when script is run directly
    main()