"""Conversão ingrediente↔embalagem: copia histórico de preços e desativa o original."""
import pytest


@pytest.fixture(scope="module")
def auth(client):
    r = client.post("/auth/register", json={
        "nome": "Conv", "email": "conversao@test.com", "senha": "senha12345",
    })
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_ingrediente_para_embalagem(client, auth):
    # caixa cadastrada errado como ingrediente, com 2 preços no histórico
    r = client.post("/ingredientes/", headers=auth, json={
        "nome": "caixa de bolo", "unidade": "unid", "fator_correcao": 1.0,
        "preco_inicial": {"preco": 50.0, "quantidade_embalagem": 25, "data_compra": "2026-06-01T12:00:00"},
    })
    assert r.status_code == 201, r.text
    ing_id = r.json()["id"]
    r = client.post(f"/ingredientes/{ing_id}/precos", headers=auth, json={
        "preco": 60.0, "quantidade_embalagem": 25, "data_compra": "2026-06-10T12:00:00",
    })
    assert r.status_code == 201, r.text

    r = client.post(f"/ingredientes/{ing_id}/converter-em-embalagem", headers=auth)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["precos_copiados"] == 2

    # sumiu da lista de ingredientes, apareceu na de embalagens com custo do preço mais recente
    nomes_ing = [i["nome"] for i in client.get("/ingredientes/", headers=auth).json()]
    assert "caixa de bolo" not in nomes_ing
    embs = client.get("/embalagens/", headers=auth).json()
    emb = next(e for e in embs if e["id"] == body["embalagem_id"])
    assert emb["nome"] == "caixa de bolo"
    assert emb["custo_unitario_atual"] == pytest.approx(60.0 / 25)

    # idempotência: converter de novo o original (inativo) → 404
    assert client.post(f"/ingredientes/{ing_id}/converter-em-embalagem", headers=auth).status_code == 404


def test_embalagem_para_ingrediente(client, auth):
    r = client.post("/embalagens/", headers=auth, json={
        "nome": "papel manteiga", "unidade": "unid",
        "preco_inicial": {"preco": 12.0, "quantidade_embalagem": 40, "data_compra": "2026-06-05T12:00:00"},
    })
    assert r.status_code == 201, r.text
    emb_id = r.json()["id"]

    r = client.post(f"/embalagens/{emb_id}/converter-em-ingrediente", headers=auth)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["precos_copiados"] == 1

    nomes_emb = [e["nome"] for e in client.get("/embalagens/", headers=auth).json()]
    assert "papel manteiga" not in nomes_emb
    ings = client.get("/ingredientes/", headers=auth).json()
    ing = next(i for i in ings if i["id"] == body["ingrediente_id"])
    assert ing["fator_correcao"] == 1.0
    assert ing["custo_unitario_atual"] == pytest.approx(12.0 / 40)


def test_conversao_respeita_tenant(client, auth):
    # usuário B não converte ingrediente do usuário A
    r = client.post("/auth/register", json={
        "nome": "Outro", "email": "outro-conv@test.com", "senha": "senha12345",
    })
    auth_b = {"Authorization": f"Bearer {r.json()['access_token']}"}
    r = client.post("/ingredientes/", headers=auth, json={
        "nome": "fita decorativa", "unidade": "unid", "fator_correcao": 1.0,
    })
    ing_id = r.json()["id"]
    assert client.post(f"/ingredientes/{ing_id}/converter-em-embalagem", headers=auth_b).status_code == 404
