from assistente_telegram_voz import prompt as pmod


def _point_prompt_to(tmp_path, monkeypatch, content: str):
    """Faz load_system_prompt ler de um arquivo temporário e limpa o cache."""
    p = tmp_path / "system.md"
    p.write_text(content, encoding="utf-8")
    monkeypatch.setenv("SYSTEM_PROMPT_PATH", str(p))
    from assistente_telegram_voz.config import get_settings

    get_settings.cache_clear()
    pmod.load_system_prompt.cache_clear()


def test_build_sem_chunks_inclui_base_e_marca_ausencia(tmp_path, monkeypatch):
    _point_prompt_to(tmp_path, monkeypatch, "Voce e um assistente.")
    out = pmod.build_system_prompt([])
    assert out.startswith("Voce e um assistente.")
    assert "nenhum documento recuperado" in out.lower()


def test_build_com_chunks_injeta_contexto(tmp_path, monkeypatch):
    _point_prompt_to(tmp_path, monkeypatch, "BASE")
    out = pmod.build_system_prompt(["fato A", "fato B"])
    assert "BASE" in out
    assert "fato A" in out and "fato B" in out
    assert "CONTEXT_RAG" in out
