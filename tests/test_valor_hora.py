"""Testes do endpoint POST /ia/sugerir-valor-hora (sugestão de valor-hora por IA).

A chamada à Anthropic é mockada — validamos o contrato do endpoint:
parsing, faixa opcional, atividade irreconhecível → 422 e auth.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from app.routers import ia


@pytest.fixture(scope="module")
def auth(client):
    r = client.post("/auth/register", json={
        "nome": "VH", "email": "valorhora@test.com", "senha": "senha12345",
    })
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _fake_resp(payload):
    m = MagicMock()
    m.content = [MagicMock(text=json.dumps(payload))]
    return m


def test_sugerir_valor_hora_feliz(client, auth):
    payload = {"valor_hora": 20.0, "faixa_min": 15.0, "faixa_max": 25.0,
               "explicacao": "Quem faz bolo caseiro costuma cobrar de R$ 15 a R$ 25 pela hora."}
    with patch.object(ia, "_client") as m:
        m.return_value.messages.create.return_value = _fake_resp(payload)
        r = client.post("/ia/sugerir-valor-hora", headers=auth, json={"atividade": "bolos caseiros"})
    assert r.status_code == 200
    d = r.json()
    assert d["valor_hora"] == 20.0
    assert d["faixa_min"] == 15.0 and d["faixa_max"] == 25.0
    assert d["fonte"] == "estimativa"
    assert "bolo" in d["explicacao"]


def test_sugerir_valor_hora_faixa_opcional(client, auth):
    # IA pode devolver só o valor — faixa/explicação viram null, não 500
    with patch.object(ia, "_client") as m:
        m.return_value.messages.create.return_value = _fake_resp({"valor_hora": 18})
        r = client.post("/ia/sugerir-valor-hora", headers=auth, json={"atividade": "marmitas"})
    assert r.status_code == 200
    d = r.json()
    assert d["valor_hora"] == 18.0
    assert d["faixa_min"] is None and d["explicacao"] is None


def test_sugerir_valor_hora_irreconhecivel_422(client, auth):
    # atividade sem sentido → IA devolve null → 422 com mensagem acionável
    with patch.object(ia, "_client") as m:
        m.return_value.messages.create.return_value = _fake_resp({"valor_hora": None})
        r = client.post("/ia/sugerir-valor-hora", headers=auth, json={"atividade": "xyzabc"})
    assert r.status_code == 422
    assert "Digite o valor direto" in r.json()["detail"]


def test_sugerir_valor_hora_valor_invalido_422(client, auth):
    with patch.object(ia, "_client") as m:
        m.return_value.messages.create.return_value = _fake_resp({"valor_hora": -5})
        r = client.post("/ia/sugerir-valor-hora", headers=auth, json={"atividade": "doces"})
    assert r.status_code == 422


def test_sugerir_valor_hora_atividade_vazia_422(client, auth):
    r = client.post("/ia/sugerir-valor-hora", headers=auth, json={"atividade": ""})
    assert r.status_code == 422


def test_sugerir_valor_hora_exige_auth(client):
    r = client.post("/ia/sugerir-valor-hora", json={"atividade": "bolos"})
    assert r.status_code == 401
