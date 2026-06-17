"""Colaboradores: CRUD, uso do valor_hora do colaborador no custo de mão de
obra (em vez do valor-hora padrão), retorno do colaborador_id e isolamento
entre tenants.

Roda em sqlite in-memory:

    DATABASE_URL=sqlite:// JWT_SECRET=test python -m pytest tests/test_colaboradores.py -v
"""
import pytest


@pytest.fixture(scope="module")
def auth(client):
    r = client.post("/auth/register", json={
        "nome": "Dona", "email": "colab@test.com", "senha": "senha12345",
    })
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_crud_colaborador(client, auth):
    # Cria
    r = client.post("/colaboradores/", headers=auth, json={"nome": "Ana", "valor_hora": 25.0})
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert r.json()["nome"] == "Ana"
    assert r.json()["valor_hora"] == 25.0
    assert r.json()["ativo"] is True

    # Lista
    r = client.get("/colaboradores/", headers=auth)
    assert r.status_code == 200
    assert any(c["id"] == cid for c in r.json())

    # Atualiza
    r = client.put(f"/colaboradores/{cid}", headers=auth, json={"valor_hora": 30.0})
    assert r.status_code == 200, r.text
    assert r.json()["valor_hora"] == 30.0
    assert r.json()["nome"] == "Ana"  # não mexeu no nome

    # Deleta (soft) → some da listagem
    r = client.delete(f"/colaboradores/{cid}", headers=auth)
    assert r.status_code == 204
    r = client.get("/colaboradores/", headers=auth)
    assert all(c["id"] != cid for c in r.json())


def test_receita_usa_valor_hora_do_colaborador(client, auth):
    # Valor-hora padrão = 10/h (config do usuário)
    r = client.put("/auth/configuracao", headers=auth, json={"valor_hora_padrao": 10.0})
    assert r.status_code == 200, r.text

    # Colaborador com valor-hora 60/h → 1,00 por minuto
    r = client.post("/colaboradores/", headers=auth, json={"nome": "Chef", "valor_hora": 60.0})
    cid = r.json()["id"]

    # Etapa de 30 min com o colaborador → 30,00 (e NÃO 5,00 do padrão)
    r = client.post("/receitas/", headers=auth, json={
        "nome": "Bolo", "rendimento_g": 1000, "ingredientes": [],
        "etapas_mo": [{"descricao": "bater", "tempo_min": 30, "colaborador_id": cid}],
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["custo_mo_total"] == pytest.approx(30.0)
    etapa = body["etapas_mo"][0]
    assert etapa["colaborador_id"] == cid
    assert etapa["colaborador_nome"] == "Chef"
    assert etapa["valor_hora"] == pytest.approx(60.0)


def test_etapa_sem_colaborador_usa_padrao(client, auth):
    client.put("/auth/configuracao", headers=auth, json={"valor_hora_padrao": 20.0})
    r = client.post("/receitas/", headers=auth, json={
        "nome": "Torta", "rendimento_g": 500, "ingredientes": [],
        "etapas_mo": [{"descricao": "montar", "tempo_min": 30, "colaborador_id": None}],
    })
    assert r.status_code == 201, r.text
    # 20/h por 30 min = 10,00
    assert r.json()["custo_mo_total"] == pytest.approx(10.0)
    assert r.json()["etapas_mo"][0]["colaborador_id"] is None


def test_produto_devolve_colaborador_id(client, auth):
    r = client.post("/colaboradores/", headers=auth, json={"nome": "Aux", "valor_hora": 12.0})
    cid = r.json()["id"]
    r = client.post("/produtos/", headers=auth, json={
        "nome": "Kit festa", "preparacoes": [], "ingredientes": [], "embalagens": [],
        "mo_montagem": [{"descricao": "embalar", "tempo_min": 10, "colaborador_id": cid}],
    })
    assert r.status_code == 201, r.text
    mo = r.json()["mo_montagem"][0]
    assert mo["colaborador_id"] == cid
    assert mo["colaborador_nome"] == "Aux"


def test_colaborador_de_outro_tenant_bloqueado(client, auth):
    # Colaborador do usuário B
    rb = client.post("/auth/register", json={
        "nome": "Outro", "email": "outro-colab@test.com", "senha": "senha12345",
    })
    auth_b = {"Authorization": f"Bearer {rb.json()['access_token']}"}
    r = client.post("/colaboradores/", headers=auth_b, json={"nome": "Estranho", "valor_hora": 99.0})
    cid_b = r.json()["id"]

    # Usuário A (auth) tenta usar o colaborador de B numa receita → 404
    r = client.post("/receitas/", headers=auth, json={
        "nome": "Invasora", "rendimento_g": 100, "ingredientes": [],
        "etapas_mo": [{"descricao": "x", "tempo_min": 5, "colaborador_id": cid_b}],
    })
    assert r.status_code == 404, r.text
