"""Testes do financeiro: CRUD de lançamentos, resumo mensal, multi-tenant e
endpoints de IA (interpretar texto / ler comprovante) com a Anthropic mockada.

Rodar: DATABASE_URL=sqlite:// JWT_SECRET=test python -m pytest tests/test_financeiro.py -q
"""
import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.routers import ia


@pytest.fixture(scope="module")
def auth(client):
    r = client.post("/auth/register", json={
        "nome": "Fin", "email": "financeiro@test.com", "senha": "senha12345",
    })
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def auth_outro(client):
    r = client.post("/auth/register", json={
        "nome": "Outro", "email": "financeiro2@test.com", "senha": "senha12345",
    })
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _fake_resp(payload: dict):
    m = MagicMock()
    m.content = [MagicMock(text=json.dumps(payload))]
    return m


# ─── CRUD + resumo ────────────────────────────────────────────────────────────

def test_criar_listar_e_resumo(client, auth):
    hoje = date.today().isoformat()
    mes = hoje[:7]

    r = client.post("/financeiro/lancamentos", headers=auth, json={
        "tipo": "entrada", "valor": 100.0, "descricao": "20 brigadeiros",
        "categoria": "venda", "data": hoje,
    })
    assert r.status_code == 201, r.text
    assert r.json()["tipo"] == "entrada"
    assert r.json()["data"] == hoje

    r = client.post("/financeiro/lancamentos", headers=auth, json={
        "tipo": "saida", "valor": 30.0, "descricao": "mercado", "categoria": "insumos",
    })
    assert r.status_code == 201  # sem data → hoje

    r = client.post("/financeiro/lancamentos", headers=auth, json={
        "tipo": "saida", "valor": 10.0, "descricao": "caixas", "categoria": "embalagem",
    })
    assert r.status_code == 201

    r = client.get(f"/financeiro/lancamentos?mes={mes}", headers=auth)
    assert r.status_code == 200
    assert len(r.json()) == 3

    r = client.get(f"/financeiro/resumo?mes={mes}", headers=auth)
    assert r.status_code == 200
    resumo = r.json()
    assert resumo["entradas"] == 100.0
    assert resumo["saidas"] == 40.0
    assert resumo["sobra"] == 60.0
    assert resumo["quantidade"] == 3
    cats = {c["categoria"]: c["total"] for c in resumo["saidas_por_categoria"]}
    assert cats == {"insumos": 30.0, "embalagem": 10.0}


def test_mes_sem_lancamentos_e_mes_invalido(client, auth):
    r = client.get("/financeiro/resumo?mes=2000-01", headers=auth)
    assert r.status_code == 200
    assert r.json()["quantidade"] == 0
    assert r.json()["sobra"] == 0

    r = client.get("/financeiro/resumo?mes=2026-13", headers=auth)
    assert r.status_code == 422
    r = client.get("/financeiro/lancamentos?mes=banana", headers=auth)
    assert r.status_code == 422


def test_valor_invalido_rejeitado(client, auth):
    r = client.post("/financeiro/lancamentos", headers=auth, json={
        "tipo": "saida", "valor": 0,
    })
    assert r.status_code == 422
    r = client.post("/financeiro/lancamentos", headers=auth, json={
        "tipo": "banana", "valor": 10,
    })
    assert r.status_code == 422


def test_origem_desconhecida_vira_manual(client, auth):
    r = client.post("/financeiro/lancamentos", headers=auth, json={
        "tipo": "saida", "valor": 5.0, "origem": "hacker",
    })
    assert r.status_code == 201
    assert r.json()["origem"] == "manual"
    client.delete(f"/financeiro/lancamentos/{r.json()['id']}", headers=auth)


