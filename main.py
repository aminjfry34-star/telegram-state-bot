import os
from telegram import Update
from telegram.ext import Application, CommandHandler

TOKEN = os.environ.get('TOKEN', "توکن_بات")

async def start(update: Update, context):
    await update.message.reply_text("سلام! بات روشنه 🎉")
# به جای run_webhook، از run_polling استفاده کن
def main():
    app = Application.builder().token(TOKEN).build()
    # ... بقیه کد هندلرها ...
    app.run_polling()
    )

if __name__ == '__main__':
    main()
