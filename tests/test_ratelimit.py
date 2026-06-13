"""RateLimiter — backend Redis (janela deslizante por sorted set) e fallback
em memória. Usa fakeredis para o caminho Redis. Roda em sqlite in-memory:

    DATABASE_URL=sqlite:// JWT_SECRET=test python -m pytest tests/test_ratelimit.py -v
"""
import fakeredis
import pytest
from fastapi import HTTPException

from app import ratelimit
from app.ratelimit import RateLimiter


def test_fallback_memoria_quando_sem_redis(monkeypatch):
    monkeypatch.setattr(ratelimit, "get_redis", lambda: None)
    rl = RateLimiter(2, 60, "limite memória")
    rl.checar("ip-a")
    rl.checar("ip-a")
    with pytest.raises(HTTPException) as exc:
        rl.checar("ip-a")
    assert exc.value.status_code == 429
    # Outra chave tem o próprio orçamento
    rl.checar("ip-b")


def test_redis_bloqueia_apos_o_limite(monkeypatch):
    fake = fakeredis.FakeStrictRedis()
    monkeypatch.setattr(ratelimit, "get_redis", lambda: fake)
    rl = RateLimiter(3, 60, "limite redis")
    for _ in range(3):
        rl.checar("ip1")  # 3 permitidas
    with pytest.raises(HTTPException) as exc:
        rl.checar("ip1")  # 4ª bloqueia
    assert exc.value.status_code == 429


def test_redis_isola_por_chave(monkeypatch):
    fake = fakeredis.FakeStrictRedis()
    monkeypatch.setattr(ratelimit, "get_redis", lambda: fake)
    rl = RateLimiter(1, 60, "limite")
    rl.checar("ipX")
    with pytest.raises(HTTPException):
        rl.checar("ipX")
    # Chave diferente não foi afetada
    rl.checar("ipY")


def test_redis_rejeicao_nao_estende_punicao(monkeypatch):
    """Uma tentativa rejeitada não deve consumir orçamento futuro: o membro é
    removido (zrem), então o zcard volta ao teto, não acima."""
    fake = fakeredis.FakeStrictRedis()
    monkeypatch.setattr(ratelimit, "get_redis", lambda: fake)
    rl = RateLimiter(2, 60, "limite")
    rl.checar("ip")
    rl.checar("ip")
    for _ in range(3):  # várias rejeições seguidas
        with pytest.raises(HTTPException):
            rl.checar("ip")
    key = "ratelimit:2:60:ip"
    assert fake.zcard(key) == 2  # nunca passou do teto


def test_redis_indisponivel_em_runtime_cai_para_memoria(monkeypatch):
    """Se a operação no Redis estourar exceção (não-HTTP), faz fallback para a
    contagem em memória em vez de derrubar a request."""
    class RedisQuebrado:
        def pipeline(self):
            raise ConnectionError("redis caiu")

    monkeypatch.setattr(ratelimit, "get_redis", lambda: RedisQuebrado())
    rl = RateLimiter(1, 60, "limite")
    rl.checar("ip")  # cai para memória, conta 1
    with pytest.raises(HTTPException) as exc:
        rl.checar("ip")  # memória bloqueia a 2ª
    assert exc.value.status_code == 429
