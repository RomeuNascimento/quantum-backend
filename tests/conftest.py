"""Fixtures compartilhadas: TestClient com banco limpo por módulo.

O engine vive em tests/db.py (módulo neutro) para que os testes possam
importar TestingSession sem reimportar este conftest.
"""
import pytest
from fastapi.testclient import TestClient

from tests.db import engine, TestingSession
from app.database import Base, get_db
from app.main import app


def _override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(scope="module", autouse=True)
def _reset_rate_limiters():
    """Os rate limiters de login/register/IA são globais em memória e o seu
    estado vaza entre módulos de teste (mesmo IP), podendo disparar 429 em
    testes que não têm a ver com rate limiting. Zera os buckets a cada módulo
    para a suíte ficar independente de ordem."""
    from app.auth.router import _login_limiter, _register_limiter
    from app.routers.ia import _ia_limiter
    for limiter in (_login_limiter, _register_limiter, _ia_limiter):
        limiter._hits.clear()
    yield


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)
