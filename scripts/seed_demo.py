"""Popula uma conta de demonstração com dados realistas de confeitaria.

Cria ingredientes com HISTÓRICO de preços (datas espalhadas em ~3 meses,
com aumentos), embalagens, receitas, produtos e precificação — o suficiente
para os gráficos de evolução de custo e o relatório de margem terem conteúdo.

Uso:
    python scripts/seed_demo.py                          # produção
    python scripts/seed_demo.py http://localhost:8000    # API local

Conta criada: demo@quantumcalc.com.br / senha demo12345
(idempotente: se a conta já existe, faz login e adiciona por cima)
"""
import sys
from datetime import datetime, timedelta

import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://api.quantumcalc.com.br"
EMAIL = "demo@quantumcalc.com.br"
SENHA = "demo12345"

s = requests.Session()


def login_ou_registra():
    r = s.post(f"{BASE}/auth/register", json={"nome": "Conta Demo", "email": EMAIL, "senha": SENHA})
    if r.status_code not in (200, 201):
        r = s.post(f"{BASE}/auth/login", json={"email": EMAIL, "senha": SENHA})
        r.raise_for_status()
    token = r.json()["access_token"]
    s.headers["Authorization"] = f"Bearer {token}"
    print(f"autenticado em {BASE} como {EMAIL}")


def dias_atras(n):
    return (datetime.utcnow() - timedelta(days=n)).isoformat()


def cria_ingrediente(nome, unidade, fator, precos):
    """precos: lista de (preco, qtd_embalagem, dias_atras)"""
    p0 = precos[0]
    r = s.post(f"{BASE}/ingredientes", json={
        "nome": nome, "unidade": unidade, "fator_correcao": fator,
        "preco_inicial": {"preco": p0[0], "quantidade_embalagem": p0[1], "data_compra": dias_atras(p0[2])},
    })
    r.raise_for_status()
    ing_id = r.json()["id"]
    for preco, qtd, dias in precos[1:]:
        s.post(f"{BASE}/ingredientes/{ing_id}/precos", json={
            "preco": preco, "quantidade_embalagem": qtd, "data_compra": dias_atras(dias),
        }).raise_for_status()
    print(f"  ingrediente: {nome} ({len(precos)} preços)")
    return ing_id


def cria_embalagem(nome, unidade, precos):
    p0 = precos[0]
    r = s.post(f"{BASE}/embalagens", json={
        "nome": nome, "unidade": unidade,
        "preco_inicial": {"preco": p0[0], "quantidade_embalagem": p0[1], "data_compra": dias_atras(p0[2])},
    })
    r.raise_for_status()
    emb_id = r.json()["id"]
    for preco, qtd, dias in precos[1:]:
        s.post(f"{BASE}/embalagens/{emb_id}/precos", json={
            "preco": preco, "quantidade_embalagem": qtd, "data_compra": dias_atras(dias),
        }).raise_for_status()
    print(f"  embalagem: {nome}")
    return emb_id


