from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"Ваш Chat ID: {chat_id}")

if __name__ == '__main__':
    TOKEN = "8172736488:AAF6tSc9TWCviWD8wVzXx6aY1z5MBOmTlWA"
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('chatid', get_chat_id))
    app.run_polling()
