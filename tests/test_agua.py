"""Água como ingrediente neutro: vem pronta (register + garantia na listagem) e
entra nas receitas com custo 0. Roda em sqlite in-memory."""
import pytest


@pytest.fixture(scope="module")
def auth(client):
    r = client.post("/auth/register", json={
        "nome": "Agua", "email": "agua@test.com", "senha": "senha12345",
    })
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _agua_id(client, auth):
    r = client.get("/ingredientes/", headers=auth)
    assert r.status_code == 200, r.text
    aguas = [i for i in r.json() if i["nome"].strip().lower() == "água"]
    assert len(aguas) == 1, "deve haver exatamente uma Água"
    return aguas[0]


def test_agua_vem_pronta_e_sem_custo(client, auth):
    agua = _agua_id(client, auth)
    assert agua["custo_unitario_atual"] in (None, 0, 0.0)


def test_agua_nao_duplica_em_varias_listagens(client, auth):
    for _ in range(3):
        r = client.get("/ingredientes/", headers=auth)
        aguas = [i for i in r.json() if i["nome"].strip().lower() == "água"]
        assert len(aguas) == 1


def test_agua_entra_na_receita_com_custo_zero(client, auth):
    agua = _agua_id(client, auth)
    # Ingrediente pago, pra a receita ter algum custo > 0 além da água
    r = client.post("/ingredientes/", headers=auth, json={
        "nome": "açúcar", "unidade": "g", "fator_correcao": 1.0,
        "preco_inicial": {"preco": 10.0, "quantidade_embalagem": 1000, "data_compra": "2026-06-01T12:00:00"},
    })
    assert r.status_code == 201, r.text
    acucar_id = r.json()["id"]

    r = client.post("/receitas/", headers=auth, json={
        "nome": "Calda", "rendimento_g": 1000,
        "ingredientes": [
            {"ingrediente_id": acucar_id, "quantidade_g": 500},   # 0,01 × 500 = 5,00
            {"ingrediente_id": agua["id"], "quantidade_g": 250},  # água = 0
        ],
        "etapas_mo": [],
    })
    assert r.status_code == 201, r.text
    # Só o açúcar entra no custo; a água soma 0
    assert r.json()["custo_mp_total"] == pytest.approx(5.0)