def main():
    login_ou_registra()

    print("ingredientes…")
    farinha = cria_ingrediente("Farinha de trigo", "g", 1.0, [(4.50, 1000, 90), (4.90, 1000, 60), (5.40, 1000, 30), (5.80, 1000, 7)])
    acucar = cria_ingrediente("Açúcar refinado", "g", 1.0, [(3.80, 1000, 85), (4.10, 1000, 45), (4.50, 1000, 10)])
    chocolate = cria_ingrediente("Chocolate em pó 50%", "g", 1.0, [(18.90, 500, 80), (21.50, 500, 40), (24.90, 500, 5)])
    manteiga = cria_ingrediente("Manteiga sem sal", "g", 1.0, [(9.90, 200, 75), (11.50, 200, 35), (12.90, 200, 8)])
    ovo = cria_ingrediente("Ovo", "unid", 0.88, [(14.90, 30, 70), (16.50, 30, 30), (17.90, 30, 6)])
    leite_cond = cria_ingrediente("Leite condensado", "g", 1.0, [(6.50, 395, 88), (7.20, 395, 50), (7.90, 395, 12)])
    creme = cria_ingrediente("Creme de leite", "g", 1.0, [(3.90, 200, 82), (4.40, 200, 41), (4.80, 200, 9)])

    print("embalagens…")
    caixa = cria_embalagem("Caixa para bolo 25cm", "unid", [(2.80, 10, 80), (3.20, 10, 20)])
    forminha = cria_embalagem("Forminha brigadeiro nº4", "unid", [(8.90, 100, 70), (9.90, 100, 15)])

    print("receitas…")
    r = s.post(f"{BASE}/receitas", json={
        "nome": "Massa de chocolate", "tipo": "Base", "rendimento_g": 1200,
        "ingredientes": [
            {"ingrediente_id": farinha, "quantidade_g": 400},
            {"ingrediente_id": acucar, "quantidade_g": 300},
            {"ingrediente_id": chocolate, "quantidade_g": 150},
            {"ingrediente_id": manteiga, "quantidade_g": 200},
            {"ingrediente_id": ovo, "quantidade_g": 4},
        ],
        "etapas_mo": [
            {"descricao": "Preparar e assar a massa", "tempo_min": 45},
        ],
    })
    r.raise_for_status()
    massa = r.json()["id"]
    print("  receita: Massa de chocolate")

    r = s.post(f"{BASE}/receitas", json={
        "nome": "Brigadeiro de panela", "tipo": "Recheio", "rendimento_g": 600,
        "ingredientes": [
            {"ingrediente_id": leite_cond, "quantidade_g": 395},
            {"ingrediente_id": creme, "quantidade_g": 100},
            {"ingrediente_id": chocolate, "quantidade_g": 80},
            {"ingrediente_id": manteiga, "quantidade_g": 30},
        ],
        "etapas_mo": [
            {"descricao": "Cozinhar até ponto de enrolar", "tempo_min": 25},
        ],
    })
    r.raise_for_status()
    brigadeiro = r.json()["id"]
    print("  receita: Brigadeiro de panela")

    print("produtos…")
    r = s.post(f"{BASE}/produtos", json={
        "nome": "Bolo de chocolate com brigadeiro",
        "preparacoes": [
            {"receita_id": massa, "quantidade_g": 900},
            {"receita_id": brigadeiro, "quantidade_g": 400},
        ],
        "ingredientes": [],
        "embalagens": [{"embalagem_id": caixa, "quantidade": 1}],
        "mo_montagem": [{"descricao": "Montagem e decoração", "tempo_min": 20}],
    })
    r.raise_for_status()
    bolo = r.json()["id"]
    print("  produto: Bolo de chocolate com brigadeiro")

    r = s.post(f"{BASE}/produtos", json={
        "nome": "Brigadeiro gourmet (cento)",
        "preparacoes": [{"receita_id": brigadeiro, "quantidade_g": 1500}],
        "ingredientes": [],
        "embalagens": [{"embalagem_id": forminha, "quantidade": 100}],
        "mo_montagem": [{"descricao": "Enrolar e embalar", "tempo_min": 60}],
    })
    r.raise_for_status()
    cento = r.json()["id"]
    print("  produto: Brigadeiro gourmet (cento)")

    print("precificação…")
    canais = s.get(f"{BASE}/precificacao/canais").json()
    ifood = next((c["id"] for c in canais if "ifood" in c["nome"].lower()), None)
    encomenda = next((c["id"] for c in canais if "encomenda" in c["nome"].lower()), None)
    if encomenda is None:
        r = s.post(f"{BASE}/precificacao/canais", json={
            "nome": "Encomenda direta", "taxa_plataforma_pct": 0, "taxa_cartao_pct": 2.99, "imposto_pct": 6,
        })
        r.raise_for_status()
        encomenda = r.json()["id"]
    print("  canais ok")

    # Bolo: margem saudável na encomenda, margem corroída no iFood (preço final baixo
    # de propósito para acionar o alerta do Dashboard e o "Revisar" do relatório)
    s.post(f"{BASE}/precificacao/produtos/{bolo}/precos", json={"canal_id": encomenda, "margem_pct": 35}).raise_for_status()
    if ifood:
        s.post(f"{BASE}/precificacao/produtos/{bolo}/precos", json={"canal_id": ifood, "margem_pct": 30, "preco_final": 44.0}).raise_for_status()
    # Cento: margem média
    s.post(f"{BASE}/precificacao/produtos/{cento}/precos", json={"canal_id": encomenda, "margem_pct": 18}).raise_for_status()
    print("  preços ok")

    print("custos fixos…")
    for nome, valor in [("Aluguel da cozinha", 800.0), ("Energia elétrica", 350.0), ("Internet", 99.90), ("MEI", 75.90)]:
        s.post(f"{BASE}/custos-fixos", json={"nome": nome, "valor": valor, "periodo": "mensal"})
    print("  custos fixos ok")

    print(f"\npronto! login: {EMAIL} / {SENHA}")


if __name__ == "__main__":
    main()
