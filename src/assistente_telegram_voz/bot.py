import asyncio
import logging
import tempfile

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from .config import get_settings
from .image import describe_image
from .llm import generate
from .memory import ConversationMemory
from .prompt import build_system_prompt
from .rag import retrieve
from .transcribe import transcribe
from .tts import synthesize

logger = logging.getLogger(__name__)

ERRO_FALLBACK = "Tive um problema ao processar sua mensagem. Pode tentar de novo?"
AUDIO_LONGO = "Esse áudio é muito longo. Envie um menor, por favor."

# Instrução padrão quando a foto vem sem legenda: comportamento "explique a imagem".
LEGENDA_PADRAO = "Explique a imagem a seguir."


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


def process_image_message(
    chat_id: int, image_bytes: bytes, mime: str, caption: str, memory: ConversationMemory
) -> str:
    """Interpreta a imagem (visão + OCR) e responde seguindo a instrução do usuário.

    A legenda do usuário guia a saída (ex.: "resuma", "só o texto", "traduza"). Sem
    legenda, usa a instrução padrão de explicar a imagem. O conteúdo visual entra
    como contexto e o RAG é feito sobre a instrução do usuário. Nunca levanta
    exceção — devolve o texto de fallback em caso de erro.
    """
    try:
        instrucao = (caption or "").strip() or LEGENDA_PADRAO
        # Extrai descrição + OCR da imagem (faz o pré-processamento internamente).
        conteudo_visual = describe_image(image_bytes, mime)

        # RAG a partir da instrução do usuário (não do dump da imagem).
        chunks = retrieve(instrucao)
        system = build_system_prompt(chunks)
        history = memory.get_history(chat_id)

        user_msg = (
            f"{instrucao}\n\n"
            "===== CONTEUDO DA IMAGEM (interpretação + OCR) =====\n"
            f"{conteudo_visual}\n"
            "===== FIM DO CONTEUDO DA IMAGEM ====="
        )
        reply = generate(system=system, history=history, user_msg=user_msg)

        # Guarda na memória o que o usuário pediu e a resposta, mantendo o contexto.
        memory.append(chat_id, "user", f"[imagem] {instrucao}")
        memory.append(chat_id, "assistant", reply)
        return reply
    except Exception:
        logger.exception("Falha ao processar imagem")
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

    # Entrega o texto imediatamente (leitura na hora), e o áudio chega em seguida.
    await update.message.reply_text(reply)

    # Se o processamento falhou, não vale gastar TTS narrando o erro.
    if reply == ERRO_FALLBACK:
        return

    # Sinaliza que está gerando o áudio e o envia quando pronto.
    try:
        await ctx.bot.send_chat_action(chat_id, "record_voice")
        audio = await asyncio.to_thread(synthesize, reply)
        await update.message.reply_voice(voice=audio)
    except Exception:
        logger.exception("Falha no TTS; o texto já foi enviado")


async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    memory: ConversationMemory = ctx.application.bot_data["memory"]
    chat_id = update.effective_chat.id

    await ctx.bot.send_chat_action(chat_id, "typing")

    # A foto vem em várias resoluções; a última é a de maior qualidade.
    photo = update.message.photo[-1]
    tg_file = await photo.get_file()
    image_bytes = bytes(await tg_file.download_as_bytearray())

    # Fotos do Telegram são reenviadas como JPEG; o pré-processamento normaliza depois.
    caption = update.message.caption or ""
    reply = await asyncio.to_thread(
        process_image_message, chat_id, image_bytes, "image/jpeg", caption, memory
    )
    await update.message.reply_text(reply)


def _setup_logging() -> None:
    """Configura o logging apenas no terminal.

    Silencia o logger do httpx (nível WARNING): em INFO ele imprime a URL de cada
    request ao Telegram, e essa URL embute o token do bot em texto claro. Sem isso,
    o token vazaria nos logs a cada chamada de polling."""
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def main() -> None:
    s = get_settings()
    _setup_logging()
    app = Application.builder().token(s.telegram_bot_token).build()
    app.bot_data["memory"] = ConversationMemory(max_messages=s.history_max_messages)
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("Bot iniciado. Polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
