import asyncio
import logging
import tempfile

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from .config import get_settings
from .llm import generate
from .memory import ConversationMemory
from .prompt import build_system_prompt
from .rag import retrieve
from .transcribe import transcribe
from .tts import synthesize

logger = logging.getLogger(__name__)

ERRO_FALLBACK = "Tive um problema ao processar sua mensagem. Pode tentar de novo?"
AUDIO_LONGO = "Esse áudio é muito longo. Envie um menor, por favor."


def process_message(chat_id: int, user_text: str, memory: ConversationMemory) -> str:
    """Orquestra RAG + histórico + LLM e atualiza a memória. Nunca levanta exceção."""
    try:
        chunks = retrieve(user_text)
        system = build_system_prompt(chunks)
        history = memory.get_history(chat_id)
        reply = generate(system=system, history=history, user_msg=user_text)
        memory.append(chat_id, "user", user_text)
        memory.append(chat_id, "assistant", reply)
        return reply
    except Exception:
        logger.exception("Falha ao processar mensagem")
        return ERRO_FALLBACK


async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    memory: ConversationMemory = ctx.application.bot_data["memory"]
    chat_id = update.effective_chat.id
    await ctx.bot.send_chat_action(chat_id, "typing")
    # process_message faz I/O de rede síncrono; roda fora do event loop.
    reply = await asyncio.to_thread(process_message, chat_id, update.message.text, memory)
    await update.message.reply_text(reply)


async def handle_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    memory: ConversationMemory = ctx.application.bot_data["memory"]
    s = get_settings()
    chat_id = update.effective_chat.id

    if update.message.voice.duration > s.max_audio_seconds:
        await update.message.reply_text(AUDIO_LONGO)
        return

    await ctx.bot.send_chat_action(chat_id, "record_voice")
    tg_file = await update.message.voice.get_file()
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=True) as tmp:
        await tg_file.download_to_drive(tmp.name)
        try:
            user_text = await asyncio.to_thread(transcribe, tmp.name)
        except Exception:
            logger.exception("Falha na transcrição")
            await update.message.reply_text(ERRO_FALLBACK)
            return

    reply = await asyncio.to_thread(process_message, chat_id, user_text, memory)

    # Se o processamento falhou, não vale gastar TTS narrando o erro: responde texto.
    if reply == ERRO_FALLBACK:
        await update.message.reply_text(reply)
        return

    try:
        audio = await asyncio.to_thread(synthesize, reply)
        await update.message.reply_voice(voice=audio)
    except Exception:
        logger.exception("Falha no TTS; caindo para texto")
        await update.message.reply_text(reply)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    s = get_settings()
    app = Application.builder().token(s.telegram_bot_token).build()
    app.bot_data["memory"] = ConversationMemory(max_messages=s.history_max_messages)
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("Bot iniciado. Polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
