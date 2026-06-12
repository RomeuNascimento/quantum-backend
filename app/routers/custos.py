"""Cálculo de custo unitário a partir de um registro de preço.

Fonte única da fórmula — antes havia 4 implementações espalhadas por
ingredientes/embalagens/receitas/produtos com variações sutis (`== 0` vs `> 0`).
"""
from app.routers.unidades import fator_unidade


def preco_mais_recente(precos):
    """Registro de preço mais recente (ou None)."""
    return max(precos, key=lambda p: p.data_compra) if precos else None


def custo_unitario_de_preco(p, unidade=None, fator_correcao=None) -> float:
    """Custo por g/ml/unid de um registro de preço de INGREDIENTE.

    `(preco / (qtd_embalagem × fator_unidade)) / fator_correcao` — kg/L viram
    g/ml via fator_unidade; fator_correcao inválido (None/0/negativo) vira 1.
    """
    if p is None or not p.quantidade_embalagem or p.quantidade_embalagem <= 0:
        return 0.0
    base = p.quantidade_embalagem * fator_unidade(unidade)
    fc = fator_correcao if fator_correcao and fator_correcao > 0 else 1.0
    return (p.preco / base) / fc


def custo_unitario_embalagem_de_preco(p) -> float:
    """Custo por unidade de um registro de preço de EMBALAGEM."""
    if p is None or not p.quantidade_embalagem or p.quantidade_embalagem <= 0:
        return 0.0
    return p.preco / p.quantidade_embalagem
