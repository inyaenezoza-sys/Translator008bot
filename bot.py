import logging
import os
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from deep_translator import GoogleTranslator
from flask import Flask, request
import threading

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Configuration ---
TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TOKEN:
    logger.error("TELEGRAM_TOKEN environment variable not set!")
    sys.exit(1)

PORT = int(os.getenv('PORT', 8080))
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # Required for webhook mode

# --- Language Database ---
LANGUAGES = {
    'en': 'English',
    'es': 'Spanish',
    'fr': 'French',
    'de': 'German',
    'zh-CN': 'Chinese (Simplified)',
    'ja': 'Japanese',
    'ru': 'Russian',
    'ar': 'Arabic',
    'hi': 'Hindi',
    'pt': 'Portuguese',
    'it': 'Italian',
    'ko': 'Korean',
    'nl': 'Dutch',
    'tr': 'Turkish',
    'vi': 'Vietnamese',
    'th': 'Thai',
}

def get_language_keyboard():
    """Create inline keyboard for language selection."""
    keyboard = []
    lang_items = list(LANGUAGES.items())
    for i in range(0, len(lang_items), 3):
        row = [
            InlineKeyboardButton(text, callback_data=code)
            for code, text in lang_items[i:i+3]
        ]
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

# --- Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome message with bot instructions."""
    user = update.effective_user
    context.user_data['target_lang'] = 'en'
    
    welcome_message = (
        f"👋 Hello {user.first_name}!\n\n"
        f"I'm a powerful translation bot. Here's how to use me:\n\n"
        f"📝 Just send me any text message and I'll translate it\n"
        f"🌍 Use /lang to change your target language\n"
        f"❓ Use /help for more commands\n\n"
        f"Current target language: {LANGUAGES['en']}"
    )
    
    await update.message.reply_text(
        welcome_message,
        reply_markup=get_language_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Help command with detailed instructions."""
    help_text = (
        "🤖 **Translation Bot Help**\n\n"
        "**Commands:**\n"
        "/start - Start the bot and see welcome message\n"
        "/help - Show this help message\n"
        "/lang - Change your translation language\n"
        "/status - Check bot status\n\n"
        "**How to use:**\n"
        "1. Send any text message\n"
        "2. The bot will translate it to your target language\n"
        "3. Use /lang to change the target language\n\n"
        "**Tips:**\n"
        "• Long messages are supported\n"
        "• The bot remembers your language preference\n"
        "• You can translate multiple languages"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show language selection menu."""
    current_lang = context.user_data.get('target_lang', 'en')
    message = (
        f"🌍 Choose your target language for translations.\n"
        f"Current: {LANGUAGES.get(current_lang, 'English')}"
    )
    await update.message.reply_text(message, reply_markup=get_language_keyboard())

async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle language selection callback."""
    query = update.callback_query
    await query.answer()
    
    selected_lang = query.data
    context.user_data['target_lang'] = selected_lang
    lang_name = LANGUAGES.get(selected_lang, selected_lang)
    
    await query.edit_message_text(
        f"✅ Language updated!\n\n"
        f"I will now translate your messages to: **{lang_name}**",
        parse_mode='Markdown'
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check bot status and current settings."""
    user_id = update.effective_user.id
    target_lang = context.user_data.get('target_lang', 'en')
    
    status_text = (
        f"📊 **Bot Status**\n\n"
        f"User ID: `{user_id}`\n"
        f"Target Language: {LANGUAGES.get(target_lang, 'English')}\n"
        f"Bot Status: 🟢 Online\n"
        f"Version: 1.0.0"
    )
    await update.message.reply_text(status_text, parse_mode='Markdown')

# --- Translation Handler ---

async def translate_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Translate user messages with error handling."""
    if not update.message or not update.message.text:
        return
    
    user_text = update.message.text.strip()
    if not user_text:
        return
    
    user_id = update.effective_user.id
    target_lang = context.user_data.get('target_lang', 'en')
    
    # Show typing indicator
    await update.message.chat.send_action(action="typing")
    
    try:
        # Translate using deep-translator
        translator = GoogleTranslator(target=target_lang)
        translated_text = translator.translate(user_text)
        
        # Prepare response with character count
        original_len = len(user_text)
        translated_len = len(translated_text)
        
        response = (
            f"📝 **Translation**\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"**Original** ({original_len} chars):\n"
            f"_{user_text}_\n\n"
            f"**Translated** ({LANGUAGES.get(target_lang, target_lang).upper()}) ({translated_len} chars):\n"
            f"_{translated_text}_"
        )
        
        await update.message.reply_text(response, parse_mode='Markdown')
        logger.info(f"✅ Translated message for user {user_id} to {target_lang}")
        
    except Exception as e:
        error_msg = (
            "❌ **Translation Error**\n\n"
            "Sorry, I couldn't translate that message. Possible reasons:\n"
            "• The text is too long\n"
            "• The language isn't supported\n"
            "• Temporary service issue\n\n"
            "Please try again with a shorter message."
        )
        await update.message.reply_text(error_msg, parse_mode='Markdown')
        logger.error(f"❌ Translation error for user {user_id}: {str(e)}")

# --- Webhook and Flask Setup ---

def create_flask_app(application):
    """Create Flask app for webhook handling."""
    flask_app = Flask(__name__)
    
    @flask_app.route('/webhook', methods=['POST'])
    async def webhook():
        """Handle incoming webhook updates."""
        try:
            update = Update.de_json(request.get_json(force=True), application.bot)
            await application.process_update(update)
            return 'OK', 200
        except Exception as e:
            logger.error(f"Webhook error: {str(e)}")
            return 'Error', 500
    
    @flask_app.route('/health', methods=['GET'])
    def health():
        """Health check endpoint for Railway."""
        return {'status': 'healthy', 'bot': 'Translator008tBot'}, 200
    
    @flask_app.route('/', methods=['GET'])
    def index():
        """Root endpoint."""
        return {
            'name': 'Translator008tBot',
            'status': 'online',
            'version': '1.0.0'
        }, 200
    
    return flask_app

# --- Main Application ---

def main():
    """Start the bot application."""
    # Create bot application
    application = Application.builder().token(TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("lang", set_language))
    application.add_handler(CommandHandler("status", status_command))
    
    # Add callback query handler for language selection
    application.add_handler(CallbackQueryHandler(
        language_callback, 
        pattern="|".join(LANGUAGES.keys())
    ))
    
    # Add message handler for translations
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        translate_message
    ))
    
    # Check if running on Railway
    is_railway = os.getenv('RAILWAY_ENVIRONMENT') is not None
    
    if is_railway and WEBHOOK_URL:
        # Webhook mode (for Railway)
        flask_app = create_flask_app(application)
        
        # Set webhook
        webhook_url = f"{WEBHOOK_URL}/webhook"
        application.bot.set_webhook(url=webhook_url)
        logger.info(f"✅ Webhook set to: {webhook_url}")
        
        # Run Flask app
        logger.info(f"🚀 Starting bot in webhook mode on port {PORT}")
        flask_app.run(host='0.0.0.0', port=PORT)
        
    else:
        # Polling mode (for development)
        logger.info("🚀 Starting bot in polling mode...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
