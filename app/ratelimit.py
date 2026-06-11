import threading
import time
from collections import defaultdict

from fastapi import HTTPException


class RateLimiter:
    """Rate limit em memória (1 worker uvicorn) — janela deslizante por chave."""

    def __init__(self, max_chamadas: int, janela_s: int, detail: str):
        self.max_chamadas = max_chamadas
        self.janela_s = janela_s
        self.detail = detail
        self._hits: dict = defaultdict(list)
        self._lock = threading.Lock()

    def checar(self, chave) -> None:
        agora = time.time()
        with self._lock:
            recentes = [t for t in self._hits[chave] if agora - t < self.janela_s]
            if len(recentes) >= self.max_chamadas:
                raise HTTPException(status_code=429, detail=self.detail)
            recentes.append(agora)
            self._hits[chave] = recentes
