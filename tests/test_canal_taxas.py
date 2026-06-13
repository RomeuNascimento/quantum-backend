"""Validação da soma de taxas do canal e da viabilidade da margem.

Antes, um canal com taxas somando ≥ 100% (ou margem + taxas ≥ 100%) fazia o
preço sugerido cair para R$ 0 silenciosamente. Agora o backend rejeita com erro
explícito. Roda em sqlite in-memory:

    DATABASE_URL=sqlite:// JWT_SECRET=test python -m pytest tests/test_canal_taxas.py -v
"""
import pytest


@pytest.fixture(scope="module")
def auth(client):
    r = client.post("/auth/register", json={
        "nome": "Taxas", "email": "taxas@test.com", "senha": "senha12345",
    })
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_criar_canal_taxas_validas(client, auth):
    r = client.post("/precificacao/canais", headers=auth, json={
        "nome": "Loja", "taxa_plataforma_pct": 40, "taxa_cartao_pct": 30, "imposto_pct": 20,
    })
    assert r.status_code == 201, r.text  # soma 90 < 100


def test_criar_canal_taxas_somam_100_ou_mais(client, auth):
    r = client.post("/precificacao/canais", headers=auth, json={
        "nome": "Abusivo", "taxa_plataforma_pct": 50, "taxa_cartao_pct": 30, "imposto_pct": 20,
    })
    assert r.status_code == 422, r.text  # soma 100 → Pydantic rejeita
    assert "100" in r.text


def test_atualizar_canal_estoura_soma(client, auth):
    r = client.post("/precificacao/canais", headers=auth, json={
        "nome": "Editável", "taxa_plataforma_pct": 10, "taxa_cartao_pct": 10, "imposto_pct": 10,
    })
    assert r.status_code == 201, r.text
    canal_id = r.json()["id"]

    # Empurrar imposto para que a soma chegue a 100
    r = client.put(f"/precificacao/canais/{canal_id}", headers=auth, json={"imposto_pct": 85})
    assert r.status_code == 400, r.text
    assert "100" in r.text


def _produto_minimo(client, auth):
    r = client.post("/produtos/", headers=auth, json={
        "nome": "Produto teste", "preparacoes": [], "ingredientes": [],
        "embalagens": [], "mo_montagem": [],
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_preco_margem_mais_taxas_estoura(client, auth):
    prod_id = _produto_minimo(client, auth)
    r = client.post("/precificacao/canais", headers=auth, json={
        "nome": "Canal 90", "taxa_plataforma_pct": 40, "taxa_cartao_pct": 30, "imposto_pct": 20,
    })
    assert r.status_code == 201, r.text
    canal_id = r.json()["id"]

    # margem 15 + taxas 90 = 105 ≥ 100 → preço sugerido seria R$ 0
    r = client.post(f"/precificacao/produtos/{prod_id}/precos", headers=auth, json={
        "canal_id": canal_id, "margem_pct": 15,
    })
    assert r.status_code == 400, r.text
    assert "100" in r.text

    # margem 5 + taxas 90 = 95 < 100 → aceito
    r = client.post(f"/precificacao/produtos/{prod_id}/precos", headers=auth, json={
        "canal_id": canal_id, "margem_pct": 5,
    })
    assert r.status_code in (200, 201), r.text
