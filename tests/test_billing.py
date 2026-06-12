"""Testes do billing: status_efetivo, endpoint /billing/status e paywall (402).

Roda em sqlite in-memory, sem chamadas ao Stripe — testa apenas a lógica de
status e o enforcement do paywall nas rotas de negócio. Executar com:

    DATABASE_URL=sqlite:// JWT_SECRET=test python -m pytest tests/ -v
"""
from datetime import datetime, timedelta

import pytest

from app.models.models import User
from app.routers.billing import status_efetivo
from tests.db import TestingSession


@pytest.fixture(scope="module")
def auth(client):
    r = client.post("/auth/register", json={
        "nome": "Billing", "email": "billing@test.com", "senha": "senha12345",
    })
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _set_user(email, **campos):
    db = TestingSession()
    user = db.query(User).filter(User.email == email).first()
    for k, v in campos.items():
        setattr(user, k, v)
    db.commit()
    db.close()


# ---------- status_efetivo (lógica pura) ----------

def _user(status, criado_em=None, validade=None):
    return User(
        nome="x", email="x@x.com", senha_hash="x",
        assinatura_status=status,
        criado_em=criado_em or datetime.utcnow(),
        assinatura_validade=validade,
    )


def test_trial_dentro_do_prazo():
    assert status_efetivo(_user("trial")) == "trial"


def test_trial_expirado():
    antigo = datetime.utcnow() - timedelta(days=8)
    assert status_efetivo(_user("trial", criado_em=antigo)) == "vencida"


def test_ativa_sem_validade_e_cortesia():
    assert status_efetivo(_user("ativa")) == "ativa"


def test_ativa_com_validade_futura():
    futuro = datetime.utcnow() + timedelta(days=300)
    assert status_efetivo(_user("ativa", validade=futuro)) == "ativa"


def test_ativa_com_validade_passada():
    passado = datetime.utcnow() - timedelta(days=1)
    assert status_efetivo(_user("ativa", validade=passado)) == "vencida"


def test_status_desconhecido_e_vencida():
    assert status_efetivo(_user("vencida")) == "vencida"


# ---------- endpoint /billing/status + paywall ----------

def test_status_endpoint_trial(client, auth):
    r = client.get("/billing/status", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "trial"
    assert body["trial_fim"] is not None


def test_paywall_libera_trial(client, auth):
    r = client.get("/ingredientes/", headers=auth)
    assert r.status_code == 200


def test_paywall_bloqueia_vencida(client, auth):
    _set_user("billing@test.com", assinatura_status="vencida")
    r = client.get("/ingredientes/", headers=auth)
    assert r.status_code == 402
    # todas as rotas de negócio bloqueadas, não só ingredientes
    assert client.get("/produtos/", headers=auth).status_code == 402
    assert client.get("/receitas/", headers=auth).status_code == 402


def test_paywall_nao_bloqueia_billing_nem_auth(client, auth):
    # usuário vencido ainda acessa status (para ver a tela de assinatura) e o /me
    assert client.get("/billing/status", headers=auth).status_code == 200
    assert client.get("/auth/me", headers=auth).status_code == 200


def test_paywall_libera_apos_reativacao(client, auth):
    _set_user(
        "billing@test.com",
        assinatura_status="ativa",
        assinatura_validade=datetime.utcnow() + timedelta(days=365),
    )
    assert client.get("/ingredientes/", headers=auth).status_code == 200
    body = client.get("/billing/status", headers=auth).json()
    assert body["status"] == "ativa"
