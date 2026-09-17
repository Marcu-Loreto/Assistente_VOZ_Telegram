from assistente_telegram_voz.memory import ConversationMemory


def test_append_e_get_isolado_por_chat():
    m = ConversationMemory(max_messages=4)
    m.append(1, "user", "oi")
    m.append(1, "assistant", "ola")
    m.append(2, "user", "outro chat")
    assert m.get_history(1) == [
        {"role": "user", "content": "oi"},
        {"role": "assistant", "content": "ola"},
    ]
    assert m.get_history(2) == [{"role": "user", "content": "outro chat"}]


def test_janela_limita_tamanho():
    m = ConversationMemory(max_messages=2)
    for i in range(5):
        m.append(1, "user", f"msg{i}")
    hist = m.get_history(1)
    assert len(hist) == 2
    assert hist[0]["content"] == "msg3"
    assert hist[1]["content"] == "msg4"


def test_get_history_chat_desconhecido_vazio():
    m = ConversationMemory(max_messages=4)
    assert m.get_history(999) == []
