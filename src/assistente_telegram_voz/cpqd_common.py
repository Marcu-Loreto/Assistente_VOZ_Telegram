"""Base compartilhada dos provedores CPQD (STT e TTS).

Adaptado da solução original do CPQD (asr.py/tts.py) para o cenário deste projeto.
STT e TTS usam o mesmo fluxo de autenticação — HTTP Basic no endpoint de auth,
devolvendo um token bearer cacheado (~23h) com um único retry após 401 — mas com
**credenciais separadas por serviço**. Por isso a autenticação é parametrizada por
um `AuthConfig` (usuário/senha próprios) e cada serviço mantém seu próprio cache.

Requer `requests` (chamadas HTTP) e `ffmpeg` no sistema (conversão de áudio).

Copyright da solução original: CPQD.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import requests

AUTH_URL = os.environ.get("CPQD_AUTH_URL", "https://speechp.cpqd.com.br/auth/token")
TIMEOUT_SECONDS = float(os.environ.get("CPQD_TIMEOUT_SECONDS", "15"))
# Margem para não usar um token nos seus últimos minutos de vida.
_TOKEN_MARGIN = 3600.0
_TOKEN_TTL_FALLBACK = 23 * 60 * 60


class CpqdError(RuntimeError):
    """Falha ao falar com um serviço do CPQD (auth, rede, conversão ou resposta)."""


@dataclass(frozen=True)
class AuthConfig:
    """Credenciais e nomes das variáveis de um serviço CPQD (ASR ou TTS)."""

    user_var: str
    password_var: str


@dataclass
class _CachedToken:
    value: str
    expires_at: float


class CpqdAuth:
    """Autenticação CPQD com token cacheado, por serviço.

    Cada instância (uma para ASR, outra para TTS) guarda seu próprio token e sessão,
    porque as credenciais são distintas por serviço.
    """

    def __init__(self, cfg: AuthConfig) -> None:
        self._cfg = cfg
        self._token: _CachedToken | None = None
        self._session: requests.Session | None = None

    def session(self) -> requests.Session:
        if self._session is None:
            self._session = requests.Session()
        return self._session

    def _credentials(self) -> tuple[str, str]:
        user = os.environ.get(self._cfg.user_var, "")
        password = os.environ.get(self._cfg.password_var, "")
        if not user or not password:
            raise CpqdError(
                f"Credenciais CPQD ausentes: defina {self._cfg.user_var} e "
                f"{self._cfg.password_var}."
            )
        return user, password

    def token(self, *, force_refresh: bool = False) -> str:
        """Retorna um token bearer válido, buscando um novo só quando necessário."""
        if self._token and not force_refresh and self._token.expires_at > time.monotonic():
            return self._token.value

        user, password = self._credentials()
        try:
            resp = self.session().post(AUTH_URL, auth=(user, password), timeout=TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            raise CpqdError(f"Falha ao autenticar no CPQD: {exc}") from exc
        if resp.status_code >= 400:
            raise CpqdError(f"Autenticação CPQD falhou ({resp.status_code}).")

        value = _read_token(resp)
        if not value:
            raise CpqdError("Autenticação CPQD respondeu sem token.")
        self._token = _CachedToken(value, time.monotonic() + _read_lifetime(resp))
        return value


def _read_token(response: requests.Response) -> str:
    """Extrai o token bearer da resposta de auth (aceita JSON ou texto puro)."""
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip()
    if not isinstance(payload, dict):
        return ""
    for key in ("access_token", "accessToken", "token"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _read_lifetime(response: requests.Response) -> float:
    """Quanto tempo (s) o token pode ser cacheado; usa expires_in quando presente."""
    try:
        payload = response.json()
    except ValueError:
        return float(_TOKEN_TTL_FALLBACK)
    if not isinstance(payload, dict):
        return float(_TOKEN_TTL_FALLBACK)
    reported = payload.get("expires_in")
    if not isinstance(reported, (int, float)) or reported <= 0:
        return float(_TOKEN_TTL_FALLBACK)
    return max(60.0, float(reported) - _TOKEN_MARGIN)


# ----------------------------------------------------------------- ffmpeg

def _ffmpeg_binary() -> str:
    """Localiza o ffmpeg: o configurado, o do imageio-ffmpeg, ou o do PATH."""
    configured = os.environ.get("FFMPEG_BINARY")
    if configured:
        return configured
    try:
        import imageio_ffmpeg
    except ImportError:
        return "ffmpeg"
    return str(imageio_ffmpeg.get_ffmpeg_exe())


FFMPEG = _ffmpeg_binary()
FFMPEG_TIMEOUT_SECONDS = float(os.environ.get("FFMPEG_TIMEOUT_SECONDS", "15"))


def run_ffmpeg(input_bytes: bytes, output_args: list[str], out_name: str) -> bytes:
    """Converte áudio com ffmpeg, gravando em arquivo real (headers corretos).

    `output_args` são as flags de saída (codec, taxa, canais, formato); `out_name`
    é o nome do arquivo de saída (a extensão orienta o container). Retorna os bytes
    do arquivo convertido.
    """
    if shutil.which(FFMPEG) is None:
        raise CpqdError(
            f"'{FFMPEG}' não encontrado: instale o ffmpeg para usar o CPQD "
            "(conversão de áudio)."
        )
    with tempfile.TemporaryDirectory() as folder:
        source = Path(folder) / "entrada"
        target = Path(folder) / out_name
        source.write_bytes(input_bytes)
        cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source)]
        cmd += output_args + [str(target)]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=FFMPEG_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as exc:
            raise CpqdError("Tempo esgotado ao converter o áudio (ffmpeg).") from exc
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.decode(errors="replace").strip()
            raise CpqdError(f"Falha ao converter o áudio: {detail or 'erro no ffmpeg'}") from exc
        if not target.exists() or target.stat().st_size == 0:
            raise CpqdError("Conversão de áudio não produziu nada.")
        return target.read_bytes()
