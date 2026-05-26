import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CallbackQueryHandler, filters
from dotenv import load_dotenv

# Configuração de logs
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
AUTHORIZED_ID = os.getenv("AUTHORIZED_USER_ID")

# Estado simples para gerenciar feedbacks pendentes
# Em produção, isso deveria estar em um cache/DB (Redis)
pending_feedbacks = {} 

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)

    # Filtro de segurança (Axioma: Certeza antes da ação)
    if user_id != AUTHORIZED_ID:
        logging.warning(f"Acesso negado para usuário: {user_id}")
        await update.message.reply_text("Acesso não autorizado.")
        return

    # Verifica se estamos aguardando um feedback de roteiro
    if user_id in pending_feedbacks:
        job_id = pending_feedbacks.pop(user_id)
        await update.message.reply_text("✏️ Ajuste recebido! Reescrevendo o roteiro...")

        from core.orchestrator import hermes
        asyncio.create_task(hermes.resume_with_feedback(job_id, update.message.text, user_id))
        return

    text = update.message.text
    if text.startswith("http"):
        await update.message.reply_text("🔍 Analisando o produto...")

        try:
            from core.orchestrator import hermes
            asyncio.create_task(hermes.start_pipeline(user_id, text))
            await update.message.reply_text("✅ Análise iniciada! Em breve você receberá o roteiro para aprovação.")
        except Exception as e:
            logging.error(f"Erro ao disparar orquestrador: {e}")
            await update.message.reply_text("❌ Erro interno. Tente novamente.")
    else:
        await update.message.reply_text("Envie a URL do produto para eu criar o roteiro do comercial.")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa os cliques nos botões Inline."""
    query = update.callback_query
    await query.answer()

    user_id = str(update.effective_user.id)
    data = query.data

    # Revalida autorização também em callbacks para evitar execução por usuários não permitidos.
    if user_id != AUTHORIZED_ID:
        logging.warning(f"Callback negado para usuário não autorizado: {user_id}")
        await query.edit_message_text(text="Acesso não autorizado.")
        return

    if data.startswith("appr_"):
        job_id = data.replace("appr_", "")
        await query.edit_message_text(text="✅ Roteiro aprovado! Iniciando a geração do comercial...")

        from core.orchestrator import hermes
        asyncio.create_task(hermes.resume_for_video(job_id, user_id))

    elif data.startswith("edit_"):
        job_id = data.replace("edit_", "")
        pending_feedbacks[user_id] = job_id
        await query.edit_message_text(text="✏️ Me diga o que você quer ajustar no roteiro:")

if __name__ == '__main__':
    if not TOKEN:
        print("Erro: TELEGRAM_BOT_TOKEN não encontrado no .env")
        exit(1)

    application = ApplicationBuilder().token(TOKEN).build()

    # Handlers
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Bot do Telegram (Hermes Gateway) iniciado...")
    application.run_polling()
