import logging
import threading
import time
import uuid
from collections import defaultdict

from fastapi import HTTPException

logger = logging.getLogger("quantum")

# Cliente Redis compartilhado, resolvido preguiçosamente uma única vez.
_redis_client = None
_redis_resolvido = False
_redis_lock = threading.Lock()


def get_redis():
    """Cliente Redis compartilhado (lazy singleton). Retorna None quando
    `REDIS_URL` não está configurada — nesse caso o rate limit cai para o modo
    em memória (só consistente com 1 worker uvicorn / sem réplicas).

    Se `REDIS_URL` estiver setada mas o Redis estiver inacessível no boot, loga
    um aviso e degrada para memória até o próximo restart (fail-open)."""
    global _redis_client, _redis_resolvido
    if _redis_resolvido:
        return _redis_client
    with _redis_lock:
        if _redis_resolvido:
            return _redis_client
        _redis_resolvido = True
        from app.database import get_settings  # import tardio: evita ciclo
        url = get_settings().redis_url
        if not url:
            _redis_client = None
            return None
        try:
            import redis  # dependência só é exigida quando REDIS_URL existe
            client = redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
            client.ping()
            _redis_client = client
            logger.info("Rate limiter: usando Redis")
        except Exception as exc:  # noqa: BLE001 — qualquer falha degrada p/ memória
            logger.warning("REDIS_URL configurada mas indisponível (%s) — rate limit em memória", exc)
            _redis_client = None
        return _redis_client


class RateLimiter:
    """Rate limit de janela deslizante por chave.

    Backend Redis (sorted set por chave) quando disponível — consistente entre
    múltiplos workers/réplicas. Sem Redis, usa um dict em memória (válido só com
    1 worker). A escolha é por-chamada: se o Redis cair em runtime, faz fallback
    para memória naquela chamada."""

    def __init__(self, max_chamadas: int, janela_s: int, detail: str):
        self.max_chamadas = max_chamadas
        self.janela_s = janela_s
        self.detail = detail
        self._hits: dict = defaultdict(list)
        self._lock = threading.Lock()

    def checar(self, chave) -> None:
        client = get_redis()
        if client is not None:
            try:
                self._checar_redis(client, chave)
                return
            except HTTPException:
                raise  # 429 legítimo — não é falha do Redis
            except Exception as exc:  # noqa: BLE001 — erro de Redis → fallback memória
                logger.warning("Rate limit via Redis falhou (%s) — fallback em memória", exc)
        self._checar_memoria(chave)

    def _checar_redis(self, client, chave) -> None:
        agora = time.time()
        key = f"ratelimit:{self.max_chamadas}:{self.janela_s}:{chave}"
        membro = f"{agora}:{uuid.uuid4().hex}"  # único: evita colisão no mesmo instante
        pipe = client.pipeline()
        pipe.zremrangebyscore(key, 0, agora - self.janela_s)  # expira a janela
        pipe.zadd(key, {membro: agora})
        pipe.zcard(key)
        pipe.expire(key, self.janela_s)
        _, _, count, _ = pipe.execute()
        if count > self.max_chamadas:
            # Desfaz a própria marca para não punir além da janela (paridade com
            # o modo memória, que não registra tentativas rejeitadas).
            client.zrem(key, membro)
            raise HTTPException(status_code=429, detail=self.detail)

    def _checar_memoria(self, chave) -> None:
        agora = time.time()
        with self._lock:
            # Expurgo periódico: sem isso o dict cresce uma entrada por chave
            # (IP/user) para sempre — vazamento de memória com IPs rotativos
            if len(self._hits) > 10_000:
                self._hits = defaultdict(
                    list,
                    {k: v for k, v in self._hits.items() if v and agora - v[-1] < self.janela_s},
                )
            recentes = [t for t in self._hits[chave] if agora - t < self.janela_s]
            if len(recentes) >= self.max_chamadas:
                raise HTTPException(status_code=429, detail=self.detail)
            recentes.append(agora)
            self._hits[chave] = recentes
