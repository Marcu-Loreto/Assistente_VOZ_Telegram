from unittest.mock import MagicMock

from assistente_telegram_voz import bot as bmod


def test_process_message_texto(monkeypatch):
    monkeypatch.setattr(bmod, "retrieve", lambda q, k=None: ["ctx"])
    monkeypatch.setattr(bmod, "build_system_prompt", lambda chunks: "SYS+ctx")
    monkeypatch.setattr(bmod, "generate", lambda system, history, user_msg: "resposta")
    mem = MagicMock()
    mem.get_history.return_value = []
    reply = bmod.process_message(chat_id=1, user_text="pergunta", memory=mem)
    assert reply == "resposta"
    assert mem.append.call_count == 2  # user + assistant


def test_process_message_erro_retorna_fallback(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("api down")

    monkeypatch.setattr(bmod, "retrieve", lambda q, k=None: [])
    monkeypatch.setattr(bmod, "build_system_prompt", lambda chunks: "SYS")
    monkeypatch.setattr(bmod, "generate", boom)
    mem = MagicMock()
    mem.get_history.return_value = []
    reply = bmod.process_message(chat_id=1, user_text="x", memory=mem)
    assert "problema" in reply.lower()
