"""Colunas monetárias/quantitativas: FLOAT (double precision) → NUMERIC(12,4)

M1 da auditoria 2026-06-11. Em PostgreSQL a conversão float → numeric é um cast
implícito (assignment), então USING não é necessário — o ALTER TYPE converte e
arredonda para 4 casas decimais direto.

Revision ID: 005
Revises: 004
Create Date: 2026-06-12

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NUMERIC = sa.Numeric(12, 4)
FLOAT = sa.Float()

# (tabela, coluna, nullable)
COLUNAS = [
    ("configuracoes", "valor_hora_padrao", True),
    ("colaboradores", "valor_hora", False),
    ("ingredientes", "fator_correcao", True),
    ("ingrediente_precos", "preco", False),
    ("ingrediente_precos", "quantidade_embalagem", False),
    ("embalagem_precos", "preco", False),
    ("embalagem_precos", "quantidade_embalagem", False),
    ("receitas", "rendimento_g", False),
    ("receita_ingredientes", "quantidade_g", False),
    ("receita_mo_etapas", "tempo_min", False),
    ("produto_massas", "quantidade_g", False),
    ("produto_recheios", "quantidade_g", False),
    ("produto_ingredientes", "quantidade_g", False),
    ("produto_embalagens", "quantidade", False),
    ("produto_mo_montagem", "tempo_min", False),
    ("canais", "taxa_plataforma_pct", True),
    ("canais", "taxa_cartao_pct", True),
    ("canais", "imposto_pct", True),
    ("produto_precos", "margem_pct", False),
    ("produto_precos", "preco_final", True),
    ("custos_fixos", "valor", False),
]


def upgrade() -> None:
    for tabela, coluna, nullable in COLUNAS:
        op.alter_column(
            tabela,
            coluna,
            type_=NUMERIC,
            existing_type=FLOAT,
            existing_nullable=nullable,
        )


def downgrade() -> None:
    for tabela, coluna, nullable in reversed(COLUNAS):
        op.alter_column(
            tabela,
            coluna,
            type_=FLOAT,
            existing_type=NUMERIC,
            existing_nullable=nullable,
        )
