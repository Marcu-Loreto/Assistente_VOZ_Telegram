from collections import defaultdict, deque


class ConversationMemory:
    """Histórico de conversa por chat em RAM, com janela de tamanho fixo.

    Cada chat_id mantém no máximo `max_messages` mensagens (as mais recentes).
    O estado vive apenas em memória: reiniciar o processo zera tudo.
    """

    def __init__(self, max_messages: int):
        self._max = max_messages
        self._store: dict[int, deque] = defaultdict(lambda: deque(maxlen=self._max))

    def append(self, chat_id: int, role: str, content: str) -> None:
        self._store[chat_id].append({"role": role, "content": content})

    def get_history(self, chat_id: int) -> list[dict]:
        return list(self._store.get(chat_id, []))
