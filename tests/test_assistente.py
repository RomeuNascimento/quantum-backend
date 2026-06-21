"""Testes do POST /assistente/salvar (gravação transacional do fluxo guiado).

Verifica: cria ingredientes novos + preços + receita + produto + precificação;
reusa ingrediente existente; custo do produto sai por porção; ovo (unid) usa
contagem; ownership; rollback em erro.
"""
import pytest

from app.models.models import (
    Canal, Ingrediente, Produto, ProdutoMassa, ProdutoPreco, Receita, User,
)
from tests.db import TestingSession


@pytest.fixture(scope="module")
def auth(client):
    r = client.post("/auth/register", json={
        "nome": "Assist", "email": "assistente@test.com", "senha": "senha12345",
    })
    assert r.status_code == 201, r.text
    # marca como pago: estes testes criam vários produtos (não são sobre freemium)
    db = TestingSession()
    u = db.query(User).filter(User.email == "assistente@test.com").first()
    u.assinatura_status = "ativa"
    db.commit()
    db.close()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _payload(**over):
    base = {
        "nome": "Bolo de Cenoura",
        "tipo": "Massa",
        "rendimento_g": 1000,
        "porcoes": 10,
        "margem_pct": 50,
        "etapas_mo": [{"descricao": "Assar", "tempo_min": 60}],
        "ingredientes": [
            # açúcar: 1 kg por R$ 5 → 0,005/g; usa 360 g
            {"nome": "açúcar refinado", "quantidade": 360, "unidade": "kg",
             "preco": 5.0, "quantidade_embalagem": 1},
            # ovo: 12 un por R$ 9 → 0,75/un; usa 3 un (contagem)
            {"nome": "ovo", "quantidade": 3, "unidade": "unid",
             "preco": 9.0, "quantidade_embalagem": 12},
        ],
    }
    base.update(over)
    return base


def test_salvar_cria_tudo(client, auth):
    r = client.post("/assistente/salvar", headers=auth, json=_payload())
    assert r.status_code == 201, r.text
    body = r.json()
    produto_id = body["produto_id"]

    db = TestingSession()
    try:
        # ingredientes criados
        assert db.query(Ingrediente).filter(Ingrediente.nome == "açúcar refinado").count() == 1
        ovo = db.query(Ingrediente).filter(Ingrediente.nome == "ovo").first()
        assert ovo.unidade.value == "unid"
        # receita + produto + preço
        assert db.query(Receita).filter(Receita.id == body["receita_id"]).first() is not None
        assert db.query(Produto).filter(Produto.id == produto_id).first() is not None
        pm = db.query(ProdutoMassa).filter(ProdutoMassa.produto_id == produto_id).first()
        # produto = 1 unidade: rendimento/porcoes = 1000/10 = 100g de receita
        assert pm.quantidade_g == 100
        pp = db.query(ProdutoPreco).filter(ProdutoPreco.produto_id == produto_id).first()
        assert pp.margem_pct == 50
        canal = db.query(Canal).filter(Canal.id == pp.canal_id).first()
        assert canal.nome == "Venda direta"
        assert canal.taxa_plataforma_pct == 0
    finally:
        db.close()


def test_custo_produto_por_porcao_e_ovo_por_contagem(client, auth):
    """Custo da receita: açúcar 360g×0,005 = 1,80 + ovo 3×0,75 = 2,25 → 4,05 MP.
    MO: 60min × valor_hora_padrao (0 p/ conta nova) = 0.
    Produto = 1/10 da receita → custo ≈ 0,405."""
    r = client.post("/assistente/salvar", headers=auth, json=_payload(nome="Bolo B"))
    produto_id = r.json()["produto_id"]
    det = client.get(f"/produtos/{produto_id}", headers=auth)
    assert det.status_code == 200, det.text
    custo = det.json()["custo_total"]
    assert abs(custo - 0.405) < 0.01, custo


def test_salvar_reusa_ingrediente_existente(client, auth):
    # cria um ingrediente antes
    ing = client.post("/ingredientes/", headers=auth, json={
        "nome": "leite", "unidade": "ml", "fator_correcao": 1.0,
    }).json()
    payload = _payload(nome="Bolo C", ingredientes=[
        {"nome": "leite", "quantidade": 200, "ingrediente_id": ing["id"]},
    ])
    r = client.post("/assistente/salvar", headers=auth, json=payload)
    assert r.status_code == 201, r.text
    db = TestingSession()
    try:
        assert db.query(Ingrediente).filter(Ingrediente.nome == "leite").count() == 1  # não duplicou
    finally:
        db.close()


def test_salvar_ingrediente_de_outro_usuario_404(client, auth):
    # ingrediente de outro tenant
    outro = client.post("/auth/register", json={
        "nome": "Outro", "email": "outro@test.com", "senha": "senha12345",
    }).json()
    ing_outro = client.post("/ingredientes/", headers={"Authorization": f"Bearer {outro['access_token']}"},
                            json={"nome": "secreto", "unidade": "g", "fator_correcao": 1.0}).json()
    payload = _payload(nome="Bolo D", ingredientes=[
        {"nome": "secreto", "quantidade": 100, "ingrediente_id": ing_outro["id"]},
    ])
    r = client.post("/assistente/salvar", headers=auth, json=payload)
    assert r.status_code == 404


def test_salvar_exige_auth(client):
    r = client.post("/assistente/salvar", json=_payload())
    assert r.status_code == 401
