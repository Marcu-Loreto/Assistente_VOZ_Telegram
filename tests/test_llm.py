from unittest.mock import MagicMock

from assistente_telegram_voz import llm as lmod


def test_generate_monta_mensagens_e_retorna_texto(monkeypatch):
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="resposta"))]
    )
    monkeypatch.setattr(lmod, "_client", lambda: fake_client)
    out = lmod.generate(
        system="SYS",
        history=[{"role": "user", "content": "oi"}],
        user_msg="tudo bem?",
    )
    assert out == "resposta"
    _, kwargs = fake_client.chat.completions.create.call_args
    msgs = kwargs["messages"]
    assert msgs[0] == {"role": "system", "content": "SYS"}
    assert msgs[-1] == {"role": "user", "content": "tudo bem?"}
