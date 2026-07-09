"""Relatório de histórico de preços dos insumos (GET /ingredientes/relatorio-precos).

Roda em sqlite in-memory:
    DATABASE_URL=sqlite:// JWT_SECRET=test python -m pytest tests/test_relatorio_precos.py -v
"""
import pytest


@pytest.fixture(scope="module")
def auth(client):
    r = client.post("/auth/register", json={
        "nome": "Hist", "email": "hist@test.com", "senha": "senha12345",
    })
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_relatorio_precos(client, auth):
    # Ingrediente com 1º preço: R$ 10,00 por 1000 g → 0,010/g
    r = client.post("/ingredientes/", headers=auth, json={
        "nome": "leite condensado", "unidade": "g", "fator_correcao": 1.0,
        "preco_inicial": {"preco": 10.0, "quantidade_embalagem": 1000,
                          "data_compra": "2026-06-01T12:00:00"},
    })
    assert r.status_code == 201, r.text
    ing_id = r.json()["id"]

    # 2º preço mais recente: R$ 12,00 por 1000 g → 0,012/g (alta de 20%)
    r = client.post(f"/ingredientes/{ing_id}/precos", headers=auth, json={
        "preco": 12.0, "quantidade_embalagem": 1000, "data_compra": "2026-07-01T12:00:00",
    })
    assert r.status_code == 201, r.text

    r = client.get("/ingredientes/relatorio-precos", headers=auth)
    assert r.status_code == 200, r.text
    dados = r.json()
    item = next((x for x in dados if x["id"] == ing_id), None)
    assert item is not None, "ingrediente deveria aparecer no relatório"
    assert item["n_registros"] == 2
    assert item["custo_atual"] == pytest.approx(0.012)
    # ponto mais recente primeiro
    assert item["pontos"][0]["custo_unitario"] == pytest.approx(0.012)
    assert item["pontos"][-1]["custo_unitario"] == pytest.approx(0.010)
    # variação do 1º registro (0,010) para o atual (0,012) = +20%
    assert item["variacao_pct"] == pytest.approx(20.0)


def test_relatorio_ignora_sem_preco(client, auth):
    # Ingrediente sem nenhum preço (ex.: Água, ou recém-criado) não entra no relatório
    r = client.post("/ingredientes/", headers=auth, json={
        "nome": "sal sem preco", "unidade": "g", "fator_correcao": 1.0,
    })
    assert r.status_code == 201, r.text
    sem_preco_id = r.json()["id"]
    r = client.get("/ingredientes/relatorio-precos", headers=auth)
    assert r.status_code == 200, r.text
    ids = [x["id"] for x in r.json()]
    assert sem_preco_id not in ids
