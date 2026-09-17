from assistente_telegram_voz import prompt as pmod


def test_build_sem_chunks_retorna_base(tmp_path, monkeypatch):
    p = tmp_path / "system.md"
    p.write_text("Voce e um assistente.", encoding="utf-8")
    monkeypatch.setattr(pmod, "PROMPT_PATH", p)
    pmod.load_system_prompt.cache_clear()
    assert pmod.build_system_prompt([]) == "Voce e um assistente."


def test_build_com_chunks_injeta_contexto(tmp_path, monkeypatch):
    p = tmp_path / "system.md"
    p.write_text("BASE", encoding="utf-8")
    monkeypatch.setattr(pmod, "PROMPT_PATH", p)
    pmod.load_system_prompt.cache_clear()
    out = pmod.build_system_prompt(["fato A", "fato B"])
    assert "BASE" in out
    assert "fato A" in out and "fato B" in out
    assert "apenas o material" in out.lower()
