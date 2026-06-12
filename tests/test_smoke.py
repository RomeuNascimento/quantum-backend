"""Smoke test do fluxo completo: register → ingrediente+preço → embalagem+preço
→ receita → produto → precificação → relatório de margem.

Roda em sqlite in-memory (sem PostgreSQL): valida a lógica e a matemática dos
cálculos, não as migrations. Executar com:

    DATABASE_URL=sqlite:// JWT_SECRET=test python -m pytest tests/ -v
"""
import pytest


@pytest.fixture(scope="module")
def auth(client):
    r = client.post("/auth/register", json={
        "nome": "Teste", "email": "smoke@test.com", "senha": "senha12345",
    })
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_fluxo_completo(client, auth):
    # Ingrediente com preço: R$ 12,00 por 1000 g → 0,012/g
    r = client.post("/ingredientes/", headers=auth, json={
        "nome": "chocolate em pó", "unidade": "g", "fator_correcao": 1.0,
        "preco_inicial": {"preco": 12.0, "quantidade_embalagem": 1000,
                          "data_compra": "2026-06-01T12:00:00"},
    })
    assert r.status_code == 201, r.text
    ing_id = r.json()["id"]
    assert r.json()["custo_unitario_atual"] == pytest.approx(0.012)

    # Embalagem com preço: R$ 10,00 por 20 unid → 0,50/unid
    r = client.post("/embalagens/", headers=auth, json={"nome": "caixa", "tipo": "caixa", "unidade": "unid"})
    assert r.status_code == 201, r.text
    emb_id = r.json()["id"]
    r = client.post(f"/embalagens/{emb_id}/precos", headers=auth, json={
        "preco": 10.0, "quantidade_embalagem": 20, "data_compra": "2026-06-01T12:00:00",
    })
    assert r.status_code == 201, r.text

    # Receita: 500 g de chocolate (custo MP = 0,012 × 500 = 6,00), rende 1000 g
    r = client.post("/receitas/", headers=auth, json={
        "nome": "Brigadeiro base", "rendimento_g": 1000,
        "ingredientes": [{"ingrediente_id": ing_id, "quantidade_g": 500}],
        "etapas_mo": [],
    })
    assert r.status_code == 201, r.text
    rec_id = r.json()["id"]
    assert r.json()["custo_mp_total"] == pytest.approx(6.0)

    # Produto: usa 500 g da receita (6,00 × 0,5 = 3,00) + 1 caixa (0,50) = 3,50
    r = client.post("/produtos/", headers=auth, json={
        "nome": "Cento de brigadeiro",
        "preparacoes": [{"receita_id": rec_id, "quantidade_g": 500}],
        "ingredientes": [],
        "embalagens": [{"embalagem_id": emb_id, "quantidade": 1}],
        "mo_montagem": [],
    })
    assert r.status_code == 201, r.text
    prod_id = r.json()["id"]
    assert r.json()["custo_total"] == pytest.approx(3.5)

    # Precificação no canal iFood (pré-cadastrado): margem 30%
    r = client.get("/precificacao/canais", headers=auth)
    assert r.status_code == 200, r.text
    canal_id = next(c["id"] for c in r.json() if c["nome"] == "iFood")
    r = client.post(f"/precificacao/produtos/{prod_id}/precos", headers=auth, json={
        "canal_id": canal_id, "margem_pct": 30.0,
    })
    assert r.status_code in (200, 201), r.text
    # preço sugerido = 3,50 / (1 − 0,30 − 0,12 − 0,0299 − 0,06)
    esperado = 3.5 / (1 - 0.30 - 0.12 - 0.0299 - 0.06)
    r = client.get(f"/precificacao/produtos/{prod_id}/precos", headers=auth)
    assert r.status_code == 200, r.text
    preco = next(p for p in r.json() if p["canal_id"] == canal_id)
    assert preco["preco_sugerido"] == pytest.approx(esperado, rel=1e-4)

    # Relatório de margem inclui o produto
    r = client.get("/precificacao/relatorio-margem", headers=auth)
    assert r.status_code == 200, r.text
    nomes = [p["produto_nome"] for p in r.json()["produtos"]]
    assert "Cento de brigadeiro" in nomes


def test_register_nao_revela_email(client, auth):
    r = client.post("/auth/register", json={
        "nome": "Outro", "email": "smoke@test.com", "senha": "senha12345",
    })
    assert r.status_code == 400
    assert "já cadastrado" not in r.json()["detail"].lower()


def test_historico_custo(client, auth):
    r = client.get("/produtos/", headers=auth)
    prod_id = r.json()[0]["id"]
    r = client.get(f"/produtos/{prod_id}/historico-custo", headers=auth)
    assert r.status_code == 200, r.text
    pontos = r.json()["pontos"]
    assert pontos and pontos[-1]["custo"] == pytest.approx(3.5)