def test_multi_tenant_e_delete(client, auth, auth_outro):
    # o outro usuário não vê nada
    r = client.get("/financeiro/lancamentos", headers=auth_outro)
    assert r.status_code == 200
    assert r.json() == []

    # nem deleta lançamento alheio
    r = client.get("/financeiro/lancamentos", headers=auth)
    lanc_id = r.json()[0]["id"]
    r = client.delete(f"/financeiro/lancamentos/{lanc_id}", headers=auth_outro)
    assert r.status_code == 404

    # o dono deleta
    r = client.delete(f"/financeiro/lancamentos/{lanc_id}", headers=auth)
    assert r.status_code == 204


# ─── IA: interpretar texto ────────────────────────────────────────────────────

def test_interpretar_lancamento(client, auth):
    payload = {"lancamentos": [
        {"tipo": "saida", "valor": 80.0, "descricao": "mercado", "categoria": "insumos", "data": None},
        {"tipo": "saida", "valor": 110.0, "descricao": "gás", "categoria": "contas", "data": "2026-08-15"},
        {"tipo": "saida", "valor": None, "descricao": "sem valor", "categoria": None, "data": None},  # descartado
        {"tipo": "saida", "valor": 5.0, "descricao": "x", "categoria": "outros", "data": "15/08"},     # data inválida → None
    ]}
    with patch.object(ia, "_client") as m:
        m.return_value.messages.create.return_value = _fake_resp(payload)
        r = client.post("/ia/interpretar-lancamento", headers=auth,
                        json={"texto": "mercado 80 e gás 110"})
    assert r.status_code == 200, r.text
    lancs = r.json()["lancamentos"]
    assert len(lancs) == 3
    assert lancs[0]["valor"] == 80.0
    assert lancs[1]["data"] == "2026-08-15"
    assert lancs[2]["data"] is None


def test_interpretar_lancamento_nada_identificado(client, auth):
    with patch.object(ia, "_client") as m:
        m.return_value.messages.create.return_value = _fake_resp({"lancamentos": []})
        r = client.post("/ia/interpretar-lancamento", headers=auth, json={"texto": "oi tudo bem"})
    assert r.status_code == 200
    assert r.json()["lancamentos"] == []


def test_interpretar_usa_modelo_financeiro(client, auth):
    with patch.object(ia, "_client") as m:
        m.return_value.messages.create.return_value = _fake_resp({"lancamentos": []})
        r = client.post("/ia/interpretar-lancamento", headers=auth, json={"texto": "abc"})
        assert r.status_code == 200
        kwargs = m.return_value.messages.create.call_args.kwargs
        assert kwargs["model"] == "claude-haiku-4-5"  # default barato, não o ANTHROPIC_MODEL


# ─── IA: comprovante ──────────────────────────────────────────────────────────

PNG_FAKE = b"\x89PNG\r\n\x1a\n" + b"0" * 100


def test_comprovante_feliz(client, auth):
    payload = {"tipo": "entrada", "valor": 100.0, "contraparte": "Maria Souza",
               "data": "2026-08-16", "descricao": "Pix de Maria Souza"}
    with patch.object(ia, "_client") as m:
        m.return_value.messages.create.return_value = _fake_resp(payload)
        r = client.post("/ia/comprovante", headers=auth,
                        files={"file": ("pix.png", PNG_FAKE, "image/png")})
    assert r.status_code == 200, r.text
    lanc = r.json()["lancamento"]
    assert lanc["tipo"] == "entrada"
    assert lanc["valor"] == 100.0
    assert lanc["contraparte"] == "Maria Souza"


def test_comprovante_ilegivel_422(client, auth):
    with patch.object(ia, "_client") as m:
        m.return_value.messages.create.return_value = _fake_resp({"valor": None})
        r = client.post("/ia/comprovante", headers=auth,
                        files={"file": ("x.png", PNG_FAKE, "image/png")})
    assert r.status_code == 422


def test_ia_financeiro_exige_auth(client):
    r = client.post("/ia/interpretar-lancamento", json={"texto": "mercado 80"})
    assert r.status_code in (401, 403)
