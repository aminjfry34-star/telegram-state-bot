import os
from telegram import Update
from telegram.ext import Application, CommandHandler

TOKEN = os.environ.get('TOKEN', "توکن_بات")

async def start(update: Update, context):
    await update.message.reply_text("سلام! بات روشنه 🎉")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    
    PORT = int(os.environ.get('PORT', 8080))
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url="https://my-telegram-bot.onrender.com"
    )

if __name__ == '__main__':
    main()
