"""Testes do endpoint POST /ia/estimar-precos (estimativa de preço por IA).

A chamada à Anthropic é mockada — validamos o contrato do endpoint:
parsing, normalização de unidade, descarte de linhas inválidas e auth.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from app.routers import ia


@pytest.fixture(scope="module")
def auth(client):
    r = client.post("/auth/register", json={
        "nome": "Est", "email": "estimativa@test.com", "senha": "senha12345",
    })
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _fake_resp(itens):
    m = MagicMock()
    m.content = [MagicMock(text=json.dumps({"itens": itens}))]
    return m


def test_estimar_precos_feliz(client, auth):
    itens = [{"nome": "açúcar refinado", "preco": 5.0, "quantidade_embalagem": 1, "unidade": "kg"}]
    with patch.object(ia, "_client") as m:
        m.return_value.messages.create.return_value = _fake_resp(itens)
        r = client.post("/ia/estimar-precos", headers=auth,
                        json={"ingredientes": [{"nome": "açúcar refinado"}]})
    assert r.status_code == 200
    data = r.json()["itens"]
    assert len(data) == 1
    assert data[0]["preco"] == 5.0
    assert data[0]["unidade"] == "kg"
    assert data[0]["fonte"] == "estimativa"


def test_estimar_precos_normaliza_unidade_e_descarta_invalidos(client, auth):
    itens = [
        {"nome": "ovo", "preco": 9.0, "quantidade_embalagem": 12, "unidade": "duzia"},  # unidade inválida
        {"nome": "vago", "preco": None, "quantidade_embalagem": None, "unidade": None},  # preço null
        {"nome": "negativo", "preco": -1, "quantidade_embalagem": 1, "unidade": "kg"},   # preço <= 0
    ]
    with patch.object(ia, "_client") as m:
        m.return_value.messages.create.return_value = _fake_resp(itens)
        r = client.post("/ia/estimar-precos", headers=auth,
                        json={"ingredientes": [{"nome": "ovo"}, {"nome": "vago"}, {"nome": "negativo"}]})
    assert r.status_code == 200
    data = r.json()["itens"]
    assert len(data) == 1  # só o ovo sobrou
    assert data[0]["nome"] == "ovo"
    assert data[0]["unidade"] == "unid"  # "duzia" normalizado


def test_estimar_precos_body_vazio_422(client, auth):
    r = client.post("/ia/estimar-precos", headers=auth, json={"ingredientes": []})
    assert r.status_code == 422


def test_estimar_precos_exige_auth(client):
    r = client.post("/ia/estimar-precos", json={"ingredientes": [{"nome": "x"}]})
    assert r.status_code == 401
